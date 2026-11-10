//! Schema-1 task intent read from immutable Git input. Runtime admission is separate.
use crate::planning::PlanProposal;
use fs2::FileExt;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::os::unix::fs::MetadataExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};

#[derive(Debug)]
pub struct StoreError(pub String);
impl std::fmt::Display for StoreError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for StoreError {}
impl From<std::io::Error> for StoreError {
    fn from(e: std::io::Error) -> Self {
        Self(e.to_string())
    }
}
pub type Result<T> = std::result::Result<T, StoreError>;
fn refuse<T>(message: impl Into<String>) -> Result<T> {
    Err(StoreError(message.into()))
}

#[derive(Clone, Debug, Default)]
pub struct Scope {
    pub task_ids: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct Record {
    pub id: String,
    pub title: String,
    pub path: String,
    pub body: String,
    pub record_revision: String,
    pub contract_hash: String,
    pub missing_fields: Vec<String>,
    pub receipt_valid: bool,
    fields: toml::Table,
}
impl Record {
    pub fn field(&self, key: &str) -> Option<&toml::Value> {
        self.fields.get(key)
    }
    pub fn string(&self, key: &str) -> &str {
        self.field(key)
            .and_then(toml::Value::as_str)
            .unwrap_or(match key {
                "kind" | "ownership" => "unknown",
                "live" => "denied",
                _ => "",
            })
    }
    pub fn strings(&self, key: &str) -> Vec<&str> {
        self.field(key)
            .and_then(toml::Value::as_array)
            .map(|a| a.iter().filter_map(toml::Value::as_str).collect())
            .unwrap_or_default()
    }
    fn number(&self, key: &str) -> i64 {
        self.field(key)
            .and_then(toml::Value::as_integer)
            .unwrap_or(0)
    }
    fn focus(&self) -> bool {
        self.field("focus")
            .and_then(toml::Value::as_bool)
            .unwrap_or(false)
    }
    pub fn draft(&self) -> bool {
        !self.missing_fields.is_empty()
    }
    /// Contract/typed authority only; never a runtime lease, check grant or admission.
    pub fn runnable(&self) -> bool {
        !self.draft()
            && self.string("status") == "open"
            && matches!(self.string("section"), "Now" | "Next")
            && matches!(
                self.string("kind"),
                "implementation" | "plan" | "inspection"
            )
            && self.string("ownership") == "worker"
            && (!self.strings("resources").contains(&"live") || self.string("live") == "authorized")
    }
    pub fn verified(&self) -> bool {
        self.string("status") == "done"
            && self.string("closure") == "coordinator_verified"
            && self.receipt_valid
    }
    pub fn qualified(&self) -> bool {
        self.verified()
            || ((!self.string("owner_waiver").is_empty()
                || !self.string("owner_qualification").is_empty())
                && !self.string("waiver_actor").is_empty()
                && !self.string("waiver_at").is_empty()
                && self
                    .strings("acceptance")
                    .into_iter()
                    .chain(self.strings("checks"))
                    .any(|s| s == self.string("waiver_for")))
    }
}

#[derive(Clone, Debug)]
pub struct Snapshot {
    revision: String,
    records: BTreeMap<String, Vec<u8>>,
    tasks: BTreeMap<String, Record>,
    goals: BTreeMap<String, Record>,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Reason {
    pub code: String,
    pub detail: String,
}
#[derive(Clone, Debug)]
pub struct Selection {
    pub task_ids: Vec<String>,
    pub blocked: BTreeMap<String, Reason>,
}
pub struct TaskStore;

// Git is always fixed argv, without inherited Git redirection or replacement refs.
fn run(mut command: Command, input: &[u8]) -> Result<Vec<u8>> {
    let mut child = command
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()?;
    let mut stdin = child.stdin.take().unwrap();
    let input = input.to_vec();
    let writer = std::thread::spawn(move || stdin.write_all(&input));
    let output = child.wait_with_output()?;
    let written = writer
        .join()
        .map_err(|_| StoreError("input writer panicked".into()))?;
    if !output.status.success() {
        return refuse(String::from_utf8_lossy(&output.stderr).trim().to_string());
    }
    written?;
    Ok(output.stdout)
}
pub(crate) fn git_command(repo: &Path, args: &[&str], index: Option<&Path>) -> Command {
    let mut command = Command::new("/usr/bin/git");
    for (key, _) in std::env::vars_os() {
        if key.to_string_lossy().starts_with("GIT_") {
            command.env_remove(key);
        }
    }
    command
        .args([
            "--literal-pathspecs",
            "-c",
            "core.fsmonitor=false",
            "--no-optional-locks",
            "--no-replace-objects",
            "-C",
        ])
        .arg(repo)
        .args(args);
    if let Some(index) = index {
        command.env("GIT_INDEX_FILE", index);
    }
    command
}
pub(crate) fn git_env(
    repo: &Path,
    args: &[&str],
    input: &[u8],
    index: Option<&Path>,
) -> Result<Vec<u8>> {
    run(git_command(repo, args, index), input)
}
fn git(repo: &Path, args: &[&str]) -> Result<Vec<u8>> {
    git_env(repo, args, &[], None)
}
fn text(bytes: Vec<u8>) -> Result<String> {
    String::from_utf8(bytes).map_err(|e| StoreError(e.to_string()))
}
pub(crate) fn git_text(repo: &Path, args: &[&str]) -> Result<String> {
    Ok(text(git(repo, args)?)?.trim_end_matches('\n').to_string())
}
pub(crate) fn digest(bytes: &[u8]) -> Result<String> {
    let out = text(run(Command::new("sha256sum"), bytes)?)?;
    let hash = out.split_whitespace().next().unwrap_or("");
    if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        return refuse("invalid SHA-256 output");
    }
    Ok(hash.to_owned())
}
fn json_hash(value: &serde_json::Value) -> Result<String> {
    digest(&serde_json::to_vec(value).map_err(|e| StoreError(e.to_string()))?)
}
fn record_path(path: &str) -> bool {
    let p: Vec<_> = path.split('/').collect();
    p.len() == 3
        && p[0] == "tasks"
        && matches!(p[1], "items" | "goals")
        && p[2].strip_suffix(".md").is_some_and(valid_id)
}
fn valid_id(id: &str) -> bool {
    id.as_bytes().first().is_some_and(u8::is_ascii_alphanumeric)
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
}
fn resource(s: &str) -> bool {
    s.as_bytes().first().is_some_and(u8::is_ascii_alphanumeric)
        && s.bytes()
            .all(|b| b.is_ascii_alphanumeric() || b"_./:-".contains(&b))
}
fn valid_date(s: &str) -> bool {
    if !s.is_ascii() || s.len() != 10 || s.as_bytes()[4] != b'-' || s.as_bytes()[7] != b'-' {
        return false;
    }
    let Ok(y) = s[..4].parse::<u32>() else {
        return false;
    };
    let Ok(m) = s[5..7].parse::<u32>() else {
        return false;
    };
    let Ok(d) = s[8..].parse::<u32>() else {
        return false;
    };
    let max = match m {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 => {
            if y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) {
                29
            } else {
                28
            }
        }
        _ => 0,
    };
    y > 0 && d > 0 && d <= max
}
const STRINGS: &[&str] = &["id", "title", "short", "status", "goal", "section", "scope"];
const LISTS: &[&str] = &[
    "depends_on",
    "touches",
    "resources",
    "acceptance",
    "checks",
    "exclusions",
];
const CLOSURE: &[&str] = &[
    "closure",
    "closure_actor",
    "closure_timestamp",
    "closure_reason",
    "closure_evidence",
    "owner_waiver",
    "owner_qualification",
    "waiver_actor",
    "waiver_at",
    "waiver_for",
];
const GRANT: &[&str] = &["live_actor", "live_at", "live_scope"];
const GOAL_REQUIRED: &[&str] = &["id", "title", "priority", "source", "status", "focus"];
fn parse(path: &str, bytes: &[u8]) -> Result<Record> {
    let fail = |key: &str, message: &str| -> StoreError {
        let content = String::from_utf8_lossy(bytes);
        let line = content
            .lines()
            .position(|l| l.split_once('=').is_some_and(|(k, _)| k.trim() == key))
            .map_or(1, |n| n + 1);
        StoreError(format!("{path}:{line}: {message}"))
    };
    let content = std::str::from_utf8(bytes).map_err(|_| fail("", "invalid UTF-8"))?;
    let mut lines = content.split_inclusive('\n');
    if lines.next().map(str::trim) != Some("+++") {
        return Err(fail("", "expected opening +++ delimiter"));
    }
    let mut header = String::new();
    let mut closed = false;
    for line in lines.by_ref() {
        if line.trim() == "+++" {
            closed = true;
            break;
        }
        header.push_str(line);
    }
    if !closed {
        return Err(fail("", "missing closing +++ delimiter"));
    }
    let body = lines.collect::<String>();
    let fields: toml::Table =
        toml::from_str(&header).map_err(|e| fail("", &format!("malformed TOML: {e}")))?;
    if fields.get("schema").and_then(toml::Value::as_integer) != Some(1) {
        return Err(fail("schema", "schema must be 1"));
    }
    let goal = path.starts_with("tasks/goals/");
    let required: Vec<_> = if goal {
        GOAL_REQUIRED.to_vec()
    } else {
        STRINGS
            .iter()
            .chain(LISTS)
            .copied()
            .chain(["rank", "kind", "ownership"])
            .filter(|key| *key != "goal")
            .collect()
    };
    let allowed: BTreeSet<_> = required
        .iter()
        .copied()
        .chain(["schema", "depends_on"])
        .chain(if goal {
            vec![]
        } else {
            CLOSURE
                .iter()
                .chain(GRANT)
                .copied()
                .chain(["goal", "live", "verified_depends_on"])
                .collect()
        })
        .collect();
    for key in fields.keys() {
        if !allowed.contains(key.as_str()) {
            return Err(fail(key, "unknown field"));
        }
    }
    let string_keys: Vec<_> = if goal {
        vec!["id", "title", "source", "status"]
    } else {
        STRINGS
            .iter()
            .chain(CLOSURE)
            .copied()
            .chain(["live_actor", "live_at"])
            .collect()
    };
    for key in string_keys {
        if let Some(value) = fields.get(key)
            && value.as_str().is_none_or(|s| s.trim().is_empty())
        {
            return Err(fail(key, "expected nonempty string"));
        }
    }
    let id = fields.get("id").and_then(toml::Value::as_str).unwrap_or("");
    if !valid_id(id) || Path::new(path).file_stem().and_then(|s| s.to_str()) != Some(id) {
        return Err(fail("id", "invalid ID or filename/ID mismatch"));
    }
    let integer = if goal { "priority" } else { "rank" };
    if fields
        .get(integer)
        .is_some_and(|v| v.as_integer().is_none())
    {
        return Err(fail(integer, "expected integer"));
    }
    let get = |key: &str| fields.get(key).and_then(toml::Value::as_str).unwrap_or("");
    for (key, choices) in if goal {
        vec![("status", vec!["unmet", "partial", "unverified", "met"])]
    } else {
        vec![
            ("status", vec!["open", "done", "superseded"]),
            ("section", vec!["Now", "Next", "Needs decision"]),
            (
                "kind",
                vec!["unknown", "implementation", "plan", "inspection"],
            ),
            (
                "ownership",
                vec!["unknown", "worker", "coordinator", "owner"],
            ),
            ("live", vec!["denied", "authorized"]),
            ("closure", vec!["manual", "coordinator_verified"]),
        ]
    } {
        if fields.contains_key(key) && !choices.contains(&get(key)) {
            return Err(fail(key, "unknown value"));
        }
    }
    if goal {
        for key in &required {
            if !fields.contains_key(*key) {
                return Err(fail(key, "missing goal field"));
            }
        }
        if fields.get("focus").and_then(toml::Value::as_bool).is_none() {
            return Err(fail("focus", "expected boolean"));
        }
    }
    for key in if goal {
        vec!["depends_on"]
    } else {
        LISTS
            .iter()
            .copied()
            .chain(["verified_depends_on", "live_scope"])
            .collect()
    } {
        if let Some(value) = fields.get(key) {
            let Some(array) = value.as_array() else {
                return Err(fail(key, "expected array of strings"));
            };
            if array.iter().any(|v| {
                !v.as_str().is_some_and(|s| {
                    !s.trim().is_empty()
                        && (goal
                            || !serde_json::from_str::<serde_json::Value>(s)
                                .is_ok_and(|v| v.is_array()))
                        && (!goal || valid_id(s))
                        && (!matches!(key, "resources" | "live_scope") || resource(s))
                })
            }) {
                return Err(fail(
                    key,
                    "expected nonempty strings, not encoded lists or invalid tokens",
                ));
            }
            if key == "live_scope" && array.is_empty() {
                return Err(fail(key, "live_scope must not be empty"));
            }
        }
    }
    let lists = |key: &str| -> Vec<&str> {
        fields
            .get(key)
            .and_then(toml::Value::as_array)
            .map(|a| a.iter().filter_map(toml::Value::as_str).collect())
            .unwrap_or_default()
    };
    if lists("verified_depends_on")
        .iter()
        .any(|id| !lists("depends_on").contains(id))
    {
        return Err(fail(
            "verified_depends_on",
            "must be a subset of depends_on",
        ));
    }
    for key in ["live_at", "waiver_at"] {
        if fields.contains_key(key) && !valid_date(get(key)) {
            return Err(fail(key, "expected YYYY-MM-DD"));
        }
    }
    if get("closure") == "manual" {
        for key in ["closure_actor", "closure_timestamp", "closure_reason"] {
            if !fields.contains_key(key) {
                return Err(fail(
                    key,
                    "manual closure needs actor, timestamp and reason",
                ));
            }
        }
    }
    if GRANT.iter().any(|k| fields.contains_key(*k)) {
        if get("live") != "authorized" {
            return Err(fail("live", "grant requires live = authorized"));
        }
        if GRANT.iter().all(|k| fields.contains_key(*k)) {
            let resources = lists("resources");
            let touches = lists("touches");
            let scope = lists("live_scope");
            if scope.iter().any(|s| {
                !resources.contains(s)
                    && !touches
                        .iter()
                        .any(|p| p == s || p.starts_with(&format!("{}/", s.trim_end_matches('/'))))
            }) || resources
                .iter()
                .any(|r| matches!(*r, "live" | "exclusive") && !scope.contains(r))
            {
                return Err(fail("live_scope", "grant does not cover declared scope"));
            }
        }
    }
    let waiver = ["waiver_actor", "waiver_at", "waiver_for"];
    if waiver.iter().any(|k| fields.contains_key(*k)) {
        if get("owner_waiver").is_empty() && get("owner_qualification").is_empty() {
            return Err(fail(
                "waiver_for",
                "waiver fields require owner attestation",
            ));
        }
        if waiver.iter().all(|k| fields.contains_key(*k))
            && !lists("acceptance")
                .into_iter()
                .chain(lists("checks"))
                .any(|s| s == get("waiver_for"))
        {
            return Err(fail(
                "waiver_for",
                "must name an Acceptance or Checks criterion",
            ));
        }
    }
    let mut missing: Vec<String> = required
        .iter()
        .filter(|k| !fields.contains_key(**k))
        .map(|k| k.to_string())
        .collect();
    if !goal {
        for key in ["acceptance", "checks", "touches"] {
            if fields.contains_key(key) && lists(key).is_empty() {
                missing.push(key.into());
            }
        }
    }
    if matches!(get("status"), "done" | "superseded") {
        missing.retain(|k| matches!(k.as_str(), "id" | "title" | "status"));
    }
    let mut contract = serde_json::Map::new();
    for key in if goal {
        vec!["priority", "source", "status", "focus", "depends_on"]
    } else {
        vec![
            "scope",
            "acceptance",
            "checks",
            "depends_on",
            "touches",
            "resources",
            "kind",
            "ownership",
            "live",
            "exclusions",
        ]
    } {
        let default = match key {
            "kind" | "ownership" => serde_json::json!("unknown"),
            "live" => serde_json::json!("denied"),
            "depends_on" if goal => serde_json::json!([]),
            _ => serde_json::Value::Null,
        };
        contract.insert(
            key.into(),
            fields
                .get(key)
                .map(|v| serde_json::to_value(v).unwrap())
                .unwrap_or(default),
        );
    }
    if !goal {
        contract.insert(
            "section_group".into(),
            if matches!(get("section"), "Now" | "Next") {
                serde_json::json!("runnable")
            } else {
                fields
                    .get("section")
                    .map(|v| serde_json::to_value(v).unwrap())
                    .unwrap_or_default()
            },
        );
        for key in GRANT
            .iter()
            .copied()
            .chain(waiver)
            .chain(["verified_depends_on"])
        {
            if let Some(v) = fields.get(key)
                && !v.as_array().is_some_and(Vec::is_empty)
            {
                contract.insert(key.into(), serde_json::to_value(v).unwrap());
            }
        }
    }
    Ok(Record {
        id: id.into(),
        title: get("title").into(),
        path: path.into(),
        body,
        record_revision: digest(bytes)?,
        contract_hash: json_hash(&contract.into())?,
        missing_fields: missing,
        receipt_valid: false,
        fields,
    })
}

