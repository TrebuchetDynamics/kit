use autowork_next::runtime::{Role, RunIdentity, RuntimeEvent, RuntimeEventKind, RuntimeStatus};
use autowork_next::state::{
    DurableStatus, EffectKind, EffectObservation, EffectOutcome, Observations, RecordKind,
    StateStore, Transition,
};
use rusqlite::Connection;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{DirBuilderExt, OpenOptionsExt, PermissionsExt};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};

static NEXT: AtomicU64 = AtomicU64::new(0);
struct Repo(PathBuf);
impl Repo {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "rust-journal-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::DirBuilder::new().mode(0o700).create(&root).unwrap();
        // A valid empty Git common-dir, independent of any consumer checkout.
        fs::create_dir(root.join(".git")).unwrap();
        fs::create_dir(root.join(".git/objects")).unwrap();
        fs::create_dir(root.join(".git/refs")).unwrap();
        fs::write(root.join(".git/HEAD"), "ref: refs/heads/main\n").unwrap();
        Self(root)
    }
    fn common(&self) -> PathBuf {
        self.0.join(".git")
    }
    fn database(&self) -> PathBuf {
        self.common().join("autowork-rust/journal.sqlite3")
    }
}
impl Drop for Repo {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}
fn identity(store: &StateStore, generation: u64) -> RunIdentity {
    RunIdentity {
        repo_id: store.repo_id().into(),
        task_id: "TASK".into(),
        attempt_id: format!("attempt-{generation}"),
        generation,
        role: Role::Worker,
        contract_hash: "contract-sha256".into(),
    }
}
fn transition(identity: &RunIdentity, kind: RecordKind) -> Transition {
    let completion = kind == RecordKind::Completion;
    Transition {
        key: format!(
            "effect-{}-{}",
            if completion { "complete" } else { "intent" },
            identity.generation
        ),
        identity: identity.clone(),
        status: if completion {
            DurableStatus::Checking
        } else {
            DurableStatus::Executing
        },
        event: RuntimeEvent {
            schema_version: 1,
            repo_id: identity.repo_id.clone(),
            operation_id: "git-publication".into(),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            contract_hash: identity.contract_hash.clone(),
            source_revision: "source-commit".into(),
            role: identity.role,
            event: if completion {
                RuntimeEventKind::Outcome
            } else {
                RuntimeEventKind::Accepted
            },
            status: if completion {
                RuntimeStatus::Succeeded
            } else {
                RuntimeStatus::Running
            },
            evidence_ref: completion.then(|| "receipt".into()),
            timestamp: "123456".into(),
        },
        kind,
    }
}
fn observation(identity: &RunIdentity, outcome: EffectOutcome) -> Observations {
    Observations {
        effects: vec![EffectObservation {
            identity: identity.clone(),
            operation_id: "git-publication".into(),
            source_revision: "source-commit".into(),
            outcome,
            evidence_ref: "observed-git-or-owned-child-receipt".into(),
        }],
    }
}
fn agree(store: &StateStore, generation: u64) {
    let projection = store.projection("TASK", generation).unwrap();
    let events = store.events().unwrap();
    let (id, event) = events
        .iter()
        .rev()
        .find(|(_, e)| e.identity.generation == generation)
        .unwrap();
    assert_eq!(projection.event_id, *id);
    assert_eq!(projection.status, event.status);
    assert_eq!(projection.identity, event.identity);
    assert_eq!(projection.source_revision, event.event.source_revision);
    assert!(events.windows(2).all(|pair| pair[0].0.0 < pair[1].0.0));
}
fn child_case(root: &Path, boundary: &str) -> ! {
    let store = StateStore::open(root.join(".git")).unwrap();
    let run = identity(&store, 1);
    store.claim(0, run.clone(), "source-commit").unwrap();
    if boundary == "before_intent" {
        std::process::exit(0);
    }
    let intent = transition(&run, RecordKind::Intent(EffectKind::Git));
    if boundary == "before_projection_commit" {
        let sql = Connection::open(root.join(".git/autowork-rust/journal.sqlite3")).unwrap();
        sql.execute_batch("CREATE TRIGGER fail_projection BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT,'injected commit boundary'); END;").unwrap();
        assert!(store.transition(1, intent).is_err());
        std::process::exit(0);
    }
    let id = store.transition(1, intent.clone()).unwrap();
    assert_eq!(store.transition(1, intent.clone()).unwrap(), id);
    let mut conflict = intent;
    conflict.event.timestamp = "different content".into();
    assert!(store.transition(1, conflict).is_err());
    if boundary == "after_intent" {
        std::process::exit(0);
    }
    // Stand-in for a nontransactional external Git/child effect: create only once.
    let mut receipt = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(root.join("effect"))
        .unwrap();
    receipt.write_all(b"one effect\n").unwrap();
    receipt.sync_all().unwrap();
    if boundary == "after_effect" {
        std::process::exit(0);
    }
    store
        .transition(1, transition(&run, RecordKind::Completion))
        .unwrap();
    // Abrupt exit deliberately skips connection/lock destructors, retaining WAL.
    std::process::exit(0);
}

