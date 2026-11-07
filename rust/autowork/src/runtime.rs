//! Owned-agent wire contracts. Native confirmations and reply channels stay local.
use std::collections::{BTreeMap, BTreeSet};
use std::future::Future;
use std::io::{Read, Write};
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::{Component, Path, PathBuf};
use std::pin::Pin;
use std::process::Stdio;
use std::sync::{Arc, Mutex};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use tokio::io::{AsyncBufReadExt, AsyncReadExt, AsyncWriteExt, BufReader};
use tokio::sync::mpsc::Receiver;
use tokio::sync::{mpsc, watch};

use native_agent::{
    Agent, AgentConfig, AgentEvent, CancellationToken, CoreTools, EffectBroker, ExtensionHost,
    FinishReason, SandboxConfig, Session, ToolCallHook, ToolContext, ToolError, ToolProgress,
};

use crate::{CONTRACT_VERSION, Result, Unavailable};

pub use octet_agent as native_agent;
pub use octet_ai as native_ai;

pub const MAX_REQUEST_BYTES: usize = 1024 * 1024;
pub const MAX_EVENT_BYTES: usize = 16 * 1024;
pub const ROLES: [Role; 3] = [Role::Worker, Role::Reviewer, Role::Planner];

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Role {
    Worker,
    Reviewer,
    Planner,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WorkspaceIdentity {
    pub canonical_path: PathBuf,
    pub device: u64,
    pub inode: u64,
}

/// Host-issued, frozen authority, never a model proposal. Runtime must validate
/// identities, normalized paths, aliases and current generation before use.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExecutionAdmission {
    pub repo_id: String,
    pub repository: WorkspaceIdentity,
    pub workspace: WorkspaceIdentity,
    pub task_id: String,
    pub attempt_id: String,
    pub generation: u64,
    pub contract_hash: String,
    pub role: Role,
    pub allowed_write_paths: Vec<PathBuf>,
    /// Must include tasks/, BLOCKERS.md, TODO.archive.md, CHANGELOG.md,
    /// all .git files/directories and resolved common Git/runtime state roots.
    /// These denies take precedence over allowed writes, including via symlinks.
    pub denied_paths: Vec<PathBuf>,
    pub admitted_check_operation_ids: Vec<String>,
}

