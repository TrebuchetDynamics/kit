# Pi Autowork component

Execution defaults to SDK-backed Pi RPC. See [installation, lifecycle guarantees,
controls and explicit JSON rollback](docs/pi-rpc.md), and the separate
[qualification evidence](../docs/research/pi-rpc-qualification-2026-10-24.md).
An already-running release is not automatically upgraded by this source change.

[Source layout and compatibility](docs/source-layout.md) describes component ownership,
selected-release loading, product tests and copied payloads.

The `pi-autowork` runner. `scripts/pi-autowork.sh` is a thin entry point and the
service command: it finds this component and runs the stable `pi_autowork/cli.py`
adapter, which continues in the toolset release it resolves. Runner and legacy-reader
implementations live in `pi-autowork/src/pi_autowork/`; the generic task lifecycle (admission,
slots, integration, closure) lives in `pi-autowork/src/pi_autowork/engine/` and remains the only
authority for task state. The original Python paths, `bin/autowork` and shell/service
commands remain public entry points. Flat engine imports and canonical
`pi_autowork.engine` imports share the same module objects, including exception types.
Standalone `worktree_paths.py` and `checkout_lock.py`, test assets and fixture helpers
remain under `pi-autowork/engine/`. A missing selected source refuses rather than
borrowing another checkout. Git-free archives support help/read commands, not immutable
runner launches, which still require a committed Git toolset.

The Python module paths in this table are relative to `src/`; `bin/autowork` is
relative to this component. Child commands and reloads use stable public adapters;
source checks, TUI code stamps and review fingerprints inspect actual implementations.
Runtime state lives outside the repository, under
`${XDG_STATE_HOME:-~/.local/state}/pi-autowork/<repository key>/`.

### Private Pi configuration and installed runner

`install.sh` (the `autowork` component) creates a fleet-wide `pi-agent/` under
`${PI_AUTOWORK_STATE_DIR:-${XDG_STATE_HOME:-~/.local/state}/pi-autowork}`.
It copies the interactive Pi home's `auth.json` login and `models.json` provider
configuration, plus only `defaultProvider`, `defaultModel` and
`defaultThinkingLevel` from `settings.json`. No sessions, package registrations,
extensions or other interactive settings are copied. The directory is 0700 and
copied files are 0600; keep them outside repositories, worktrees, logs and reports.
The interactive source is `${PI_CODING_AGENT_DIR:-~/.pi/agent}` and is not changed
by this copy. Runner jobs always set `PI_CODING_AGENT_DIR` to the private directory;
they do not fall back to the interactive home.

The command link and installed systemd launcher use the independent Git checkout
in the state root's `installed/`, not the interactive Pi package clone. Immutable
process releases remain under `releases/`. Removing the interactive home leaves
these paths usable; the Pi executable and Node still need to be on PATH.
Automatic updates of this installed checkout fetch its origin and fast-forward
only after the existing fleet/schema check. For legacy package launches, updates
still require a registered Git package source in `pi list`, including its ref;
local-path declarations remain owner-managed. Running processes keep their
selected release until a supported reload or restart.

