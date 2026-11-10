use std::io::{self, BufRead, Read};
use std::process::ExitCode;

use autowork_next::{CONTRACT_VERSION, ENGINE, ENGINE_REVISION, runtime};
use clap::{Parser, Subcommand, ValueEnum};
use serde_json::json;

#[derive(Parser)]
#[command(
    name = "autowork-next",
    version,
    about = "Native-Octet Autowork candidate (explicit local cycles)"
)]
struct Cli {
    /// Wire contract: `public-v1` is the published query/status/pending-edit surface;
    /// `inspection-v1` is the typed inspection and local publication surface.
    #[arg(long, global = true, value_enum, default_value = "public-v1")]
    format: Format,
    #[command(subcommand)]
    command: Command,
}

#[derive(Clone, Copy, PartialEq, Eq, ValueEnum)]
enum Format {
    #[value(name = "public-v1")]
    PublicV1,
    #[value(name = "inspection-v1")]
    InspectionV1,
}

#[derive(Subcommand)]
enum Command {
    /// Print application and immutable engine versions as JSON.
    Version,
    /// Report implemented commands and versioned wire contracts as JSON.
    Capabilities,
    /// Inspect committed tasks or explicitly preview/publish pending records.
    Tasks {
        #[arg(long, global = true)]
        repo: Option<std::path::PathBuf>,
        /// Committed revision to read; either before or after the subcommand, once.
        #[arg(long, global = true)]
        rev: Option<String>,
        /// Required base revision for public-v1 pending edits.
        #[arg(long)]
        expected_revision: Option<String>,
        #[command(subcommand)]
        command: TaskCommand,
    },
    /// Read committed goals or prepare ordinary pending goal metadata edits.
    Goals {
        #[arg(long, global = true)]
        repo: Option<std::path::PathBuf>,
        #[arg(long, global = true)]
        rev: Option<String>,
        #[arg(long)]
        expected_revision: Option<String>,
        #[command(subcommand)]
        command: GoalCommand,
    },
    /// Read committed tasks and the existing journal without runtime side effects.
    Status {
        #[arg(long)]
        repo: std::path::PathBuf,
        /// JSON is the only output; the flag is a compatibility marker, not a selector.
        #[arg(long)]
        json: bool,
    },
    /// Run serialized local deliveries with explicit model routes (no service or push).
    Run {
        #[arg(long)]
        repo: std::path::PathBuf,
        #[arg(long)]
        models: std::path::PathBuf,
        #[arg(long)]
        worker_model: String,
        #[arg(long)]
        reviewer_model: String,
        #[arg(long)]
        planner_model: String,
        #[arg(long)]
        one_task: bool,
        #[arg(long)]
        no_commit: bool,
        /// Enable deterministic checks only in a disposable fixture repository.
        #[arg(long)]
        fixture_checks: bool,
        #[arg(long)]
        task: Vec<String>,
    },
    #[command(hide = true)]
    InternalFixtureCheck { result: String },
    #[command(hide = true)]
    InternalAgent,
}

#[derive(Subcommand)]
enum TaskCommand {
    List,
    Goals,
    Show {
        id: String,
    },
    Why {
        id: String,
    },
    /// Preview exact pending task/goal records, or publish a reviewed token locally.
    Commit {
        #[arg(long, conflicts_with = "expect_token")]
        dry_run: bool,
        #[arg(long)]
        expect_token: Option<String>,
    },
    /// public-v1: write one new pending record (never committed or selectable).
    Add {
        id: String,
        #[arg(long)]
        record: std::path::PathBuf,
    },
    /// public-v1: edit one ordinary field of a pending record.
    Field {
        id: String,
        #[arg(long)]
        record_revision: String,
        key: String,
        value: String,
    },
    /// public-v1: move a pending record to another section.
    Place {
        id: String,
        #[arg(long)]
        record_revision: String,
        section: String,
    },
    /// public-v1: show the pending records without publishing them.
    Preview,
}

#[derive(Subcommand)]
enum GoalCommand {
    List,
    Show {
        id: String,
    },
    Add {
        id: String,
        #[arg(long)]
        record: std::path::PathBuf,
    },
    Field {
        id: String,
        #[arg(long)]
        record_revision: String,
        key: String,
        value: String,
    },
}

