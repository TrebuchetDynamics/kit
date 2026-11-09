//! Disposable repositories and the real native Octet runtime over loopback only.
use autowork_next::planning::*;
use autowork_next::runtime::*;
use autowork_next::state::StateStore;
use autowork_next::task_store::{Scope, TaskService, TaskStore};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{Read, Write};
use std::net::TcpListener;
use std::os::unix::fs::{MetadataExt, PermissionsExt};
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

struct Repo(PathBuf);
impl Repo {
    fn new(name: &str) -> Self {
        let path = std::env::temp_dir().join(format!("planning-{}-{name}", std::process::id()));
        std::fs::create_dir(&path).unwrap();
        let repo = Self(path);
        repo.git(&["init", "-q"]);
        repo.git(&["config", "user.email", "fixture@example.invalid"]);
        repo.git(&["config", "user.name", "Fixture"]);
        std::fs::create_dir_all(repo.0.join("tasks/items")).unwrap();
        std::fs::write(repo.0.join("tasks/items/LIVE.md"), task("LIVE", true)).unwrap();
        repo.git(&["add", "tasks"]);
        repo.git(&["commit", "-qm", "fixture"]);
        repo
    }
    fn git(&self, args: &[&str]) -> String {
        let output = Command::new("git")
            .arg("-C")
            .arg(&self.0)
            .args(args)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        String::from_utf8(output.stdout).unwrap().trim().into()
    }
    fn request(&self, state: &StateStore, generation: u64) -> AgentRequest {
        let meta = self.0.metadata().unwrap();
        let workspace = WorkspaceIdentity {
            canonical_path: self.0.clone(),
            device: meta.dev(),
            inode: meta.ino(),
        };
        AgentRequest {
            schema_version: 1,
            repo_id: state.repo_id().into(),
            task_id: "LIVE".into(),
            attempt_id: format!("planning-{generation}"),
            generation,
            role: Role::Planner,
            workspace: self.0.clone(),
            model_ref: "fixture".into(),
            contract_hash: TaskStore::read_at(&self.0, "HEAD").unwrap().tasks()["LIVE"]
                .contract_hash
                .clone(),
            source_revision: self.git(&["rev-parse", "HEAD"]),
            prompt: String::new(),
            admission: ExecutionAdmission {
                repo_id: state.repo_id().into(),
                repository: workspace.clone(),
                workspace,
                task_id: "LIVE".into(),
                attempt_id: format!("planning-{generation}"),
                generation,
                contract_hash: TaskStore::read_at(&self.0, "HEAD").unwrap().tasks()["LIVE"]
                    .contract_hash
                    .clone(),
                role: Role::Planner,
                allowed_write_paths: vec![],
                denied_paths: vec![],
                admitted_check_operation_ids: vec![],
            },
            check_operations: vec![],
        }
    }
}
impl Drop for Repo {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
        let _ = std::fs::remove_dir_all(self.0.with_extension("evidence"));
    }
}
fn task(id: &str, live: bool) -> String {
    format!(
        "+++\nschema = 1\nid = \"{id}\"\ntitle = \"Offline contract\"\nshort = \"Offline contract\"\nstatus = \"open\"\nsection = \"Next\"\nrank = 1\ndepends_on = []\ntouches = [\"src.txt\"]\nresources = [{}]\nkind = \"implementation\"\nownership = \"worker\"\nlive = \"denied\"\nscope = \"Bounded fixture work\"\nacceptance = [\"Keep acceptance\"]\nchecks = [\"fixture-check\"]\nexclusions = []\n+++\n",
        if live { "\"live\"" } else { "" }
    )
}
fn failure() -> FailureEvidence {
    FailureEvidence {
        operation_id: "blocked-queue".into(),
        fingerprint: "observed-input-v1".into(),
        evidence_refs: vec!["source:src.txt".into()],
    }
}
fn proposal(revision: &str) -> PlanProposal {
    PlanProposal {
        expected_revision: revision.into(),
        failed_operation: failure(),
        disposition: PlanDisposition::DiscoverOffline,
        record_changes: vec![RecordChange {
            path: "tasks/items/OFFLINE.md".into(),
            expected_revision: String::new(),
            proposed_bytes: task("OFFLINE", false).into_bytes(),
        }],
        reason: "Independent source-backed work".into(),
        sources: vec!["source:src.txt".into()],
    }
}
fn fixture(response: String) -> (String, std::thread::JoinHandle<()>) {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let url = format!("http://{}/", listener.local_addr().unwrap());
    let thread = std::thread::spawn(move || {
        let (mut stream, _) = listener.accept().unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(10)))
            .unwrap();
        let mut bytes = Vec::new();
        loop {
            let mut buf = [0; 4096];
            let n = stream.read(&mut buf).unwrap();
            assert!(n > 0);
            bytes.extend_from_slice(&buf[..n]);
            if let Some(at) = bytes.windows(4).position(|w| w == b"\r\n\r\n") {
                let headers = String::from_utf8_lossy(&bytes[..at]).to_lowercase();
                let len: usize = headers
                    .lines()
                    .find_map(|l| l.strip_prefix("content-length: "))
                    .unwrap()
                    .parse()
                    .unwrap();
                if bytes.len() >= at + 4 + len {
                    break;
                }
            }
        }
        let request: serde_json::Value = serde_json::from_slice(
            &bytes[bytes.windows(4).position(|w| w == b"\r\n\r\n").unwrap() + 4..],
        )
        .unwrap();
        assert!(
            request["tools"]
                .as_array()
                .unwrap()
                .iter()
                .all(|t| t["function"]["name"] == "read")
        );
        let body = format!(
            "data: {}\n\ndata: {}\n\ndata: [DONE]\n\n",
            serde_json::json!({"choices":[{"index":0,"delta":{"content":response},"finish_reason":null}]}),
            serde_json::json!({"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]})
        );
        write!(stream, "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
    });
    (url, thread)
}

#[tokio::test]
async fn replan_and_select_independent_offline_work() {
    let repo = Repo::new("offline");
    let state = StateStore::open(repo.0.join(".git")).unwrap();
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let request = repo.request(&state, 1);
    state
        .claim(0, request.identity(), snapshot.revision())
        .unwrap();
    let response = serde_json::to_string(&PlanResponse {
        generation: 1,
        contract_hash: request.contract_hash.clone(),
        proposal: proposal(snapshot.revision()),
        exhausted_search: None,
    })
    .unwrap();
    let (url, thread) = fixture(response);
    let evidence = repo.0.with_extension("evidence");
    std::fs::create_dir(&evidence).unwrap();
    std::fs::set_permissions(&evidence, std::fs::Permissions::from_mode(0o700)).unwrap();
    let runtime = Runtime::new(
        env!("CARGO_BIN_EXE_autowork-next").into(),
        evidence,
        BTreeMap::from([(
            "fixture".into(),
            ModelRoute {
                provider: "openai_chat".into(),
                model: "fixture".into(),
                base_url: url,
                secret_file: None,
            },
        )]),
        Duration::from_secs(10),
    )
    .unwrap();
    let service = TaskService::new(&repo.0).unwrap();
    let planner = Planner::new(&runtime, &service, &state);
    let context = PlanningContext::new(request, BTreeSet::new(), vec![], vec![]);
    let outcome = planner
        .propose(&snapshot, &failure(), &context)
        .await
        .unwrap();
    let PlanOutcome::Pending {
        edit,
        snapshot: pending,
    } = outcome
    else {
        panic!("publication required")
    };
    assert_eq!(edit.paths, vec![PathBuf::from("tasks/items/OFFLINE.md")]);
    assert!(!pending.token.is_empty());
    assert_eq!(pending.base_head, snapshot.revision());
    assert_eq!(
        TaskStore::read_at(&repo.0, "HEAD").unwrap().records(),
        snapshot.records()
    );
    assert!(!snapshot.tasks()["LIVE"].runnable());
    assert!(
        !snapshot
            .select(&Scope::default())
            .unwrap()
            .task_ids
            .contains(&"OFFLINE".into())
    );
    assert!(matches!(
        planner
            .propose(&snapshot, &failure(), &context)
            .await
            .unwrap(),
        PlanOutcome::UnchangedEvidence
    ));
    thread.join().unwrap();
}

#[test]
fn classify_owner_help_and_reject_stale_plan() {
    let repo = Repo::new("validation");
    let state = StateStore::open(repo.0.join(".git")).unwrap();
    let service = TaskService::new(&repo.0).unwrap();
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let request = repo.request(&state, 1);
    state
        .claim(0, request.identity(), snapshot.revision())
        .unwrap();
    let context = PlanningContext::new(request.clone(), BTreeSet::new(), vec![], vec![]);
    let wrap = |proposal| PlanResponse {
        generation: 1,
        contract_hash: request.contract_hash.clone(),
        proposal,
        exhausted_search: None,
    };
    let mut stale = wrap(proposal(snapshot.revision()));
    stale.generation = 2;
    assert!(validate_and_apply(&service, &state, &snapshot, &failure(), &context, stale).is_err());
    let mut stale = wrap(proposal(snapshot.revision()));
    stale.proposal.failed_operation.fingerprint = "different".into();
    assert!(validate_and_apply(&service, &state, &snapshot, &failure(), &context, stale).is_err());
    let mut weakened = proposal(snapshot.revision());
    weakened.record_changes = vec![RecordChange {
        path: "tasks/items/LIVE.md".into(),
        expected_revision: snapshot.tasks()["LIVE"].record_revision.clone(),
        proposed_bytes: task("LIVE", true)
            .replace("Keep acceptance", "Weakened")
            .into_bytes(),
    }];
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            wrap(weakened)
        )
        .is_err()
    );
    let mut stale_revision = wrap(proposal(snapshot.revision()));
    stale_revision.proposal.expected_revision = "0".repeat(40);
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            stale_revision
        )
        .is_err()
    );
    let mut wrong_contract = wrap(proposal(snapshot.revision()));
    wrong_contract.contract_hash = "wrong".into();
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            wrong_contract
        )
        .is_err()
    );
    let in_flight = PlanningContext::new(
        request.clone(),
        BTreeSet::from(["LIVE".into()]),
        vec![],
        vec![],
    );
    let mut active_edit = proposal(snapshot.revision());
    active_edit.record_changes = vec![RecordChange {
        path: "tasks/items/LIVE.md".into(),
        expected_revision: snapshot.tasks()["LIVE"].record_revision.clone(),
        proposed_bytes: format!("{}Additional note.\n", task("LIVE", true)).into_bytes(),
    }];
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &in_flight,
            wrap(active_edit)
        )
        .is_err()
    );
    let secret_context = PlanningContext::new(
        request.clone(),
        BTreeSet::new(),
        vec![],
        vec!["sensitive-fixture".into()],
    );
    let mut secret = proposal(snapshot.revision());
    secret.record_changes[0]
        .proposed_bytes
        .extend_from_slice(b"sensitive-fixture");
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &secret_context,
            wrap(secret)
        )
        .is_err()
    );
    let mut unfounded = proposal(snapshot.revision());
    unfounded.sources = vec!["made-up".into()];
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            wrap(unfounded)
        )
        .is_err()
    );
    let mut empty = proposal(snapshot.revision());
    empty.record_changes.clear();
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            wrap(empty)
        )
        .is_err()
    );
    for disposition in [PlanDisposition::NeedSudo, PlanDisposition::NeedCredential] {
        let mut help = proposal(snapshot.revision());
        help.disposition = disposition.clone();
        help.record_changes.clear();
        assert!(
            validate_and_apply(
                &service,
                &state,
                &snapshot,
                &failure(),
                &context,
                wrap(help.clone())
            )
            .is_err()
        );
        let mut observed = context.clone();
        observed.prerequisites.push(ObservedPrerequisite {
            operation_id: failure().operation_id,
            fingerprint: failure().fingerprint,
            kind: if matches!(disposition, PlanDisposition::NeedSudo) {
                PrerequisiteKind::SudoRequired
            } else {
                PrerequisiteKind::CredentialRequired
            },
            evidence_ref: "observed:prerequisite".into(),
            resume_action: "Configure the prerequisite reference, then resume".into(),
        });
        assert!(matches!(
            validate_and_apply(
                &service,
                &state,
                &snapshot,
                &failure(),
                &observed,
                wrap(help)
            )
            .unwrap(),
            PlanOutcome::OwnerHelp(_)
        ));
    }
    for disposition in [PlanDisposition::WaitExternal, PlanDisposition::RefusedScope] {
        let mut p = proposal(snapshot.revision());
        p.disposition = disposition;
        p.record_changes.clear();
        assert!(matches!(
            validate_and_apply(&service, &state, &snapshot, &failure(), &context, wrap(p)).unwrap(),
            PlanOutcome::WaitingExternal | PlanOutcome::RefusedScope
        ));
    }
    let mut malicious = serde_json::to_value(wrap(proposal(snapshot.revision()))).unwrap();
    malicious["admission"] = serde_json::json!({"allowed_write_paths":["/"]});
    assert!(serde_json::from_value::<PlanResponse>(malicious).is_err());
    let newer = repo.request(&state, 2);
    state
        .claim(1, newer.identity(), snapshot.revision())
        .unwrap();
    assert!(
        validate_and_apply(
            &service,
            &state,
            &snapshot,
            &failure(),
            &context,
            wrap(proposal(snapshot.revision()))
        )
        .is_err()
    );
    assert!(!repo.0.join("tasks/items/OFFLINE.md").exists());
}
