//! Sole coordinator loop: serialized local delivery, checks, review and recovery.
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
use std::path::{Component, Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::planning::{
    FailureEvidence, PlanOutcome, Planner, PlanningContext, RecordChange,
};
use crate::runtime::{
    AgentRequest, CheckOperationSpec, ExecutionAdmission, Role, Runtime, RuntimeEvent,
    RuntimeEventKind, RuntimeStatus, WorkspaceIdentity, native_agent, native_ai,
};
use crate::state::{
    DurableStatus, EffectKind, RecordKind, StateStore, Transition,
};
use crate::task_store::{
    CommittedRevision, PendingSnapshot, Record, Scope, Snapshot, TaskService, TaskStore,
};
use crate::{Result, Unavailable};

pub const FIXTURE_SOURCE_REVISION: &str = "autowork-cycle-fixture-v1";
const PUBLICATION_SCHEMA: u32 = 1;
const MAX_AGENT_TRANSCRIPT: u64 = 4 * 1024 * 1024;

#[derive(Clone, Debug, Serialize)]
pub struct RunSummary {
    pub completed_task_ids: Vec<String>,
    pub pending_task_ids: Vec<String>,
    pub evidence_refs: Vec<String>,
    /// External waits are not owner decisions.
    pub waiting_external: Vec<String>,
    /// Owner-help states are reported separately from ordinary pending work.
    pub waiting_sudo: Vec<String>,
    pub waiting_credential: Vec<String>,
    pub paused: bool,
    pub limit_reached: Option<String>,
    pub reason: String,
}

impl Default for RunSummary {
    fn default() -> Self {
        Self {
            completed_task_ids: Vec::new(),
            pending_task_ids: Vec::new(),
            evidence_refs: Vec::new(),
            waiting_external: Vec::new(),
            waiting_sudo: Vec::new(),
            waiting_credential: Vec::new(),
            paused: false,
            limit_reached: None,
            reason: "quiescent".into(),
        }
    }
}

#[derive(Clone, Debug, Default)]
pub struct CycleLimits {
    pub max_tasks: Option<usize>,
    /// A user stop or pause wins before dispatch and creates no new work.
    pub paused: bool,
    /// Do not publish task edits locally; retain them as pending, not selectable.
    pub no_commit: bool,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CrashPoint {
    AfterPublicationIntent,
    AfterPublicationCommit,
    AfterIntegrationRef,
}

#[derive(Clone, Debug, Default)]
pub struct CheckRegistry {
    specs: BTreeMap<String, CheckOperationSpec>,
    accepted_sources: BTreeSet<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct CheckReceipt {
    pub schema: u32,
    pub operation_id: String,
    pub task_id: String,
    pub source_revision: String,
    pub executable_sha256: String,
    pub argv: Vec<String>,
    pub cwd: PathBuf,
    pub passed: bool,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub output_sha256: String,
    pub output_bytes: u64,
    pub output_truncated: bool,
    pub receipt_id: String,
}

impl CheckRegistry {
    pub fn new<I, S>(accepted_sources: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        Self {
            specs: BTreeMap::new(),
            accepted_sources: accepted_sources.into_iter().map(Into::into).collect(),
        }
    }

    pub fn accept_source(&mut self, source: impl Into<String>) {
        self.accepted_sources.insert(source.into());
    }

    pub fn insert(&mut self, spec: CheckOperationSpec) -> Result<()> {
        if !valid_operation_id(&spec.operation_id)
            || !spec.executable.is_absolute()
            || !spec.cwd.is_absolute()
            || spec.argv.is_empty()
            || spec.timeout_ms == 0
            || spec.max_output_bytes == 0
            || !spec.executable_sha256.bytes().all(|b| b.is_ascii_hexdigit())
            || spec.executable_sha256.len() != 64
            || spec.receipt_id.trim().is_empty()
            || !self.accepted_sources.contains(&spec.source_revision)
        {
            return Err(Unavailable("check operation rejected"));
        }
        let actual = sha256_file(&spec.executable)?;
        if actual != spec.executable_sha256 {
            return Err(Unavailable("check executable identity drifted"));
        }
        if self.specs.insert(spec.operation_id.clone(), spec).is_some() {
            return Err(Unavailable("duplicate check operation"));
        }
        Ok(())
    }

    pub fn operation_ids(&self) -> impl Iterator<Item = &str> {
        self.specs.keys().map(String::as_str)
    }

    /// Task check notes are operation IDs only, never shell text or argv.
    pub fn for_task(&self, task: &Record) -> Result<Vec<CheckOperationSpec>> {
        let mut selected = Vec::new();
        for name in task.strings("checks") {
            let Some(spec) = self.specs.get(name) else {
                return Err(Unavailable("unknown check operation"));
            };
            selected.push(spec.clone());
        }
        Ok(selected)
    }

    fn verify(&self, spec: &CheckOperationSpec) -> Result<()> {
        if !self.accepted_sources.contains(&spec.source_revision)
            || sha256_file(&spec.executable)? != spec.executable_sha256
        {
            return Err(Unavailable("check executable or source identity drifted"));
        }
        Ok(())
    }

    pub fn run(
        &self,
        receipt_dir: &Path,
        task_id: &str,
        source_revision: &str,
        spec: &CheckOperationSpec,
    ) -> Result<CheckReceipt> {
        self.verify(spec)?;
        fs::create_dir_all(receipt_dir)?;
        let tag = format!(
            "{}-{}",
            safe_fragment(&spec.operation_id),
            safe_fragment(task_id)
        );
        let out_path = receipt_dir.join(format!(".{tag}.out.tmp"));
        let err_path = receipt_dir.join(format!(".{tag}.err.tmp"));
        for path in [&out_path, &err_path] {
            match fs::remove_file(path) {
                Ok(()) => (),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                Err(e) => return Err(Unavailable(Box::leak(e.to_string().into_boxed_str()))),
            }
        }
        let stdout = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&out_path)?;
        let stderr = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&err_path)?;
        let mut command = Command::new(&spec.executable);
        command
            .args(&spec.argv)
            .current_dir(&spec.cwd)
            .env_clear()
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr));
        for (key, value) in &spec.environment_allowlist {
            command.env(key, value);
        }
        let mut child = command.spawn().map_err(|_| Unavailable("check executable failed"))?;
        let deadline = Instant::now() + Duration::from_millis(spec.timeout_ms);
        let mut timed_out = false;
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break status,
                Ok(None) if Instant::now() < deadline => {
                    std::thread::sleep(Duration::from_millis(5));
                }
                Ok(None) => {
                    timed_out = true;
                    let _ = child.kill();
                    break child
                        .wait()
                        .map_err(|_| Unavailable("check reap failed"))?;
                }
                Err(_) => return Err(Unavailable("check wait failed")),
            }
        };
        let mut output = fs::read(&out_path)?;
        output.extend_from_slice(&fs::read(&err_path)?);
        let _ = fs::remove_file(&out_path);
        let _ = fs::remove_file(&err_path);
        let limit = spec.max_output_bytes as usize;
        let truncated = output.len() > limit;
        output.truncate(limit);
        let output_sha256 = sha256(&output)?;
        let passed = status.success() && !timed_out && !truncated;
        let mut receipt = CheckReceipt {
            schema: 1,
            operation_id: spec.operation_id.clone(),
            task_id: task_id.into(),
            source_revision: source_revision.into(),
            executable_sha256: spec.executable_sha256.clone(),
            argv: spec.argv.clone(),
            cwd: spec.cwd.clone(),
            passed,
            exit_code: status.code(),
            timed_out,
            output_sha256,
            output_bytes: output.len() as u64,
            output_truncated: truncated,
            receipt_id: String::new(),
        };
        let unsigned = serde_json::to_vec(&receipt)
            .map_err(|_| Unavailable("check receipt serialization"))?;
        receipt.receipt_id = sha256(&unsigned)?;
        let bytes = serde_json::to_vec(&receipt)
            .map_err(|_| Unavailable("check receipt serialization"))?;
        let path = receipt_dir.join(format!("{}.json", receipt.receipt_id));
        atomic_bytes(&path, &bytes)?;
        Ok(receipt)
    }
}

