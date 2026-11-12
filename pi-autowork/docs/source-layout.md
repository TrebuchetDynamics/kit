# Source layout and compatibility

The [component placement contract](../../docs/plans/pi-autowork-component-layout.md#one-product-root-contract)
keeps all product implementation under `pi-autowork/`. The runner has one canonical
Python package at `pi-autowork/pi_autowork/`, including `engine/`, `legacy/` and
`supervision/`. There is no second runner package under `src/`.

`pi-autowork/engine/` retains flat engine import and command adapters. Its
`checkout_lock.py`, `worktree_paths.py` and `agent_commit.sh` remain standalone.
They are not duplicate runner implementations. Product tests and fixtures stay in
`pi-autowork/tests/{runner,engine,native,support,fixtures}/`; shared Kit checks stay
in root `tests/`.

Native implementations retain their distinct loading model and ownership under
`pi-autowork/src/autowork_runtime/`. Their public entries remain in root `scripts/`
and the Hermes-required root `__init__.py`. The shared bootstrap implementation
remains at `pi-autowork/src/autowork_bootstrap.py`.

Dedicated tools and copied cron payloads remain in `pi-autowork/scripts/`.
Provisioning copies the canonical payload bytes, not a checkout-dependent adapter.
`pi-autowork/bin/pi-autowork.sh` is the canonical launcher. Root
`scripts/pi-autowork.sh` preserves copied-entry discovery, arguments and exit status.

## Selected-release APIs

`scripts/autowork_bootstrap.py` loads only its selected tree's bootstrap, with one
root-keyed identity. There is no cwd, site-packages or other-release fallback.
Source discovery does not import product modules or start processes.

`Layout(root)` is frozen. `root` is the Kit resource/release root, not the consumer
repository. `component` is `root/pi-autowork`; `package` is
`component/pi_autowork`; `engine` is `package/engine`. `src` remains
`component/src` for the native payloads and shared bootstrap. `runtime` is
`src/autowork_runtime`.

`resource(relative)` confines paths to the selected root. `entrypoint(name)` resolves
supported command paths. `implementation(public_relative)` resolves native and flat
engine adapters to their owners. Canonical runner and native implementation files
own themselves; discovering them does not parse their bodies to rediscover ownership.
Declared but missing adapter payloads still fail closed.

`Layout.python_sources(root)` returns sorted, bounded production Python owners from
the native sources, canonical runner package, public entries and standalone hooks.
It excludes tests, fixtures, bytecode and escaping symlinks. Syntax checks compile
the actual owners separately. Source fingerprints and review checks retain actual
source bytes and modes.

## Native namespace boundary

Native public entries call `execute(namespace, source_relative)` from their own
bootstrap. The implementation compiles with its real filename into the caller's
existing dictionary. Public `__file__`, module identity and global monkeypatch
behavior remain intact. `_AUTOWORK_LAYOUT` and `_AUTOWORK_COMPAT` bind resources
and peers to that release.

`peer(namespace, name)` resolves the caller's plugin package or a root-keyed private
package. Independent native releases may coexist in one process. Missing or escaping
payloads refuse instead of borrowing the host checkout. This behavior is unchanged
by runner consolidation.

## Runner package boundary

`activate(root)` validates and binds one canonical `pi_autowork` package. Its
initializer performs the same release binding for ordinary package imports. It
starts no runner, task or provider operation. `load(root, canonical_name)` validates
the selected origin and returns one module object.

Flat engine names and `pi_autowork.engine.*` names share objects in both import
orders, including classes, exceptions and mutable globals. The engine directory is
not added to `sys.path` by activation. A runner bound to another release refuses;
supported release changes re-exec before importing the new tree. Standalone hooks
retain their explicit origin exceptions.

Supported command modules retain direct-file execution. Their small early entry
blocks dispatch through the selected bootstrap before importing the canonical body.
`run(root, canonical_name, argv)` calls the explicit `_compat_main` function; it does
not execute a canonical body twice. Arguments, exit behavior and module identity
remain covered by the existing entrypoint tests. Library-only file execution is
retired; import those modules instead. No library compatibility copies remain.

Children, TUI reloads and main-check commands use `Layout.entrypoint`. Candidate
updates validate source syntax and the public capabilities command before changing
the selected release. State schemas, release locks, pruning and inherited release
selection remain unchanged.

## TUI screen owners

`tui.py` owns the application and runner selection. `tui_tasks.py` owns task and
decision screens, which use the application without importing it. `tui_common.py`
owns shared screen helpers. `tui_reads.py` owns physical read scheduling and
`tui_dialogs.py` owns confirmation. Existing reexports and code-stamp behavior remain.

## Offline qualification and packaging

The npm allowlist includes the canonical runner package and both bootstrap files.
It continues to exclude native-only `src/autowork_runtime/`. Archive help/read
commands are distinct from immutable runner launch, which requires committed Git
inputs.

`tests/src_fixture.py:copy_sources` copies complete Python closure plus explicitly
requested resources. Copied fixtures never borrow missing owners from the checkout.
The same test modules, method identities, shard partitions and native exclusions
survive consolidation. Affected selection follows canonical imports, flat engine
adapters and package initializers. Unresolved or deleted inputs retain conservative
full selection.

```sh
python3 scripts/check.py pi-autowork/tests/native/test_src_bootstrap.py pi-autowork/tests/native/test_src_native.py pi-autowork/tests/runner/test_src_entrypoints.py tests/test_check.py tests/test_affected_tests.py tests/test_portable_package.py
node --test tests/portable_pi.test.mjs
```

These offline checks use disposable sources, unrelated working directories, poisoned
import paths and extracted archives. They do not install a runner or qualify live
models, profiles or jobs.

## Paseo and Rust component owners

`pi-autowork/integrations/paseo/` retains the complete Paseo package. Its Python
bridge resolves the canonical runner owners. Root Paseo entries remain byte-identical
to their component owners. Package generation and operator policy are unchanged.

`pi-autowork/rust/autowork/` retains the separate crate, tests and dependency lock.
Runner consolidation does not activate Rust or move runtime state, credentials,
installed releases, task records or recovery worktrees.