/// Coordinator-authored registry entry, frozen before dispatch. Models may name
/// an admitted ID only; executable identity, source and argv are not model input.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CheckOperationSpec {
    pub operation_id: String,
    pub executable: PathBuf,
    pub executable_sha256: String,
    pub implementation_id: String,
    pub source_revision: String,
    pub argv: Vec<String>,
    pub cwd: PathBuf,
    /// The complete permitted environment, not additions to inherited secrets.
    pub environment_allowlist: BTreeMap<String, String>,
    pub timeout_ms: u64,
    pub max_output_bytes: u64,
    pub receipt_id: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentRequest {
    pub schema_version: u32,
    pub repo_id: String,
    pub task_id: String,
    pub attempt_id: String,
    pub generation: u64,
    pub role: Role,
    pub workspace: PathBuf,
    /// Configuration reference only: never a credential value.
    pub model_ref: String,
    pub contract_hash: String,
    pub source_revision: String,
    pub prompt: String,
    pub admission: ExecutionAdmission,
    pub check_operations: Vec<CheckOperationSpec>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RunIdentity {
    pub repo_id: String,
    pub task_id: String,
    pub attempt_id: String,
    pub generation: u64,
    pub role: Role,
    pub contract_hash: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeStatus {
    Running,
    Succeeded,
    Failed,
    Cancelled,
    Unavailable,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentResult {
    pub schema_version: u32,
    pub identity: RunIdentity,
    pub status: RuntimeStatus,
    pub evidence_ref: Option<String>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeEventKind {
    Accepted,
    Progress,
    Usage,
    Outcome,
}

/// Schema-1 projection, not serialization of Octet AgentEvent or reply channels.
/// Evidence is a secret-free reference; no raw prompts, credentials or env dumps.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeEvent {
    pub schema_version: u32,
    pub repo_id: String,
    pub operation_id: String,
    pub task_id: String,
    pub attempt_id: String,
    pub generation: u64,
    pub contract_hash: String,
    pub source_revision: String,
    pub role: Role,
    pub event: RuntimeEventKind,
    pub status: RuntimeStatus,
    pub evidence_ref: Option<String>,
    pub timestamp: String,
}

impl RuntimeEvent {
    /// The owned child must use this bounded projection for each JSONL record.
    pub fn to_json_line(&self) -> std::io::Result<Vec<u8>> {
        use std::io::{Error, ErrorKind, Write};
        // A bounded writer prevents oversized strings from allocating a full JSON copy.
        struct Bounded(Vec<u8>);
        impl Write for Bounded {
            fn write(&mut self, bytes: &[u8]) -> std::io::Result<usize> {
                if bytes.len() > MAX_EVENT_BYTES - 1 - self.0.len() {
                    return Err(Error::new(
                        ErrorKind::InvalidData,
                        "runtime event exceeds limit",
                    ));
                }
                self.0.extend_from_slice(bytes);
                Ok(bytes.len())
            }
            fn flush(&mut self) -> std::io::Result<()> {
                Ok(())
            }
        }
        if self.schema_version != CONTRACT_VERSION {
            return Err(Error::new(
                ErrorKind::InvalidData,
                "unsupported runtime event schema",
            ));
        }
        let mut writer = Bounded(Vec::new());
        serde_json::to_writer(&mut writer, self)?;
        writer.0.push(b'\n');
        Ok(writer.0)
    }
}

/// Explicit host configuration, selected by model_ref, not by prompt text.
/// Only OpenAI Chat-compatible routes are supported in this first slice.
#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelRoute {
    pub provider: String,
    pub model: String,
    pub base_url: String,
    /// Private regular file outside the workspace; resolved only in the child.
    pub secret_file: Option<PathBuf>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OwnedProcess {
    pub identity: RunIdentity,
    pub pid: u32,
    /// Linux /proc starttime, not a PID-only adoption or signalling capability.
    pub birth_ticks: u64,
    pub evidence_dir: PathBuf,
}

struct OwnedRun {
    process: OwnedProcess,
    cancel: CancellationToken,
    reaped: watch::Receiver<bool>,
}

/// One runtime owner per coordinator. Generations are monotonic per task even
/// after reaping; a different attempt cannot consume this child's terminal event.
pub struct Runtime {
    executable: PathBuf,
    evidence_root: PathBuf,
    models: BTreeMap<String, ModelRoute>,
    timeout: Duration,
    runs: Mutex<BTreeMap<(String, String), OwnedRun>>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct ChildConfig {
    route: ModelRoute,
    evidence_dir: PathBuf,
    operation_id: String,
    timeout_ms: u64,
}

fn refused<T>() -> Result<T> {
    Err(Unavailable("runtime admission refused"))
}

fn io_result<T>(value: std::io::Result<T>) -> Result<T> {
    value.map_err(|_| Unavailable("runtime I/O"))
}

impl AgentRequest {
    pub fn identity(&self) -> RunIdentity {
        RunIdentity {
            repo_id: self.repo_id.clone(),
            task_id: self.task_id.clone(),
            attempt_id: self.attempt_id.clone(),
            generation: self.generation,
            role: self.role,
            contract_hash: self.contract_hash.clone(),
        }
    }

    fn event(
        &self,
        operation: &str,
        kind: RuntimeEventKind,
        status: RuntimeStatus,
    ) -> RuntimeEvent {
        RuntimeEvent {
            schema_version: CONTRACT_VERSION,
            repo_id: self.repo_id.clone(),
            operation_id: operation.into(),
            task_id: self.task_id.clone(),
            attempt_id: self.attempt_id.clone(),
            generation: self.generation,
            contract_hash: self.contract_hash.clone(),
            source_revision: self.source_revision.clone(),
            role: self.role,
            event: kind,
            status,
            evidence_ref: Some(operation.into()),
            timestamp: now_millis().to_string(),
        }
    }

    fn validate(&self) -> Result<()> {
        let a = &self.admission;
        let ids = [
            &self.repo_id,
            &self.task_id,
            &self.attempt_id,
            &self.contract_hash,
            &self.source_revision,
            &self.model_ref,
        ];
        if self.schema_version != CONTRACT_VERSION
            || self.generation == 0
            || ids.iter().any(|s| {
                s.is_empty()
                    || s.len() > 128
                    || !s
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b"._:-".contains(&b))
            })
            || self.repo_id != a.repo_id
            || self.task_id != a.task_id
            || self.attempt_id != a.attempt_id
            || self.generation != a.generation
            || self.contract_hash != a.contract_hash
            || self.role != a.role
            || self.workspace != a.workspace.canonical_path
        {
            return refused();
        }
        a.validate_roots()?;
        for path in &a.allowed_write_paths {
            if !normalized_relative(path) {
                return refused();
            }
        }
        // Check execution belongs to the coordinator, never to a model shell.
        // Carry registry entries as data; they do not install tools here.
        Ok(())
    }
}

impl WorkspaceIdentity {
    fn validate(&self) -> Result<()> {
        let meta = io_result(std::fs::symlink_metadata(&self.canonical_path))?;
        if !meta.is_dir()
            || io_result(self.canonical_path.canonicalize())? != self.canonical_path
            || meta.dev() != self.device
            || meta.ino() != self.inode
        {
            return refused();
        }
        Ok(())
    }
}

fn normalized_relative(path: &Path) -> bool {
    !path.as_os_str().is_empty()
        && path.components().all(|c| matches!(c, Component::Normal(_)))
        && path.to_str().is_some_and(|s| {
            !s.starts_with('~')
                && !s.contains('\\')
                && !s.contains('\0')
                && s.split('/').all(|p| !p.is_empty() && p != "." && p != "..")
        })
}

impl ExecutionAdmission {
    fn validate_roots(&self) -> Result<()> {
        self.repository.validate()?;
        self.workspace.validate()
    }

    /// Reject lexical escapes, symlinks, hard-link aliases and protected paths
    /// before the native workspace resolver and secure mutation implementation.
    fn path(&self, path: &Path, mutation: bool) -> Result<()> {
        self.validate_roots()?;
        if !normalized_relative(path)
            || (mutation
                && (self.role != Role::Worker
                    || !self
                        .allowed_write_paths
                        .iter()
                        .any(|allowed| allowed == path)))
        {
            return refused();
        }
        let forbidden = [
            "tasks",
            "BLOCKERS.md",
            "TODO.archive.md",
            "CHANGELOG.md",
            ".git",
        ];
        if path
            .components()
            .any(|c| forbidden.iter().any(|p| c.as_os_str() == *p))
        {
            return refused();
        }
        let target = self.workspace.canonical_path.join(path);
        let mut denied = self.denied_paths.clone();
        // Derive Git/common roots as well: an incomplete envelope cannot grant them.
        for root in [
            &self.repository.canonical_path,
            &self.workspace.canonical_path,
        ] {
            let git = root.join(".git");
            denied.push(git.clone());
            let git_dir = if git.is_file() {
                std::fs::read_to_string(&git)
                    .ok()
                    .and_then(|s| s.trim().strip_prefix("gitdir: ").map(|p| root.join(p)))
            } else {
                Some(git)
            };
            if let Some(dir) = git_dir.and_then(|p| p.canonicalize().ok()) {
                if let Ok(common) = std::fs::read_to_string(dir.join("commondir")) {
                    denied.push(
                        dir.join(common.trim())
                            .canonicalize()
                            .unwrap_or_else(|_| dir.clone()),
                    );
                }
                denied.push(dir);
            }
        }
        for deny in denied {
            let deny = if deny.is_absolute() {
                deny
            } else {
                self.workspace.canonical_path.join(deny)
            };
            if target.starts_with(&deny) {
                return refused();
            }
            if let Ok(real) = deny.canonicalize() {
                if target.starts_with(real) {
                    return refused();
                }
            }
        }
        let mut cursor = self.workspace.canonical_path.clone();
        for part in path.components() {
            cursor.push(part);
            match std::fs::symlink_metadata(&cursor) {
                Ok(meta)
                    if meta.file_type().is_symlink()
                        || (!meta.is_dir() && (!meta.is_file() || meta.nlink() != 1)) =>
                {
                    return refused();
                }
                Ok(_) => {}
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
                Err(_) => return refused(),
            }
        }
        Ok(())
    }
}

fn now_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
}

fn private_json(path: &Path, value: &impl Serialize) -> Result<()> {
    let mut file = io_result(
        std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(path),
    )?;
    let bytes = serde_json::to_vec(value).map_err(|_| Unavailable("runtime serialization"))?;
    io_result(file.write_all(&bytes))?;
    io_result(file.sync_all())
}

fn birth_ticks(pid: u32) -> Result<u64> {
    let stat = io_result(std::fs::read_to_string(format!("/proc/{pid}/stat")))?;
    stat.rsplit_once(") ")
        .and_then(|(_, fields)| fields.split_whitespace().nth(19))
        .and_then(|s| s.parse().ok())
        .ok_or(Unavailable("runtime process identity"))
}

impl Runtime {
    pub fn new(
        executable: PathBuf,
        evidence_root: PathBuf,
        models: BTreeMap<String, ModelRoute>,
        timeout: Duration,
    ) -> Result<Self> {
        let executable = io_result(executable.canonicalize())?;
        let evidence_root = io_result(evidence_root.canonicalize())?;
        if timeout.is_zero() || timeout.as_millis() > u64::MAX as u128 {
            return refused();
        }
        Ok(Self {
            executable,
            evidence_root,
            models,
            timeout,
            runs: Mutex::new(BTreeMap::new()),
        })
    }

    pub fn owned_process(&self, identity: &RunIdentity) -> Option<OwnedProcess> {
        self.runs
            .lock()
            .ok()?
            .get(&(identity.repo_id.clone(), identity.task_id.clone()))
            .filter(|r| r.process.identity == *identity)
            .map(|r| r.process.clone())
    }

    pub async fn run(&self, request: AgentRequest) -> Result<Receiver<RuntimeEvent>> {
        request.validate()?;
        if self.evidence_root.starts_with(&request.workspace) {
            return refused();
        }
        let route = self
            .models
            .get(&request.model_ref)
            .ok_or(Unavailable("runtime model reference"))?
            .clone();
        let identity = request.identity();
        let key = (identity.repo_id.clone(), identity.task_id.clone());
        let mut runs = self
            .runs
            .lock()
            .map_err(|_| Unavailable("runtime ownership"))?;
        if runs.get(&key).is_some_and(|r| {
            !*r.reaped.borrow() || r.process.identity.generation >= identity.generation
        }) {
            return refused();
        }
        // Exclusive creation, not task/model text, supplies the operation namespace.
        let operation_id = format!(
            "run-{}-{}-{}",
            std::process::id(),
            now_millis(),
            NEXT_OPERATION.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
        );
        let evidence_dir = self.evidence_root.join(&operation_id);
        io_result(std::fs::DirBuilder::new().mode(0o700).create(&evidence_dir))?;
        private_json(&evidence_dir.join("authority.json"), &identity)?;
        private_json(
            &evidence_dir.join("uncertainty.json"),
            &serde_json::json!({
                "identity": identity, "state": "dispatch_intent", "reconcile_before_retry": true
            }),
        )?;
        let config = ChildConfig {
            route,
            evidence_dir: evidence_dir.clone(),
            operation_id: operation_id.clone(),
            timeout_ms: self.timeout.as_millis() as u64,
        };
        let mut input = serde_json::to_vec(&request).map_err(|_| Unavailable("runtime request"))?;
        if input.len() + 1 > MAX_REQUEST_BYTES {
            return refused();
        }
        input.push(b'\n');
        let config = serde_json::to_string(&config).map_err(|_| Unavailable("runtime config"))?;
        let child = io_result(
            tokio::process::Command::new(&self.executable)
                .arg("internal-agent")
                .env_clear()
                .env("AUTOWORK_OWNED_CONFIG", config)
                .current_dir(&request.workspace)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .kill_on_drop(true)
                .spawn(),
        )?;
        let pid = child.id().ok_or(Unavailable("runtime child"))?;
        let process = OwnedProcess {
            identity,
            pid,
            birth_ticks: birth_ticks(pid)?,
            evidence_dir: evidence_dir.clone(),
        };
        private_json(&evidence_dir.join("owner.json"), &process)?;
        let cancel = CancellationToken::default();
        let (done, reaped) = watch::channel(false);
        let (tx, rx) = mpsc::channel(64);
        let cancel_run = cancel.clone();
        runs.insert(
            key,
            OwnedRun {
                process,
                cancel,
                reaped,
            },
        );
        let timeout = self.timeout;
        tokio::spawn(async move {
            supervise(
                child,
                input,
                request,
                operation_id,
                evidence_dir,
                timeout,
                cancel_run,
                tx,
            )
            .await;
            let _ = done.send(true);
        });
        Ok(rx)
    }

    /// Revoke admission before signalling; wait for this exact Child handle to
    /// be reaped. Never signal a process discovered by PID or a process group.
    pub async fn cancel(&self, identity: RunIdentity) -> Result<()> {
        let mut reaped = {
            let runs = self
                .runs
                .lock()
                .map_err(|_| Unavailable("runtime ownership"))?;
            let owned = runs
                .get(&(identity.repo_id.clone(), identity.task_id.clone()))
                .filter(|r| r.process.identity == identity)
                .ok_or(Unavailable("runtime stale identity"))?;
            let _ = std::fs::remove_file(owned.process.evidence_dir.join("authority.json"));
            owned.cancel.cancel();
            owned.reaped.clone()
        };
        while !*reaped.borrow_and_update() {
            reaped
                .changed()
                .await
                .map_err(|_| Unavailable("runtime reap"))?;
        }
        Ok(())
    }
}

impl Drop for Runtime {
    fn drop(&mut self) {
        if let Ok(runs) = self.runs.lock() {
            for owned in runs.values() {
                let _ = std::fs::remove_file(owned.process.evidence_dir.join("authority.json"));
                owned.cancel.cancel();
            }
        }
    }
}

static NEXT_OPERATION: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);

async fn bounded_line(
    reader: &mut BufReader<tokio::process::ChildStdout>,
) -> std::io::Result<Option<Vec<u8>>> {
    let mut line = Vec::new();
    loop {
        let bytes = reader.fill_buf().await?;
        if bytes.is_empty() {
            return if line.is_empty() {
                Ok(None)
            } else {
                Err(std::io::ErrorKind::InvalidData.into())
            };
        }
        let count = bytes
            .iter()
            .position(|b| *b == b'\n')
            .map_or(bytes.len(), |p| p + 1);
        if line.len() + count > MAX_EVENT_BYTES {
            return Err(std::io::ErrorKind::InvalidData.into());
        }
        let complete = bytes[count - 1] == b'\n';
        line.extend_from_slice(&bytes[..count]);
        reader.consume(count);
        if complete {
            return Ok(Some(line));
        }
    }
}

async fn supervise(
    mut child: tokio::process::Child,
    input: Vec<u8>,
    request: AgentRequest,
    operation: String,
    evidence: PathBuf,
    timeout: Duration,
    cancel: CancellationToken,
    tx: mpsc::Sender<RuntimeEvent>,
) {
    let mut stdin = child.stdin.take().expect("owned stdin");
    let mut stdout = BufReader::new(child.stdout.take().expect("owned stdout"));
    // Payloads are deliberately discarded, including provider errors and panic text.
    let mut stderr = child.stderr.take().expect("owned stderr");
    let drain = tokio::spawn(async move {
        let mut buf = [0u8; 4096];
        let mut discarded_bytes = 0u64;
        while let Ok(n) = stderr.read(&mut buf).await {
            if n == 0 {
                break;
            }
            discarded_bytes = discarded_bytes.saturating_add(n as u64);
        }
        discarded_bytes
    });
    let mut terminal = None;
    let mut count = 0;
    let mut stopped = false;
    let deadline = tokio::time::sleep(timeout + Duration::from_secs(2));
    let result = async {
        stdin.write_all(&input).await?;
        loop {
            let Some(line) = bounded_line(&mut stdout).await? else {
                break;
            };
            count += 1;
            if count > 4096 {
                return Err(std::io::ErrorKind::InvalidData.into());
            }
            let event: RuntimeEvent = serde_json::from_slice(&line)?;
            let expected = request.event(&operation, event.event, event.status);
            if event.schema_version != CONTRACT_VERSION
                || event.repo_id != expected.repo_id
                || event.task_id != expected.task_id
                || event.attempt_id != expected.attempt_id
                || event.generation != expected.generation
                || event.contract_hash != expected.contract_hash
                || event.source_revision != expected.source_revision
                || event.role != expected.role
                || event.operation_id != operation
                || event.evidence_ref != expected.evidence_ref
                || terminal.is_some()
            {
                return Err(std::io::ErrorKind::InvalidData.into());
            }
            // Reconstruct rather than forwarding any child-supplied free text.
            if event.event == RuntimeEventKind::Outcome {
                terminal = Some(event.status);
            } else if tx.capacity() > 1 {
                let _ = tx.try_send(expected);
            }
        }
        child.wait().await
    };
    // The native child has its own deadline. This outer limit also covers
    // malformed/stuck children that never open or finish their native stream.
    let result = tokio::select! {
        biased;
        _ = deadline => { stopped = true; None },
        result = result => Some(result),
        _ = cancel.cancelled() => { stopped = true; None },
        _ = tx.closed() => { stopped = true; None },
    };
    let status = if let Some(Ok(exit)) = result {
        if cancel.is_cancelled() || !evidence.join("authority.json").exists() {
            RuntimeStatus::Cancelled
        } else if exit.success() {
            terminal.unwrap_or(RuntimeStatus::Failed)
        } else {
            RuntimeStatus::Failed
        }
    } else {
        let _ = std::fs::remove_file(evidence.join("authority.json"));
        // EOF revokes the child too. Never await a control write to a pipe
        // that may already be full from interrupted request delivery.
        drop(stdin);
        if tokio::time::timeout(Duration::from_secs(2), child.wait())
            .await
            .is_err()
        {
            let _ = child.kill().await;
        }
        if stopped {
            RuntimeStatus::Cancelled
        } else {
            RuntimeStatus::Failed
        }
    };
    let _ = std::fs::remove_file(evidence.join("authority.json"));
    let discarded_bytes = drain.await.unwrap_or(0);
    let _ = private_json(
        &evidence.join("diagnostics.json"),
        &serde_json::json!({
            "stderr_bytes_discarded": discarded_bytes, "status": status,
            "payload_policy": "native diagnostics suppressed; inspect private session for reconciliation"
        }),
    );
    let outcome = request.event(&operation, RuntimeEventKind::Outcome, status);
    let _ = private_json(&evidence.join("outcome.json"), &outcome);
    let _ = tx.try_send(outcome);
}

#[derive(Clone)]
struct Authority {
    admission: ExecutionAdmission,
    identity: RunIdentity,
    lease: PathBuf,
    cancelled: CancellationToken,
    validated: Arc<Mutex<BTreeSet<String>>>,
}

#[derive(Deserialize)]
struct PathArgument {
    path: PathBuf,
}

impl Authority {
    fn current(&self) -> Result<()> {
        if self.cancelled.is_cancelled() {
            return refused();
        }
        let bytes =
            native_agent::secure_fs::read_private_file_bounded(&self.lease, MAX_EVENT_BYTES)
                .map_err(|_| Unavailable("runtime lease"))?;
        let identity: RunIdentity =
            serde_json::from_slice(&bytes).map_err(|_| Unavailable("runtime lease"))?;
        if identity != self.identity {
            return refused();
        }
        self.admission.validate_roots()
    }

    fn check(&self, name: &str, args: &serde_json::Value) -> Result<()> {
        self.current()?;
        if !matches!(name, "read" | "edit" | "write") {
            return refused();
        }
        let path: PathArgument =
            serde_json::from_value(args.clone()).map_err(|_| Unavailable("runtime path"))?;
        self.admission.path(&path.path, name != "read")
    }

    fn key(name: &str, args: &serde_json::Value) -> String {
        native_agent::tool::content_hash(format!("{name}:{args}").as_bytes())
    }

    fn confirm(&self, name: &str, args: &serde_json::Value) -> bool {
        matches!(name, "edit" | "write")
            && self.check(name, args).is_ok()
            && self
                .validated
                .lock()
                .is_ok_and(|mut v| v.remove(&Self::key(name, args)))
    }
}

// Match async-trait's public ABI without adding a dependency just for three hooks.
type HookFuture<'a, T> = Pin<Box<dyn Future<Output = T> + Send + 'a>>;
impl ToolCallHook for Authority {
    fn transform_tool_call<'a, 'b, 'c, 'd, 'e, 'f>(
        &'a self,
        name: &'b str,
        args: &'c serde_json::Value,
        _ctx: &'d ToolContext<'e>,
    ) -> HookFuture<'f, std::result::Result<Option<serde_json::Value>, ToolError>>
    where
        'a: 'f,
        'b: 'f,
        'c: 'f,
        'd: 'f,
        'e: 'f,
        Self: 'f,
    {
        Box::pin(async move {
            self.check(name, args)
                .map_err(|_| ToolError::new("task authority denied"))?;
            if name != "read" {
                self.validated
                    .lock()
                    .map_err(|_| ToolError::new("task authority denied"))?
                    .insert(Self::key(name, args));
            }
            Ok(None)
        })
    }

    fn before_tool_call<'a, 'b, 'c, 'd, 'e, 'f>(
        &'a self,
        name: &'b str,
        args: &'c serde_json::Value,
        _ctx: &'d ToolContext<'e>,
    ) -> HookFuture<'f, std::result::Result<(), ToolError>>
    where
        'a: 'f,
        'b: 'f,
        'c: 'f,
        'd: 'f,
        'e: 'f,
        Self: 'f,
    {
        Box::pin(async move {
            self.check(name, args)
                .map_err(|_| ToolError::new("task authority denied"))
        })
    }

    fn after_tool_call<'a, 'b, 'c, 'd, 'e, 'f, 'g>(
        &'a self,
        _name: &'b str,
        _args: &'c serde_json::Value,
        _output: &'d str,
        _is_error: bool,
        _ctx: &'e ToolContext<'f>,
    ) -> HookFuture<'g, ()>
    where
        'a: 'g,
        'b: 'g,
        'c: 'g,
        'd: 'g,
        'e: 'g,
        'f: 'g,
        Self: 'g,
    {
        Box::pin(async {})
    }
}

