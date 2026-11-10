use std::io::Write;
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

struct TaskCliRepo(std::path::PathBuf);
impl TaskCliRepo {
    fn new() -> Self {
        use std::sync::atomic::{AtomicU64, Ordering};
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let root = std::env::temp_dir().join(format!(
            "autowork cli fixture {} {}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        std::fs::create_dir_all(root.join("tasks/items")).unwrap();
        std::fs::create_dir_all(root.join("tasks/goals")).unwrap();
        let repo = Self(root);
        repo.git(&["init", "-q", "-b", "main"]);
        repo.git(&["config", "user.name", "Fixture"]);
        repo.git(&["config", "user.email", "fixture@example.invalid"]);
        std::fs::write(
            repo.0.join("tasks/items/T-1.md"),
            include_str!("fixtures/task_store/tasks/items/T-1.md"),
        )
        .unwrap();
        std::fs::write(
            repo.0.join("tasks/goals/G-1.md"),
            include_str!("fixtures/task_store/tasks/goals/G-1.md"),
        )
        .unwrap();
        repo.git(&["add", "tasks"]);
        repo.git(&["commit", "-qm", "fixture"]);
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
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        String::from_utf8(out.stdout).unwrap().trim().into()
    }
    fn run(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_autowork-next"))
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .args(args)
            .output()
            .unwrap()
    }
    fn value(&self, args: &[&str]) -> Value {
        let result = self.run(args);
        assert!(
            result.status.success(),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        serde_json::from_slice(&result.stdout).unwrap()
    }
}
impl Drop for TaskCliRepo {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn status_reads_committed_tasks_without_creating_or_recovering_state() {
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let original = std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap();
    let value = repo.value(&["status", "--repo", path, "--json"]);
    assert_eq!(value["schema_version"], 1);
    assert_eq!(value["task_count"], 1);
    assert_eq!(value["journal"]["status"], "unavailable");
    assert!(!repo.0.join(".git/autowork-rust").exists());
    let store = autowork_next::state::StateStore::open(repo.0.join(".git")).unwrap();
    assert_eq!(
        repo.value(&["status", "--repo", path, "--json"])["journal"]["status"],
        "unavailable"
    );
    drop(store);
    let database = repo.0.join(".git/autowork-rust/journal.sqlite3");
    let bytes = std::fs::read(&database).unwrap();
    assert_eq!(
        repo.value(&["status", "--repo", path, "--json"])["journal"]["status"],
        "observed"
    );
    assert_eq!(std::fs::read(&database).unwrap(), bytes);
    assert!(
        !repo
            .0
            .join(".git/autowork-rust/journal.sqlite3-shm")
            .exists()
    );
    std::fs::write(&database, b"invalid database").unwrap();
    assert_eq!(
        repo.value(&["status", "--repo", path, "--json"])["journal"]["status"],
        "unavailable"
    );
    assert_eq!(std::fs::read(database).unwrap(), b"invalid database");
    assert_eq!(
        std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap(),
        original
    );
    assert_eq!(repo.git(&["status", "--porcelain"]), "");
}

#[test]
fn task_cli_prepares_edits_and_refuses_stale_or_protected_changes() {
    use autowork_next::task_store::TaskStore;
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let revision = snapshot.revision();
    let record = &snapshot.tasks()["T-1"].record_revision;
    let before = std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap();
    for key in ["live", "ownership", "Owner decision", "verified_depends_on"] {
        let out = repo.run(&[
            "tasks",
            "--repo",
            path,
            "--expected-revision",
            revision,
            "field",
            "T-1",
            "--record-revision",
            record,
            key,
            "\"authorized\"",
        ]);
        assert!(!out.status.success());
        assert_eq!(
            std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap(),
            before
        );
    }
    let out = repo.run(&[
        "tasks",
        "--repo",
        path,
        "--expected-revision",
        "stale",
        "field",
        "T-1",
        "--record-revision",
        record,
        "title",
        "\"Updated\"",
    ]);
    assert!(!out.status.success());
    let value = repo.value(&[
        "tasks",
        "--repo",
        path,
        "--expected-revision",
        revision,
        "field",
        "T-1",
        "--record-revision",
        record,
        "title",
        "\"Updated\"",
    ]);
    assert_eq!(value["status"], "pending");
    assert_eq!(value["selectable"], false);
    assert_eq!(value["base_revision"], revision);
    let pending_revision = value["record_revisions"]["tasks/items/T-1.md"]
        .as_str()
        .unwrap();
    let pending = std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap();
    assert!(String::from_utf8_lossy(&pending).contains("Free notes."));
    assert_eq!(
        TaskStore::read_at(&repo.0, "HEAD").unwrap().tasks()["T-1"].title,
        "Read tasks"
    );
    assert!(
        !repo
            .run(&[
                "tasks",
                "--repo",
                path,
                "--expected-revision",
                revision,
                "place",
                "T-1",
                "--record-revision",
                record,
                "Next"
            ])
            .status
            .success()
    );
    assert_eq!(
        std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap(),
        pending
    );
    let next = repo.value(&[
        "tasks",
        "--repo",
        path,
        "--expected-revision",
        revision,
        "place",
        "T-1",
        "--record-revision",
        pending_revision,
        "Next",
    ]);
    let chained = std::fs::read_to_string(repo.0.join("tasks/items/T-1.md")).unwrap();
    assert!(chained.contains("title = \"Updated\""));
    assert!(chained.contains("section = \"Next\""));
    assert!(chained.contains("Free notes."));
    assert_ne!(
        next["record_revisions"]["tasks/items/T-1.md"],
        pending_revision
    );
    assert_eq!(
        repo.value(&["tasks", "--repo", path, "preview"])["status"],
        "pending"
    );
}

#[test]
fn task_cli_add_and_place_preserve_unknown_notes_and_pending_boundaries() {
    use autowork_next::task_store::TaskStore;
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let revision = snapshot.revision();
    let bytes = include_str!("fixtures/task_store/tasks/items/T-1.md").replace("T-1", "T-2");
    let input = repo.0.join("proposal.md");
    std::fs::write(&input, bytes).unwrap();
    let value = repo.value(&[
        "tasks",
        "--repo",
        path,
        "--expected-revision",
        revision,
        "add",
        "T-2",
        "--record",
        input.to_str().unwrap(),
    ]);
    assert_eq!(value["selectable"], false);
    assert!(repo.0.join("tasks/items/T-2.md").exists());
    assert!(
        !TaskStore::read_at(&repo.0, "HEAD")
            .unwrap()
            .tasks()
            .contains_key("T-2")
    );
    let record = &snapshot.tasks()["T-1"].record_revision;
    repo.value(&[
        "tasks",
        "--repo",
        path,
        "--expected-revision",
        revision,
        "place",
        "T-1",
        "--record-revision",
        record,
        "Next",
    ]);
    let pending = std::fs::read_to_string(repo.0.join("tasks/items/T-1.md")).unwrap();
    assert!(pending.contains("Free notes."));
    assert!(pending.contains("section = \"Next\""));
    assert!(repo.0.join("tasks/items/T-2.md").exists());
    let observed = repo.value(&["status", "--repo", path, "--json"]);
    assert_eq!(observed["task_count"], 1);
    assert_eq!(
        std::fs::read_to_string(repo.0.join("tasks/items/T-1.md")).unwrap(),
        pending
    );
}

#[test]
fn status_reports_dependency_blocks_and_mutations_validate_types_and_grants() {
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let fixture = include_str!("fixtures/task_store/tasks/items/T-1.md");
    std::fs::write(
        repo.0.join("tasks/items/T-2.md"),
        fixture
            .replace("T-1", "T-2")
            .replace("depends_on = []", "depends_on = [\"T-1\"]"),
    )
    .unwrap();
    repo.git(&["add", "tasks"]);
    repo.git(&["commit", "-qm", "dependency"]);
    let value = repo.value(&["status", "--repo", path, "--json"]);
    let tasks = value["tasks"].as_array().unwrap();
    assert_eq!(
        tasks.iter().find(|t| t["id"] == "T-1").unwrap()["ready"],
        true
    );
    let blocked = tasks.iter().find(|t| t["id"] == "T-2").unwrap();
    assert_eq!(blocked["ready"], false);
    assert!(blocked["blocked"]["code"].is_string());
    let snap = autowork_next::task_store::TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let revision = snap.revision();
    let record = &snap.tasks()["T-1"].record_revision;
    let before = std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap();
    assert!(
        !repo
            .run(&[
                "tasks",
                "--repo",
                path,
                "--expected-revision",
                revision,
                "field",
                "T-1",
                "--record-revision",
                record,
                "title",
                "123"
            ])
            .status
            .success()
    );
    assert!(
        !repo
            .run(&[
                "tasks",
                "--repo",
                path,
                "--expected-revision",
                revision,
                "place",
                "T-1",
                "--record-revision",
                record,
                "Next",
                "--decision",
                "approve"
            ])
            .status
            .success()
    );
    assert_eq!(
        std::fs::read(repo.0.join("tasks/items/T-1.md")).unwrap(),
        before
    );
    let input = repo.0.join("protected.md");
    std::fs::write(
        &input,
        fixture
            .replace("T-1", "T-3")
            .replace("live = \"denied\"", "live = \"authorized\""),
    )
    .unwrap();
    assert!(
        !repo
            .run(&[
                "tasks",
                "--repo",
                path,
                "--expected-revision",
                revision,
                "add",
                "T-3",
                "--record",
                input.to_str().unwrap()
            ])
            .status
            .success()
    );
    assert!(!repo.0.join("tasks/items/T-3.md").exists());
}
