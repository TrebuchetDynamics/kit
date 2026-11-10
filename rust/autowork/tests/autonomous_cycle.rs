//! Public coordinator seam; real native Octet over deterministic loopback, no Pi/Python/model billing.
use autowork_next::{execution::*, planning::*, runtime::*, state::StateStore, task_store::*};
use serde_json::{Value, json};
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::process::Command;
use std::sync::{
    Arc, Mutex,
    atomic::{AtomicBool, Ordering},
};
use std::time::Duration;

struct Repo(PathBuf);
impl Repo {
    fn new(name: &str, tasks: &[(&str, &str, &str)]) -> Self {
        let repo = Self(std::env::temp_dir().join(format!("cycle-{}-{name}", std::process::id())));
        std::fs::create_dir(&repo.0).unwrap();
        repo.git(&["init", "-q"]);
        repo.git(&["config", "user.email", "fixture@example.invalid"]);
        repo.git(&["config", "user.name", "Fixture"]);
        std::fs::create_dir_all(repo.0.join("tasks/items")).unwrap();
        for (id, section, check) in tasks {
            std::fs::write(
                repo.0.join(format!("tasks/items/{id}.md")),
                task(id, section, check),
            )
            .unwrap();
            if *id != "B" {
                std::fs::write(repo.0.join(format!("{id}.txt")), "before\n").unwrap();
            }
        }
        for name in ["staged.txt", "dirty.txt"] {
            std::fs::write(repo.0.join(name), "base\n").unwrap();
        }
        repo.git(&["add", "."]);
        repo.git(&["commit", "-qm", "fixture"]);
        repo
    }
    fn git(&self, args: &[&str]) -> String {
        let out = Command::new("/usr/bin/git")
            .arg("-C")
            .arg(&self.0)
            .args(args)
            .output()
            .unwrap();
        assert!(
            out.status.success(),
            "{args:?}: {}",
            String::from_utf8_lossy(&out.stderr)
        );
        String::from_utf8(out.stdout)
            .unwrap()
            .trim_end_matches('\n')
            .into()
    }
    fn state(&self) -> StateStore {
        // Parallel test subprocesses can briefly inherit a closing lock before exec.
        let deadline = std::time::Instant::now() + Duration::from_secs(5);
        loop {
            match StateStore::open(self.0.join(".git")) {
                Ok(state) => return state,
                Err(error)
                    if error.0 == "repository journal writer is owned"
                        && std::time::Instant::now() < deadline =>
                {
                    std::thread::sleep(Duration::from_millis(5));
                }
                Err(error) => panic!("{}: {error}", self.0.display()),
            }
        }
    }
    fn dirty(&self) -> String {
        std::fs::write(self.0.join("staged.txt"), "staged bytes\n").unwrap();
        self.git(&["add", "staged.txt"]);
        std::fs::write(self.0.join("staged.txt"), "unstaged bytes\n").unwrap();
        std::fs::write(self.0.join("dirty.txt"), "dirty bytes\n").unwrap();
        self.git(&["diff", "--cached", "--binary", "--", "staged.txt"])
    }
    fn assert_dirty(&self, staged: &str) {
        assert_eq!(
            self.git(&["diff", "--cached", "--binary", "--", "staged.txt"]),
            staged
        );
        assert_eq!(
            std::fs::read(self.0.join("staged.txt")).unwrap(),
            b"unstaged bytes\n"
        );
        assert_eq!(
            std::fs::read(self.0.join("dirty.txt")).unwrap(),
            b"dirty bytes\n"
        );
    }
    fn runtime(&self, fixture: &Fixture) -> Runtime {
        let evidence = self.0.join(".git/native-evidence");
        std::fs::create_dir_all(&evidence).unwrap();
        std::fs::set_permissions(&evidence, std::fs::Permissions::from_mode(0o700)).unwrap();
        Runtime::new(
            binary(),
            evidence,
            ["worker", "reviewer", "planner"]
                .into_iter()
                .map(|model| {
                    (
                        model.into(),
                        ModelRoute {
                            provider: "openai_chat".into(),
                            model: model.into(),
                            base_url: fixture.url.clone(),
                            secret_file: None,
                        },
                    )
                })
                .collect(),
            Duration::from_secs(15),
        )
        .unwrap()
    }
}
impl Drop for Repo {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn binary() -> PathBuf {
    env!("CARGO_BIN_EXE_autowork-next").into()
}
fn task(id: &str, section: &str, check: &str) -> String {
    format!(
        "+++\nschema = 1\nid = \"{id}\"\ntitle = \"Offline {id}\"\nshort = \"Offline {id}\"\nstatus = \"open\"\nsection = \"{section}\"\nrank = 1\ndepends_on = []\ntouches = [\"{id}.txt\"]\nresources = []\nkind = \"implementation\"\nownership = \"worker\"\nlive = \"denied\"\nscope = \"Write the offline fixture file\"\nacceptance = [\"The admitted file contains after\"]\nchecks = [\"{check}\"]\nexclusions = [\"No live execution\"]\n+++\n"
    )
}
fn options() -> RunOptions {
    RunOptions {
        worker_model: "worker".into(),
        reviewer_model: "reviewer".into(),
        planner_model: "planner".into(),
        max_tasks: None,
        allow_commit: true,
        control: Control::default(),
        prerequisites: vec![],
    }
}
fn coordinator<'a>(
    repo: &Repo,
    runtime: &'a Runtime,
    service: &'a TaskService,
    state: &'a StateStore,
    options: RunOptions,
) -> Coordinator<'a> {
    let mut c = Coordinator::new(&repo.0, &binary(), runtime, service, state, options).unwrap();
    c.enable_fixture_checks();
    c
}