#[tokio::main]
async fn main() -> ExitCode {
    // clap lets a global option repeat across subcommand levels and keeps the last value;
    // two revisions are contradictory input, never a silent choice.
    let revisions = std::env::args_os()
        .skip(1)
        .take_while(|arg| arg != "--")
        .filter(|arg| arg == "--rev" || arg.to_string_lossy().starts_with("--rev="))
        .count();
    if revisions > 1 {
        eprintln!(
            "{}",
            json!({"status": "unavailable", "error": "--rev may be given only once"})
        );
        return ExitCode::FAILURE;
    }
    let cli = Cli::parse();
    match dispatch(cli.command, cli.format).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            let diagnostic = if let Some(error) =
                error.downcast_ref::<autowork_next::state::InspectionError>()
            {
                json!({"status": "unavailable", "code": error.code(), "error": error.to_string()})
            } else {
                json!({"status": "unavailable", "error": error.to_string()})
            };
            eprintln!("{diagnostic}");
            ExitCode::FAILURE
        }
    }
}

async fn dispatch(command: Command, format: Format) -> Result<(), Box<dyn std::error::Error>> {
    match command {
        Command::Version => println!(
            "{}",
            json!({
                "application": "autowork-next",
                "version": env!("CARGO_PKG_VERSION"),
                "engine": ENGINE,
                "engine_revision": ENGINE_REVISION,
            })
        ),
        Command::Capabilities => println!(
            "{}",
            json!({
                "application": "autowork-next",
                "engine": ENGINE,
                "engine_revision": ENGINE_REVISION,
                "commands": {
                    "version": "available",
                    "capabilities": "available",
                    "run": "explicit-local-cycle",
                    "tasks": if format == Format::InspectionV1 {
                        json!(["list", "goals", "show", "why", "commit"])
                    } else {
                        json!("committed-queries-and-pending-ordinary-edits")
                    },
                    "goals": if format == Format::PublicV1 {
                        json!(["list", "show", "add", "field"])
                    } else {
                        json!("unsupported")
                    },
                    "status": if format == Format::InspectionV1 {
                        "journal-projection-only"
                    } else {
                        "read-only-json-v1"
                    },
                    "internal-agent": "owned-only"
                },
                "unknown_commands": "unsupported",
                "formats": {
                    "selected": if format == Format::InspectionV1 { "inspection-v1" } else { "public-v1" },
                    "default": "public-v1",
                    "public-v1": {
                        "status": "committed tasks plus persisted runs of every generation",
                        "tasks": ["list", "show", "add", "field", "place", "preview"],
                        "goals": ["list", "show", "add", "field"],
                        // Pending edits check only this runtime's task lock; another
                        // runtime's active owner is not detected.
                        "pending_edits": "unqualified-on-active-repositories"
                    },
                    "inspection-v1": {
                        "status": "latest-generation journal projection",
                        "tasks": ["list", "goals", "show", "why", "commit"]
                    }
                },
                "contracts": {
                    "agent_request": CONTRACT_VERSION,
                    "agent_result": CONTRACT_VERSION,
                    "runtime_event": CONTRACT_VERSION,
                    "task_inspection": 1,
                    "task_publication": 1,
                    "status": 1,
                    "roles": runtime::ROLES,
                    "max_request_bytes": runtime::MAX_REQUEST_BYTES,
                    "max_event_bytes": runtime::MAX_EVENT_BYTES
                },
                "model_execution": "explicit-owned-route",
                "installed_runner": "unchanged"
            })
        ),
        Command::Tasks {
            repo,
            rev,
            expected_revision,
            command,
        } => {
            use autowork_next::task_store::{Record, Scope, TaskStore};
            let repo = repo.ok_or_else(|| io::Error::other("tasks requires --repo PATH"))?;
            let inspection_only = matches!(
                command,
                TaskCommand::Goals | TaskCommand::Why { .. } | TaskCommand::Commit { .. }
            );
            let public_only = matches!(
                command,
                TaskCommand::Add { .. }
                    | TaskCommand::Field { .. }
                    | TaskCommand::Place { .. }
                    | TaskCommand::Preview
            );
            if format == Format::PublicV1 {
                if inspection_only {
                    return Err(io::Error::other(
                        "this tasks command requires --format inspection-v1",
                    )
                    .into());
                }
                if public_only && rev.as_deref().is_some_and(|rev| rev != "HEAD") {
                    return Err(io::Error::other("pending edits require --rev HEAD").into());
                }
                println!(
                    "{}",
                    task_command(
                        &repo,
                        rev.as_deref().unwrap_or("HEAD"),
                        expected_revision,
                        command,
                        false
                    )?
                );
                return Ok(());
            }
            if public_only || expected_revision.is_some() {
                return Err(io::Error::other(
                    "pending edits are public-v1 commands; omit --format",
                )
                .into());
            }
            let rev = rev.unwrap_or_else(|| "HEAD".into());
            if let TaskCommand::Commit {
                dry_run,
                expect_token,
            } = command
            {
                use autowork_next::{execution::*, state::StateStore, task_store::TaskService};
                if rev != "HEAD" {
                    return Err(io::Error::other("tasks commit requires --rev HEAD").into());
                }
                if expect_token
                    .as_deref()
                    .is_some_and(|t| !autowork_next::task_store::valid_publication_token(t))
                {
                    return Err(io::Error::other("malformed publication token").into());
                }
                let repo = std::fs::canonicalize(repo)?;
                let service = TaskService::new(&repo)?;
                if dry_run {
                    println!("{}", serde_json::to_string(&service.preview_pending()?)?);
                    return Ok(());
                }
                let common = git_common(&repo)?;
                let state = StateStore::open(&common)?;
                let binary = std::env::current_exe()?;
                // No routes and no dispatch: this runtime only satisfies the shared constructor.
                let runtime = runtime::Runtime::new(
                    binary.clone(),
                    state.directory().to_owned(),
                    Default::default(),
                    std::time::Duration::from_secs(120),
                )?;
                let coordinator = Coordinator::new(
                    &repo,
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
                )?;
                let result = match coordinator.publish_pending(expect_token.as_deref())? {
                    Some((token, revision)) => json!({"state":"committed", "commit":revision.0,
                        "token":token, "publication":"local_only", "execution_evaluated":false,
                        "closure_evaluated":false}),
                    None => json!({"state":"clean", "commit":null, "token":null,
                        "publication":"local_only", "execution_evaluated":false, "closure_evaluated":false}),
                };
                println!("{result}");
                return Ok(());
            }
            let snapshot = TaskStore::read_at(&repo, &rev)
                .map_err(|_| io::Error::other("committed task snapshot unavailable"))?;
            let source = json!({"only": true, "admission_evaluated": false,
                "runtime_evaluated": false, "source": "committed", "ref": rev,
                "revision": snapshot.revision(), "revision_ephemeral": false});
            let record_json = |record: &Record| -> Result<serde_json::Value, serde_json::Error> {
                let mut value = serde_json::to_value(record.fields())?;
                value.as_object_mut().unwrap().extend(json!({
                    "path": record.path, "body": record.body,
                    "snapshot": {"source": "committed", "ref": rev,
                        "revision": snapshot.revision(), "revision_ephemeral": false},
                    "record_revision": record.record_revision, "contract_hash": record.contract_hash,
                    "missing_fields": record.missing_fields, "receipt_valid": record.receipt_valid
                }).as_object().unwrap().clone());
                Ok(value)
            };
            let value = match command {
                TaskCommand::Goals => serde_json::Value::Array(
                    snapshot
                        .goals()
                        .values()
                        .map(record_json)
                        .collect::<Result<_, _>>()?,
                ),
                TaskCommand::Show { id } => record_json(
                    snapshot
                        .tasks()
                        .get(&id)
                        .ok_or_else(|| io::Error::other("unknown task ID"))?,
                )?,
                command => {
                    let selection = snapshot
                        .select(&Scope::default())
                        .map_err(|_| io::Error::other("task selection unavailable"))?;
                    let explanation = |id: &str| {
                        let position = selection
                            .task_ids
                            .iter()
                            .position(|t| t == id)
                            .map(|p| p + 1);
                        json!({"id": id, "position": position,
                            "blocked_by": selection.blocked.get(id).map(|r| r.code.as_str()),
                            "eligible": position.is_some(), "first": position == Some(1),
                            "reasons": snapshot.selection_reasons(&selection, id), "selection": source})
                    };
                    match command {
                        TaskCommand::Why { id } => explanation(&id),
                        TaskCommand::List => serde_json::Value::Array(
                            snapshot
                                .tasks()
                                .values()
                                .map(|record| {
                                    let mut row = record_json(record)?;
                                    row.as_object_mut().unwrap().extend(
                                        explanation(&record.id).as_object().unwrap().clone(),
                                    );
                                    Ok(row)
                                })
                                .collect::<Result<_, serde_json::Error>>()?,
                        ),
                        _ => unreachable!(),
                    }
                }
            };
            println!("{}", serde_json::to_string(&value)?);
        }
        Command::Goals {
            repo,
            rev,
            expected_revision,
            command,
        } => {
            if format != Format::PublicV1 {
                return Err(io::Error::other("goals requires public-v1; omit --format").into());
            }
            let repo = repo.ok_or_else(|| io::Error::other("goals requires --repo PATH"))?;
            let action = match command {
                GoalCommand::List => TaskCommand::List,
                GoalCommand::Show { id } => TaskCommand::Show { id },
                GoalCommand::Add { id, record } => TaskCommand::Add { id, record },
                GoalCommand::Field {
                    id,
                    record_revision,
                    key,
                    value,
                } => TaskCommand::Field {
                    id,
                    record_revision,
                    key,
                    value,
                },
            };
            let rev = rev.as_deref().unwrap_or("HEAD");
            if !matches!(action, TaskCommand::List | TaskCommand::Show { .. }) && rev != "HEAD" {
                return Err(io::Error::other("pending edits require --rev HEAD").into());
            }
            println!(
                "{}",
                task_command(&repo, rev, expected_revision, action, true)?
            );
        }
        Command::Status { repo, json: _ } => {
            if format == Format::PublicV1 {
                println!("{}", status(&repo)?);
                return Ok(());
            }
            use autowork_next::state::{InspectionError, read_status};
            let common = git_common(&repo).map_err(|_| InspectionError::UnsafeSource)?;
            let status = read_status(std::path::Path::new(&common))?;
            println!("{}", serde_json::to_string(&status)?);
        }
        Command::Run {
            repo,
            models,
            worker_model,
            reviewer_model,
            planner_model,
            one_task,
            no_commit,
            fixture_checks,
            task,
        } => {
            use autowork_next::{
                execution::*,
                state::StateStore,
                task_store::{Scope, TaskService},
            };
            use std::os::unix::fs::DirBuilderExt;
            let repo = std::fs::canonicalize(repo)?;
            let common = git_common(&repo)?;
            let state = StateStore::open(&common)?;
            let evidence = state.directory().join("native-cycle");
            if !evidence.exists() {
                std::fs::DirBuilder::new().mode(0o700).create(&evidence)?;
            }
            let routes = serde_json::from_slice(&std::fs::read(models)?)?;
            let binary = std::env::current_exe()?;
            let runtime = runtime::Runtime::new(
                binary.clone(),
                evidence,
                routes,
                std::time::Duration::from_secs(120),
            )?;
            let service = TaskService::new(&repo)?;
            let mut coordinator = Coordinator::new(
                &repo,
                &binary,
                &runtime,
                &service,
                &state,
                RunOptions {
                    worker_model,
                    reviewer_model,
                    planner_model,
                    max_tasks: one_task.then_some(1),
                    allow_commit: !no_commit,
                    control: Control::default(),
                    prerequisites: vec![],
                },
            )?;
            if fixture_checks {
                coordinator.enable_fixture_checks();
            }
            println!(
                "{}",
                serde_json::to_string(
                    &coordinator
                        .run_until_quiescent(Scope { task_ids: task })
                        .await?
                )?
            );
        }
        Command::InternalFixtureCheck { result } => match result.as_str() {
            "pass" => println!("offline fixture check: pass (not general check qualification)"),
            "fail" => return Err(io::Error::other("offline fixture check failure").into()),
            _ => return Err(io::Error::other("unknown fixture operation").into()),
        },
        Command::InternalAgent => {
            let mut bytes = Vec::new();
            // One bounded JSON line, then stdin remains the owned cancellation pipe.
            io::BufReader::new(
                io::stdin()
                    .lock()
                    .take(runtime::MAX_REQUEST_BYTES as u64 + 1),
            )
            .read_until(b'\n', &mut bytes)?;
            if bytes.len() > runtime::MAX_REQUEST_BYTES {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "agent request exceeds limit",
                )
                .into());
            }
            let request: runtime::AgentRequest = serde_json::from_slice(&bytes)
                .map_err(|_| io::Error::new(io::ErrorKind::InvalidData, "invalid agent request"))?;
            if request.schema_version != CONTRACT_VERSION {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    "unsupported agent request schema",
                )
                .into());
            }
            // The child emits normalized RuntimeEvent JSONL, not native reply channels.
            let _ = runtime::serve_owned_agent(request).await?;
        }
    }
    Ok(())
}