#[test]
fn recover_without_duplicate_effects() {
    if let Ok(boundary) = std::env::var("AW_JOURNAL_CRASH") {
        child_case(
            Path::new(&std::env::var_os("AW_JOURNAL_ROOT").unwrap()),
            &boundary,
        );
    }
    for boundary in [
        "before_intent",
        "before_projection_commit",
        "after_intent",
        "after_effect",
        "after_completion",
    ] {
        let repo = Repo::new();
        let result = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "recover_without_duplicate_effects",
                "--nocapture",
            ])
            .env("AW_JOURNAL_CRASH", boundary)
            .env("AW_JOURNAL_ROOT", &repo.0)
            .output()
            .unwrap();
        assert!(
            result.status.success(),
            "{boundary}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        let store = StateStore::open(repo.common()).unwrap();
        let old = identity(&store, 1);
        agree(&store, 1);
        let sql = Connection::open(repo.database()).unwrap();
        sql.execute_batch("DROP TRIGGER IF EXISTS fail_projection")
            .unwrap();
        if boundary == "before_intent" || boundary == "before_projection_commit" {
            assert_eq!(store.events().unwrap().len(), 1);
            assert_eq!(
                store.projection("TASK", 1).unwrap().status,
                DurableStatus::Ready
            );
        }
        // A restart never grants the retained attempt's authority to this owner.
        assert!(
            store
                .transition(1, transition(&old, RecordKind::Completion))
                .is_err()
        );
        let current = identity(&store, 2);
        store.claim(1, current.clone(), "source-commit").unwrap();
        let pending = boundary == "after_intent" || boundary == "after_effect";
        let recovered = store.reconcile(Observations::default()).unwrap();
        assert_eq!(
            recovered.reconcile_operation_ids.len(),
            usize::from(pending)
        );
        if pending {
            let mut premature_success = transition(&current, RecordKind::Note);
            premature_success.key = "premature-complete".into();
            premature_success.status = DurableStatus::Complete;
            premature_success.event.status = RuntimeStatus::Succeeded;
            assert!(store.transition(2, premature_success).is_err());
            assert!(
                store
                    .transition(2, transition(&current, RecordKind::Intent(EffectKind::Git)))
                    .is_err()
            );
            assert!(
                store
                    .reconcile(observation(&current, EffectOutcome::Applied))
                    .is_err()
            );
            let mut wrong_source = observation(&old, EffectOutcome::Applied);
            wrong_source.effects[0].source_revision = "wrong-source".into();
            assert!(store.reconcile(wrong_source).is_err());
            assert_eq!(
                store
                    .reconcile(observation(&old, EffectOutcome::Unknown))
                    .unwrap()
                    .reconcile_operation_ids
                    .len(),
                1
            );
            let outcome = if repo.0.join("effect").exists() {
                EffectOutcome::Applied
            } else {
                EffectOutcome::Absent
            };
            let resolved = store.reconcile(observation(&old, outcome)).unwrap();
            assert!(resolved.reconcile_operation_ids.is_empty());
            assert_eq!(resolved.resolved[0].outcome, outcome);
            assert_eq!(
                store.projection("TASK", 1).unwrap().status,
                DurableStatus::Uncertain
            );
            let count = store.events().unwrap().len();
            store.reconcile(observation(&old, outcome)).unwrap();
            assert_eq!(store.events().unwrap().len(), count);
            let contradictory = if outcome == EffectOutcome::Applied {
                EffectOutcome::Absent
            } else {
                EffectOutcome::Applied
            };
            assert!(store.reconcile(observation(&old, contradictory)).is_err());
        }
        if boundary == "after_completion" || boundary == "after_effect" {
            assert_eq!(fs::read(repo.0.join("effect")).unwrap(), b"one effect\n");
            // Even a fresh generation cannot replay the already-applied operation.
            assert!(
                store
                    .transition(2, transition(&current, RecordKind::Intent(EffectKind::Git)))
                    .is_err()
            );
        } else {
            assert!(!repo.0.join("effect").exists());
        }
        agree(&store, 1);
        agree(&store, 2);
        assert_eq!(
            store.projection("TASK", 2).unwrap().status,
            DurableStatus::Ready
        );
        assert!(
            store
                .events()
                .unwrap()
                .iter()
                .all(|(_, e)| e.status != DurableStatus::Complete)
        );
        assert_eq!(
            sql.query_row("SELECT count(*) FROM pragma_foreign_key_check", [], |r| r
                .get::<_, i64>(
                0
            ))
            .unwrap(),
            0
        );
        if boundary == "after_intent" {
            // Absence, unlike uncertainty, permits an explicitly requested new intent.
            store
                .transition(2, transition(&current, RecordKind::Intent(EffectKind::Git)))
                .unwrap();
            assert_eq!(
                store
                    .reconcile(Observations::default())
                    .unwrap()
                    .reconcile_operation_ids
                    .len(),
                1
            );
            assert!(!repo.0.join("effect").exists());
            agree(&store, 2);
        }
    }
}

