//! Private, repository-bound journal. External effects are never replayed here.
use crate::runtime::{RunIdentity, RuntimeEvent, RuntimeEventKind, RuntimeStatus};
use fs2::FileExt;
use rusqlite::{Connection, OpenFlags, OptionalExtension, TransactionBehavior, params};
use serde::{Deserialize, Serialize};
use std::fs::{self, File, OpenOptions};
use std::os::unix::fs::{DirBuilderExt, MetadataExt, OpenOptionsExt};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

pub const SCHEMA_VERSION: i64 = 1;

#[derive(Debug)]
pub struct StateError(pub String);
impl std::fmt::Display for StateError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for StateError {}
macro_rules! convert_error {
    ($($ty:ty),*) => {$(
        impl From<$ty> for StateError {
            fn from(error: $ty) -> Self { Self(error.to_string()) }
        }
    )*};
}
convert_error!(std::io::Error, rusqlite::Error, serde_json::Error);
pub type Result<T> = std::result::Result<T, StateError>;
fn require(condition: bool, reason: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(StateError(reason.into()))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
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

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectKind {
    Child,
    Git,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RecordKind {
    Note,
    Intent(EffectKind),
    Completion,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Transition {
    /// Stable idempotency key for this record, not the whole agent stream.
    pub key: String,
    pub identity: RunIdentity,
    pub status: DurableStatus,
    pub event: RuntimeEvent,
    pub kind: RecordKind,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct EventId(pub i64);

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EffectOutcome {
    Applied,
    Absent,
    Unknown,
}

/// Coordinator-authored evidence from inspecting actual Git/owned-child effects.
/// This is not a process-adoption API, nor authority to accept a canonical task.
pub struct EffectObservation {
    pub identity: RunIdentity,
    pub operation_id: String,
    pub source_revision: String,
    pub outcome: EffectOutcome,
    pub evidence_ref: String,
}
#[derive(Default)]
pub struct Observations {
    pub effects: Vec<EffectObservation>,
}
#[derive(Debug)]
pub struct RecoveredOperation {
    pub identity: RunIdentity,
    pub operation_id: String,
    pub outcome: EffectOutcome,
    pub evidence_ref: String,
}
#[derive(Default, Debug)]
pub struct RecoveryActions {
    pub reconcile_operation_ids: Vec<String>,
    pub resolved: Vec<RecoveredOperation>,
}
#[derive(Debug)]
pub struct Projection {
    pub identity: RunIdentity,
    pub source_revision: String,
    pub status: DurableStatus,
    pub event_id: EventId,
}

#[derive(Debug, PartialEq, Eq, Serialize, Deserialize)]
struct Repository {
    common_dir: PathBuf,
    device: u64,
    inode: u64,
}
impl Repository {
    fn inspect(path: &Path) -> Result<Self> {
        let common_dir = fs::canonicalize(path)?;
        require(
            common_dir.join("HEAD").is_file()
                && common_dir.join("objects").is_dir()
                && common_dir.join("refs").is_dir(),
            "expected a Git common directory",
        )?;
        let meta = fs::metadata(&common_dir)?;
        Ok(Self {
            common_dir,
            device: meta.dev(),
            inode: meta.ino(),
        })
    }
}

#[derive(Debug, PartialEq, Eq, Serialize, Deserialize)]
struct Owner {
    pid: u32,
    birth_ticks: u64,
    boot_id: String,
}
impl Owner {
    fn current() -> Result<Self> {
        let stat = fs::read_to_string("/proc/self/stat")?;
        let birth_ticks = stat
            .rsplit_once(") ")
            .and_then(|(_, fields)| fields.split_whitespace().nth(19))
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| StateError("cannot verify owner birth identity".into()))?;
        Ok(Self {
            pid: std::process::id(),
            birth_ticks,
            boot_id: fs::read_to_string("/proc/sys/kernel/random/boot_id")?
                .trim()
                .into(),
        })
    }
}

/// Fixed diagnostics: never forward SQLite, filesystem or private payload text.
#[derive(Debug)]
pub enum InspectionError {
    UnsafeSource,
    UnsupportedSchema,
    ForeignJournal,
    CorruptJournal,
    Busy,
}
impl InspectionError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::UnsafeSource => "unsafe_source",
            Self::UnsupportedSchema => "unsupported_schema",
            Self::ForeignJournal => "foreign_journal",
            Self::CorruptJournal => "corrupt_journal",
            Self::Busy => "busy",
        }
    }
}
impl std::fmt::Display for InspectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "journal inspection unavailable: {}; state retained",
            self.code()
        )
    }
}
impl std::error::Error for InspectionError {}
impl From<rusqlite::Error> for InspectionError {
    fn from(error: rusqlite::Error) -> Self {
        match error.sqlite_error_code() {
            Some(rusqlite::ErrorCode::DatabaseBusy | rusqlite::ErrorCode::DatabaseLocked) => {
                Self::Busy
            }
            _ => Self::CorruptJournal,
        }
    }
}

