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