Ordinary installation keeps existing private files. To refresh the copied settings
and login, run `autowork update --only autowork` from an interactive shell with a
working Pi home (set `PI_CODING_AGENT_DIR` there for a custom source).
`autowork status` names this command when the private directory/login is missing
or the runner has observed a refused login. Status is read-only and makes no
provider call. See [installation and recovery](../docs/installation.md#private-runner-pi-directory).
Disposable offline fixtures verify permissions, job configuration, command-link
survival and missing/refused-login diagnosis, not live provider acceptance.

| Module | Role |
| --- | --- |
| `pi_autowork/engine/task_store.py` | Read-only, pinned-commit TaskStore used by the engine and committed fleet inventory; [schema and API](task-store.md) |
| `pi_autowork/engine/parallel_integrate.py` | Integration and closure transaction authority, locks, replay and cleanup; compatibility facades compose changelog proposals after document preparation |
| `pi_autowork/engine/integration/closure_documents.py` | Read-only task, receipt and live-followup preparation returning `{path: text}`; frozen `ClosurePorts` binds current `git`, `passed`, `task_path` and `live_items` callables per facade call |
| `pi_autowork/engine/provenance.py` | Append-only attempt evidence: toolset, host, model, contract, prompt and instruction hashes, and the attempt's descriptive authority, captured before launch; never read to decide or authorize anything |
| `pi_autowork/cli.py` | Options, repository and toolset resolution (one release per run), `--status`, `--dry-run`, `--fleet`, `--set-aside`, the runner lock |
| `pi_autowork/coordinator.py` | The loop: engine lease owner, session branch and final merge, settle and close, requests, priority drift, Touches proposals and widening, health, self-update and restart, graceful stop |
| `pi_autowork/supervision/main_checks.py` | Main-check supervision behind unchanged Coordinator methods; stateless helpers use the owner's phase callbacks and current Git/planning predicates. Coordinator retains policy, state, port leases and regression mutation. Child checks use Layout's public entrypoint. |
| `pi_autowork/post_merge_barrier.py` | Opt-in revision-bound admission, verdict validation and terminal classification using the existing main-check receipt; no separate scheduler. |
| `pi_autowork/worker.py` | The engine-launched `--worker` and `--verify` modes |
| `pi_autowork/service.py` | `--install-service` / `--remove-service` for `pi-autowork@<repository>.service` |
| `pi_autowork/common.py` | Logging, Git helpers and task lifecycle words |
| `pi_autowork/pi_runtime.py` | One Pi job: existing model/fallback policy, RPC by default, explicit JSON rollback, bounded retries and provenance-aware accounting |
| `pi_autowork/pi_rpc.py` | Pinned AsyncPiClient host, immutable accepted input, session ownership, settlement, private live progress and opt-in bounded controls |
| `pi_autowork/pi_process.py` | Linux parent/descendant ownership, pidfd signalling and cleanup receipts |
| `pi_autowork/pi_events.py` | Bounded event projection, lifecycle timing and conservative usage coverage |
| `pi_autowork/accounting.py`, `scorecard.py` | Private run/owner-time accounting and read-only scorecard aggregation; unknown billing is never priced or treated as zero |
| `pi_autowork/health.py` | Per-runner `status.json`, one stall announcement per episode with its root blockers, and the `--fleet` view |
| `pi_autowork/processes.py` | Shared Linux process start ticks, identity-aware liveness, runner ancestry and process names |
| `pi_autowork/workspaces.py` | Mirrors `PI_AUTOWORK_LINK_PATHS` gitignored dependencies into task and review worktrees (real directories, hard-linked files) |
| `pi_autowork/task_status.py` | Pure task-state display vocabulary shared by snapshots and CLI worker lanes |
| `pi_autowork/task_snapshot.py` | Immutable committed task inventory: ordered rows, five buckets and total, goals, questions, independently observed pending paths, runtime identity/freshness and errors; display-only, never dispatch authority |
| `pi_autowork/blockers_report.py` | Plain-text read-only diagnostic report; fresh committed selection reasons separated from recorded fleet/runtime observations |
| `pi_autowork/fleet_view.py` | Every runner on the machine (tmux sessions, `pi-autowork@` services, `status.json` health), its worker lanes (engine slots in flight, the runner's latest phase line, the Pi transcript's last action), its blockers grouped by kind, recent logs, and the exact existing command behind each action; standard library only |
| `bin/autowork`, `pi_autowork/command.py` | The `autowork` command (below), standard library only |
| `pi_autowork/command_results.py` | Headless command-output and answer-receipt interpretation; no command execution, task mutation or UI effects |
| `pi_autowork/tui_reads.py` | UI-loop read coordinator: four physical workers, coalesced requests, lifetime/identity/epoch-bound publication and cancellation-safe resource slots |
| `pi_autowork/tui.py` | The `autowork` TUI (Textual, run through `uv`): live runners with what each needs (the owner's open BLOCKERS.md questions, else its first blocker), worker lanes, model and log, stacked full width so it reads on an 80-column terminal, a directory browser that starts services, and keys that run `autowork` commands; `--view-only` disables the keys |
| `pi_autowork/tui_web.py` | `autowork web`: serves the TUI to a browser with textual-serve, on 127.0.0.1 by default |
| `pi_autowork/questions.py` | The owner's questions block in `BLOCKERS.md`, built from the engine status without a model |
| `pi_autowork/release.py` | Safe-checkpoint test before a self-update: fleet idle, and the new release reads current state |

## Rust candidate

The separate [native-Octet candidate](rust/autowork/README.md) lives entirely in
`pi-autowork/rust/autowork/`, including its locked dependencies, tests and fixtures.
It builds `autowork-next`; it does not replace the installed Python runner.
See its [offline build checks](rust/autowork/README.md#build-and-offline-checks)
and [dependency prerequisites](../docs/dependencies.md#rust-autowork-candidate).
A source relocation grants no live-provider, service or migration qualification.

## Reviewed Hermes observers

Startup and `--install-service` normally refuse active repository Hermes jobs
mentioning `autowork` (exit 4). A progress monitor is not exempt just because its
name or prompt says “read-only”. For a **reviewed, genuinely read-only** monitor,
`PI_AUTOWORK_HERMES_OBSERVERS` can point to one private JSON policy outside Git.
Other active writers still block; disabled/paused jobs remain ignored. Do not use
`--allow-hermes` or `PI_AUTOWORK_ALLOW_HERMES=1` to exempt a monitor: those bypass
all Hermes overlap classification.

### Review and exact binding

1. Privately inspect the exact job in `<hermes-home>/cron/jobs.json` (`default`)
   or `<hermes-home>/profiles/<profile>/cron/jobs.json`. Require a unique string
   job ID within that profile. Review the complete prompt, working directory,
   selected skills, scripts and effective tools, including inherited permissions.
   The approved contract must prohibit repository edits, dispatch, claims and
   service actions. An explicit `autowork` development skill (including qualified
   names and skill paths) is never eligible, even with a matching fingerprint.
2. Save the reviewed **single job object**, not the jobs wrapper, to a private
   snapshot. Compute its fingerprint from this release (example paths only):

   ```sh
   PYTHONPATH=/path/to/autowork/pi-autowork python3 - <<'PY'
   import json
   from pathlib import Path
   from pi_autowork.hermes_observers import contract_sha256
   job = json.loads(Path('/private/reviewed-job.json').read_text())
   print(contract_sha256(job))
   PY
   ```

   Computing a fingerprint is **not** a safety review. Never automatically refresh
   a binding after drift. The hash uses UTF-8 Python JSON with sorted keys,
   separators `(',', ':')`, default ASCII escaping and no nonfinite numbers.
   It binds the entire job object, including unknown fields, except these
   scheduler observations: `last_run_at`, `next_run_at`, `last_status`,
   `last_error`, `last_delivery_error`, `last_execution_error`, `last_failure`,
   `failure_streak`, and nested `repeat.completed`.
3. Create a private policy, for example
   `${XDG_CONFIG_HOME:-~/.config}/pi-autowork/my-project-observers.json`, with
   mode 0600 in a private directory. Use canonical absolute repository and Hermes
   installation paths, the exact profile/ID, and the reviewed fingerprint:

   ```json
   {
     "version": 1,
     "repo": "/path/to/my-project",
     "hermes_home": "/private/hermes-home",
     "observers": [
       {"profile": "default", "id": "reviewed-monitor", "sha256": "<64 lowercase hex characters>"}
     ]
   }
   ```

   This is a template, not a valid grant. Duplicate JSON keys, unknown schema
   fields, missing/unreadable policies, wrong repository/installation, missing
   or duplicate identities, and changed contracts refuse rather than waive the
   overlap check. Job identities in different profiles are distinct. Keep real
   IDs, profile names, snapshots and policy files out of version control.
4. Set `PI_AUTOWORK_HERMES_OBSERVERS=/absolute/private/policy.json` and, for a
   nondefault installation, `PI_AUTOWORK_HERMES_HOME=/absolute/hermes-home`.
   For an existing service, add these lines to its existing private
   `${XDG_CONFIG_HOME:-~/.config}/pi-autowork/<repository-name>.env` (or configured
   `PI_AUTOWORK_ENV_DIR`), preserving all unrelated settings. Normal repository
   settings loading and `--install-service` persist both values across reinstall,
   restart and terminal launch. Explicit shell values take precedence; `autowork
   start` refuses conflicting saved settings instead of silently replacing them.
   An explicitly empty observer setting revokes exemptions and stays empty on
   reinstall instead of restoring a saved binding. `--status` or `--dry-run` can
   inspect the next launch's classification without starting workers.

Changes to workdir, prompt, selected skill/tool configuration or any other bound
field invalidate the review, even when a changed workdir no longer matches this
repository. Re-review the exact changed contract before replacing the digest.
Paused/disabled identities do not compete; an old binding will be checked again
when they become active. Remove an obsolete entry explicitly rather than treating
its missing job as safe.

This is **classification, not a filesystem/tool sandbox**, continuous enforcement,
or proof that a past run obeyed its instructions. Fingerprints bind job JSON,
not the contents of referenced skills/scripts or the implementation/inherited
configuration of tools. Re-review those dependencies when they change; use real
permission isolation where required. Checks run at install/start/re-exec, not on
every cron execution. Existing engine leases and writer-custody checks remain
necessary. Offline coverage is in `tests/test_hermes_observers.py` and the runner's
service/command fixtures; live toolset activation, service restart and competing
interactive-writer handoff require separate operational qualification.

Source: `pi-autowork/src/pi_autowork/hermes_observers.py`, `cli.py`, and `service.py`.

## Blockers report

Select a runner, open **t Tasks**, then press **B Report** (or click **Report**).
The read-only summary separates runtime/source health from recorded decisions,
required inputs, and dependency waits. Decisions precede other task holds; it links
planning questions to their committed decision task while retaining who raised
them, and warns when selectable metadata conflicts with an explicit execution
restriction in an owner note. These warnings do not change admission or authorize
execution. Genuine input/authorization holds are not advice to weaken acceptance,
checks or scope. Technical/mixed or incomplete evidence does not receive an
owner-only headline. No worker observations does not prove no active workers.
An existing dated owner deferral is already answered, not a new permission question.
Planning stops under `## Resolved` or explicitly marked `Status: RESOLVED` do not
count as questions in the fleet banner, Tasks or report. Their source history is
left untouched. The Needs-decision inventory count still includes deferred records;
its label names the section rather than demanding another owner answer.
When the evidence contains only deferred work and its waiting dependents, the default
copy is a short overview (at most five task lines), quoting each recorded owner
condition instead of a generic deferral label. Long notes are explicitly excerpted;
the complete dated owner notes stay in Details.
Missing dependent checks remain visible. Mixed holds, active work, busy integration
or incomplete sources retain the general report rather than hiding another blocker.

**d Details** expands the same frozen capture: committed selection reasons,
main-check revisions/failure IDs, dependency roots and runtime evidence. Identical
reasons are shown once with explicit references preserving each task/source link;
linked planning evidence remains in Details even when the committed question is
primary. Closed history stays in Tasks → Closed, and integrated
work awaiting closure remains visible. Observations have separate readable source
times where available; missing data or unknown freshness is not health evidence.
The committed section reads the selected repository's HEAD on each report request,
not a last-good inventory. Selection eligibility is never runtime admission.
Full producer reasons replace matching truncated questions; unavailable full
reasons remain explicitly truncated. Source: `pi-autowork/src/pi_autowork/blockers_report.py:build`.

**a Answer** leaves the frozen report for that runner's Tasks in the **Decisions**
view, where the answer form, its default destination section and the single dispatch
live. The report itself stays read-only: it lists the recorded questions, and
answering never happens inside a frozen capture. View-only navigation opens the same
list without its actions. Source: `pi-autowork/src/pi_autowork/tui.py:BlockersScreen`.

**c Copy** requests the plain text of the current summary/details view, without
terminal padding. **F7** selects all; **Ctrl+C** requests copying a selection.
Textual emits OSC 52; SSH/tmux, terminal policy or browser permissions can prevent
clipboard delivery. The UI cannot acknowledge a client clipboard: paste to verify.
It does not change terminal settings or choose a host desktop clipboard backend.

If copying is unavailable, **e Export** saves the frozen current view as a unique
private UTF-8 file under `<state-root>/reports/` (normally mode 0600), showing its
exact **app-host** path—not a file on the SSH client. In browser mode it requests
a plain-text download; transfer completion is not proof the user saved/opened it.
Export is explicit, never automatic; reports may contain sensitive operational
context. Refresh, Details and Escape remain usable during a host save, and a
refresh does not change the exported capture. Source: `pi-autowork/src/pi_autowork/tui.py:BlockersScreen`.

**r** explicitly refreshes; **Esc** returns. Opening, refreshing and copying run no
agent, runner command or task mutation; only explicit Export writes a report copy.
Native terminal drag selection remains available.
The directory browser's **g Plan** opens the embedded planning console for any
repository; Tasks offers **g Discuss** and **v Investigate** for a selected task.
Both **b** and **B** in Tasks open this in-app report; neither launches an agent
or suspends the TUI. Interactive repair is still the separate
`autowork blockers [dir]` command, not this report.

## The autowork command

Select a runner and press **t Tasks**, select a task (use **Decisions** or
**Questions** to filter), then **e Decide**. **Ctrl+S** or **Ctrl+Enter** saves and
commits the answer on main/master with a revision check; **Esc** cancels. On detached
HEAD, Save instead reports **Saved locally — pending commit**, without switching
branches or creating a commit. Named non-main branches still refuse. A commit
failure is not pending-save success: it keeps the draft and reports why; inspect
`tasks handoff` before retrying. Neither result proves runner acceptance, releases
a hold, retries technical recovery or grants live permission.
Small dialogs keep action buttons visible while their contents scroll. In opt-in
`--mouse`/browser mode, fleet menu clicks use the same guarded actions as keys;
normal terminal mode still permits native text selection.

**Log** opens in **Summary** mode. Press **v Raw** to inspect every original line
in the captured journal excerpt, including hidden startup and pending lines. Press
**v Summary** to return. These labelled menu items use the same local action as the
keyboard. **Esc** or **q** returns to the fleet. Toggling changes only cached text,
keeps scroll/follow behavior, and runs no read or runner action. Raw is the bounded
capture, not all historical logs or the worker's Pi transcript.

Matching exhausted or held automatic-triage failures appear as **Technical recovery
needed**, separately from the preserved worker-reported questions. Details and the
Blockers report show the recorded failure and retained-work reconciliation guidance.
A technical triage failure is not an owner verdict, and an answer does not provide
missing operator access or qualification evidence.

In the TUI, Tasks defaults to **1 Open**, excluding closed history and independent
question annotations from the open count. **6 Closed** keeps completed records
available for read-only inspection; number keys or Tab/Shift+Tab switch views.
The separate snapshot diagnostics pane stays three lines high; **i Info** focuses
it for scrolling/selecting/copying the full text, and **i** returns to the rows.
Questions outside current open inventory remain in **Questions**, not Open.
Explicit **Manual** closure shows its recorded actor/time/reason and is not
coordinator-verified. Old records without a closure method show **Unknown closure**;
the display neither reopens them nor invents missing evidence. Closed-history
detail cannot change section or execute answer/repair actions. These are local
source/UI semantics, not proof an installed or remote TUI loaded this release.

`autowork` runs, watches and controls the runners on this machine. A repository's
runner is a systemd user service, `pi-autowork@<repository name>`; a target is a runner
name, a repository path or `.`. Status and inventory reads call no model; planning
and the explicit agent commands below do.

| Command | What it does |
|---|---|
| `autowork` | The live TUI on a terminal (help otherwise) |
| `autowork start [dir]` | Safely select an existing local main branch when needed, then install (if needed) and start the repository's service. Requires a valid committed `tasks/` store on main/master, saying what is missing (`autowork tasks prepare` converts legacy planning or reports the next step). Services prefer the independent installed runner under the shared state root; legacy package installations are used only when that installation is absent |
| `autowork stop [target]` | Stop the service; workers pause and resume on the same attempt. A deliberate stop is terminal: a restart will not revive the previous release or its push grant until `autowork start` |
| `autowork restart [target] [--stop-workers [--now]]` | Reload in place; running workers keep running. `--stop-workers` waits for in-flight merges, then restarts the service and pauses workers; `--now` interrupts immediately instead |
| `autowork pause` / `resume [target]` | Stop the service and keep it off, also after a reboot (disable), or start it again (enable); only a paused service is listed as `paused`, any other stopped one as `not running` |
| `autowork model [target] [provider/model] [--fallback provider/model]` | Show or set this service's Pi model (checked against Pi's list), then reload it |
| `autowork models [search]` | Pi's model list (`pi --list-models`); an empty catalog is an actionable error, never `No/models` |
| `autowork setup-portal --provider NAME --model ID [--endpoint URL] [--apply] [--json]` | Preview a selected Pi provider for the local Hermes Nous proxy; only `--apply` consents to configuration, never a proxy/service start |
| `autowork ls [--long]` | One colored line per runner; `--long` adds its workers in flight, blockers, open owner-question count and model |
| `autowork status [target]` / `logs [-f] [target]` | The runner's full status; its journal |
| `autowork remove [target]` | Stop/disable the selected service, clear its failed state and remove its registration from the fleet; history and worktrees stay |
| `autowork run [dir]` | Run the runner in the foreground here, for debugging |
| `autowork web [--port N] [--host H] [--view-only]` | The TUI in a browser at `http://127.0.0.1:8765` (this machine only); `--view-only` disables control keys |
| `autowork blockers [dir]` | `/autowork blockers` in an agent (`AUTOWORK_AGENT`, else `claude`, else `pi`); records the session's elapsed owner minutes privately when the agent exits |
| `autowork plan [dir]` | Embedded Pi RPC planning: autonomous discovery, task discussion/investigation, saved sessions, roadmap and explicit Review → Apply. `--interactive` chats/steers; `--list`, `--session ID`, `--history`, `--preview`, `--apply REV` resume/review locally. No service start or push; [planning guide](docs/planning-console.md). `--legacy` retains the former external-agent planner and its owner-time accounting |
| `autowork attention MINUTES [--task ID] [--note TEXT] [target]` | Record other owner time (finite, nonnegative minutes); defaults to this repository, optionally attributed to one task. Notes stay private |
| `autowork tasks list\|validate\|new-id [target]`, `autowork tasks show\|why TASK [target]` | Read the `tasks/` store at HEAD (`validate --worktree`: uncommitted edits too) |
| `autowork tasks add\|field\|place\|move\|hold\|release\|decide\|done\|supersede\|delete\|goal ... [target]` | Edit task and goal files in the working tree, never committing: an owner answer (`field TASK "Owner decision" TEXT`, `"Blocker resolution"`), a dated direction (`decide TASK TEXT`, optionally `--section`), a section (`place`, optionally `--decision`), the priority (`move TASK up\|down` changes its rank), a hold (`hold --by`, `release`), a manual close (`done ID --by WHO --reason TEXT [--evidence REF]`, not verification), a new task or goal, or a full record removal (`delete ID`; busy or still-depended-on tasks warn but are removed). Each write validates the whole store |
| `autowork tasks prepare [target] [--check\|--no-commit]` | What Docs Sync runs first: detect the store's state, convert or finish converting a TODO.md + goals.json repository, and report diagnostics with the command that repairs each, as JSON; `--check` writes nothing ([task store](task-store.md#preparing-a-repository-autowork-tasks-prepare)) |
| `autowork tasks commit [target] [--dry-run] [--expect-pending REVISION]` | Preview the exact task diff and its `pending_revision`, or commit only `tasks/`. `--expect-pending` binds HEAD and captured task content under the task lock; drift requires a fresh preview. TUI and plugin confirmations use it. Unrelated staged edits stay; no push. |
| `autowork migrate [target] [--dry-run] [--no-commit]` | Convert a TODO.md + goals.json repository to `tasks/` once, in one local commit (`--no-commit`: staged); an interrupted run resumes; it refuses while work is in flight |
| `autowork scorecard [--days N] [--json \| --csv] [--baseline FILE] [target...]` | Per runner and overall over 1–30 days (default 7): labelled evaluation metrics, weekly breakdown and first-to-last-week changes; JSON retains closure, held-share, questions and task/attempt accounting details; no model call |

### Safe branch selection on explicit start

`autowork start` keeps an already checked-out `main` or `master`. Otherwise it
selects existing local `main`, or local `master` only when `main` is absent.
A clean named feature branch keeps its ref and commits. A detached HEAD must be
reachable from the selected branch, including when both name the same commit.
This also supports a checkout that is a Git submodule. Start does not change the
parent repository's submodule index.

Start refuses to switch when it observes:

- Tracked, staged, untracked or dirty submodule changes, or an ignored file that
  switching would overwrite.
- An unfinished Git operation or Git lock, detached-only commits, or no local target branch.
- The target branch held or locked in another worktree.
- An active runner/service, execution lease, unfinished worker slot, or held repository writer lock.
- Changed branch, HEAD, target ref or worktree inventory during the final recheck,
  newly dirty state, or a failed ordinary Git switch.

The diagnostic gives the reason and a manual next step. Finish the Git operation,
preserve local work, or stop the active writer before retrying. Start never forces
a switch, stashes, resets, fetches, creates a branch/worktree, or redirects to another checkout.
Refusal keeps pause/stop markers and starts no service.

After switching, Start reruns uncached readiness on the selected tree, including
task-store validation. If this fails, it reports the successful switch and the
readiness problem without starting a service. It does not roll back the checkout.
Resolve that problem before retrying. These checks do not atomically exclude
arbitrary external Git or editor processes.

Readiness, status, browse and refresh never switch branches. Browse Play confirms
the intended local branch and possible switch, then calls the same Start command.
Cancel, view-only mode and a stale repository selection do not start it.
Fleet Play for a stopped service uses Start too. Paused resume and the raw runner's
main/master requirement are unchanged.

Disposable Git/submodule fixtures in `tests/test_autowork_command.py` cover selection,
ref/content/index preservation, refusals and post-switch readiness failure.
`test_play_routes_safe_branch_switch` in `pi-autowork/tests/test_tui_controls.py`
composes Browse confirmation with Start using pinned offline Textual and stubbed
service effects. This evidence does not qualify a live service or installed terminal UI.

`autowork restart --stop-workers [target]` names the batch or merge-train check,
integration review or merge resolution it is waiting for. The coordinator records
its result and finishes pending batch landings before allowing the service restart;
it starts no new merge work while the request waits. With no merge in flight, it
acknowledges the restart at its next safe point. Workers keep running until the
service actually restarts, then pause and resume on the same attempt.

The wait defaults to **30 minutes**. Set `PI_AUTOWORK_RESTART_WAIT=SECONDS` in the
calling shell to change it (finite, nonnegative seconds). Expiry exits nonzero,
names the operation still pending and leaves the service running; it never turns
into an immediate restart. Cancelling the command releases the request too.
Overlapping safe restarts are serialized within the same wait bound; each caller
checks the current runner after the earlier restart completes.
`autowork restart --stop-workers --now [target]` bypasses this protection and can
interrupt a check or lose an unread integration result. `--now` requires
`--stop-workers`. Plain `autowork restart` is unchanged.

A running older release without the safe-restart handshake is refused: reload it
with plain `autowork restart` first, or explicitly interrupt it with `--stop-workers
--now`. A stopped service restarts without waiting. Offline command/coordinator
fixtures cover idle, wait, timeout refusal, recorded batch results and immediate
interruption; they do not qualify a live systemd service.

A deliberate stop is not a failure. `autowork stop` records it beside the unit's
settings file and clears any failed unit state, so a `Restart=on-failure` restart
refuses to run rather than revive the previous release or its push grant; only
`autowork start` or `autowork restart` clears the record and re-resolves the release.
A runner also records the release and effective `PI_AUTOWORK_PUSH` it verified at
start, re-asserts the grant from the saved settings before its first cycle, and
refuses dispatch with the named difference when its running release or grant no
longer matches. Publication is bound to the verified revision: a push refuses,
naming both values, when HEAD, the running release or the effective grant differs
from that record, and an unknown outcome reconciles from the recorded revision,
never a force-push.

Publication fetches, pushes (including repository pre-push hooks) and remote
readback run as tracked background jobs. Dispatch and main-check recovery keep
cycling. A push names the exact verified commit, never a moving branch; each
candidate gets at most three attempts with 30/60-second retry delays. Every push
outcome is read back from the remote. Three failed readback probes leave publication
unknown and prevent another push, rather than claiming delivery. Read-only probes
resume after a 300-second cooldown without resetting the push attempt count.
Destination fingerprints are revalidated before enqueue and in the child before
execution; observed drift refuses publication. The named remote is retained so
pre-push hooks receive their normal remote name. This is not an atomic URL pin:
external concurrent Git configuration edits remain a standard Git race.
Upstream session merges wait for reviews, resolvers and other session writers to
release it. Only that merge waits: a fetch, and a push of a main that is not behind
its upstream, run while reviews are in flight, so a queue that is never idle is
still published. An upstream that conflicts with the session goes to the Pi merge resolver,
once per upstream revision in a runner process, the same way a moved main does; the
resolved merge passes the task-record checks before main takes it. An unresolved
conflict is aborted and logged as `Upstream merge deferred`, and main stays
unpublished until the upstream moves, the runner restarts or someone merges it.

Toolset discovery, fetch/schema checks and `pi update` also run off-loop. Lock
contention defers immediately; the complete update job is bounded to 600 seconds.
Background and synchronous publication share a 3600-second (one-hour) bound for
the whole push, including local pre-push verification. A five-minute network-sized
deadline could kill valid repository checks. Hooks remain enabled. Upstream
fetches stay bounded to 120 seconds and remote probes to 60. Installation retries are
limited to three per checked release. An installed revision that differs from the
checked candidate, or an interrupted update that moved the package, cannot activate
through the runner's automatic re-exec. Automatic activation prepares the exact
qualified receipt SHA even if the package moves after receipt collection; an
explicit supported reload still reselects settings and release. Reload/restart
checkpoints wait for tracked job receipts; finite runs drain publication through
ordinary cycles. Receipts,
process start ticks and job logs live in the existing per-repository state
folder, not in Git. These mechanics do not grant publication or skip hooks.

Before reusing an installed or running service, `autowork start` refuses if an
explicitly supplied supported service setting differs from its saved env file
(including a setting absent there).
For example, `PI_AUTOWORK_PUSH=0 autowork start` cannot silently start a service saved
with push enabled. The error names the conflicting settings and file and prints the
`--install-service` command to apply them; run it with the requested environment.
A refusal leaves the service and its pause marker unchanged. Matching settings keep
start idempotent. Without a saved or explicitly supplied `PI_AUTOWORK_PUSH=1` grant,
automatic publication is disabled, including upstream-sync publication; local commits
and merges still proceed.

Grant automatic push once when installing a new repository's runner:

```sh
PI_AUTOWORK_PUSH=1 autowork start /path/to/my-project
```

The installer saves the grant in that repository's settings file; later cycles and
launches reuse it without asking again. It does not grant permission to another
repository, even one with the same directory name. For an existing service, use the
`--install-service --repo /path/to/my-project` command above with `PI_AUTOWORK_PUSH=1`
to grant, or `PI_AUTOWORK_PUSH=0` to revoke; reinstalling applies the settings and
reloads/restarts that service. A shell-only override is not a persisted grant.

`autowork status /path/to/my-project` (or `pi-autowork.sh --status`) shows
`Push: enabled` or `Push: disabled` after loading repository settings, with an explicitly
set environment value taking precedence. This read does not edit settings or change
service lifecycle; it describes the next launch, not an unreloaded process's environment.
Existing saved `1`/`0` settings remain enabled/disabled and are not migrated or rewritten
by a settings load or status read. No live service migration is part of this default change.

`autowork ls --json` includes a boolean `push` for each runner, and the TUI detail
pane shows `Push enabled` or `Push disabled`. Both read the saved service env file,
not the viewing shell's overrides: only `PI_AUTOWORK_PUSH=1` enables push; a missing
or other value means disabled. Like status, these are read-only settings displays,
not probes of an unreloaded process's environment. Offline command tests and the
headless TUI pilot cover these displays; they do not qualify live publication.

The fleet defaults to a bounded summary, leaving space for worker rows and the
journal. **i Details** replaces that summary with a keyboard-scrollable diagnostics
pane (End/Page Down scroll; **i** returns to the fleet). It retains paths, revisions,
source errors and notes, model/fallback and push settings. Runtime observation failures
remain visible in the summary; a short viewport prioritizes the main-check result
over the generic explanation. This changes presentation, not health or admission.
The fleet table's State uses the semantic label from the same captured verdict as
selected status: **Blocked** when inventory has no active work and action is needed,
even if raw service health says `working`. The explanation names **Needs your action**,
**Needs repair**, or **Waiting for capacity**; mixed repair/owner cases retain both.
Normal dependency waits remain **Waiting**. Elapsed time is context, not a new state:
`autowork ls` and status render old `stalled`/`waiting on you` observations as `blocked`.
The 30-minute stall alert and its clock remain internal compatibility behavior. `Runner.state`
and CLI/Paseo schemas retain their existing raw lifecycle meaning.
`fleet_view.presentation(runner)` projects an already attached snapshot without
reads into a frozen label, explanation, style, counts and observed activity. Only
identity-matched active lanes and recorded runner jobs supply that activity;
independent main checks remain separate receipt evidence with checked/current
revisions and original start times. Unknown counts remain unavailable, never zero.

The projection groups **acquisition errors** separately from informational **source
notes** (unmatched execution, unmatched activity, revision and provenance). Its
counts deduplicate identical messages within each category; every original message
and explicit affected task ID remains available on the groups for Details consumers.
The overview shows deduplicated **errors** and **notes**, not a combined warning
count. Details groups their categories and retains every original observation,
including repeated notes and unmatched task IDs. Main-check evidence retains the
checked revision, current main revision and original start age, even when superseded;
it does not qualify the newer main. Details/Blockers retain their full evidence.
The projection grants no readiness, scheduling or current-main verification authority.

Below 120 columns the fleet shows Runner, State and Total; selecting a runner shows
its complete task-count breakdown. Below 100 columns the repository browser stacks
readiness below the directory tree. Source: `pi-autowork/src/pi_autowork/tui.py` (`FleetApp`,
`BrowseScreen`); fixture coverage: `pi-autowork/tests/runner/test_tui_layout.py`
and the bounded `test_tui_operations.py` / `tui_operations_pilot.py` beside it.
Matched worker cells show committed task titles (or the captured short name when
no full record is available). **i Details** exposes full names, exact IDs, phases
and wait reasons; **Enter** on a worker opens that task's action log. Duplicate
names never become action keys. Unmatched lanes remain observations, not active
committed tasks.

The fleet menu shows one useful **Next** action, then **Log**, **Tasks**,
**Details** and **? More** (without duplicate entries). Next uses captured status:
Tasks for questions or waiting work, Details for blocked/unavailable inventory,
Log for live work, or Play for a stopped runner when controls are allowed.
Every available action remains searchable in More; all direct keys remain:
`l` (or Enter) **L**og, `p` **P**lay/**P**ause (starts a stopped service, resumes a
paused one, pauses a running one), `s` **S**top, `r` **R**estart, `m` **M**odel
(from Pi's list, type to filter), `t` **T**asks, `u` **U**ninstall the
service, `n` **Browse**: browse directories (from `~/git`, `AUTOWORK_BROWSE_ROOT`), see which
repositories are ready or what they need, and `p` there plays one; `q` **Q**uit.
**Tasks** is the only task-management entry on the fleet screen; answering,
planning and blocker inspection live inside task views (or the directory browser
for repository-wide planning), not separate fleet hotkeys or palette entries.
Press **? More** to search all available actions and see their shortcuts. Choosing
an action uses the same command and confirmation as its direct key. Read-only
views list only read-only actions. Stop, Restart, Model, Browse, Uninstall (when
available) and Quit live in More at every size and retain their direct shortcuts.
Model also remains directly clickable on the model bar. More rechecks the selected
repository identity before dispatch and uses the existing confirmation flow.
Press **Ctrl+P** to search fleet commands, switch themes, or find screen-specific
actions. The palette includes provider/model selection on the fleet and provider configuration
and refresh while the model picker is open. Read-only mode omits actions that
change runner or repository state.

The fleet uses a two-pane workspace on terminals at least 130 columns and 26
rows: project/context on the left, current work/activity on the right. Smaller
terminals keep a vertical stack. Borders identify panels and highlight keyboard
focus; the fixed footer shows **1 Projects**, **2 Work**, **3 Activity**, Help and
Quit. Press **h Guide** for the setup/execution/review/publication flow and how to
interpret waiting, attention and unconfirmed states. Task progress is separate
from the service being alive. The number keys move focus only on the fleet screen; arrows select and
Enter opens the selected log. Resizing does not acquire new state or dispatch an
action.

The fleet has three numbered regions: **Projects**, **Current work** and
**Recent activity**. The project list shows Project, Status and Tasks at every
width. The selected summary identifies the next useful action; detailed counts,
source status, attempts and elapsed/quiet times remain under **i Details**.
Unconfirmed worker observations retain that label and never count as verified
active tasks. Repeated memory waits in the dashboard show their latest value,
range, number of updates and first/last timestamps. Full-screen **Log**, including
Summary and Raw modes, keeps the individual original samples.
Below 22 terminal rows, the selected summary uses three lines and keeps the main
check visible. The activity journal retains at least four rows and one worker row
remains selectable at 60×18. Abbreviated names, phases or evidence have a visible
Details route; those cell sizes are fixture test dimensions, not live terminal
qualification. Repeated identical text does not repaint widgets; style and
click-target changes still update them.
Acquisition and freshness rules are unchanged. See [DESIGN.md](../DESIGN.md) for the maintained
terminal layout and interaction contract.

The browser shows an editable directory path plus **Parent** and **Home** buttons.
Use arrows to select folders and Enter to open the selected folder. **Ctrl+L**
selects the path for typing or pasting; Enter opens it. Relative paths resolve
from the current browser directory, and `~` opens your home directory.
**Alt+Up** goes to the parent and **Alt+Home** goes home. Invalid or unreadable
paths leave the current directory unchanged and show an error. Browsing changes
neither the process working directory nor a runner's repository.

The project summary separates **Now**, the **last observed action**, **Your action**,
**Main** checks, and **Publish**. An active worker is not proof of code changes.
A worker with no observed action says so; after five minutes without an observed
action it is labelled **Quiet worker**, without claiming a hang. Other blocked
tasks can need attention while active work continues. Unmatched/stale observations
cannot supply current progress. Small terminals retain the compact summary and
Details route.

A recorded OpenRouter daily free-model quota failure (HTTP 429 with
`free-models-per-day`) is displayed as **Daily free-model quota exhausted**.
Wait for the provider's reset or choose another configured provider before
retrying. The diagnostic is display-only: failure ownership, retry admission,
credentials and model selection keep their existing guards.

In **Tasks**, select held work and press **r Retry** to request a fresh failed
attempt, preserving previous work. Confirmation explains eligibility; the CLI
refuses attempts it cannot safely retry. **c Clear** returns a held commit to
integration instead. If context overflow repeats, return to **Choose model** and
select a suitable alternative before retrying. Restarting a service preserves its
attempts and is not a replacement for Retry.

The dashboard journal prefers the latest runner start found in its last-hour
window. Full Log retains earlier runs; if no start is captured, the dashboard
keeps the available window rather than guessing a session boundary.

A visible **Choose model** row shows the selected service's model. Press `m` (or
click it with `autowork tui --mouse`) to choose a **Provider**, then search that
provider's models. With multiple providers, select one before choosing a model;
the current provider or the only available provider is preselected. Use Down to
browse, Enter to select and Escape to return. Loading, no matches and catalog
failures appear inside the selector. The provider menu includes Pi's configurable
providers even when no models are available. It distinguishes credentials stored in
Pi from model availability; stored credentials have not necessarily been validated
by the provider. Public SDK model metadata remains browsable before login.
**Free models** searches explicitly free OpenRouter routes across providers,
using the catalog's zero input/output/cache prices and `:free`/free-router IDs;
unknown prices and subscription-only models are not labelled free. Availability
and provider limits can change. Selecting an unconfigured model opens provider
configuration; refresh after login and choose the model to use it.
Choose **Configure provider** for the selected provider, select
OAuth or API key where supported, then **Connect**. Follow the prompts in the TUI.
All answers are masked and never prefilled from storage. Text replies preserve blank
provider-defined defaults, such as Copilot's `github.com` host. Secrets and callback
codes still require a nonblank answer. **Browser** explicitly
opens the provider's HTTPS OAuth page when required. Escape cancels the connection;
progress and failures stay in the dialog. Pi owns credential persistence in the
selected runner's `PI_CODING_AGENT_DIR` (the session's profile for a new runner).
Successful setup refreshes models automatically; **Refresh models** retries manually.
API-key setup stores the key using Pi's SDK; it does not prove that a provider will
accept the key or execute a model. Providers without interactive setup require their
normal Pi environment/settings configuration. Opening the picker starts no login,
model call, service or browser. Changing the selected repository, runner or profile,
or entering read-only mode, cancels an active dialog and discards stale model
callbacks. A same-name runner with the same profile but a different repository is
a different target.

Provider setup uses the official **Pi SDK 1.5.0** and Node.js **22.19 or newer**.
A native Pi binary alone does not contain the importable SDK. For Pi 1.5.0, prepare
an isolated, matching SDK explicitly (no credentials or runner changes):

```sh
npm install --prefix "${XDG_DATA_HOME:-$HOME/.local/share}/kit/pi-auth-sdk/1.5.0" \
  --ignore-scripts --no-audit --no-fund --save-exact @earendil-works/pi-coding-agent@1.5.0
```

The TUI discovers this versioned location automatically, or an existing matching
npm Pi installation next to its executable. `AUTOWORK_PI_SDK` explicitly selects
the package directory containing `package.json` and `dist/index.js`; an invalid
explicit path fails without silently choosing another SDK. Missing/incompatible
helpers produce setup guidance; the TUI never installs packages automatically.
No second credential store is introduced. The bridge uses the tagged public
[`ModelRuntime` SDK](https://github.com/earendil-works/pi/blob/v1.5.0/packages/coding-agent/src/core/model-runtime.ts)
and [`AuthInteraction` contract](https://github.com/earendil-works/pi/blob/v1.5.0/packages/ai/src/auth/types.ts).


Before starting a new service, choose its model in the TUI. You can select it from
the fleet before browsing, or Play asks for it before the start confirmation.
This choice stays in the TUI session until Start saves it for the new service;
the confirmation names the model and disables automatic fallback. Existing services
keep their saved model, fallback and Pi configuration. Changing an existing service's
model still uses the separate model-change confirmation.
The fleet has no Fallback or Nous Portal controls. Fallback remains visible in
runner details; configure it with `autowork model --fallback` and use
`autowork setup-portal` for opt-in provider setup.
If only the branch prevents readiness, Browse Play confirms the intended branch
and calls Start for safe selection as described above. Other unready repositories
offer **Prepare**, **Prepare and start**, **Plan**,
**Force** and **Cancel**. Prepare runs `autowork tasks prepare` without blocking the
TUI and can commit a legacy conversion; it displays the outcome code, every refusal
and the next step, then refreshes the repository's readiness and tree label.
`NO_STORE` directs you to plan accepted intent with `/docs-sync`; it creates no goals
or tasks. Deferred, blocked, invalid
and toolchain outcomes are not readiness. Prepare and start asks to start only
after successful preparation and a fresh readiness check; Prepare alone never
starts a service. A deferred conversion stays unavailable until it completes.
**Force** first asks for confirmation: it stops the service and live workers, sets
attempts aside with worktrees, branches and files kept, commits planning edits,
converts, and restarts a previously active service. Escape cancels without running
anything; Yes runs `autowork tasks prepare --force <repo>` through the same background
worker. The pane shows the forced step's `stopped`, `set_aside`, `landed`, `committed`
and `commit` fields when present, alongside every refusal and the next step. For a
long report, Tab focuses the pane; End or Page Down scrolls to the rest.
The directory tree marks legacy or interrupted conversions **legacy planning**, not
**needs tasks**; a repository without planning still reads **needs tasks**.
The headless pilot exercises preparation on disposable repositories, with faked
service starts and forced service/worker effects; it does not qualify a live service.
The Tasks window shows a queue and a selected-task reading panel. Wide terminals
(120×26 and larger) place them side by side; smaller terminals stack them. The
panel explains **What is happening** and **What you can do**. **Space** focuses it
for scrolling; **Enter** opens the complete task. Full committed titles are used
where space permits. **i Info/Help** replaces the reading panel with technical
context without changing the selected task. On short terminals, the current filter
and count remain visible with Tab / 1–7 hints; other terminals show all filters.
In a task's complete view, scope and acceptance are readable first; **i Technical
record** explicitly reveals the raw working-tree fields and source provenance.

`1`–`7` (or Tab) show Open, Active, Blocker, Waiting, Questions, Decisions or
Closed. Decisions is the committed **Needs decision** section: open tasks that wait
for the owner and never dispatch. Closed history shows **Verified** with the receipt, or **Manual** with the reason
(a missing/invalid verified receipt is explicitly warned, never relabelled Manual).
On the selected task `u`/`d`
move it **U**p or **D**own (its rank is the priority), `s` to another **S**ection (Now,
Next, Needs decision), `c` **C**lears its hold, `a` sets a held task **A**side, `e`
(or `a` on a row without a hold) **Decide** records an owner direction without AI,
`g` **Discuss** and `v` **Investigate** open the planning
console scoped to that task, and `n` adds a **N**ew task from a form. Enter opens the
task: its question and the runner's suggested answer, its whole task record and its
worker's last actions. **Decide** Save uses `tasks decide --commit --save-if-detached`:
main/master commits only the answer and chosen section; detached HEAD keeps them
locally pending. Return/reopen feedback identifies pending edits; the runner cannot
see them until committed. An unchanged answer/section creates no new pending delta
or commit, but existing pending edits remain visible. `C` **C**ommits the saved owner answers that a reading runner
cannot see yet: one line above the rows names how many edits wait, and the form asks
for a commit message before it moves tasks/ paths only (no push, no execution).
Answer it there, written to the task's record where the runner reads
it: `w` **W**rite a dated `Owner decision:` note, `d` **D**efer it to Needs decision with your
reason; a repeated quick hold takes `r` **R**esolve with the producer or decision. Stop,
restart, pause, uninstall, clear, set-aside and model changes ask first.

Confirmed **Uninstall** uses `autowork remove`. On success, the selected runner
leaves the next successful CLI `ls`, TUI and Paseo fleet result. Removal verifies
that the service stopped, clears any failed state, and removes only its saved
settings and pause/stop markers, including its legacy path-named instance.
Stop, state-query or cleanup failures report an error instead of full success.
The shared service template, other instances, history, repositories, task data,
worktrees and unmerged branches stay intact. Removal also works when the saved
checkout is missing. A later explicit `autowork start PATH` installs the usual
registration again.

Saved settings keep installed stopped/paused runners visible. Retained history
and unregistered inactive/failed units do not register a runner. Unregistered
active, starting or stopping units remain visible for diagnosis. Unreadable or
malformed saved settings remain visible with errors, not treated as removal.
Offline fake-systemctl tests cover this lifecycle. Real systemd uninstall still
needs a separately authorized check on a disposable service instance.

Terminal text can be selected by dragging with the mouse, then copied with your
terminal's copy shortcut (often Ctrl+Shift+C). Mouse capture is off by default;
keyboard navigation and controls remain available. Use `autowork tui --mouse` to
restore clickable rows/buttons instead; hold Shift while dragging if your terminal
or tmux intercepts selection. The browser view retains mouse controls.

### Fleet task inventory and freshness

Fleet counts, task rows and Waiting/Blocker details use one committed `tasks/`
snapshot per repository and refresh generation. Each committed open ID contributes
once to Active, Mergeable, Waiting, Blocker or Decision, whose sum is Total.
Ordinary ready worker tasks are Waiting (`ready; awaiting dispatch`). Ready
owner-only tasks are Blocker (`owner action required`), not a worker dispatch wait
or another approval request. Ready coordinator-owned tasks are Waiting
(`awaiting coordinator action`) for two hours after the committer time of the last
commit that changed their task file. The claim then expires: parallel admission
and sequential fallback treat them as worker tasks without rewriting the record.
Their ready wait becomes `coordinator claim expired; ready; awaiting dispatch`.
This also applies to existing records. Unrelated commits and uncommitted edits do
not renew the claim. Owner-only and live-authorization gates remain unchanged.
Committed Needs decision takes precedence as
Decision. Stopped dependency waits are Blocker. Uncommitted records and
planning-branch records do not enlarge this inventory.

Ownership comes from the committed record, even without runtime data. Compatible
idle waiting text cannot replace an owner-action or coordinator-claim reason,
including an expired claim's ready wait. Compatible
in-flight evidence still supplies the runtime state under the identity guards below.
An existing question adds context but is not required to show owner action.
A saved yes records direction, not completed action or live authorization. These
labels do not change task selection, worker admission, ownership or closure.

Runtime observations must name the same repository and compatible current/admitted
contracts. Compatibility symlinks to the same state directory are read once; distinct
historical directories still receive duplicate-identity diagnostics.
Missing legacy identity, duplicate/orphan observations and mismatched or
stale slot activity are annotations, not additional tasks or evidence of Active or
Mergeable work. Session/canonical revision divergence is disclosed. Questions for
closed or noninventory IDs remain visible as annotations in the Questions view.
The task record body is labelled as independently read working-tree content.

The Tasks window shows one short Inventory line with inventory and execution
freshness. Stale capture age and acquisition warnings remain visible. Press `i`
(**Info/Help**) for full selected-task context (including owner guidance), pending
edit messages, revision, generation, capture age, full diagnostics and all task
keys. Compact banners/details are bounded so long text cannot push task rows off
screen; their complete text remains scrollable in Info/Help. Pending paths and questions are independently observed working data.
A valid empty store has zero counts. Unavailable or invalid inventory shows `?`
and `unknown / unavailable`, not zero. Failed refreshes can retain last-good
inventory with its original revision/capture age, visibly stale. Pending-path read
failure means unknown, never clean. In the Tasks window, unavailable inventory
shows `?` for every view count and an unavailable placeholder rather than a verified
empty list. The task table uses descriptive names instead of a separate ID column,
leaving more room for names and status on narrow terminals. IDs remain in the
selected-task details and the full record; actions still target the exact ID even
when names match. State and activity are separate: for example, **Active** in State
and **Implementing** in Why. Normal-width layouts reserve space for Why; narrow
layouts keep state and show the full reason in the selected details and Info/Help.
The selected task names its section explicitly and shows repeated activity only
once, not as a misleading next action. Owner-action questions show the committed
scope and acceptance criteria. Missing instructions
are identified, not replaced with another approval request. The main menu shows
Open, e Decide, Report, Info/Help and Back where applicable, with clickable commands
in mouse/browser mode. Other keys remain available in
Info/Help. In this window, `i` shows or hides the scrollable diagnostics and returns
focus to the task table when hidden. Page Down/End reads long errors. Verified
empty keeps zero counts. Stale last-good rows keep their counts and capture age
with an acquisition warning visible. Info/Help retains the original revision. The rendered pilot opens all three
states in wide and narrow viewports, checks painted cells/layout bounds, and scrolls
a long acquisition error through its final line.

A confirmed TUI **Delete** (`x` or Delete) uses the repository path captured before
confirmation, not a runner-name lookup. After command success, rows, closed history,
counts and detail/actions update on the next UI-loop update, without waiting for a
reader, timer or commit. Inventory diagnostics label this display-only adjustment
**deletion pending commit**; the original committed snapshot, dependency/admission
authority, worker activity and independent questions remain unchanged. Failures or
cancelled confirmation do not remove rows. Old or failed reads cannot resurrect the
record. Fresh off-loop working-tree and committed observations retire the adjustment
when deletion is committed or the record is restored. A recreation absent from HEAD
is disclosed as a pending record, never added to committed inventory. External CLI
edits retain the normal observation cadence; the TUI never commits deletions.

Non-interactive command results are interpreted by `command_results.interpret`
without Textual: generic output uses the last line (including stderr warnings),
execution exceptions and nonzero exits are failures, and answers without `--commit`
remain pending. A committed answer requires a committed lifecycle receipt; an
invalid receipt reports failure and keeps the draft. This is command feedback,
not runner acceptance or authority to mutate or commit tasks.

`FleetApp` still owns command execution and terminal suspension. After interpreting
a non-interactive result, it posts the notification (at most 300 characters), calls
any completion callback with the full message, then updates and refreshes the view.
`tests/runner/test_command_results.py` covers headless interpretation, and
`tests/runner/test_tui_architecture.py` covers delegation and callback ordering.

The TUI runs `collect_for_tui` off the event loop and publishes its `FleetSnapshot`
envelope atomically, including acquisition errors. Its labelled preparation diagnostics can be
reused for less than 30 seconds, invalidated by observed revision, dirty-file,
settings or environment changes. Explicit refresh and action/preparation return
invalidate the audit. Cached diagnostics supply neither task membership nor Start
authority: confirmed Start still reads readiness afresh. CLI/full readiness stays
uncached; service-enabled queries have a ten-second bound.

Fleet, journal, task-detail, goals, directory-readiness, model-catalog and code-update
reads share a four-worker coordinator. Each resource has one physical read and at
most one replaceable pending request. Timer polls do not invalidate a slower active
read; selection changes, action/interactive return and screen closure discard obsolete
results. Cancelling a subscription does not free its running thread's resource slot.
Only the UI loop publishes results and touches widgets. A screen's first read that
completes while its Mount dispatch is still running is retained and published after
mounting; invalidation or unmount discards it. Resize, task filters and worker-log
wrap use cached data. Directory labels are loaded separately from the selected
repository's readiness; confirmed Start always requests fresh readiness.
Model discovery is fresh per opening and uses the selected service's provider context.
Read failures retain last-good data with a stale/unavailable diagnostic and allow retry.

Activity requests up to **400 journal lines from the last hour**. Full-screen Log
requests up to **1000 lines**. Both use the existing **20-second** command timeout
and shared four-reader coordinator. Summary folds only adjacent identical messages
with explicit task identity, or operation family and revision (plus an explicit
target when present). Folded events show their count and original first/last times,
including spans across midnight. Changed reasons and interleaved events remain in
source order. Unknown and multiline diagnostics are retained, not deduplicated.
Restart markers retain their observed time span and toolset revision when present.
A missing start or outcome remains absent evidence. A timeout or unconfirmed push,
integration, closure, or an older main-check result does not prove remote publication
or current-main acceptance.

The TUI distinguishes a successful empty journal from timeout, OS error and nonzero
journal exit. Failed reads keep the last-good capture with a stale/error notice,
or show **Journal unavailable** when no capture exists. Log also shows its last
successful read time. Raw/Summary and resize retain these disclosures and reject
obsolete reader results. The CLI journal command and `logs(..., strict=False)`
compatibility remain unchanged; only TUI acquisition opts into strict errors.
`tests/runner/test_activity_log.py` covers projection and subprocess failures, plus
`tests/runner/activity_log_pilot.py` at 60×18, 80×24 and 120×32 with blocked fixture
readers. These offline checks do not qualify physical terminal, SSH/browser or
installed-release behavior.

Offline checks in `tests/test_tui_reads.py`, `tests/test_task_snapshot.py`,
`tests/test_fleet_view.py` and `tests/test_health.py`, plus the headless
`tests/tui_pilot.py`, cover these boundaries. The pilot acknowledges keys and closes
screens while reader providers are held by Events, before releasing them. Its
immediate-deletion case runs the real CLI on a private fixture with timers disabled
and the fleet reader blocked, then checks stale-result rejection, restore and
pending-only recreation. These checks do not qualify SSH transport latency, a live
service or execution through a provider.

The main-check line in runner status and the TUI reads the current check receipt,
not just the runner's cached health snapshot. A missing process or a reused PID
(with different process start ticks) reads `main check interrupted`, even if the
runner stopped before recording a result. A process without recorded start ticks
cannot be verified live and also reads `interrupted`. A verified live check reads
`running`; one queued for admission reads `waiting for a check slot`. A live check
past its execution budget reads `overdue` and `past timeout`; waiting does not
consume that budget. New slot receipts carry the command's configured timeout;
older receipts fall back to 3600 seconds. Each line names the checked revision;
a check of an older revision also reads `superseded by main at REV`.
On the next supervision cycle after main moves, the runner stops an obsolete
check unless the checker reports **more than 80%** of its test modules complete.
Exactly 80% does not qualify. The offline checker reports actual module
completions through `AUTOWORK_MODULE_PROGRESS`, counting a split module only
when all its shards finish; buffered log output is not a progress count.
Commands without module progress can be stopped too. The existing process
supervisor reaps the check and its descendants, including detached test processes,
before the runner removes its scratch worktree and temporary directory and
schedules the current head through normal admission. A stopped check publishes
no verdict or regression and preserves the previous last-green and red state.
A check allowed to finish records its result for its own revision; the current
head is checked next. Jobs adopted from an older release without cleanup
supervision finish normally rather than risk orphaned processes.
`tests/runner/test_main_check.py` covers replacement below and at the cutoff,
cleanup, preserved state and completion above the cutoff; `../tests/test_check.py`
covers the checker's split-module count. These are offline fixtures, not an
installed-service qualification.
A green result reads `main check passed at REV` for that revision only. If HEAD
has advanced, it reads `Last green: OLD · HEAD: NEW · verification pending`.
These are read-only displays: rendering never signals, cancels or restarts a check.

### Opt-in post-merge admission

`PI_AUTOWORK_POST_MERGE_POLICY=revision-barrier` requires an explicit
`PI_AUTOWORK_MAIN_CHECK` repository command and a positive
`PI_AUTOWORK_POST_MERGE_TIMEOUT` of at most 900 seconds (default 900, excluding
host check-slot wait). The default `async` policy is unchanged. Service installs
persist these settings without replacing unrelated saved grants; the CLI also
loads them on terminal launches.

The selected policy runs the command on exact canonical main through existing
main-check supervision, leases and restart adoption. Every further canonical
landing waits for a completed zero-exit green verdict bound to that revision and
attempt. Planning-only commits, batch tree receipts and an older green cannot
release it. Clean landings also use the existing index-lock/ref-CAS path so a
concurrent main advance cannot spend stale admission. Dirty-main guards remain;
owner planning files are not auto-committed in this mode. Deferred legacy conversion
is refused: migrate explicitly outside the runner before activation. Candidate/review gates
and isolated worker implementation continue unchanged. Automatic regression
reverts are disabled for this policy, including jobs adopted while enabling it.

The command writes schema-1 JSON at the absolute
`AUTOWORK_POST_MERGE_VERDICT` path (`<runner-state>/post-merge-verdict.json`).
It must echo `AUTOWORK_POST_MERGE_REVISION` and `AUTOWORK_POST_MERGE_RUN_ID`,
set boolean `complete: true`, and provide `status` and `failures`. Green requires
exit 0 and no failures; red requires exit 1 and nonempty named failures. The
supervisor's matching terminal receipt is also required. See the
[exact schema, environment, timeout and recovery contract](../docs/cross-host.md#revision-bound-post-merge-barrier).
This is bounded-command qualification, not a full-suite or live pass.

Red creates/deduplicates a revision-keyed repair through supported task writes in
the session, never by repairing canonical source or automatically reverting.
Pending repair incidents survive later checks/restarts and refused task commits;
repair Checks use candidate-specific variables and a private verdict path. Bounded
green receipts cannot substitute for full-suite base evidence, even with matching
command strings. No subsequent runner merge, including a repair merge, is permitted while red.
A real source repair requires separately authorized checked recovery; the resulting
external main advance is checked afresh. For transient failure, the runner CLI's
`--recheck-main --repo /path/to/project` requests a fresh attempt without cancelling
an adopted job, changing attempts or granting green. Terminal broken/red evidence
otherwise remains held; a dead job without a receipt is retried. The normal main
receipt/log/evidence files retain diagnostics; restart does not reset admission.

`tests/test_post_merge_barrier.py`, `tests/test_main_check.py` and
`tests/test_supervision_main_checks.py` provide offline seams, including import
isolation/DAG checks. These fixtures do not activate an installed service or qualify
a consumer's touched-project command, time bound, model execution or live hardware.

Manual closure is available for implementation, plan and inspection tasks, but writes no
receipt or passing-check claim. It alone qualifies neither a goal nor a prerequisite
explicitly listed in `verified_depends_on`. An authorized owner records a structured
waiver through `tasks field`: `owner_waiver` or `owner_qualification`, plus `waiver_actor`,
`waiver_at` and `waiver_for` naming one Acceptance or Checks item; a met-goal write names
these exceptions. See [closure provenance and owner qualification](task-store.md#writing-and-autowork-tasks).

Skills leave tasks active by default. Only an explicit user request permits a
new or renewed `Held by:` note; manual work uses supported execution leases and
workspace locks instead. For an explicitly requested pause, use
`autowork tasks hold TASK --by WHO [--until DATE]`; the runner never starts it and asks
nothing about it. `autowork tasks release TASK` lifts the hold; a dated hold ends by itself.

The fleet lists runners with open owner questions or task-store setup/repair first,
then other runners; each group is alphabetical. An idle runner with open questions or
tasks in `Needs decision` reads `Waiting on you`, not `Idle`. The headline and Needs field follow the
read-only `autowork tasks prepare --check` result: no store reads
`Setup required — run /docs-sync`; a legacy TODO.md + goals.json
queue reads `Migration required — Force converts legacy planning`; an invalid store
or interrupted conversion reads `Task store needs repair`. Docs Sync prepares and
reconciles the store; `autowork migrate` remains available as direct CLI conversion recovery.

The TUI and web view run Textual 8.2.8 (and textual-serve 1.1.3) through `uv`.

## Autonomous planning and waiting

Continuous runners retry safe repository-discovery failures after the persistent
30-minute cooldown, including after three failed attempts. The terminal receipt
must prove a preflight or settled provider failure with safe cleanup. Attempt
counts remain recorded until a completed collection. Restarting does not clear
those records or shorten the cooldown. Other auxiliary retry budgets stay bounded.
Uncertain acceptance, in-flight submissions, incomplete cleanup and malformed
recovery evidence never gain replay permission from this policy. A service also
checks its saved pause and deliberate-stop markers before discovery, even if the
unit is active. An unreadable marker observation refuses discovery. Task authority
and unavailable external inputs still apply. A recovery attempt is
not completed implementation or proof that the queue progressed.

An accepted `kind = "plan"` task runs through DOCS-MAINTAINER, not a code worker.
The maintainer can write its existing planning surface and the task's exact declared
Markdown files under `docs/plans/`. Directory, glob, traversal and symlink paths do
not grant extra access. The prompt and the landing check use the same original
path list. Product code, task evidence receipts and live authority remain excluded.
Routine reversible engineering choices follow the [standing decision policy](../docs/autonomy.md);
they do not require a repeated owner answer.

A completed planning-path refusal can receive one fresh bounded attempt after the
material path-policy correction. The new attempt records the policy and retains
normal retry limits. An uncertain submission or unproven cleanup does not gain a
retry from this migration. Runtime receipts are not deleted to force progress.

The task view shows a matching saved planning failure as `Blocker · Planning repair`,
with its refusal reason, rather than calling it ready or asking the owner to fix it.
The receipt must match the current task's exact record revision. Owner-only waits
remain local to their dependent tasks and do not age into engineering stalls.
Independent ready work can still run. Offline tests cover these contracts; installed
runner execution needs separate qualification.

### Post-completion Docs Sync

After a worker's verified closure is finalized **and landed on the canonical branch**,
DOCS-MAINTAINER runs a scoped `/skill:docs-sync` Maintain pass asynchronously in its
existing isolated checkout. Worker exit, a report, a held candidate or an unlanded
closure is not sufficient. Continuous, `--once` and draining runs use the same path;
finite runs collect an admitted pass before exiting, without dispatching another task.

The pass prunes eligible done records, their unneeded `tasks/evidence/ID.toml` receipts
and dedicated `docs/tasks/ID{,-report,-repair}.md` reports. It improves inactive pending
titles, short names, scope descriptions and Description/Notes/Sources notes, and can
clarify existing explicitly referenced files under `docs/plans/`. Git is the archive;
there is no keep-last-N quota or replacement completion ledger. A no-change result is
valid. The maintainer reports cleanup counts and concrete retention reasons.

The proposal gate rechecks selected-source identity and fresh ownership at collection.
Active/retained attempts, sequential claims, shared active plans, acceptance/checks,
priorities, goals, owner decisions, verified dependencies and live authority stay intact.
Only already-satisfied ordinary edges to pruned tasks may be removed, on inactive
consumers. New concurrent dependencies/references retain their evidence; immutable Git
references must resolve in reachable history. Pruning waits for a clean canonical
checkout. This is task/document maintenance, not implementation, dispatch, proof of
live acceptance, or permission to remove runtime recovery state/worktrees.

Closed engine slots and canonical receipts recover completion triggers after restart.
The existing maintainer journal records each captured completion independently, coalesces
bursts into one pass and leaves newer completions for the next pass. Provider reservations
are durable before launch; uncertain submissions or unproven cleanup never gain an
automatic replay. Refusals/no-change outcomes are recorded rather than spinning a finite
run; technical retries keep the existing bounded recovery policy. A refused or failed
pass is not a claim that cleanup happened. Offline tests exercise the real engine and
Git with fake model output; installed-model execution needs separate qualification.

## Questions

The fleet reads owner questions from `BLOCKERS.md`, preferring the runner's session
worktree until it merges into the repository. It lists both engine-generated
questions inside `<!-- pi-autowork:questions:start -->` / `<!-- pi-autowork:questions:end -->`
and maintainer sections headed `### Q-<planning task ID> — Planning stopped` outside
that block. Planning stops appear after engine questions as kind `decision`, effort
`decision`, unblocking one goal-continuation task. Their need includes the `Task:`
and `Question:` lines; a prose-only section uses its body instead.

`autowork ls --long` counts both kinds. The TUI shows both in the runner's question
detail and the Tasks window's Questions filter. A stop question stays visible under
its planning task ID even after that planning task closes; this does not reopen it
or add to the open-task count. Listing or refreshing questions never rewrites
`BLOCKERS.md` or answers a question. The engine still writes only its marked block.
Offline coverage in `tests/test_fleet_view.py` exercises mixed and planning-only
session files, CLI counts, the TUI's question-row filter and unchanged file bytes;
it does not qualify a live runner or terminal session.

## Retained attempt files

The stale `/tmp` sweep (`PI_AUTOWORK_TMP_STALE`) preserves scratch allocated to
unfinished engine slots, including held and interrupted attempts with no live
worker. It reads current slots for all registered runners, including stopped
runners, rather than relying on cached health; incomplete reservation discovery
defers the sweep. Released, closed and set-aside slots no longer reserve scratch;
close and set-aside also remove their allocated temp directories directly.

The same host-wide pass bounds each state key: `engine.err` keeps only its newest
bytes (`PI_AUTOWORK_ENGINE_ERR_BYTES`, default 1 MiB), and `full-check/`, `runs/`,
`sessions/` and `review-tmp/` evidence is trimmed by age (`PI_AUTOWORK_STATE_STALE`,
default 30 days) and total size (`PI_AUTOWORK_STATE_MAX_BYTES`, default 512 MiB).
Evidence named for an unfinished slot's task, a live `aw-r-`/`aw-b-` review scratch,
a gate receipt (`full-check/` `.json`/`.jsonl`), or a file a process still holds open
is never removed; a state key whose record names another live runner is skipped,
and incomplete slot discovery bounds `engine.err` but trims no evidence. The pass
reports the reclaimed bytes with the `/tmp` sweep.

When a task runs fresh after set-aside, its prompt lists earlier task branches
and any retained set-aside worktrees with their uncommitted paths. These files
are not restored automatically: inspect them and reuse only work relevant to the
current task, without modifying the retained worktree.

When a first attempt and its fresh retry both end with a dead worker or a report that
nothing needed changing, the slot is exhausted with no commit: `--parallel-clear-held`
has nothing to clear and the ordinary refill retries neither. One explicit, bounded
request, `--parallel-requeue-empty TASK --requeue-by ACTOR --requeue-reason TEXT`,
requeues that task once from current main and records the actor, the reason and the
held attempt's evidence on the new slot. Every earlier worktree and branch is kept
under its `-set-aside-N` name, and a held commit still goes through
`--parallel-clear-held`. A second empty or no-change hold after that requeue is parked
as a visible engineering hold and is never retried automatically.

An [acceptance hold](#verified-acceptance-evidence) resumes the same worker once
on the same attempt and retained commit, with the missing or unmet items named.
A second acceptance hold is a visible engineering hold: no further resume or fresh
attempt starts automatically.

### Attempt provenance

Each launch appends one record to `slot-data/<task>/attempt-N/provenance.jsonl`
before the worker starts: the task, attempt and attempt id, contract hash and
record revision, the worktree revision the worker reads, the resolved toolset
revision, host and model, the prompt's SHA-256 and byte length, the SHA-256 of
the repository instruction files as that worktree has them (`AGENTS.md`,
`CLAUDE.md`; absent ones are named `unavailable`, not guessed), and the
attempt's descriptive authority (ownership and live-grant identity). Records are
append-only: a resume adds a record for the same attempt with its new prompt
hash, a retry writes under its own attempt directory, and no earlier byte is
rewritten. A missing identity is `null` and is never inferred after the run; a
record marks a prepared launch, while the slot and journal record whether the
worker then started. The prompt text, instruction text, environment
and credentials are not stored. This file is evidence, not a grant: admission,
authorization, integration and closure never import or read it, so a recorded
profile cannot widen what an attempt may do.

A failed worker runtime keeps its bounded, redacted failure in the attempt's existing
`session.json` and worker log, not a fabricated task report. When no commit or changes
remain, reconciliation appends matching task/baseline diagnostics to the empty-worker
reason. This does not change its hold cause, retry budget or acceptance; malformed,
foreign and earlier-attempt metadata supplies no diagnosis. Retained commits and explicit
restart reasons take precedence over runtime failure text.

## Nous Portal setup (opt-in)

Pi remains the executor; Hermes owns the Portal login and subscription proxy.
Installing Autowork does not configure this route. With a current Hermes supporting
`hermes proxy` and Pi's compatible-endpoint `models.json` format:

```sh
# Replace with an exact model ID available on your Portal plan (may contain /).
MODEL_ID='model-from-your-plan'
autowork setup-portal --provider nous-local --model "$MODEL_ID"
# Review the proposal, then explicitly consent to that provider edit only:
autowork setup-portal --provider nous-local --model "$MODEL_ID" --apply
```

Portal setup is CLI-only; the fleet TUI has no setup shortcut. Without `--apply`,
the command only previews the proposal and leaves configuration bytes unchanged.
`--json` exposes the path, provider/model, endpoint, prerequisite diagnostics,
proxy state and applied flag to automation.

The default endpoint is `http://127.0.0.1:8645/v1`. `--endpoint` accepts only literal
`127.0.0.1` or `[::1]` HTTP addresses with a port and `/v1`; no remote hosts,
credentials, queries or redirects. Setup reads only local `/health`, without an
Authorization header or environment HTTP proxy. It does **not** request the upstream
model catalog, authenticate, refresh credentials, start/stop anything or call a model.
`available` means the expected Nous proxy reports stored authentication, **not** that
refresh, model access, billing or inference succeeded. Missing Pi/Hermes executables,
unavailable proxy, missing login and incompatible health responses have separate
messages. An unavailable proxy does not prevent preparing configuration for later use.

Only the selected provider under `${PI_CODING_AGENT_DIR:-~/.pi/agent}/models.json`
is prepared, using `openai-completions`, a non-secret `local-proxy-placeholder` key
and the exact model ID. Real credentials stay in Hermes. Other providers and settings
are preserved as JSON values (formatting may change). Existing models in that provider
are retained; changing its endpoint affects **all** its models. Only an existing entry
with this placeholder, compatible API and supported structure can be updated. Retained
model entries support `id`, `name`, `reasoning`, `input`, `contextWindow`, `maxTokens`
and complete nonnegative `cost` metadata. Other model fields, including `baseUrl`,
`api` and executable `headers`, are refused rather than silently overriding the
selected provider route. Provider-level `modelOverrides` are also refused. The same
validation runs before runtime model selection, including after manual config edits.
Conflicting keys/headers/API settings, malformed/duplicate-key JSON, symlinked files and edits since
the displayed proposal refuse without replacement. Writes use a private temporary file,
fsync and atomic replacement; repeated identical application preserves the file bytes.
No Pi defaults or runner model choices are changed by setup.

Use the same **absolute** `PI_CODING_AGENT_DIR` for setup and service installation
if you do not use Pi's default directory. The installer saves it and preserves it
on reinstall; foreground runners load it from repository settings unless explicitly
overridden. CLI/TUI service-model selection uses the saved directory, so it validates
against that service's catalog. An existing service without a saved directory uses
Pi's default directory, not the model picker's shell override. Relative agent directories
are refused to prevent resolution differences between setup and services.
Setup itself always targets the calling process's Pi
directory, displayed in the proposal; it never edits an unrelated service/profile.
Existing services need explicit reinstallation to adopt a different directory.

Starting a runner is a **separate operation that makes model calls**. For a new
service, set `PI_AUTOWORK_PRIMARY="nous-local/$MODEL_ID"` and
`PI_AUTOWORK_NO_FALLBACK=1` when running `autowork start /path/to/project`, or supply
an explicit available `PI_AUTOWORK_FALLBACK` instead. No Codex/OpenRouter login is
required for a proxy-only choice. Existing services use `autowork model` and the
supported installer for changed service settings. A missing proxy on a prepared
entry is diagnosed before worker/model selection, never delegated to workers for
repeated configuration approvals.

Offline coverage: `tests/test_autowork_command.py`, `pi-autowork/tests/test_portal.py`
and the headless `tui_pilot.py` use disposable configurations and health-only stubs;
no real proxy, auth, service lifecycle or inference is qualified. For manual
prerequisites and the separately opt-in live probe, see
[the cross-host guide](../docs/cross-host.md#nous-portal-through-the-local-proxy).
Contracts verified against [Hermes subscription proxy documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/subscription-proxy),
[Hermes health implementation](https://github.com/NousResearch/hermes-agent/blob/3a9d585e4f1a60588237587a72d365d187094c74/hermes_cli/proxy/server.py)
and [Pi compatible endpoints](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md#configure-a-compatible-endpoint)
(Pi 1.3.0 installed documentation); earlier Pi versions are not newly qualified.

## Fleet full-check capacity

Every runner of the same user shares **two full-suite slots** by default.
`PI_AUTOWORK_CHECK_SLOTS` sets the fleet limit; configure the same value for all
runners. The private lock pool is `~/.local/state/pi-autowork/check-slots`.
`PI_AUTOWORK_CHECK_ROOT` can select another shared private directory for isolated
fixtures or a whole fleet; use the same directory for every participating process.
XDG runtime directories and repository state directories do not create extra pools.

Main checks, batch/landing full checks and worker full suites through
`autowork-run` use this pool. Focused checker invocations take no slot; affected
checks take one only when conservative selection expands to the full inventory.
The repository's existing main-check lock still prevents duplicate main checks.
A queued full check names the current holders in its progress record and runner
status/fleet view. Queue time does not consume check, worker command or worker
task execution budgets and does not create an owner question. Kernel `flock` leases are reclaimed when the
last holder exits, including a killed process; a surviving check child retains its
lease until it exits. Reviews precede background main checks, with the existing
30-minute aging rule preventing background starvation. Native Hermes workers use
Kit's finite process guard for this queue-aware task deadline; parent-death and
cleanup checks remain enforced.

Worker admission retains its memory and disk checks. Load average does not block
ready workers: the fleet slots bound expensive suites while model workers wait.

## Affected landing checks

When a repository declares `python3 scripts/check.py` as its full check, batch and
single-candidate gates run `scripts/check.py --affected BASE..HEAD` on the merged
tree. The command prints the selected test modules and the reason for each:
changed tests, transitive repository Python importers (including lazy imports and
package re-exports), and code naming a changed path. It also runs the available
tree guard, Docs Sync document check and working-tree task-store validation.
`--list` previews the selection without running checks.

Unresolved paths, shared fixtures, checker/shard-map changes, CI and packaging
inputs select the full offline inventory. Non-test files under the check inventory
directories are conservatively treated as shared inputs too. Custom full-check
commands retain their existing behavior; optimistic landing still skips unsupported custom full gates,
while the affected checker runs before landing, including its conservative full
fallback when needed.

Private state retains the selection, reasons, range and core in
`full-check/tree-<tree>.json`, carries it through batch verdicts and records each
accepted supported landing in `landing-check/<task>.json`. A batch receipt names
the selection for the combined candidate tree, not only one task's changes. The
core list is a plan: consult the producing log to confirm which tools existed and ran.

Under the default asynchronous policy, main still runs the declared **full** suite
after landing, with existing regression attribution and repair/revert handling.
The [opt-in post-merge policy](#opt-in-post-merge-admission) instead qualifies its
explicit bounded command; it must not be read as a full-suite result. Only a passing full-inventory receipt for
the same tree and command can replace main's check. An affected-only pass cannot
mark main or its base green. Offline fixtures in `tests/test_check.py`,
`tests/test_pi_autowork.py` and `pi-autowork/tests/test_main_check.py` cover selection,
landing receipts and this full-main boundary; they do not establish live qualification.

## Verified acceptance evidence

A Verified close needs one recorded result for every acceptance item of the admitted
contract. The worker report's `acceptance` list contains `item` (exact item text),
`result` (`met`, `not_met` or `not_checked`) and `evidence` (the observed result and
supporting proof). Integration refuses incomplete or duplicate coverage. Every item
must be `met` with evidence, even when all checks pass. An empty `checks` list does
not satisfy a contract that declares checks.

A stopped or unreached verdict is `not_checked`. An item that needs a live or device
check stays `not_checked` and retains its `pending_live` evidence. It cannot close
Verified from offline results. These gaps leave the task open with an engineering
hold that names the items, not an owner question. No done record or receipt is written.
Reports from older in-flight attempts without the list are held with their candidate
work and reports preserved, not discarded or silently accepted.

The first acceptance hold automatically resumes the same worker in its retained
worktree on the same attempt and commit, once. Its prompt names the exact missing
or unmet items. The worker finishes missing work and rewrites its own `report.json`
with a result and evidence for every item; the runner never supplies or infers a
result. A second acceptance hold on that attempt is final: it keeps the commit and
names the remaining items as an engineering hold. No further resume or fresh attempt
starts automatically.

The reviewer receives the list and must confirm each item and its proof. An
unconfirmed `met` claim fails review. A successful close records the per-item results
in the receipt. `model_review` distinguishes a passed model review from a skipped
review or missing model-review evidence. The legacy `review` field remains the
aggregate validation verdict, not proof that a model ran.
Existing manual closure, historical receipt validation, live authority
and goal-qualification rules do not change. See the
[task-store close contract](task-store.md#integration-and-closure) for details and
offline regression coverage.

## Passing batch prefixes

After a batch's merged chain passes its existing gate, a contiguous passing prefix
can land while tail reviews continue in detached checkouts. Each complete candidate
still receives its own policy decision and independent review when required. A missing
or failed predecessor blocks early prefix landing; the terminal batch uses the existing
hold/reverification paths. Integration and closure remain serial engine operations.
Neither affected checks nor optimistic landing can qualify main's full suite.

The private batch channel publishes complete records by temporary write, flush/fsync
and atomic rename under `state/batch/<unpredictable-generation>/`. Admission identity
(task, engine attempt, contract and candidate), batch base, prefix tree, producing
check selection/command and review policy must match the current owned producer.
The coordinator reserves each accepted record once before promoting it to the engine's
one-use verdict channel. An old producer cannot publish into a replacement generation.
An independent merge-train car is invalidated as soon as a prefix moves its base.
Each producer keeps its unique output filename in its tip-pointer path. Gate logs,
status and rerun artifacts use its generation (PID for legacy direct calls), so
concurrent train cars cannot overwrite each other's pointers or diagnostics.
Immutable tree receipt reuse remains bound to its producing source and log.

Stopping invalidates the generation before replacement. The existing birth-bound
runtime supervisor must prove descendant cleanup; missing or false persisted cleanup
proof stops replacement, including after restart. Restart never adopts unconsumed
generations. A verdict consumed before integration may need ordinary verification
again; integrated work uses engine receipt recovery
and idempotent closure, not another landing. The terminal result excludes prefixes
already integrated by that producer.

Offline batch-prefix fixtures in `tests/test_pi_autowork.py` cover a fast A landing
before blocked B in optimistic and affected-gated modes, plus incomplete, stale and
replayed publication. The train fixture in `pi-autowork/tests/test_worker_tmp.py`
covers producer exit during prefix landing and independent-car invalidation. These
are control-flow checks, not live-service qualification or a measured latency benefit.

## Selective review pilot

`PI_AUTOWORK_REVIEW=auto` is the default. This conservative policy skips the
model only for small **ordinary prose** changes whose
committed task checks are already proved by a successful, source/log-bound gate.
It does not skip the gate, change full-main checks, grant publication, or treat a
timeout as a pass. Review findings about style, preferred abstractions, repetitive
tests or table-driven organization are advisory unless they demonstrate a concrete
defect or violate an explicit task requirement. Acceptance failures, regressions,
security issues and credible data-loss risks still block.

The pilot inspects the full candidate diff from the session baseline (first
parent) of the engine's two-parent integration merge, not the task's `touches` or
a worker's risk label. Ordinary commits and other unsupported merge shapes retain
review: their first-parent diff cannot establish the authorized candidate range.
Eligible files are ordinary `.md` and `.rst` files in
`docs/`, plus root `README.md` and `CHANGELOG.md`, at most ten files and 400
added/deleted lines. Deletions, renames, special file modes, sensitive paths/text
(including review, security, authority, planning and contract language), and
executable markup retain review. **Tests, source code and configuration always
retain review** in this first version; path names alone cannot prove them safe.

The task contract must be unchanged from the parent. Any review mention in the
task conservatively retains review. Repository instruction files may contain only
full-check declarations matching the executed command; any other instruction text
retains review rather than guessing which obligations it creates. CODEOWNERS,
indirect instruction files, and tasks requiring live/manual/owner acceptance also
retain review. Every declared task check must exactly match the gate's full
command, with a complete successful
result and no recorded skips; uncovered commands, affected-only selections,
missing/legacy evidence and unknown inventory retain review. Optimistic landing
without a pre-landing gate therefore still invokes the reviewer in `auto` mode.
Unknown setting values also retain review. Explicit `PI_AUTOWORK_REVIEW=1` reviews
every task. Explicit `PI_AUTOWORK_REVIEW=0` remains
the broader operator opt-out; it is not the selective policy and is not recommended
as a fleet-wide speed shortcut.

Each decision records its reason, mode, policy version, commit and tree under the
private state's `review-policy/<task>.json`. Single and batch paths share the
policy. Skipping requires a clean checkout and exact-tree evidence: a later batch
step's passing gate cannot prove an earlier step passes. A skipped-review batch
verdict is invalidated by tree, policy, mode or validation-command drift; it cannot
reuse the broader docs/task drift allowance.
A skip is a policy decision, not an independent model approval.

Use `autowork scorecard --days 7 <target>` to compare dispatch-to-integration time,
repeated attempts, regressions and owner attention; inspect decision records to see
how often review was actually skipped. Set `PI_AUTOWORK_REVIEW=1` to require a model
review for every task. Saved explicit service settings remain in effect; services
with no explicit review setting use `auto` when they load this code. Reloading a
running service is a separate operator action. Offline fixtures cover the default,
policy and receipt boundaries, not live model compliance or a measured throughput
improvement.

## Cost and owner attention

```sh
autowork attention 15 --task CACHE-01 --note 'Reviewed behavior'
autowork attention 5 /path/to/repository   # repository-level time
autowork scorecard --days 30 --json .
autowork scorecard --days 30 --csv . > evaluation.csv
autowork scorecard --days 30 --baseline /private/baseline.json .
```

### A slot kept for the owner's own continuation

A worker limit does not make a person wait behind the runner's own work. An attempt a person
paused, restarted or answered — or one the runner paused to resume safely — already held a
slot, so when new autonomous work has filled the pool, one such attempt may resume beside it:
N+1 workers run until that attempt ends. The reserve is one attempt at most, it takes a free
normal slot first, fresh work never uses it, the plan's exclusive, serial, dependency and
resource checks still apply, and the host memory and load gates still apply. While the
reserved worker lives, status keeps `max_workers` at N+1 with `owner_slot` 1 and
`configured_max_workers` at N, so the reported limit never reads below the workers actually
running; it returns to N when that worker ends.

### Evaluation report

Text, `--json` and `--csv` render the same evaluation metrics. JSON adds
`runners.<name>.evaluation` and `overall`, while retaining the existing runner
counters and `usage`. Each evaluation contains `summary`, `weeks`, `change`,
`baseline`, `baseline_change` and separate `phase_diagnostics`. Each metric has
`value`, `unit` and `status`:
`measured`, `estimate` or `missing`; missing JSON values are `null`, CSV values
are empty, and text says `missing`. Metadata (names, window bounds and week
numbers) is not a metric. CSV is long-form: one row per scope, runner, period
and metric, with the same labels and values as JSON. Periods are `summary`,
`week-1` onward, `change`, `baseline`, `baseline_change` and
`phase_diagnostics.<row>`. CSV also includes `cohort`, `identity` and `rules`
columns for diagnostic rows (empty for other periods).

Weeks are consecutive seven-day intervals from the window's start, oldest first;
the final week can be shorter (two days for a 30-day window). Boundaries are epoch
seconds: start inclusive, end exclusive except the final end. Changes are absolute
last-week minus first-week values, not relative percentages; percentage changes
use percentage points. A single-week window compares that week with itself.
Overall metrics pool task counts, duration samples and denominators across unique
repositories; runner medians and percentages are never averaged. Repeated targets
for one repository count once.

| Metric | Definition and limits |
| --- | --- |
| `verified_tasks`, `verified_tasks_per_day` | Distinct currently closed tasks with valid coordinator receipts and a close transition in the window, divided by actual period days. A reopened/reclosed task counts once in its latest close's week. A lifecycle close observation dates that transition when available; otherwise its Git timestamp does. Conversion itself closes nothing. |
| `manual_closed`, `owner_interventions` | Manual/legacy hand closes are separate, never verified. Each counts as one intervention even without telemetry. Other interventions are explicit `blocker_answered`, `contract_edited` and `hand_closed` facts, not retries or inferred Git authorship. |
| `unattended_completion_percentage` | Percentage of verified completions with no recorded lifecycle intervention or positive task-attributed owner time before closure, including observations before the window. Requires accepted/dispatch/close telemetry for every counted task. Unattributed positive owner time overlapping a task's lifecycle, or invalid attention records, makes this unknown. Manual closes enter neither numerator nor denominator. |
| `accepted_to_delivered_{median,p95}_minutes` | First acceptance to first delivery for each verified completion in the period; delivery is observed by the coordinator, not inferred from a candidate commit. |
| `dispatch_to_integrated_{median,p95}_minutes` | First dispatch to first integration, including retry delays. Both duration metrics are missing if any verified completion lacks ordered endpoints. p95 uses nearest rank, with no extrapolation for small cohorts. |
| `cost_per_verified_task_usd`, `owner_minutes_per_verified_task` | All window spend / recorded owner time divided by verified completions, including unattributed overhead and work not yet completed. Missing billing or missing attention for a verified task leaves the corresponding ratio missing. These are period ratios, not lifetime task bills; costs just before a week's boundary remain in that earlier week. |
| `recovery_success_rate` | Fraction of observed restart/interruption episodes followed by `worker_adopted`/`resumed` for the same task and attempt by the report end. A success means execution recovered, not that the task subsequently passed. Episodes belong to their trigger's week; no episodes means missing. |
| `regression_rate` | Fraction of the period's verified completion cohort with at least one explicit receipt-linked regression discovered during the selected window, observed through the report end. Multiple notes/reverts for one task count once. Older deliveries' discoveries remain visible in runner `regressions`, but do not inflate the completion cohort's rate. This is observed attribution, not proof that all regressions were found. |

With no verified completion, all rates and per-task ratios are **missing**, not
zero. Counts (including manual closes and interventions) remain measured. A
measured unattended result means no *recorded* intervention, not proof of complete
human-activity coverage. Recorded owner time is likewise not an inferred total.
An undated torn attention record cannot be proved outside a task's lifecycle, so
it conservatively leaves unattended results missing. Missing values propagate into
changes; no guessed zero fills a gap.

An optional private baseline file is a JSON object with finite nonnegative values:

```json
{"cost_per_verified_task_usd": 5, "owner_minutes_per_verified_task": 15}
```

`baseline.metrics` labels these owner-supplied values `estimate`, beside the
unchanged measured summary metrics. `baseline_change` is measured summary minus
baseline, also labelled `estimate` (or `missing` when measurement is unavailable).
Without `--baseline`, every format says `no baseline` and comparison values are
missing. Keep baseline files and exported reports private; they can reveal
repository names and operating costs. No evaluation output proves a live 30-day
run; [the evaluation plan](../docs/evaluation.md#30-day-evaluation) keeps that separate.

### Observed phase diagnostics

`evaluation.phase_diagnostics` (also under `overall`) is an observed-subset
report, not a replacement for strict whole-cohort summary timing. Each row has
`cohort`, `identity`, `rules` and `metrics`; text and CSV expose the same labels,
values and coverage. Rows are:

| Row | Identity and endpoints |
| --- | --- |
| `task_accepted_to_dispatched` | Task: first acceptance → first dispatch; retries collapsed. |
| `task_dispatched_to_integrated` | Task: first dispatch → first integration, including retry waits. |
| `attempt_running_to_reported` | Task + attempt: first running → first reported. |
| `attempt_reported_to_integrating` | Task + attempt: first reported → first integrating. |
| `attempt_integrating_to_integrated` | Task + attempt: first integrating → first integrated; may include holds. |
| `attempt_integrated_to_closed` | Task + attempt: first integrated → observed closed, matched to that attempt's ID. |
| `all_attempt_exposure` | Separate all-outcome cohort: first running → first reported. |

The six phase rows select tasks whose **latest receipt-valid verified close** lies
in the report window, using the same closure dating as the summary. Task rows
collapse retries; attempt rows retain distinct `(task_id, attempt_id)` keys for
those tasks, including failed/retry attempts. All retained lifecycle and slot-state
endpoints through cutoff can resolve a pair: starts may predate the window. Slot
records without an attempt ID (or with `unknown`/`unassigned`) do not create
invented attempts. A task-scoped close without an attempt ID cannot supply an
attempt's close endpoint.

Each row reports `eligible`, `observed_pairs`, `missing_start`,
`missing_end_terminal`, `right_censored`, `reversed`, `median_minutes` and
`p95_minutes`. Choose the first timestamp of each endpoint kind, not a later
convenient pair: a reversed first pair stays excluded even when a later end would
be ordered. Classify missing start first. A start without an end is terminal-missing
only if a later attempt of the same task (by first observation) or a closed state
is observed through cutoff at/after the phase start; otherwise it is
right-censored. Task rows also use later-attempt evidence when no close endpoint
is retained. A historical close cannot terminate newer work. A held/interrupted
attempt can resume, so those states alone do not mean terminal failure. For phase
rows, eligible equals the sum of observed, missing-start, terminal-missing,
right-censored and reversed counts. Median and nearest-rank p95 use only observed
pairs; empty samples have missing values, never fabricated zero latency.

`all_attempt_exposure` instead selects first-running starts in the inclusive
`[window_start, cutoff]` interval **across all outcomes**, including open and manually
closed tasks. `missing_start` counts observed attempt keys without running;
`left_excluded` counts starts before the window. Both are outside this row's
`eligible` count. Sum only ordered pairs whose first report is also in the window,
without clipping or extrapolation. `observed_completed_attempt_span_hours` is that
sum in hours (missing without pairs). Parallel spans can overlap or include
suspension: these are **attempt-span hours, never runner uptime**. The report does
not derive deliveries/runner-hour from them. Missing delivered facts or explicit
runner-availability intervals remain missing evidence, not inferred throughput.

See the [phase cohort contract](../docs/evaluation.md#phase-cohort-and-endpoint-contract).
Offline identity/coverage, missing-delivery and format-parity fixtures are in
`pi-autowork/tests/test_scorecard.py`; they do not qualify live delivery or uptime.

### Accounting details

The scorecard's JSON `usage` contains `tasks`, each with `attempts`, `roles`
(worker, reviewer, coordinator), `host_models`, token totals, billing and
`owner_minutes`. Runtime roles `verify` map to reviewer; merge, triage,
provision and maintainer map to coordinator. Repository-wide merge and maintainer
jobs stay unattributed rather than becoming invented tasks. New runs carry a unique `run_id`
and the engine `attempt_id` when available. Replayed IDs count once; distinct
retry runs add spend but not another verified or delivered task. Older records
without attempt/host metadata retain explicit `unknown` attribution. Records
missing a task or role count under `unattributed`, never disappear. Torn records
and replayed IDs are counted in `diagnostics`, with separate invalid-run and
invalid-attention counts. Unreadable run records invalidate the complete window
bill and cost-per-task ratios, but retain the valid measured subtotal.

`input_tokens`, `output_tokens` and `tokens` are observed counts, or `null` when
missing. `cost_usd` is `null` and `cost_status` is `missing` if any run lacks
provider-reported billing; `measured_cost_usd` retains the known subtotal, not
an estimate of the missing spend. `unknown_cost_tasks` lists tasks with missing
billing/usage. Subscription usage reports tokens with cost unknown. Pi's ordinary
`usage.cost` is catalog-derived, **not provider billing**, so neither it nor older
unlabelled `runs.jsonl` costs establish measured spend. Only amounts explicitly
labelled `cost_source: provider_reported` by a billing-aware adapter are accepted;
stock Pi output without that provenance remains unknown. There are no pricing
tables, billing API calls or budget changes here.

`cost_per_verified_task_usd` and `cost_per_delivered_task_usd` divide the window's
total spend by distinct verified closures and lifecycle delivery observations,
respectively. A retry does not add a completion. Missing billing, missing usage
for a counted completion, or a zero denominator leaves the ratio `null`.
The measured subtotal includes unattributed runs so their spend cannot vanish.

`owner_minutes` means **recorded** time, not complete coverage: unrecorded time
stays unknown. A task with no attention record reports `null`, never zero.
`autowork blockers` measures wall-clock time until its agent exits (including
idle time and failed/interrupted sessions); it records repository-level time,
not a guessed division among tasks. A forcibly killed wrapper cannot record its
duration. Other time must be logged with `autowork attention`; avoid logging the
same blocker session twice. `unattributed_owner_minutes` keeps repository-level
time separate. `interventions` counts the lifecycle categories `blocker_answered`,
`contract_edited` and `hand_closed`, without inferring human activity from model
retries or commit authorship.

Usage and attention logs live only in private runner state (`runs.jsonl` and
`attention.jsonl` under the repository's state key), including optional notes.
No usage records or attention logs belong in Git. These are offline accounting
facilities, not evidence that a live task was delivered or that a bill was paid.

## Runner health reads

`runner.json` and the runner's own `job.json` record both the PID and its Linux
process start ticks (`start_time`), separately from the wall-clock start time. It
also records the release the process runs (`toolset_rev`, and its directory as
`toolset`). A release is retained only while a live process uses it, so the record can
outlive the directory it names.
Status, fleet health and update-checkpoint reads require matching ticks and a
non-zombie process; a reused PID reads `not running`, and cannot keep an old job
current. Status also requires the runner lock to be held. Older records without
start ticks cannot establish liveness and read `not running` until the runner
writes a new record on startup or reload. These reads do not change the records.
Offline health and CLI fixtures cover matching, mismatched and missing identity;
main-check and ancestry fixtures exercise the same shared process helper. These
checks do not qualify recovery after a real host crash or live service restart.

Fleet reads isolate malformed runtime files per runner. A non-object JSON record,
unusable repository identity, or invalid consumed timestamp, count or container
marks that observation `unavailable`, with its source path and error. Boolean and
non-finite timestamps cannot establish current activity. Runtime counts from an
invalid observation are unknown, not zero; independently readable committed task
inventory remains available. The task snapshot's separate status reread applies
the same validation. Healthy sibling runners keep their current observations.
Main-check history fields `crashed`, `gated` and `failures` may be null when no
prior crash, gate or failure history exists: the running-check writer emits these
values and health publication preserves them. Non-null values still require strings
for `crashed`/`gated` and an array for `failures`; a nonempty main-check record also
requires string `state` and `rev` values. This exception does not permit nulls in
other validated fields. The offline writer-to-publication-to-fleet regression in
`tests/test_health.py` covers nullable history, non-null history, malformed controls,
healthy siblings, independent committed inventory and byte-preserving reads; it
does not qualify installed adoption or live recovery.
When multiple folders name one repository, collection prefers verified live runner
identity, then valid observations and their update time; retained historical-folder
errors remain visible without replacing the chosen current row.

A valid runtime record or registered service supplies repository identity; a folder
name alone never does. When neither runtime record supplies usable identity, health
reports the folder/source error without assigning it to a service; CLI collection
prints unassociated diagnostics to stderr and the TUI acquisition envelope retains
them. Installed services remain visible, and service lifecycle (including explicit
pause markers), confirmed Start readiness and PID/start-tick checks stay independent.
Readers preserve malformed bytes rather than repairing or deleting files. Offline
health/fleet fixtures cover isolation, unknown identity and retained task inventory;
they do not prove that a live service has corrupt state or loaded this repair.

An unusable repository (not Git, detached HEAD or a non-main branch), missing
runner tools or invalid `--workers` stops startup with exit **4 (needs attention)**.
The service does not restart this exit every minute. The reason is saved outside
the repository and remains visible in `autowork status <name>` and the TUI's
headline, Needs and Blocker detail, ahead of generic setup or start-service advice,
even if the checkout's `.git` is unavailable. Fix the named condition,
then use `autowork start <name>`; a successful startup clears the saved setup stop.
Read-only status and dry runs do not replace it. Generated units also suppress
restart for bootstrap/usage exit 2 (for example when Python cannot launch); such
pre-Python errors remain in the service journal. Reinstall the service to update
an older unit's exit-2 handling.

Startup compares the configured repository's Git common directory and toplevel
with independent probes that remove inherited `GIT_*` variables. A mismatched
`GIT_DIR` or `GIT_WORK_TREE` stops before repository writes; remove the inherited
variables and start again. The check runs before release snapshot creation, even
when the configured repository is the toolset itself. Release snapshot Git commands
also ignore inherited `GIT_*`, and runner descendants do not inherit Git routing,
index or config overrides.

Offline regression coverage in `tests/test_pi_autowork.py` checks setup exits
against the generated unit and injects Git routing into disposable repositories.
`tests/test_autowork_command.py` checks saved reasons through status, fleet reads
and the TUI display helpers, including escaped service names and a checkout
without `.git`. `tests/test_task_store_qualification.py` verifies exit 4 before
migration and successful task execution after conversion. These do not qualify a
live systemd service.

Engine JSON status includes `task_source`: the resolved `workspace`,
`repository_identity` (the resolved Git common directory, shared by linked
worktrees), pinned committed `revision`, and `observed_at` (Unix seconds). All
current task records in one answer come from that revision. Each task row exposes
its current `contract_hash` separately from the attempt's `admitted_contract_hash`;
a missing record or legacy attempt identity is `null`, never filled from the other
hash. These diagnostic fields do not grant authority or change task/attempt schemas.
Revision discovery ignores inherited Git routing and replacement refs.

The coordinator reuses status for at most five seconds, only for the same resolved
workspace and source revision, and drops it after its engine mutations. Health
preserves `task_source` and uses its `observed_at` for `snapshot_at` and snapshot
age, including cached writes and failed-read recovery; `updated_at` is only the
health-file write time. Legacy source fields and observation times remain unknown
when absent, rather than borrowing a new write time. Offline producer/cache/health
fixtures cover these contracts; they do not prove a deployed runner loaded this
source or qualify SSH responsiveness.

Fleet health rows and `autowork ls --json` add a display-only `observation`
object. It separates coordinator activity from successful task reads:

| Field | Meaning |
| --- | --- |
| `runner_alive` | PID and process start ticks match; a service PID or fresh file alone is not enough. |
| `health_written_at` | Finite health-file write timestamp, or `null`. |
| `snapshot_at` | Finite successful task-observation timestamp, or `null`. |
| `snapshot_age_seconds` | Nonnegative snapshot age, or `null` when unknown. |
| `task_state` | `current` for trustworthy provenance within the existing 600-second bound; `stale` for valid older evidence; `unavailable` for a failed read or invalid source; `unknown` without trustworthy provenance. |
| `error` | Read/source error, or `null`. |

Each `autowork ls --json` runner record also carries a `resources` object sampled
from `/proc` when the record is read; there is no sampler, journal event or
background service. It describes the coordinator and its live descendants:

| Field | Meaning |
| --- | --- |
| `coordinator_rss_mb` | Coordinator resident set size in MiB, or `null`. |
| `coordinator_cpu_seconds` | Coordinator user plus system CPU seconds, or `null`. |
| `process_count` | Live descendants of the coordinator, excluding the coordinator itself. |
| `fleet_rss_mb` | Summed resident set size of those descendants, excluding the coordinator. |
| `sampled_at` | Epoch time of this sample, or `null`. |
| `reason` | Why the sample is unknown, or `''` when it succeeded. |

A missing, dead or unreadable coordinator makes every value `null` with a stated
`reason`; a live coordinator with no live descendant reports `process_count` 0 and
`fleet_rss_mb` 0. One sample is a status observation, not a benchmark or a language
decision. External-wait time remains in `autowork scorecard` phase diagnostics.

A verified runner with a fresh health write can be **cycling** while task state
is stale or unavailable. Even the first failed read is unavailable in this display
object; the existing one-read grace for the execution-state label is unchanged.
Shared CLI/TUI verdicts and fleet logs show the distinction and snapshot age/error.
Runtime worker, waiting and stopped counts are `null` unless the observation is
current and the runner identity is alive; text lists use `?` for unknown counts.
Committed task inventory remains independently available. A separately verified
`job` can still show work in progress, but does not clear task-read errors or
refresh the snapshot. Paused and stopped service labels retain precedence.

An IDLE cycle with a failed task-status read reports **Task state unavailable**
with the reason, not **Queue empty**. This changes only the diagnostic: dispatch,
integration, waits, finite-run exit codes and zero-model empty-queue behavior stay
unchanged. Offline health/fleet and coordinator fixtures cover these cases;
installed adoption and live recovery still require separate qualification.

Status replays journal events in physical append order, not wall-clock order.
A decreasing event timestamp or an observation time before the latest event no
longer hides valid task/slot state. The JSON response adds `journal_timing` when
clock order is unreliable (`reliable: false`, `backwards` count and
`observation_before_latest` flag). Its four aggregate duration metrics and
journal-derived row elapsed times are then `null`; text renders them as `unknown`.
Event-derived counts remain available. Ordered histories retain their numeric
output, strict journal readers remain strict, and status never sorts or repairs
journal bytes. This is observation fault isolation, not proof of clock recovery.

Engine status reads wait up to two seconds for the writer lock, so brief dispatch
or integration writes do not immediately fail a read. If a read still fails,
health keeps its last observed state for that one failure, with the snapshot's
original timestamp and the read error. A second consecutive failure marks health
`unavailable`; without a previous snapshot it is unavailable immediately. A
successful read clears the failure episode without resetting an unchanged state's
stall clock. In `autowork status`, an unavailable Health line shows when reads
began failing, not when the previous healthy or blocked state began.

`autowork status` names the engine build, not only the toolset. `Toolset:` is the
package or checkout a new start or reload loads; `Release:` is the build that wrote
the state, with its commit date and the directory it imports from, marked `running`
or `last`, and it says so when that directory is gone. A runner pinned to an older
release therefore cannot read as current source: measuring the old build's behavior
as a defect of the reported `Toolset:` revision is the mistake this line prevents.
The two revisions are not compared, because `Toolset:` can be another checkout whose
revisions are not comparable. Repositories where no runner has recorded a release
show no `Release:` line, and status still writes nothing.

A saved service can outlive its checkout, for example after a repository rename or
a deleted toolset checkout. `autowork status NAME` then reports the saved
`PI_AUTOWORK_REPO` and `PI_AUTOWORK_TOOLSET` paths, the service state and the exact
missing path, and prints `autowork remove NAME` or the reinstall action after the
checkout is restored; it starts nothing and rewrites no settings. `autowork ls`
(and its JSON `toolset_problem`) and the TUI detail mark a saved toolset that is
missing or is not an Autowork checkout, while a healthy saved toolset stays
unmarked. `autowork start` still refuses the missing checkout or invalid toolset
with its explicit setup error and never falls back to the current release.

`autowork status` lists every unfinished task, with running, integrating, reported,
held and waiting tasks first, in that order. Rows retain the task, lifecycle and
reason columns; closed tasks appear as one finished-task count after the rows.
If the engine read fails (for example, while another process holds `writer.lock`),
status keeps the read error visible and lists saved `status.json` task rows with
that snapshot's age. The age uses the last successful observation, not the latest
failed read; missing timestamps are labelled `age unknown`. These read-only
fallbacks do not refresh the snapshot or establish that a saved worker is still live.
Saved rows lack pause metadata, so interrupted/released tasks retain those raw states
instead of being labelled failed. Offline CLI fixtures cover active-first rows and
the held-lock fallback.

## Session merge recovery

Before merging main, the coordinator tries to commit edits left in its own session.
If Git refuses a bookkeeping commit, the warning includes Git's output (including
hook diagnostics). When all staged paths are runner bookkeeping (`BLOCKERS.md`,
task-store files or frozen history), it unstages those paths without changing their
working contents so unrelated main fixes can merge. The edits stay in the session
for a later commit; they are not landed uncommitted. A refused work commit still
holds the landing. Repository hooks are never disabled for this recovery.

Overlapping-code landings need no idle interval. The runner attempts a guarded
content merge and preserves owner edits uncommitted. Owner-planning sweeps retain
their separate content-based quiet clock. A failed waiting merge retries on later
cycles even when refs and status are unchanged: a Git/process lock may have cleared.
Actual content conflicts, staged overlaps and detected active writers still refuse
landing without changing the owner's files, index or branch. See
[main-checkout changes](../docs/reference.md#main-checkout-changes-pi-runner)
for the external-editor race limit.

A merge refusal without unmerged paths is reported as `Merge pending` with Git's
message, not as an unknown-file conflict. Only actual unmerged paths trigger the
Pi conflict resolver. Overlapping uncommitted bookkeeping can still prevent the
merge; its contents and session worktree are kept for retry.

The engine's own disposable integration worktree is durable across a restart. When a
restart leaves it on disk, the next integration recognizes it by the marker the engine
writes into the worktree's Git admin directory, not only by the best-effort journal. A
registered, detached worktree carrying that marker is archived under a
`-set-aside-<timestamp>` name and recreated cleanly, with one `worktree_recovered` reason;
its uncommitted bytes are kept as an `integration-residue` patch when it cannot be moved.
A worktree of this repository without the marker, one from another repository, or one
whose recorded identity changed is never adopted: integration refuses it, naming the exact
path and `git worktree remove --force <path>` as the supported recovery.

If a merge invents a task/goal status, Evidence or closure value, or synthesizes a
contract field absent from both parents, the runner rejects it before landing or
adoption. The diagnostic names the record and field; the pre-merge head is restored
and main stays unchanged. Resolve by selecting parent values, combining only ordinary
notes; record intentional task transitions separately. See the
[merge and closure rules](task-store.md#integration-and-closure).

## Isolated runtime comparison

The [TOOLSET-117-cb spike](spikes/runtime-comparison/README.md) compares the current
CLI path, pinned AgwaB `runSubagent` headless execution and experimental pi-durable
on identical offline fixtures. It defines launch/observe/stop/resume and explicit
replay capabilities without changing the default worker. Measurements and limits
are in the [research comparison](../docs/research/pi-autowork-reference-architectures.md#worker-runtime-comparison-toolset-117-cb).
Do not configure services to load the spike; adoption requires an owner decision.

Design: [coordinator redesign](../docs/plans/2026-10-16-pi-autowork-coordinator.md),
[component layout](../docs/plans/pi-autowork-component-layout.md). Tests run from
`python3 scripts/check.py` (`pi-autowork/tests`).

Explicit dated `Owner decision: YYYY-MM-DD: deferred: …` notes display as
Deferred in task inventory with no expiry. A later dated nondeferred decision
restores presentation; deferral grants no execution or completion authority.