fn resolve_model(route: &ModelRoute, workspace: &Path) -> Result<native_ai::Model> {
    use native_ai::{Auth, Endpoint, EndpointId, Model, ModelSpec};
    if route.provider != "openai_chat" {
        return refused();
    }
    let url = route
        .base_url
        .parse()
        .map_err(|_| Unavailable("runtime provider URL"))?;
    let mut endpoint = Endpoint {
        id: EndpointId("owned-provider".into()),
        base_url: url,
        auth: Auth::None,
        default_headers: Default::default(),
        transport: Default::default(),
        runtime: Default::default(),
        timeout: Duration::from_secs(30),
    };
    if !endpoint.base_url.path().ends_with('/')
        || !endpoint.base_url.username().is_empty()
        || endpoint.base_url.password().is_some()
        || endpoint.base_url.query().is_some()
        || endpoint.base_url.fragment().is_some()
        || !(endpoint.base_url.scheme() == "https"
            || (endpoint.base_url.scheme() == "http"
                && matches!(endpoint.base_url.host_str(), Some("127.0.0.1" | "[::1]"))))
    {
        return refused();
    }
    if let Some(path) = &route.secret_file {
        let real = io_result(path.canonicalize())?;
        if real.starts_with(workspace) {
            return refused();
        }
        let bytes = native_agent::secure_fs::read_private_file_bounded(path, 4096)
            .map_err(|_| Unavailable("runtime credential reference"))?;
        let secret =
            String::from_utf8(bytes).map_err(|_| Unavailable("runtime credential reference"))?;
        if secret.trim().is_empty() {
            return refused();
        }
        endpoint.auth = Auth::Bearer(secret.trim().to_owned().into());
    }
    // No builtin catalog, auth store, provider discovery or user-global configuration.
    let spec: ModelSpec = serde_json::from_value(serde_json::json!({
        "id": "owned-model", "endpoint": "owned-provider", "api_name": route.model,
        "protocol": "open_ai_chat", "capabilities": { "input_modalities": {"bits": 0},
            "output_modalities": {"bits": 0}, "tools": true,
            "parallel_tool_calls": false, "reasoning": null, "structured_output": false },
        "limits": { "context_window": 32768, "max_output_tokens": 4096 }, "pricing": null
    }))
    .map_err(|_| Unavailable("runtime model config"))?;
    Ok(Model {
        spec: Arc::new(spec),
        endpoint: Arc::new(endpoint),
    })
}