/// Git's absolute common directory. Only Git's own trailing newline is removed:
/// trailing whitespace can be part of a path.
fn git_common(repo: &std::path::Path) -> Result<String, Box<dyn std::error::Error>> {
    let result = std::process::Command::new("/usr/bin/git")
        .env_clear()
        .env("PATH", "/usr/bin:/bin")
        .args(["--no-replace-objects", "-C"])
        .arg(repo)
        .args(["rev-parse", "--path-format=absolute", "--git-common-dir"])
        .output()?;
    if !result.status.success() {
        return Err(io::Error::other("Git repository required").into());
    }
    Ok(String::from_utf8(result.stdout)?
        .strip_suffix('\n')
        .ok_or_else(|| io::Error::other("invalid Git directory"))?
        .to_owned())
}

fn status(repo: &std::path::Path) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    use autowork_next::task_store::{Scope, TaskStore};
    let repo = std::fs::canonicalize(repo)?;
    let snapshot = TaskStore::read_at(&repo, "HEAD")?;
    let selection = snapshot.select(&Scope { task_ids: vec![] })?;
    let tasks: Vec<_> = snapshot.tasks().values().map(|task| json!({
        "id": task.id, "title": task.title, "status": task.string("status"),
        "ready": selection.task_ids.contains(&task.id),
        "blocked": selection.blocked.get(&task.id).map(|reason| json!({"code": reason.code, "detail": reason.detail}))
    })).collect();
    let journal = match autowork_next::state::read_persisted_runs(git_common(&repo)?) {
        Ok(value) => value,
        Err(_) => json!({"status": "unavailable", "reason": "journal absent, invalid or changing"}),
    };
    Ok(
        json!({"schema_version": 1, "application": "autowork-next", "version": env!("CARGO_PKG_VERSION"),
        "revision": snapshot.revision(), "task_count": tasks.len(), "tasks": tasks, "journal": journal,
        "qualification": "observed-only"}),
    )
}

