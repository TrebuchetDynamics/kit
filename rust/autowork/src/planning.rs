//! Planning proposes; only the coordinator validates and publishes task changes.
use crate::runtime::{
    AgentRequest, Role, Runtime, RuntimeEventKind, RuntimeStatus, native_agent, native_ai,
};
use crate::state::{DurableStatus, EffectKind, RecordKind, StateStore, Transition};
use crate::task_store::{PendingEdit, PendingSnapshot, Snapshot, TaskService};
use crate::{Result, Unavailable};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
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

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
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
    #[serde(deserialize_with = "record_bytes")]
    pub proposed_bytes: Vec<u8>,
}

// Native JSON can express the exact UTF-8 record directly; existing byte arrays
// remain accepted for the foundation/TaskService wire contract.
fn record_bytes<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> std::result::Result<Vec<u8>, D::Error> {
    #[derive(Deserialize)]
    #[serde(untagged)]
    enum Bytes {
        Text(String),
        Bytes(Vec<u8>),
    }
    Ok(match Bytes::deserialize(deserializer)? {
        Bytes::Text(s) => s.into_bytes(),
        Bytes::Bytes(b) => b,
    })
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

/// Model response carries bindings, never admission or executable/check definitions.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PlanResponse {
    pub generation: u64,
    pub contract_hash: String,
    pub proposal: PlanProposal,
    pub exhausted_search: Option<ExhaustedSearch>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ExhaustedSearch {
    pub inspected_sources: Vec<String>,
    pub alternatives: Vec<String>,
    pub bound: u32,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum PrerequisiteKind {
    SudoRequired,
    CredentialRequired,
}
/// Coordinator-authored observation, not deserializable from model output.
#[derive(Clone, Debug)]
pub struct ObservedPrerequisite {
    pub operation_id: String,
    pub fingerprint: String,
    pub kind: PrerequisiteKind,
    pub evidence_ref: String,
    pub resume_action: String,
}
#[derive(Clone)]
pub struct PlanningContext {
    request: AgentRequest,
    in_flight: BTreeSet<String>,
    pub prerequisites: Vec<ObservedPrerequisite>,
    forbidden_values: Vec<String>,
}
impl PlanningContext {
    /// Construct only from the coordinator's current generation and secret references.
    pub fn new(
        request: AgentRequest,
        in_flight: BTreeSet<String>,
        prerequisites: Vec<ObservedPrerequisite>,
        forbidden_values: Vec<String>,
    ) -> Self {
        Self {
            request,
            in_flight,
            prerequisites,
            forbidden_values,
        }
    }
}
pub enum PlanOutcome {
    Pending {
        edit: PendingEdit,
        snapshot: PendingSnapshot,
    },
    OwnerHelp(ObservedPrerequisite),
    WaitingExternal,
    RefusedScope,
    Exhausted(ExhaustedSearch),
    UnchangedEvidence,
}
pub struct Planner<'a> {
    runtime: &'a Runtime,
    service: &'a TaskService,
    state: &'a StateStore,
}
fn refused<T>() -> Result<T> {
    Err(Unavailable("planning validation refused"))
}
fn bind(state: &StateStore, snapshot: &Snapshot, context: &PlanningContext) -> Result<()> {
    let request = &context.request;
    let a = &request.admission;
    if request.schema_version != crate::CONTRACT_VERSION
        || request.generation == 0
        || request.repo_id != a.repo_id
        || request.task_id != a.task_id
        || request.attempt_id != a.attempt_id
        || request.generation != a.generation
        || request.contract_hash != a.contract_hash
        || request.role != a.role
        || request.workspace != a.workspace.canonical_path
    {
        return refused();
    }
    if snapshot
        .tasks()
        .get(&request.task_id)
        .is_none_or(|task| task.contract_hash != request.contract_hash)
    {
        return refused();
    }
    if request.role != Role::Planner
        || request.source_revision != snapshot.revision()
        || !request.admission.allowed_write_paths.is_empty()
        || !request.check_operations.is_empty()
        || !request.admission.admitted_check_operation_ids.is_empty()
    {
        return refused();
    }
    let projection = state
        .projection(&request.task_id, request.generation)
        .map_err(|_| Unavailable("planning generation"))?;
    if projection.identity != request.identity()
        || projection.source_revision != snapshot.revision()
        || matches!(
            projection.status,
            DurableStatus::Paused
                | DurableStatus::Refused
                | DurableStatus::Complete
                | DurableStatus::Uncertain
        )
    {
        return refused();
    }
    // A newer claim fences this generation even if the old projection is unchanged.
    if state
        .events()
        .map_err(|_| Unavailable("planning journal"))?
        .iter()
        .any(|(_, event)| {
            event.identity.task_id == request.task_id
                && event.identity.generation > request.generation
        })
    {
        return refused();
    }
    Ok(())
}
fn marker(
    snapshot: &Snapshot,
    failure: &FailureEvidence,
    context: &PlanningContext,
) -> Result<String> {
    // Length-delimited JSON avoids collisions between user-controlled operation IDs.
    serde_json::to_string(&(
        "planning-input",
        snapshot.revision(),
        &context.request.task_id,
        &context.request.contract_hash,
        &failure.operation_id,
        &failure.fingerprint,
        &failure.evidence_refs,
    ))
    .map_err(|_| Unavailable("planning input"))
}
impl<'a> Planner<'a> {
    pub fn new(runtime: &'a Runtime, service: &'a TaskService, state: &'a StateStore) -> Self {
        Self {
            runtime,
            service,
            state,
        }
    }
    pub async fn propose(
        &self,
        snapshot: &Snapshot,
        failure: &FailureEvidence,
        context: &PlanningContext,
    ) -> Result<PlanOutcome> {
        bind(self.state, snapshot, context)?;
        if failure.operation_id.is_empty()
            || failure.fingerprint.is_empty()
            || failure.evidence_refs.is_empty()
        {
            return refused();
        }
        let input = marker(snapshot, failure, context)?;
        if self
            .state
            .events()
            .map_err(|_| Unavailable("planning journal"))?
            .iter()
            .any(|(_, e)| e.event.evidence_ref.as_deref() == Some(&input))
        {
            return Ok(PlanOutcome::UnchangedEvidence);
        }
        let mut request = context.request.clone();
        // Bundled instructions are Kit-owned, never read from a consumer checkout.
        let records: Vec<_> = snapshot
            .records()
            .iter()
            .map(|(p, b)| (p, String::from_utf8_lossy(b)))
            .collect();
        request.prompt = format!(
            "{}\n{}\nREAD-ONLY COORDINATOR SUBSTEP: Return only one strict JSON PlanResponse, no fences. Do not dispatch, write records, mark done, emit admission or propose executable argv. Preserve acceptance, live gates and active contracts. Only observed prerequisites justify owner help. A wait is not completion. An exhausted result requires bounded source-backed alternatives. Bind generation {} and contract {}. Snapshot revision: {}. Failure: {}. Records: {}. Observed prerequisites: {:?}",
            include_str!("../../../skills/plan-for-me/SKILL.md"),
            include_str!("../../../skills/shared/RESEARCH-PLAN.md"),
            request.generation,
            request.contract_hash,
            snapshot.revision(),
            serde_json::to_string(failure).map_err(|_| Unavailable("planning evidence"))?,
            serde_json::to_string(&records).map_err(|_| Unavailable("planning snapshot"))?,
            context.prerequisites
        );
        request.prompt.push_str(r#"
Response shape (all listed fields required; no additional fields):
{"generation":<host generation>,"contract_hash":<host contract>,"proposal":{"expected_revision":<snapshot revision>,"failed_operation":<exact supplied failure object>,"disposition":"discover_offline","record_changes":[{"path":"tasks/items/NEW-ID.md","expected_revision":"","proposed_bytes":"complete UTF-8 schema-1 record, including +++ delimiters"}],"reason":"source-backed explanation","sources":[<supplied inspected evidence reference>]},"exhausted_search":null}
Disposition is one of repair_current, split_dependency, choose_independent, discover_offline, wait_external, need_sudo, need_credential, refused_scope. Non-edit dispositions require an empty record_changes array. An exhausted wait additionally needs exhausted_search={"inspected_sources":[<supplied evidence refs>],"alternatives":[<at least two concrete rejected alternatives>],"bound":<2..16>}. Existing record expected_revision is its supplied SHA-256; a new record uses an empty revision. Preserve existing acceptance and all in-flight contracts. Record sources may only cite coordinator-supplied inspected evidence references; request another inspection when needed.
"#);
        let child_operation = format!("planner-child-{}-{}", request.task_id, request.generation);
        let intent = crate::runtime::RuntimeEvent {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: request.repo_id.clone(),
            task_id: request.task_id.clone(),
            attempt_id: request.attempt_id.clone(),
            generation: request.generation,
            contract_hash: request.contract_hash.clone(),
            source_revision: request.source_revision.clone(),
            role: request.role,
            operation_id: child_operation.clone(),
            event: RuntimeEventKind::Accepted,
            status: RuntimeStatus::Running,
            evidence_ref: Some(input.clone()),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map_err(|_| Unavailable("planner time"))?
                .as_secs()
                .to_string(),
        };
        self.state
            .transition(
                request.generation,
                Transition {
                    key: format!("{child_operation}/intent"),
                    identity: request.identity(),
                    status: DurableStatus::Planning,
                    event: intent.clone(),
                    kind: RecordKind::Intent(EffectKind::Child),
                },
            )
            .map_err(|_| Unavailable("planner dispatch journal"))?;
        let mut events = self.runtime.run(request.clone()).await?;
        let mut terminal = None;
        let mut sequence = 0u64;
        while let Some(mut event) = events.recv().await {
            sequence += 1;
            if event.event == RuntimeEventKind::Outcome {
                terminal = Some(event.status);
            }
            event.evidence_ref = Some(input.clone());
            self.state
                .transition(
                    request.generation,
                    Transition {
                        key: format!(
                            "planner/{}/{}/{}/{:?}/{sequence}",
                            request.task_id, request.generation, event.operation_id, event.event
                        ),
                        identity: request.identity(),
                        status: DurableStatus::Planning,
                        event,
                        kind: RecordKind::Note,
                    },
                )
                .map_err(|_| Unavailable("planning journal"))?;
        }
        if let Some(status) = terminal {
            let mut completed = intent;
            completed.event = RuntimeEventKind::Outcome;
            completed.status = status;
            self.state
                .transition(
                    request.generation,
                    Transition {
                        key: format!("{child_operation}/complete"),
                        identity: request.identity(),
                        status: DurableStatus::Planning,
                        event: completed,
                        kind: RecordKind::Completion,
                    },
                )
                .map_err(|_| Unavailable("planner completion journal"))?;
        }
        if terminal != Some(RuntimeStatus::Succeeded) {
            return Err(Unavailable("planner native outcome"));
        }
        let owned = self
            .runtime
            .owned_process(&request.identity())
            .ok_or(Unavailable("planner evidence"))?;
        let path = owned.evidence_dir.join("session.jsonl");
        // Bounded private transcript; never copy model/tool prose to public events.
        if std::fs::metadata(&path)
            .map_err(|_| Unavailable("planner transcript"))?
            .len()
            > 4 * 1024 * 1024
        {
            return refused();
        }
        let session = native_agent::Session::open_read_only(path)
            .map_err(|_| Unavailable("planner transcript"))?;
        let text = session
            .entries()
            .iter()
            .rev()
            .find_map(|entry| match &entry.value {
                native_agent::session::EntryValue::Message(native_ai::Message::Assistant(
                    message,
                )) => Some(
                    message
                        .content
                        .iter()
                        .filter_map(|part| match part {
                            native_ai::AssistantPart::Text(t) => Some(t.as_str()),
                            _ => None,
                        })
                        .collect::<String>(),
                ),
                _ => None,
            })
            .ok_or(Unavailable("planner response"))?;
        if context
            .forbidden_values
            .iter()
            .any(|s| !s.is_empty() && text.contains(s))
        {
            return refused();
        }
        let response: PlanResponse =
            serde_json::from_str(&text).map_err(|_| Unavailable("planner response schema"))?;
        validate_and_apply(
            self.service,
            self.state,
            snapshot,
            failure,
            context,
            response,
        )
    }
}
fn header(bytes: &[u8]) -> Result<toml::Table> {
    let text = std::str::from_utf8(bytes).map_err(|_| Unavailable("planner record encoding"))?;
    let mut lines = text.lines();
    if lines.next() != Some("+++") {
        return refused();
    }
    let header: String = lines
        .take_while(|l| *l != "+++")
        .map(|l| format!("{l}\n"))
        .collect();
    toml::from_str(&header).map_err(|_| Unavailable("planner record header"))
}
/// Coordinator validation is deliberately callable separately from inference.
/// A valid edit returns a publication token; no uncommitted Snapshot is exposed.
pub fn validate_and_apply(
    service: &TaskService,
    state: &StateStore,
    snapshot: &Snapshot,
    failure: &FailureEvidence,
    context: &PlanningContext,
    response: PlanResponse,
) -> Result<PlanOutcome> {
    bind(state, snapshot, context)?;
    let before = service
        .capture_pending()
        .map_err(|_| Unavailable("planning current source"))?;
    if before.base_head != snapshot.revision() || before.captured_bytes != *snapshot.records() {
        return refused();
    }
    let proposal = &response.proposal;
    if response.generation != context.request.generation
        || response.contract_hash != context.request.contract_hash
        || proposal.expected_revision != snapshot.revision()
        || &proposal.failed_operation != failure
        || proposal.reason.trim().is_empty()
        || proposal.sources.is_empty()
        || !proposal
            .sources
            .iter()
            .all(|s| !s.trim().is_empty() && failure.evidence_refs.contains(s))
    {
        return refused();
    }
    let encoded =
        serde_json::to_string(&response).map_err(|_| Unavailable("planner serialization"))?;
    if context
        .forbidden_values
        .iter()
        .any(|s| !s.is_empty() && encoded.contains(s))
    {
        return refused();
    }
    for change in &proposal.record_changes {
        let Some(path) = change.path.to_str() else {
            return refused();
        };
        let proposed_text = std::str::from_utf8(&change.proposed_bytes)
            .map_err(|_| Unavailable("planner encoding"))?;
        if context
            .forbidden_values
            .iter()
            .any(|s| !s.is_empty() && proposed_text.contains(s))
        {
            return refused();
        }
        let new = header(&change.proposed_bytes)?;
        if let Some(old_bytes) = snapshot.records().get(path) {
            let old = header(old_bytes)?;
            let id = old.get("id").and_then(toml::Value::as_str).unwrap_or("");
            if context.in_flight.contains(id) && old_bytes != &change.proposed_bytes {
                return refused();
            }
            for key in [
                "acceptance",
                "checks",
                "exclusions",
                "touches",
                "resources",
                "verified_depends_on",
            ] {
                if old.get(key) != new.get(key) {
                    return refused();
                }
            }
            // Splits may add prerequisites, never remove existing obligations.
            if old
                .get("depends_on")
                .and_then(toml::Value::as_array)
                .is_some_and(|deps| {
                    deps.iter().any(|dep| {
                        !new.get("depends_on")
                            .and_then(toml::Value::as_array)
                            .is_some_and(|n| n.contains(dep))
                    })
                })
            {
                return refused();
            }
        }
    }
    match proposal.disposition {
        PlanDisposition::NeedSudo | PlanDisposition::NeedCredential => {
            if !proposal.record_changes.is_empty() {
                return refused();
            }
            let kind = if proposal.disposition == PlanDisposition::NeedSudo {
                PrerequisiteKind::SudoRequired
            } else {
                PrerequisiteKind::CredentialRequired
            };
            let observed = context
                .prerequisites
                .iter()
                .find(|p| {
                    p.kind == kind
                        && p.operation_id == failure.operation_id
                        && p.fingerprint == failure.fingerprint
                        && !p.evidence_ref.is_empty()
                        && !p.resume_action.trim().is_empty()
                })
                .ok_or(Unavailable("unobserved prerequisite"))?;
            Ok(PlanOutcome::OwnerHelp(observed.clone()))
        }
        PlanDisposition::WaitExternal | PlanDisposition::RefusedScope => {
            if !proposal.record_changes.is_empty() {
                return refused();
            }
            if let Some(search) = response.exhausted_search {
                if proposal.disposition != PlanDisposition::WaitExternal
                    || search.bound == 0
                    || search.bound > 16
                    || search.alternatives.len() < 2
                    || search.alternatives.len() > search.bound as usize
                    || search.inspected_sources.is_empty()
                    || !search
                        .inspected_sources
                        .iter()
                        .all(|s| failure.evidence_refs.contains(s) || proposal.sources.contains(s))
                {
                    return refused();
                }
                return Ok(PlanOutcome::Exhausted(search));
            }
            Ok(if proposal.disposition == PlanDisposition::WaitExternal {
                PlanOutcome::WaitingExternal
            } else {
                PlanOutcome::RefusedScope
            })
        }
        _ => {
            if proposal.record_changes.is_empty() || response.exhausted_search.is_some() {
                return refused();
            }
            let edit = service
                .apply(snapshot.revision(), proposal)
                .map_err(|_| Unavailable("planner task application"))?;
            let pending = service
                .capture_pending()
                .map_err(|_| Unavailable("planner snapshot capture"))?;
            if pending.captured_bytes == *snapshot.records() {
                return refused();
            }
            Ok(PlanOutcome::Pending {
                edit,
                snapshot: pending,
            })
        }
    }
}