fn emit(event: &RuntimeEvent) -> Result<()> {
    let bytes = io_result(event.to_json_line())?;
    io_result(std::io::stdout().lock().write_all(&bytes))?;
    io_result(std::io::stdout().lock().flush())
}

/// CLI-owned child. Configuration/admission arrive out-of-band from the prompt;
/// native confirmations and their ephemeral replies never cross the process seam.
pub async fn serve_owned_agent(request: AgentRequest) -> Result<AgentResult> {
    let config = std::env::var("AUTOWORK_OWNED_CONFIG")
        .map_err(|_| Unavailable("runtime::serve_owned_agent"))?;
    let config: ChildConfig =
        serde_json::from_str(&config).map_err(|_| Unavailable("runtime child config"))?;
    request.validate()?;
    let cancelled = CancellationToken::default();
    let authority = Authority {
        admission: request.admission.clone(),
        identity: request.identity(),
        lease: config.evidence_dir.join("authority.json"),
        cancelled: cancelled.clone(),
        validated: Arc::new(Mutex::new(BTreeSet::new())),
    };
    authority.current()?;
    let model = resolve_model(&config.route, &request.workspace)?;
    let session = Session::create(config.evidence_dir.join("session.jsonl"))
        .map_err(|_| Unavailable("runtime native session"))?;
    let mut extensions = ExtensionHost::new();
    extensions.load(&CoreTools);
    let worker = request.role == Role::Worker;
    extensions.retain_tools(|name| name == "read" || (worker && matches!(name, "edit" | "write")));
    extensions.tool_call_hook(authority.clone());
    let mut sandbox = SandboxConfig::new(&request.workspace);
    sandbox.allow_edit = worker;
    sandbox.allow_write = worker;
    let mut agent = Agent::new(AgentConfig {
        client: native_ai::AiClient::new(),
        model,
        session,
        system: "Follow the supplied task. Tool authority is host-owned, not prompt text.".into(),
        sandbox,
        effect_broker: EffectBroker::default(),
        extensions,
        max_turns: Some(16),
        reasoning: native_ai::ReasoningConfig::Off,
        reasoning_mode: native_ai::ReasoningMode::Standard,
        cache_retention: native_ai::CacheRetention::None,
        session_id: None,
    })
    .map_err(|_| Unavailable("runtime native agent"))?;
    // stdin is an owned control pipe: cancellation or parent death revokes the run.
    let cancel_input = cancelled.clone();
    std::thread::spawn(move || {
        let mut byte = [0u8];
        let _ = std::io::stdin().read(&mut byte);
        cancel_input.cancel();
    });
    let mut run = agent
        .prompt(request.prompt.as_str())
        .await
        .map_err(|_| Unavailable("runtime native prompt"))?;
    let control = run.control();
    emit(&request.event(
        &config.operation_id,
        RuntimeEventKind::Accepted,
        RuntimeStatus::Running,
    ))?;
    let deadline = tokio::time::sleep(Duration::from_millis(config.timeout_ms));
    tokio::pin!(deadline);
    let mut aborting = false;
    let mut calls = BTreeMap::new();
    let mut status = RuntimeStatus::Failed;
    let mut projected = 0;
    loop {
        let Some(event) = (tokio::select! {
        biased;
        _ = cancelled.cancelled(), if !aborting => { control.abort(); aborting = true; continue; },
        _ = &mut deadline, if !aborting => { cancelled.cancel(); control.abort(); aborting = true; continue; },
        event = run.next() => event,
        }) else {
            break;
        };
        let kind = if matches!(&event, AgentEvent::TurnFinished { .. }) {
            RuntimeEventKind::Usage
        } else {
            RuntimeEventKind::Progress
        };
        match event {
            AgentEvent::OutputDelta { .. } => continue,
            AgentEvent::ToolStarted { id, name, args } => {
                calls.insert(id.0, (name, args));
            }
            AgentEvent::ToolProgress {
                id,
                progress: ToolProgress::Confirmation(reply),
            } => {
                let allowed = calls
                    .get(&id.0)
                    .is_some_and(|(name, args)| authority.confirm(name, args));
                reply.respond(allowed);
            }
            AgentEvent::ToolProgress {
                progress: ToolProgress::Input(reply),
                ..
            } => reply.cancel(),
            AgentEvent::ToolFinished { id, .. } => {
                calls.remove(&id.0);
            }
            AgentEvent::RunFinished { reason, .. } => {
                status = if aborting || authority.current().is_err() {
                    RuntimeStatus::Cancelled
                } else {
                    match reason {
                        FinishReason::Completed => RuntimeStatus::Succeeded,
                        FinishReason::Aborted => RuntimeStatus::Cancelled,
                        _ => RuntimeStatus::Failed,
                    }
                };
                break;
            }
            _ => {}
        }
        // Payload-free bounded progress; never persist provider or tool prose.
        if projected < 4000 {
            emit(&request.event(&config.operation_id, kind, RuntimeStatus::Running))?;
            projected += 1;
        }
    }
    drop(run);
    emit(&request.event(&config.operation_id, RuntimeEventKind::Outcome, status))?;
    Ok(AgentResult {
        schema_version: CONTRACT_VERSION,
        identity: request.identity(),
        status,
        evidence_ref: Some(config.operation_id),
    })
}
