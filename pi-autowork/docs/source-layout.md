# Source layout and compatibility

The accepted [one-product-root contract](../../docs/plans/pi-autowork-component-layout.md#one-product-root-contract)
separates source ownership from stable entry paths. Runner, legacy-reader and engine
implementations now live in `pi-autowork/src/pi_autowork/`; the public `pi-autowork/` Python
files are import/command adapters. Standalone checkout/worktree hooks remain in
`pi-autowork/engine/`; product fixture helpers live in `pi-autowork/tests/support/`. Native implementations live in
`pi-autowork/src/autowork_runtime/`, with Python entrypoint adapters in `scripts/`. Only the
Hermes-required `__init__.py` adapter remains beside root `plugin.yaml`.
Canonical package initializers remain inert.

The mechanical source mapping is `pi-autowork/pi_autowork/<module>.py` to
`pi-autowork/src/pi_autowork/<module>.py` (including `legacy/`), and
`pi-autowork/engine/<module>.py` to `pi-autowork/src/pi_autowork/engine/<module>.py`.
The production engine exceptions are `worktree_paths.py`, `checkout_lock.py` and
`agent_commit.sh`; they stay standalone. Runner, engine and native tests live in
`pi-autowork/tests/{runner,engine,native}/`. Engine fixtures live in
`pi-autowork/tests/fixtures/engine/`, and migration fixtures in
`pi-autowork/tests/fixtures/task_migrate/`. Shared Kit checks and registration tests
stay in `tests/`; `tests/src_fixture.py` is shared copied-release support.

Dedicated tools and self-contained cron payloads live in `pi-autowork/scripts/`.
Profile provisioning copies the canonical payload bytes, not an old compatibility
entry. `pi-autowork/bin/pi-autowork.sh` is the canonical launcher; the root
`scripts/pi-autowork.sh` preserves copied-entry discovery, arguments and exit status.

## Selected-release APIs

`scripts/autowork_bootstrap.py` loads only its own `pi-autowork/src/autowork_bootstrap.py`, with one
root-keyed identity even for path-based native callers. There is no cwd, Git,
site-packages or other-release fallback. Bootstrap loading and source discovery
do not write bytecode, start processes or import product modules.

`Layout(root)` is frozen and resolves a linked selected root. Its `root`, `src`,
`runtime`, `package`, `engine` and `component` properties locate the toolset,
not the target repository. `root` remains the Kit resource/release root; `src` is
`root/pi-autowork/src`, never cwd. `resource(relative)` confines resources to that root.
`entrypoint(name)` returns public paths (native names under `scripts/`, runner names,
canonical dotted runner names, `autowork`, `agent_commit`, or explicit relative
paths). `implementation(public_relative)` follows literal native `execute`
payloads and corresponding canonical runner owners; an unmigrated entry remains
its own owner. A declared but missing native or runner payload fails.

`Layout.python_sources(root)` returns sorted bounded production Python owners,
including nested source modules and unmigrated entries. It excludes tests,
fixtures, bytecode directories and escaping symlinks. Source checks must inspect
these owners, not only public shims. The checker preserves the baseline test
identities and shard counts under their relocated process keys and validates source syntax/closure without imports.
Canonical runner sources must not use unqualified flat engine imports.

### Native namespace boundary

A migrating native public entry calls `execute(namespace, source_relative)` from
its exact tree-local bootstrap. The implementation compiles with its real source
filename but runs in the caller's existing dictionary. Caller module identity,
package/spec/path and public `__file__` remain intact, so global monkeypatches
continue to affect functions. The loader injects `_AUTOWORK_LAYOUT` and
`_AUTOWORK_COMPAT`. Resources use `_AUTOWORK_LAYOUT.root`, not the adapter's
containing directory; subprocesses launch the selected release's `scripts/` entries.

Native dependencies use `_AUTOWORK_COMPAT.peer(globals(), name)`. Peers bind to
the current plugin package or a root-keyed private package, never an unrelated
top-level cached module. Independent native releases may coexist in a process.
Missing or escaping payloads refuse; they are not repaired from another release.

### Runner package boundary

`activate(root) -> Layout` selects the canonical `pi-autowork/src/pi_autowork` package for an
explicit caller. `load(root, canonical_name)` validates selected-root origins and
returns a single imported module. Flat engine aliases and canonical engine names
share objects in either import order, without adding engine directories to
`sys.path`. A runner already bound to another release is refused. This is separate
from native multiple-release loading. The only legacy origin exceptions are the
standalone `worktree_paths.py` and `checkout_lock.py` hooks. Runner workspace
allocation and engine dispatch reuse the same selected-root hook module rather
than loading another copy under a private name.

`run(root, canonical_name, argv)` calls the module's explicit `_compat_main(argv)`
adapter; it never executes the canonical module body a second time. Public Python
adapters preserve their former terminal-block exception and exit behavior. Children,
TUI reload and main-check commands use `Layout.entrypoint`, not implementation
`__file__` paths. Source discovery, fingerprints and nested candidate syntax checks
inspect actual owners. Before re-exec, the updater also probes the candidate's
public capabilities command; an invalid or incomplete payload leaves the running
release selected. Existing release pinning and environment contracts are unchanged.

## TUI screen owners

`pi_autowork.tui` owns `FleetApp`, runner selection, the shared read coordinator,
command execution, pending-deletion overlays and planning navigation. Flat
`tui_tasks.py` owns task/decision screens and task edit forms; they call the host
through `self.app` without importing the application. `tui_common.py` owns
`ReadScreen`, shared text/widget helpers and the refresh interval. Physical read
scheduling stays in `tui_reads.py`; confirmation stays in `tui_dialogs.py`.
`tui` reexports the same screen/helper objects for existing callers. Flat screen
owners participate in the selected release's existing code-stamp scan, while open
screens and running actions continue to defer reload.

## Offline qualification and packaging

The npm allowlist includes the scripts/src bootstrap and `pi-autowork/src/pi_autowork/`, together with
existing portable entries/resources. It excludes Hermes-only
`pi-autowork/src/autowork_runtime/`. Archive help and read probes are distinct from immutable
runner launch: release pinning still requires a committed Git toolset.

`tests/src_fixture.py:copy_sources` copies complete selected Python source closure
plus explicitly requested resources into private fixtures, including both standalone
hooks. `tests/test_install_plugins.py` uses it because its shell fixture imports
native runtime policy; it is not a shell-discovery-only fixture.

Focused checks:

```sh
python3 scripts/check.py pi-autowork/tests/native/test_src_bootstrap.py tests/test_affected_tests.py tests/test_check.py tests/test_portable_package.py tests/test_install_plugins.py
node --test tests/portable_pi.test.mjs
python3 scripts/affected_tests.py --run
```

The package test uses private sources, offline `npm pack --ignore-scripts`, and
extracted files; it runs no installation or lifecycle scripts. Affected selection
resolves qualified/relative imports, package initializers and old-entry-to-source
edges. The command-line selector falls back to the full inventory for unresolved,
deleted, initializer or global inputs rather than silently losing coverage.
These offline oracles do not qualify installed profiles, live models or jobs.