#[derive(Serialize)]
pub struct StatusRepository {
    device: u64,
    inode: u64,
}
#[derive(Serialize)]
pub struct StatusProjection {
    task_id: String,
    attempt_id: String,
    generation: u64,
    role: crate::runtime::Role,
    contract_hash: String,
    source_revision: String,
    status: DurableStatus,
    event_id: i64,
}
#[derive(Serialize)]
pub struct JournalStatus {
    schema_version: u32,
    source: &'static str,
    repository: StatusRepository,
    journal_state: &'static str,
    journal_schema: Option<i64>,
    event_high_water_mark: Option<i64>,
    projections: Vec<StatusProjection>,
}

/// A short read transaction, not a StateStore and never a writer lease.
/// Ordinary SQLite WAL coordination may create/change its own private sidecars.
pub fn read_status(common_dir: &Path) -> std::result::Result<JournalStatus, InspectionError> {
    Ok(read_snapshot(common_dir)?.0)
}

fn read_snapshot(
    common_dir: &Path,
) -> std::result::Result<(JournalStatus, Vec<serde_json::Value>), InspectionError> {
    let mut history = Vec::new();
    let repository = Repository::inspect(common_dir).map_err(|_| InspectionError::UnsafeSource)?;
    require_local(&repository.common_dir).map_err(|_| InspectionError::UnsafeSource)?;
    let mut status = JournalStatus {
        schema_version: 1,
        source: "runtime-journal",
        repository: StatusRepository {
            device: repository.device,
            inode: repository.inode,
        },
        journal_state: "absent",
        journal_schema: None,
        event_high_water_mark: None,
        projections: vec![],
    };
    let directory = repository.common_dir.join("autowork-rust");
    let exists = |path: &Path, directory: bool| -> std::result::Result<bool, InspectionError> {
        match fs::symlink_metadata(path) {
            Ok(_) => {
                private_path(path, directory)
                    .and_then(|_| require_local(path))
                    .map_err(|_| InspectionError::UnsafeSource)?;
                Ok(true)
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(false),
            Err(_) => Err(InspectionError::UnsafeSource),
        }
    };
    if !exists(&directory, true)? {
        return Ok((status, history));
    }
    for name in [
        "writer.lock",
        "journal.sqlite3-wal",
        "journal.sqlite3-shm",
        "journal.sqlite3-journal",
    ] {
        exists(&directory.join(name), false)?;
    }
    let database = directory.join("journal.sqlite3");
    if !exists(&database, false)? {
        return Ok((status, history));
    }
    let mut connection = Connection::open_with_flags(
        &database,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NOFOLLOW,
    )?;
    connection.busy_timeout(std::time::Duration::from_millis(200))?;
    connection.pragma_update(None, "query_only", true)?;
    let tx = connection.transaction()?;
    let version: i64 = tx.pragma_query_value(None, "user_version", |r| r.get(0))?;
    if version != SCHEMA_VERSION {
        return Err(InspectionError::UnsupportedSchema);
    }
    let (count, retained, epoch): (i64, String, i64) =
        tx.query_row("SELECT count(*),repository,epoch FROM metadata", [], |r| {
            Ok((r.get(0)?, r.get(1)?, r.get(2)?))
        })?;
    if count != 1 || epoch < 1 {
        return Err(InspectionError::CorruptJournal);
    }
    let retained: Repository =
        serde_json::from_str(&retained).map_err(|_| InspectionError::CorruptJournal)?;
    if retained != repository {
        return Err(InspectionError::ForeignJournal);
    }
    let repo_id =
        serde_json::to_string(&repository).map_err(|_| InspectionError::CorruptJournal)?;
    let high_water: i64 =
        tx.query_row("SELECT coalesce(max(id),0) FROM events", [], |r| r.get(0))?;
    {
        let mut statement = tx.prepare(
            "SELECT task,generation,identity,source,status,event_id,
                (SELECT payload FROM events WHERE id=r.event_id),
                (SELECT key FROM events WHERE id=r.event_id),
                generation=(SELECT max(generation) FROM runs WHERE task=r.task), owner_epoch
             FROM runs r ORDER BY task,generation",
        )?;
        let mut rows = statement.query([])?;
        while let Some(row) = rows.next()? {
            let task: String = row.get(0)?;
            let generation: i64 = row.get(1)?;
            let identity: String = row.get(2)?;
            let source: String = row.get(3)?;
            let durable: String = row.get(4)?;
            let event_id: i64 = row.get(5)?;
            let payload: Option<String> = row.get(6)?;
            let key: Option<String> = row.get(7)?;
            let latest: bool = row.get(8)?;
            let owner_epoch: i64 = row.get(9)?;
            let transition: Transition =
                serde_json::from_str(&payload.ok_or(InspectionError::CorruptJournal)?)
                    .map_err(|_| InspectionError::CorruptJournal)?;
            let event = &transition.event;
            let identity: RunIdentity =
                serde_json::from_str(&identity).map_err(|_| InspectionError::CorruptJournal)?;
            let durable: DurableStatus =
                serde_json::from_str(&durable).map_err(|_| InspectionError::CorruptJournal)?;
            validate_identity(&identity, &repo_id, &source)
                .map_err(|_| InspectionError::CorruptJournal)?;
            if identity.task_id != task
                || generation <= 0
                || identity.generation != generation as u64
                || event_id <= 0
                || event_id > high_water
                || owner_epoch < 1
                || owner_epoch > epoch
                || transition.identity != identity
                || transition.status != durable
                || key.as_deref() != Some(transition.key.as_str())
                || transition.key.is_empty()
                || event.repo_id != identity.repo_id
                || event.task_id != identity.task_id
                || event.attempt_id != identity.attempt_id
                || event.generation != identity.generation
                || event.role != identity.role
                || event.contract_hash != identity.contract_hash
                || event.source_revision != source
                || event.to_json_line().is_err()
            {
                return Err(InspectionError::CorruptJournal);
            }
            history.push(serde_json::json!({"task": task, "generation": generation,
                "status": durable, "revision": source}));
            if latest {
                status.projections.push(StatusProjection {
                    task_id: identity.task_id,
                    attempt_id: identity.attempt_id,
                    generation: identity.generation,
                    role: identity.role,
                    contract_hash: identity.contract_hash,
                    source_revision: source,
                    status: durable,
                    event_id,
                });
            }
        }
    }
    tx.commit()?;
    status.journal_state = "present";
    status.journal_schema = Some(version);
    status.event_high_water_mark = Some(high_water);
    Ok((status, history))
}

/// Exclusive offline boundary for pending CLI edits. Python execution history is
/// deliberately unsupported: even an idle-looking retained attempt is refused.
pub struct OfflineAdmission {
    _python: Vec<File>,
    repository: Repository,
    native: Option<File>,
}
impl OfflineAdmission {
    pub fn acquire(common_dir: &Path) -> Result<Self> {
        let repository = Repository::inspect(common_dir)?;
        require_local(&repository.common_dir)?;
        let directory = repository.common_dir.join("autowork-execution");
        match fs::DirBuilder::new().mode(0o700).create(&directory) {
            Ok(()) => (),
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(error) => return Err(error.into()),
        }
        private_path(&directory, true)?;
        require_local(&directory)?;
        let names = ["dispatch.lock", "integration.lock", "writer.lock"];
        let mut locks = Vec::new();
        for name in names {
            let lock = private_file(&directory.join(name))?;
            require_local(&directory.join(name))?;
            lock.try_lock_exclusive()
                .map_err(|_| StateError("offline exclusion unavailable".into()))?;
            locks.push(lock);
        }
        for entry in fs::read_dir(&directory)? {
            require(
                names
                    .iter()
                    .any(|name| entry.as_ref().is_ok_and(|entry| entry.file_name() == *name)),
                "Python execution state requires its owning runtime",
            )?;
        }
        let native_dir = repository.common_dir.join("autowork-rust");
        match fs::DirBuilder::new().mode(0o700).create(&native_dir) {
            Ok(()) => (),
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(error) => return Err(error.into()),
        }
        private_path(&native_dir, true)?;
        require_local(&native_dir)?;
        let native = private_file(&native_dir.join("writer.lock"))?;
        require_local(&native_dir.join("writer.lock"))?;
        native
            .try_lock_exclusive()
            .map_err(|_| StateError("repository journal writer is owned".into()))?;
        Ok(Self {
            _python: locks,
            repository,
            native: Some(native),
        })
    }
}

pub struct StateStore {
    connection: Mutex<Connection>,
    // Drop the connection before releasing the cooperative repository lock.
    _writer: File,
    _offline: Vec<File>,
    repository: Repository,
    repo_id: String,
    owner: Owner,
    epoch: i64,
    directory: PathBuf,
}

impl StateStore {
    /// The caller resolves Git's common-dir; no Git subprocess or Python state is used.
    pub fn open(common_dir: impl AsRef<Path>) -> Result<Self> {
        Self::open_admitted(common_dir, None)
    }

    pub fn open_offline(
        common_dir: impl AsRef<Path>,
        admission: &mut OfflineAdmission,
    ) -> Result<Self> {
        Self::open_admitted(common_dir, Some(admission))
    }

    fn open_admitted(
        common_dir: impl AsRef<Path>,
        admission: Option<&mut OfflineAdmission>,
    ) -> Result<Self> {
        let repository = Repository::inspect(common_dir.as_ref())?;
        require_local(&repository.common_dir)?;
        let mut offline_locks = Vec::new();
        let writer = match admission {
            Some(admission) => {
                require(
                    admission.repository == repository,
                    "foreign offline exclusion",
                )?;
                offline_locks = std::mem::take(&mut admission._python);
                Some(
                    admission
                        .native
                        .take()
                        .ok_or_else(|| StateError("consumed offline exclusion".into()))?,
                )
            }
            None => None,
        };
        let directory = repository.common_dir.join("autowork-rust");
        match fs::DirBuilder::new().mode(0o700).create(&directory) {
            Ok(()) => File::open(&repository.common_dir)?.sync_all()?,
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(e) => return Err(e.into()),
        }
        private_path(&directory, true)?;
        require_local(&directory)?;
        let writer = match writer {
            Some(writer) => writer,
            None => private_file(&directory.join("writer.lock"))?,
        };
        require_local(&directory.join("writer.lock"))?;
        writer
            .try_lock_exclusive()
            .map_err(|_| StateError("repository journal writer is owned".into()))?;
        let database = directory.join("journal.sqlite3");
        let existed = database.try_exists()?;
        let database_file = private_file(&database)?;
        require_local(&database)?;
        for suffix in ["-wal", "-shm", "-journal"] {
            let sidecar = directory.join(format!("journal.sqlite3{suffix}"));
            match fs::symlink_metadata(&sidecar) {
                Ok(_) => {
                    private_path(&sidecar, false)?;
                    require_local(&sidecar)?;
                }
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                Err(e) => return Err(e.into()),
            }
        }
        database_file.sync_all()?;
        let flags = OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NOFOLLOW;
        let mut connection = Connection::open_with_flags(&database, flags)?;
        let version: i64 = connection.pragma_query_value(None, "user_version", |r| r.get(0))?;
        require(
            (0..=SCHEMA_VERSION).contains(&version),
            "unsupported journal schema; state retained",
        )?;
        if version == 0 {
            let tables: i64 = connection.query_row(
                "SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'",
                [],
                |r| r.get(0),
            )?;
            require(
                tables == 0,
                "unrecognized unversioned journal; state retained",
            )?;
            if existed {
                // No in-place migration without a durable, SQLite-consistent backup.
                let backup = directory.join("journal.schema-0.backup.sqlite3");
                if backup.try_exists()? {
                    // A crash after backup but before migration must be resumable.
                    private_path(&backup, false)?;
                    let saved = Connection::open_with_flags(
                        &backup,
                        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NOFOLLOW,
                    )?;
                    let valid: bool = saved.query_row(
                        "SELECT (SELECT user_version FROM pragma_user_version)=0 AND
                         (SELECT count(*) FROM sqlite_master WHERE name NOT LIKE 'sqlite_%')=0",
                        [],
                        |r| r.get(0),
                    )?;
                    require(valid, "unrecognized migration backup; state retained")?;
                } else {
                    let file = OpenOptions::new()
                        .write(true)
                        .create_new(true)
                        .mode(0o600)
                        .open(&backup)?;
                    connection.execute("VACUUM INTO ?1", [backup.to_string_lossy().as_ref()])?;
                    file.sync_all()?;
                }
                File::open(&directory)?.sync_all()?;
            }
        } else {
            let retained: String =
                connection.query_row("SELECT repository FROM metadata", [], |r| r.get(0))?;
            require(
                retained == serde_json::to_string(&repository)?,
                "journal belongs to a different Git common-dir",
            )?;
        }
        connection.pragma_update(None, "foreign_keys", true)?;
        let mode: String = connection.query_row("PRAGMA journal_mode=WAL", [], |r| r.get(0))?;
        require(mode == "wal", "local WAL unavailable")?;
        connection.pragma_update(None, "synchronous", "FULL")?;
        let owner = Owner::current()?;
        let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        if version == 0 {
            tx.execute_batch(
                "CREATE TABLE metadata(repository TEXT NOT NULL, epoch INTEGER NOT NULL, owner TEXT NOT NULL);
                 CREATE TABLE events(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL);
                 CREATE TABLE runs(task TEXT NOT NULL, generation INTEGER NOT NULL CHECK(generation > 0),
                    identity TEXT NOT NULL, source TEXT NOT NULL, owner_epoch INTEGER NOT NULL,
                    status TEXT NOT NULL, event_id INTEGER NOT NULL REFERENCES events(id),
                    PRIMARY KEY(task,generation));
                 CREATE TABLE effects(operation TEXT NOT NULL, task TEXT NOT NULL, generation INTEGER NOT NULL,
                    intent INTEGER NOT NULL UNIQUE REFERENCES events(id),
                    resolution INTEGER REFERENCES events(id), outcome TEXT,
                    PRIMARY KEY(operation,generation), FOREIGN KEY(task,generation) REFERENCES runs(task,generation));
                 PRAGMA user_version=1;"
            )?;
            tx.execute(
                "INSERT INTO metadata VALUES (?1,0,'')",
                [serde_json::to_string(&repository)?],
            )?;
        }
        tx.execute(
            "UPDATE metadata SET epoch=epoch+1, owner=?1",
            [serde_json::to_string(&owner)?],
        )?;
        let epoch = tx.query_row("SELECT epoch FROM metadata", [], |r| r.get(0))?;
        tx.commit()?;
        File::open(&directory)?.sync_all()?;
        let repo_id = serde_json::to_string(&repository)?;
        Ok(Self {
            connection: Mutex::new(connection),
            _writer: writer,
            _offline: offline_locks,
            repository,
            repo_id,
            owner,
            epoch,
            directory,
        })
    }

    pub fn repo_id(&self) -> &str {
        &self.repo_id
    }
    pub fn directory(&self) -> &Path {
        &self.directory
    }

    fn verify_owner(&self, connection: &Connection) -> Result<()> {
        require(
            self.owner == Owner::current()?,
            "foreign process or reused PID",
        )?;
        require(
            self.repository == Repository::inspect(&self.repository.common_dir)?,
            "Git common-dir identity changed",
        )?;
        let (epoch, owner): (i64, String) =
            connection.query_row("SELECT epoch,owner FROM metadata", [], |r| {
                Ok((r.get(0)?, r.get(1)?))
            })?;
        require(
            epoch == self.epoch && owner == serde_json::to_string(&self.owner)?,
            "stale journal owner",
        )
    }

    fn connection(&self) -> Result<std::sync::MutexGuard<'_, Connection>> {
        self.connection
            .lock()
            .map_err(|_| StateError("journal connection poisoned".into()))
    }

    /// Admit exactly the next generation for a task. Restarts require a new claim;
    /// old intent remains unresolved even when a new generation is admitted.
    pub fn claim(
        &self,
        expected_generation: u64,
        identity: RunIdentity,
        source_revision: &str,
    ) -> Result<EventId> {
        validate_identity(&identity, self.repo_id(), source_revision)?;
        require(
            identity.generation == expected_generation.checked_add(1).unwrap_or(0),
            "claim must advance one generation",
        )?;
        let mut connection = self.connection()?;
        let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        self.verify_owner(&tx)?;
        let current: i64 = tx.query_row(
            "SELECT coalesce(max(generation),0) FROM runs WHERE task=?1",
            [&identity.task_id],
            |r| r.get(0),
        )?;
        require(
            current as u64 == expected_generation,
            "stale task generation",
        )?;
        let event = RuntimeEvent {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: identity.repo_id.clone(),
            operation_id: format!("claim/{}/{}", identity.task_id, identity.generation),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            contract_hash: identity.contract_hash.clone(),
            source_revision: source_revision.into(),
            role: identity.role,
            event: RuntimeEventKind::Accepted,
            status: RuntimeStatus::Running,
            evidence_ref: None,
            timestamp: timestamp(),
        };
        let transition = Transition {
            key: format!("claim/{}/{}", identity.task_id, identity.generation),
            identity,
            status: DurableStatus::Ready,
            event,
            kind: RecordKind::Note,
        };
        transition.event.to_json_line()?;
        let id = append(&tx, &transition)?;
        tx.execute(
            "INSERT INTO runs VALUES (?1,?2,?3,?4,?5,?6,?7)",
            params![
                transition.identity.task_id,
                transition.identity.generation as i64,
                serde_json::to_string(&transition.identity)?,
                source_revision,
                self.epoch,
                serde_json::to_string(&transition.status)?,
                id.0
            ],
        )?;
        tx.commit()?;
        Ok(id)
    }

    pub fn transition(&self, expected_generation: u64, transition: Transition) -> Result<EventId> {
        validate_identity(
            &transition.identity,
            self.repo_id(),
            &transition.event.source_revision,
        )?;
        let event = &transition.event;
        require(
            event.repo_id == transition.identity.repo_id
                && event.task_id == transition.identity.task_id
                && event.attempt_id == transition.identity.attempt_id
                && event.generation == transition.identity.generation
                && event.role == transition.identity.role
                && event.contract_hash == transition.identity.contract_hash
                && !event.operation_id.is_empty()
                && !event.timestamp.is_empty()
                && !transition.key.is_empty()
                && !transition.key.starts_with("claim/")
                && !transition.key.starts_with("reconcile/"),
            "event identity/key mismatch",
        )?;
        event.to_json_line()?;
        let mut connection = self.connection()?;
        let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        self.verify_owner(&tx)?;
        let (generation, identity, source, epoch): (i64,String,String,i64) = tx.query_row(
            "SELECT generation,identity,source,owner_epoch FROM runs WHERE task=?1 ORDER BY generation DESC LIMIT 1",
            [&transition.identity.task_id], |r| Ok((r.get(0)?,r.get(1)?,r.get(2)?,r.get(3)?)))?;
        require(
            generation as u64 == expected_generation
                && generation as u64 == transition.identity.generation
                && identity == serde_json::to_string(&transition.identity)?
                && source == event.source_revision
                && epoch == self.epoch,
            "stale generation, contract, source, attempt or owner",
        )?;
        if let Some(id) = existing(&tx, &transition)? {
            return Ok(id);
        }
        if transition.status == DurableStatus::Complete {
            let pending: bool = tx.query_row(
                "SELECT EXISTS(SELECT 1 FROM effects WHERE task=?1 AND resolution IS NULL)",
                [&event.task_id],
                |r| r.get(0),
            )?;
            require(!pending, "unresolved effects cannot be declared complete")?;
        }
        match transition.kind {
            RecordKind::Intent(_) => {
                require(
                    transition.status != DurableStatus::Complete,
                    "intent cannot complete a task",
                )?;
                let unsafe_retry: bool = tx.query_row(
                    "SELECT EXISTS(SELECT 1 FROM effects WHERE
                     (task=?1 AND resolution IS NULL) OR
                     (operation=?2 AND (resolution IS NULL OR outcome='applied')))",
                    params![event.task_id, event.operation_id],
                    |r| r.get(0),
                )?;
                require(
                    !unsafe_retry,
                    "reconcile unresolved effects; do not replay an applied operation",
                )?;
            }
            RecordKind::Completion => {
                let intent: String = tx.query_row(
                    "SELECT e.payload FROM effects f JOIN events e ON e.id=f.intent
                     WHERE f.operation=?1 AND f.generation=?2 AND f.task=?3 AND f.resolution IS NULL",
                    params![event.operation_id, generation, event.task_id], |r| r.get(0))?;
                let intent: Transition = serde_json::from_str(&intent)?;
                require(
                    intent.identity == transition.identity
                        && intent.event.source_revision == source
                        && event
                            .evidence_ref
                            .as_ref()
                            .is_some_and(|r| !r.trim().is_empty())
                        && transition.status != DurableStatus::Complete,
                    "completion needs matching intent and evidence, not task acceptance",
                )?;
            }
            RecordKind::Note => (),
        }
        let id = append(&tx, &transition)?;
        match transition.kind {
            RecordKind::Intent(_) => {
                tx.execute(
                    "INSERT INTO effects(operation,task,generation,intent) VALUES (?1,?2,?3,?4)",
                    params![event.operation_id, event.task_id, generation, id.0],
                )?;
            }
            RecordKind::Completion => {
                tx.execute("UPDATE effects SET resolution=?1,outcome='applied' WHERE operation=?2 AND generation=?3",
                params![id.0,event.operation_id,generation])?;
            }
            RecordKind::Note => (),
        }
        project(&tx, &transition, id)?;
        tx.commit()?;
        Ok(id)
    }

    /// Resolve only explicitly observed effects. Missing/unknown observations stay
    /// pending; neither a PID nor an old session is evidence of task success.
    pub fn reconcile(&self, observations: Observations) -> Result<RecoveryActions> {
        let mut connection = self.connection()?;
        let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
        self.verify_owner(&tx)?;
        for observation in observations.effects {
            validate_identity(
                &observation.identity,
                self.repo_id(),
                &observation.source_revision,
            )?;
            let generation = observation.identity.generation as i64;
            let payload: String = tx.query_row(
                "SELECT e.payload FROM effects f JOIN events e ON e.id=f.intent
                 WHERE f.operation=?1 AND f.generation=?2 AND f.task=?3",
                params![
                    observation.operation_id,
                    generation,
                    observation.identity.task_id
                ],
                |r| r.get(0),
            )?;
            let mut transition: Transition = serde_json::from_str(&payload)?;
            require(
                transition.identity == observation.identity
                    && transition.event.source_revision == observation.source_revision
                    && !observation.evidence_ref.trim().is_empty(),
                "observation identity/source/evidence mismatch",
            )?;
            if observation.outcome == EffectOutcome::Unknown {
                continue;
            }
            let (resolution, outcome): (Option<i64>, Option<String>) = tx.query_row(
                "SELECT resolution,outcome FROM effects WHERE operation=?1 AND generation=?2",
                params![observation.operation_id, generation],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )?;
            let outcome_text = match observation.outcome {
                EffectOutcome::Applied => "applied",
                EffectOutcome::Absent => "absent",
                EffectOutcome::Unknown => unreachable!(),
            };
            if resolution.is_some() {
                require(
                    outcome.as_deref() == Some(outcome_text),
                    "conflicting effect observation",
                )?;
                continue;
            }
            transition.key = format!(
                "reconcile/{}/{}",
                observation.operation_id, observation.identity.generation
            );
            transition.kind = RecordKind::Completion;
            transition.status = DurableStatus::Uncertain;
            transition.event.event = RuntimeEventKind::Outcome;
            transition.event.status = RuntimeStatus::Unavailable;
            transition.event.evidence_ref = Some(observation.evidence_ref);
            transition.event.timestamp = timestamp();
            transition.event.to_json_line()?;
            let id = append(&tx, &transition)?;
            tx.execute(
                "UPDATE effects SET resolution=?1,outcome=?2 WHERE operation=?3 AND generation=?4",
                params![id.0, outcome_text, observation.operation_id, generation],
            )?;
            project(&tx, &transition, id)?;
        }
        let mut actions = RecoveryActions::default();
        {
            let mut statement = tx.prepare(
                "SELECT i.payload,f.outcome,r.payload FROM effects f JOIN events i ON i.id=f.intent
                 LEFT JOIN events r ON r.id=f.resolution ORDER BY i.id",
            )?;
            let rows = statement.query_map([], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, Option<String>>(1)?,
                    r.get::<_, Option<String>>(2)?,
                ))
            })?;
            for row in rows {
                let (intent, outcome, resolution) = row?;
                let intent: Transition = serde_json::from_str(&intent)?;
                if let (Some(outcome), Some(resolution)) = (outcome, resolution) {
                    let resolution: Transition = serde_json::from_str(&resolution)?;
                    actions.resolved.push(RecoveredOperation {
                        identity: intent.identity,
                        operation_id: intent.event.operation_id,
                        outcome: if outcome == "applied" {
                            EffectOutcome::Applied
                        } else {
                            EffectOutcome::Absent
                        },
                        evidence_ref: resolution.event.evidence_ref.unwrap_or_default(),
                    });
                } else {
                    actions
                        .reconcile_operation_ids
                        .push(intent.event.operation_id);
                }
            }
        }
        tx.commit()?;
        Ok(actions)
    }

    pub fn projection(&self, task: &str, generation: u64) -> Result<Projection> {
        let connection = self.connection()?;
        let (identity, source, status, id): (String, String, String, i64) = connection.query_row(
            "SELECT identity,source,status,event_id FROM runs WHERE task=?1 AND generation=?2",
            params![
                task,
                i64::try_from(generation).map_err(|_| StateError("generation overflow".into()))?
            ],
            |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?)),
        )?;
        Ok(Projection {
            identity: serde_json::from_str(&identity)?,
            source_revision: source,
            status: serde_json::from_str(&status)?,
            event_id: EventId(id),
        })
    }
    pub fn events(&self) -> Result<Vec<(EventId, Transition)>> {
        let connection = self.connection()?;
        let mut statement = connection.prepare("SELECT id,payload FROM events ORDER BY id")?;
        let rows =
            statement.query_map([], |r| Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?)))?;
        rows.map(|row| {
            let (id, payload) = row?;
            Ok((EventId(id), serde_json::from_str(&payload)?))
        })
        .collect()
    }
}