impl TaskStore {
    pub fn read_at(repo: &Path, revision: &str) -> Result<Snapshot> {
        let pinned = git_text(
            repo,
            &[
                "rev-parse",
                "--verify",
                "--end-of-options",
                &format!("{revision}^{{commit}}"),
            ],
        )?;
        let (records, evidence) = read_tree(repo, &pinned)?;
        snapshot(repo, &pinned, records, &evidence)
    }
}
type FileBytes = BTreeMap<String, Vec<u8>>;
fn read_tree(repo: &Path, revision: &str) -> Result<(FileBytes, FileBytes)> {
    let entries = git(
        repo,
        &["ls-tree", "-rtz", "--full-tree", revision, "--", "tasks"],
    )?;
    let mut files = Vec::new();
    let mut has_store = false;
    for entry in entries.split(|b| *b == 0).filter(|e| !e.is_empty()) {
        let Some(tab) = entry.iter().position(|b| *b == b'\t') else {
            return refuse("invalid ls-tree output");
        };
        let (meta, path) = (&entry[..tab], &entry[tab + 1..]);
        let path =
            std::str::from_utf8(path).map_err(|_| StoreError("tasks/:1: non-UTF-8 path".into()))?;
        let meta = std::str::from_utf8(meta).unwrap();
        let parts: Vec<_> = meta.split_whitespace().collect();
        if matches!(path, "tasks" | "tasks/items" | "tasks/goals") {
            if parts[0] != "040000" || parts[1] != "tree" {
                return refuse(format!("{path}:1: expected store directory"));
            }
            if path == "tasks" {
                has_store = true;
            }
            continue;
        }
        if path.starts_with("tasks/items/") || path.starts_with("tasks/goals/") {
            if !record_path(path) || !matches!(parts[0], "100644" | "100755") || parts[1] != "blob"
            {
                return refuse(format!("{path}:1: expected regular tasks record"));
            }
        } else if !(path.starts_with("tasks/evidence/")
            && matches!(parts[0], "100644" | "100755")
            && parts[1] == "blob")
        {
            continue;
        }
        files.push((path.to_owned(), parts[2].to_owned()));
    }
    if !has_store {
        return refuse("tasks/:1: no task store at pinned revision");
    }
    let input = files
        .iter()
        .map(|(_, oid)| format!("{oid}\n"))
        .collect::<String>();
    let output = git_env(repo, &["cat-file", "--batch"], input.as_bytes(), None)?;
    let mut rest = output.as_slice();
    let mut records = BTreeMap::new();
    let mut evidence = BTreeMap::new();
    for (path, _) in files {
        let end = rest
            .iter()
            .position(|b| *b == b'\n')
            .ok_or_else(|| StoreError("truncated Git batch".into()))?;
        let header = std::str::from_utf8(&rest[..end]).unwrap();
        let size: usize = header
            .split_whitespace()
            .nth(2)
            .and_then(|n| n.parse().ok())
            .ok_or_else(|| StoreError("invalid Git batch".into()))?;
        rest = &rest[end + 1..];
        if rest.len() < size + 1 {
            return refuse("truncated Git blob");
        }
        let bytes = rest[..size].to_vec();
        rest = &rest[size + 1..];
        (if record_path(&path) {
            &mut records
        } else {
            &mut evidence
        })
        .insert(path, bytes);
    }
    Ok((records, evidence))
}
fn snapshot(
    repo: &Path,
    revision: &str,
    records: BTreeMap<String, Vec<u8>>,
    evidence: &BTreeMap<String, Vec<u8>>,
) -> Result<Snapshot> {
    let mut tasks = BTreeMap::new();
    let mut goals = BTreeMap::new();
    let mut ids = BTreeSet::new();
    for (path, bytes) in &records {
        let mut record = parse(path, bytes)?;
        if !ids.insert(record.id.clone()) {
            return refuse(format!("{path}:1: duplicate ID {}", record.id));
        }
        if path.starts_with("tasks/goals/") {
            goals.insert(record.id.clone(), record);
        } else {
            record.receipt_valid = receipt_valid(repo, revision, &record, evidence);
            tasks.insert(record.id.clone(), record);
        }
    }
    if goals.values().filter(|r| r.focus()).count() > 1 {
        return refuse("tasks/goals/:1: only one goal may have focus");
    }
    for goal in goals.values() {
        for dep in goal.strings("depends_on") {
            if !goals.contains_key(dep) {
                return refuse(format!("{}:1: unknown goal dependency {dep}", goal.path));
            }
        }
    }
    for task in tasks.values() {
        if !task.string("goal").is_empty() && !goals.contains_key(task.string("goal")) {
            return refuse(format!("{}:1: unknown goal", task.path));
        }
    }
    Ok(Snapshot {
        revision: revision.into(),
        records,
        tasks,
        goals,
    })
}
fn receipt_valid(
    repo: &Path,
    revision: &str,
    record: &Record,
    evidence: &BTreeMap<String, Vec<u8>>,
) -> bool {
    if record.string("closure") != "coordinator_verified"
        || record.string("closure_evidence") != format!("tasks/evidence/{}.toml", record.id)
    {
        return false;
    }
    let Some(bytes) = evidence.get(record.string("closure_evidence")) else {
        return false;
    };
    let Ok(s) = std::str::from_utf8(bytes) else {
        return false;
    };
    let Ok(receipt) = toml::from_str::<toml::Table>(s) else {
        return false;
    };
    let get = |key: &str| receipt.get(key).and_then(toml::Value::as_str).unwrap_or("");
    if receipt.get("schema").and_then(toml::Value::as_integer) != Some(1)
        || get("task") != record.id
        || get("contract_hash") != record.contract_hash
        || get("result") != "pass"
        || get("review") != "passed"
    {
        return false;
    }
    for key in ["candidate", "integration", "tree"] {
        let s = get(key);
        if !matches!(s.len(), 40 | 64)
            || !s
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        {
            return false;
        }
    }
    let check = || -> Result<bool> {
        if git_text(repo, &["cat-file", "-t", get("candidate")])? != "commit"
            || git_text(repo, &["cat-file", "-t", get("integration")])? != "commit"
            || git_text(repo, &["cat-file", "-t", get("tree")])? != "tree"
        {
            return Ok(false);
        }
        let integration = git_text(repo, &["cat-file", "commit", get("integration")])?;
        let headers = integration.split("\n\n").next().unwrap();
        let parents: Vec<_> = headers
            .lines()
            .filter_map(|l| l.strip_prefix("parent "))
            .collect();
        Ok(parents.len() == 2
            && parents[1] == get("candidate")
            && headers
                .lines()
                .any(|l| l == format!("tree {}", get("tree"))))
        .and_then(|valid| {
            git(
                repo,
                &["merge-base", "--is-ancestor", get("integration"), revision],
            )?;
            Ok(valid)
        })
    };
    check().unwrap_or(false)
}
impl Snapshot {
    pub fn revision(&self) -> &str {
        &self.revision
    }
    pub fn records(&self) -> &BTreeMap<String, Vec<u8>> {
        &self.records
    }
    pub fn tasks(&self) -> &BTreeMap<String, Record> {
        &self.tasks
    }
    pub fn goals(&self) -> &BTreeMap<String, Record> {
        &self.goals
    }
    pub fn select(&self, scope: &Scope) -> Result<Selection> {
        let today = text(run(
            {
                let mut c = Command::new("date");
                c.arg("+%F");
                c
            },
            &[],
        )?)?;
        self.select_on(scope, today.trim())
    }
    /// Explicit local calendar date for reproducible expiring-hold decisions.
    pub fn select_on(&self, scope: &Scope, today: &str) -> Result<Selection> {
        if !valid_date(today) {
            return refuse("invalid selection date");
        }
        let mut selected = Vec::new();
        let mut blocked = BTreeMap::new();
        for id in &scope.task_ids {
            if !self.tasks.contains_key(id) {
                blocked.insert(
                    id.clone(),
                    Reason {
                        code: "UNKNOWN_TASK".into(),
                        detail: id.clone(),
                    },
                );
            }
        }
        for task in self
            .tasks
            .values()
            .filter(|t| scope.task_ids.is_empty() || scope.task_ids.contains(&t.id))
        {
            if let Some(reason) = self.blocking(task, today) {
                blocked.insert(task.id.clone(), reason);
            } else {
                selected.push(task);
            }
        }
        selected.sort_by_key(|t| {
            let g = self.goals.get(t.string("goal"));
            (
                !g.is_some_and(Record::focus),
                if t.string("section") == "Now" { 0 } else { 1 },
                t.number("rank"),
                g.map_or(100, |g| g.number("priority")),
                match g.map_or("unmet", |g| g.string("status")) {
                    "unverified" => 0,
                    "partial" => 1,
                    "unmet" => 2,
                    _ => 3,
                },
                &t.id,
            )
        });
        Ok(Selection {
            task_ids: selected.into_iter().map(|t| t.id.clone()).collect(),
            blocked,
        })
    }
    fn blocking(&self, task: &Record, today: &str) -> Option<Reason> {
        let reason = |code: &str, detail: &str| {
            Some(Reason {
                code: code.into(),
                detail: detail.into(),
            })
        };
        match task.string("status") {
            "done" => return reason("DONE", ""),
            "superseded" => return reason("SUPERSEDED", ""),
            _ => (),
        }
        if !matches!(task.string("section"), "Now" | "Next") {
            return reason("NEEDS_DECISION", task.string("section"));
        }
        if task.draft() {
            return reason("DRAFT", &task.missing_fields.join(", "));
        }
        if let Some(holder) = task
            .body
            .lines()
            .filter_map(|l| l.strip_prefix("- Held by: "))
            .next_back()
        {
            let until = holder.match_indices("until ").find_map(|(at, _)| {
                if holder[..at]
                    .chars()
                    .next_back()
                    .is_some_and(|c| c.is_alphanumeric() || c == '_')
                {
                    return None;
                }
                let tail = &holder[at + 6..];
                let date = tail.get(..10).filter(|s| valid_date(s))?;
                if tail[10..]
                    .chars()
                    .next()
                    .is_some_and(|c| c.is_alphanumeric() || c == '_')
                {
                    None
                } else {
                    Some(date)
                }
            });
            if until.is_none_or(|date| date >= today) {
                return reason("HELD", holder.trim());
            }
        }
        if let Some(goal) = self.goals.get(task.string("goal")) {
            if goal.string("status") == "met" {
                return reason("GOAL_MET", &goal.id);
            }
            for dep in goal.strings("depends_on") {
                if self.goals[dep].string("status") != "met" {
                    return reason("GOAL_DEPENDENCY_UNMET", dep);
                }
            }
        } else if !task.string("goal").is_empty() {
            return reason("NO_GOAL", task.string("goal"));
        }
        for dep in task.strings("depends_on") {
            let Some(prerequisite) = self.tasks.get(dep).filter(|t| t.string("status") == "done")
            else {
                return reason("DEPENDENCY_UNFINISHED", dep);
            };
            if task.strings("verified_depends_on").contains(&dep) && !prerequisite.qualified() {
                return reason("DEPENDENCY_UNVERIFIED", dep);
            }
        }
        None
    }
}

