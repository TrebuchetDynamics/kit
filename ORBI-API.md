# Orbi API and host inventory

**Use Kit `/orbi status --json` to inspect one repository, the scheduler to list runners on a host, and GitHub to establish what was delivered.** These answer different questions. In particular, bare **`/orbi`** in Kit means *status*; bare **`orbi`** in a shell runs a **real delivery tick**. Use `orbi --version` to identify a binary without running a tick.

This reference covers Kit’s [lifecycle client](skills/orbi/SKILL.md) and the self-hosted engine at [Orbi v0.7.56](https://github.com/orbi-build/orbi/tree/v0.7.56). Check the deployed version before relying on a flag or format. The engine has no documented HTTP control plane to enumerate deployments, enqueue issues or restart workers. Its [public interface inventory](https://github.com/orbi-build/orbi/blob/v0.7.56/docs/public-contracts.mdx) defines what integrators can rely on; the optional exporter is monitoring, not that API. **Kit remains paused and live-unqualified** under its [cutover policy](docs/github-native.md#cutover). Nothing below authorizes activation.

## Inspect one repository with Kit

Use `/orbi help` in Pi or Hermes, `/kit:orbi help` in Claude Code, or `$kit:orbi help` in Codex. Help requires no repository or deployment. For scripts, from the Kit checkout:

```sh
python3 -B skills/orbi/scripts/orbi_control.py help --json
python3 -B skills/orbi/scripts/orbi_control.py status --repo-dir /path/to/canonical/repo --json
```

`--repo-dir` selects the delivery repository; `--config` selects an existing native deployment config. Distinguish `absent` (no deployment found) from `unavailable` (evidence could not be read). Configured slots, enabled timers, active timers and running services are separate observations. None proves a model answered or a PR merged.

| Kit action | Effect |
|---|---|
| `help`, `status` | Read only. Help works on all platforms; status on Linux and macOS. |
| `/orbi setup` | Starts by default. Use `/orbi setup --prepare-only` for non-activating preparation. The direct Python helper’s `setup` action is prepare-only; native `orbi setup` is different. |
| `start` | Prepares if genuinely absent, then activates the owned timers and requests a first tick if idle. Requires separate scheduling authority. |
| `stop` | Disables owned timers; active services drain rather than being killed. It does not cancel an issue. |
| `update` | Plain `update` requires a stopped, drained deployment. Refreshing installed units can briefly activate timers before Kit restores inactivity. `update --stop` pauses owned timers, defers while workers finish, and skips the activating unit refresh. |

Kit mutations are Linux-only; `--dry-run` previews them. On an error inspect the JSON `error.code`, `error.fix` and `error.mutated`: nonzero exit does not mean nothing changed. Use the helper for lifecycle changes, not hand-written unit commands.

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