fn valid_operation_id(id: &str) -> bool {
    !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"._:-/".contains(&b))
}

fn safe_fragment(value: &str) -> String {
    value
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect()
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct PublicationJournal {
    schema: u32,
    operation_id: String,
    token: String,
    base_head: String,
    branch: String,
    tree: String,
    committed: Option<String>,
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct IntegrationJournal {
    schema: u32,
    task_id: String,
    generation: u64,
    base_head: String,
    candidate: String,
    integration: String,
    tree: String,
    check_refs: Vec<String>,
    review_ref: String,
}

/// Coordinator owns the services; tests and the CLI supply explicit limits.
pub struct Coordinator {
    repo: PathBuf,
    service: TaskService,
    state: StateStore,
    runtime: Runtime,
    model_ref: String,
    checks: CheckRegistry,
    limits: CycleLimits,
    crash: Option<CrashPoint>,
}

impl Coordinator {
    pub fn new(
        repo: impl AsRef<Path>,
        runtime: Runtime,
        model_ref: impl Into<String>,
        checks: CheckRegistry,
        limits: CycleLimits,
    ) -> Result<Self> {
        let repo = fs::canonicalize(repo)?;
        let service = TaskService::new(&repo)?;
        let common = PathBuf::from(git_text(&repo, &["rev-parse", "--absolute-git-dir"])?);
        let state = StateStore::open(&common)?;
        let model_ref = model_ref.into();
        if model_ref.is_empty() {
            return Err(Unavailable("coordinator model reference"));
        }
        Ok(Self {
            repo,
            service,
            state,
            runtime,
            model_ref,
            checks,
            limits,
            crash: None,
        })
    }

    #[doc(hidden)]
    pub fn with_crash_point(mut self, crash: CrashPoint) -> Self {
        self.crash = Some(crash);
        self
    }

    pub async fn run_until_quiescent(&self, scope: Scope) -> Result<RunSummary> {
        let mut summary = RunSummary::default();
        self.service.recover()?;
        self.recover_publication()?;
        self.recover_integration()?;
        if self.limits.paused {
            summary.paused = true;
            summary.reason = "paused".into();
            return Ok(summary);
        }
        let mut attempted = BTreeSet::new();
        let mut planned = BTreeSet::new();
        loop {
            if let Some(max) = self.limits.max_tasks
                && summary.completed_task_ids.len() >= max
            {
                summary.limit_reached = Some(format!("completed {max} task(s)"));
                summary.reason = "task limit reached".into();
                return Ok(summary);
            }
            let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
            let selection = snapshot.select(&scope)?;
            let Some(id) = selection.task_ids.iter().find(|id| !attempted.contains(*id)) else {
                // A blocked queue may still have a routine planning decision available.
                if let Some((blocked_id, reason)) = selection
                    .blocked
                    .iter()
                    .find(|(id, _)| !attempted.contains(*id) && !planned.contains(*id))
                {
                    attempted.insert(blocked_id.clone());
                    planned.insert(blocked_id.clone());
                    match self
                        .replan(
                            &snapshot,
                            blocked_id,
                            FailureEvidence {
                                operation_id: format!("queue/{}", reason.code),
                                fingerprint: format!("{}:{}", reason.code, reason.detail),
                                evidence_refs: vec![format!("selection:{}", reason.code)],
                            },
                        )
                        .await?
                    {
                        PlanDispositionResult::WaitingExternal(id) => {
                            summary.waiting_external.push(id)
                        }
                        PlanDispositionResult::WaitingSudo(id) => summary.waiting_sudo.push(id),
                        PlanDispositionResult::WaitingCredential(id) => {
                            summary.waiting_credential.push(id)
                        }
                        PlanDispositionResult::Pending(id) => {
                            summary.pending_task_ids.push(id);
                            if self.limits.no_commit {
                                summary.limit_reached = Some("no-commit publication limit".into());
                                summary.reason = "pending task edits retained; not selectable".into();
                                return Ok(summary);
                            }
                        }
                        PlanDispositionResult::NoChange => (),
                    }
                    continue;
                }
                summary.pending_task_ids.extend(
                    selection
                        .blocked
                        .keys()
                        .filter(|id| !summary.completed_task_ids.contains(*id))
                        .cloned(),
                );
                summary.reason = if summary.waiting_external.is_empty()
                    && summary.waiting_sudo.is_empty()
                    && summary.waiting_credential.is_empty()
                {
                    "no eligible work".into()
                } else {
                    "waiting for external or owner input".into()
                };
                return Ok(summary);
            };
            let id = id.clone();
            attempted.insert(id.clone());
            let task = snapshot.tasks()[&id].clone();
            match self.run_task(&snapshot, &task).await? {
                TaskResult::Completed(receipts) => {
                    summary.completed_task_ids.push(id);
                    summary.evidence_refs.extend(receipts);
                }
                TaskResult::Failed { reason, evidence } => {
                    summary.pending_task_ids.push(id.clone());
                    summary.evidence_refs.extend(evidence);
                    summary.reason = reason;
                }
            }
        }
    }

    /// Publish an exact pending task edit snapshot through a private index.
    /// The real index and unrelated dirty/staged bytes are never rewritten.
    pub fn commit_proposal(&self, snapshot: PendingSnapshot) -> Result<CommittedRevision> {
        let expected_token = pending_token(&snapshot)?;
        if snapshot.token != expected_token {
            return Err(Unavailable("publication token mismatch"));
        }
        let journal_path = self.publication_path();
        if let Some(journal) = read_json::<PublicationJournal>(&journal_path)? {
            if journal.schema != PUBLICATION_SCHEMA || journal.token != snapshot.token {
                return Err(Unavailable("publication journal mismatch"));
            }
            return self.settle_publication(journal, &journal_path);
        }
        if git_text(&self.repo, &["rev-parse", "--verify", "HEAD^{commit}"])? != snapshot.base_head
            || git_text(&self.repo, &["symbolic-ref", "--quiet", "HEAD"])? != snapshot.branch
        {
            return Err(Unavailable("publication base changed"));
        }
        let current = fs::canonicalize(&self.repo)?;
        if self.service.capture_pending()?.token != snapshot.token || current != self.repo {
            return Err(Unavailable("publication working tree changed"));
        }
        let journal = PublicationJournal {
            schema: PUBLICATION_SCHEMA,
            operation_id: format!("publication/{}", snapshot.token),
            token: snapshot.token.clone(),
            base_head: snapshot.base_head.clone(),
            branch: snapshot.branch.clone(),
            tree: snapshot.tree.clone(),
            committed: None,
        };
        write_json_atomic(&journal_path, &journal)?;
        if self.crash == Some(CrashPoint::AfterPublicationIntent) {
            return Err(Unavailable("injected publication interruption"));
        }
        self.settle_publication(journal, &journal_path)
    }

    /// Reconcile a retained publication intent before any new selection.
    pub fn recover_publication(&self) -> Result<Option<CommittedRevision>> {
        let path = self.publication_path();
        let Some(journal) = read_json::<PublicationJournal>(&path)? else {
            return Ok(None);
        };
        if journal.schema != PUBLICATION_SCHEMA {
            return Err(Unavailable("unsupported publication journal"));
        }
        self.settle_publication(journal, &path).map(Some)
    }

    fn publication_path(&self) -> PathBuf {
        self.state.directory().join("publication.json")
    }

    fn integration_path(&self) -> PathBuf {
        self.state.directory().join("integration.json")
    }

    fn settle_publication(
        &self,
        mut journal: PublicationJournal,
        path: &Path,
    ) -> Result<CommittedRevision> {
        if let Some(committed) = &journal.committed {
            verify_commit(&self.repo, committed)?;
            return Ok(CommittedRevision(committed.clone()));
        }
        let head = git_text(&self.repo, &["rev-parse", "--verify", "HEAD^{commit}"])?;
        if head != journal.base_head {
            if commit_tree(&self.repo, &head)? == journal.tree
                && commit_parents(&self.repo, &head)? == vec![journal.base_head.clone()]
            {
                journal.committed = Some(head.clone());
                write_json_atomic(path, &journal)?;
                return Ok(CommittedRevision(head));
            }
            return Err(Unavailable("publication head moved unexpectedly"));
        }
        if git_text(&self.repo, &["symbolic-ref", "--quiet", "HEAD"])? != journal.branch {
            return Err(Unavailable("publication branch changed"));
        }
        let commit = self.commit_index_tree(&journal.tree, &journal.operation_id)?;
        if commit == journal.base_head {
            return Err(Unavailable("publication made no commit"));
        }
        if self.crash == Some(CrashPoint::AfterPublicationCommit) {
            return Err(Unavailable("injected publication interruption"));
        }
        journal.committed = Some(commit.clone());
        write_json_atomic(path, &journal)?;
        Ok(CommittedRevision(commit))
    }

    fn commit_index_tree(&self, tree: &str, operation_id: &str) -> Result<String> {
        let scratch = self.state.directory().join(format!(".publication-index-{}", std::process::id()));
        let _ = fs::remove_file(&scratch);
        let _ = fs::remove_file(scratch.with_extension("lock"));
        git_env(&self.repo, &["read-tree", tree], &[], Some(&scratch))?;
        let message = format!("autowork: publish task records ({operation_id})");
        git_env(
            &self.repo,
            &["commit", "--no-gpg-sign", "-m", &message],
            &[],
            Some(&scratch),
        )?;
        let _ = fs::remove_file(&scratch);
        let _ = fs::remove_file(scratch.with_extension("lock"));
        git_text(&self.repo, &["rev-parse", "--verify", "HEAD^{commit}"])
    }

    fn recover_integration(&self) -> Result<()> {
        let path = self.integration_path();
        let Some(journal) = read_json::<IntegrationJournal>(&path)? else {
            return Ok(());
        };
        if journal.schema != PUBLICATION_SCHEMA {
            return Err(Unavailable("unsupported integration journal"));
        }
        let head = git_text(&self.repo, &["rev-parse", "--verify", "HEAD^{commit}"])?;
        if head == journal.base_head {
            git(
                &self.repo,
                &[
                    "update-ref",
                    &format!("refs/heads/{}", branch_name(&journal.base_head, &self.repo)?),
                    &journal.integration,
                    &journal.base_head,
                ],
            )?;
        }
        Err(Unavailable("interrupted Git integration requires operator reconciliation"))
    }

    async fn run_task(&self, snapshot: &Snapshot, task: &Record) -> Result<TaskResult> {
        let checks = match self.checks.for_task(task) {
            Ok(checks) => checks,
            Err(error) => return Ok(TaskResult::Failed {
                reason: "unsupported required check; planning required".into(),
                evidence: vec![error.to_string()],
            }),
        };
        if checks.is_empty() && !task.strings("checks").is_empty() {
            return Ok(TaskResult::Failed {
                reason: "unsupported required check; planning required".into(),
                evidence: vec![],
            });
        }
        let generation = next_generation(&self.state, &task.id)?;
        let attempt_id = format!("cycle-{}-{generation}", task.id);
        let identity = crate::runtime::RunIdentity {
            repo_id: self.state.repo_id().into(),
            task_id: task.id.clone(),
            attempt_id: attempt_id.clone(),
            generation,
            role: Role::Worker,
            contract_hash: task.contract_hash.clone(),
        };
        self.state
            .claim(generation.saturating_sub(1), identity.clone(), snapshot.revision())?;
        let candidate = self.create_candidate(&task.id, generation, snapshot.revision())?;
        let allowed = task
            .strings("touches")
            .into_iter()
            .filter_map(|p| normalized_relative(Path::new(p)).then(|| PathBuf::from(p)))
            .collect::<Vec<_>>();
        let worker = self
            .run_owned(
                identity.clone(),
                Role::Worker,
                &candidate,
                snapshot.revision(),
                format!(
                    "AUTOWORK_TASK={};AUTOWORK_ROLE=worker\nImplement the accepted task exactly. Do not edit tasks/, BLOCKERS.md, CHANGELOG.md, TODO.archive.md or .git. Use only allowed workspace paths.",
                    task.id
                ),
                allowed.clone(),
                checks
                    .iter()
                    .map(|s| s.operation_id.clone())
                    .collect(),
                checks.clone(),
            )
            .await?;
        if worker.status != RuntimeStatus::Succeeded {
            let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
            return Ok(TaskResult::Failed {
                reason: "worker did not succeed".into(),
                evidence: vec![worker.evidence_ref],
            });
        }
        let changed = worktree_changes(&candidate)?;
        if changed.is_empty() || changed.iter().any(|p| protected_path(p)) {
            let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
            return Ok(TaskResult::Failed {
                reason: "worker candidate is empty or protected".into(),
                evidence: changed,
            });
        }
        if !allowed.is_empty() && changed.iter().any(|p| !allowed.contains(&PathBuf::from(p))) {
            let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
            return Ok(TaskResult::Failed {
                reason: "worker wrote outside admitted paths".into(),
                evidence: changed,
            });
        }
        let candidate_commit = commit_worktree(&candidate, &format!("autowork candidate {}", task.id))?;
        let candidate_tree = commit_tree(&self.repo, &candidate_commit)?;
        let receipt_dir = self
            .state
            .directory()
            .join("checks")
            .join(safe_fragment(&task.id));
        let mut check_refs = Vec::new();
        for spec in &checks {
            let receipt = self.checks.run(
                &receipt_dir,
                &task.id,
                snapshot.revision(),
                spec,
            )?;
            if !receipt.passed {
                let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
                return Ok(TaskResult::Failed {
                    reason: format!("check failed: {}", receipt.operation_id),
                    evidence: vec![format!("check:{}", receipt.receipt_id)],
                });
            }
            check_refs.push(format!("check:{}", receipt.receipt_id));
        }
        let mut review_identity = identity.clone();
        review_identity.role = Role::Reviewer;
        let review = self
            .run_owned(
                review_identity,
                Role::Reviewer,
                &candidate,
                snapshot.revision(),
                format!(
                    "AUTOWORK_TASK={};AUTOWORK_ROLE=reviewer\nReview candidate {candidate_commit} for the accepted task. Respond only with strict JSON {{\"verdict\":\"passed|rejected\",\"evidence\":\"nonempty\"}}.",
                    task.id
                ),
                vec![],
                vec![],
                vec![],
            )
            .await?;
        let verdict = review_verdict(&review.text);
        if review.status != RuntimeStatus::Succeeded || verdict.is_none() {
            let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
            return Ok(TaskResult::Failed {
                reason: "independent review did not pass".into(),
                evidence: vec![review.evidence_ref],
            });
        }
        let integration = integrate_candidate(
            &self.repo,
            snapshot.revision(),
            &candidate_commit,
            &candidate_tree,
            &task.id,
        )?;
        let integration_tree = commit_tree(&self.repo, &integration)?;
        let journal = IntegrationJournal {
            schema: PUBLICATION_SCHEMA,
            task_id: task.id.clone(),
            generation,
            base_head: snapshot.revision().into(),
            candidate: candidate_commit.clone(),
            integration: integration.clone(),
            tree: integration_tree.clone(),
            check_refs: check_refs.clone(),
            review_ref: review.evidence_ref.clone(),
        };
        write_json_atomic(&self.integration_path(), &journal)?;
        if self.crash == Some(CrashPoint::AfterIntegrationRef) {
            return Err(Unavailable("injected integration interruption"));
        }
        let closure = self.close_task(
            task,
            &candidate_commit,
            &integration,
            &integration_tree,
            &check_refs,
            &review.evidence_ref,
        )?;
        let _ = fs::remove_file(self.integration_path());
        let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
        self.complete_state(identity, &closure)?;
        let mut evidence = check_refs;
        evidence.push(review.evidence_ref);
        evidence.push(format!("integration:{integration}"));
        evidence.push(format!("revision:{}", closure.0));
        Ok(TaskResult::Completed(evidence))
    }

    fn close_task(
        &self,
        task: &Record,
        candidate: &str,
        integration: &str,
        tree: &str,
        check_refs: &[String],
        review_ref: &str,
    ) -> Result<CommittedRevision> {
        let snapshot = TaskStore::read_at(&self.repo, "HEAD")?;
        let current = snapshot
            .records()
            .get(&task.path)
            .ok_or(Unavailable("closure record missing"))?;
        let closed = close_record(task, current)?;
        let evidence_path = format!("tasks/evidence/{}.toml", task.id);
        let evidence = closure_receipt(
            task,
            candidate,
            integration,
            tree,
            check_refs,
            review_ref,
        );
        let changes = vec![
            RecordChange {
                path: task.path.clone().into(),
                expected_revision: sha256(current)?,
                proposed_bytes: closed,
            },
            RecordChange {
                path: evidence_path.into(),
                expected_revision: String::new(),
                proposed_bytes: evidence.into_bytes(),
            },
        ];
        self.service.apply_coordinator(snapshot.revision(), &changes)?;
        let pending = self.service.capture_pending()?;
        self.commit_proposal(pending)
    }

    fn complete_state(&self, identity: crate::runtime::RunIdentity, revision: &CommittedRevision) -> Result<()> {
        let event = RuntimeEvent {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: identity.repo_id.clone(),
            operation_id: format!("complete/{}", identity.task_id),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            contract_hash: identity.contract_hash.clone(),
            source_revision: revision.0.clone(),
            role: identity.role,
            event: RuntimeEventKind::Outcome,
            status: RuntimeStatus::Succeeded,
            evidence_ref: Some(format!("integration:{}", revision.0)),
            timestamp: now_text(),
        };
        // Completion events retain the claimed source binding; the closure commit is evidence.
        self.state.transition(
            identity.generation,
            Transition {
                key: format!("complete/{}/{}", identity.task_id, identity.generation),
                identity,
                status: DurableStatus::Complete,
                event: RuntimeEvent {
                    source_revision: {
                        let events = self.state.events()?;
                        events
                            .iter()
                            .find(|(_, t)| {
                                t.identity.task_id == event.task_id
                                    && t.identity.generation == event.generation
                            })
                            .map(|(_, t)| t.event.source_revision.clone())
                            .unwrap_or(event.source_revision.clone())
                    },
                    ..event
                },
                kind: RecordKind::Note,
            },
        )?;
        Ok(())
    }

    fn create_candidate(&self, task: &str, generation: u64, base: &str) -> Result<PathBuf> {
        let root = self.state.directory().join("candidates");
        fs::create_dir_all(&root)?;
        let candidate = root.join(format!(
            "{}-{}-{}",
            safe_fragment(task),
            generation,
            std::process::id()
        ));
        if candidate.exists() {
            let _ = git(&self.repo, &["worktree", "remove", "--force", path(&candidate)]);
        }
        git(
            &self.repo,
            &[
                "worktree",
                "add",
                "--detach",
                path(&candidate),
                base,
            ],
        )?;
        Ok(candidate)
    }

    #[allow(clippy::too_many_arguments)]
    async fn run_owned(
        &self,
        identity: crate::runtime::RunIdentity,
        role: Role,
        workspace: &Path,
        source_revision: &str,
        prompt: String,
        allowed: Vec<PathBuf>,
        admitted_checks: Vec<String>,
        check_operations: Vec<CheckOperationSpec>,
    ) -> Result<AgentReport> {
        let meta = fs::metadata(workspace)?;
        let workspace_identity = WorkspaceIdentity {
            canonical_path: fs::canonicalize(workspace)?,
            device: meta.dev(),
            inode: meta.ino(),
        };
        let request = AgentRequest {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: identity.repo_id.clone(),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            role,
            workspace: workspace_identity.canonical_path.clone(),
            model_ref: self.model_ref.clone(),
            contract_hash: identity.contract_hash.clone(),
            source_revision: source_revision.into(),
            prompt,
            admission: ExecutionAdmission {
                repo_id: identity.repo_id.clone(),
                repository: workspace_identity.clone(),
                workspace: workspace_identity,
                task_id: identity.task_id.clone(),
                attempt_id: identity.attempt_id.clone(),
                generation: identity.generation,
                contract_hash: identity.contract_hash.clone(),
                role,
                allowed_write_paths: allowed,
                denied_paths: vec![],
                admitted_check_operation_ids: admitted_checks,
            },
            check_operations,
        };
        let operation = format!("owned/{}/{}/{:?}", identity.task_id, identity.generation, role);
        let intent_event = RuntimeEvent {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: identity.repo_id.clone(),
            operation_id: operation.clone(),
            task_id: identity.task_id.clone(),
            attempt_id: identity.attempt_id.clone(),
            generation: identity.generation,
            contract_hash: identity.contract_hash.clone(),
            source_revision: source_revision.into(),
            role,
            event: RuntimeEventKind::Accepted,
            status: RuntimeStatus::Running,
            evidence_ref: Some(operation.clone()),
            timestamp: now_text(),
        };
        self.state.transition(
            identity.generation,
            Transition {
                key: format!("{operation}/intent"),
                identity: identity.clone(),
                status: DurableStatus::Executing,
                event: intent_event.clone(),
                kind: RecordKind::Intent(EffectKind::Child),
            },
        )?;
        let mut events = self.runtime.run(request).await?;
        let mut terminal = None;
        while let Some(event) = events.recv().await {
            if event.event == RuntimeEventKind::Outcome {
                terminal = Some(event.status);
            }
        }
        let status = terminal.ok_or(Unavailable("owned agent missing outcome"))?;
        let owned = self
            .runtime
            .owned_process(&identity)
            .ok_or(Unavailable("owned agent evidence missing"))?;
        let text = session_text(&owned.evidence_dir).unwrap_or_default();
        let mut completion = intent_event;
        completion.event = RuntimeEventKind::Outcome;
        completion.status = status;
        completion.evidence_ref = Some(operation.clone());
        completion.timestamp = now_text();
        self.state.transition(
            identity.generation,
            Transition {
                key: format!("{operation}/complete"),
                identity,
                status: DurableStatus::Checking,
                event: completion,
                kind: RecordKind::Completion,
            },
        )?;
        Ok(AgentReport {
            status,
            text,
            evidence_ref: format!("owned:{}", owned.evidence_dir.display()),
        })
    }

    async fn replan(
        &self,
        snapshot: &Snapshot,
        task_id: &str,
        failure: FailureEvidence,
    ) -> Result<PlanDispositionResult> {
        let Some(task) = snapshot.tasks().get(task_id) else {
            return Ok(PlanDispositionResult::NoChange);
        };
        let generation = next_generation(&self.state, task_id)?;
        let attempt_id = format!("planner-{task_id}-{generation}");
        let identity = crate::runtime::RunIdentity {
            repo_id: self.state.repo_id().into(),
            task_id: task_id.into(),
            attempt_id: attempt_id.clone(),
            generation,
            role: Role::Planner,
            contract_hash: task.contract_hash.clone(),
        };
        self.state
            .claim(generation.saturating_sub(1), identity.clone(), snapshot.revision())?;
        let meta = fs::metadata(&self.repo)?;
        let workspace = WorkspaceIdentity {
            canonical_path: self.repo.clone(),
            device: meta.dev(),
            inode: meta.ino(),
        };
        let request = AgentRequest {
            schema_version: crate::CONTRACT_VERSION,
            repo_id: identity.repo_id.clone(),
            task_id: task_id.into(),
            attempt_id,
            generation,
            role: Role::Planner,
            workspace: self.repo.clone(),
            model_ref: self.model_ref.clone(),
            contract_hash: task.contract_hash.clone(),
            source_revision: snapshot.revision().into(),
            prompt: String::new(),
            admission: ExecutionAdmission {
                repo_id: identity.repo_id,
                repository: workspace.clone(),
                workspace,
                task_id: task_id.into(),
                attempt_id: identity.attempt_id,
                generation,
                contract_hash: task.contract_hash.clone(),
                role: Role::Planner,
                allowed_write_paths: vec![],
                denied_paths: vec![],
                admitted_check_operation_ids: vec![],
            },
            check_operations: vec![],
        };
        let context = PlanningContext::new(request, BTreeSet::new(), vec![], vec![]);
        let planner = Planner::new(&self.runtime, &self.service, &self.state);
        match planner.propose(snapshot, &failure, &context).await? {
            PlanOutcome::Pending { snapshot, .. } => {
                if self.limits.no_commit {
                    return Ok(PlanDispositionResult::Pending(task_id.into()));
                }
                let committed = self.commit_proposal(snapshot)?;
                let _ = committed;
                Ok(PlanDispositionResult::Pending(task_id.into()))
            }
            PlanOutcome::OwnerHelp(help) => Ok(match help.kind {
                crate::planning::PrerequisiteKind::SudoRequired => {
                    PlanDispositionResult::WaitingSudo(task_id.into())
                }
                crate::planning::PrerequisiteKind::CredentialRequired => {
                    PlanDispositionResult::WaitingCredential(task_id.into())
                }
            }),
            PlanOutcome::WaitingExternal | PlanOutcome::Exhausted(_) => {
                Ok(PlanDispositionResult::WaitingExternal(task_id.into()))
            }
            PlanOutcome::RefusedScope | PlanOutcome::UnchangedEvidence => {
                Ok(PlanDispositionResult::NoChange)
            }
        }
    }
}

enum TaskResult {
    Completed(Vec<String>),
    Failed { reason: String, evidence: Vec<String> },
}

enum PlanDispositionResult {
    Pending(String),
    WaitingExternal(String),
    WaitingSudo(String),
    WaitingCredential(String),
    NoChange,
}

struct AgentReport {
    status: RuntimeStatus,
    text: String,
    evidence_ref: String,
}

fn next_generation(state: &StateStore, task: &str) -> Result<u64> {
    Ok(state
        .events()?
        .iter()
        .filter(|(_, event)| event.identity.task_id == task)
        .map(|(_, event)| event.identity.generation)
        .max()
        .unwrap_or(0)
        + 1)
}

fn pending_token(snapshot: &PendingSnapshot) -> Result<String> {
    let value = serde_json::json!({
        "base_head": snapshot.base_head,
        "branch": snapshot.branch,
        "tree": snapshot.tree,
        "captured_bytes": snapshot.captured_bytes,
        "captured_evidence": snapshot.captured_evidence,
    });
    sha256(&serde_json::to_vec(&value).map_err(|_| Unavailable("token serialization"))?)
}

fn close_record(task: &Record, current: &[u8]) -> Result<Vec<u8>> {
    let text = std::str::from_utf8(current).map_err(|_| Unavailable("task encoding"))?;
    let mut closed = text.replace("status = \"open\"", "status = \"done\"");
    let marker = "\n+++\n";
    let at = closed
        .find(marker)
        .ok_or(Unavailable("task header delimiter"))?;
    let fields = format!(
        "closure = \"coordinator_verified\"\nclosure_evidence = \"tasks/evidence/{}.toml\"\n",
        task.id
    );
    closed.insert_str(at + 1, &fields);
    Ok(closed.into_bytes())
}

fn closure_receipt(
    task: &Record,
    candidate: &str,
    integration: &str,
    tree: &str,
    check_refs: &[String],
    review_ref: &str,
) -> String {
    format!(
        "schema = 1\ntask = \"{}\"\ncontract_hash = \"{}\"\nresult = \"pass\"\nreview = \"passed\"\ncandidate = \"{}\"\nintegration = \"{}\"\ntree = \"{}\"\nchecks = [{}]\nreview_evidence = \"{}\"\n",
        task.id,
        task.contract_hash,
        candidate,
        integration,
        tree,
        check_refs
            .iter()
            .map(|s| format!("\"{}\"", s.replace('"', "")))
            .collect::<Vec<_>>()
            .join(", "),
        review_ref.replace('"', "")
    )
}

fn review_verdict(text: &str) -> Option<String> {
    #[derive(Deserialize)]
    struct Verdict {
        verdict: String,
        evidence: String,
    }
    let parsed: Verdict = serde_json::from_str(text.trim()).ok()?;
    (parsed.verdict == "passed" && !parsed.evidence.trim().is_empty()).then_some(parsed.verdict)
}

fn session_text(evidence: &Path) -> Option<String> {
    let path = evidence.join("session.jsonl");
    if fs::metadata(&path).ok()?.len() > MAX_AGENT_TRANSCRIPT {
        return None;
    }
    let session = native_agent::Session::open_read_only(path).ok()?;
    session
        .entries()
        .iter()
        .rev()
        .find_map(|entry| match &entry.value {
            native_agent::session::EntryValue::Message(native_ai::Message::Assistant(message)) => {
                Some(
                    message
                        .content
                        .iter()
                        .filter_map(|part| match part {
                            native_ai::AssistantPart::Text(text) => Some(text.as_str()),
                            _ => None,
                        })
                        .collect::<String>(),
                )
            }
            _ => None,
        })
}

fn integrate_candidate(
    repo: &Path,
    base: &str,
    candidate: &str,
    tree: &str,
    task: &str,
) -> Result<String> {
    let head = git_text(repo, &["rev-parse", "--verify", "HEAD^{commit}"])?;
    if head != base {
        return Err(Unavailable("integration base changed"));
    }
    let branch = git_text(repo, &["symbolic-ref", "--quiet", "HEAD"])?;
    let integration = git_input(
        repo,
        &["commit-tree", tree, "-p", base, "-p", candidate],
        &format!("autowork: integrate candidate for {task}\n"),
    )?;
    git(
        repo,
        &["update-ref", &branch, &integration, base],
    )?;
    Ok(integration)
}

fn commit_worktree(worktree: &Path, message: &str) -> Result<String> {
    git(worktree, &["add", "-A"])?;
    git(worktree, &["commit", "--no-gpg-sign", "-m", message])?;
    git_text(worktree, &["rev-parse", "--verify", "HEAD^{commit}"])
}

fn worktree_changes(worktree: &Path) -> Result<Vec<String>> {
    let out = text(git(worktree, &["status", "--porcelain=v1", "-z"])?)?;
    Ok(out
        .split('\0')
        .filter_map(|entry| {
            let entry = entry.trim_start();
            (!entry.is_empty()).then(|| entry.get(3..).unwrap_or(entry).to_string())
        })
        .collect())
}

fn protected_path(path: &str) -> bool {
    let p = Path::new(path);
    p.components().any(|c| {
        matches!(
            c,
            Component::Normal(v)
                if matches!(
                    v.to_str().unwrap_or(""),
                    "tasks" | ".git" | "BLOCKERS.md" | "CHANGELOG.md" | "TODO.archive.md"
                )
        )
    })
}

fn normalized_relative(path: &Path) -> bool {
    !path.as_os_str().is_empty()
        && path.components().all(|c| matches!(c, Component::Normal(_)))
        && path.to_str().is_some_and(|s| {
            !s.starts_with('/')
                && !s.starts_with('~')
                && !s.contains('\\')
                && !s.contains('\0')
        })
}

fn commit_tree(repo: &Path, commit: &str) -> Result<String> {
    git_text(repo, &["rev-parse", &format!("{commit}^{{tree}}")])
}

fn commit_parents(repo: &Path, commit: &str) -> Result<Vec<String>> {
    Ok(git_text(repo, &["cat-file", "commit", commit])?
        .lines()
        .filter_map(|line| line.strip_prefix("parent "))
        .map(str::to_owned)
        .collect())
}

fn verify_commit(repo: &Path, commit: &str) -> Result<()> {
    if git_text(repo, &["cat-file", "-t", commit])? != "commit" {
        return Err(Unavailable("publication commit missing"));
    }
    Ok(())
}

fn branch_name(base_head: &str, repo: &Path) -> Result<String> {
    let branch = git_text(repo, &["symbolic-ref", "--quiet", "HEAD"])?;
    let _ = base_head;
    branch
        .strip_prefix("refs/heads/")
        .map(str::to_owned)
        .ok_or(Unavailable("integration branch"))
}

fn git_env(repo: &Path, args: &[&str], input: &[u8], index: Option<&Path>) -> Result<Vec<u8>> {
    let mut command = Command::new("git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            command.env_remove(key);
        }
    }
    command
        .args(["--no-optional-locks", "--no-replace-objects", "-C"])
        .arg(repo)
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(index) = index {
        command.env("GIT_INDEX_FILE", index);
    }
    let mut child = command.spawn().map_err(|_| Unavailable("git spawn"))?;
    let mut stdin = child.stdin.take().unwrap();
    let input = input.to_vec();
    let writer = std::thread::spawn(move || stdin.write_all(&input));
    let output = child
        .wait_with_output()
        .map_err(|_| Unavailable("git wait"))?;
    let _ = writer.join();
    if !output.status.success() {
        return Err(Unavailable("git command refused"));
    }
    Ok(output.stdout)
}

fn git(repo: &Path, args: &[&str]) -> Result<Vec<u8>> {
    git_env(repo, args, &[], None)
}

fn git_input(repo: &Path, args: &[&str], input: &str) -> Result<String> {
    Ok(text(git_env(repo, args, input.as_bytes(), None)?)?
        .trim()
        .to_owned())
}

fn git_text(repo: &Path, args: &[&str]) -> Result<String> {
    Ok(text(git(repo, args)?)?
        .trim_end_matches('\n')
        .to_owned())
}

fn text(bytes: Vec<u8>) -> Result<String> {
    String::from_utf8(bytes).map_err(|_| Unavailable("git output encoding"))
}

fn path(path: &Path) -> &str {
    path.to_str().unwrap_or("")
}

fn sha256(bytes: &[u8]) -> Result<String> {
    let mut child = Command::new("sha256sum")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .map_err(|_| Unavailable("sha256sum unavailable"))?;
    child
        .stdin
        .take()
        .unwrap()
        .write_all(bytes)
        .map_err(|_| Unavailable("sha256sum write"))?;
    let output = child
        .wait_with_output()
        .map_err(|_| Unavailable("sha256sum wait"))?;
    if !output.status.success() {
        return Err(Unavailable("sha256sum failed"));
    }
    let hash = String::from_utf8(output.stdout)
        .map_err(|_| Unavailable("sha256sum output"))?
        .split_whitespace()
        .next()
        .unwrap_or("")
        .to_owned();
    if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err(Unavailable("invalid sha256"));
    }
    Ok(hash)
}

