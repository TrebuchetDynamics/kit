use std::io::Write;
use std::process::{Command, Output, Stdio};

use autowork_next::runtime::{
    AgentRequest, AgentResult, MAX_EVENT_BYTES, Role, RunIdentity, RuntimeEvent, RuntimeEventKind,
    RuntimeStatus,
};
use serde_json::{Value, json};

fn cli(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_autowork-next"))
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

#[test]
fn bootstrap_without_pi() {
    let version = output_json(&["version"]);
    assert_eq!(version["application"], "autowork-next");
    assert_eq!(version["engine"], "native-Octet");
    assert!(cli(&["--version"]).status.success());
    let capabilities = output_json(&["capabilities"]);
    assert_eq!(capabilities["commands"]["version"], "available");
    assert_eq!(capabilities["commands"]["capabilities"], "available");
    assert_eq!(capabilities["model_execution"], "unavailable");
    assert_eq!(capabilities["installed_runner"], "unchanged");
    for command in ["run", "internal-agent"] {
        assert_eq!(capabilities["commands"][command], "unavailable");
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
