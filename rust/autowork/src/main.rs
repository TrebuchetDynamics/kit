use std::collections::BTreeMap;
use std::io::{self, BufRead, Read};
use std::os::unix::fs::DirBuilderExt;
use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;

use autowork_next::execution::{CheckRegistry, Coordinator, CycleLimits};
use autowork_next::task_store::Scope;
use autowork_next::{CONTRACT_VERSION, ENGINE, ENGINE_REVISION, runtime};
use clap::{Parser, Subcommand};
use serde_json::json;

#[derive(Parser)]
#[command(
    name = "autowork-next",
    version,
    about = "Native-Octet Autowork coordinator"
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
    /// Run the native coordinator with an explicit model route from the environment.
    Run {
        #[arg(long, default_value = ".")]
        repo: PathBuf,
        #[arg(long = "task")]
        task_ids: Vec<String>,
        #[arg(long)]
        max_tasks: Option<usize>,
        #[arg(long)]
        pause: bool,
        #[arg(long)]
        no_commit: bool,
    },
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
                    "run": "available",
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
        Command::Run { repo, task_ids, max_tasks, pause, no_commit } => {
            if max_tasks == Some(0) {
                return Err(autowork_next::Unavailable("max tasks must be positive").into());
            }
            let repo = repo.canonicalize()?;
            let state_base = std::env::var_os("XDG_STATE_HOME")
                .map(PathBuf::from)
                .or_else(|| std::env::var_os("HOME").map(|p| PathBuf::from(p).join(".local/state")))
                .ok_or(autowork_next::Unavailable("private state directory"))?;
            let evidence = state_base.join("autowork-next/evidence");
            std::fs::DirBuilder::new().recursive(true).mode(0o700).create(&evidence)?;
            let model_ref = std::env::var("AUTOWORK_MODEL_REF").unwrap_or_else(|_| "default".into());
            let models = match (std::env::var("AUTOWORK_MODEL_NAME"), std::env::var("AUTOWORK_MODEL_BASE_URL")) {
                (Ok(model), Ok(base_url)) => {
                    let route = runtime::ModelRoute {
                        provider: "openai_chat".into(),
                        model,
                        base_url,
                        secret_file: std::env::var_os("AUTOWORK_MODEL_SECRET_FILE").map(PathBuf::from),
                    };
                    BTreeMap::from([(model_ref.clone(), route)])
                }
                _ => BTreeMap::new(),
            };
            let runtime = runtime::Runtime::new(
                std::env::current_exe()?, evidence, models, Duration::from_secs(300),
            )?;
            let coordinator = Coordinator::new(
                &repo, runtime, &model_ref, CheckRegistry::default(),
                CycleLimits { max_tasks, paused: pause, no_commit },
            )?;
            let summary = coordinator.run_until_quiescent(Scope { task_ids }).await?;
            println!("{}", serde_json::to_string(&summary)?);
        }
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
