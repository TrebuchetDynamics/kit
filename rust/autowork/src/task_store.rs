//! Canonical task intent stays in revision-bound TOML files, not runtime state.
use crate::{Result, Unavailable};
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Clone, Debug)]
pub struct Scope {
    pub task_ids: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct Snapshot {
    pub revision: String,
    pub records: BTreeMap<String, Vec<u8>>,
}

#[derive(Clone, Debug)]
pub struct Selection {
    pub task_ids: Vec<String>,
}

pub struct TaskStore;

impl TaskStore {
    pub fn read_at(_repo: &Path, _revision: &str) -> Result<Snapshot> {
        Err(Unavailable("TaskStore::read_at"))
    }
}

impl Snapshot {
    pub fn select(&self, _scope: &Scope) -> Result<Selection> {
        Err(Unavailable("Snapshot::select"))
    }
}

#[derive(Clone, Debug)]
pub struct PendingEdit {
    pub expected_revision: String,
    pub paths: Vec<std::path::PathBuf>,
}

/// Captured publication input, never itself a committed/selectable revision.
#[derive(Clone, Debug)]
pub struct PendingSnapshot {
    pub base_head: String,
    pub branch: String,
    pub tree: String,
    pub captured_bytes: BTreeMap<String, Vec<u8>>,
    pub token: String,
}

#[derive(Clone, Debug)]
pub struct CommittedRevision(pub String);

pub struct TaskService;

impl TaskService {
    pub fn apply(
        &self,
        _expected_revision: &str,
        _proposal: &crate::planning::PlanProposal,
    ) -> Result<PendingEdit> {
        Err(Unavailable("TaskService::apply"))
    }

    pub fn capture_pending(&self) -> Result<PendingSnapshot> {
        Err(Unavailable("TaskService::capture_pending"))
    }
}
