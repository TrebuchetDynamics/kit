use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};

use autowork_next::state::{DurableStatus, RecordKind, StateStore, Transition};
use autowork_next::task_store::TaskStore;
use rusqlite::Connection;
use std::process::{Command, Output, Stdio};

use autowork_next::runtime::{
    AgentRequest, AgentResult, MAX_EVENT_BYTES, Role, RunIdentity, RuntimeEvent, RuntimeEventKind,
    RuntimeStatus,
};
use serde_json::{Value, json};

fn cli(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_autowork-next"))
        .args(args)
        .env_clear()
        .env("PATH", "")
        .output()
        .unwrap()
}

fn owned_agent(input: &[u8]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_autowork-next"))
        .arg("internal-agent")
        .env_clear()
        .env("PATH", "")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    // Oversized requests may be rejected before all bytes reach the child.
    let _ = child.stdin.take().unwrap().write_all(input);
    child.wait_with_output().unwrap()
}

fn output_json(args: &[&str]) -> Value {
    let output = cli(args);
    assert!(output.status.success(), "{:?}", output);
    serde_json::from_slice(&output.stdout).unwrap()
}

const TASK: &str = include_str!("fixtures/task_store/tasks/items/T-1.md");
static NEXT_REPO: AtomicU64 = AtomicU64::new(0);
struct Repo(PathBuf);
impl Repo {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "rust-inspection-{}-{}",
            std::process::id(),
            NEXT_REPO.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&root).unwrap();
        let repo = Self(root);
        repo.git(&["init", "-q", "-b", "main"]);
        repo.git(&["config", "user.name", "Fixture"]);
        repo.git(&["config", "user.email", "fixture@example.invalid"]);
        fs::create_dir_all(repo.0.join("tasks/items")).unwrap();
        fs::create_dir_all(repo.0.join("tasks/goals")).unwrap();
        repo.write_task("T-1", TASK);
        fs::write(
            repo.0.join("tasks/goals/G-1.md"),
            include_str!("fixtures/task_store/tasks/goals/G-1.md"),
        )
        .unwrap();
        repo.commit();
        repo
    }
    fn git(&self, args: &[&str]) -> String {
        let out = Command::new("/usr/bin/git")
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .arg("-C")
            .arg(&self.0)
            .args(args)
            .output()
            .unwrap();
        assert!(out.status.success(), "{out:?}");
        String::from_utf8(out.stdout).unwrap().trim_end().into()
    }
    fn commit(&self) {
        self.git(&["add", "tasks"]);
        self.git(&["commit", "-qm", "fixture"]);
    }
    fn write_task(&self, id: &str, text: impl AsRef<[u8]>) {
        fs::write(self.0.join(format!("tasks/items/{id}.md")), text).unwrap();
    }
    fn cli(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_autowork-next"))
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .args(args)
            .arg("--repo")
            .arg(&self.0)
            .output()
            .unwrap()
    }
    fn json(&self, args: &[&str]) -> Value {
        let out = self.cli(args);
        assert!(out.status.success(), "{out:?}");
        serde_json::from_slice(&out.stdout).unwrap()
    }
    fn database(&self) -> PathBuf {
        self.0.join(".git/autowork-rust/journal.sqlite3")
    }
}
impl Drop for Repo {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn task_inspection_is_pinned_and_selection_only() {
    let repo = Repo::new();
    repo.write_task(
        "T-2",
        TASK.replace("T-1", "T-2")
            .replace("rank = 1", "rank = 2")
            .replace("ownership = \"worker\"", "ownership = \"owner\""),
    );
    repo.write_task(
        "T-3",
        format!("{}\n- Held by: Fixture\n", TASK.replace("T-1", "T-3")),
    );
    repo.commit();
    let pinned = repo.git(&["rev-parse", "HEAD"]);
    let snapshot = TaskStore::read_at(&repo.0, &pinned).unwrap();
    repo.write_task("T-1", TASK.replace("Read tasks", "New commit"));
    repo.commit();
    repo.write_task("T-1", TASK.replace("Read tasks", "Staged"));
    repo.git(&["add", "tasks"]);
    repo.write_task("T-1", "dirty invalid bytes");
    let before = (
        repo.git(&["status", "--porcelain"]),
        fs::read(repo.0.join(".git/index")).unwrap(),
        repo.git(&["show-ref"]),
    );
    let rows = repo.json(&["tasks", "list", "--rev", &pinned]);
    let rows = rows.as_array().unwrap();
    assert_eq!(rows.len(), 3);
    assert_eq!(rows[0]["title"], "Read tasks");
    assert_eq!(rows[0]["rank"], 1);
    assert_eq!(rows[0]["touches"], json!(["src/"]));
    assert_eq!(
        rows[0]["record_revision"],
        snapshot.tasks()["T-1"].record_revision
    );
    assert_eq!(rows[1]["position"], 2); // Owner authority is not selection.
    assert_eq!(rows[2]["blocked_by"], "HELD");
    for row in rows {
        assert_eq!(
            row["selection"],
            json!({"only":true,"admission_evaluated":false,"runtime_evaluated":false,
            "source":"committed","ref":pinned,"revision":pinned,"revision_ephemeral":false})
        );
    }
    let goals = repo.json(&["tasks", "goals", "--rev", &pinned]);
    assert_eq!(goals.as_array().unwrap().len(), 1);
    assert_eq!(goals[0]["id"], "G-1");
    assert_eq!(goals[0]["source"], "docs/design.md#task-store");
    assert_eq!(
        goals[0]["snapshot"],
        json!({"source":"committed", "ref":pinned,
        "revision":pinned, "revision_ephemeral":false})
    );
    assert!(goals[0]["focus"].is_boolean());
    assert_eq!(
        goals[0]["record_revision"],
        snapshot.goals()["G-1"].record_revision
    );
    let show = repo.json(&["tasks", "show", "T-1", "--rev", &pinned]);
    assert_eq!(show["body"], snapshot.tasks()["T-1"].body);
    assert_eq!(show["title"], "Read tasks");
    assert_eq!(repo.json(&["tasks", "show", "T-1"])["title"], "New commit");
    let why = repo.json(&["tasks", "why", "T-2", "--rev", &pinned]);
    assert_eq!(why["eligible"], true);
    assert_eq!(why["first"], false);
    assert_eq!(
        why["reasons"],
        json!([{"code":"POSITION","detail":"2"},{"code":"AFTER_RANK","detail":"T-1"}])
    );
    let unknown = repo.json(&["tasks", "why", "UNKNOWN", "--rev", &pinned]);
    assert_eq!(unknown["reasons"][0]["code"], "UNKNOWN_TASK");
    assert_eq!(unknown["selection"], rows[0]["selection"]);
    assert!(!repo.cli(&["tasks", "show", "UNKNOWN"]).status.success());
    for args in [
        vec!["tasks", "field", "T-1", "title", "no"],
        vec!["tasks", "list", "--worktree"],
    ] {
        assert!(!repo.cli(&args).status.success());
    }
    let capabilities = output_json(&["capabilities"]);
    assert_eq!(capabilities["contracts"]["task_inspection"], 1);
    assert_eq!(
        capabilities["commands"]["tasks"],
        json!(["list", "goals", "show", "why"])
    );
    assert_eq!(
        before,
        (
            repo.git(&["status", "--porcelain"]),
            fs::read(repo.0.join(".git/index")).unwrap(),
            repo.git(&["show-ref"])
        )
    );
    assert_eq!(
        fs::read_to_string(repo.0.join("tasks/items/T-1.md")).unwrap(),
        "dirty invalid bytes"
    );
    assert!(!repo.0.join(".git/autowork-rust").exists());
}

fn journal_run(store: &StateStore, generation: u64) -> RunIdentity {
    let run = RunIdentity {
        repo_id: store.repo_id().into(),
        task_id: "T-1".into(),
        attempt_id: format!("attempt-{generation}"),
        generation,
        role: Role::Worker,
        contract_hash: "contract".into(),
    };
    store
        .claim(generation - 1, run.clone(), "source-commit")
        .unwrap();
    run
}
fn journal_note(store: &StateStore, run: RunIdentity) -> i64 {
    store
        .transition(
            run.generation,
            Transition {
                key: format!("note-{}", run.generation),
                identity: run.clone(),
                status: DurableStatus::Checking,
                kind: RecordKind::Note,
                event: RuntimeEvent {
                    schema_version: 1,
                    repo_id: run.repo_id,
                    operation_id: "fixture".into(),
                    task_id: run.task_id,
                    attempt_id: run.attempt_id,
                    generation: run.generation,
                    contract_hash: run.contract_hash,
                    source_revision: "source-commit".into(),
                    role: run.role,
                    event: RuntimeEventKind::Progress,
                    status: RuntimeStatus::Running,
                    evidence_ref: Some("PRIVATE_SECRET_SESSION_MODEL_ENV_TOKEN".into()),
                    timestamp: "1".into(),
                },
            },
        )
        .unwrap()
        .0
}
fn journal_image(sql: &Connection) -> (String, i64, String, i64, String, i64) {
    sql.query_row(
        "SELECT repository,epoch,owner,(SELECT count(*) FROM events),
        coalesce((SELECT group_concat(identity||source||status||event_id,'|') FROM runs),''),
        (SELECT count(*) FROM effects) FROM metadata",
        [],
        |r| {
            Ok((
                r.get(0)?,
                r.get(1)?,
                r.get(2)?,
                r.get(3)?,
                r.get(4)?,
                r.get(5)?,
            ))
        },
    )
    .unwrap()
}

#[test]
fn status_reads_without_writer_claim() {
    let repo = Repo::new();
    assert_eq!(output_json(&["capabilities"])["contracts"]["status"], 1);
    assert_eq!(repo.json(&["status"])["journal_state"], "absent");
    assert!(!repo.0.join(".git/autowork-rust").exists());
    let (advance, commands) = std::sync::mpsc::channel();
    let (ready, commits) = std::sync::mpsc::channel();
    let common = repo.0.join(".git");
    let writer = std::thread::spawn(move || {
        let store = StateStore::open(common).unwrap();
        for generation in 1..=2 {
            let run = journal_run(&store, generation);
            let id = journal_note(&store, run);
            ready.send(id).unwrap();
            commands.recv().unwrap(); // Keep the writer lease until the reader finishes.
        }
    });
    for generation in 1..=2 {
        let high_water = commits.recv().unwrap();
        let sql = Connection::open(repo.database()).unwrap();
        let before = journal_image(&sql);
        sql.execute_batch(
            "BEGIN IMMEDIATE; INSERT INTO events(key,payload) VALUES ('uncommitted','private');",
        )
        .unwrap();
        let status = repo.json(&["status"]);
        assert_eq!(status["schema_version"], 1);
        assert_eq!(status["source"], "runtime-journal");
        assert_eq!(status["journal_schema"], 1);
        assert_eq!(status["journal_state"], "present");
        assert_eq!(status["event_high_water_mark"], high_water);
        assert_eq!(
            status["projections"],
            json!([{"task_id":"T-1", "attempt_id":format!("attempt-{generation}"),
            "generation":generation,"role":"worker","contract_hash":"contract","source_revision":"source-commit",
            "status":"checking","event_id":high_water}])
        );
        assert_eq!(status["repository"].as_object().unwrap().len(), 2);
        assert!(!status.to_string().contains("PRIVATE_SECRET"));
        sql.execute_batch("ROLLBACK").unwrap();
        assert_eq!(before, journal_image(&sql));
        assert!(StateStore::open(repo.0.join(".git")).is_err());
        advance.send(()).unwrap();
    }
    writer.join().unwrap();
    assert_eq!(repo.git(&["status", "--porcelain"]), "");
    // Git's output newline is not part of the path; trailing path whitespace is.
    repo.git(&["init", "--bare", "-q", "private"]);
    repo.git(&["init", "--bare", "-q", "private "]);
    let ordinary = StateStore::open(repo.0.join("private")).unwrap();
    journal_run(&ordinary, 1);
    let spaced = repo.0.join("private ");
    let absent = output_json(&["status", "--repo", spaced.to_str().unwrap()]);
    assert_eq!(absent["journal_state"], "absent");
    assert!(!spaced.join("autowork-rust").exists());
}

#[test]
fn inspection_refuses_unsafe_sources() {
    fn refused(repo: &Repo, code: &str) {
        let out = repo.cli(&["status"]);
        assert!(!out.status.success(), "{out:?}");
        assert!(out.stdout.is_empty());
        let diagnostic: Value = serde_json::from_slice(&out.stderr).unwrap();
        assert_eq!(diagnostic["status"], "unavailable");
        assert_eq!(diagnostic["code"], code);
        assert!(out.stderr.len() < 256);
        assert!(!String::from_utf8_lossy(&out.stderr).contains("PRIVATE_SECRET"));
    }
    let repo = Repo::new();
    let directory = repo.0.join(".git/autowork-rust");
    fs::create_dir(&directory).unwrap();
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o755)).unwrap();
    refused(&repo, "unsafe_source");
    fs::set_permissions(&directory, fs::Permissions::from_mode(0o700)).unwrap();
    let secret = repo.0.join("PRIVATE_SECRET");
    fs::write(&secret, "PRIVATE_SECRET").unwrap();
    std::os::unix::fs::symlink(&secret, repo.database()).unwrap();
    refused(&repo, "unsafe_source");
    fs::remove_file(repo.database()).unwrap();
    let store = StateStore::open(repo.0.join(".git")).unwrap();
    journal_note(&store, journal_run(&store, 1));
    let sql = Connection::open(repo.database()).unwrap();
    sql.execute(
        "UPDATE metadata SET owner=json_set(owner,'$.session','PRIVATE_SECRET')",
        [],
    )
    .unwrap();
    assert!(
        !repo
            .json(&["status"])
            .to_string()
            .contains("PRIVATE_SECRET")
    );
    drop(sql);
    drop(store);
    let original = fs::read(repo.database()).unwrap();
    fs::hard_link(repo.database(), directory.join("journal.sqlite3-wal")).unwrap();
    refused(&repo, "unsafe_source");
    fs::remove_file(directory.join("journal.sqlite3-wal")).unwrap();
    fs::set_permissions(repo.database(), fs::Permissions::from_mode(0o644)).unwrap();
    refused(&repo, "unsafe_source");
    fs::set_permissions(repo.database(), fs::Permissions::from_mode(0o600)).unwrap();
    for (sql_text, code) in [
        ("PRAGMA user_version=2", "unsupported_schema"),
        (
            "UPDATE metadata SET repository=json_set(repository,'$.inode',0)",
            "foreign_journal",
        ),
        (
            "UPDATE runs SET identity='PRIVATE_SECRET'",
            "corrupt_journal",
        ),
    ] {
        let sql = Connection::open(repo.database()).unwrap();
        sql.execute_batch(sql_text).unwrap();
        drop(sql);
        let retained = fs::read(repo.database()).unwrap();
        refused(&repo, code);
        assert_eq!(retained, fs::read(repo.database()).unwrap());
        fs::write(repo.database(), &original).unwrap();
    }
    // SQLite's exclusive WAL lock deterministically prevents readers, without sleeps.
    let sql = Connection::open(repo.database()).unwrap();
    sql.execute_batch("PRAGMA locking_mode=EXCLUSIVE; BEGIN EXCLUSIVE;")
        .unwrap();
    refused(&repo, "busy");
    sql.execute_batch("ROLLBACK").unwrap();
    drop(sql);
    assert_eq!(repo.json(&["status"])["journal_state"], "present");
    fs::write(repo.database(), b"PRIVATE_SECRET corrupt SQLite bytes").unwrap();
    refused(&repo, "corrupt_journal");
    assert_eq!(fs::read(&secret).unwrap(), b"PRIVATE_SECRET");
}