#[derive(Clone, Debug)]
pub struct PendingEdit {
    pub record_revisions: BTreeMap<String, String>,
    pub expected_revision: String,
    pub paths: Vec<PathBuf>,
}
/// Publication input, deliberately without a Snapshot/select conversion.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct PendingSnapshot {
    pub base_head: String,
    pub branch: String,
    pub tree: String,
    pub captured_bytes: BTreeMap<String, Vec<u8>>,
    pub token: String,
}
#[derive(Clone, Debug)]
pub struct CommittedRevision(pub String);

pub struct TaskService {
    repo: PathBuf,
}
static NEXT: AtomicU64 = AtomicU64::new(0);
struct Scratch(PathBuf);
impl Scratch {
    fn new() -> Result<Self> {
        loop {
            let p = std::env::temp_dir().join(format!(
                "autowork-store-{}-{}",
                std::process::id(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            match fs::create_dir(&p) {
                Ok(()) => return Ok(Self(p)),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => return Err(e.into()),
            }
        }
    }
}
impl Drop for Scratch {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
pub(crate) struct TaskLock {
    _file: File,
    git_dir: PathBuf,
}
impl TaskService {
    pub fn new(repo: impl AsRef<Path>) -> Result<Self> {
        let repo = fs::canonicalize(repo)?;
        if git_text(&repo, &["rev-parse", "--show-toplevel"])? != repo.to_string_lossy() {
            return refuse("TaskService requires repository root");
        }
        Ok(Self { repo })
    }
    pub(crate) fn repository(&self) -> &Path {
        &self.repo
    }
    pub(crate) fn lock(&self) -> Result<TaskLock> {
        let git_dir = PathBuf::from(git_text(&self.repo, &["rev-parse", "--absolute-git-dir"])?);
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(git_dir.join("autowork-tasks.lock"))?;
        file.lock_exclusive()?;
        if git_dir.join("autowork-tasks.transaction").exists() {
            return refuse("Python task transaction requires its owning runtime recovery");
        }
        Ok(TaskLock {
            _file: file,
            git_dir,
        })
    }
    /// Read exact current bytes under the task lock; apply rechecks the same digest.
    pub fn record_for_edit(&self, id: &str, expected_digest: &str) -> Result<Vec<u8>> {
        if id.is_empty()
            || !id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        {
            return refuse("invalid task ID");
        }
        let _lock = self.lock()?;
        let records = self.working_records()?;
        let bytes = records
            .get(&format!("tasks/items/{id}.md"))
            .ok_or_else(|| StoreError("unknown task".into()))?;
        if digest(bytes)? != expected_digest {
            return refuse("stale expected record revision");
        }
        Ok(bytes.clone())
    }
    pub fn recover(&self) -> Result<()> {
        let lock = self.lock()?;
        self.undo(&lock)
    }
    /// Revisions are the full base commit and SHA-256 record bytes (empty for a new path).
    pub fn apply(&self, expected_revision: &str, proposal: &PlanProposal) -> Result<PendingEdit> {
        let lock = self.lock()?;
        self.undo(&lock)?;
        let base = TaskStore::read_at(&self.repo, "HEAD")?;
        if base.revision != expected_revision || proposal.expected_revision != expected_revision {
            return refuse("stale proposal base revision");
        }
        let mut records = self.working_records()?;
        let before = records.clone();
        let mut edits = Vec::new();
        let mut paths = BTreeSet::new();
        for change in &proposal.record_changes {
            let Some(path) = change.path.to_str().filter(|p| record_path(p)) else {
                return refuse("proposal path is not a task/goal record");
            };
            if !paths.insert(path.to_string()) {
                return refuse("duplicate proposal path");
            }
            let old = records.get(path);
            let revision = match old {
                Some(b) => digest(b)?,
                None => String::new(),
            };
            if revision != change.expected_revision {
                return refuse(format!("{path}: stale expected record revision"));
            }
            planner_authority(path, old.map(Vec::as_slice), &change.proposed_bytes)?;
            edits.push(JournalRecord {
                path: path.into(),
                before: old.cloned(),
                after: change.proposed_bytes.clone(),
            });
            records.insert(path.into(), change.proposed_bytes.clone());
        }
        let (_, evidence) = read_tree(&self.repo, &base.revision)?;
        snapshot(&self.repo, &base.revision, records.clone(), &evidence)?;
        // Compare all inputs, not just the edited paths, before making the journal durable.
        if self.working_records()? != before
            || git_text(&self.repo, &["rev-parse", "HEAD"])? != base.revision
        {
            return refuse("store or HEAD changed during proposal validation");
        }
        for edit in &edits {
            if side_path(&self.repo.join(&edit.path), "undo").exists() {
                return refuse("reconcile preserved external undo bytes before writing");
            }
        }
        let journal = lock.git_dir.join("autowork-rust-tasks.transaction");
        atomic_bytes(
            &journal,
            &serde_json::to_vec(&edits).map_err(|e| StoreError(e.to_string()))?,
        )?;
        let result = (|| -> Result<()> {
            for edit in &edits {
                let path = self.repo.join(&edit.path);
                fs::create_dir_all(path.parent().unwrap())?;
                if read_regular(&path)? != edit.before {
                    return refuse("record changed before replace");
                }
                atomic_bytes(&path, &edit.after)?;
            }
            if self.working_records()? != records
                || git_text(&self.repo, &["rev-parse", "HEAD"])? != base.revision
            {
                return refuse("store or HEAD changed during proposal write");
            }
            Ok(())
        })();
        if let Err(e) = result {
            self.undo(&lock)?;
            return Err(e);
        }
        fs::remove_file(&journal)?;
        sync_dir(&lock.git_dir)?;
        let record_revisions = edits
            .iter()
            .map(|edit| Ok((edit.path.clone(), digest(&edit.after)?)))
            .collect::<Result<BTreeMap<_, _>>>()?;
        Ok(PendingEdit {
            record_revisions,
            expected_revision: base.revision,
            paths: paths.into_iter().map(PathBuf::from).collect(),
        })
    }
    /// Does not recover implicitly: inspecting a partial transaction must change nothing.
    pub fn capture_pending(&self) -> Result<PendingSnapshot> {
        let lock = self.lock()?;
        self.capture_locked(&lock)
    }
    pub(crate) fn capture_locked(&self, lock: &TaskLock) -> Result<PendingSnapshot> {
        if lock
            .git_dir
            .join("autowork-rust-tasks.transaction")
            .exists()
        {
            return refuse("interrupted task transaction; call recover before capture");
        }
        let base_head = git_text(&self.repo, &["rev-parse", "--verify", "HEAD^{commit}"])?;
        let branch = git_text(&self.repo, &["symbolic-ref", "--quiet", "HEAD"])?;
        let (base_records, evidence) = read_tree(&self.repo, &base_head)?;
        let captured_bytes = self.working_records()?;
        snapshot(&self.repo, &base_head, captured_bytes.clone(), &evidence)?;
        let scratch = Scratch::new()?;
        let index = scratch.0.join("index");
        git_env(&self.repo, &["read-tree", &base_head], &[], Some(&index))?;
        for path in base_records
            .keys()
            .filter(|p| !captured_bytes.contains_key(*p))
        {
            git_env(
                &self.repo,
                &["update-index", "--force-remove", "--", path],
                &[],
                Some(&index),
            )?;
        }
        for (path, bytes) in &captured_bytes {
            if base_records.get(path) == Some(bytes) {
                continue;
            }
            let oid = text(git_env(
                &self.repo,
                &["hash-object", "-w", "--stdin"],
                bytes,
                None,
            )?)?;
            let entry = git_text(&self.repo, &["ls-tree", &base_head, "--", path])?;
            let mode = entry.split_whitespace().next().unwrap_or("100644");
            git_env(
                &self.repo,
                &[
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    &format!("{mode},{},{}", oid.trim(), path),
                ],
                &[],
                Some(&index),
            )?;
        }
        let tree = text(git_env(&self.repo, &["write-tree"], &[], Some(&index))?)?
            .trim()
            .to_owned();
        if git_text(&self.repo, &["rev-parse", "HEAD"])? != base_head
            || git_text(&self.repo, &["symbolic-ref", "--quiet", "HEAD"])? != branch
            || self.working_records()? != captured_bytes
        {
            return refuse("capture inputs changed; retry");
        }
        let token = json_hash(
            &serde_json::json!({"base_head":base_head,"branch":branch,"tree":tree,"captured_bytes":captured_bytes}),
        )?;
        Ok(PendingSnapshot {
            base_head,
            branch,
            tree,
            captured_bytes,
            token,
        })
    }
    fn working_records(&self) -> Result<BTreeMap<String, Vec<u8>>> {
        let mut records = BTreeMap::new();
        let root = self.repo.join("tasks");
        if !fs::symlink_metadata(&root)?.file_type().is_dir() {
            return refuse("tasks/:1: expected directory");
        }
        for kind in ["items", "goals"] {
            let dir = root.join(kind);
            match fs::symlink_metadata(&dir) {
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
                Ok(m) if m.file_type().is_dir() => (),
                _ => return refuse("expected regular store directory"),
            }
            for entry in fs::read_dir(dir)? {
                let path = entry?.path();
                let name = path
                    .strip_prefix(&self.repo)
                    .unwrap()
                    .to_str()
                    .ok_or_else(|| StoreError("non-UTF-8 record path".into()))?
                    .to_owned();
                if !record_path(&name) {
                    return refuse(format!("{name}:1: invalid record path"));
                }
                records.insert(
                    name,
                    read_regular(&path)?.ok_or_else(|| StoreError("record disappeared".into()))?,
                );
            }
        }
        Ok(records)
    }
    fn undo(&self, lock: &TaskLock) -> Result<()> {
        let journal = lock.git_dir.join("autowork-rust-tasks.transaction");
        let Some(bytes) = read_regular(&journal)? else {
            return Ok(());
        };
        let edits: Vec<JournalRecord> = serde_json::from_slice(&bytes)
            .map_err(|e| StoreError(format!("invalid task journal: {e}")))?;
        for edit in &edits {
            if !record_path(&edit.path) {
                return refuse("invalid journal record path");
            }
        }
        let mut conflicts = Vec::new();
        for edit in edits.iter().rev() {
            let path = self.repo.join(&edit.path);
            // Refuse linked directories before touching any recovery pathname.
            for dir in [
                self.repo.join("tasks"),
                path.parent().unwrap().to_path_buf(),
            ] {
                match fs::symlink_metadata(dir) {
                    Ok(m) if m.file_type().is_dir() => (),
                    Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                    _ => return refuse("unsafe recovery directory"),
                }
            }
            let staged = side_path(&path, "tmp");
            match fs::remove_file(&staged) {
                Ok(()) => (),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
                Err(e) => return Err(e.into()),
            }
            let saved = side_path(&path, "undo");
            if read_recovery(&saved)?.is_none() {
                let current = read_recovery(&path)?;
                if current == edit.before {
                    continue;
                }
                if current.as_deref() != Some(edit.after.as_slice()) {
                    conflicts.push(edit.path.clone());
                    continue;
                }
                fs::rename(&path, &saved)?;
                sync_dir(path.parent().unwrap())?;
            }
            if read_recovery(&saved)?.as_deref() != Some(edit.after.as_slice()) {
                match fs::hard_link(&saved, &path) {
                    Ok(()) => sync_dir(path.parent().unwrap())?,
                    Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
                    Err(e) => return Err(e.into()),
                }
                let a = fs::symlink_metadata(&saved)?;
                let b = fs::symlink_metadata(&path)?;
                if a.dev() == b.dev() && a.ino() == b.ino() {
                    fs::remove_file(&saved)?;
                    sync_dir(path.parent().unwrap())?;
                } else {
                    conflicts.push(
                        saved
                            .strip_prefix(&self.repo)
                            .unwrap()
                            .to_string_lossy()
                            .into_owned(),
                    );
                }
                conflicts.push(edit.path.clone());
                continue;
            }
            if let Some(before) = &edit.before {
                let staged = stage(&path, before)?;
                match fs::hard_link(&staged, &path) {
                    Ok(()) => sync_dir(path.parent().unwrap())?,
                    Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
                    Err(e) => return Err(e.into()),
                }
                fs::remove_file(staged)?;
            }
            if read_recovery(&path)? != edit.before {
                conflicts.push(edit.path.clone());
            }
            fs::remove_file(saved)?;
            sync_dir(path.parent().unwrap())?;
        }
        // Keep the journal when external bytes conflict; original bytes remain recoverable.
        if !conflicts.is_empty() {
            return refuse(format!(
                "external edits preserved; reconcile journal and paths: {}",
                conflicts.join(", ")
            ));
        }
        fs::remove_file(journal)?;
        sync_dir(&lock.git_dir)
    }
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct JournalRecord {
    path: String,
    before: Option<Vec<u8>>,
    after: Vec<u8>,
}
fn read_regular(path: &Path) -> Result<Option<Vec<u8>>> {
    match fs::symlink_metadata(path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Ok(m) if m.file_type().is_file() && m.nlink() == 1 => Ok(Some(fs::read(path)?)),
        Ok(_) => refuse(format!("{}: expected private regular file", path.display())),
        Err(e) => Err(e.into()),
    }
}
// Recovery only links/renames saved inodes; it never truncates an externally linked file.
fn read_recovery(path: &Path) -> Result<Option<Vec<u8>>> {
    match fs::symlink_metadata(path) {
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Ok(m) if m.file_type().is_file() => Ok(Some(fs::read(path)?)),
        Ok(_) => refuse(format!(
            "{}: expected regular recovery file",
            path.display()
        )),
        Err(e) => Err(e.into()),
    }
}
fn sync_dir(path: &Path) -> Result<()> {
    File::open(path)?.sync_all()?;
    Ok(())
}
fn side_path(path: &Path, suffix: &str) -> PathBuf {
    path.with_file_name(format!(
        ".{}.autowork-rust.{suffix}",
        path.file_name().unwrap().to_string_lossy()
    ))
}
fn stage(path: &Path, bytes: &[u8]) -> Result<PathBuf> {
    let staged = side_path(path, "tmp");
    match fs::remove_file(&staged) {
        Ok(()) => (),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(e) => return Err(e.into()),
    }
    let mut f = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&staged)?;
    f.write_all(bytes)?;
    f.sync_all()?;
    Ok(staged)
}
pub(crate) fn atomic_bytes(path: &Path, bytes: &[u8]) -> Result<()> {
    let staged = stage(path, bytes)?;
    fs::rename(staged, path)?;
    sync_dir(path.parent().unwrap())
}
fn protected_notes(body: &str) -> Vec<String> {
    body.lines()
        .filter(|line| {
            let line = line
                .trim_start()
                .trim_start_matches('-')
                .trim_start()
                .to_ascii_lowercase();
            line.split_once(':').is_some_and(|(key, _)| {
                matches!(
                    key.trim(),
                    "evidence"
                        | "verified"
                        | "held by"
                        | "owner decision"
                        | "owner waiver"
                        | "owner qualification"
                        | "live authorization"
                )
            })
        })
        .map(str::to_owned)
        .collect()
}
fn planner_authority(path: &str, before: Option<&[u8]>, after: &[u8]) -> Result<()> {
    let new = parse(path, after)?;
    let old = before.map(|b| parse(path, b)).transpose()?;
    for key in CLOSURE.iter().chain(GRANT) {
        if new.field(key) != old.as_ref().and_then(|o| o.field(key)) {
            return refuse(format!(
                "{path}: planner cannot change closure/owner authority {key}"
            ));
        }
    }
    let previous = |key: &str, default: &str| {
        old.as_ref()
            .map(|o| o.string(key))
            .filter(|v| !v.is_empty())
            .unwrap_or(default)
            .to_owned()
    };
    if path.starts_with("tasks/goals/") {
        if new.string("status") != previous("status", "unmet") {
            return refuse("planner cannot change goal progress");
        }
    } else {
        let status = if new.string("status").is_empty() {
            "open"
        } else {
            new.string("status")
        };
        let live = if new.string("live").is_empty() {
            "denied"
        } else {
            new.string("live")
        };
        if status != previous("status", "open")
            || live != previous("live", "denied")
            || old
                .as_ref()
                .is_some_and(|o| new.string("ownership") != o.string("ownership"))
            || new.strings("resources").contains(&"live")
                != old
                    .as_ref()
                    .is_some_and(|o| o.strings("resources").contains(&"live"))
        {
            return refuse("planner cannot change status, ownership or live gate");
        }
    }
    if protected_notes(&new.body)
        != old
            .as_ref()
            .map(|o| protected_notes(&o.body))
            .unwrap_or_default()
    {
        return refuse("planner cannot change evidence, owner notes or holds");
    }
    Ok(())
}