fn task_command(
    repo: &std::path::Path,
    rev: &str,
    expected: Option<String>,
    action: TaskCommand,
    goal: bool,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    use autowork_next::{
        planning::{FailureEvidence, PlanDisposition, PlanProposal, RecordChange},
        task_store::{TaskService, TaskStore},
    };
    match &action {
        TaskCommand::List => return task_query(repo, rev, None, goal),
        TaskCommand::Show { id } => return task_query(repo, rev, Some(id), goal),
        _ => (),
    }
    let service = TaskService::new(repo)?;
    if matches!(action, TaskCommand::Preview) {
        return Ok(
            json!({"status": "pending", "snapshot": service.capture_pending()?, "selectable": false}),
        );
    }
    let expected = expected
        .ok_or_else(|| io::Error::other("--expected-revision is required for mutations"))?;
    let snapshot = TaskStore::read_at(repo, "HEAD")?;
    if snapshot.revision() != expected {
        return Err(io::Error::other("stale expected revision").into());
    }
    let (id, record_revision, bytes) = match action {
        TaskCommand::Add { id, record } => (id, String::new(), std::fs::read(record)?),
        TaskCommand::Field {
            id,
            record_revision,
            key,
            value,
        } => {
            let bytes = edit_record(
                &service,
                &id,
                &record_revision,
                &key,
                serde_json::from_str(&value)?,
                goal,
            )?;
            (id, record_revision, bytes)
        }
        TaskCommand::Place {
            id,
            record_revision,
            section,
        } => {
            if !["Now", "Next", "Needs decision"].contains(&section.as_str()) {
                return Err(io::Error::other("invalid section").into());
            }
            let bytes = edit_record(
                &service,
                &id,
                &record_revision,
                "section",
                json!(section),
                false,
            )?;
            (id, record_revision, bytes)
        }
        _ => unreachable!(),
    };
    if id.is_empty()
        || !id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
    {
        return Err(io::Error::other("invalid task ID").into());
    }
    let pending = service.apply(
        &expected,
        &PlanProposal {
            expected_revision: expected.clone(),
            failed_operation: FailureEvidence {
                operation_id: "cli-task-edit".into(),
                fingerprint: expected.clone(),
                evidence_refs: vec![],
            },
            disposition: PlanDisposition::RepairCurrent,
            record_changes: vec![RecordChange {
                path: format!("tasks/{}/{id}.md", if goal { "goals" } else { "items" }).into(),
                expected_revision: record_revision,
                proposed_bytes: bytes,
            }],
            reason: "Explicit pending task edit; no publication authority".into(),
            sources: vec![],
        },
    )?;
    Ok(
        json!({"status": "pending", "paths": pending.paths, "base_revision": pending.expected_revision, "record_revisions": pending.record_revisions, "selectable": false, "publication": "not-committed"}),
    )
}