fn validate_identity(identity: &RunIdentity, repo: &str, source: &str) -> Result<()> {
    require(
        identity.repo_id == repo
            && !identity.task_id.is_empty()
            && !identity.attempt_id.is_empty()
            && !identity.contract_hash.is_empty()
            && !source.is_empty()
            && identity.generation > 0
            && identity.generation <= i64::MAX as u64,
        "invalid journal identity/source",
    )
}
fn existing(connection: &Connection, transition: &Transition) -> Result<Option<EventId>> {
    let row: Option<(i64, String)> = connection
        .query_row(
            "SELECT id,payload FROM events WHERE key=?1",
            [&transition.key],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .optional()?;
    if let Some((id, payload)) = row {
        require(
            payload == serde_json::to_string(transition)?,
            "operation key reused with different content",
        )?;
        Ok(Some(EventId(id)))
    } else {
        Ok(None)
    }
}
fn append(connection: &Connection, transition: &Transition) -> Result<EventId> {
    connection.execute(
        "INSERT INTO events(key,payload) VALUES (?1,?2)",
        params![transition.key, serde_json::to_string(transition)?],
    )?;
    Ok(EventId(connection.last_insert_rowid()))
}
fn project(connection: &Connection, transition: &Transition, id: EventId) -> Result<()> {
    require(
        connection.execute(
            "UPDATE runs SET status=?1,event_id=?2 WHERE task=?3 AND generation=?4",
            params![
                serde_json::to_string(&transition.status)?,
                id.0,
                transition.identity.task_id,
                transition.identity.generation as i64
            ],
        )? == 1,
        "missing run projection",
    )
}
fn timestamp() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .to_string()
}
fn private_path(path: &Path, directory: bool) -> Result<()> {
    let meta = fs::symlink_metadata(path)?;
    require(
        (if directory {
            meta.is_dir()
        } else {
            meta.is_file() && meta.nlink() == 1
        }) && meta.mode() & 0o077 == 0
            && meta.uid() == fs::metadata("/proc/self")?.uid(),
        "journal paths must be private, owned and not aliases",
    )
}
fn private_file(path: &Path) -> Result<File> {
    let file = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(0x20000 /* Linux O_NOFOLLOW */)
        .open(path)?;
    private_path(path, false)?;
    Ok(file)
}