#[test]
fn crate_has_one_product_owner() {
    let manifest_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"));
    let root = manifest_dir
        .ancestors()
        .find(|path| path.join(".git").exists())
        .unwrap();
    let owner = root.join("pi-autowork/rust/autowork");
    assert_eq!(manifest_dir, owner);
    for retired in ["Cargo.toml", "src", "tests"] {
        assert!(!root.join("rust/autowork").join(retired).exists());
    }

    let output = Command::new(env!("CARGO"))
        .args([
            "metadata",
            "--locked",
            "--offline",
            "--no-deps",
            "--format-version",
            "1",
            "--manifest-path",
        ])
        .arg(owner.join("Cargo.toml"))
        .current_dir(std::env::temp_dir())
        .output()
        .unwrap();
    assert!(output.status.success(), "{:?}", output);
    let metadata: Value = serde_json::from_slice(&output.stdout).unwrap();
    let packages = metadata["packages"].as_array().unwrap();
    assert_eq!(packages.len(), 1);
    assert_eq!(metadata["workspace_members"].as_array().unwrap().len(), 1);
    assert_eq!(
        packages[0]["manifest_path"],
        owner.join("Cargo.toml").to_str().unwrap()
    );
    let targets: std::collections::BTreeSet<_> = packages[0]["targets"]
        .as_array()
        .unwrap()
        .iter()
        .map(|target| {
            assert!(std::path::Path::new(target["src_path"].as_str().unwrap()).starts_with(&owner));
            (
                target["name"].as_str().unwrap(),
                target["kind"][0].as_str().unwrap(),
            )
        })
        .collect();
    assert_eq!(
        targets,
        std::collections::BTreeSet::from([
            ("autowork_next", "lib"),
            ("autowork-next", "bin"),
            ("autonomous_cycle", "test"),
            ("cli", "test"),
            ("planning_reentry", "test"),
            ("runtime_native", "test"),
            ("state_recovery", "test"),
            ("task_store", "test"),
        ])
    );
    for module in ["execution", "planning", "runtime", "state", "task_store"] {
        assert!(owner.join(format!("src/{module}.rs")).is_file());
        assert!(include_str!("../src/lib.rs").contains(&format!("pub mod {module};")));
    }
}