fn edit_record(
    service: &autowork_next::task_store::TaskService,
    id: &str,
    record_revision: &str,
    key: &str,
    value: serde_json::Value,
    goal: bool,
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    let allowed: &[&str] = if goal {
        &["title", "source", "priority", "focus", "depends_on"]
    } else {
        &[
            "title",
            "short",
            "scope",
            "acceptance",
            "checks",
            "exclusions",
            "touches",
            "resources",
            "depends_on",
            "rank",
            "section",
        ]
    };
    if !allowed.contains(&key) {
        return Err(io::Error::other("unsupported or protected record field").into());
    }
    let bytes = if goal {
        service.goal_record_for_edit(id, record_revision)?
    } else {
        service.record_for_edit(id, record_revision)?
    };
    let source = std::str::from_utf8(&bytes)?;
    let (header, notes) = source
        .strip_prefix("+++\n")
        .or_else(|| source.strip_prefix("+++\r\n"))
        .and_then(|s| s.split_once("\n+++"))
        .ok_or_else(|| io::Error::other("invalid task header"))?;
    let mut fields: toml::Table = toml::from_str(header)?;
    fields.insert(key.into(), toml::Value::try_from(value)?);
    Ok(format!("+++\n{}+++{}", toml::to_string(&fields)?, notes).into_bytes())
}