// Fail closed for network, FUSE and unrecognized filesystems, before enabling WAL.
fn require_local(path: &Path) -> Result<()> {
    let mounts = fs::read_to_string("/proc/self/mountinfo")?;
    let mut selected = None;
    for line in mounts.lines() {
        let Some((fields, tail)) = line.split_once(" - ") else {
            continue;
        };
        let Some(mount) = fields.split_whitespace().nth(4) else {
            continue;
        };
        let mount = mount
            .replace("\\040", " ")
            .replace("\\011", "\t")
            .replace("\\012", "\n")
            .replace("\\134", "\\");
        if path.starts_with(&mount)
            && selected
                .as_ref()
                .is_none_or(|(length, _)| mount.len() >= *length)
        {
            selected = Some((mount.len(), tail.split_whitespace().next().unwrap_or("")));
        }
    }
    require(
        selected.is_some_and(|(_, kind)| {
            matches!(
                kind,
                "ext2" | "ext3" | "ext4" | "xfs" | "btrfs" | "zfs" | "tmpfs" | "overlay"
            )
        }),
        "journal WAL requires a verified local filesystem",
    )
}

/// Public history and inspection latest projections use the same validated read transaction.
pub fn read_persisted_runs(common_dir: impl AsRef<Path>) -> Result<serde_json::Value> {
    let (snapshot, runs) =
        read_snapshot(common_dir.as_ref()).map_err(|error| StateError(error.code().into()))?;
    require(snapshot.journal_state == "present", "journal absent")?;
    Ok(serde_json::json!({"status":"observed", "runs":runs, "qualification":"persisted-only"}))
}
