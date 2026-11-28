# Orbi API and host inventory

**Use Kit `/orbi version --json` to identify one deployment’s engine, `/orbi status --json` to inspect one repository, `/orbi status all --json` for observable local host services, and GitHub to establish what was delivered.** These answer different questions. In particular, bare **`/orbi`** in Kit means *status*; bare **`orbi`** in a shell runs a **real delivery tick**. Use `orbi --version` to identify a binary without running a tick.

This reference covers Kit’s [lifecycle client](skills/orbi/SKILL.md) and the self-hosted engine at [Orbi v0.7.56](https://github.com/orbi-build/orbi/tree/v0.7.56). Check the deployed version before relying on a flag or format. The engine has no documented HTTP control plane to enumerate deployments, enqueue issues or restart workers. Its [public interface inventory](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/public-contracts.mdx) defines what integrators can rely on; the optional exporter is monitoring, not that API. Explicit `/orbi start`, plain `/orbi update`, and `install.sh` with Orbi selected authorize activation after verified unit and file ownership, a validated release pin and a passing `orbi check`. Activation does not qualify live delivery. See [Kit lifecycle](docs/github-native.md#kit-lifecycle-skill).

## Inspect one repository with Kit

Use `/orbi help` in Pi, `/kit:orbi help` in Claude Code, or `$kit:orbi help` in Codex. Help requires no repository or deployment. For scripts, from the Kit checkout:

```sh
python3 -B skills/orbi/scripts/orbi_control.py help --json
python3 -B skills/orbi/scripts/orbi_control.py version --repo-dir /path/to/canonical/repo --json
python3 -B skills/orbi/scripts/orbi_control.py status --repo-dir /path/to/canonical/repo --json
```

`--repo-dir` selects the delivery repository; `--config` selects an existing native deployment config. Distinguish `absent` (no deployment found) from `unavailable` (evidence could not be read). Configured slots, enabled timers, active timers and running services are separate observations. None proves a model answered or a PR merged.

### Deployment engine version

`/orbi version [--repo-dir PATH] [--config PATH] [--json]` works on Linux and macOS.
Portable hosts forward it unchanged to one read-only helper invocation. It uses
status's canonical repository/config discovery and safe binding rules; explicit
missing/foreign or ambiguous targets fail with the existing error and repair,
without fallback to another deployment.

Text and JSON identify the repository, config, deploy home and unit name. JSON
returns `action: version`, `platform`, `repo`, `repo_dir` and `deployment` with
`state: configured` and `engine`: verified `version`, observed `revision`,
verification `state`, `provenance` or `reason`, and `selected_source`. The engine
uses the same pin/manifest/clean-source evidence as repository status, but omits
`bootstrap_cli`. An observed revision alone is not a verified release. Unknown
metadata returns `state: unknown` and a reason, not a guessed version. No deployment
returns `deployment.state: absent` and `engine.state: unconfigured`, with null
version/revision and a reason.

This action does not run full status, a bootstrap/global CLI, latest-release
lookup, scheduler/queue/worker/authentication/network probes, acquire locks or
write files. There is no `version all`; mutation/bootstrap flags, including
`--dry-run`, are refused before probes. Bare `/orbi` remains status, and upstream
`orbi --version` still identifies only that binary, not a selected deployment.

### Deployment and per-slot status receipt

Human text leads with the repository, deployed package version + revision and
metadata provenance, then scheduler capacity/activity and slots. JSON preserves
legacy `deployment`, `scheduler`, `queue` and `doctor` fields and adds:

- `deployment.engine`: verified deployment `pyproject.toml` version, checked against
  the pinned Git revision's manifest and clean tracked package source. Unknown or
  mismatching metadata stays unknown; `selected_source` identifies pin/source
  evidence separately. `bootstrap_cli` is the bootstrap executable's unscoped
  `--version`, explicitly unverified as deployment proof, with match/mismatch/unknown
  comparison. Neither CLI version nor source metadata proves live delivery.
- `deployment.last_lifecycle`: newest local Kit receipt, or null when unavailable.
  It contains `timestamp` (UTC), `action`, `argv` (action and flag names only),
  `user` (host account) and `result` (status or error code). `status all` returns
  the same `last_lifecycle` on bound deployment rows. This is not live state or
  a record of operations performed outside the Kit helper.
- `activity.slots`: one record per observed owned scheduler slot (including observed
  surplus instances). `running` has `issue.number`, `issue.url`, title when available,
  `run_id` and observed phase/last activity. Other states are `idle`, `starting`,
  `draining`, `active/issue unknown` or `unknown`. Never substitute the ready head
  or newest retained run for missing identity.
- `activity.working`: verified working count, or unavailable/null if observations
  are incomplete; scheduler inventory still distinguishes configured slots,
  enabled/active timers and running services. `activity.ticks` carries allowlisted
  last/next timer timestamps when readable; Linux slot health retains failed states.

Linux attribution binds the owned service's current `InvocationID`, `MainPID` and
working directory to a `run_start` scene from that same invocation/PID. The journal
reads select only required fields and recheck the binding. Each read caps at 100
entries: lifecycle scenes are filtered before the cap, separately from the recent
activity tail, so command/heartbeat volume cannot evict a retained start binding.
Missing, stale or conflicting scenes mean active/issue unknown.
No raw journal, command/action, session, environment or auth data is returned.
macOS reads at most five owned LaunchAgents with `launchctl print`; a running job
is issue unknown because retained log scenes lack a current invocation binding.
Launchd next-fire time and missing job evidence remain unavailable, not zero.

The reusable `local_deployment_summary` contains only local deployment metadata.
Repository queue/title enrichment and doctor probes stay outside it. The existing
bounded GitHub read supplies titles **after** local liveness/identity is established;
GitHub progress/PR/label records alone never establish a running issue. Partial and
unavailable queue/pending evidence is preserved. Status never fetches, polls, runs a
tick, activates/repairs anything or updates a stale installed helper.

| Kit action | Effect |
|---|---|
| `help`, `status`, `version` | Read only. Help works on all platforms; status/version on Linux and macOS. Version reads only selected deployment engine evidence. |
| `/orbi setup` | Starts by default. Use `/orbi setup --prepare-only` for non-activating preparation. The direct Python helper’s `setup` action is prepare-only; native `orbi setup` is different. |
| `start` | Prepares if genuinely absent. For an existing target, reports `already-running` without mutation when the newest official release is pinned and configured timers are enabled and active. Otherwise, quiesces as needed, syncs/pins/checks under the config lock, repairs units via shared setup/install steps and confirms enabled/active scheduling. Sync or check failure starts nothing and reports a bound `repair_command`. |
| `stop` | Under the config lock, disable owned timers, cancel verified queued starts, stop owned non-idle workers with `systemctl --user stop` and verify inactivity. Report `stopped` with `disabled_timers` and `stopped_services`. No direct kill, restart, issue cancellation or recovery-input removal. |
| `update` | Quiesce as for `stop`, then sync/pin/check the release and start configured scheduling through start's technical checks, even after a previous `stop`, and confirm enabled/active timers (`activation: started`). `update --stop` updates and leaves stopped (`activation: held`). Quiesce failure is nonzero, preserves partial scheduler evidence and blocks engine sync. Dry-run does not mutate or lock. |

`/orbi prune [--apply] [--json]` is host-scoped and Linux-only. JSON returns
`candidates` with unit paths, config and stale reason, and `removed` with paths
actually removed. Without `--apply`, `removed` is empty. See the
[stale templates rules](skills/orbi/references/lifecycle.md#lifecycle-history-and-stale-templates).

Kit mutations are Linux-only; `--dry-run` previews them. On an error inspect the JSON `error.code`, `error.fix` and `error.mutated`: nonzero exit does not mean nothing changed. Use the helper for lifecycle changes, not hand-written unit commands.

## Inspect observable local host services with Kit

From any working directory, invoke `/orbi status all` for one row per deployment,
`/orbi status all --verbose` for per-unit text and coverage details, or
`/orbi status all --json` for structured per-unit inventory. Portable and native
command routes preserve the literal arguments in one helper call. Scripts can use
the absolute loaded helper path:

```sh
python3 -B /path/to/kit/skills/orbi/scripts/orbi_control.py status all --json
```

This branches before repository identity: no global Git checkout or GitHub auth
is required. Do not inject `--repo-dir` or `--config`. Explicit repo/config,
dry-run, stop and bootstrap/mutation selectors conflict and are rejected before
probes with `invalid_host_selection`; retry without those selectors.

Linux inventories the accessible current-user and system managers with bulk
`list-units` and `list-unit-files` JSON queries for services and timers, then
bounded allowlisted `show`/definition reads. It includes failed/inactive services,
unloaded installed definitions, orphan instances, templates, nonrunner Orbi
services and discoverable deployment configs. Full manager + service identity
separates deployments sharing `@1`; there is no slots-1–5 restriction or Kit-only
name filter. Timer targets pair with full service identities; timers/templates
are not workers. Repo ownership requires resolved config evidence, never a basename.
macOS inventories observable GUI/user/system launchd domains and installed
LaunchAgents/Daemons separately: an installed/unloaded plist is not a running job.

JSON returns `scope: host`, `rows`, `totals` and `coverage`. Each row preserves
manager, unit/timer, kind, loaded/installed evidence, scheduler/worker state,
resolved config binding, repo, deployed engine version/revision or explicit
unknown, current issue when locally bound and next trigger when available.
Config-only rows are prepared-only. Engine metadata is shared per resolved config;
no bootstrap CLI, provider/env/session reads, per-deployment queue/doctor or
network calls. Linux live issue attribution prefers the invocation-bound evidence
above, then checks the live worker's locked slot and worktree branch. macOS live
issue identity and next trigger remain unknown.

Successful empty listings mean zero **observed** workers. Failed/denied managers,
unreadable configs, conflicting bindings and scan limits yield partial coverage
without discarding healthy rows. Totals describe observed loaded worker services
in accessible managers, not all users, namespaces, containers or a remote fleet.
No sudo, other-user impersonation, container entry or scheduler actions. See the
[lifecycle inventory contract](skills/orbi/references/lifecycle.md#host-inventory)
for discovery roots, limits and read-access repairs. Native upstream `orbi status`
does not implement Kit's literal `all` mode.

## Native Orbi CLI

Use `orbi --help` and `orbi <command> --help` from the installed release. For a normal deployment command, select the config explicitly (for example `orbi status --config /path/to/orbi.toml`) or use `ORBI_CONFIG` or the deployment’s local `orbi.toml`. Place `--config` after the final subcommand (e.g. `orbi notify test --config PATH`). With no explicit or local config, only `doctor`, `check`, `status` and `session` look for a unique config in installed units. The upstream [CLI and operations guide](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/operations.mdx) describes command output. **Native `status` has no `--json`; Kit’s `status --json` is a different command.**

| To inspect | What the result means |
|---|---|
| `orbi status [--repo OWNER/REPO] [--issue N] [--follow]` | Snapshot of configured repos; `--follow` continues observation. With several repos, `--issue` requires `--repo`. Does not claim work, but reads GitHub and can fetch the base, updating local Git metadata. Retained sessions do not prove an issue is active. |
| `orbi session [--pretty] [--follow]` | Print the newest session file’s path (by mtime); `--pretty` summarizes records and `--follow` follows that file, not later sessions. Output can expose prompts, commands and paths. |
| `orbi doctor [--installed-dir DIR]` | Inspect source drift, slots, installed units and journal diagnostics. Read the findings: a completed report can exit 0 even when a probe says `FAILED`. |
| `orbi check` | Check prerequisites including scheduler, transport, GitHub access and provider configuration; not an end-to-end delivery test. |

| To act (not required for inventory) | Effect |
|---|---|
| `orbi` | Runs a tick; can claim work and advance a delivery. |
| `orbi add TITLE [--body TEXT] [--repo OWNER/REPO]` | Creates an issue, then adds the engine queue label (`ai-ready` in this release), not a repository-specific override. A label failure can leave the new issue unlabeled. |
| `orbi suggest [--repo OWNER/REPO] [--count N] [--size N] [--locale LANG] [--json]` | Runs two model sessions against a fetched base and retains their artifacts. `--json` does not file issues; interactive confirmation can. `--count` accepts 1–3; `--locale` accepts `en` or `zh`. JSON includes `repo`, `base_sha`, `session_dir` and `suggestions`. Positive `--size N` asks for a task within budget first, if available, and adds `size` estimates; it does not cap every suggestion. |
| `orbi draft [REQUEST] [--repo OWNER/REPO]` | Interactive drafting; confirmation can create issues. For automation `--session-dir DIR` reads a round from stdin and writes JSON to stdout; **separately**, `--create` reads a confirmed draft and writes `{"created":[...]}`. See the [draft input, error and retry contract](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/public-contracts.mdx#the-draft-command-contract). |
| `orbi fix-base`, `orbi amend`, `orbi split` | Each requires `--repo OWNER/REPO --issue N`. Respectively open/reuse a base-CI repair ticket, apply proposed acceptance criteria and requeue, or create proposed child issues and turn the original into an epic. |
| `orbi milestone set TITLE` | Sets the active milestone by exact title. If repository policy declares `active_milestone`, this writes to the default branch through the GitHub Contents API without a PR. Otherwise it rewrites the host config. |
| `orbi notify test` | Exercises the configured notification path; can send a real message. |
| `orbi setup [--repo OWNER/REPO] [--installed-dir DIR] [--json]` | Can create config, change the checkout’s origin, repair the CLI, align GitHub labels and activate scheduling. `--json` changes the output, not the effects. |
| `orbi install-units [--installed-dir DIR]` | Installs scheduler definitions and enables and starts configured Linux timers. A timer can trigger a tick; this does not restart an already running service. Not an exporter installer or a read-only drift check. |
| `orbi sync-engine-source` | Updates the deployment checkout according to its configured engine source track. |

## GitHub and run records

GitHub Issues, native dependencies, PRs, reviews and checks record delivery state. The dispatch label means **queued**, not running: the claim removes it and adds `ai-in-progress`. Its name can be overridden per repository; the other engine label roles are defined in [labels.toml](https://github.com/orbi-build/orbi/blob/v0.7.56/src/orbi/labels.toml). Kit publishes readiness last, after verifying the issues and native `blockedBy` edges. `ai-epic` is coordination only; Kit’s `ai-paused` opts out of automatic labeling, not a runtime stop signal. See [Kit’s handoff rules](docs/github-native.md#default-dispatch).

For a read-only integration, key by `(OWNER/REPO, issue number)`. For example, replace the placeholders to read the issue and **all** comment pages:

```sh
gh api repos/OWNER/REPO/issues/42 --jq '{number,state,labels:[.labels[].name]}'
gh api --paginate repos/OWNER/REPO/issues/42/comments --jq '.[] | {id,updated_at,author:.user.login,body}'
```

Each attempt has an eight-hex `run_id`, reused across ticks that resume the same delivery. Correlate `[run_id]` in the journal with `<!-- orbi:run=<run_id> -->` in trusted GitHub comment prefixes and PR bodies. One progress comment per run is updated in place. Its next line is `<!-- orbi:progress:v1 {json} -->` with `step`, `reported_at`, and `activity` (null or `{at,kind,target}`). A heartbeat can advance `reported_at` without new activity. For kinded comments the next line is instead `<!-- orbi:comment=… -->` (`started`, `failure`, `review-round`, `merged`, `requeued`). The trusted opened-PR comment’s `orbi:scene:v1` block records resume information.

Verify the publisher and formal prefix; ignore quoted or fenced markers. Select the most recently updated formal run record, then the most recently updated progress comment **for that run**. If its report is missing, unsupported or invalid, do not borrow a previous run’s report. A progress block does not prove liveness or override a closed issue, a manual wait, PR state or required checks. A failed or partial API read is unknown, not an empty queue. The [public contracts](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/public-contracts.mdx) also specify stop questions/answers, failure records, clarification proposals and command receipts; parse those formats, not translated prose.

For local correlation the issue branch is `orbi/<owner>-<repo>-issue-<N>`, the attempt worktree is `.worktrees/orbi-<owner>-<repo>-issue-<N>-<run_id>`, and Pi writes `<worktree>/.pi-session/*.jsonl`. Neither file mtime nor a leftover directory proves current ownership. The [configuration reference](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/configuration.mdx) distinguishes host settings (`orbi.toml`, provider metadata, `.orbi/env`) from repository overrides (`.github/orbi.toml`). Keep credentials, session records and raw journal output private.

## List runners on Linux

Run these read-only queries on the **runner host**, as the user that owns the deployment. No Orbi config is needed. For the community Docker wrapper, the scheduler is *inside the container*. The host’s user bus cannot inventory it.

```sh
systemctl --user list-units --all --type=service 'orbi*@*.service' --no-pager
systemctl --user list-timers --all 'orbi*@*.timer' --no-pager
systemctl --user list-unit-files 'orbi*' --no-pager
```

The first query lists **loaded** runner services, including failed ones; the second shows timers and what they activate. The third includes **installed** definitions, even if unloaded, and can include templates, the exporter or unrelated matching files. `orbi@.service` is a template, not a worker. A timer and service with the same stem are one scheduled slot, not two workers. Verify the unit’s working directory/config before attributing it to a repository. One user manager is not a machine-wide registry.

On systemd versions supporting JSON output, scripts can select fields without parsing column widths:

```bash
set -o pipefail
systemctl --user list-units --all --type=service 'orbi*@*.service' -o json --no-pager |
  jq 'map({unit,load,active,sub})'
```

A successful `[]` means no matching **loaded** services. A bus/permission failure means inventory is **unavailable**; check the exit status. On D-Bus the equivalent read-only manager methods are `ListUnitsByPatterns` (names, load/active/substate) and `ListUnitFilesByPatterns` (paths, install state). For example:

```sh
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 \
  org.freedesktop.systemd1.Manager ListUnitsByPatterns asas 0 1 'orbi*@*.service'
busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 \
  org.freedesktop.systemd1.Manager ListUnitFilesByPatterns asas 0 1 'orbi*'
```

Keep the full unit name: slot `@1` can exist in several deployments. Substitute a stem from the timer listing:

```sh
stem=orbi-example@1
systemctl --user show "$stem.timer" -p ActiveState -p SubState -p UnitFileState -p LastTriggerUSec
systemctl --user show "$stem.service" -p ActiveState -p SubState -p Result -p ExecMainStatus -p MainPID -p WorkingDirectory -p FragmentPath
journalctl --user -u "$stem.service" --since '1 hour ago' -n 100 --no-pager
```

The default timer schedules a tick every five minutes with up to 240 seconds of stable randomized delay and 30 seconds of accuracy. Missed triggers are not replayed; a trigger while the service is active does not start another copy. A tick runs and exits: `inactive/dead` with `Result=success` can be normal between triggers. Check the timer’s `LAST` and `NEXT`; *enabled* is not *active*. For `failed`, inspect the instance journal including pre-start checks (`ExecMainStatus` alone can miss a preflight failure). For `no_ready_issue`, inspect queue eligibility, milestone and dependencies rather than restarting anything. See the shipped [service and timer templates](https://github.com/orbi-build/orbi/tree/v0.7.56/systemd).

## List runners on macOS

As the owning GUI user, list installed LaunchAgents, then inspect the actual label of one returned plist:

```sh
find "$HOME/Library/LaunchAgents" -maxdepth 1 -name 'org.orbi.*.plist' -print
plist="$HOME/Library/LaunchAgents/org.orbi.example.runner.1.plist"  # substitute a listed file
label=$(/usr/libexec/PlistBuddy -c 'Print :Label' "$plist") &&
  launchctl print "gui/$(id -u)/$label"
```

`~/Library/LaunchAgents` is the default; use the deployment’s actual installation directory if overridden. Surplus plists can remain after downsizing. A plist is an installed definition, not proof of a loaded job or a live process. Each slot’s schedule and process share one job. Inspect its state and last exit status and read the log at the plist’s `StandardOutPath`. `launchctl print-disabled "gui/$(id -u)"` reports disable overrides; `bootout` is **not** an inspection command. See [upstream launchd support](https://github.com/orbi-build/orbi/blob/v0.7.56/src/orbi/launchd_deploy.py).

## Optional Prometheus exporter (Linux)

The [exporter implementation](https://github.com/orbi-build/orbi/blob/v0.7.56/3rd/monitoring/prometheus/orbi-exporter.py) listens on `127.0.0.1:9106` by default. Keep it local; metric labels can identify repositories and issues. If already installed, inspect it without changing runners:

```sh
curl -fsS --max-time 5 http://127.0.0.1:9106/health
curl -sS -i --max-time 90 http://127.0.0.1:9106/metrics
```

| GET path | Response | Interpretation |
|---|---|---|
| `/health` | `200`, text `ok` | Handler liveness only; no journal or scheduler check. |
| `/metrics` | `200`, Prometheus text (`version=0.0.4`); collection exception: `500` | Journal-derived activity and service probes, not a complete inventory. |
| Other paths | `404` | No delivery, registry or restart route. |

`--bind` and `--port` set the listener. `--units` (default `orbi@*`) filters **journal entries**; `--instances` (default `1,2`) selects slot numbers for **service probes**. Those probes construct `orbi@N.service` even if `--units` names a different deployment. Widening the filter does not fix the probes. `slot` is the systemd instance suffix, not the runner’s lock number: different deployments’ `@1` events can overwrite each other’s run state. Use systemd for named-unit state. `--cache-ttl` defaults to 5 seconds for journal entries, not for the service probes.

Gauges: `orbi_service_active`, `orbi_run_active`, `orbi_run_idle_seconds`, `orbi_run_seconds`. Counters: `orbi_run_start_total`, `orbi_run_end_total`, `orbi_run_failed_total`, `orbi_progress_publish_failed_total`, `orbi_model_wait_total`, `orbi_pi_idle_total`, `orbi_pi_idle_term_total`, `orbi_pi_idle_kill_total`. Counters reflect the retained journal, so rotation can lower them. A missing end event can leave a stale active gauge; a failed `is-active` probe can look like zero. Neither a zero nor a missing series proves there are no workers. The [example exporter unit](https://github.com/orbi-build/orbi/blob/v0.7.56/systemd/orbi-exporter.service) is separate from runner units; its checkout paths must match the installation.
