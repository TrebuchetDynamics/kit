//! Serialized offline deliveries. Agents propose bytes; this module owns Git and acceptance.
use crate::planning::{FailureEvidence, PlanOutcome, Planner, PlanningContext};
use crate::runtime::*;
use crate::state::{
    DurableStatus, EffectKind, EffectObservation, EffectOutcome, Observations, RecordKind,
    StateStore, Transition,
};
use crate::task_store::{
    CommittedRevision, PendingSnapshot, Record, Scope, Snapshot, TaskService, TaskStore,
    atomic_bytes, digest, git_command, git_env, git_text,
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::Read;
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::{
    Arc,
    atomic::{AtomicU8, Ordering},
};
use std::time::{Duration, Instant};

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;
// Attribute inspection is data-only; never let Git's fixed argv invoke candidate filter scripts.
fn reject_filters(repo: &Path, revision: &str, extra: &[&str], index: Option<&Path>) -> Result<()> {
    let mut paths = git_env(
        repo,
        &["ls-tree", "--name-only", "-r", "-z", revision],
        &[],
        None,
    )?;
    for path in extra {
        paths.extend_from_slice(path.as_bytes());
        paths.push(0);
    }
    let mut args = vec!["check-attr", "-z"];
    if index.is_some() {
        args.push("--cached");
    }
    args.extend(["--stdin", "filter"]);
    let attributes = git_env(repo, &args, &paths, index)?;
    for entry in attributes.split(|b| *b == 0).collect::<Vec<_>>().chunks(3) {
        if entry.len() < 3 {
            continue;
        }
        require(
            matches!(entry[2], b"unspecified" | b"unset"),
            "Git content filters require a later execution authority boundary",
        )?;
    }
    Ok(())
}
fn require(ok: bool, reason: &str) -> Result<()> {
    if ok {
        Ok(())
    } else {
        Err(std::io::Error::other(reason).into())
    }
}

#[derive(Clone, Default)]
pub struct Control(Arc<AtomicU8>);
impl Control {
    pub fn pause(&self) {
        self.0.store(1, Ordering::SeqCst);
    }
    pub fn stop(&self) {
        self.0.store(2, Ordering::SeqCst);
    }
}
#[derive(Clone)]
pub struct RunOptions {
    pub worker_model: String,
    pub reviewer_model: String,
    pub planner_model: String,
    pub max_tasks: Option<usize>,
    pub allow_commit: bool,
    pub control: Control,
    pub prerequisites: Vec<crate::planning::ObservedPrerequisite>,
}
#[derive(Debug, Serialize)]
pub struct RunSummary {
    pub completed_task_ids: Vec<String>,
    pub pending_task_ids: Vec<String>,
    pub evidence_refs: Vec<String>,
    pub disposition: String,
    pub owner_help: Option<String>,
}

/// Fixed, host-authored operations only. No task string is parsed as argv.
#[derive(Serialize, Deserialize)]
pub struct CheckRegistry {
    entries: BTreeMap<String, CheckOperationSpec>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CheckReceipt {
    pub spec: CheckOperationSpec,
    pub candidate: String,
    pub tree: String,
    pub contract_hash: String,
    pub passed: bool,
    pub output_sha256: String,
}
impl CheckRegistry {
    pub fn new(binary: &Path, workspace: &Path, source: &str, fixtures: bool) -> Result<Self> {
        let mut entries = BTreeMap::new();
        let mut operations = vec![(
            "git-diff-check",
            PathBuf::from("/usr/bin/git"),
            vec![
                "--no-replace-objects".into(),
                "-c".into(),
                "core.fsmonitor=false".into(),
                "diff".into(),
                "--no-textconv".into(),
                "--no-ext-diff".into(),
                "--check".into(),
                source.into(),
                "HEAD".into(),
                "--".into(),
            ],
        )];
        if fixtures {
            for (id, result) in [("fixture-pass", "pass"), ("fixture-fail", "fail")] {
                operations.push((
                    id,
                    binary.to_owned(),
                    vec!["internal-fixture-check".into(), result.into()],
                ));
            }
        }
        for (id, executable, argv) in operations {
            let executable = fs::canonicalize(executable)?;
            let spec = CheckOperationSpec {
                operation_id: id.into(),
                executable_sha256: digest(&fs::read(&executable)?)?,
                executable,
                implementation_id: "autowork-next-fixed-checks-v1".into(),
                source_revision: source.into(),
                argv,
                cwd: fs::canonicalize(workspace)?,
                environment_allowlist: BTreeMap::from([
                    ("PATH".into(), "/usr/bin:/bin".into()),
                    ("LANG".into(), "C".into()),
                    ("GIT_CONFIG_NOSYSTEM".into(), "1".into()),
                    ("GIT_CONFIG_GLOBAL".into(), "/dev/null".into()),
                    ("GIT_NO_REPLACE_OBJECTS".into(), "1".into()),
                ]),
                timeout_ms: 10_000,
                max_output_bytes: 64 * 1024,
                receipt_id: format!("{id}-{source}"),
            };
            entries.insert(id.into(), spec);
        }
        Ok(Self { entries })
    }
    pub fn operation(&self, id: &str) -> Result<&CheckOperationSpec> {
        self.entries
            .get(id)
            .ok_or_else(|| std::io::Error::other("unsupported required check operation").into())
    }
    pub fn execute(
        &self,
        spec: &CheckOperationSpec,
        candidate: &str,
        tree: &str,
        contract: &str,
    ) -> Result<CheckReceipt> {
        let accepted = self.operation(&spec.operation_id)?;
        let oid = |s: &str| matches!(s.len(), 40 | 64) && s.bytes().all(|b| b.is_ascii_hexdigit());
        require(
            oid(candidate) && oid(tree),
            "check source identity is not an object ID",
        )?;
        require(
            serde_json::to_vec(accepted)? == serde_json::to_vec(spec)?,
            "check specification drift",
        )?;
        require(
            digest(&fs::read(&spec.executable)?)? == spec.executable_sha256,
            "check executable drift",
        )?;
        reject_filters(&spec.cwd, candidate, &[], None)?;
        require(
            git_text(
                &spec.cwd,
                &[
                    "diff",
                    "--no-ext-diff",
                    "--no-textconv",
                    "--exit-code",
                    candidate,
                    "--",
                ],
            )?
            .is_empty(),
            "check worktree drift",
        )?;
        require(
            git_text(&spec.cwd, &["rev-parse", "HEAD"])? == candidate
                && git_text(&spec.cwd, &["rev-parse", "HEAD^{tree}"])? == tree,
            "check source drift",
        )?;
        let mut child = Command::new(&spec.executable)
            .args(&spec.argv)
            .current_dir(&spec.cwd)
            .env_clear()
            .envs(&spec.environment_allowlist)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        let limit = spec.max_output_bytes;
        fn drain(
            mut pipe: impl Read + Send + 'static,
            limit: u64,
        ) -> std::thread::JoinHandle<(Vec<u8>, bool)> {
            std::thread::spawn(move || {
                let mut bytes = Vec::new();
                let mut overflow = false;
                let mut buf = [0; 4096];
                loop {
                    match pipe.read(&mut buf) {
                        Ok(0) | Err(_) => break,
                        Ok(n) => {
                            let keep = n.min((limit as usize).saturating_sub(bytes.len()));
                            bytes.extend_from_slice(&buf[..keep]);
                            overflow |= keep != n;
                        }
                    }
                }
                (bytes, overflow)
            })
        }
        let stdout = drain(child.stdout.take().unwrap(), limit);
        let stderr = drain(child.stderr.take().unwrap(), limit);
        let start = Instant::now();
        let (status, timed_out) = loop {
            if let Some(status) = child.try_wait()? {
                break (status, false);
            }
            if start.elapsed() >= Duration::from_millis(spec.timeout_ms) {
                child.kill()?;
                break (child.wait()?, true);
            }
            std::thread::sleep(Duration::from_millis(5));
        };
        let (mut out, a) = stdout
            .join()
            .map_err(|_| std::io::Error::other("check reader"))?;
        let (err, b) = stderr
            .join()
            .map_err(|_| std::io::Error::other("check reader"))?;
        out.extend(err);
        require(
            digest(&fs::read(&spec.executable)?)? == spec.executable_sha256
                && git_text(&spec.cwd, &["rev-parse", "HEAD"])? == candidate,
            "check identity changed during execution",
        )?;
        Ok(CheckReceipt {
            spec: spec.clone(),
            candidate: candidate.into(),
            tree: tree.into(),
            contract_hash: contract.into(),
            passed: status.success() && !timed_out && !a && !b,
            output_sha256: digest(&out)?,
        })
    }
}

/// Deterministic crash boundaries used only by disposable offline tests.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum FaultPoint {
    AfterProposalApply,
    AfterChildOutcome,
    BeforeProposalCommit,
    AfterProposalCommit,
    BeforeSelection,
    IntegrationCheckout,
    IntegrationRef,
}
#[derive(Clone, Serialize, Deserialize)]
struct GitEffect {
    identity: RunIdentity,
    source: String,
    operation: String,
    base: String,
    branch: String,
    tree: String,
    target: Option<String>,
    pending: Option<PendingSnapshot>,
    integration: bool,
    settled: bool,
    files: BTreeMap<String, Vec<u8>>,
    commit: Option<CommitInvocation>,
}
#[derive(Clone, Serialize, Deserialize)]
struct CommitInvocation {
    workspace: PathBuf,
    started: bool,
    owner: Option<(u32, u64)>,
    finished: bool,
    succeeded: bool,
}
#[derive(Clone, Serialize, Deserialize)]
struct Delivery {
    task: String,
    contract: String,
    source: String,
    candidate: String,
    tree: String,
    worker: RunIdentity,
    reviewer: RunIdentity,
    checks: Vec<CheckReceipt>,
    review_evidence: String,
    integration: Option<String>,
    settled: bool,
}

pub struct Coordinator<'a> {
    repo: PathBuf,
    binary: PathBuf,
    runtime: &'a Runtime,
    service: &'a TaskService,
    state: &'a StateStore,
    options: RunOptions,
    fixtures: bool,
    fault: Option<FaultPoint>,
}
impl<'a> Coordinator<'a> {
    pub fn new(
        repo: &Path,
        binary: &Path,
        runtime: &'a Runtime,
        service: &'a TaskService,
        state: &'a StateStore,
        options: RunOptions,
    ) -> Result<Self> {
        let repo = fs::canonicalize(repo)?;
        require(
            git_text(&repo, &["rev-parse", "--show-toplevel"])? == repo.to_string_lossy(),
            "repository root required",
        )?;
        let common =
            fs::canonicalize(repo.join(git_text(&repo, &["rev-parse", "--git-common-dir"])?))?;
        require(
            fs::canonicalize(state.directory().parent().unwrap())? == common,
            "state repository mismatch",
        )?;
        require(
            service.repository() == repo,
            "task service repository mismatch",
        )?;
        require(
            runtime.executable() == fs::canonicalize(binary)?,
            "runtime/check binary mismatch",
        )?;
        fs::create_dir_all(state.directory().join("cycle-effects"))?;
        fs::create_dir_all(state.directory().join("cycle-requests"))?;
        Ok(Self {
            repo,
            binary: fs::canonicalize(binary)?,
            runtime,
            service,
            state,
            options,
            fixtures: false,
            fault: None,
        })
    }
    /// Explicit opt-in by the host for disposable fixture repositories only.
    pub fn enable_fixture_checks(&mut self) {
        self.fixtures = true;
    }
    pub fn inject_fault(&mut self, fault: FaultPoint) {
        self.fault = Some(fault);
    }
    fn fault(&self, point: FaultPoint) -> Result<()> {
        require(
            self.fault != Some(point),
            "injected coordinator interruption",
        )
    }
    fn stopped(&self) -> Option<&'static str> {
        if self.options.control.0.load(Ordering::SeqCst) == 2
            || self.state.directory().join("stop").exists()
        {
            Some("stopped")
        } else if self.options.control.0.load(Ordering::SeqCst) == 1
            || self.state.directory().join("pause").exists()
        {
            Some("paused")
        } else {
            None
        }
    }
    fn gate(&self) -> Result<()> {
        require(self.stopped().is_none(), "coordinator paused or stopped")
    }
    fn task_paused(&self, task: &str) -> Result<bool> {
        Ok(self
            .state
            .events()?
            .iter()
            .rev()
            .find(|(_, e)| e.identity.task_id == task)
            .is_some_and(|(_, e)| {
                matches!(e.status, DurableStatus::Paused | DurableStatus::Refused)
            }))
    }
    fn admitted(&self, task: &Record) -> Result<bool> {
        Ok(task.runnable()
            && !task.strings("resources").contains(&"live")
            && !self.task_paused(&task.id)?)
    }
    fn claim(&self, task: &str, contract: &str, source: &str, role: Role) -> Result<RunIdentity> {
        self.gate()?;
        let previous = self
            .state
            .events()?
            .iter()
            .filter(|(_, e)| e.identity.task_id == task)
            .map(|(_, e)| e.identity.generation)
            .max()
            .unwrap_or(0);
        let identity = RunIdentity {
            repo_id: self.state.repo_id().into(),
            task_id: task.into(),
            attempt_id: format!("cycle-{}", previous + 1),
            generation: previous + 1,
            role,
            contract_hash: contract.into(),
        };
        self.state.claim(previous, identity.clone(), source)?;
        Ok(identity)
    }
    fn record(
        &self,
        identity: &RunIdentity,
        source: &str,
        operation: &str,
        status: DurableStatus,
        kind: RecordKind,
        evidence: &str,
    ) -> Result<()> {
        let suffix = match kind {
            RecordKind::Intent(_) => "intent",
            RecordKind::Completion => "completion",
            RecordKind::Note => "note",
        };
        self.state.transition(
            identity.generation,
            Transition {
                key: format!("{operation}/{suffix}"),
                identity: identity.clone(),
                status,
                kind,
                event: RuntimeEvent {
                    schema_version: 1,
                    repo_id: identity.repo_id.clone(),
                    operation_id: operation.into(),
                    task_id: identity.task_id.clone(),
                    attempt_id: identity.attempt_id.clone(),
                    generation: identity.generation,
                    contract_hash: identity.contract_hash.clone(),
                    source_revision: source.into(),
                    role: identity.role,
                    event: if matches!(kind, RecordKind::Intent(_)) {
                        RuntimeEventKind::Accepted
                    } else {
                        RuntimeEventKind::Outcome
                    },
                    status: if matches!(kind, RecordKind::Intent(_)) {
                        RuntimeStatus::Running
                    } else {
                        RuntimeStatus::Succeeded
                    },
                    evidence_ref: Some(evidence.into()),
                    timestamp: "cycle".into(),
                },
            },
        )?;
        Ok(())
    }
    fn effect_path(&self, operation: &str) -> PathBuf {
        self.state
            .directory()
            .join("cycle-effects")
            .join(format!("{operation}.json"))
    }
    fn save_effect(&self, effect: &GitEffect) -> Result<()> {
        atomic_bytes(
            &self.effect_path(&effect.operation),
            &serde_json::to_vec(effect)?,
        )?;
        Ok(())
    }
    fn is_completed(&self, operation: &str) -> Result<bool> {
        Ok(self
            .state
            .events()?
            .iter()
            .any(|(_, e)| e.event.operation_id == operation && e.kind == RecordKind::Completion))
    }
    fn settle_git(&self, effect: &mut GitEffect) -> Result<String> {
        self.gate()?;
        if effect.settled {
            return Ok(effect.target.clone().unwrap());
        }
        let status = if effect.integration {
            DurableStatus::Integrating
        } else {
            DurableStatus::Planning
        };
        if !self
            .state
            .events()?
            .iter()
            .any(|(_, e)| e.event.operation_id == effect.operation)
        {
            effect.identity = self.claim(
                "coordinator-git",
                &effect.identity.contract_hash,
                &effect.source,
                Role::Planner,
            )?;
            self.save_effect(effect)?;
            self.record(
                &effect.identity,
                &effect.source,
                &effect.operation,
                status,
                RecordKind::Intent(EffectKind::Git),
                &self.effect_path(&effect.operation).to_string_lossy(),
            )?;
        }
        let lock = self.service.lock()?;
        require(
            git_text(&self.repo, &["symbolic-ref", "--quiet", "HEAD"])? == effect.branch,
            "Git branch drift",
        )?;
        let head = git_text(&self.repo, &["rev-parse", "HEAD"])?;
        if head == effect.base {
            if let Some(pending) = &effect.pending {
                require(
                    self.service.capture_locked(&lock)? == *pending,
                    "pending snapshot drift",
                )?;
            }
            if effect.integration {
                reject_filters(&self.repo, &effect.base, &[], None)?;
                let target = effect.target.as_ref().unwrap();
                // Two-tree checkout preserves unrelated staged/worktree changes and refuses overlap.
                git_text(&self.repo, &["read-tree", "-m", "-u", &effect.base, target])?;
                self.fault(FaultPoint::IntegrationCheckout)?;
                self.gate()?;
                git_text(
                    &self.repo,
                    &["update-ref", &effect.branch, target, &effect.base],
                )?;
                self.fault(FaultPoint::IntegrationRef)?;
            } else {
                for (path, after) in &effect.files {
                    let full = self.repo.join(path);
                    require(
                        Path::new(path)
                            .components()
                            .all(|c| matches!(c, std::path::Component::Normal(_))),
                        "invalid closure path",
                    )?;
                    let mut parent = self.repo.clone();
                    for part in Path::new(path).parent().unwrap().components() {
                        parent.push(part);
                        match fs::symlink_metadata(&parent) {
                            Ok(m) => {
                                require(m.file_type().is_dir(), "linked closure directory refused")?
                            }
                            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                                fs::create_dir(&parent)?
                            }
                            Err(e) => return Err(e.into()),
                        }
                    }
                    if let Ok(m) = fs::symlink_metadata(&full) {
                        require(
                            m.file_type().is_file() && m.nlink() == 1,
                            "linked closure file refused",
                        )?;
                    }
                    let before = git_env(
                        &self.repo,
                        &["show", &format!("{}:{path}", effect.base)],
                        &[],
                        None,
                    )
                    .ok();
                    let current = fs::read(&full).ok();
                    require(
                        current == before || current.as_ref() == Some(after),
                        "closure bytes changed; recovery retained",
                    )?;
                    fs::create_dir_all(full.parent().unwrap())?;
                    atomic_bytes(&full, after)?;
                }
                self.fault(FaultPoint::BeforeProposalCommit)?;
                self.advance_index(&effect.base, &effect.tree, false)?;
                require(
                    git_text(&self.repo, &["rev-parse", "HEAD"])? == effect.base
                        && git_text(&self.repo, &["symbolic-ref", "HEAD"])? == effect.branch,
                    "proposal source drift",
                )?;
                let target = self.commit_off_branch(effect)?;
                effect.target = Some(target.clone());
                self.save_effect(effect)?;
                self.fault(FaultPoint::AfterProposalCommit)?;
                self.gate()?;
                if let Some(pending) = &effect.pending {
                    require(
                        self.service.capture_locked(&lock)? == *pending,
                        "pending snapshot changed by hook",
                    )?;
                }
                require(
                    git_text(&self.repo, &["symbolic-ref", "HEAD"])? == effect.branch,
                    "proposal branch drift",
                )?;
                git_text(
                    &self.repo,
                    &["update-ref", &effect.branch, &target, &effect.base],
                )?;
            }
        }
        let head = git_text(&self.repo, &["rev-parse", "HEAD"])?;
        require(
            git_text(&self.repo, &["symbolic-ref", "HEAD"])? == effect.branch,
            "Git branch changed during effect",
        )?;
        if let Some(pending) = &effect.pending {
            require(
                self.service.capture_locked(&lock)?.captured_bytes == pending.captured_bytes,
                "pending bytes changed during commit",
            )?;
        }
        for (path, bytes) in &effect.files {
            require(
                fs::read(self.repo.join(path))? == *bytes,
                "closure bytes changed during commit",
            )?;
        }
        require(
            effect.target.as_deref() == Some(&head)
                && git_text(&self.repo, &["rev-parse", &format!("{head}^{{tree}}")])?
                    == effect.tree
                && git_text(&self.repo, &["rev-parse", &format!("{head}^1")])? == effect.base,
            "uncertain Git effect; retained for reconciliation",
        )?;
        if !effect.integration {
            require(
                git_text(&self.repo, &["log", "-1", "--format=%B", &head])?
                    == format!("autowork-next {}", effect.operation),
                "unowned proposal commit",
            )?;
            self.advance_index(&effect.base, &head, true)?;
        }
        self.save_effect(effect)?;
        if !self.is_completed(&effect.operation)? {
            self.state.reconcile(Observations {
                effects: vec![EffectObservation {
                    identity: effect.identity.clone(),
                    operation_id: effect.operation.clone(),
                    source_revision: effect.source.clone(),
                    outcome: EffectOutcome::Applied,
                    evidence_ref: head.clone(),
                }],
            })?;
        }
        effect.settled = true;
        self.save_effect(effect)?;
        Ok(head)
    }
    fn commit_off_branch(&self, effect: &mut GitEffect) -> Result<String> {
        if effect.commit.is_none() {
            let common = PathBuf::from(git_text(
                &self.repo,
                &["rev-parse", "--path-format=absolute", "--git-common-dir"],
            )?);
            let workspace = common
                .parent()
                .unwrap()
                .join(".worktrees")
                .join(format!("autowork-next-{}", effect.operation));
            effect.commit = Some(CommitInvocation {
                workspace,
                started: false,
                owner: None,
                finished: false,
                succeeded: false,
            });
            self.save_effect(effect)?;
        }
        let invocation = effect.commit.as_ref().unwrap().clone();
        let workspace = &invocation.workspace;
        if !invocation.started {
            fs::create_dir_all(workspace.parent().unwrap())?;
            self.plain_tree(&effect.base)?;
            self.plain_tree(&effect.tree)?;
            if !workspace.exists() {
                git_text(
                    &self.repo,
                    &[
                        "worktree",
                        "add",
                        "--detach",
                        workspace.to_str().unwrap(),
                        &effect.base,
                    ],
                )?;
            }
            require(
                git_text(workspace, &["rev-parse", "HEAD"])? == effect.base,
                "publication workspace drift",
            )?;
            reject_filters(workspace, &effect.base, &[], None)?;
            git_text(workspace, &["read-tree", "--reset", "-u", &effect.tree])?;
            let index = self.effect_path(&effect.operation).with_extension("index");
            let _ = fs::remove_file(&index);
            git_env(workspace, &["read-tree", &effect.tree], &[], Some(&index))?;
            self.gate()?;
            effect.commit.as_mut().unwrap().started = true;
            self.save_effect(effect)?;
            let mut child = git_command(
                workspace,
                &[
                    "commit",
                    "-m",
                    &format!("autowork-next {}", effect.operation),
                ],
                Some(&index),
            )
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;
            effect.commit.as_mut().unwrap().owner =
                Some((child.id(), crate::runtime::birth_ticks(child.id())?));
            self.save_effect(effect)?;
            let status = child.wait()?;
            effect.commit.as_mut().unwrap().finished = true;
            effect.commit.as_mut().unwrap().succeeded = status.success();
            self.save_effect(effect)?;
        }
        let invocation = effect.commit.as_ref().unwrap();
        if invocation.finished {
            require(
                invocation.succeeded,
                "ordinary commit hook failed; retained, never automatically replayed",
            )?;
        } else {
            require(
                invocation.owner.is_some_and(|(pid, birth)| {
                    crate::runtime::birth_ticks(pid).ok() != Some(birth)
                }),
                "owned Git invocation is live or uncertain; no replay",
            )?;
        }
        let target = git_text(workspace, &["rev-parse", "HEAD"])?;
        require(
            target != effect.base
                && git_text(workspace, &["rev-parse", "HEAD^{tree}"])? == effect.tree
                && git_text(workspace, &["rev-parse", "HEAD^1"])? == effect.base
                && git_text(workspace, &["log", "-1", "--format=%B"])?
                    == format!("autowork-next {}", effect.operation),
            "hook changed captured publication tree/parent/message; canonical HEAD unchanged",
        )?;
        Ok(target)
    }
    fn advance_index(&self, base: &str, target: &str, write: bool) -> Result<()> {
        let paths = git_env(
            &self.repo,
            &[
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                base,
                target,
                "--",
            ],
            &[],
            None,
        )?;
        let mut updates = Vec::new();
        for path in paths.split(|b| *b == 0).filter(|p| !p.is_empty()) {
            let path = std::str::from_utf8(path)?;
            let before = git_text(&self.repo, &["ls-tree", base, "--", path])?;
            let after = git_text(&self.repo, &["ls-tree", target, "--", path])?;
            let staged = git_text(&self.repo, &["ls-files", "--stage", "--", path])?;
            let identity = |entry: &str| {
                entry
                    .split_whitespace()
                    .take(2)
                    .collect::<Vec<_>>()
                    .join(" ")
            };
            let tree_identity = |entry: &str| {
                let parts: Vec<_> = entry.split_whitespace().collect();
                if parts.len() >= 3 {
                    format!("{} {}", parts[0], parts[2])
                } else {
                    String::new()
                }
            };
            require(
                identity(&staged) == tree_identity(&before)
                    || identity(&staged) == tree_identity(&after),
                "overlapping staged task edit retained; reconcile index",
            )?;
            if after.is_empty() {
                updates.extend_from_slice(
                    format!("0 {}\t{path}\0", "0".repeat(base.len())).as_bytes(),
                );
            } else {
                let parts: Vec<_> = after.split_whitespace().collect();
                updates
                    .extend_from_slice(format!("{} {}\t{path}\0", parts[0], parts[2]).as_bytes());
            }
        }
        if write {
            git_env(
                &self.repo,
                &["update-index", "-z", "--index-info"],
                &updates,
                None,
            )?;
        }
        Ok(())
    }
    pub fn commit_proposal(&self, snapshot: PendingSnapshot) -> Result<CommittedRevision> {
        require(
            self.options.allow_commit,
            "no-commit scope: pending edits retained, not selectable",
        )?;
        self.gate()?;
        let operation = format!("proposal-{}", snapshot.token);
        let path = self.effect_path(&operation);
        let mut effect = if path.exists() {
            serde_json::from_slice(&fs::read(path)?)?
        } else {
            let lock = self.service.lock()?;
            require(
                self.service.capture_locked(&lock)? == snapshot,
                "pending snapshot drift",
            )?;
            require(
                snapshot.tree != git_text(&self.repo, &["rev-parse", "HEAD^{tree}"])?,
                "empty pending proposal",
            )?;
            drop(lock);
            let identity = self.claim(
                "coordinator-publication",
                &snapshot.token,
                &snapshot.base_head,
                Role::Planner,
            )?;
            let effect = GitEffect {
                identity,
                source: snapshot.base_head.clone(),
                operation,
                base: snapshot.base_head.clone(),
                branch: snapshot.branch.clone(),
                tree: snapshot.tree.clone(),
                target: None,
                pending: Some(snapshot),
                integration: false,
                settled: false,
                files: BTreeMap::new(),
                commit: None,
            };
            self.save_effect(&effect)?;
            effect
        };
        let revision = self.settle_git(&mut effect)?;
        self.clear_publication(effect.pending.as_ref().unwrap())?;
        Ok(CommittedRevision(revision))
    }
    fn clear_publication(&self, pending: &PendingSnapshot) -> Result<()> {
        let path = self
            .state
            .directory()
            .join(crate::planning::PUBLICATION_INTENT);
        if !path.exists() {
            return Ok(());
        }
        let intent: crate::planning::PublicationIntent = serde_json::from_slice(&fs::read(&path)?)?;
        let mut after = intent.before;
        for change in intent.proposal.record_changes {
            after.insert(change.path.to_str().unwrap().into(), change.proposed_bytes);
        }
        require(
            intent.proposal.expected_revision == pending.base_head
                && after == pending.captured_bytes,
            "proposal publication receipt mismatch",
        )?;
        fs::remove_file(path)?;
        fs::File::open(self.state.directory())?.sync_all()?;
        Ok(())
    }
    fn recover_publication(&self) -> Result<()> {
        let path = self
            .state
            .directory()
            .join(crate::planning::PUBLICATION_INTENT);
        if !path.exists() {
            return Ok(());
        }
        let intent: crate::planning::PublicationIntent = serde_json::from_slice(&fs::read(&path)?)?;
        let base = TaskStore::read_at(&self.repo, &intent.proposal.expected_revision)?;
        require(
            !self.state.events()?.iter().any(|(_, e)| {
                e.identity.task_id == intent.identity.task_id
                    && e.identity.generation > intent.identity.generation
            }),
            "stale planner publication generation",
        )?;
        require(
            base.records() == &intent.before
                && intent.identity.repo_id == self.state.repo_id()
                && intent.identity.role == Role::Planner
                && base
                    .tasks()
                    .get(&intent.identity.task_id)
                    .is_some_and(|t| t.contract_hash == intent.identity.contract_hash),
            "planner publication source mismatch",
        )?;
        let mut after = intent.before.clone();
        for change in &intent.proposal.record_changes {
            after.insert(
                change
                    .path
                    .to_str()
                    .ok_or_else(|| std::io::Error::other("invalid publication path"))?
                    .into(),
                change.proposed_bytes.clone(),
            );
        }
        if git_text(&self.repo, &["rev-parse", "HEAD"])? == base.revision() {
            let current = self.service.capture_pending()?;
            if current.captured_bytes == intent.before {
                self.service.apply(base.revision(), &intent.proposal)?;
            }
            let pending = self.service.capture_pending()?;
            require(
                pending.captured_bytes == after,
                "external task bytes preserved; planner publication is uncertain",
            )?;
            self.commit_proposal(pending)?;
        } else {
            let effects = fs::read_dir(self.state.directory().join("cycle-effects"))?;
            let mut matched = false;
            for entry in effects {
                let entry = entry?;
                if entry.path().extension().is_none_or(|e| e != "json") {
                    continue;
                }
                let effect: GitEffect = serde_json::from_slice(&fs::read(entry.path())?)?;
                if let Some(pending) = effect
                    .pending
                    .as_ref()
                    .filter(|p| p.base_head == base.revision() && p.captured_bytes == after)
                {
                    require(effect.settled, "unsettled proposal commit")?;
                    git_text(
                        &self.repo,
                        &[
                            "merge-base",
                            "--is-ancestor",
                            effect.target.as_deref().unwrap(),
                            "HEAD",
                        ],
                    )?;
                    self.clear_publication(pending)?;
                    matched = true;
                    break;
                }
            }
            require(matched, "planner publication HEAD drift")?;
        }
        Ok(())
    }
    fn request(
        &self,
        task: &Record,
        snapshot: &Snapshot,
        workspace: &Path,
        role: Role,
    ) -> Result<AgentRequest> {
        let identity = self.claim(&task.id, &task.contract_hash, snapshot.revision(), role)?;
        fn inspect(path: &Path) -> Result<WorkspaceIdentity> {
            let canonical_path = fs::canonicalize(path)?;
            let m = fs::metadata(&canonical_path)?;
            Ok(WorkspaceIdentity {
                canonical_path,
                device: m.dev(),
                inode: m.ino(),
            })
        }
        Ok(AgentRequest {
            schema_version: 1,
            repo_id: identity.repo_id.clone(),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            role,
            workspace: workspace.into(),
            model_ref: match role {
                Role::Worker => &self.options.worker_model,
                Role::Reviewer => &self.options.reviewer_model,
                Role::Planner => &self.options.planner_model,
            }
            .clone(),
            contract_hash: task.contract_hash.clone(),
            source_revision: snapshot.revision().into(),
            prompt: String::new(),
            admission: ExecutionAdmission {
                repo_id: identity.repo_id,
                repository: inspect(&self.repo)?,
                workspace: inspect(workspace)?,
                task_id: task.id.clone(),
                attempt_id: identity.attempt_id,
                generation: identity.generation,
                contract_hash: task.contract_hash.clone(),
                role,
                allowed_write_paths: if role == Role::Worker {
                    task.strings("touches").iter().map(PathBuf::from).collect()
                } else {
                    vec![]
                },
                denied_paths: vec![],
                admitted_check_operation_ids: vec![],
            },
            check_operations: vec![],
        })
    }
    async fn agent(&self, request: AgentRequest) -> Result<(String, String)> {
        self.gate()?;
        let identity = request.identity();
        atomic_bytes(
            &self
                .state
                .directory()
                .join("cycle-requests")
                .join(format!("{}-{}.json", request.task_id, request.generation)),
            &serde_json::to_vec(&request)?,
        )?;
        let operation = format!("child-{}-{}", request.task_id, request.generation);
        let status = if request.role == Role::Worker {
            DurableStatus::Executing
        } else {
            DurableStatus::Reviewing
        };
        self.record(
            &identity,
            &request.source_revision,
            &operation,
            status,
            RecordKind::Intent(EffectKind::Child),
            "native-owned-child",
        )?;
        let mut events = self.runtime.run(request.clone()).await?;
        let mut terminal = None;
        loop {
            tokio::select! {
                event = events.recv() => match event {
                    Some(event) if event.event == RuntimeEventKind::Outcome => { terminal = Some(event.status); },
                    Some(_) => (),
                    None => break,
                },
                _ = tokio::time::sleep(Duration::from_millis(20)) => {
                    if self.stopped().is_some() {
                        self.runtime.cancel(identity.clone()).await?;
                    }
                }
            }
        }
        let owned = self
            .runtime
            .owned_process(&identity)
            .ok_or_else(|| std::io::Error::other("missing native evidence"))?;
        let evidence = owned
            .evidence_dir
            .join("outcome.json")
            .to_string_lossy()
            .into_owned();
        self.fault(FaultPoint::AfterChildOutcome)?;
        if terminal.is_some() {
            self.record(
                &identity,
                &request.source_revision,
                &operation,
                status,
                RecordKind::Completion,
                &evidence,
            )?;
        }
        require(
            terminal == Some(RuntimeStatus::Succeeded),
            "native role did not succeed",
        )?;
        self.gate()?;
        let path = owned.evidence_dir.join("session.jsonl");
        require(
            fs::metadata(&path)?.len() <= 4 * 1024 * 1024,
            "native transcript limit",
        )?;
        let session = native_agent::Session::open_read_only(path)?;
        let response = session
            .entries()
            .iter()
            .rev()
            .find_map(|e| match &e.value {
                native_agent::session::EntryValue::Message(native_ai::Message::Assistant(m)) => {
                    Some(
                        m.content
                            .iter()
                            .filter_map(|p| {
                                if let native_ai::AssistantPart::Text(t) = p {
                                    Some(t.as_str())
                                } else {
                                    None
                                }
                            })
                            .collect::<String>(),
                    )
                }
                _ => None,
            })
            .ok_or_else(|| std::io::Error::other("missing native response"))?;
        Ok((response, evidence))
    }
    fn plain_tree(&self, source: &str) -> Result<()> {
        let index = self.state.directory().join("attributes.index");
        let _ = fs::remove_file(&index);
        git_env(&self.repo, &["read-tree", source], &[], Some(&index))?;
        reject_filters(&self.repo, source, &[], Some(&index))
    }
    fn workspace(&self, task: &str, source: &str, role: &str) -> Result<PathBuf> {
        self.gate()?;
        self.plain_tree(source)?;
        // Candidate worktrees are retained for recovery, never shared by writers.
        let root = PathBuf::from(git_text(
            &self.repo,
            &["rev-parse", "--path-format=absolute", "--git-common-dir"],
        )?)
        .parent()
        .unwrap()
        .join(".worktrees");
        fs::create_dir_all(&root)?;
        let serial = self.state.events()?.len();
        let path = root.join(format!("autowork-next-{task}-{role}-{serial}"));
        require(!path.exists(), "candidate workspace already exists")?;
        git_text(
            &self.repo,
            &[
                "worktree",
                "add",
                "--detach",
                path.to_str().unwrap(),
                source,
            ],
        )?;
        Ok(path)
    }
    fn delivery_path(&self) -> PathBuf {
        self.state.directory().join("cycle-delivery.json")
    }
    fn save_delivery(&self, delivery: &Delivery) -> Result<()> {
        atomic_bytes(&self.delivery_path(), &serde_json::to_vec(delivery)?)?;
        Ok(())
    }
    fn tree_with(
        &self,
        base: &str,
        files: &BTreeMap<String, Vec<u8>>,
        name: &str,
    ) -> Result<String> {
        let index = self.state.directory().join(format!("{name}.index"));
        let _ = fs::remove_file(&index);
        git_env(&self.repo, &["read-tree", base], &[], Some(&index))?;
        for (path, bytes) in files {
            let oid = String::from_utf8(git_env(
                &self.repo,
                &["hash-object", "-w", "--stdin"],
                bytes,
                None,
            )?)?;
            git_env(
                &self.repo,
                &[
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    &format!("100644,{},{}", oid.trim(), path),
                ],
                &[],
                Some(&index),
            )?;
        }
        Ok(
            String::from_utf8(git_env(&self.repo, &["write-tree"], &[], Some(&index))?)?
                .trim()
                .into(),
        )
    }
    fn finish_delivery(&self, delivery: &mut Delivery) -> Result<()> {
        if delivery.settled {
            return Ok(());
        }
        self.gate()?;
        let closure_path = self.effect_path(&format!(
            "close-{}-{}",
            delivery.task, delivery.reviewer.generation
        ));
        if closure_path.exists() {
            let closure: GitEffect = serde_json::from_slice(&fs::read(closure_path)?)?;
            if closure.settled {
                let revision = closure.target.as_deref().unwrap();
                git_text(
                    &self.repo,
                    &["merge-base", "--is-ancestor", revision, "HEAD"],
                )?;
                let closed = TaskStore::read_at(&self.repo, revision)?;
                require(
                    closed
                        .tasks()
                        .get(&delivery.task)
                        .is_some_and(|t| t.verified() && t.contract_hash == delivery.contract),
                    "retained closure receipt mismatch",
                )?;
                self.retire_delivery(delivery, revision)?;
                return Ok(());
            }
        }
        require(self.options.allow_commit, "no-commit scope")?;
        require(
            delivery.worker.role == Role::Worker
                && delivery.reviewer.role == Role::Reviewer
                && delivery.worker.generation < delivery.reviewer.generation
                && delivery.worker.contract_hash == delivery.contract
                && delivery.reviewer.contract_hash == delivery.contract
                && !delivery.review_evidence.is_empty(),
            "review receipt mismatch",
        )?;
        let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
        let task = snapshot
            .tasks()
            .get(&delivery.task)
            .ok_or_else(|| std::io::Error::other("unsettled delivery task removed"))?;
        require(
            task.contract_hash == delivery.contract,
            "integrated contract drift",
        )?;
        if task.verified() {
            return Ok(());
        }
        require(self.admitted(task)?, "delivery authority changed or paused")?;
        for receipt in &delivery.checks {
            reject_filters(&receipt.spec.cwd, &delivery.candidate, &[], None)?;
            require(
                git_text(&receipt.spec.cwd, &["rev-parse", "HEAD"])? == delivery.candidate
                    && git_text(
                        &receipt.spec.cwd,
                        &[
                            "diff",
                            "--no-ext-diff",
                            "--no-textconv",
                            "--exit-code",
                            &delivery.candidate,
                            "--",
                        ],
                    )?
                    .is_empty(),
                "checked source drift",
            )?;
            let registry = CheckRegistry::new(
                &self.binary,
                &receipt.spec.cwd,
                &delivery.source,
                self.fixtures,
            )?;
            require(
                serde_json::to_vec(registry.operation(&receipt.spec.operation_id)?)?
                    == serde_json::to_vec(&receipt.spec)?,
                "accepted check implementation drift",
            )?;
            require(
                digest(&fs::read(&receipt.spec.executable)?)? == receipt.spec.executable_sha256,
                "accepted executable drift",
            )?;
        }
        let required = task.strings("checks");
        require(
            required.len() == delivery.checks.len()
                && required.iter().zip(&delivery.checks).all(|(id, r)| {
                    r.passed
                        && **id == r.spec.operation_id
                        && r.candidate == delivery.candidate
                        && r.tree == delivery.tree
                        && r.contract_hash == delivery.contract
                }),
            "required checks unmet",
        )?;
        let operation = format!(
            "integrate-{}-{}",
            delivery.task, delivery.reviewer.generation
        );
        let path = self.effect_path(&operation);
        let mut effect: GitEffect = if path.exists() {
            serde_json::from_slice(&fs::read(path)?)?
        } else {
            require(
                snapshot.revision() == delivery.source,
                "integration base drift",
            )?;
            require(
                git_text(
                    &self.repo,
                    &["rev-parse", &format!("{}^1", delivery.candidate)],
                )? == delivery.source
                    && git_text(
                        &self.repo,
                        &["rev-parse", &format!("{}^{{tree}}", delivery.candidate)],
                    )? == delivery.tree,
                "candidate source mismatch",
            )?;
            let commit = String::from_utf8(git_env(
                &self.repo,
                &[
                    "commit-tree",
                    &delivery.tree,
                    "-p",
                    &delivery.source,
                    "-p",
                    &delivery.candidate,
                ],
                format!("autowork-next {operation}\n").as_bytes(),
                None,
            )?)?
            .trim()
            .to_owned();
            let effect = GitEffect {
                identity: delivery.reviewer.clone(),
                source: delivery.source.clone(),
                operation,
                base: delivery.source.clone(),
                branch: git_text(&self.repo, &["symbolic-ref", "HEAD"])?,
                tree: delivery.tree.clone(),
                target: Some(commit),
                pending: None,
                integration: true,
                settled: false,
                files: BTreeMap::new(),
                commit: None,
            };
            self.save_effect(&effect)?;
            effect
        };
        let integrated = self.settle_git(&mut effect)?;
        delivery.integration = Some(integrated.clone());
        self.save_delivery(delivery)?;
        let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
        require(snapshot.revision() == integrated, "closure source drift")?;
        let task = &snapshot.tasks()[&delivery.task];
        let mut header: toml::Table = toml::from_str(
            snapshot.records()[&task.path]
                .split(|b| *b == b'\n')
                .skip(1)
                .take_while(|l| *l != b"+++")
                .map(|l| String::from_utf8_lossy(l).into_owned() + "\n")
                .collect::<String>()
                .as_str(),
        )?;
        header.insert("status".into(), "done".into());
        header.insert("closure".into(), "coordinator_verified".into());
        let receipt_path = format!("tasks/evidence/{}.toml", task.id);
        header.insert("closure_evidence".into(), receipt_path.clone().into());
        let record = format!("+++\n{}+++\n{}", toml::to_string(&header)?, task.body).into_bytes();
        let mut receipt = toml::Table::new();
        receipt.insert("schema".into(), 1.into());
        for (key, value) in [
            ("task", task.id.as_str()),
            ("contract_hash", delivery.contract.as_str()),
            ("candidate", delivery.candidate.as_str()),
            ("integration", integrated.as_str()),
            ("tree", delivery.tree.as_str()),
            ("result", "pass"),
            ("review", "passed"),
            ("review_evidence", delivery.review_evidence.as_str()),
        ] {
            receipt.insert(key.into(), value.into());
        }
        receipt.insert(
            "checks".into(),
            toml::Value::Array(
                delivery
                    .checks
                    .iter()
                    .map(|r| toml::Value::String(r.spec.receipt_id.clone()))
                    .collect(),
            ),
        );
        let files = BTreeMap::from([
            (task.path.clone(), record),
            (receipt_path, toml::to_string(&receipt)?.into_bytes()),
        ]);
        for (path, _) in &files {
            let tracked = git_text(&self.repo, &["status", "--porcelain", "--", path])?;
            require(
                tracked.is_empty(),
                "closure would overwrite pending task bytes",
            )?;
        }
        let tree = self.tree_with(&integrated, &files, "closure")?;
        // Publish coordinator-authored closure bytes, never planner authority.
        let closure_op = format!("close-{}-{}", task.id, delivery.reviewer.generation);
        let mut closure = GitEffect {
            identity: delivery.reviewer.clone(),
            source: delivery.source.clone(),
            operation: closure_op,
            base: integrated,
            branch: git_text(&self.repo, &["symbolic-ref", "HEAD"])?,
            tree,
            target: None,
            pending: None,
            integration: false,
            settled: false,
            files,
            commit: None,
        };
        self.save_effect(&closure)?;
        self.settle_git(&mut closure)?;
        require(
            TaskStore::read_at(&self.repo, "HEAD")?.tasks()[&delivery.task].verified(),
            "closure receipt rejected",
        )?;
        self.retire_delivery(delivery, closure.target.as_deref().unwrap())
    }
    fn retire_delivery(&self, delivery: &mut Delivery, revision: &str) -> Result<()> {
        let complete = self.state.events()?.iter().any(|(_, e)| {
            e.identity.task_id == delivery.task
                && e.identity.contract_hash == delivery.contract
                && e.status == DurableStatus::Complete
                && e.event.evidence_ref.as_deref() == Some(revision)
        });
        if !complete {
            let accepted = self.claim(
                &delivery.task,
                &delivery.contract,
                &delivery.source,
                Role::Reviewer,
            )?;
            self.record(
                &accepted,
                &delivery.source,
                &format!("accepted-{}-{}", delivery.task, accepted.generation),
                DurableStatus::Complete,
                RecordKind::Note,
                revision,
            )?;
        }
        delivery.settled = true;
        self.save_delivery(delivery)
    }
    fn resumed_worker(&self, snapshot: &Snapshot, task: &Record) -> Result<Option<AgentRequest>> {
        let outcomes = self.runtime.retained_outcomes()?;
        let mut requests = Vec::new();
        for entry in fs::read_dir(self.state.directory().join("cycle-requests"))? {
            let request: AgentRequest = serde_json::from_slice(&fs::read(entry?.path())?)?;
            if request.role == Role::Worker
                && request.task_id == task.id
                && request.contract_hash == task.contract_hash
                && request.repo_id == self.state.repo_id()
                && request.source_revision == snapshot.revision()
                && outcomes.iter().any(|(owner, event)| {
                    owner.identity == request.identity() && event.status == RuntimeStatus::Succeeded
                })
            {
                requests.push(request);
            }
        }
        Ok(requests.into_iter().max_by_key(|r| r.generation))
    }
    async fn execute(&self, snapshot: &Snapshot, task: &Record) -> Result<()> {
        self.gate()?;
        require(
            self.admitted(task)?,
            "task is not admitted for offline execution",
        )?;
        require(
            git_text(&self.repo, &["rev-parse", "HEAD"])? == snapshot.revision(),
            "dispatch source drift",
        )?;
        // Resolve all IDs before any worker dispatch; unsupported checks remain required.
        let resumed = self.resumed_worker(snapshot, task)?;
        let workspace = match &resumed {
            Some(request) => request.workspace.clone(),
            None => self.workspace(&task.id, snapshot.revision(), "worker")?,
        };
        let registry =
            CheckRegistry::new(&self.binary, &workspace, snapshot.revision(), self.fixtures)?;
        for id in task.strings("checks") {
            registry.operation(id)?;
        }
        let worker = if let Some(request) = resumed {
            let prior = fs::read(
                self.state
                    .directory()
                    .join(format!("registry-{}-{}.json", task.id, request.generation)),
            )?;
            require(
                prior == serde_json::to_vec(&registry)?,
                "resumed check admission drift",
            )?;
            request.identity()
        } else {
            let mut request = self.request(task, snapshot, &workspace, Role::Worker)?;
            request.prompt = format!(
                "Implement exactly this accepted task using only admitted file edits. Do not execute commands or change task state. Contract: {}\n{}",
                task.contract_hash,
                String::from_utf8_lossy(&snapshot.records()[&task.path])
            );
            let worker = request.identity();
            atomic_bytes(
                &self
                    .state
                    .directory()
                    .join(format!("registry-{}-{}.json", task.id, worker.generation)),
                &serde_json::to_vec(&registry)?,
            )?;
            self.agent(request).await?;
            worker
        };
        self.gate()?;
        let index = self.state.directory().join("candidate.index");
        let _ = fs::remove_file(&index);
        git_env(
            &workspace,
            &["read-tree", snapshot.revision()],
            &[],
            Some(&index),
        )?;
        let mut args = vec!["add", "--"];
        let touches = task.strings("touches");
        reject_filters(&workspace, snapshot.revision(), &touches, None)?;
        args.extend(touches);
        git_env(&workspace, &args, &[], Some(&index))?;
        let tree = String::from_utf8(git_env(&workspace, &["write-tree"], &[], Some(&index))?)?
            .trim()
            .to_owned();
        let head = git_text(&workspace, &["rev-parse", "HEAD"])?;
        let candidate = if head == snapshot.revision() {
            let candidate = String::from_utf8(git_env(
                &workspace,
                &["commit-tree", &tree, "-p", snapshot.revision()],
                format!("autowork-next candidate {}\n", task.id).as_bytes(),
                None,
            )?)?
            .trim()
            .to_owned();
            git_text(
                &workspace,
                &["update-ref", "HEAD", &candidate, snapshot.revision()],
            )?;
            candidate
        } else {
            require(
                git_text(&workspace, &["rev-parse", "HEAD^1"])? == snapshot.revision()
                    && git_text(&workspace, &["rev-parse", "HEAD^{tree}"])? == tree,
                "retained candidate source drift",
            )?;
            head
        };
        // This isolated index has no user changes. Include newly created admitted files.
        git_text(&workspace, &["read-tree", &candidate])?;
        let changed = git_env(
            &workspace,
            &[
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-z",
                snapshot.revision(),
                &candidate,
            ],
            &[],
            None,
        )?;
        for path in changed.split(|b| *b == 0).filter(|p| !p.is_empty()) {
            require(
                task.strings("touches")
                    .contains(&std::str::from_utf8(path)?),
                "candidate widened admitted write scope",
            )?;
        }
        let mut checks = Vec::new();
        for id in task.strings("checks") {
            self.gate()?;
            let receipt = registry.execute(
                registry.operation(id)?,
                &candidate,
                &tree,
                &task.contract_hash,
            )?;
            atomic_bytes(
                &self
                    .state
                    .directory()
                    .join(format!("check-{}-{}-{id}.json", task.id, worker.generation)),
                &serde_json::to_vec(&receipt)?,
            )?;
            require(
                receipt.passed,
                &format!("required candidate check failed: {id}"),
            )?;
            checks.push(receipt);
        }
        let review_workspace = self.workspace(&task.id, &candidate, "reviewer")?;
        let mut request = self.request(task, snapshot, &review_workspace, Role::Reviewer)?;
        let reviewer = request.identity();
        request.prompt = format!(
            "{}\nFresh READ-ONLY independent review. Inspect the actual candidate {} tree {}, compared with base {}. Acceptance and exclusions: {}. Check receipts: {}. Return ONLY JSON {{\"approved\":true|false,\"candidate\":\"{}\",\"tree\":\"{}\",\"contract_hash\":\"{}\"}}. Reject unmet acceptance. Do not run commands, dispatch, or write.",
            include_str!("../../../skills/ponytail-review/SKILL.md"),
            candidate,
            tree,
            snapshot.revision(),
            String::from_utf8_lossy(&snapshot.records()[&task.path]),
            serde_json::to_string(&checks)?,
            candidate,
            tree,
            task.contract_hash
        );
        let diff = git_env(
            &self.repo,
            &[
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--binary",
                snapshot.revision(),
                &candidate,
                "--",
            ],
            &[],
            None,
        )?;
        require(
            diff.len() <= 256 * 1024,
            "review diff exceeds offline slice limit",
        )?;
        request.prompt.push_str(&format!(
            "\nCoordinator-authored exact base/candidate diff (including deletions):\n{}",
            String::from_utf8_lossy(&diff)
        ));
        let (response, review_evidence) = self.agent(request).await?;
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Review {
            approved: bool,
            candidate: String,
            tree: String,
            contract_hash: String,
        }
        let review: Review = serde_json::from_str(&response)?;
        reject_filters(&review_workspace, &candidate, &[], None)?;
        require(
            git_text(&review_workspace, &["rev-parse", "HEAD"])? == candidate
                && git_text(
                    &review_workspace,
                    &[
                        "diff",
                        "--no-ext-diff",
                        "--no-textconv",
                        "--exit-code",
                        &candidate,
                        "--",
                    ],
                )?
                .is_empty(),
            "review source drift",
        )?;
        require(
            review.approved
                && review.candidate == candidate
                && review.tree == tree
                && review.contract_hash == task.contract_hash,
            "independent review rejected or mismatched candidate",
        )?;
        let mut delivery = Delivery {
            task: task.id.clone(),
            contract: task.contract_hash.clone(),
            source: snapshot.revision().into(),
            candidate,
            tree,
            worker,
            reviewer,
            checks,
            review_evidence,
            integration: None,
            settled: false,
        };
        self.save_delivery(&delivery)?;
        self.finish_delivery(&mut delivery)?;
        Ok(())
    }
    fn recover(&self) -> Result<()> {
        self.service.recover()?;
        let unresolved = self
            .state
            .reconcile(Default::default())?
            .reconcile_operation_ids;
        let outcomes = self.runtime.retained_outcomes()?;
        let mut observations = Observations::default();
        for (_, transition) in self.state.events()? {
            if transition.kind != RecordKind::Intent(EffectKind::Child)
                || !unresolved.contains(&transition.event.operation_id)
            {
                continue;
            }
            if let Some((owner, event)) = outcomes.iter().find(|(owner, event)| {
                owner.identity == transition.identity
                    && event.source_revision == transition.event.source_revision
            }) {
                observations.effects.push(EffectObservation {
                    identity: owner.identity.clone(),
                    operation_id: transition.event.operation_id,
                    source_revision: event.source_revision.clone(),
                    outcome: EffectOutcome::Applied,
                    evidence_ref: owner
                        .evidence_dir
                        .join("outcome.json")
                        .to_string_lossy()
                        .into_owned(),
                });
            }
        }
        self.state.reconcile(observations)?;
        let mut effects: Vec<GitEffect> =
            fs::read_dir(self.state.directory().join("cycle-effects"))?
                .filter_map(|e| e.ok())
                .filter(|e| e.path().extension().is_some_and(|s| s == "json"))
                .map(|e| -> Result<GitEffect> { Ok(serde_json::from_slice(&fs::read(e.path())?)?) })
                .collect::<Result<_>>()?;
        effects.retain(|e| !e.settled);
        // There is at most one unsettled serialized Git operation.
        require(effects.len() <= 1, "multiple unsettled Git effects")?;
        for mut effect in effects {
            self.settle_git(&mut effect)?;
        }
        if self.delivery_path().exists() {
            let mut delivery: Delivery = serde_json::from_slice(&fs::read(self.delivery_path())?)?;
            self.finish_delivery(&mut delivery)?;
        }
        if self
            .state
            .reconcile(Default::default())?
            .reconcile_operation_ids
            .is_empty()
        {
            self.recover_publication()?;
        }
        Ok(())
    }
    pub async fn run_until_quiescent(&self, scope: Scope) -> Result<RunSummary> {
        let mut summary = RunSummary {
            completed_task_ids: vec![],
            pending_task_ids: vec![],
            evidence_refs: vec![],
            disposition: "pending".into(),
            owner_help: None,
        };
        if let Some(reason) = self.stopped() {
            summary.disposition = reason.into();
        } else if !self.options.allow_commit {
            summary.disposition = "no_commit".into();
        } else {
            self.recover()?;
            let unresolved = self.state.reconcile(Default::default())?;
            if !unresolved.reconcile_operation_ids.is_empty() {
                summary.disposition = "uncertain".into();
                summary.evidence_refs = unresolved.reconcile_operation_ids;
            } else {
                let mut attempted = BTreeSet::new();
                let mut failed: Option<FailureEvidence> = None;
                let mut failure_summary = String::new();
                loop {
                    if !self
                        .state
                        .reconcile(Default::default())?
                        .reconcile_operation_ids
                        .is_empty()
                    {
                        summary.disposition = "uncertain".into();
                        break;
                    }
                    if let Some(reason) = self.stopped() {
                        summary.disposition = reason.into();
                        break;
                    }
                    if self.options.max_tasks.is_some_and(|n| attempted.len() >= n) {
                        summary.disposition = "task_limit".into();
                        break;
                    }
                    self.fault(FaultPoint::BeforeSelection)?;
                    let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
                    if self.service.capture_pending()?.captured_bytes != *snapshot.records() {
                        summary.disposition = "pending_edits".into();
                        break;
                    }
                    let selection = snapshot.select(&scope)?;
                    let mut next = None;
                    for id in &selection.task_ids {
                        if !attempted.contains(id) && self.admitted(&snapshot.tasks()[id])? {
                            next = Some(id);
                            break;
                        }
                    }
                    if let Some(id) = next {
                        attempted.insert(id.clone());
                        match self.execute(&snapshot, &snapshot.tasks()[id]).await {
                            Ok(()) => {
                                summary.completed_task_ids.push(id.clone());
                            }
                            Err(error) => {
                                if self.fault.is_some() {
                                    return Err(error);
                                }
                                failure_summary = format!("Task {id}: {}", error)
                                    .chars()
                                    .filter(|c| !c.is_control())
                                    .take(2048)
                                    .collect();
                                let path = self
                                    .state
                                    .directory()
                                    .join(format!("failure-{id}-{}.json", snapshot.revision()));
                                let bytes = serde_json::to_vec(
                                    &serde_json::json!({"task":id, "source":snapshot.revision(), "contract":snapshot.tasks()[id].contract_hash, "failure":failure_summary}),
                                )?;
                                atomic_bytes(&path, &bytes)?;
                                let evidence_ref = path.to_string_lossy().into_owned();
                                failed = Some(FailureEvidence {
                                    operation_id: format!("failed-task-{id}"),
                                    fingerprint: digest(&bytes)?,
                                    evidence_refs: vec![evidence_ref.clone()],
                                });
                                summary.evidence_refs.push(evidence_ref);
                                if self.stopped().is_some() {
                                    continue;
                                }
                            }
                        }
                        continue;
                    }
                    let mut paused = BTreeSet::new();
                    for id in snapshot.tasks().keys() {
                        if self.task_paused(id)? {
                            paused.insert(id.clone());
                        }
                    }
                    let Some(task) = snapshot.tasks().values().find(|t| {
                        t.string("status") == "open"
                            && !paused.contains(&t.id)
                            && (scope.task_ids.is_empty() || scope.task_ids.contains(&t.id))
                    }) else {
                        summary.disposition = if paused.is_empty() {
                            "completed"
                        } else {
                            "paused"
                        }
                        .into();
                        break;
                    };
                    let planning_workspace =
                        self.workspace(&task.id, snapshot.revision(), "planner")?;
                    let mut request =
                        self.request(task, &snapshot, &planning_workspace, Role::Planner)?;
                    request.admission.allowed_write_paths.clear();
                    let failure = failed.clone().unwrap_or_else(|| FailureEvidence {
                        operation_id: "queue-quiescent".into(),
                        fingerprint: snapshot.revision().into(),
                        evidence_refs: vec![format!("committed:{}", snapshot.revision())],
                    });
                    let planner_identity = request.identity();
                    let context = PlanningContext::new(
                        request,
                        paused,
                        self.options.prerequisites.clone(),
                        vec![],
                    )
                    .with_control(self.options.control.0.clone())
                    .with_failure_summary(failure_summary.clone());
                    let planner = Planner::new(self.runtime, self.service, self.state);
                    let planning = planner.propose(&snapshot, &failure, &context);
                    tokio::pin!(planning);
                    let outcome = loop {
                        tokio::select! {
                            outcome = &mut planning => break outcome,
                            _ = tokio::time::sleep(Duration::from_millis(20)) => {
                                if self.stopped().is_some() && self.runtime.owned_process(&planner_identity).is_some() {
                                    self.runtime.cancel(planner_identity.clone()).await?;
                                }
                            }
                        }
                    };
                    let outcome = match outcome {
                        Ok(outcome) => outcome,
                        Err(_) if self.stopped().is_some() => {
                            summary.disposition = self.stopped().unwrap().into();
                            break;
                        }
                        Err(error) => return Err(error.into()),
                    };
                    match outcome {
                        PlanOutcome::Pending { snapshot, .. } => {
                            self.fault(FaultPoint::AfterProposalApply)?;
                            self.commit_proposal(snapshot)?;
                        }
                        PlanOutcome::OwnerHelp(observation) => {
                            summary.disposition = match observation.kind {
                                crate::planning::PrerequisiteKind::SudoRequired => "waiting_sudo",
                                crate::planning::PrerequisiteKind::CredentialRequired => {
                                    "waiting_credential"
                                }
                            }
                            .into();
                            summary.owner_help = Some(observation.resume_action);
                            break;
                        }
                        PlanOutcome::WaitingExternal | PlanOutcome::Exhausted(_) => {
                            summary.disposition = "waiting_external".into();
                            break;
                        }
                        PlanOutcome::RefusedScope => {
                            summary.disposition = "refused_scope".into();
                            break;
                        }
                        PlanOutcome::UnchangedEvidence => {
                            summary.disposition = "pending".into();
                            break;
                        }
                    }
                }
            }
        }
        let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
        summary.pending_task_ids = snapshot
            .tasks()
            .values()
            .filter(|t| {
                t.string("status") == "open"
                    && (scope.task_ids.is_empty() || scope.task_ids.contains(&t.id))
            })
            .map(|t| t.id.clone())
            .collect();
        Ok(summary)
    }
}
