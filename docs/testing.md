# Verification and compatibility

## Removed executor checks

Executor, task-store, Rust candidate, Textual and Paseo plugin checks no longer
ship. Their [prior test contracts and qualification gaps](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/testing.md#rust-candidate-offline-checks)
remain immutable evidence, not current test commands. Existing tasks, worktrees,
attempts and recovery state are preserved. Removal does not satisfy outstanding
live acceptance.

## Component inventory and source closure

Use `python3 scripts/check.py --list` for the maintained offline inventory and
`python3 scripts/check.py PATH ...` for focused modules. Native Hermes source
lives in `src/kit_runtime/`; portable packages retain their host adapters.
Source/layout checks do not qualify installed models or delivery.

## Skill task-persistence contracts

Planning checks enforce GitHub-native publication and preservation of legacy
records, not local task CLI execution. See [Plan Handoff](../skills/shared/PLAN-HANDOFF.md).

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

### Other offline checks

`tests/test_project_status.py` checks current project contracts and preserved live
qualification boundaries. Native plugin status/list/update remain
maintenance operations; their registration tests do not qualify live Telegram
routing, gateway activation or model execution.

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

`python3 -m unittest discover -s skills/docs-sync/scripts -p test_docs_manifest.py -v`
checks malformed array/object role statuses through `validate`, `check` and `stale`. Each command must return exit 1 with a role-specific diagnostic,
retain independent field errors, emit no traceback and leave fixture files unchanged.
Supported status values retain the existing positive and negative CLI coverage.

Document-anchor CLI fixtures cover numeric-suffix collisions in both heading orders
and chains of occupied suffixes. They check valid local links and
role-mapping fragments and reject nonexistent suffixes; this is offline checker
coverage, not a claim of full Markdown-renderer compatibility.

Document-anchor regressions exclude HTML-commented ATX/Setext headings and explicit
HTML anchors, including unclosed comments, from both local-link and role-mapping
checks. Commented headings do not consume visible duplicate suffixes;
visible headings, explicit anchors and literal comment markers in code spans remain
supported. CLI fixtures also verify that checking leaves source files unchanged.

Collector response regressions also mask complete Cookie, Set-Cookie,
Authorization and Proxy-Authorization lines, including comma/semicolon tails,
case and indentation variants, through native and legacy response consumers. They preserve surrounding status/check lines and source bytes.
This covers actual header lines, not comprehensive secret redaction; installed
adoption and product recovery remain separate.

Removed executor/profile-consult framing checks remain
[immutable evidence](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/testing.md#other-offline-checks),
not current test commands or live qualification. Retained collector behavior must
be checked through its maintained tests.

Fleet execution metadata is bounded to twelve recent records per existing job,
not twelve across a profile: frequent sync occurrences must not hide paused
or infrequent development jobs. Collector regressions cover cross-job starvation,
removed/empty job sets, schema refusal and unchanged SQLite bytes. These metadata
windows do not bind output files to executions or establish a no-progress streak;
newest completed responses and original run identity still need separate verification.

```sh
uv run --python 3.12 --no-project --with-requirements requirements-test.txt python scripts/check.py
python3 scripts/check.py --list
python -m py_compile __init__.py scripts/bundle.py scripts/install-graphify.py
node --test tests/portable_pi.test.mjs
```

The checker decodes captured diagnostics as UTF-8 with replacement for malformed
bytes. Real subprocess fixtures cover successful and failing unittest runs emitting
invalid bytes, retaining their exit verdicts, sibling output and aggregate summary. Replacement is display recovery, not byte-exact log preservation.

The checker runs top-level and maintained bundled workflow tests in separate
Python processes, with a 1,800-second timeout per test process by default. It uses
one or two processes according to available capacity. `--jobs N` requests a process
count, capped at two; `--jobs 1` runs them one after another. Output stays grouped
in directory order. The removed executor's Paseo/renderer checks are not run.

`--exclude PATH` (repeatable) leaves
a module or directory out of the selection, and `--shard I/N` keeps every N-th test id
from the I-th, so several machines can share one selection; a module whose tests cannot
be listed without importing runs whole on the first shard. On a shard, a module with
20 or more selected test ids is dealt across the shard's processes, and the largest
units start first. A new push to a pull request cancels its older CI run. `--list` prints the
inventory without importing tests. Symlinked test modules and maintained-directory
components below the resolved checkout root are skipped, so a linked `skills` or
workflow parent cannot redirect discovery into external tests. Checkout-root aliases
remain supported. This static check is not protection against concurrent hostile
filesystem replacement. Model, installed native backend and optional
integration suites are explicitly excluded with reasons; live opt-in flags are
removed from test subprocesses. Passing this gate does not qualify model/native
execution. Tests use temporary Git fixtures and may write offline scratch receipts.

Historical suite inventories and timing reports belong in Git history, not a
completed-task report. This cleanup migrates no installed profiles or schedules
and supplies no live qualification.

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

By default the pre-push hook runs only the revision guards and core contracts.
It does not select or run test modules. CI still runs the full suite.
To also run targeted tests locally, use `KIT_PRE_PUSH=affected git push`. This adds
`scripts/affected_tests.py --run --defer-full` from the sha the remote already has.
In this mode, targeted test failures refuse the push. Whole-suite selections (check, CI, packaging or an unresolved mapping such as
`.gitignore`) print the reason and defer test execution to CI instead of blocking a push on
all modules. This is a deferral, not a passing local test result; the core contracts still run.
A document no test reads selects no test module, and a document reaches at most the tests
that read it and the tests of the code that reads it. Direct `scripts/affected_tests.py --run`
keeps the conservative whole-suite fallback; `--full` explicitly selects the full suite and
cannot be combined with `--defer-full`.
`python3 scripts/pre_push_check.py --install` writes the hook, or chains it after an existing
one-line exec hook such as the private-terms check. Existing installations use the updated
script without reinstalling the hook.
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
checks the PR merge revision or the commit pushed to `main` or a tag. A feature
branch push alone does not start a second copy of the PR checks.

A failing affected run is not proof of a red tree on a busy host. Every runner and
worker test that waits on a window or a check slot can fail while the machine runs
its own suites: the hook now prints the load average and cpu count when it refuses,
so the failure can be attributed instead of bypassed. Run one failing module alone
before you treat the tree as broken; a second failure there is the tree's.

`main` requires the GitHub Actions `test` check and an up-to-date branch. Eight
`shard` jobs run the full offline Python suite with Python 3.12, each with
`check.py --shard I/8`. The first shard also checks plugin syntax and runs the Pi
adapter tests with Node 22. The `test` job passes only when every shard passed. Inspect
[the workflow](../.github/workflows/test.yml) for its current inventory. Live
Telegram delivery and model execution require separate qualification.

## Live qualification harness (A–E)

The [prior executor scenarios and remaining proof](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/testing.md#live-qualification-harness-ae)
are retained immutable requirements evidence, not runnable Kit checks. Removal
qualifies none of those scenarios. Reconcile still-required outcomes into GitHub
Issues before a successor pilot; preserve original evidence and live/owner gates.

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
closure and exercise real `src/kit_runtime` bodies through the `scripts/`
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

The task CLI and executor tests are removed. Existing task records remain
read-only migration evidence; do not validate by installing the old executor or
rewrite records to make a check green. See [migration](../skills/shared/PLAN-HANDOFF.md).

## Paseo plugin checks

Paseo-hosted Kit sessions and Orbi delivery require separate live qualification;
offline checks do not establish physical-client or live-control acceptance.

## Portable package checks

Codex/Pi packaging and adapter-reference checks run in `tests/test_portable_package.py`.
The Pi Node tests cover command registration, literal arguments, queued messages
and packaged support files. CI uses Node 22 for those tests. See
[cross-host installation and verification](cross-host.md) for tested client versions
and disposable-home installation checks. Package discovery does not prove model
execution or completion of a delivery task. Required model-driven qualification
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

## Pi provider setup in the TUI

The executor TUI and provider bridge are removed. The
[prior provider qualification boundary](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/testing.md#pi-provider-setup-in-the-tui)
remains evidence, not a supported setup path. Ordinary Pi provider configuration
belongs to Pi; removal does not alter interactive credentials or model settings.

## Local planning model smoke

The [opt-in Pi planning smoke](../evals/README.md#opt-in-local-planning-smoke-pi)
runs Plan With Me or Plan For Me against a disposable repository with existing
authentication and explicit portable-skill loading. It retains private evidence
and rejects an empty response, failed reads, write/edit attempts or changed fixture
files. Review answer semantics and shell activity separately. It neither publishes
issues nor qualifies Orbi delivery. `tests/test_planning_smoke.py` uses a fake Pi
for the runner's failure boundaries; the offline inventory never calls a model.
