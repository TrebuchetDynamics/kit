//! Planning proposes; only the coordinator validates and publishes task changes.
use crate::task_store::Snapshot;
use crate::{Result, Unavailable};
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum PlanDisposition {
    RepairCurrent,
    SplitDependency,
    ChooseIndependent,
    DiscoverOffline,
    WaitExternal,
    NeedSudo,
    NeedCredential,
    RefusedScope,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FailureEvidence {
    pub operation_id: String,
    pub fingerprint: String,
    pub evidence_refs: Vec<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecordChange {
    pub path: std::path::PathBuf,
    pub expected_revision: String,
    pub proposed_bytes: Vec<u8>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanProposal {
    pub expected_revision: String,
    pub failed_operation: FailureEvidence,
    pub disposition: PlanDisposition,
    pub record_changes: Vec<RecordChange>,
    pub reason: String,
    pub sources: Vec<String>,
}

pub struct Planner;

impl Planner {
    pub fn propose(
        &self,
        _snapshot: &Snapshot,
        _failure_evidence: &FailureEvidence,
    ) -> Result<PlanProposal> {
        Err(Unavailable("Planner::propose"))
    }
}