fn task_query(
    repo: &std::path::Path,
    revision: &str,
    id: Option<&str>,
    goal: bool,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let snapshot = autowork_next::task_store::TaskStore::read_at(repo, revision)?;
    let describe = |task: &autowork_next::task_store::Record| -> Result<serde_json::Value, Box<dyn std::error::Error>> {
        let bytes = snapshot.records().get(&task.path).ok_or_else(|| io::Error::other("record missing from snapshot"))?;
        if goal {
            let mut row = serde_json::to_value(task.fields())?;
            row.as_object_mut().unwrap().extend(json!({
                "path": task.path, "record_revision": task.record_revision,
                "contract_hash": task.contract_hash, "content": std::str::from_utf8(bytes)?
            }).as_object().unwrap().clone());
            return Ok(row);
        }
        Ok(json!({"id": task.id, "title": task.title, "record_revision": task.record_revision,
            "contract_hash": task.contract_hash, "status": task.string("status"), "section": task.string("section"),
            "kind": task.string("kind"), "ownership": task.string("ownership"), "live": task.string("live"),
            "goal": task.string("goal"), "scope": task.string("scope"), "acceptance": task.strings("acceptance"),
            "checks": task.strings("checks"), "depends_on": task.strings("depends_on"),
            "verified_depends_on": task.strings("verified_depends_on"), "touches": task.strings("touches"),
            "resources": task.strings("resources"), "exclusions": task.strings("exclusions"),
            "missing_fields": task.missing_fields, "content": std::str::from_utf8(bytes)?}))
    };
    let mut result = json!({"schema_version": 1, "application": "autowork-next", "revision": snapshot.revision(), "source": "committed"});
    let records = if goal {
        snapshot.goals()
    } else {
        snapshot.tasks()
    };
    if let Some(id) = id {
        let record = records.get(id).ok_or_else(|| {
            io::Error::other(if goal {
                "unknown goal ID"
            } else {
                "unknown task ID"
            })
        })?;
        result[if goal { "goal" } else { "task" }] = describe(record)?;
    } else {
        result[if goal { "goals" } else { "tasks" }] = records
            .values()
            .map(describe)
            .collect::<Result<Vec<_>, _>>()?
            .into();
    }
    Ok(result)
}
