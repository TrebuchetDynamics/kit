//! Sole future coordinator loop; no dispatch registry or Git effects yet.
use crate::task_store::{CommittedRevision, PendingSnapshot, Scope};
use crate::{Result, Unavailable};

pub struct RunSummary {
    pub completed_task_ids: Vec<String>,
    pub pending_task_ids: Vec<String>,
    pub evidence_refs: Vec<String>,
}

pub struct Coordinator;

impl Coordinator {
    pub async fn run_until_quiescent(&self, _scope: Scope) -> Result<RunSummary> {
        Err(Unavailable("Coordinator::run_until_quiescent"))
    }

    pub fn commit_proposal(&self, _snapshot: PendingSnapshot) -> Result<CommittedRevision> {
        Err(Unavailable("Coordinator::commit_proposal"))
    }
}