#[test]
fn bootstrap_without_pi() {
    let version = output_json(&["version"]);
    assert_eq!(version["application"], "autowork-next");
    assert_eq!(version["engine"], "native-Octet");
    assert!(cli(&["--version"]).status.success());
    let capabilities = output_json(&["capabilities"]);
    assert_eq!(capabilities["commands"]["version"], "available");
    assert_eq!(capabilities["commands"]["capabilities"], "available");
    assert_eq!(capabilities["model_execution"], "explicit-owned-route");
    assert_eq!(capabilities["installed_runner"], "unchanged");
    assert_eq!(capabilities["commands"]["run"], "explicit-local-cycle");
    assert_eq!(capabilities["commands"]["internal-agent"], "owned-only");
    for command in ["run", "internal-agent"] {
        assert!(!cli(&[command]).status.success());
    }
    assert_eq!(capabilities["unknown_commands"], "unsupported");
    assert!(!cli(&["not-a-command"]).status.success());
}

#[test]
fn reports_runtime_contract() {
    const REVISION: &str = "4d7a3e3ff83b300a57b20f9ac70cfa20cb3242ee";
    let capabilities = output_json(&["capabilities"]);
    assert_eq!(capabilities["engine_revision"], REVISION);
    assert_eq!(output_json(&["version"])["engine_revision"], REVISION);
    assert!(include_str!("../Cargo.lock").contains(&format!(
        "git+https://github.com/skaft-software/octet?rev={REVISION}#{REVISION}"
    )));
    let contracts = &capabilities["contracts"];
    for name in ["agent_request", "agent_result", "runtime_event"] {
        assert_eq!(contracts[name], 1);
    }
    assert_eq!(contracts["roles"], json!(["worker", "reviewer", "planner"]));
    for role in ["worker", "reviewer", "planner"] {
        let workspace = json!({"canonical_path": "/fixture", "device": 1, "inode": 2});
        let identity = json!({
            "repo_id": "fixture", "task_id": "task", "attempt_id": "attempt",
            "generation": 1, "role": role, "contract_hash": "contract"
        });
        let mut request = identity.clone();
        request.as_object_mut().unwrap().extend(json!({
            "schema_version": 1, "workspace": "/fixture", "model_ref": "not-resolved",
            "source_revision": "fixture-revision", "prompt": "offline only",
            "admission": {
                "repo_id": "fixture", "repository": workspace, "workspace": workspace,
                "task_id": "task", "attempt_id": "attempt", "generation": 1,
                "contract_hash": "contract", "role": role, "allowed_write_paths": [],
                "denied_paths": ["tasks/", ".git", "BLOCKERS.md", "TODO.archive.md", "CHANGELOG.md"],
                "admitted_check_operation_ids": []
            }, "check_operations": []
        }).as_object().unwrap().clone());
        let mut typed: AgentRequest = serde_json::from_value(request).unwrap();
        assert_eq!(serde_json::to_value(&typed).unwrap()["role"], role);
        let result = AgentResult {
            schema_version: 1,
            identity: serde_json::from_value::<RunIdentity>(identity).unwrap(),
            status: RuntimeStatus::Unavailable,
            evidence_ref: None,
        };
        let result_json = serde_json::to_value(&result).unwrap();
        assert_eq!(result_json["identity"]["role"], role);
        assert_eq!(result_json["status"], "unavailable");
        let output = owned_agent(&serde_json::to_vec(&typed).unwrap());
        assert!(!output.status.success());
        assert!(output.stdout.is_empty());
        assert!(
            String::from_utf8(output.stderr)
                .unwrap()
                .contains("runtime::serve_owned_agent")
        );
        typed.schema_version = 2;
        let output = owned_agent(&serde_json::to_vec(&typed).unwrap());
        assert!(!output.status.success());
        assert!(
            String::from_utf8(output.stderr)
                .unwrap()
                .contains("unsupported agent request schema")
        );
    }
    let output = owned_agent(&vec![b' '; autowork_next::runtime::MAX_REQUEST_BYTES + 1]);
    assert!(!output.status.success());
    assert!(
        String::from_utf8(output.stderr)
            .unwrap()
            .contains("agent request exceeds limit")
    );
}

#[test]
fn bounds_runtime_events() {
    let mut event = RuntimeEvent {
        schema_version: 1,
        repo_id: "fixture".into(),
        operation_id: "operation".into(),
        task_id: "task".into(),
        attempt_id: "attempt".into(),
        generation: 1,
        contract_hash: "contract".into(),
        source_revision: "revision".into(),
        role: Role::Worker,
        event: RuntimeEventKind::Outcome,
        status: RuntimeStatus::Unavailable,
        evidence_ref: None,
        timestamp: "2026-11-07T00:00:00Z".into(),
    };
    let line = event.to_json_line().unwrap();
    assert_eq!(line.last(), Some(&b'\n'));
    assert_eq!(
        serde_json::from_slice::<Value>(&line).unwrap()["event"],
        "outcome"
    );
    // Exercise the exact byte boundary, including JSON escaping and newline.
    event.repo_id = "f".repeat("fixture".len() + MAX_EVENT_BYTES - line.len());
    assert_eq!(event.to_json_line().unwrap().len(), MAX_EVENT_BYTES);
    event.repo_id.push('"');
    assert!(event.to_json_line().is_err());
    event.repo_id.clear();
    event.schema_version = 2;
    assert!(event.to_json_line().is_err());
}