fn sha256_file(path: &Path) -> Result<String> {
    let bytes = fs::read(path).map_err(|_| Unavailable("check executable missing"))?;
    sha256(&bytes)
}

fn now_text() -> String {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis()
        .to_string()
}

fn read_json<T: for<'de> Deserialize<'de>>(path: &Path) -> Result<Option<T>> {
    match fs::read(path) {
        Ok(bytes) => serde_json::from_slice(&bytes)
            .map(Some)
            .map_err(|_| Unavailable("journal encoding")),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(_) => Err(Unavailable("journal read")),
    }
}

fn write_json_atomic(path: &Path, value: &impl Serialize) -> Result<()> {
    let bytes = serde_json::to_vec(value).map_err(|_| Unavailable("journal serialization"))?;
    atomic_bytes(path, &bytes)
}

fn atomic_bytes(path: &Path, bytes: &[u8]) -> Result<()> {
    let staged = path.with_file_name(format!(
        ".{}.tmp",
        path.file_name().unwrap().to_string_lossy()
    ));
    match fs::remove_file(&staged) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(_) => return Err(Unavailable("journal cleanup")),
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(&staged)
        .map_err(|_| Unavailable("journal create"))?;
    file.write_all(bytes)
        .map_err(|_| Unavailable("journal write"))?;
    file.sync_all().map_err(|_| Unavailable("journal sync"))?;
    fs::rename(&staged, path).map_err(|_| Unavailable("journal rename"))?;
    File::open(path.parent().unwrap())
        .and_then(|f| f.sync_all())
        .map_err(|_| Unavailable("journal directory sync"))?;
    Ok(())
}