struct Fixture {
    url: String,
    stop: Arc<AtomicBool>,
    thread: Option<std::thread::JoinHandle<()>>,
    calls: Arc<Mutex<Vec<String>>>,
}
impl Fixture {
    fn new(
        offset: u16,
        repo: &Repo,
        reject: bool,
        disposition: &str,
        control: Option<Control>,
    ) -> Self {
        let listener = if let Ok(base) = std::env::var("AUTOWORK_PORT_BASE") {
            let base = base.parse::<u16>().unwrap();
            std::iter::once(offset)
                .chain(20..100)
                .find_map(|offset| TcpListener::bind(("127.0.0.1", base + offset)).ok())
                .expect("no available port in the task's reserved fixture range")
        } else {
            TcpListener::bind(("127.0.0.1", 0)).unwrap()
        };
        listener.set_nonblocking(true).unwrap();
        let url = format!("http://{}/", listener.local_addr().unwrap());
        let stop = Arc::new(AtomicBool::new(false));
        let calls = Arc::new(Mutex::new(Vec::new()));
        let (end, log, root, disposition) = (
            stop.clone(),
            calls.clone(),
            repo.0.clone(),
            disposition.to_string(),
        );
        let thread = std::thread::spawn(move || {
            while !end.load(Ordering::SeqCst) {
                match listener.accept() {
                    Ok((stream, _)) => {
                        respond(stream, &root, reject, &disposition, &log, control.as_ref())
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        std::thread::sleep(Duration::from_millis(2))
                    }
                    Err(e) => panic!("{e}"),
                }
            }
        });
        Self {
            url,
            stop,
            thread: Some(thread),
            calls,
        }
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        self.thread.take().unwrap().join().unwrap();
    }
}
fn respond(
    mut stream: TcpStream,
    repo: &PathBuf,
    reject: bool,
    disposition: &str,
    calls: &Mutex<Vec<String>>,
    control: Option<&Control>,
) {
    stream
        .set_read_timeout(Some(Duration::from_secs(10)))
        .unwrap();
    let mut bytes = Vec::new();
    let request = loop {
        let mut buf = [0; 8192];
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
                break serde_json::from_slice::<Value>(&bytes[at + 4..at + 4 + len]).unwrap();
            }
        }
    };
    let model = request["model"].as_str().unwrap();
    calls.lock().unwrap().push(model.into());
    let text = request["messages"]
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|m| m["content"].as_str())
        .collect::<Vec<_>>()
        .join("\n");
    let has_tool_result = request["messages"]
        .as_array()
        .unwrap()
        .iter()
        .any(|m| m["role"] == "tool");
    let delta = match model {
        "worker" => {
            let id = ["A", "B", "C"]
                .into_iter()
                .find(|id| text.contains(&format!("id = \"{id}\"")))
                .unwrap();
            if id == "C" {
                // Discovered/repaired intent must already be a durable tasks-only commit.
                let output = Command::new("/usr/bin/git")
                    .arg("-C")
                    .arg(repo)
                    .args(["log", "-1", "--format=%B"])
                    .output()
                    .unwrap();
                assert!(
                    String::from_utf8(output.stdout)
                        .unwrap()
                        .contains("proposal-")
                );
                assert!(TaskStore::read_at(repo, "HEAD").unwrap().tasks()["C"].runnable());
            }
            if !has_tool_result {
                json!({"tool_calls":[{"index":0,"id":"write-fixture","type":"function","function":{
                    "name":"write","arguments":json!({"path":format!("{id}.txt"),"content":"after\n"}).to_string()}}]})
            } else {
                if let Some(control) = control {
                    control.pause();
                }
                json!({"content":"implemented"})
            }
        }
        "reviewer" => {
            assert!(
                request["tools"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .all(|t| t["function"]["name"] == "read")
            );
            let raw = text
                .split("Return ONLY JSON ")
                .nth(1)
                .unwrap()
                .split(". Reject unmet")
                .next()
                .unwrap();
            let review: Value = serde_json::from_str(
                &raw.replace("true|false", if reject { "false" } else { "true" }),
            )
            .unwrap();
            json!({"content":review.to_string()})
        }
        "planner" => {
            assert!(
                request["tools"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .all(|t| t["function"]["name"] == "read")
            );
            let snapshot = TaskStore::read_at(repo, "HEAD").unwrap();
            let generation: u64 = text
                .split("Bind generation ")
                .nth(1)
                .unwrap()
                .split(' ')
                .next()
                .unwrap()
                .parse()
                .unwrap();
            let contract = text
                .split(" and contract ")
                .nth(1)
                .unwrap()
                .split('.')
                .next()
                .unwrap();
            let failure =
                serde_json::Deserializer::from_str(text.split("Failure: ").nth(1).unwrap())
                    .into_iter::<FailureEvidence>()
                    .next()
                    .unwrap()
                    .unwrap();
            if failure.operation_id.starts_with("failed-task-") {
                assert!(text.contains("Coordinator-observed failure data"));
                assert!(
                    text.contains("required candidate check failed")
                        || text.contains("independent review rejected")
                        || text.contains("unsupported required check operation")
                );
            }
            let changes = if disposition == "repair_current" {
                vec![RecordChange {
                    path: "tasks/items/C.md".into(),
                    expected_revision: snapshot.tasks()["C"].record_revision.clone(),
                    proposed_bytes: task("C", "Next", "fixture-pass").into_bytes(),
                }]
            } else {
                vec![]
            };
            let response = PlanResponse {
                generation,
                contract_hash: contract.into(),
                exhausted_search: None,
                proposal: PlanProposal {
                    expected_revision: snapshot.revision().into(),
                    failed_operation: failure.clone(),
                    disposition: serde_json::from_value(json!(disposition)).unwrap(),
                    record_changes: changes,
                    reason: "Routine offline decision from the accepted committed source".into(),
                    sources: failure.evidence_refs,
                },
            };
            if let Some(control) = control {
                control.pause();
            }
            json!({"content":serde_json::to_string(&response).unwrap()})
        }
        _ => panic!("unknown fixture role"),
    };
    let finish = if delta.get("tool_calls").is_some() {
        "tool_calls"
    } else {
        "stop"
    };
    let body = format!(
        "data: {}\n\ndata: {}\n\ndata: [DONE]\n\n",
        json!({"choices":[{"index":0,"delta":delta,"finish_reason":null}]}),
        json!({"choices":[{"index":0,"delta":{},"finish_reason":finish}]})
    );
    write!(stream, "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}", body.len()).unwrap();
}

#[tokio::test]
async fn finish_multiple_tasks_and_replan() {
    let repo = Repo::new(
        "multiple",
        &[
            ("A", "Next", "git-diff-check"),
            ("B", "Next", "fixture-pass"),
            ("C", "Needs decision", "fixture-pass"),
        ],
    );
    let staged = repo.dirty();
    let fixture = Fixture::new(20, &repo, false, "repair_current", None);
    let runtime = repo.runtime(&fixture);
    let service = TaskService::new(&repo.0).unwrap();
    let state = repo.state();
    let c = coordinator(&repo, &runtime, &service, &state, options());
    let summary = c.run_until_quiescent(Scope::default()).await.unwrap();
    assert_eq!(summary.completed_task_ids, ["A", "B", "C"], "{summary:?}");
    assert!(summary.pending_task_ids.is_empty());
    assert_eq!(summary.disposition, "completed");
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    assert!(snapshot.tasks().values().all(Record::verified));
    assert_eq!(repo.git(&["rev-list", "--count", "--merges", "HEAD"]), "3");
    let log = repo.git(&["log", "--format=%B"]);
    assert_eq!(log.matches("proposal-").count(), 1);
    // Exact pending tree, no unrelated index content, became the proposal's durable tree.
    let effect = std::fs::read_dir(state.directory().join("cycle-effects"))
        .unwrap()
        .filter_map(|e| e.ok())
        .find(|e| {
            e.file_name().to_string_lossy().starts_with("proposal-")
                && e.path().extension().is_some_and(|s| s == "json")
        })
        .unwrap();
    let effect: Value = serde_json::from_slice(&std::fs::read(effect.path()).unwrap()).unwrap();
    let target = effect["target"].as_str().unwrap();
    assert_eq!(
        repo.git(&["rev-parse", &format!("{target}^{{tree}}")]),
        effect["pending"]["tree"]
    );
    assert_eq!(
        repo.git(&["diff-tree", "--no-commit-id", "--name-only", "-r", target]),
        "tasks/items/C.md"
    );
    repo.assert_dirty(&staged);
    let calls = fixture.calls.lock().unwrap().clone();
    assert_eq!(calls.iter().filter(|r| *r == "reviewer").count(), 3);
    assert_eq!(calls.iter().filter(|r| *r == "planner").count(), 1);
    assert!(
        c.run_until_quiescent(Scope::default())
            .await
            .unwrap()
            .completed_task_ids
            .is_empty()
    );
    assert_eq!(*fixture.calls.lock().unwrap(), calls);
    // Historical completion must not pin a pruned or reopened task forever.
    std::fs::remove_file(repo.0.join("tasks/items/C.md")).unwrap();
    repo.git(&[
        "commit",
        "--only",
        "-qm",
        "prune completed fixture",
        "--",
        "tasks/items/C.md",
    ]);
    assert_eq!(
        c.run_until_quiescent(Scope::default())
            .await
            .unwrap()
            .disposition,
        "completed"
    );
    let reopened = task("C", "Needs decision", "fixture-pass").replace(
        "The admitted file contains after",
        "New accepted qualification",
    );
    std::fs::write(repo.0.join("tasks/items/C.md"), &reopened).unwrap();
    repo.git(&["add", "--", "tasks/items/C.md"]);
    repo.git(&[
        "commit",
        "--only",
        "-qm",
        "reopen changed fixture",
        "--",
        "tasks/items/C.md",
    ]);
    let waiting = Fixture::new(31, &repo, false, "wait_external", None);
    let runtime = repo.runtime(&waiting);
    let summary = coordinator(&repo, &runtime, &service, &state, options())
        .run_until_quiescent(Scope::default())
        .await
        .unwrap();
    assert_eq!(summary.pending_task_ids, ["C"]);
    assert_eq!(summary.disposition, "waiting_external");
    assert_eq!(
        std::fs::read_to_string(repo.0.join("tasks/items/C.md")).unwrap(),
        reopened
    );
    repo.assert_dirty(&staged);
}

#[tokio::test]
async fn recover_git_effects_without_false_closure() {
    // Failed checks and rejected independent review retain the original open contract.
    for (index, check, reject) in [
        (0, "fixture-fail", false),
        (1, "fixture-pass", true),
        (2, "echo accepted; touch hacked", false),
        (3, "unknown-operation", false),
    ] {
        let repo = Repo::new(&format!("reject-{index}"), &[("A", "Next", check)]);
        let staged = repo.dirty();
        let base = repo.git(&["rev-parse", "HEAD"]);
        let fixture = Fixture::new(21, &repo, reject, "wait_external", None);
        let runtime = repo.runtime(&fixture);
        let service = TaskService::new(&repo.0).unwrap();
        let state = repo.state();
        let result = coordinator(&repo, &runtime, &service, &state, options())
            .run_until_quiescent(Scope::default())
            .await
            .unwrap();
        assert_eq!(result.pending_task_ids, ["A"]);
        assert!(result.completed_task_ids.is_empty());
        assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
        assert_eq!(
            TaskStore::read_at(&repo.0, "HEAD").unwrap().tasks()["A"].strings("checks"),
            [check]
        );
        repo.assert_dirty(&staged);
        if index >= 2 {
            assert!(fixture.calls.lock().unwrap().iter().all(|r| r == "planner"));
        }
    }
    // Reopen both journal and Runtime at every external-effect crash boundary.
    for (i, fault) in [
        FaultPoint::AfterProposalApply,
        FaultPoint::BeforeProposalCommit,
        FaultPoint::AfterProposalCommit,
        FaultPoint::BeforeSelection,
        FaultPoint::IntegrationCheckout,
        FaultPoint::IntegrationRef,
        FaultPoint::AfterChildOutcome,
    ]
    .into_iter()
    .enumerate()
    {
        let proposal = i < 4;
        let repo = Repo::new(
            &format!("crash-{i}"),
            &[(
                if proposal { "C" } else { "A" },
                if proposal { "Needs decision" } else { "Next" },
                "fixture-pass",
            )],
        );
        let staged = repo.dirty();
        let fixture = Fixture::new(22, &repo, false, "repair_current", None);
        let service = TaskService::new(&repo.0).unwrap();
        {
            let runtime = repo.runtime(&fixture);
            let state = repo.state();
            let mut c = coordinator(&repo, &runtime, &service, &state, options());
            c.inject_fault(fault);
            if fault == FaultPoint::BeforeSelection {
                // Publish first, then crash at the selection seam.
                let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
                service
                    .apply(
                        snapshot.revision(),
                        &PlanProposal {
                            expected_revision: snapshot.revision().into(),
                            failed_operation: FailureEvidence {
                                operation_id: "fixture".into(),
                                fingerprint: "fixture".into(),
                                evidence_refs: vec!["fixture".into()],
                            },
                            disposition: PlanDisposition::RepairCurrent,
                            record_changes: vec![RecordChange {
                                path: "tasks/items/C.md".into(),
                                expected_revision: snapshot.tasks()["C"].record_revision.clone(),
                                proposed_bytes: task("C", "Next", "fixture-pass").into_bytes(),
                            }],
                            reason: "routine".into(),
                            sources: vec!["fixture".into()],
                        },
                    )
                    .unwrap();
                c.commit_proposal(service.capture_pending().unwrap())
                    .unwrap();
            }
            assert!(
                c.run_until_quiescent(Scope::default()).await.is_err(),
                "{fault:?}"
            );
            assert!(
                TaskStore::read_at(&repo.0, "HEAD")
                    .unwrap()
                    .tasks()
                    .values()
                    .all(|t| !t.verified())
            );
        }
        {
            let runtime = repo.runtime(&fixture);
            let state = repo.state();
            let c = coordinator(&repo, &runtime, &service, &state, options());
            let before_calls = fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .filter(|r| *r == "worker")
                .count();
            let recovered = c.run_until_quiescent(Scope::default()).await.unwrap();
            if fault == FaultPoint::AfterChildOutcome {
                assert_eq!(
                    fixture
                        .calls
                        .lock()
                        .unwrap()
                        .iter()
                        .filter(|r| *r == "worker")
                        .count(),
                    before_calls
                );
            }
            assert!(
                TaskStore::read_at(&repo.0, "HEAD")
                    .unwrap()
                    .tasks()
                    .values()
                    .all(Record::verified),
                "{fault:?}: {recovered:?}"
            );
            assert_eq!(repo.git(&["rev-list", "--count", "--merges", "HEAD"]), "1");
            let log = repo.git(&["log", "--format=%B"]);
            assert_eq!(log.matches("proposal-").count(), usize::from(proposal));
            let calls = fixture.calls.lock().unwrap().len();
            c.run_until_quiescent(Scope::default()).await.unwrap();
            assert_eq!(fixture.calls.lock().unwrap().len(), calls);
        }
        repo.assert_dirty(&staged);
    }
    // Hooks run off-branch, cannot publish a changed tree, and are never replayed after failure/interruption.
    for (i, body) in [
        "printf 'hook mutation\\n' > staged.txt\n/usr/bin/git add -- staged.txt\n",
        "exit 1\n",
        "kill -KILL \"$PPID\"\n",
    ]
    .into_iter()
    .enumerate()
    {
        let repo = Repo::new(
            &format!("hook-{i}"),
            &[("C", "Needs decision", "fixture-pass")],
        );
        let staged = repo.dirty();
        let base = repo.git(&["rev-parse", "HEAD"]);
        std::fs::write(
            repo.0.join("tasks/items/C.md"),
            task("C", "Next", "fixture-pass"),
        )
        .unwrap();
        let hook = repo.0.join(".git/hooks/pre-commit");
        std::fs::write(&hook, format!("#!/bin/sh\ncommon=$(/usr/bin/git rev-parse --git-common-dir)\nprintf 'called\\n' >> \"$common/hook-calls\"\n{body}")).unwrap();
        std::fs::set_permissions(&hook, std::fs::Permissions::from_mode(0o700)).unwrap();
        let fixture = Fixture::new(27, &repo, false, "wait_external", None);
        let service = TaskService::new(&repo.0).unwrap();
        {
            let runtime = repo.runtime(&fixture);
            let state = repo.state();
            assert!(
                coordinator(&repo, &runtime, &service, &state, options())
                    .commit_proposal(service.capture_pending().unwrap())
                    .is_err()
            );
        }
        {
            let runtime = repo.runtime(&fixture);
            let state = repo.state();
            assert!(
                coordinator(&repo, &runtime, &service, &state, options())
                    .run_until_quiescent(Scope::default())
                    .await
                    .is_err()
            );
        }
        assert_eq!(
            std::fs::read_to_string(repo.0.join(".git/hook-calls")).unwrap(),
            "called\n"
        );
        assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
        repo.assert_dirty(&staged);
    }
    // A recovered apply never adopts later external task bytes as its captured proposal.
    let repo = Repo::new("apply-drift", &[("C", "Needs decision", "fixture-pass")]);
    let fixture = Fixture::new(28, &repo, false, "repair_current", None);
    let service = TaskService::new(&repo.0).unwrap();
    let base = repo.git(&["rev-parse", "HEAD"]);
    {
        let runtime = repo.runtime(&fixture);
        let state = repo.state();
        let mut c = coordinator(&repo, &runtime, &service, &state, options());
        c.inject_fault(FaultPoint::AfterProposalApply);
        assert!(c.run_until_quiescent(Scope::default()).await.is_err());
    }
    let changed = format!("{}External bytes.\n", task("C", "Next", "fixture-pass"));
    std::fs::write(repo.0.join("tasks/items/C.md"), &changed).unwrap();
    let runtime = repo.runtime(&fixture);
    let state = repo.state();
    assert!(
        coordinator(&repo, &runtime, &service, &state, options())
            .run_until_quiescent(Scope::default())
            .await
            .is_err()
    );
    assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
    assert_eq!(
        std::fs::read_to_string(repo.0.join("tasks/items/C.md")).unwrap(),
        changed
    );
}

#[tokio::test]
async fn respect_limits_and_explain_quiescence() {
    let repo = Repo::new(
        "limit",
        &[("A", "Next", "fixture-pass"), ("B", "Next", "fixture-pass")],
    );
    let fixture = Fixture::new(23, &repo, false, "wait_external", None);
    let runtime = repo.runtime(&fixture);
    let service = TaskService::new(&repo.0).unwrap();
    let state = repo.state();
    let mut limit = options();
    limit.max_tasks = Some(1);
    let result = coordinator(&repo, &runtime, &service, &state, limit)
        .run_until_quiescent(Scope::default())
        .await
        .unwrap();
    assert_eq!(result.completed_task_ids, ["A"], "{result:?}");
    assert_eq!(result.pending_task_ids, ["B"]);
    assert_eq!(result.disposition, "task_limit");
    {
        let repo = Repo::new(
            "failed-limit",
            &[("A", "Next", "fixture-fail"), ("B", "Next", "fixture-pass")],
        );
        let fixture = Fixture::new(29, &repo, false, "wait_external", None);
        let runtime = repo.runtime(&fixture);
        let service = TaskService::new(&repo.0).unwrap();
        let state = repo.state();
        let mut o = options();
        o.max_tasks = Some(1);
        let summary = coordinator(&repo, &runtime, &service, &state, o)
            .run_until_quiescent(Scope::default())
            .await
            .unwrap();
        assert!(summary.completed_task_ids.is_empty());
        assert_eq!(summary.pending_task_ids, ["A", "B"]);
        assert_eq!(summary.disposition, "task_limit");
        assert_eq!(
            fixture
                .calls
                .lock()
                .unwrap()
                .iter()
                .filter(|r| *r == "worker")
                .count(),
            2
        );
    }
    for stopped in [false, true] {
        let o = options();
        if stopped {
            o.control.stop();
        } else {
            o.control.pause();
        }
        let count = fixture.calls.lock().unwrap().len();
        let result = coordinator(&repo, &runtime, &service, &state, o)
            .run_until_quiescent(Scope::default())
            .await
            .unwrap();
        assert_eq!(
            result.disposition,
            if stopped { "stopped" } else { "paused" }
        );
        assert_eq!(fixture.calls.lock().unwrap().len(), count);
    }
    // Unknown/model-authored operation strings never become executable authority.
    let registry =
        CheckRegistry::new(&binary(), &repo.0, &repo.git(&["rev-parse", "HEAD"]), true).unwrap();
    for id in ["echo accepted; touch hacked", "unknown-operation"] {
        assert!(registry.operation(id).is_err());
    }
    let spec = registry.operation("fixture-pass").unwrap().clone();
    let head = repo.git(&["rev-parse", "HEAD"]);
    let tree = repo.git(&["rev-parse", "HEAD^{tree}"]);
    let mut changed = spec.clone();
    changed.source_revision = "untrusted".into();
    assert!(
        registry
            .execute(&changed, &head, &tree, "contract")
            .is_err()
    );
    changed = spec.clone();
    changed.executable = "/bin/sh".into();
    assert!(
        registry
            .execute(&changed, &head, &tree, "contract")
            .is_err()
    );
    assert!(
        registry
            .execute(&spec, "untrusted-candidate", &tree, "contract")
            .is_err()
    );
    {
        let repo = Repo::new("executable-drift", &[("A", "Next", "fixture-pass")]);
        let copy = repo.0.join(".git/check-binary");
        std::fs::copy(binary(), &copy).unwrap();
        let head = repo.git(&["rev-parse", "HEAD"]);
        let tree = repo.git(&["rev-parse", "HEAD^{tree}"]);
        let registry = CheckRegistry::new(&copy, &repo.0, &head, true).unwrap();
        let spec = registry.operation("fixture-pass").unwrap();
        assert!(
            registry
                .execute(spec, &head, &tree, "contract")
                .unwrap()
                .passed
        );
        std::fs::write(&copy, b"changed executable identity").unwrap();
        assert!(registry.execute(spec, &head, &tree, "contract").is_err());
        std::fs::write(repo.0.join(".gitattributes"), "A.txt filter=unsafe\n").unwrap();
        std::fs::write(
            repo.0.join(".git/filter"),
            "printf ran > .git/FILTER-RAN\ncat\n",
        )
        .unwrap();
        repo.git(&["config", "filter.unsafe.clean", "sh .git/filter"]);
        let registry = CheckRegistry::new(&binary(), &repo.0, &head, true).unwrap();
        let error = registry
            .execute(
                registry.operation("fixture-pass").unwrap(),
                &head,
                &tree,
                "contract",
            )
            .unwrap_err();
        assert!(error.to_string().contains("content filters"));
        assert!(!repo.0.join(".git/FILTER-RAN").exists());
    }

    for (i, edit) in [
        (
            0,
            task("C", "Next", "fixture-pass")
                .replace("ownership = \"worker\"", "ownership = \"owner\""),
        ),
        (
            1,
            task("C", "Next", "fixture-pass").replace("resources = []", "resources = [\"live\"]"),
        ),
    ] {
        let repo = Repo::new(&format!("admission-{i}"), &[("C", "Next", "fixture-pass")]);
        std::fs::write(repo.0.join("tasks/items/C.md"), &edit).unwrap();
        repo.git(&["add", "tasks/items/C.md"]);
        repo.git(&["commit", "-qm", "host admission fixture"]);
        let fixture = Fixture::new(32, &repo, false, "wait_external", None);
        let runtime = repo.runtime(&fixture);
        let service = TaskService::new(&repo.0).unwrap();
        let state = repo.state();
        let summary = coordinator(&repo, &runtime, &service, &state, options())
            .run_until_quiescent(Scope::default())
            .await
            .unwrap();
        assert_eq!(summary.pending_task_ids, ["C"]);
        assert!(summary.completed_task_ids.is_empty());
        assert!(fixture.calls.lock().unwrap().iter().all(|r| r == "planner"));
        assert_eq!(
            std::fs::read_to_string(repo.0.join("tasks/items/C.md")).unwrap(),
            edit
        );
    }
    for (i, disposition, expected) in [
        (0, "wait_external", "waiting_external"),
        (1, "need_sudo", "waiting_sudo"),
        (2, "need_credential", "waiting_credential"),
    ] {
        let repo = Repo::new(
            &format!("help-{i}"),
            &[("C", "Needs decision", "fixture-pass")],
        );
        let fixture = Fixture::new(24, &repo, false, disposition, None);
        let runtime = repo.runtime(&fixture);
        let service = TaskService::new(&repo.0).unwrap();
        let state = repo.state();
        let mut o = options();
        if i > 0 {
            o.prerequisites.push(ObservedPrerequisite {
                operation_id: "queue-quiescent".into(),
                fingerprint: repo.git(&["rev-parse", "HEAD"]),
                kind: if i == 1 {
                    PrerequisiteKind::SudoRequired
                } else {
                    PrerequisiteKind::CredentialRequired
                },
                evidence_ref: "host-observed-prerequisite".into(),
                resume_action: "Provide the observed prerequisite reference, then resume".into(),
            });
        }
        let summary = coordinator(&repo, &runtime, &service, &state, o)
            .run_until_quiescent(Scope::default())
            .await
            .unwrap();
        assert_eq!(summary.disposition, expected);
        assert_eq!(summary.owner_help.is_some(), i > 0);
        assert_eq!(summary.pending_task_ids, ["C"]);
    }
    let repo = Repo::new("no-commit", &[("C", "Needs decision", "fixture-pass")]);
    let fixture = Fixture::new(25, &repo, false, "repair_current", None);
    let runtime = repo.runtime(&fixture);
    let service = TaskService::new(&repo.0).unwrap();
    let state = repo.state();
    std::fs::write(
        repo.0.join("tasks/items/C.md"),
        task("C", "Next", "fixture-pass"),
    )
    .unwrap();
    let pending = service.capture_pending().unwrap();
    let mut o = options();
    o.allow_commit = false;
    let c = coordinator(&repo, &runtime, &service, &state, o);
    assert!(c.commit_proposal(pending.clone()).is_err());
    let summary = c.run_until_quiescent(Scope::default()).await.unwrap();
    assert_eq!(summary.disposition, "no_commit");
    drop(c);
    drop(state);
    let routes = repo.0.join(".git/routes.json");
    std::fs::write(&routes, "{}").unwrap();
    let output = Command::new(binary())
        .args(["run", "--repo"])
        .arg(&repo.0)
        .arg("--models")
        .arg(routes)
        .args([
            "--worker-model",
            "worker",
            "--reviewer-model",
            "reviewer",
            "--planner-model",
            "planner",
            "--no-commit",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(
        serde_json::from_slice::<Value>(&output.stdout).unwrap()["disposition"],
        "no_commit"
    );
    assert!(fixture.calls.lock().unwrap().is_empty());
    assert_eq!(service.capture_pending().unwrap(), pending);
    assert!(!TaskStore::read_at(&repo.0, "HEAD").unwrap().tasks()["C"].runnable());

    let repo = Repo::new(
        "pause-inflight",
        &[("A", "Next", "fixture-pass"), ("B", "Next", "fixture-pass")],
    );
    let o = options();
    let fixture = Fixture::new(26, &repo, false, "wait_external", Some(o.control.clone()));
    let runtime = repo.runtime(&fixture);
    let service = TaskService::new(&repo.0).unwrap();
    let state = repo.state();
    let result = coordinator(&repo, &runtime, &service, &state, o)
        .run_until_quiescent(Scope::default())
        .await
        .unwrap();
    assert_eq!(result.disposition, "paused");
    assert!(result.completed_task_ids.is_empty());
    assert!(fixture.calls.lock().unwrap().iter().all(|r| r == "worker"));

    let repo = Repo::new("pause-planner", &[("C", "Needs decision", "fixture-pass")]);
    let o = options();
    let fixture = Fixture::new(30, &repo, false, "repair_current", Some(o.control.clone()));
    let runtime = repo.runtime(&fixture);
    let service = TaskService::new(&repo.0).unwrap();
    let state = repo.state();
    let before = service.capture_pending().unwrap();
    let result = coordinator(&repo, &runtime, &service, &state, o)
        .run_until_quiescent(Scope::default())
        .await
        .unwrap();
    assert_eq!(result.disposition, "paused");
    assert_eq!(service.capture_pending().unwrap(), before);
    assert!(!state.directory().join("planning-publication.json").exists());
}
