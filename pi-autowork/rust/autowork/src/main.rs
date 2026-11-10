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
    /// Print application and immutable engine versions as JSON.
    Version,
    /// Report implemented commands and versioned wire contracts as JSON.
    Capabilities,
    /// Inspect committed tasks only (no mutations or working-tree reads).
    Tasks {
        #[arg(long, global = true)]
        repo: Option<std::path::PathBuf>,
        #[arg(long, global = true, default_value = "HEAD")]
        rev: String,
        #[command(subcommand)]
        command: TaskCommand,
    },
    /// Read the private journal projection without claiming writer ownership.
    Status {
        #[arg(long)]
        repo: std::path::PathBuf,
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
    Show { id: String },
    Why { id: String },
}

#[tokio::main]
async fn main() -> ExitCode {
    match dispatch(Cli::parse().command).await {
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

async fn dispatch(command: Command) -> Result<(), Box<dyn std::error::Error>> {
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
                    "tasks": ["list", "goals", "show", "why"],
                    "status": "journal-projection-only",
                    "internal-agent": "owned-only"
                },
                "unknown_commands": "unsupported",
                "contracts": {
                    "agent_request": CONTRACT_VERSION,
                    "agent_result": CONTRACT_VERSION,
                    "runtime_event": CONTRACT_VERSION,
                    "task_inspection": 1,
                    "status": 1,
                    "roles": runtime::ROLES,
                    "max_request_bytes": runtime::MAX_REQUEST_BYTES,
                    "max_event_bytes": runtime::MAX_EVENT_BYTES
                },
                "model_execution": "explicit-owned-route",
                "installed_runner": "unchanged"
            })
        ),
        Command::Tasks { repo, rev, command } => {
            use autowork_next::task_store::{Record, Scope, TaskStore};
            let repo = repo.ok_or_else(|| io::Error::other("tasks requires --repo PATH"))?;
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
        Command::Status { repo } => {
            use autowork_next::state::{InspectionError, read_status};
            let common = std::process::Command::new("/usr/bin/git")
                .env_clear()
                .env("PATH", "/usr/bin:/bin")
                .args(["--no-replace-objects", "-C"])
                .arg(repo)
                .args(["rev-parse", "--path-format=absolute", "--git-common-dir"])
                .output()
                .map_err(|_| InspectionError::UnsafeSource)?;
            if !common.status.success() {
                return Err(InspectionError::UnsafeSource.into());
            }
            let common =
                String::from_utf8(common.stdout).map_err(|_| InspectionError::UnsafeSource)?;
            let common = common
                .strip_suffix('\n')
                .ok_or(InspectionError::UnsafeSource)?;
            let status = read_status(std::path::Path::new(common))?;
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
