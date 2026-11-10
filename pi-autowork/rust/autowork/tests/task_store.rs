use autowork_next::planning::{FailureEvidence, PlanDisposition, PlanProposal, RecordChange};
use autowork_next::task_store::{Scope, TaskService, TaskStore};
use fs2::FileExt;
use serde_json::json;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

const TASK: &str = include_str!("fixtures/task_store/tasks/items/T-1.md");
const GOAL: &str = include_str!("fixtures/task_store/tasks/goals/G-1.md");
static NEXT: AtomicU64 = AtomicU64::new(0);
struct Repo(PathBuf);
impl Repo {
    fn new() -> Self {
        let path = std::env::temp_dir().join(format!(
            "rust-task-store-test-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir(&path).unwrap();
        let repo = Self(path);
        repo.git(&["init", "-q", "-b", "main"]);
        repo.git(&["config", "user.name", "Fixture"]);
        repo.git(&["config", "user.email", "fixture@example.invalid"]);
        repo.write("tasks/items/T-1.md", TASK);
        repo.write("tasks/goals/G-1.md", GOAL);
        repo.commit();
        repo
    }
    fn write(&self, path: &str, text: impl AsRef<[u8]>) {
        let path = self.0.join(path);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(path, text).unwrap();
    }
    fn git(&self, args: &[&str]) -> String {
        self.git_input(args, "")
    }
    fn git_input(&self, args: &[&str], input: &str) -> String {
        let mut cmd = Command::new("git");
        for (k, _) in std::env::vars_os() {
            if k.to_string_lossy().starts_with("GIT_") {
                cmd.env_remove(k);
            }
        }
        let mut child = cmd
            .arg("-C")
            .arg(&self.0)
            .args(args)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .unwrap();
        child
            .stdin
            .take()
            .unwrap()
            .write_all(input.as_bytes())
            .unwrap();
        let out = child.wait_with_output().unwrap();
        assert!(
            out.status.success(),
            "git {args:?}: {}",
            String::from_utf8_lossy(&out.stderr)
        );
        String::from_utf8(out.stdout).unwrap().trim_end().to_owned()
    }
    fn commit(&self) {
        self.git(&["add", "-A"]);
        self.git(&["commit", "-qm", "fixture"]);
    }
    fn task(&self, id: &str, changes: &[(&str, &str)], extra: &str) {
        let mut bytes = TASK.replace("id = \"T-1\"", &format!("id = \"{id}\""));
        for (old, new) in changes {
            bytes = bytes.replace(old, new);
        }
        bytes = bytes.replace("+++\nFree notes.", &format!("{extra}+++\nFree notes."));
        self.write(&format!("tasks/items/{id}.md"), bytes);
    }
    fn proposal(&self, bytes: &str) -> PlanProposal {
        let base = TaskStore::read_at(&self.0, "HEAD").unwrap();
        PlanProposal {
            expected_revision: base.revision().into(),
            failed_operation: FailureEvidence {
                operation_id: "fixture".into(),
                fingerprint: "failure".into(),
                evidence_refs: vec![],
            },
            disposition: PlanDisposition::RepairCurrent,
            record_changes: vec![RecordChange {
                path: "tasks/items/T-1.md".into(),
                expected_revision: base.tasks()["T-1"].record_revision.clone(),
                proposed_bytes: bytes.as_bytes().to_vec(),
            }],
            reason: "bounded repair".into(),
            sources: vec!["docs/design.md#task-store".into()],
        }
    }
}
impl Drop for Repo {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}

#[test]
fn ungrouped_tasks_preserve_contracts_and_dependency_guards() {
    let r = Repo::new();
    let original = TaskStore::read_at(&r.0, "HEAD").unwrap();
    let hash = original.tasks()["T-1"].contract_hash.clone();
    let ungrouped = TASK.replace("goal = \"G-1\"\n", "");
    r.write("tasks/items/T-1.md", &ungrouped);
    r.write(
        "tasks/items/WAIT.md",
        ungrouped
            .replace("id = \"T-1\"", "id = \"WAIT\"")
            .replace("depends_on = []", "depends_on = [\"T-1\"]"),
    );
    r.commit();
    let snapshot = TaskStore::read_at(&r.0, "HEAD").unwrap();
    assert_eq!(snapshot.tasks()["T-1"].contract_hash, hash);
    assert!(!snapshot.tasks()["T-1"].draft());
    let selection = snapshot.select(&Scope::default()).unwrap();
    assert_eq!(selection.task_ids, vec!["T-1"]);
    assert_eq!(selection.blocked["WAIT"].code, "DEPENDENCY_UNFINISHED");
    r.write(
        "tasks/items/T-1.md",
        ungrouped.replace("touches = [\"src/\"]", "touches = []"),
    );
    r.commit();
    let snapshot = TaskStore::read_at(&r.0, "HEAD").unwrap();
    assert!(snapshot.tasks()["T-1"].draft());
}

#[test]
fn pinned_selection_preserves_contracts() {
    let r = Repo::new();
    r.write(
        "tasks/goals/G-2.md",
        GOAL.replace("G-1", "G-2")
            .replace("focus = true", "focus = false"),
    );
    r.write(
        "tasks/goals/G-WAIT.md",
        GOAL.replace("G-1", "G-WAIT")
            .replace("focus = true", "focus = false\ndepends_on = [\"G-2\"]"),
    );
    r.write(
        "tasks/goals/G-MET.md",
        GOAL.replace("G-1", "G-MET")
            .replace("focus = true", "focus = false")
            .replace("unmet", "met"),
    );
    for (id, changes, extra) in [
        (
            "NEXT",
            vec![("section = \"Now\"", "section = \"Next\"")],
            "",
        ),
        (
            "OTHER",
            vec![
                ("goal = \"G-1\"", "goal = \"G-2\""),
                ("rank = 1", "rank = -10"),
            ],
            "",
        ),
        (
            "AUTHORITY",
            vec![("ownership = \"worker\"", "ownership = \"owner\"")],
            "",
        ),
        (
            "PAUSED",
            vec![("section = \"Now\"", "section = \"Needs decision\"")],
            "",
        ),
        (
            "GOALWAIT",
            vec![("goal = \"G-1\"", "goal = \"G-WAIT\"")],
            "",
        ),
        ("GOALMET", vec![("goal = \"G-1\"", "goal = \"G-MET\"")], ""),
        (
            "DRAFT",
            vec![("checks = [\"python3 -m unittest\"]\n", "")],
            "",
        ),
        ("HELD", vec![], ""),
        ("EXPIRED", vec![], ""),
        ("DONE", vec![("status = \"open\"", "status = \"done\"")], ""),
        (
            "MANUAL",
            vec![("status = \"open\"", "status = \"done\"")],
            "closure = \"manual\"\nclosure_actor = \"Fixture owner\"\nclosure_timestamp = \"2026-01-01T00:00:00Z\"\nclosure_reason = \"Not qualified\"\nowner_waiver = \"Legacy prose is not proof\"\n",
        ),
        (
            "ORDINARY",
            vec![("depends_on = []", "depends_on = [\"MANUAL\"]")],
            "",
        ),
        (
            "WAIT",
            vec![("depends_on = []", "depends_on = [\"MISSING\"]")],
            "",
        ),
        (
            "STRICT",
            vec![("depends_on = []", "depends_on = [\"MANUAL\"]")],
            "verified_depends_on = [\"MANUAL\"]\n",
        ),
    ] {
        r.task(id, &changes, extra);
    }
    for (id, note) in [
        ("HELD", "- Held by: fixture; until 2099-01-01\n"),
        ("EXPIRED", "- Held by: fixture; until 2000-01-01\n"),
    ] {
        let path = format!("tasks/items/{id}.md");
        let bytes = fs::read_to_string(r.0.join(&path)).unwrap();
        r.write(&path, bytes + note);
    }
    r.write("tasks/items/LEGACY.md", "+++\nschema = 1\nid = \"LEGACY\"\ntitle = \"History\"\nstatus = \"done\"\n+++\nHistorical notes.\n");
    r.commit();
    let pinned = r.git(&["rev-parse", "HEAD"]);
    let snapshot = TaskStore::read_at(&r.0, "HEAD").unwrap();
    // Static expectations from the current schema-1 Python fixture, not a runtime dependency.
    assert_eq!(
        snapshot.tasks()["T-1"].record_revision,
        "259e3eaff874560b93d7f673e7d165a97d08ec57146522912f30cb27ade596e8"
    );
    assert_eq!(
        snapshot.tasks()["T-1"].contract_hash,
        "434acaef460510a4376e4f5e00789f667f2f531b2e97bb9b215f725f1459f4b0"
    );
    assert_eq!(snapshot.tasks()["T-1"].body, "Free notes.\n");
    assert!(!snapshot.tasks()["AUTHORITY"].runnable());
    assert!(!snapshot.tasks()["DONE"].qualified());
    assert!(!snapshot.tasks()["LEGACY"].draft());
    assert_eq!(snapshot.tasks()["LEGACY"].string("ownership"), "unknown");
    assert_eq!(snapshot.tasks()["LEGACY"].string("live"), "denied");
    assert_eq!(
        snapshot
            .select(&Scope {
                task_ids: vec!["T-1".into()]
            })
            .unwrap()
            .task_ids,
        ["T-1"]
    );
    let selected = snapshot.select_on(&Scope::default(), "2026-01-01").unwrap();
    assert_eq!(
        selected.task_ids,
        ["AUTHORITY", "EXPIRED", "ORDINARY", "T-1", "NEXT", "OTHER"]
    );
    for (id, reason) in [
        ("PAUSED", "NEEDS_DECISION"),
        ("GOALWAIT", "GOAL_DEPENDENCY_UNMET"),
        ("GOALMET", "GOAL_MET"),
        ("DRAFT", "DRAFT"),
        ("HELD", "HELD"),
        ("WAIT", "DEPENDENCY_UNFINISHED"),
        ("STRICT", "DEPENDENCY_UNVERIFIED"),
    ] {
        assert_eq!(selected.blocked[id].code, reason);
    }
    // Dirty bytes, even invalid ones, cannot change the pinned read or selection.
    r.write("tasks/items/T-1.md", "not a record");
    assert_eq!(
        TaskStore::read_at(&r.0, &pinned).unwrap().records(),
        snapshot.records()
    );
    r.write("tasks/items/T-1.md", TASK);
    let manual = fs::read_to_string(r.0.join("tasks/items/MANUAL.md")).unwrap();
    r.write("tasks/items/MANUAL.md", manual.replace("+++\nFree notes.", "waiver_actor = \"Fixture owner\"\nwaiver_at = \"2026-01-01\"\nwaiver_for = \"Pinned reads\"\n+++\nFree notes."));
    r.commit();
    assert!(
        TaskStore::read_at(&r.0, "HEAD")
            .unwrap()
            .select_on(
                &Scope {
                    task_ids: vec!["STRICT".into()]
                },
                "2026-01-01"
            )
            .unwrap()
            .task_ids
            .contains(&"STRICT".into())
    );
    assert!(!snapshot.tasks()["MANUAL"].qualified());
    for holder in [
        "Notuntil 2000-01-01",
        "fixture; until 2000-01-01pending",
        "fixture (indefinite)",
    ] {
        r.write(
            "tasks/items/HELD.md",
            format!("{}- Held by: {holder}\n", TASK.replace("T-1", "HELD")),
        );
        r.commit();
        assert_eq!(
            TaskStore::read_at(&r.0, "HEAD")
                .unwrap()
                .select_on(&Scope::default(), "2026-01-01")
                .unwrap()
                .blocked["HELD"]
                .code,
            "HELD"
        );
    }

    // Passing text alone is not evidence: require a real two-parent integration ancestor.
    r.task(
        "VERIFIED",
        &[("status = \"open\"", "status = \"done\"")],
        "closure = \"coordinator_verified\"\nclosure_evidence = \"tasks/evidence/VERIFIED.toml\"\n",
    );
    r.task(
        "EVIDENCE",
        &[("depends_on = []", "depends_on = [\"VERIFIED\"]")],
        "verified_depends_on = [\"VERIFIED\"]\n",
    );
    r.commit();
    let head = r.git(&["rev-parse", "HEAD"]);
    let tree = r.git(&["rev-parse", "HEAD^{tree}"]);
    let candidate = r.git_input(&["commit-tree", &tree, "-p", &head], "candidate\n");
    let integration = r.git_input(
        &["commit-tree", &tree, "-p", &head, "-p", &candidate],
        "integration\n",
    );
    r.git(&["update-ref", "HEAD", &integration, &head]);
    let hash = TaskStore::read_at(&r.0, "HEAD").unwrap().tasks()["VERIFIED"]
        .contract_hash
        .clone();
    let receipt = format!(
        "schema = 1\ntask = \"VERIFIED\"\ncontract_hash = \"{hash}\"\nresult = \"pass\"\nreview = \"passed\"\ncandidate = \"{candidate}\"\nintegration = \"{integration}\"\ntree = \"{tree}\"\n"
    );
    r.write("tasks/evidence/VERIFIED.toml", &receipt);
    r.commit();
    assert!(TaskStore::read_at(&r.0, "HEAD").unwrap().tasks()["VERIFIED"].verified());
    r.git(&[
        "tag",
        "-a",
        "integration-tag",
        &integration,
        "-m",
        "not a commit object",
    ]);
    let tag = r.git(&["rev-parse", "integration-tag"]);
    for bad in [
        receipt.replace(&hash, &"0".repeat(64)),
        receipt.replace(&integration, &candidate),
        receipt.replace("passed", "failed"),
        receipt.replace(&integration, &tag),
    ] {
        r.write("tasks/evidence/VERIFIED.toml", bad);
        r.commit();
        let s = TaskStore::read_at(&r.0, "HEAD").unwrap();
        assert!(!s.tasks()["VERIFIED"].qualified());
        assert_eq!(
            s.select_on(&Scope::default(), "2026-01-01")
                .unwrap()
                .blocked["EVIDENCE"]
                .code,
            "DEPENDENCY_UNVERIFIED"
        );
    }
}

#[test]
fn goal_edit_reader_uses_working_bytes_and_apply_rechecks_the_digest() {
    let r = Repo::new();
    let service = TaskService::new(&r.0).unwrap();
    let snapshot = TaskStore::read_at(&r.0, "HEAD").unwrap();
    let base = snapshot.revision();
    let hash = &snapshot.goals()["G-1"].record_revision;
    assert_eq!(
        service.goal_record_for_edit("G-1", hash).unwrap(),
        GOAL.as_bytes()
    );
    for id in ["UNKNOWN", "../G-1", "T-1"] {
        assert!(service.goal_record_for_edit(id, hash).is_err());
    }
    assert!(service.record_for_edit("G-1", hash).is_err());
    let edited = GOAL.replace("Task store", "Pending goal");
    let mut proposal = r.proposal(TASK);
    proposal.record_changes = vec![RecordChange {
        path: "tasks/goals/G-1.md".into(),
        expected_revision: hash.clone(),
        proposed_bytes: edited.as_bytes().to_vec(),
    }];
    let pending = service.apply(base, &proposal).unwrap();
    let hash = &pending.record_revisions["tasks/goals/G-1.md"];
    assert_eq!(
        service.goal_record_for_edit("G-1", hash).unwrap(),
        edited.as_bytes()
    );
    proposal.record_changes[0].expected_revision = hash.clone();
    // Another writer changes the record after the locked read, before apply.
    let external = format!("{edited}Unknown note: preserve me\n");
    r.write("tasks/goals/G-1.md", &external);
    assert!(service.apply(base, &proposal).is_err());
    assert!(service.goal_record_for_edit("G-1", hash).is_err());
    assert_eq!(
        fs::read(r.0.join("tasks/goals/G-1.md")).unwrap(),
        external.as_bytes()
    );
}

#[test]
fn transaction_refuses_stale_or_invalid_records() {
    let r = Repo::new();
    let service = TaskService::new(&r.0).unwrap();
    let before = fs::read(r.0.join("tasks/items/T-1.md")).unwrap();
    let edited = TASK.replace("Read tasks", "Pending title");
    let valid = r.proposal(&edited);
    let head = valid.expected_revision.clone();
    let mut stale = valid.clone();
    stale.record_changes[0].expected_revision = "stale".into();
    assert!(service.apply(&head, &stale).is_err());
    assert!(service.apply("stale", &valid).is_err());
    for bad in [
        TASK.replace("goal = \"G-1\"", "goal = \"UNKNOWN\""),
        TASK.replace("schema = 1", "schema = 2"),
        TASK.replace("resources = []", "resources = [\"[\\\"live\\\"]\"]"),
        TASK.replace("ownership = \"worker\"", "ownership = \"owner\""),
        format!("{TASK}- Held by: invented\n"),
    ] {
        assert!(service.apply(&head, &r.proposal(&bad)).is_err());
        assert_eq!(fs::read(r.0.join("tasks/items/T-1.md")).unwrap(), before);
    }
    let mut focused = valid.clone();
    focused.record_changes.push(RecordChange {
        path: "tasks/goals/G-2.md".into(),
        expected_revision: String::new(),
        proposed_bytes: GOAL.replace("G-1", "G-2").into_bytes(),
    });
    assert!(service.apply(&head, &focused).is_err());
    assert!(!r.0.join("tasks/goals/G-2.md").exists());

    // A flushed undo journal is the crash boundary; recover before consuming worktree bytes.
    let journal = r.0.join(".git/autowork-rust-tasks.transaction");
    for phase in ["before", "replace", "claim", "restore"] {
        fs::write(&journal, serde_json::to_vec(&json!([
            {"path":"tasks/items/T-1.md", "before":before,"after":edited.as_bytes()},
            {"path":"tasks/items/NEW.md", "before":null,"after":TASK.replace("T-1", "NEW").into_bytes()}
        ])).unwrap()).unwrap();
        if phase != "before" {
            r.write("tasks/items/T-1.md", &edited);
            r.write("tasks/items/NEW.md", TASK.replace("T-1", "NEW"));
        }
        if matches!(phase, "claim" | "restore") {
            fs::rename(
                r.0.join("tasks/items/T-1.md"),
                r.0.join("tasks/items/.T-1.md.autowork-rust.undo"),
            )
            .unwrap();
        }
        if phase == "restore" {
            r.write("tasks/items/.T-1.md.autowork-rust.tmp", &before);
            fs::hard_link(
                r.0.join("tasks/items/.T-1.md.autowork-rust.tmp"),
                r.0.join("tasks/items/T-1.md"),
            )
            .unwrap();
        }
        assert!(service.capture_pending().is_err());
        service.recover().unwrap();
        service.recover().unwrap();
        assert_eq!(fs::read(r.0.join("tasks/items/T-1.md")).unwrap(), before);
        assert!(!journal.exists());
        assert!(!r.0.join("tasks/items/NEW.md").exists());
    }
    // Undo never discards a non-cooperating editor's bytes, and retains originals in the journal.
    fs::write(
        &journal,
        serde_json::to_vec(
            &json!([{"path":"tasks/items/T-1.md", "before":before,"after":edited.as_bytes()}]),
        )
        .unwrap(),
    )
    .unwrap();
    r.write("tasks/items/T-1.md", "external bytes");
    assert!(service.recover().is_err());
    assert_eq!(
        fs::read_to_string(r.0.join("tasks/items/T-1.md")).unwrap(),
        "external bytes"
    );
    assert!(journal.exists());
    let saved = "tasks/items/.T-1.md.autowork-rust.undo";
    r.write(saved, "displaced external bytes");
    let conflict = service.recover().unwrap_err().to_string();
    assert!(conflict.contains(saved) && conflict.contains("tasks/items/T-1.md"));
    assert_eq!(
        fs::read_to_string(r.0.join(saved)).unwrap(),
        "displaced external bytes"
    );
    assert_eq!(
        fs::read_to_string(r.0.join("tasks/items/T-1.md")).unwrap(),
        "external bytes"
    );
    fs::remove_file(r.0.join(saved)).unwrap(); // fixture has reconciled the two external versions
    r.write("tasks/items/T-1.md", &before);
    service.recover().unwrap();

    let lock = OpenOptions::new()
        .append(true)
        .create(true)
        .open(r.0.join(".git/autowork-tasks.lock"))
        .unwrap();
    lock.lock_exclusive().unwrap();
    let path = r.0.clone();
    let (tx, rx) = std::sync::mpsc::channel();
    let thread = std::thread::spawn(move || {
        let s = TaskService::new(path).unwrap();
        tx.send(s.capture_pending().is_ok()).unwrap();
    });
    assert!(
        rx.recv_timeout(std::time::Duration::from_millis(50))
            .is_err()
    );
    FileExt::unlock(&lock).unwrap();
    assert!(rx.recv_timeout(std::time::Duration::from_secs(10)).unwrap());
    thread.join().unwrap();

    r.write("unrelated.txt", "unrelated staged bytes");
    r.git(&["add", "unrelated.txt"]);
    let index = fs::read(r.0.join(".git/index")).unwrap();
    let pending = service.apply(&head, &valid).unwrap();
    assert_eq!(pending.expected_revision, head);
    assert_eq!(pending.paths, [Path::new("tasks/items/T-1.md")]);
    assert_eq!(
        TaskStore::read_at(&r.0, "HEAD").unwrap().tasks()["T-1"].title,
        "Read tasks"
    );
    let captured = service.capture_pending().unwrap();
    assert_eq!(captured.base_head, head);
    assert_eq!(captured.branch, "refs/heads/main");
    assert_eq!(captured.token.len(), 64);
    assert_eq!(captured.token, service.capture_pending().unwrap().token);
    assert_eq!(
        captured.captured_bytes["tasks/items/T-1.md"],
        edited.as_bytes()
    );
    assert_eq!(
        r.git(&[
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            &head,
            &captured.tree
        ]),
        "tasks/items/T-1.md"
    );
    assert_eq!(
        r.git(&["show", &format!("{}:tasks/items/T-1.md", captured.tree)]),
        edited.trim_end()
    );
    assert!(
        TaskStore::read_at(&r.0, &captured.tree).is_err(),
        "a pending tree is not a committed selectable revision"
    );
    r.write("tasks/items/T-1.md", TASK);
    assert_ne!(captured.token, service.capture_pending().unwrap().token);
    assert_eq!(
        captured.captured_bytes["tasks/items/T-1.md"],
        edited.as_bytes(),
        "capture is frozen"
    );
    assert_eq!(fs::read(r.0.join(".git/index")).unwrap(), index);
    assert_eq!(r.git(&["rev-parse", "HEAD"]), head);
}
