use std::io::{self, BufRead, Read};
use std::process::ExitCode;

use autowork_next::{CONTRACT_VERSION, ENGINE, ENGINE_REVISION, runtime};
use clap::{Parser, Subcommand};
use serde_json::json;

#[derive(Parser)]
#[command(
    name = "autowork-next",
    version,
    about = "Native-Octet Autowork candidate (explicit local cycles)"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Read committed tasks and existing journal without runtime side effects.
    Status {
        #[arg(long)]
        repo: std::path::PathBuf,
        #[arg(long)]
        json: bool,
    },
    /// Prepare ordinary task edits; protected authority remains refused.
    Tasks {
        #[arg(long)]
        repo: std::path::PathBuf,
        #[arg(long)]
        expected_revision: Option<String>,
        #[command(subcommand)]
        action: TaskCommand,
    },
    /// Print application and immutable engine versions as JSON.
    Version,
    /// Report implemented commands and versioned wire contracts as JSON.
    Capabilities,
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
    Place {
        id: String,
        #[arg(long)]
        record_revision: String,
        section: String,
    },
    Preview,
}

#[tokio::main]
async fn main() -> ExitCode {
    match dispatch(Cli::parse().command).await {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!(
                "{}",
                json!({"status": "unavailable", "error": error.to_string()})
            );
            ExitCode::FAILURE
        }
    }
}

async fn dispatch(command: Command) -> Result<(), Box<dyn std::error::Error>> {
    match command {
        Command::Status { repo, json: _ } => println!("{}", status(&repo)?),
        Command::Tasks {
            repo,
            expected_revision,
            action,
        } => println!("{}", task_command(&repo, expected_revision, action)?),
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
                    "status": "read-only-json-v1",
                    "tasks": "pending-ordinary-edits",
                    "internal-agent": "owned-only"
                },
                "unknown_commands": "unsupported",
                "contracts": {
                    "agent_request": CONTRACT_VERSION,
                    "agent_result": CONTRACT_VERSION,
                    "runtime_event": CONTRACT_VERSION,
                    "roles": runtime::ROLES,
                    "max_request_bytes": runtime::MAX_REQUEST_BYTES,
                    "max_event_bytes": runtime::MAX_EVENT_BYTES
                },
                "model_execution": "explicit-owned-route",
                "installed_runner": "unchanged"
            })
        ),
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
            let common = std::process::Command::new("/usr/bin/git")
                .env_clear()
                .env("PATH", "/usr/bin:/bin")
                .args(["--no-replace-objects", "-C"])
                .arg(&repo)
                .args(["rev-parse", "--path-format=absolute", "--git-common-dir"])
                .output()?;
            if !common.status.success() {
                return Err(io::Error::other("Git repository required").into());
            }
            let state = StateStore::open(String::from_utf8(common.stdout)?.trim())?;
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

fn git_common(repo: &std::path::Path) -> Result<std::path::PathBuf, Box<dyn std::error::Error>> {
    let mut command = std::process::Command::new("/usr/bin/git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            command.env_remove(key);
        }
    }
    let result = command
        .arg("-C")
        .arg(repo)
        .args(["rev-parse", "--path-format=absolute", "--git-common-dir"])
        .output()?;
    if !result.status.success() {
        return Err(io::Error::other("Git repository required").into());
    }
    Ok(String::from_utf8(result.stdout)?.trim().into())
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
    let journal = match autowork_next::state::read_status(git_common(&repo)?) {
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
    expected: Option<String>,
    action: TaskCommand,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    use autowork_next::{
        planning::{FailureEvidence, PlanDisposition, PlanProposal, RecordChange},
        task_store::{TaskService, TaskStore},
    };
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
            let bytes = edit_record(&service, &id, &record_revision, "section", json!(section))?;
            (id, record_revision, bytes)
        }
        TaskCommand::Preview => unreachable!(),
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
                path: format!("tasks/items/{id}.md").into(),
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
) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    if ![
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
    .contains(&key)
    {
        return Err(io::Error::other("unsupported or protected task field").into());
    }
    let bytes = service.record_for_edit(id, record_revision)?;
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
