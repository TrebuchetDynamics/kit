//! Private runtime journal seam; observations cannot close canonical tasks.
use crate::runtime::{RunIdentity, RuntimeEvent};
use crate::{Result, Unavailable};

#[derive(Clone, Copy, Debug)]
pub enum DurableStatus {
    Ready,
    Planning,
    Executing,
    Checking,
    Reviewing,
    Integrating,
    Complete,
    WaitingExternal,
    WaitingSudo,
    WaitingCredential,
    Paused,
    Uncertain,
    Refused,
}

pub struct Transition {
    pub identity: RunIdentity,
    pub status: DurableStatus,
    pub event: RuntimeEvent,
}

pub struct EventId(pub u64);

pub struct Observations {
    pub evidence_refs: Vec<String>,
}

pub struct RecoveryActions {
    pub reconcile_operation_ids: Vec<String>,
}

pub struct StateStore;

impl StateStore {
    pub fn transition(
        &self,
        _expected_generation: u64,
        _transition: Transition,
    ) -> Result<EventId> {
        Err(Unavailable("StateStore::transition"))
    }

    pub fn reconcile(&self, _observations: Observations) -> Result<RecoveryActions> {
        Err(Unavailable("StateStore::reconcile"))
    }
}
