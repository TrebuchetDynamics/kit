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

/// The typed inspection surface; `TaskCliRepo` below exercises the default public-v1.
const INSPECTION: [&str; 2] = ["--format", "inspection-v1"];

fn cli(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_autowork-next"))
        .arg("--offline")
        .args(INSPECTION)
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
        fs::create_dir(root.join("scratch")).unwrap();
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
            .env("TMPDIR", self.0.join("scratch"))
            .env("PATH", "/usr/bin:/bin")
            .arg("--offline")
            .args(INSPECTION)
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
        json!(["list", "goals", "show", "why", "commit"])
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

#[test]
fn pending_publication_preview_is_exact() {
    let repo = Repo::new();
    repo.write_task("T-2", TASK.replace("T-1", "T-2"));
    fs::write(
        repo.0.join("tasks/goals/G-2.md"),
        include_str!("fixtures/task_store/tasks/goals/G-1.md")
            .replace("G-1", "G-2")
            .replace("focus = true", "focus = false"),
    )
    .unwrap();
    repo.commit();
    fs::remove_file(repo.0.join("tasks/items/T-2.md")).unwrap();
    fs::remove_file(repo.0.join("tasks/goals/G-2.md")).unwrap();
    repo.write_task("T-3", format!("{}\0", TASK.replace("T-1", "T-3")));
    repo.write_task("T-1", TASK.replace("Read tasks", "Reviewed tasks"));
    fs::write(
        repo.0.join("tasks/goals/G-3.md"),
        include_str!("fixtures/task_store/tasks/goals/G-1.md")
            .replace("G-1", "G-3")
            .replace("focus = true", "focus = false"),
    )
    .unwrap();
    fs::write(repo.0.join("staged"), "staged sentinel").unwrap();
    repo.git(&["add", "staged"]);
    fs::write(repo.0.join("staged"), "dirty sentinel").unwrap();
    let script = repo.0.join(".git/hooks/post-index-change");
    fs::write(
        &script,
        format!(
            "#!/bin/sh\nprintf unexpected >> '{}'\nexit 1\n",
            repo.0.join("unexpected-hook").display()
        ),
    )
    .unwrap();
    fs::set_permissions(&script, fs::Permissions::from_mode(0o755)).unwrap();
    repo.git(&["config", "diff.external", script.to_str().unwrap()]);
    repo.git(&["config", "diff.preview.textconv", script.to_str().unwrap()]);
    fs::write(repo.0.join(".git/info/attributes"), "*.md diff=preview\n").unwrap();
    let order = repo.0.join(".git/diff-order");
    fs::write(&order, "tasks/items/*\ntasks/goals/*\n").unwrap();
    repo.git(&["config", "diff.orderFile", order.to_str().unwrap()]);
    let records = || {
        ["tasks/items", "tasks/goals"]
            .into_iter()
            .flat_map(|dir| fs::read_dir(repo.0.join(dir)).unwrap())
            .map(|entry| {
                let path = entry.unwrap().path();
                let bytes = fs::read(&path).unwrap();
                (path, bytes)
            })
            .collect::<std::collections::BTreeMap<_, _>>()
    };
    let original_records = records();
    let store = StateStore::open(repo.0.join(".git")).unwrap();
    let sql = Connection::open(repo.database()).unwrap();
    let before = (
        fs::read(repo.0.join(".git/index")).unwrap(),
        repo.git(&["show-ref"]),
        repo.git(&[
            "cat-file",
            "--batch-all-objects",
            "--batch-check=%(objectname)",
        ]),
        journal_image(&sql),
    );
    assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
    drop(store);
    let preview = repo.json(&["tasks", "commit", "--dry-run"]);
    assert_eq!(preview["state"], "pending_commit");
    assert_eq!(preview["base_head"], repo.git(&["rev-parse", "HEAD"]));
    assert_eq!(preview["branch"], "refs/heads/main");
    assert_eq!(
        preview["files"],
        json!([
            "tasks/goals/G-2.md",
            "tasks/goals/G-3.md",
            "tasks/items/T-1.md",
            "tasks/items/T-2.md",
            "tasks/items/T-3.md"
        ])
    );
    assert!(
        preview["diff"]
            .as_str()
            .unwrap()
            .contains("+title = \"Reviewed tasks\"")
    );
    assert!(!preview["diff"].as_str().unwrap().contains("sentinel"));
    assert!(
        preview["diff"]
            .as_str()
            .unwrap()
            .contains("GIT binary patch")
    );
    assert_eq!(preview, repo.json(&["tasks", "commit", "--dry-run"]));
    assert_eq!(
        before,
        (
            fs::read(repo.0.join(".git/index")).unwrap(),
            repo.git(&["show-ref"]),
            repo.git(&[
                "cat-file",
                "--batch-all-objects",
                "--batch-check=%(objectname)"
            ]),
            journal_image(&sql)
        )
    );
    assert_eq!(original_records, records());
    assert!(
        fs::read_dir(repo.0.join("scratch"))
            .unwrap()
            .next()
            .is_none()
    );
    assert!(!repo.0.join("unexpected-hook").exists());
    let captured = autowork_next::task_store::TaskService::new(&repo.0)
        .unwrap()
        .capture_pending()
        .unwrap();
    assert_eq!(preview["tree"], captured.tree);
    assert_eq!(preview["token"], captured.token);
    assert_eq!(
        preview["diff"],
        format!(
            "{}\n",
            repo.git(&[
                "diff",
                "--binary",
                "--full-index",
                "--no-ext-diff",
                "--no-textconv",
                "--no-renames",
                "--no-color",
                "--src-prefix=a/",
                "--dst-prefix=b/",
                &captured.base_head,
                &captured.tree,
                "--"
            ])
        )
    );
    assert!(!repo.0.join("unexpected-hook").exists());
    assert_eq!(
        fs::read_to_string(repo.0.join("staged")).unwrap(),
        "dirty sentinel"
    );
    assert!(
        !repo
            .cli(&["tasks", "commit", "--dry-run", "--rev", "HEAD~1"])
            .status
            .success()
    );
    for journal in [
        "autowork-tasks.transaction",
        "autowork-rust-tasks.transaction",
    ] {
        let path = repo.0.join(".git").join(journal);
        fs::write(&path, "retained").unwrap();
        assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
        assert_eq!(fs::read_to_string(&path).unwrap(), "retained");
        fs::remove_file(path).unwrap();
    }
    repo.write_task("T-1", "invalid");
    assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
    fs::remove_file(repo.0.join("tasks/items/T-1.md")).unwrap();
    std::os::unix::fs::symlink(
        repo.0.join("tasks/items/T-3.md"),
        repo.0.join("tasks/items/T-1.md"),
    )
    .unwrap();
    assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
    fs::remove_file(repo.0.join("tasks/items/T-1.md")).unwrap();
    repo.write_task(
        "T-1",
        format!("{TASK}\n{}", "large preview\n".repeat(24000)),
    );
    assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
    repo.write_task("T-1", TASK);
    repo.git(&["checkout", "--detach", "-q"]);
    assert!(!repo.cli(&["tasks", "commit", "--dry-run"]).status.success());
    assert!(
        fs::read_dir(repo.0.join("scratch"))
            .unwrap()
            .next()
            .is_none()
    );
    let clean = Repo::new();
    let preview = clean.json(&["tasks", "commit", "--dry-run"]);
    assert_eq!(preview["state"], "clean");
    assert_eq!(preview["files"], json!([]));
    assert_eq!(preview["diff"], "");
    assert!(preview["token"].is_null());
    assert!(!clean.database().exists());
}

fn preview_token(repo: &Repo) -> String {
    repo.json(&["tasks", "commit", "--dry-run"])["token"]
        .as_str()
        .unwrap()
        .into()
}
fn publish(repo: &Repo, token: &str) -> Output {
    repo.cli(&["tasks", "commit", "--expect-token", token])
}
fn hook(repo: &Repo, body: &str) {
    let path = repo.0.join(".git/hooks/pre-commit");
    fs::write(
        &path,
        format!(
            "#!/bin/sh\nprintf 'hook\\n' >> '{}'\n{body}",
            repo.0.join("hook-calls").display()
        ),
    )
    .unwrap();
    fs::set_permissions(path, fs::Permissions::from_mode(0o755)).unwrap();
}

#[test]
fn pending_publication_commits_only_reviewed_records() {
    let repo = Repo::new();
    let clean = repo.json(&["tasks", "commit"]);
    assert_eq!(clean["state"], "clean");
    assert!(clean["commit"].is_null());
    assert_eq!(
        output_json(&["capabilities"])["contracts"]["task_publication"],
        1
    );
    repo.write_task("T-2", TASK.replace("T-1", "T-2"));
    repo.commit();
    fs::remove_file(repo.0.join("tasks/items/T-2.md")).unwrap();
    repo.write_task("T-3", TASK.replace("T-1", "T-3"));
    let reviewed = TASK.replace("Read tasks", "Reviewed tasks");
    repo.write_task("T-1", &reviewed);
    fs::write(
        repo.0.join("tasks/goals/G-1.md"),
        include_str!("fixtures/task_store/tasks/goals/G-1.md")
            .replace("Goal notes.", "Reviewed goal."),
    )
    .unwrap();
    fs::write(repo.0.join("sentinel"), "staged").unwrap();
    repo.git(&["add", "sentinel"]);
    fs::write(repo.0.join("sentinel"), "dirty").unwrap();
    let staged = repo.git(&["ls-files", "--stage", "--", "sentinel"]);
    let base = repo.git(&["rev-parse", "HEAD"]);
    let token = preview_token(&repo);
    assert!(!repo.cli(&["tasks", "commit"]).status.success());
    for bad in ["../../escape", &"0".repeat(64), ""] {
        assert!(!publish(&repo, bad).status.success());
    }
    repo.write_task("T-1", TASK.replace("Read tasks", "Drift"));
    assert!(!publish(&repo, &token).status.success());
    repo.write_task("T-1", &reviewed);
    repo.git(&["symbolic-ref", "HEAD", "refs/heads/other"]);
    repo.git(&["update-ref", "refs/heads/other", &base]);
    assert!(!publish(&repo, &token).status.success());
    repo.git(&["symbolic-ref", "HEAD", "refs/heads/main"]);
    let oid = repo.git(&["rev-parse", "HEAD:tasks/items/T-1.md"]);
    let mut index = Command::new("/usr/bin/git")
        .arg("-C")
        .arg(&repo.0)
        .args(["update-index", "--index-info"])
        .stdin(Stdio::piped())
        .spawn()
        .unwrap();
    index.stdin.take().unwrap().write_all(format!("0 {}\ttasks/items/T-1.md\n100644 {oid} 1\ttasks/items/T-1.md\n100644 {oid} 2\ttasks/items/T-1.md\n100644 {oid} 3\ttasks/items/T-1.md\n", "0".repeat(oid.len())).as_bytes()).unwrap();
    assert!(index.wait().unwrap().success());
    let conflicted = fs::read(repo.0.join(".git/index")).unwrap();
    assert!(!publish(&repo, &token).status.success());
    assert_eq!(fs::read(repo.0.join(".git/index")).unwrap(), conflicted);
    repo.git(&["reset", "-q", "HEAD", "--", "tasks/items/T-1.md"]);
    repo.write_task("T-1", TASK.replace("Read tasks", "Staged conflict"));
    repo.git(&["add", "tasks/items/T-1.md"]);
    repo.write_task("T-1", &reviewed);
    assert!(!publish(&repo, &token).status.success());
    repo.git(&["reset", "-q", "HEAD", "--", "tasks/items/T-1.md"]);
    // The same retained intent can now resume; no hook had started on the index conflict.
    for marker in ["pause", "stop"] {
        let path = repo.0.join(".git/autowork-rust").join(marker);
        fs::write(&path, "gate").unwrap();
        assert!(!publish(&repo, &token).status.success());
        fs::remove_file(path).unwrap();
    }
    let writer = StateStore::open(repo.0.join(".git")).unwrap();
    assert!(!publish(&repo, &token).status.success());
    drop(writer);
    let state = StateStore::open(repo.0.join(".git")).unwrap();
    let identity = journal_run(&state, 1);
    journal_note(&state, identity.clone());
    let mut intent = state.events().unwrap().last().unwrap().1.clone();
    intent.key = "unrelated-child-intent".into();
    intent.kind = RecordKind::Intent(autowork_next::state::EffectKind::Child);
    intent.event.operation_id = "unrelated-child".into();
    intent.event.event = RuntimeEventKind::Accepted;
    intent.event.status = RuntimeStatus::Running;
    state.transition(1, intent).unwrap();
    drop(state);
    assert!(!publish(&repo, &token).status.success());
    let state = StateStore::open(repo.0.join(".git")).unwrap();
    state
        .reconcile(autowork_next::state::Observations {
            effects: vec![autowork_next::state::EffectObservation {
                identity,
                operation_id: "unrelated-child".into(),
                source_revision: "source-commit".into(),
                outcome: autowork_next::state::EffectOutcome::Absent,
                evidence_ref: "fixture-no-child".into(),
            }],
        })
        .unwrap();
    drop(state);
    assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
    hook(&repo, "exit 0\n");
    let preview = repo.json(&["tasks", "commit", "--dry-run"]);
    let result = repo.json(&["tasks", "commit", "--expect-token", &token]);
    assert_eq!(result["state"], "committed");
    assert_eq!(result["token"], token);
    assert_eq!(result["publication"], "local_only");
    assert_eq!(result["execution_evaluated"], false);
    assert_eq!(result["closure_evaluated"], false);
    assert_eq!(result["commit"], repo.git(&["rev-parse", "HEAD"]));
    assert_eq!(repo.git(&["rev-parse", "HEAD^{tree}"]), preview["tree"]);
    assert_eq!(
        repo.git(&["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"]),
        "tasks/goals/G-1.md\ntasks/items/T-1.md\ntasks/items/T-2.md\ntasks/items/T-3.md"
    );
    assert_eq!(repo.git(&["ls-files", "--stage", "--", "sentinel"]), staged);
    assert_eq!(
        fs::read_to_string(repo.0.join("sentinel")).unwrap(),
        "dirty"
    );
    assert_eq!(
        fs::read_to_string(repo.0.join("hook-calls")).unwrap(),
        "hook\n"
    );
    assert_eq!(repo.json(&["tasks", "commit"])["state"], "clean");
    assert!(!repo.0.join("tasks/evidence").exists());
    let store = StateStore::open(repo.0.join(".git")).unwrap();
    assert!(
        store
            .events()
            .unwrap()
            .iter()
            .filter(|(_, t)| t.event.operation_id != "unrelated-child")
            .all(|(_, t)| !matches!(
                t.kind,
                RecordKind::Intent(autowork_next::state::EffectKind::Child)
            ))
    );
    drop(store);
    // Advancing the source with unchanged records still invalidates the token.
    let drift = Repo::new();
    drift.write_task("T-1", &reviewed);
    let token = preview_token(&drift);
    drift.git(&["commit", "--allow-empty", "-qm", "source drift"]);
    assert!(!publish(&drift, &token).status.success());
}

fn interrupt_publication(repo: &Repo, fault: autowork_next::execution::FaultPoint) {
    use autowork_next::{execution::*, runtime::Runtime, task_store::TaskService};
    let token = preview_token(repo);
    let state = StateStore::open(repo.0.join(".git")).unwrap();
    let binary = PathBuf::from(env!("CARGO_BIN_EXE_autowork-next"));
    let runtime = Runtime::new(
        binary.clone(),
        state.directory().into(),
        Default::default(),
        std::time::Duration::from_secs(10),
    )
    .unwrap();
    let service = TaskService::new(&repo.0).unwrap();
    let mut coordinator = Coordinator::new(
        &repo.0,
        &binary,
        &runtime,
        &service,
        &state,
        RunOptions {
            worker_model: String::new(),
            reviewer_model: String::new(),
            planner_model: String::new(),
            max_tasks: None,
            allow_commit: true,
            control: Control::default(),
            prerequisites: vec![],
        },
    )
    .unwrap();
    coordinator.inject_fault(fault);
    assert!(coordinator.publish_pending(Some(&token)).is_err());
}

#[test]
fn pending_publication_recovers_without_dispatch() {
    use autowork_next::execution::FaultPoint;
    for (fault, advance_ref) in [
        (FaultPoint::BeforeProposalCommit, false),
        (FaultPoint::AfterProposalCommit, false),
        (FaultPoint::AfterProposalCommit, true),
    ] {
        let repo = Repo::new();
        repo.write_task("T-1", TASK.replace("Read tasks", "Reviewed tasks"));
        let token = preview_token(&repo);
        let base = repo.git(&["rev-parse", "HEAD"]);
        hook(&repo, "exit 0\n");
        interrupt_publication(&repo, fault);
        let path = repo.0.join(format!(
            ".git/autowork-rust/cycle-effects/proposal-{token}.json"
        ));
        let effect: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        let calls = fs::read_to_string(repo.0.join("hook-calls")).unwrap_or_default();
        let mut unrelated = effect.clone();
        unrelated["operation"] = json!("unrelated");
        let other = path.with_file_name("unrelated.json");
        fs::write(&other, serde_json::to_vec(&unrelated).unwrap()).unwrap();
        assert!(!publish(&repo, &token).status.success());
        fs::remove_file(other).unwrap();
        repo.write_task("T-1", TASK.replace("Read tasks", "External conflict"));
        let retained = fs::read(&path).unwrap();
        assert!(!publish(&repo, &token).status.success());
        assert_eq!(fs::read(&path).unwrap(), retained);
        assert_eq!(
            fs::read_to_string(repo.0.join("hook-calls")).unwrap_or_default(),
            calls
        );
        repo.write_task("T-1", TASK.replace("Read tasks", "Reviewed tasks"));
        if advance_ref {
            repo.git(&[
                "update-ref",
                "refs/heads/main",
                effect["target"].as_str().unwrap(),
                &base,
            ]);
        }
        let result = repo.json(&["tasks", "commit", "--expect-token", &token]);
        assert_eq!(result["state"], "committed");
        fs::copy(
            repo.0.join(".git/hooks/pre-commit"),
            repo.0.join(".git/hooks/post-index-change"),
        )
        .unwrap();
        assert_eq!(
            result,
            repo.json(&["tasks", "commit", "--expect-token", &token])
        );
        assert_eq!(repo.git(&["rev-list", "--count", "HEAD"]), "2");
        assert_eq!(
            fs::read_to_string(repo.0.join("hook-calls")).unwrap(),
            "hook\n"
        );
        let store = StateStore::open(repo.0.join(".git")).unwrap();
        assert!(
            store
                .events()
                .unwrap()
                .iter()
                .all(|(_, t)| t.identity.role == Role::Planner
                    && !matches!(
                        t.kind,
                        RecordKind::Intent(autowork_next::state::EffectKind::Child)
                    ))
        );
    }
    for (body, uncertain) in [
        ("exit 1\n", false),
        ("kill -KILL \"$PPID\"\n", false),
        (
            "printf 'changed\\n' > tasks/items/T-1.md\n/usr/bin/git add tasks/items/T-1.md\n",
            false,
        ),
        ("exit 1\n", true),
    ] {
        let repo = Repo::new();
        repo.write_task("T-1", TASK.replace("Read tasks", "Reviewed tasks"));
        let token = preview_token(&repo);
        let base = repo.git(&["rev-parse", "HEAD"]);
        hook(&repo, body);
        assert!(!publish(&repo, &token).status.success());
        let path = repo.0.join(format!(
            ".git/autowork-rust/cycle-effects/proposal-{token}.json"
        ));
        if uncertain {
            // Simulate interruption before the owned invocation outcome was durable.
            let mut effect: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
            effect["commit"]["finished"] = json!(false);
            effect["commit"]["owner"] = Value::Null;
            fs::write(&path, serde_json::to_vec(&effect).unwrap()).unwrap();
        }
        let retained = fs::read(&path).unwrap();
        assert!(!publish(&repo, &token).status.success());
        assert_eq!(fs::read(&path).unwrap(), retained);
        assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
        assert_eq!(
            fs::read_to_string(repo.0.join("hook-calls")).unwrap(),
            "hook\n"
        );
    }
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
            .arg("--offline")
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .env("TMPDIR", std::env::temp_dir())
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
        "observed"
    );
    drop(store);
    let database = repo.0.join(".git/autowork-rust/journal.sqlite3");
    let bytes = std::fs::read(&database).unwrap();
    assert_eq!(
        repo.value(&["status", "--repo", path, "--json"])["journal"]["status"],
        "observed"
    );
    assert_eq!(std::fs::read(&database).unwrap(), bytes);
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

#[test]
fn task_queries_pin_commits_and_preserve_pending_and_runtime_bytes() {
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let record = repo.0.join("tasks/items/T-1.md");
    let original = std::fs::read_to_string(&record).unwrap();
    let first = repo.git(&["rev-parse", "HEAD"]);
    std::fs::write(&record, original.replace("Read tasks", "Committed update")).unwrap();
    repo.git(&["add", "tasks"]);
    repo.git(&["commit", "-qm", "second snapshot"]);
    let second = repo.git(&["rev-parse", "HEAD"]);
    let committed = std::fs::read_to_string(&record).unwrap();
    std::fs::write(
        &record,
        committed.replace("Committed update", "Pending update"),
    )
    .unwrap();
    let pending = std::fs::read(&record).unwrap();
    let before = repo.git(&["status", "--porcelain"]);
    for _ in 0..2 {
        let list = repo.value(&["tasks", "--repo", path, "list"]);
        assert_eq!(list["schema_version"], 1);
        assert_eq!(list["revision"], second);
        assert_eq!(list["tasks"][0]["title"], "Committed update");
        assert_eq!(list["tasks"][0]["content"], committed);
        let historical = repo.value(&["tasks", "--repo", path, "show", "T-1", "--rev", &first]);
        assert_eq!(historical["revision"], first);
        assert_eq!(historical["task"]["content"], original);
        let old_list = repo.value(&["tasks", "--repo", path, "list", "--rev", &first]);
        assert_eq!(old_list["tasks"][0]["title"], "Read tasks");
        assert_eq!(
            repo.value(&["tasks", "--repo", path, "show", "T-1"])["task"]["content"],
            committed
        );
    }
    for args in [
        vec!["tasks", "--repo", path, "show", "unknown"],
        vec!["tasks", "--repo", path, "list", "--rev", "missing-commit"],
        vec!["tasks", "--repo", path, "show", "T-1", "--rev", "--help"],
    ] {
        assert!(!repo.run(&args).status.success());
    }
    let poisoned = Command::new(env!("CARGO_BIN_EXE_autowork-next"))
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("GIT_DIR", "/nonexistent/foreign-git")
        .env("GIT_INDEX_FILE", repo.0.join("foreign-index"))
        .args(["tasks", "--repo", path, "show", "T-1"])
        .output()
        .unwrap();
    assert!(
        poisoned.status.success(),
        "{}",
        String::from_utf8_lossy(&poisoned.stderr)
    );
    assert_eq!(
        serde_json::from_slice::<Value>(&poisoned.stdout).unwrap()["revision"],
        second
    );
    assert!(!repo.0.join("foreign-index").exists());
    assert_eq!(std::fs::read(record).unwrap(), pending);
    assert_eq!(repo.git(&["status", "--porcelain"]), before);
    assert!(!repo.0.join(".git/autowork-tasks.lock").exists());
    assert!(!repo.0.join(".git/autowork-rust").exists());
}

#[test]
fn goal_queries_preserve_committed_content_types_and_revision_isolation() {
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let record = repo.0.join("tasks/goals/G-1.md");
    let original = std::fs::read_to_string(&record).unwrap();
    let first = repo.git(&["rev-parse", "HEAD"]);
    let committed = original.replace("Task store", "Committed goal");
    std::fs::write(&record, &committed).unwrap();
    repo.git(&["add", "tasks"]);
    repo.git(&["commit", "-qm", "goal update"]);
    let second = repo.git(&["rev-parse", "HEAD"]);
    std::fs::write(&record, b"invalid pending goal bytes").unwrap();
    let before = repo.git(&["status", "--porcelain"]);
    let list = repo.value(&["goals", "--repo", path, "list"]);
    assert_eq!(list["revision"], second);
    assert_eq!(list["source"], "committed");
    let row = &list["goals"][0];
    assert_eq!(row["content"], committed);
    assert_eq!(row["priority"], 1);
    assert_eq!(row["focus"], true);
    assert_eq!(row["source"], "docs/design.md#task-store");
    assert_eq!(
        repo.value(&["goals", "show", "G-1", "--repo", path])["goal"],
        *row
    );
    assert_eq!(
        repo.value(&["goals", "--repo", path, "list", "--rev", &first])["goals"][0]["content"],
        original
    );
    let old = repo.value(&["goals", "--repo", path, "--rev", &first, "show", "G-1"]);
    assert_eq!(old["revision"], first);
    assert_eq!(old["goal"]["content"], original);
    for args in [
        vec!["goals", "--repo", path, "show", "UNKNOWN"],
        vec!["goals", "--repo", path, "list", "--rev", "missing-commit"],
        vec![
            "goals", "--repo", path, "--rev", "HEAD", "list", "--rev", &first,
        ],
        vec!["--format", "inspection-v1", "goals", "--repo", path, "list"],
    ] {
        assert!(!repo.run(&args).status.success(), "{args:?}");
    }
    let poisoned = Command::new(env!("CARGO_BIN_EXE_autowork-next"))
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .env("GIT_DIR", "/nonexistent/foreign-git")
        .env("GIT_INDEX_FILE", repo.0.join("foreign-index"))
        .args(["goals", "--repo", path, "show", "G-1"])
        .output()
        .unwrap();
    assert!(poisoned.status.success());
    assert_eq!(
        serde_json::from_slice::<Value>(&poisoned.stdout).unwrap()["goal"],
        *row
    );
    assert!(!repo.0.join("foreign-index").exists());
    assert_eq!(
        std::fs::read(record).unwrap(),
        b"invalid pending goal bytes"
    );
    assert_eq!(repo.git(&["status", "--porcelain"]), before);
    assert!(!repo.0.join(".git/autowork-tasks.lock").exists());
    assert!(!repo.0.join(".git/autowork-rust").exists());
}

#[test]
fn goal_pending_edits_validate_types_preserve_notes_and_refuse_authority() {
    use autowork_next::task_store::TaskStore;
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let snapshot = TaskStore::read_at(&repo.0, "HEAD").unwrap();
    let base = snapshot.revision();
    let record = repo.0.join("tasks/goals/G-1.md");
    let task = repo.0.join("tasks/items/T-1.md");
    std::fs::write(
        &task,
        std::fs::read_to_string(&task)
            .unwrap()
            .replace("Read tasks", "Pending task"),
    )
    .unwrap();
    let task_bytes = std::fs::read(&task).unwrap();
    let original = std::fs::read_to_string(&record).unwrap();
    let notes = "- Unknown label: keep `literal` notes.\n- Owner decision: existing only\n";
    std::fs::write(&record, format!("{original}{notes}")).unwrap();
    let digest = |file: &std::path::Path| {
        let out = Command::new("sha256sum").arg(file).output().unwrap();
        String::from_utf8(out.stdout)
            .unwrap()
            .split_whitespace()
            .next()
            .unwrap()
            .to_owned()
    };
    let run = |base: &str, args: &[&str]| {
        let mut command = vec!["goals", "--repo", path, "--expected-revision", base];
        command.extend(args);
        repo.run(&command)
    };
    let field = |base: &str, hash: &str, key: &str, value: &str| {
        run(
            base,
            &["field", "G-1", "--record-revision", hash, key, value],
        )
    };
    let input = repo.0.join("proposal.md");
    let add_args = ["add", "G-2", "--record", input.to_str().unwrap()];
    let first_hash = digest(&record);
    let mut hash = first_hash.clone();
    for (key, value) in [
        ("title", "\"Pending goal\""),
        ("source", "\"docs/new.md#goal\""),
        ("priority", "7"),
        ("focus", "false"),
        ("depends_on", "[]"),
    ] {
        let out = field(base, &hash, key, value);
        assert!(
            out.status.success(),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
        let result: Value = serde_json::from_slice(&out.stdout).unwrap();
        assert_eq!(result["status"], "pending");
        assert_eq!(result["base_revision"], base);
        assert_eq!(result["selectable"], false);
        assert_eq!(result["publication"], "not-committed");
        assert_eq!(result["paths"], json!(["tasks/goals/G-1.md"]));
        hash = result["record_revisions"]["tasks/goals/G-1.md"]
            .as_str()
            .unwrap()
            .into();
        assert_eq!(hash, digest(&record));
    }
    let pending = std::fs::read_to_string(&record).unwrap();
    assert!(pending.ends_with(notes));
    assert!(pending.contains("title = \"Pending goal\""));
    assert!(pending.contains("priority = 7"));
    assert!(pending.contains("focus = false"));
    for (key, value) in [
        ("priority", "\"high\""),
        ("focus", "1"),
        ("source", "[]"),
        ("title", "false"),
        ("depends_on", "[1]"),
        ("depends_on", "[\"UNKNOWN\"]"),
        ("status", "\"met\""),
        ("closure", "\"manual\""),
        ("owner_qualification", "\"yes\""),
        ("live", "\"authorized\""),
        ("ownership", "\"owner\""),
        ("Owner decision", "\"new\""),
    ] {
        assert!(
            !field(base, &hash, key, value).status.success(),
            "{key}={value}"
        );
        assert_eq!(std::fs::read_to_string(&record).unwrap(), pending);
    }
    assert!(
        !field("stale", &hash, "title", "\"Stale base\"")
            .status
            .success()
    );
    assert!(
        !field(base, &first_hash, "title", "\"Stale record\"")
            .status
            .success()
    );
    let new = original
        .replace("G-1", "G-2")
        .replace("focus = true", "focus = false");
    for bad in [
        new.replace("unmet", "met"),
        new.replace("unmet", "partial"),
        new.replace("unmet", "unverified"),
        new.replace("priority = 1", "priority = true"),
        new.replace("schema = 1", "schema = 1\nlive = \"authorized\""),
        format!("{new}- Owner decision: invented\n"),
    ] {
        std::fs::write(&input, bad).unwrap();
        assert!(!run(base, &add_args).status.success());
        assert!(!repo.0.join("tasks/goals/G-2.md").exists());
    }
    std::fs::write(&input, &new).unwrap();
    let out = run(base, &add_args);
    assert!(out.status.success());
    let added: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(
        added["record_revisions"]["tasks/goals/G-2.md"],
        digest(&repo.0.join("tasks/goals/G-2.md"))
    );
    assert!(!run(base, &add_args).status.success());
    let out = run(
        base,
        &[
            "field",
            "G-2",
            "--record-revision",
            added["record_revisions"]["tasks/goals/G-2.md"]
                .as_str()
                .unwrap(),
            "depends_on",
            "[\"G-1\"]",
        ],
    );
    assert!(out.status.success());
    let linked: Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(
        linked["record_revisions"]["tasks/goals/G-2.md"],
        digest(&repo.0.join("tasks/goals/G-2.md"))
    );
    assert!(
        std::fs::read_to_string(repo.0.join("tasks/goals/G-2.md"))
            .unwrap()
            .contains("depends_on = [\"G-1\"]")
    );
    assert_eq!(std::fs::read_to_string(&record).unwrap(), pending);
    assert_eq!(std::fs::read(task).unwrap(), task_bytes);
    assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
    assert_eq!(
        repo.value(&["goals", "--repo", path, "list"])["goals"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    assert_eq!(
        repo.value(&["goals", "--repo", path, "show", "G-1"])["goal"]["content"],
        original
    );
    assert!(!repo.0.join(".git/autowork-rust/journal.sqlite3").exists());
}

#[test]
fn wire_formats_are_explicit_and_never_answer_in_the_other_shape() {
    let repo = TaskCliRepo::new();
    let path = repo.0.to_str().unwrap();
    let first = repo.git(&["rev-parse", "HEAD"]);
    let inspection = |args: &[&str]| {
        let mut all = vec!["--format", "inspection-v1"];
        all.extend(args);
        repo.run(&all)
    };
    // Both --repo/--rev placements select the same committed snapshot in both formats.
    let public = repo.value(&["tasks", "--repo", path, "--rev", &first, "list"]);
    assert_eq!(
        public,
        repo.value(&["tasks", "list", "--rev", &first, "--repo", path])
    );
    assert_eq!(public["schema_version"], 1);
    assert!(public["tasks"].is_array());
    let typed = inspection(&["tasks", "--repo", path, "--rev", &first, "list"]);
    assert!(typed.status.success());
    assert_eq!(
        typed.stdout,
        inspection(&["tasks", "list", "--repo", path, "--rev", &first]).stdout
    );
    let typed: Value = serde_json::from_slice(&typed.stdout).unwrap();
    assert_eq!(typed[0]["selection"]["revision"], first);
    // Contradictory or repeated revision inputs are refused.
    for args in [
        vec![
            "tasks", "--repo", path, "--rev", "HEAD", "list", "--rev", &first,
        ],
        vec!["tasks", "--repo", path, "--rev", &first, "preview"],
    ] {
        assert!(!repo.run(&args).status.success(), "{args:?}");
    }
    // A command outside the selected format fails instead of changing shape.
    for args in [
        vec!["tasks", "--repo", path, "goals"],
        vec!["tasks", "--repo", path, "why", "T-1"],
        vec!["tasks", "--repo", path, "commit", "--dry-run"],
        vec![
            "--format",
            "inspection-v1",
            "tasks",
            "--repo",
            path,
            "preview",
        ],
        vec!["--format", "unknown-v9", "tasks", "--repo", path, "list"],
    ] {
        assert!(!repo.run(&args).status.success(), "{args:?}");
    }
    assert_eq!(repo.git(&["status", "--porcelain"]), "");
    // --json marks JSON output; it never selects a format.
    assert_eq!(
        repo.value(&["status", "--repo", path]),
        repo.value(&["status", "--repo", path, "--json"])
    );
    let journal = inspection(&["status", "--repo", path, "--json"]);
    let journal: Value = serde_json::from_slice(&journal.stdout).unwrap();
    assert_eq!(journal["journal_state"], "absent");
    let capabilities = repo.value(&["capabilities"]);
    assert_eq!(capabilities["formats"]["selected"], "public-v1");
    assert_eq!(capabilities["formats"]["default"], "public-v1");
    assert_eq!(capabilities["commands"]["status"], "read-only-json-v1");
    assert_eq!(
        capabilities["formats"]["public-v1"]["pending_edits"],
        "exclusive-offline-only"
    );
    assert_eq!(
        capabilities["formats"]["inspection-v1"]["tasks"],
        json!(["list", "goals", "show", "why", "commit"])
    );
}

#[test]
fn pending_cli_requires_exclusion_before_task_or_journal_effects() {
    use fs2::FileExt;
    use std::io::BufRead;
    use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt};
    let actions = [
        vec!["tasks", "add", "T-2", "--record", "/missing-record"],
        vec![
            "tasks",
            "field",
            "T-1",
            "--record-revision",
            "missing",
            "title",
            "\"new\"",
        ],
        vec![
            "tasks",
            "place",
            "T-1",
            "--record-revision",
            "missing",
            "Next",
        ],
        vec!["tasks", "preview"],
        vec!["--format", "inspection-v1", "tasks", "commit", "--dry-run"],
        vec!["--format", "inspection-v1", "tasks", "commit"],
        vec!["goals", "add", "G-2", "--record", "/missing-record"],
        vec![
            "goals",
            "field",
            "G-1",
            "--record-revision",
            "missing",
            "title",
            "\"new\"",
        ],
    ];
    for mode in [
        "missing",
        "python-lock-dispatch",
        "python-lock-integration",
        "python-lock-writer",
        "python-attempt",
        "python-stale",
        "python-foreign",
        "python-dangling",
        "native",
        "unsafe-owner",
    ] {
        for action in &actions {
            let repo = TaskCliRepo::new();
            let path = repo.0.to_str().unwrap();
            let original = fs::read(repo.0.join("tasks/items/T-1.md")).unwrap();
            let base = repo.git(&["rev-parse", "HEAD"]);
            let objects = repo.git(&[
                "cat-file",
                "--batch-all-objects",
                "--batch-check=%(objectname)",
            ]);
            let scratch = repo.0.join("scratch");
            fs::create_dir(&scratch).unwrap();
            let mut python_lock = None;
            let mut python_worker = None;
            let native = if mode == "native" {
                Some(StateStore::open(repo.0.join(".git")).unwrap())
            } else {
                None
            };
            let python = repo.0.join(".git/autowork-execution");
            if mode.starts_with("python") || mode == "unsafe-owner" {
                fs::DirBuilder::new().mode(0o700).create(&python).unwrap();
                if mode == "python-dangling" {
                    std::os::unix::fs::symlink("missing", python.join("coordinator.json")).unwrap();
                } else if matches!(mode, "python-attempt" | "python-stale" | "python-foreign") {
                    let bytes = match mode {
                        "python-stale" => r#"{"owner":{"pid":99999999,"start_ticks":0}}"#,
                        "python-foreign" => r#"{"workspace":"foreign","owner":{"pid":1}}"#,
                        _ => "retained contract and receipt",
                    };
                    fs::write(python.join("active.json"), bytes).unwrap();
                } else {
                    let lock = fs::OpenOptions::new()
                        .create(true)
                        .truncate(false)
                        .read(true)
                        .write(true)
                        .mode(0o600)
                        .open(python.join(if mode == "python-lock-dispatch" {
                            "dispatch.lock"
                        } else if mode == "python-lock-integration" {
                            "integration.lock"
                        } else {
                            "writer.lock"
                        }))
                        .unwrap();
                    if mode.starts_with("python-lock-") {
                        if mode == "python-lock-writer" {
                            let mut child = Command::new("/usr/bin/python3")
                                .args(["-c", "import fcntl,sys; f=open(sys.argv[1],'r+'); fcntl.flock(f,fcntl.LOCK_EX); print('held',flush=True); sys.stdin.read()"])
                                .arg(python.join("writer.lock"))
                                .stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().unwrap();
                            let mut ready = String::new();
                            std::io::BufReader::new(child.stdout.take().unwrap())
                                .read_line(&mut ready)
                                .unwrap();
                            assert_eq!(ready, "held\n");
                            python_worker = Some(child);
                        } else {
                            lock.lock_exclusive().unwrap();
                        }
                        python_lock = Some(lock);
                    } else {
                        fs::set_permissions(
                            python.join("writer.lock"),
                            fs::Permissions::from_mode(0o644),
                        )
                        .unwrap();
                    }
                }
            }
            let before_journal = native.as_ref().map(|_| {
                journal_image(
                    &Connection::open(repo.0.join(".git/autowork-rust/journal.sqlite3")).unwrap(),
                )
            });
            let mut command = Command::new(env!("CARGO_BIN_EXE_autowork-next"));
            command
                .env_clear()
                .env("PATH", "/usr/bin:/bin")
                .env("TMPDIR", &scratch);
            if mode != "missing" {
                command.arg("--offline");
            }
            let result = command
                .args(action)
                .args(["--repo", path])
                .output()
                .unwrap();
            assert!(!result.status.success(), "mode={mode} action={action:?}");
            let diagnostic = String::from_utf8_lossy(&result.stderr);
            let expected = match mode {
                "missing" => "require --offline",
                "python-attempt" | "python-stale" | "python-foreign" | "python-dangling" => {
                    "Python execution state requires its owning runtime"
                }
                "native" => "repository journal writer is owned",
                "unsafe-owner" => "private, owned and not aliases",
                _ => "offline exclusion unavailable",
            };
            assert!(
                diagnostic.contains(expected),
                "mode={mode} action={action:?}: {diagnostic}"
            );
            assert!(
                !String::from_utf8_lossy(&result.stderr).contains("unexpected argument"),
                "{result:?}"
            );
            assert!(
                !repo.0.join(".git/autowork-tasks.lock").exists(),
                "mode={mode} action={action:?}"
            );
            assert!(fs::read_dir(&scratch).unwrap().next().is_none());
            assert_eq!(
                fs::read(repo.0.join("tasks/items/T-1.md")).unwrap(),
                original
            );
            assert_eq!(repo.git(&["rev-parse", "HEAD"]), base);
            assert_eq!(
                repo.git(&[
                    "cat-file",
                    "--batch-all-objects",
                    "--batch-check=%(objectname)"
                ]),
                objects
            );
            if let Some(before) = before_journal {
                assert_eq!(
                    journal_image(
                        &Connection::open(repo.0.join(".git/autowork-rust/journal.sqlite3"))
                            .unwrap()
                    ),
                    before
                );
            } else {
                assert!(!repo.0.join(".git/autowork-rust/journal.sqlite3").exists());
            }
            if mode == "missing" {
                assert!(!python.exists());
                assert!(!repo.0.join(".git/autowork-rust").exists());
            }
            if mode == "python-attempt" {
                assert_eq!(
                    fs::read_to_string(python.join("active.json")).unwrap(),
                    "retained contract and receipt"
                );
            }
            if let Some(mut child) = python_worker {
                drop(child.stdin.take());
                assert!(child.wait().unwrap().success());
            }
            drop(python_lock);
        }
    }
}