#[test]
fn fence_foreign_owner_and_schema() {
    let repo = Repo::new();
    let directory = repo.common().join("autowork-rust");
    fs::DirBuilder::new()
        .mode(0o700)
        .create(&directory)
        .unwrap();
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(repo.database())
        .unwrap();
    let store = StateStore::open(repo.common()).unwrap();
    let backup = directory.join("journal.schema-0.backup.sqlite3");
    assert_eq!(
        Connection::open(&backup)
            .unwrap()
            .query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))
            .unwrap(),
        0
    );
    assert_eq!(
        fs::metadata(repo.database()).unwrap().permissions().mode() & 0o777,
        0o600
    );
    drop(store);
    // Reconstruct interruption after backup, before the schema transaction committed.
    let retained_backup = fs::read(&backup).unwrap();
    fs::copy(&backup, repo.database()).unwrap();
    let store = StateStore::open(repo.common()).unwrap();
    assert_eq!(fs::read(&backup).unwrap(), retained_backup);
    assert!(StateStore::open(repo.common()).is_err());
    let run = identity(&store, 1);
    store.claim(0, run.clone(), "source-commit").unwrap();
    assert!(store.claim(0, run.clone(), "source-commit").is_err());
    let note = transition(&run, RecordKind::Note);
    let sql = Connection::open(repo.database()).unwrap();
    let retained_owner: String = sql
        .query_row("SELECT owner FROM metadata", [], |r| r.get(0))
        .unwrap();
    // Same PID, different birth identity: neither an inherited lock nor PID reuse grants authority.
    let mut reused: serde_json::Value = serde_json::from_str(&retained_owner).unwrap();
    reused["birth_ticks"] = serde_json::json!(reused["birth_ticks"].as_u64().unwrap() + 1);
    sql.execute("UPDATE metadata SET owner=?1", [reused.to_string()])
        .unwrap();
    assert!(store.transition(1, note.clone()).is_err());
    assert!(store.reconcile(Observations::default()).is_err());
    sql.execute("UPDATE metadata SET owner=?1", [&retained_owner])
        .unwrap();
    let mut foreign = note.clone();
    foreign.identity.attempt_id = "foreign-attempt".into();
    foreign.event.attempt_id = "foreign-attempt".into();
    assert!(store.transition(1, foreign).is_err());
    let mut wrong_contract = note.clone();
    wrong_contract.identity.contract_hash = "foreign-contract".into();
    wrong_contract.event.contract_hash = "foreign-contract".into();
    assert!(store.transition(1, wrong_contract).is_err());
    let mut wrong_source = note.clone();
    wrong_source.event.source_revision = "foreign-source".into();
    assert!(store.transition(1, wrong_source).is_err());
    let id = store.transition(1, note.clone()).unwrap();
    assert_eq!(store.transition(1, note.clone()).unwrap(), id);
    store
        .claim(1, identity(&store, 2), "new-source-commit")
        .unwrap();
    assert!(store.transition(1, note).is_err());
    agree(&store, 1);
    agree(&store, 2);
    let events = store.events().unwrap().len() as i64;
    drop(sql);
    drop(store);
    let other = Repo::new();
    fs::DirBuilder::new()
        .mode(0o700)
        .create(other.common().join("autowork-rust"))
        .unwrap();
    fs::copy(repo.database(), other.database()).unwrap();
    assert!(StateStore::open(other.common()).is_err());
    let sql = Connection::open(repo.database()).unwrap();
    sql.pragma_update(None, "user_version", 2).unwrap();
    drop(sql);
    let bytes = fs::read(repo.database()).unwrap();
    assert!(StateStore::open(repo.common()).is_err());
    assert_eq!(fs::read(repo.database()).unwrap(), bytes);
    let sql = Connection::open(repo.database()).unwrap();
    assert_eq!(
        sql.query_row("SELECT count(*) FROM events", [], |r| r.get::<_, i64>(0))
            .unwrap(),
        events
    );
    assert_eq!(
        sql.query_row("PRAGMA user_version", [], |r| r.get::<_, i64>(0))
            .unwrap(),
        2
    );
    assert!(backup.exists());
}
