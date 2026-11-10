# Verification and compatibility

## Rust candidate offline checks

The separate native-Octet crate is owned by `pi-autowork/rust/autowork/`.
Use Rust/Cargo 1.95.0 with the already-populated locked cache described in
[dependencies](dependencies.md#rust-autowork-candidate):

```sh
export RUSTUP_TOOLCHAIN=1.95.0
cargo metadata --locked --offline --no-deps --format-version 1 --manifest-path pi-autowork/rust/autowork/Cargo.toml
cargo check --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml
cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml
```

Repeat these commands from an unrelated disposable working directory using the
absolute manifest path. `cli::crate_has_one_product_owner` checks Cargo's sole
manifest owner, the `autowork-next` binary, integration-test targets, internal
module ownership and absence of the retired root implementation. Preserve all
existing test names, fixtures, lock bytes and the pinned Octet revision when moving
the crate. The shared Python checker does not execute Cargo; run these checks
separately. The [crate guide](../pi-autowork/rust/autowork/README.md) describes the
bounded offline/fake-agent authority and recovery fixtures and their port ranges.
Historical task-store, state, planning and fake-runtime reports still describe
their original source revisions, not fresh checks of this layout. Neither those
reports nor relocation checks qualify live models, devices or the Python service.

## Read-only fleet blocker report

`python3 -m unittest discover -s pi-autowork/tests/runner -p test_blockers_report.py`
checks a real disposable committed TaskStore, full reasons/IDs/questions, selector
decisions, unreadable/invalid sources, literal text and no repository/state writes.
The real `health.update` fixture retains full held/root and waiting observations
beyond the legacy compact-row limit, including all recorded affected IDs and
integration-backlog pauses/reasons. Builder fixtures also retain full main-check
revision/failure IDs and real question-reader acquisition errors without replacing
current committed eligibility.
Its pinned offline Textual pilot covers 80/120 columns, normal/view-only mode,
keyboard/menu click, explicit refresh/back, read-only editing refusal, whole-report
and selected-text copying, setup-only Backlog on `g` and control denial. An
Event barrier proves Escape works before a stalled read returns and close/reopen
does not overlap readers or publish the previous runner's result. Run the affected
selector on the implementation base as well. Cache/dependency skips are not
rendered passes. These fixtures do not prove an SSH terminal accepted its clipboard
sequence or that an installed TUI loaded the new source.

## Open task inventory and closed history

`python3 scripts/check.py pi-autowork/tests/runner/test_task_history.py` uses a real
committed store for open, legacy and explicit manual records; checks annotation
separation, unchanged task bytes and verified versus unverified labels; and runs a
pinned offline Textual pilot at 80/120 by 24 columns, normal/view-only. It checks
Open/Closed counts, closed records with related questions, visible tabs, numeric/
backward-tab navigation and denial of section/answer actions in history details.
Twenty unmatched-runtime annotations exercise a bounded diagnostics pane without
hiding the task rows; the pilot focuses it with **i**, copies its full text and
checks view navigation while it has focus.
Run affected modules from the implementation base as well. Historical receipts,
statuses and missing closure metadata are not repaired by these tests. A skipped
renderer dependency is not a rendered pass; remote-host adoption stays unqualified.

## Component inventory and source closure

Product Python tests are direct children of `pi-autowork/tests/runner/`,
`pi-autowork/tests/engine/` and `pi-autowork/tests/native/`. Shared Kit tests and
`src_fixture.py` remain in `tests/`; product helpers and fixtures stay under
`pi-autowork/tests/`. Use `python3 scripts/check.py PATH ...` for focused checks.

`tests/test_check.py` reconciles the complete method identities in
`tests/fixtures/python-layout.json`. The fixture is derived from immutable
pre-migration, failed-integration-base, landed-integration-base and task-base Git
inputs, not hashes regenerated from the migrated result. The chain also includes
the held integration's actual first-parent input and the corrective task base;
intentional scheduler test replacements retain their `fd36cedb` patch and blob
provenance instead of restoring superseded scheduling rules. Its snapshot rows retain
source blob IDs/modes and exact added/removed identities; each historical removal
names its replacement and the commit that renamed it. Later additions are allowed,
but lost baseline identities, changed exclusions and incomplete/duplicate shard
coverage fail. The self-contained fixture also works in shallow CI checkouts.
When an intentional later rename/removal needs reconciliation, preserve its Git
provenance rather than deleting an expected ID or repinning to a passing tree.

The extracted offline archive checks use paths with spaces and poisoned unrelated
cwd/PYTHONPATH, including deterministic fake inference. Native copied-release
fixtures remain separate; neither closure qualifies a model or installed service.
See [source layout](../pi-autowork/docs/source-layout.md).

## Skill task-persistence contracts

`python3 scripts/check.py tests/test_planning_cli_contract.py` checks every
first-party skill's explicit route to the shared task CLI policy, excluding pinned
upstream methods. It checks unavailable-tool, authority and deletion guidance and
uses a disposable repository to exercise the existing absolute Python entrypoint
from an unrelated directory: capabilities, add, literal JSON field update with a
record revision, readback and validation. The stale-read and completed-task safety
contracts remain covered. These checks do not prove model adherence or live delivery.

## Parallel offline acceptance

`python3 -m unittest pi-autowork/tests/engine/test_parallel_e2e.py` exercises the
real coordinator CLI and disposable Git worktrees with fake local workers. It
checks A/B overlap, C starting only after A closes, merged-tree validation,
cleanup, golden status text/JSON, journal metrics and capacity changes on refill.
`python3 pi-autowork/scripts/bench_parallel.py` compares that pipeline with one and two slots;
its overhead is elapsed time minus the controlled sleep critical path, including
process startup, Git, validation and waits, not isolated coordinator CPU time.
Neither test nor benchmark qualifies model-worker throughput or live hosts.
Integration regressions additionally refuse changed checked/archived contracts
and enforce retry-worker deadlines before returning WAITING.
`python3 -m unittest pi-autowork/tests/engine/test_parallel_compat.py` compares
sequential `owner_cycle.py` output, byte for byte, with a snapshot captured before
any parallel code, and checks that a Claude Code coordinator without
`--worker-command` or a missing worker CLI returns `SEQUENTIAL_FALLBACK` without
claiming or starting anything.

## Tree guard and fix hotspots

`python3 scripts/check.py` first runs `python3 scripts/tree_guard.py`, which refuses
conflict-marker lines, Python that does not compile and invalid JSON in tracked files;
`--rev <commit>` vets a candidate commit without a checkout and `--staged` the index.
A file that must show markers carries `tree-guard: allow-markers` in its first five
lines. To prevent fewer bugs being fixed twice: every fix ships with a regression test
that fails before the fix, a commit repairing an earlier one adds a `Fixes: <sha>`
trailer, and `python3 scripts/fix_hotspots.py` (fix commits per file, ratio and
fix-of-a-fix chains; `--json`) guides which files to refactor or test first.

## Verify

The offline check gives its test subprocesses a `TMPDIR` when the shell has none.
Three suites read it with `os.environ['TMPDIR']` and their fixtures shell out to it,
so an unset value used to report as a red tree in an interactive shell and invited
`--no-verify`. CI already exports one; the checker now supplies a real directory
instead of relying on the host.

### Prepare the pinned Textual cache

The optional renderer checks use `uv run --offline --no-project --with textual==8.2.8`.
They never install from the network during a check. Before offline execution,
prepare the cache explicitly on a network-enabled host:

```sh
uv run --no-project --with textual==8.2.8 python3 -c 'import textual; print(textual.__version__)'
```

Use the same Python interpreter, platform and uv cache for preparation and tests.
For workers with a shared cache, set `UV_CACHE_DIR` to that cache before both
commands. Installing Textual in an unrelated virtual environment does not prepare
this uv environment. Confirm preparation without network access:

```sh
uv run --offline --no-project --with textual==8.2.8 python3 -c 'import textual; print(textual.__version__)'
python3 scripts/check.py pi-autowork/tests/runner/test_task_prepare.py tests/test_check.py pi-autowork/tests/runner/test_blockers_report.py pi-autowork/tests/runner/test_fleet_view.py pi-autowork/tests/runner/test_planning_ui.py pi-autowork/tests/runner/test_task_history.py pi-autowork/tests/runner/test_tui_controls.py pi-autowork/tests/runner/test_tui_layout.py pi-autowork/tests/runner/test_tui_mouse.py
```

An unavailable pinned cache produces explicit dependency skips, not rendered
passes. The shared test helper recognizes uv's exit-1 resolver diagnostic
(`textual was not found in the cache`, pinned `8.2.8`, and `network was disabled`)
and the exit-2 offline unavailable-cache diagnostic. Other resolver errors, import
errors and pilot assertions still fail. Import-graph and non-renderer checks remain
enforced when optional renderer subtests skip. Deterministic subprocess fixtures
exercise available, unavailable and failing outcomes without a network or renderer.
They do not qualify rendering. Record actual pilot execution separately when the
cache is available; otherwise report rendered behavior as unverified.

The normal full-main gate remains required. Preserve its test results and skip
counts. Neither fixture coverage nor dependency skips qualify live services,
installed adoption or rendered behavior.

### Other offline checks

Repository-status chat coverage runs through the normal offline entry point:

```sh
python3 scripts/check.py tests/test_bundle.py tests/test_bundle_repo_status.py pi-autowork/tests/runner/test_autowork_command.py tests/test_workflow_commands.py pi-autowork/tests/runner/test_release.py pi-autowork/tests/runner/test_fleet_view.py
```

It exercises the public maintenance dispatcher with real disposable
Python subprocesses for bare fleet and literal named/absolute targets, retains the
plugin setup overview, and tests argument refusal, failed/empty/timed-out reads and
bounded literal gateway output. Native regressions additionally require status to
leave release worktrees unchanged, service-discovery failure to remain unavailable,
and unknown engine data not to become zero workers. The child uses the bundled
reader rather than an inherited older launcher. A real native CLI subprocess with
fixture providers also asserts that status never invokes authentication checks or
refreshes. These offline cases do not qualify live Telegram
routing or activate a gateway. A read-only invocation against installed local runner
records additionally checks the source handler; it still does not prove the gateway
loaded that revision.

README-audit fixtures exclude Markdown/HTML image examples in
single-line backtick spans, including mixed prose and literal shorter backtick runs.
They retain real image checks beside unmatched/escaped runs, across block boundaries,
and in literal-backtick link/image destinations, HTML and autolinks. Quoted titles,
angle destinations and continuation-line link titles have adjacent missing-image
regressions. Large unmatched-delimiter, backslash, bracket and angle-prefix fixtures
have five-second subprocess bounds; fixture bytes must remain unchanged. Multiline
code spans and ambiguous markup retain conservative auditing; these offline checks
do not establish full CommonMark/hosted GitHub rendering compatibility.

`python3 -m unittest discover -s tests -p test_preflight.py -v` includes runtime
installation-facts shape regressions. Malformed root, packages,
venv and environment values return a generic safe error before any validator
launch; valid facts retain interpreter selection, validation failure and missing
parser fallback. Fixture metadata/configuration remain byte-identical. These are
offline fixtures, not live setup or installed-profile qualification.

Consultation stream-json regressions exercise real local
subprocesses with Unicode NEL, line separator and paragraph separator inside
reply and tool-event JSON strings. LF-only framing must retain exact replies and
parseable sanitized receipts, preserve tool-limit observations and nonzero exit
verdicts, and mask synthetic credentials. These fixtures do not establish native
profile recovery or installed adoption.

`python3 -m unittest discover -s skills/docs-sync/scripts -p test_docs_manifest.py -v`
checks malformed array/object role statuses through `validate`, `check` and `stale`. Each command must return exit 1 with a role-specific diagnostic,
retain independent field errors, emit no traceback and leave fixture files unchanged.
Supported status values retain the existing positive and negative CLI coverage.

`python3 -m unittest discover -s pi-autowork/tests/native -p test_profile_consult.py -v` includes
real local subprocesses emitting valid stream-json replies and malformed stderr
for zero and nonzero exit codes. Diagnostics retain replacement
characters without discarding replies or changing failure verdicts. Malformed
stdout remains refused. These fixtures do not launch models or qualify native
profile recovery, installed adoption or delivery.


Document-anchor CLI fixtures cover numeric-suffix collisions in both heading orders
and chains of occupied suffixes. They check valid local links and
role-mapping fragments and reject nonexistent suffixes; this is offline checker
coverage, not a claim of full Markdown-renderer compatibility.

Document-anchor regressions exclude HTML-commented ATX/Setext headings and explicit
HTML anchors, including unclosed comments, from both local-link and role-mapping
checks. Commented headings do not consume visible duplicate suffixes;
visible headings, explicit anchors and literal comment markers in code spans remain
supported. CLI fixtures also verify that checking leaves source files unchanged.

The fake-Pi idle-update journey forces different human-readable log timestamps
before and after an exec restart. It requires multiple startup records bearing the
original runner PID, alongside the update, completed-queue and interrupt-exit
assertions. Timestamp variation is not a process-identity change.
Only display times are replaced; scheduling clocks and ISO timestamps stay real.
This is offline control-flow evidence, not live Pi/model qualification.

Collector response regressions also mask complete Cookie, Set-Cookie,
Authorization and Proxy-Authorization lines, including comma/semicolon tails,
case and indentation variants, through native and legacy response consumers. They preserve surrounding status/check lines and source bytes.
This covers actual header lines, not comprehensive secret redaction; installed
adoption and product recovery remain separate.

Native response framing regressions preserve complete answers containing embedded
Response headings, Unicode and long prompts. The collector shares the consultation
cache's character-count parser, reads native documents up to 256 KiB, and redacts
before capping display at 32,768 characters. Invalid or oversized frames produce
explicit gaps; legacy compatibility tails retain their unknown-coverage boundary.
`python3 -m unittest discover -s pi-autowork/tests/engine -p test_response_tail.py`
and `python3 -m unittest discover -s pi-autowork/tests/native -p test_profile_consult.py` cover both
callers. Frame validity does not prove execution/file association or completion.

Fleet execution metadata is bounded to twelve recent records per existing job,
not twelve across a profile: frequent sync occurrences must not hide paused
or infrequent development jobs. Collector regressions cover cross-job starvation,
removed/empty job sets, schema refusal and unchanged SQLite bytes. These metadata
windows do not bind output files to executions or establish a no-progress streak;
newest completed responses and original run identity still need separate verification.

```sh
uv run --python 3.12 --no-project --with-requirements requirements-test.txt python scripts/check.py
python3 scripts/check.py --list
python3 scripts/typecheck.py
python -m py_compile __init__.py scripts/bundle.py scripts/install-graphify.py
node --test tests/portable_pi.test.mjs
```

The checker decodes captured diagnostics as UTF-8 with replacement for malformed
bytes. Real subprocess fixtures cover successful and failing unittest runs emitting
invalid bytes, retaining their exit verdicts, sibling output and aggregate summary. Replacement is display recovery, not byte-exact log preservation.

The checker runs top-level and maintained bundled workflow tests in separate
Python processes, with a 600-second timeout per directory (the Autowork suite
alone takes about 150 seconds on an idle machine). The directories run at the same
time by default, and each one's output is printed whole and in the usual order, so a
full run takes about as long as the Autowork suite; `--jobs N` limits how many run at
once and `--jobs 1` runs them one after another. `--exclude PATH` (repeatable) leaves
a module or directory out of the selection, and `--shard I/N` keeps every N-th test id
from the I-th, so several machines can share one selection; a module whose tests cannot
be listed without importing runs whole on the first shard. `--list` prints the
inventory without importing tests. Symlinked test modules and maintained-directory
components below the resolved checkout root are skipped, so a linked `skills` or
workflow parent cannot redirect discovery into external tests. Checkout-root aliases
remain supported. This static check is not protection against concurrent hostile
filesystem replacement. Model, installed native backend and optional
integration suites are explicitly excluded with reasons; live opt-in flags are
removed from test subprocesses. Passing this gate does not qualify model/native
execution. Tests use temporary Git fixtures and may write offline scratch receipts.

Autowork check receipts fingerprint the command executable using the check's
working directory and execution environment, including relative or empty `PATH`
entries. Receipts created before the `execution-cwd-v1` resolution policy cannot
be reused; preserve them and run the check with a new receipt path. An unresolved
executable also prevents reuse.

Check receipts cache package metadata and interpreter hashes within a process.
Filesystem stamps detect in-place upgrades; unsupported providers or uninspectable
paths fall back to original discovery. Regressions cover add/edit/remove drift,
interpreter replacement, caller mutation, legacy/ZIP/symlink metadata and unreadable
search directories. Historical timing samples are not a current performance claim.

Current Autowork executes repository tasks in the current session without Kanban
setup or native-card transitions. Its direct-execution, recovery and isolated
no-agent qualification are described in the
[project verification contract](project.md#todo-first-delivery-qualification).
Model-driven recovery and useful-action timing remain separate qualification
requirements; no-agent execution is not a substitute. Current execution, parallel
integration, profile collection and source-bound receipt checks remain in the
maintained inventory. The coordinator owns the merged-tree full-suite gate.
Historical suite inventories and timing reports belong in Git history, not a
completed-task report. This cleanup migrates no installed profiles or schedules
and supplies no live qualification.

Selection reads every task and goal at one commit with a single `git cat-file --batch`;
a 1000-task store reads and orders in about half a second (`test_task_select.py` prints the time and
peak memory instead of asserting a wall clock).

Offline task-store regressions cover pinned reads and whole-store refusal
(`pi-autowork/tests/engine/test_task_store.py`), selection order and reasons
(`test_task_select.py`), the `autowork tasks` writer (`pi-autowork/tests/runner/test_task_commands.py`),
conversion (`pi-autowork/tests/runner/test_task_migrate.py`), preparation/bootstrap/recovery and
read-only diagnostics (`pi-autowork/tests/runner/test_task_prepare.py`), admission and closure by contract hash
(`test_parallel_dispatch.py`, `test_parallel_integrate.py`) and the runner's reopening of
a close a merge left under another contract (`pi-autowork/tests/runner/test_task_reopen.py`).

`tests/integration_plugin.py` additionally checks the actual Hermes manifest
reader, native install security scan, loader, bundled skill reader, Telegram menu, CLI queue, gateway routing,
and unload behavior. Run it using Hermes' Python environment with the Hermes
source root on `PYTHONPATH`. It uses a temporary profile and a capture callback
instead of sending Telegram messages or calling a model. Native command collisions,
such as Hermes' `/goal`, require a registered namespaced Kit skill fallback; they do
not replace the Hermes command or excuse a missing skill.

The focused profile-policy fixtures in `tests/test_plugin.py`,
`tests/test_preflight.py` and `tests/test_install_plugins.py` cover fresh interactive
profiles, explicit autonomous selection, retained approval/turn values, canonical
and legacy settings, opt-outs and read-only setup previews. The native loader check
also verifies interactive values, explicit autonomy, opt-out and idempotent writes.
It does not qualify a live profile or unattended model behavior.

`tests/integration_bundle.py` checks an existing isolated `HERMES_HOME`: all
loaded skill content, CLI queues and captured gateway routing for every generated
alias, plus the expected-import inventory. Run it with the same Hermes Python
environment and source `PYTHONPATH`. It exits nonzero for missing plugins, missing,
blocked or ambiguous skills, and skill sources not yet set up. Native command registration is inspected; upstream actions, external
services, and live Telegram delivery are not invoked.

From this repository's root, use the installed Hermes interpreter and source
checkout (adjust `HERMES_SOURCE` if Hermes is installed elsewhere):

```sh
HERMES_PYTHON="$(hermes --print-runtime-command --module runpy | python -c 'import json, sys; print(json.load(sys.stdin)[0])')"
HERMES_SOURCE="$HOME/.hermes/hermes-agent"
PYTHONPATH="$HERMES_SOURCE" "$HERMES_PYTHON" -c 'import hermes_bootstrap, runpy, sys; runpy.run_path(sys.argv[1], run_name="__main__")' tests/integration_plugin.py
```

For the full bundle check, first provide an existing isolated profile where the
bundle and its declared imports have already been installed. Do not point this
check at your live profile; plugin loading may write runtime records.

```sh
HERMES_HOME="/path/to/isolated-installed-profile" PYTHONPATH="$HERMES_SOURCE" "$HERMES_PYTHON" -c 'import hermes_bootstrap, runpy, sys; runpy.run_path(sys.argv[1], run_name="__main__")' tests/integration_bundle.py
```

Before a push, the pre-push hook runs the checker's core contracts (docs check and
task-store validation, a few seconds) and then `scripts/affected_tests.py --run` from the sha
the remote already has. A document no test reads selects no test module, and a document
reaches at most the tests that read it and the tests of the code that reads it; code no test
reaches still selects the whole suite (`python3 scripts/pre_push_check.py --install` writes the hook,
or chains it after an existing one-line exec hook such as the private-terms check).
A push with nothing new, a deletion, or `KIT_PRE_PUSH=0` runs nothing; `git push
--no-verify` skips every hook. The full suite is CI's job.

Before running checks, every changed local ref must resolve to the checked-out
HEAD commit. Annotated and lightweight tags and multiple refs are accepted when
they peel to that same commit. A different commit, an unavailable or non-commit
object, or an unreadable HEAD refuses the push without running checks or moving
Git refs or files. Use a checkout at the intended commit, or explicitly choose the
existing CI-only option above. After successful checks, the hook reads HEAD again
and refuses observed revision drift or an unreadable HEAD. Check failures retain
their original result.

Checks still run against the current working tree, including same-HEAD dirty files.
This guard checks revision identity, not an immutable candidate tree: uncommitted
changes and changes not observable from HEAD remain outside that guarantee. CI
checks the pushed revision.

A failing affected run is not proof of a red tree on a busy host. Every runner and
worker test that waits on a window or a check slot can fail while the machine runs
its own suites: the hook now prints the load average and cpu count when it refuses,
so the failure can be attributed instead of bypassed. Run one failing module alone
before you treat the tree as broken; a second failure there is the tree's.

The offline suite runs in GitHub Actions as two jobs: `fast` runs every module except
`pi-autowork/tests/runner/test_pi_autowork.py` (`scripts/check.py --exclude pi-autowork/tests/runner/test_pi_autowork.py`),
and `runner` runs that module alone on three machines
(`scripts/check.py pi-autowork/tests/runner/test_pi_autowork.py --shard I/3`), because its tests each start
a real runner over a Git fixture and were three quarters of a 17-minute single job.
CI byte-compiles only `__init__.py`, not the four files above. Live Telegram delivery and model
execution require your configured Hermes installation.

## Live qualification harness (A–E)

The [authorized-autonomy audit](research/authorized-autonomy-audit-2026-11-04.md)
adopted five reliability fixes, and their deterministic tests do not exercise the real
process, filesystem and remote path. The qualification harness is one disposable-target
scenario set for those five checks. It runs on demand, is not part of `scripts/check.py`,
and its exact path and command live in the task record that creates it.

| Scenario | What it drives | Evidence |
| --- | --- | --- |
| A | a real `git push` to a local bare remote whose pre-receive hook stalls past the 300 s timeout, then the remote reconciliation | the push outcome, the remote refs, and that the process did not raise |
| B | a torn `BLOCKERS.md` (start marker, no end marker) and a failed replacement/commit, then the real recovery | the file bytes before and after, the commit, and the repaired block |
| C | real dispatch in a disposable repository: a legacy prose grant, a structured grant, a foreign scope, and a worker edit to `tasks/` | the waiting and dispatched rows, and the held reason |
| D | real dispatch with a paused or answered attempt and a full pool, plus an exclusive holder | the launched count, the reserve, and the typed waiting reason |
| E | one real dispatch with a stub worker, then a resume | the `provenance.jsonl` records, the prompt hash, the append-only prefix, and the absence of prompt or environment text |

Rules:

- Each scenario builds a temporary Git repository and its own state, then removes
  them. It uses no real remote, model, service, credential or production checkout.
- The harness prints one JSON object per scenario and exits nonzero on any failure.
  Its transcript is private; the command and its summary are the evidence.
- A stub worker exercises the engine's launch path. A model-driven delivery and an
  interrupted real runner remain the owner's live qualification, not
  this harness.
- A product defect found by a scenario is reported with its record, never fixed by
  changing the harness's expectation.

## Compatibility

Verified locally on October 11, 2026; this is a tested baseline, not a discovered
minimum-version guarantee:

| Layer | Evidence / boundary |
| --- | --- |
| Host | Ubuntu 24.04.4, x86_64 |
| Hermes | `v0.21.6+556.g6a2662a`, source `6a2662a4aaad68e1b75f6e7ac789409aa653abf7` |
| Native integration interpreter | Hermes-managed Python 3.14.7 |
| Offline tests | Python 3.12; the suite also requires PyYAML (profile audit, portable package and Telegram menu tests) and mypy 1.19.1 for the strict selection/authority typecheck |
| CI declaration | Ubuntu runner and Python 3.12 in [.github/workflows/test.yml](../.github/workflows/test.yml); a declaration is not a current passing CI result |
| Required Hermes APIs | `register_skill`, `register_command`, origin-aware `inject_message`, profile-scoped loader and native gateway control socket |
| Other Hermes revisions / macOS / Windows | Not qualified by these receipts; shell setup requires Bash |

The manifest does not declare `requires_hermes`, although current Hermes loaders
enforce it when present. Do not interpret
“current Hermes” as compatibility evidence. Check `hermes --version`, then use the
native integration tests against that interpreter. There is no supported claim
that an earlier version has all required APIs.

`tests/integration_autoresearch.py` checks all research aliases, CLI queues,
the Telegram menu (current workflows advertised, Autoresearch compatibility aliases
not advertised) and captured gateway origin routing. Like the main plugin
integration test, it runs without a live model or message delivery.

## Core versus full-stack diagnostics

`python3 -m unittest discover -s tests -p test_doctor_modes.py` covers core success
with external gaps, strict full-stack failure, command ownership, missing skill
registration, plugin load failure and readable/JSON output. The native plugin
integration fixture additionally loads a real bundle-only profile and requires
core success plus full-stack failure from the same installed state.
These checks do not call a model or send a Telegram message. Use the separate
[operator-run onboarding checks](onboarding.md) for those outcomes.

## Installer preflight

`test_preflight.py` covers admission failure before any installer call, unchanged
profile snapshots, incomplete destination conflicts, source timeouts and the core
policy/memory preview. Run it with Hermes's managed Python as well to exercise
strict YAML rejection, preservation of custom memory providers and secret-safe errors (those parser
cases skip when ruamel.yaml is unavailable). `test_complete_setup.py` separately
checks orchestration after admission, including no installation calls on dry-run,
and rejects missing declared native source/bootstrap payloads before stages run.
The setup/provisioning and Graphify fixtures copy the same-release Python
closure and exercise real `pi-autowork/src/autowork_runtime` bodies through the `scripts/`
entrypoints; external commands and gateway responses remain private fixtures.
No passing preview is evidence of a live model or Telegram workflow.

## Update self-healing and Telegram menu checks

The implemented update/menu changes in `b021c54` have focused offline contracts:

```sh
python3 -m unittest discover -s tests -p test_telegram_menu_policy.py
python3 -m unittest discover -s tests -p test_setup_runtime.py
python3 -m unittest discover -s tests -p test_update_bundle.py
```

Menu fixtures check that only current workflow names receive priority, stale
compatibility entries are removed without deleting user choices, reconciliation
is idempotent, and typed compatibility registrations remain available with required
text hints. Finalization fixtures reject settings that remain unhealed after load.
Local-Git updater fixtures check `settings_healed`, one requested restart after
change, `not_running` for an absent gateway, no restart on an unchanged retry, and
`pending` with no second restart while a requested one is still draining.

These use temporary profiles and mocked activation/restart calls. Passing them
proves the local contracts, not that a real gateway drained, reconnected, refreshed
Telegram menus, delivered a message or executed a model. Inspect the actual update
receipt and activation/transport evidence before making those live claims.

## Task store checks

```sh
python3 scripts/check.py pi-autowork/tests/engine/test_task_store.py pi-autowork/tests/engine/test_task_select.py \
  pi-autowork/tests/runner/test_task_commands.py pi-autowork/tests/runner/test_task_migrate.py pi-autowork/tests/runner/test_task_prepare.py \
  pi-autowork/tests/runner/test_task_store_qualification.py
```

The fixtures use real disposable Git repositories: a malformed or conflicting record
refuses the whole store with its `path:line`, a write that would break the store is
undone, conversion proves the store selects what the old queue selected, and the
qualification fixture runs one task end to end (refused before migration, selected,
run and closed with one receipt after). Preparation cases additionally cover new
repository bootstrap, conversion staging/recovery, unchanged-repeat behavior,
read-only HEAD diagnostics and active-contract protection. These are offline
fixtures, not proof of model adherence. The safe root gate remains:

```sh
uv run --python 3.12 --no-project --with-requirements requirements-test.txt python scripts/check.py
```

These offline checks do not qualify installed model behavior, native task
execution, publication or Telegram reporting. Keep those live gates separate.
At the repository root, `python3 -m unittest discover -s pi-autowork/tests/native -p test_owner_cron.py`
checks prompt generation, repair-mode opt-in and preserved job settings without
scheduling or executing a live repair.

## Paseo plugin checks

The Paseo plugin in `integrations/paseo/` has its own Node 24+ dependency tree and CI
job (`.github/workflows/paseo.yml`). From the repository root:

```sh
npm --prefix integrations/paseo ci --ignore-scripts
npm --prefix integrations/paseo run check
npm --prefix integrations/paseo run package:check
```

These run the strict native-client and server TypeScript checks, the offline fixtures,
the pinned Paseo 0.15 compiler and an isolated plugin runtime. `python3 scripts/check.py`
runs the same `npm run check` when the dependencies are installed and reports a skip
reason otherwise. None of this installs into or reloads a user daemon. See the
[plugin qualification record](../integrations/paseo/docs/qualification.md); physical
Android and desktop clients, provider planning and real service controls remain
separate live acceptance.

## Portable package checks

Codex/Pi packaging and adapter-reference checks run in `tests/test_portable_package.py`.
The Pi Node tests cover command registration, literal arguments, queued messages
and packaged support files. CI uses Node 22 for those tests. See
[cross-host installation and verification](cross-host.md) for tested client versions
and disposable-home installation checks. Package discovery does not prove model
execution or completion of an Autowork task. Required model-driven qualification
remains separate from package discovery and needs explicit scope and real evidence.

## Qualification boundaries

Removing completed-task records does not qualify the following current surfaces.
Any still-required proof remains an open product obligation, under its original
scope and owner/live gates, not a reason to recreate completed-task reports:

- Installed-profile registration, legacy settings preservation, native security
  admission, gateway activation and Telegram delivery require their actual host
  checks. Source tests and installation-script fixtures are insufficient.
- Real service stop/disable/failure-state cleanup, restart configuration, forced
  conversion, release/grant binding, interrupted-worker adoption and observation
  recovery need scoped live proof. Do not operate an unrelated service or infer
  execution ownership from a saved approval.
- Work/planning/maintenance instruction adherence, provider execution and private
  monitor permissions need actual authorized evaluation. Offline routing and
  classification do not establish model behavior or safe live coexistence.
- Physical Android/desktop display, SSH responsiveness/freshness and clipboard
  delivery require the real client/transport. Headless pilots and event-loop
  assertions do not establish remote latency or installed activation.
- Consumer-specific touched-project checks still require a complete inventory and
  actual budget evidence; no source-only result proves a runtime speedup or a
  fifteen-minute bound. The real-repository evaluation remains independently gated.
- Native signed downloads/installation and destination executable readback require
  supported-host qualification. Hosted README rendering, external links and live
  badge state likewise require external readback; local previews are approximations.

Keep current task and goal requirements authoritative. Never convert an unrun
qualification to passed because its earlier implementation record was pruned.
