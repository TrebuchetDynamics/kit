//! Owned-agent wire contracts. Native confirmations and reply channels stay local.
use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tokio::sync::mpsc::Receiver;

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

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RunIdentity {
    pub repo_id: String,
    pub task_id: String,
    pub attempt_id: String,
    pub generation: u64,
    pub role: Role,
    pub contract_hash: String,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
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

#[derive(Clone, Copy, Debug, Serialize, Deserialize)]
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

pub struct Runtime;

impl Runtime {
    pub async fn run(&self, _request: AgentRequest) -> Result<Receiver<RuntimeEvent>> {
        Err(Unavailable("runtime::run"))
    }

    pub async fn cancel(&self, _run_identity: RunIdentity) -> Result<()> {
        Err(Unavailable("runtime::cancel"))
    }
}

/// CLI-owned child entrypoint. Fail closed until role/effect admission, process
/// ownership and native cancellation are implemented; never fabricate an outcome.
pub async fn serve_owned_agent(_request: AgentRequest) -> Result<AgentResult> {
    Err(Unavailable("runtime::serve_owned_agent"))
}
