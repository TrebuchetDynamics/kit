# Pi Autowork component layout

Status: Accepted. The owner approved one canonical runner package on 2026-11-11,
retaining commands and Python imports while retiring compatibility-only library-file
execution. This is the current placement contract, not a completed-task report.

## One-product-root contract

Status: Accepted, 2026-11-07. Owner request: **refactor all Autowork code, even tests, into one folder `pi-autowork`**. Plan For Me delegates the engineering choices below. This supersedes placement only in the earlier proposal, the [source-root plan](structural-audit-2026-10.md#sdd-maintainability-refactor), and the [Rust plan](rust-octet-autowork.md). Preserve their accepted behavior, task IDs, completed evidence, dependencies and live gates.

### Scope and decided architecture

`pi-autowork/` owns all editable Autowork implementation, product tests, fixtures, dedicated tools and UI. This includes the generic engine, native/Hermes runtime and Rust successor, not just the Pi process adapter. Retain Python import names and the current native-versus-runner loading models. The folder name is an ownership boundary, not a requirement that Rust use Pi.

```text
pi-autowork/
  src/
    autowork_bootstrap.py
    autowork_runtime/                 # native plugin, policy, install and update bodies
  pi_autowork/                       # canonical runner, engine, legacy, supervision
  engine/                            # supported flat entries and standalone hooks
  bin/                               # autowork and canonical shell launcher
  scripts/                           # product tools and copied native payloads
  tests/
    runner/                          # runner tests and UI pilots
    engine/                          # engine tests and manual fake-worker harness
    native/                          # product-native tests
    support/                         # shared product fixture helpers
    fixtures/                        # engine, fleet and migration fixtures
  integrations/paseo/                 # TS source, tests, assets and existing package
  rust/autowork/                      # existing single crate, moved after its first batch
  docs/                              # source-layout, RPC and planning-console runbooks
```

No new distribution, import namespace, database, general registry or package framework. Keep the existing Paseo package/lock and Rust crate/lock. `Layout.root` continues to mean **Kit resource/release root**; `Layout.src` remains `root/pi-autowork/src` for native code and the bootstrap. `Layout.package` is `root/pi-autowork/pi_autowork`. Derive locations from the selected release, never cwd. Preserve the two distinct loader models, supported commands and flat engine imports. Canonical package initialization binds the selected release without starting work. Retire the duplicate runner adapters and `pi-autowork/src/pi_autowork`, not the native loader or standalone hooks.

This improves locality. It does not by itself deepen modules, remove task-state complexity or fix the separately reproduced generic-commit race, retirement rollback, batch-cleanup refusal or dependency-display amplification. Those correctness changes are excluded.

### Fixed mapping and compatibility boundary

All paths below are repository-relative and fix the accepted origin/destination map.
The [source-layout guide](../../pi-autowork/docs/source-layout.md) owns the current
Python layout. Paseo and Rust relocation keep their separate prerequisite gates.

| Planning-baseline owner | Destination or retained boundary |
| --- | --- |
| Runner implementation, including former `pi-autowork/src/pi_autowork/**` | One canonical package at `pi-autowork/pi_autowork/**`; no forwarding runner copies. |
| `src/autowork_runtime/**`, `src/autowork_bootstrap.py` | Same suffix under `pi-autowork/src/`; include every native install/update subtree. |
| Production `pi-autowork/engine/*` | Keep flat import/command adapters; actual `checkout_lock.py`, `worktree_paths.py` and `agent_commit.sh` stay standalone in engine. |
| `scripts/pi-autowork.sh` | Canonical body `pi-autowork/bin/pi-autowork.sh`; old path forwards. Preserve copied-launcher discovery, arguments, exit codes and selected release. |
| `scripts/install-pi-rpc.py`, `bench_parallel.py`, `migrate-autowork.py`, `wire-owner-cron.py`, `heal-owner-cron.py`, `profile-consult.py` | Same basename under `pi-autowork/scripts/`; old documented or installed paths are thin forwarding entries, not copied business logic. |
| `scripts/profile-audit-cron.py`, `skills/cron-autowork/scripts/autowork-start-notice.py` | Canonical payloads under `pi-autowork/scripts/`. Provision the real self-contained payload bytes. Keep old source paths only as compatibility dispatch, never copy a checkout-dependent shim into a profile. |
| `scripts/preflight_config.py` | `pi-autowork/src/autowork_runtime/install/preflight_config.py`; preserve standalone subprocess entry through its old adapter. |
| `src/README.md`, `docs/pi-rpc.md`, `docs/planning-console.md` | `pi-autowork/docs/source-layout.md`, `pi-rpc.md`, `planning-console.md`; update current navigation and local links. |
| `integrations/paseo/**` | `pi-autowork/integrations/paseo/**`, including all tests, manifests, existing lockfile, docs, assets and licenses; exclude generated/cache/dependency files. |
| `rust/autowork/**` | `pi-autowork/rust/autowork/**`, including Cargo manifests/lock, tests, fixtures and documentation; exclude target/cache/state. |

**Explicit outside exceptions:** root `__init__.py`, `plugin.yaml`, native root `scripts/` entrypoints and `scripts/autowork_bootstrap.py` are compatibility/registration boundaries. Root `paseo-plugin.json`, `index.server.ts` and `index.client.tsx` remain because Git-root Paseo installation checks entries before build and rejects simple external re-exports. Keep the two entry files byte-identical to their component owners and verify equality; they are the narrow required executable-copy exception, not independently editable implementations. Preserve existing API generation and operator policy.

**Genuinely shared Kit owners remain outside:** root installers and installer menu, package/host manifests, `adapters/pi.mjs`, skills and their portable adapters, shared check/typecheck/affected-test tools, test dependency configuration, plugin catalog/default resources, skill evaluation tooling and shared docs/assets. Native code below the component may serve all of Kit; that does not move the resource root or erase shared registration tests. Project `tasks/`, goals, planning/research history, `BLOCKERS.md` and changelog remain project intent/evidence. Runtime state, credentials, worktrees, leases and installed services do not move. Product-specific executable skill payloads move as mapped above; portable workflow instructions do not.

Keep native-only payloads excluded from the portable Pi npm archive, as today. Physical ownership does not widen distribution contents. Test the Pi archive and native copied-release closure separately. Remove stale archive entries only after proving they have no payload/consumer; do not broaden to shipping every component file, test, native installer or Rust build artifact.

### Complete product-test mapping

Move every current `pi-autowork/tests/*.py` to `pi-autowork/tests/runner/`, including pilot/support files. Move every `pi-autowork/engine/test_*.py` to `pi-autowork/tests/engine/`. The duplicate runner/engine/shared test stems remain separate process identities, not flattened names.

Move these root `tests/` files to `pi-autowork/tests/runner/` with their basenames unchanged:

- `test_async_maintenance.py`, `test_autowork_command.py`, `test_autowork_push_setting.py`, `test_autowork_resilience.py`, `test_cli_startup.py`.
- `test_conversion_audit.py`, `test_hermes_observers.py`, `test_pi_autowork.py`, `test_pi_rpc_engine.py`, `test_planning_authority.py`, `test_ponytail_runner.py`, `test_repository_identity.py`.
- `test_task_commands.py`, `test_task_handoff.py`, `test_task_migrate.py`, `test_task_prepare.py`, `test_task_presentation.py`, `test_task_store_qualification.py`, `test_src_entrypoints.py`.

Move these root `tests/` files to `pi-autowork/tests/native/`: `test_audit_launcher.py`, `test_autowork_migration.py`, `test_cron_autoheal.py`, `test_owner_cron.py`, `test_profile_consult.py`, `test_start_notice.py`, `test_src_native.py`, `test_src_bootstrap.py`.

Move `tests/live_qualification.py` to `pi-autowork/tests/engine/live_qualification.py`. Its documented worker is fake; retain its manual/non-discovered policy and do not call it live model qualification. Move `pi-autowork/engine/{store_fixture,offline_fixtures}.py` to `pi-autowork/tests/support/`; move engine fixtures to `pi-autowork/tests/fixtures/engine/` and root `tests/fixtures/task_migrate/` to `pi-autowork/tests/fixtures/task_migrate/`. Existing fleet fixtures remain under `pi-autowork/tests/fixtures/`.

Other root tests retain shared Kit responsibilities: installation/provisioning, registration, package boundaries, shared planning/skill contracts, check tooling, Git skills, docs, terminal and evaluation. In particular, `test_plugin.py`, `test_bundle.py`, `test_setup_runtime.py`, `test_portable_package.py`, `test_paseo_plugin_root.py`, `test_planning_cli_contract.py`, `test_planning_specimens.py`, `test_task_touches_contract.py`, `test_check.py` and `test_affected_tests.py` are not product-only just because they import product code. Keep the three native integration exclusions, shared Node portable tests, planning/APK/fake-tmux fixtures and the two skill-script suites. Split any newly found product-only cases out of a genuinely mixed test without losing its shared assertion.

Keep `tests/src_fixture.py` as shared test support and retarget its selected-release closure. Extract the shared host `Context` fixture from root `test_plugin.py` into a non-test shared helper; native tests must not import a shared TestCase module as API. Co-locate the runner baseline, RPC and task-store qualification tests; preserve fixture teardown and avoid duplicate TestCase discovery when extracting helpers. Checker subprocesses and direct test scripts must resolve product support explicitly, not through cwd, host PYTHONPATH or pytest-only hooks.

At implementation baseline, enumerate tracked files and discovered test methods before movement. Reconcile additions since `77be5faa` by the same responsibility rule. Produce a one-to-one old/new inventory, documenting only actual extracted/new tests. No test deletion, skip, blanket exclusion or passing empty suite may stand in for migration.

### Migration tasks and observable acceptance

The full batch has four implementation tasks under existing `CODE-HEALTH-2026-10`; preserve its focus and priority.

| Task | Outcome | Prerequisites |
| --- | --- | --- |
| `TOOLSET-479-7f124d5c` (A) | Python source, tools and product test closure | None |
| `TOOLSET-480-9166695b` (B) | Complete Paseo package ownership | A |
| `TOOLSET-481-33040cb9` (C) | Completed Rust crate ownership | Existing six Rust builders |
| `TOOLSET-482-18ae1de9` (D) | Final ownership and offline release proof | A, B, C |

**A — Python source, tools and test closure.** One atomic relocation updates both loaders, native adapters, dedicated scripts, all mapped Python tests/helpers/fixtures, checker discovery/shards, affected-test edges, strict typecheck paths, archive allowlists, shared fixture consumers and current path documentation. This cut exceeds a small-file heuristic because a half-moved loader or fixture cannot represent a coherent selected release. Do not combine it with feature redesign.

Start by adding failing ownership/closure oracles to `test_src_bootstrap`, `test_src_entrypoints`, `test_src_native`, `test_check`, `test_affected_tests` and `test_portable_package`, then move their product-owned files. Prove canonical/flat engine identity in both import orders; native caller globals/monkeypatch identity across two releases; late and child imports pinned to one release; refusal on missing/foreign source; standalone copied hooks; copied cron payloads; unchanged root resources and consumer repo selection. Preserve raw tracked-blob fingerprints and modes. Extract an offline npm archive into a disposable path with spaces and use unrelated cwd/poisoned import paths; exercise real help/read and fake-worker inference behavior, not just an allowlist. Native closure tests must not fall back to the host checkout. Retain immutable-release admission requirements distinct from archive read commands.

Update `TEST_DIRS`, direct-child discovery, baseline and parallel-integrate split keys, source guard and module normalization together. Test every renamed/deleted owner edge and duplicate stem; unresolved edges retain conservative full selection. Compare old/new discovery and shard partitions, including unchanged exclusions. New checker cases must actually exercise the new split paths. Retarget Paseo's two Python-source consumers and `integrations/paseo/tests/planning.test.ts` in place; task B consumes those corrected mappings. Its fixture directories, fixture bootstrap and bytecode-absence assertion must all use `pi-autowork/src` in this same cut. A must run `npm --prefix integrations/paseo run check` in the existing locked offline environment (or reuse the matching full-check result); the shared checker's missing-dependency skip is not proof of this boundary.

**B — Paseo product ownership.** Depends on A's final source and test layout. Move its complete independent package without changing API 4, executable discovery, action policy, task draft behavior, FIFO admission or feature semantics. Update root manifest copy/build inputs, archive files, checker paths, navigation and root entry equality checks atomically. Prove `test_paseo_plugin_root`, existing plugin-load tests and the package's typecheck/test commands still cover Git-root and standalone packaging. No plugin install, daemon restart or real action delivery is part of this task.

**C — Rust product ownership.** Wait for the six existing first-batch Rust building tasks, `TOOLSET-472-48c78e95`, `TOOLSET-473-afef55de`, `TOOLSET-474-6b517117`, `TOOLSET-475-66aacc5f`, `TOOLSET-476-fb27960d`, `TOOLSET-477-e5de6356`. They keep their frozen `rust/autowork/` contracts; the foundation was in flight during planning. Relocate their completed crate as a mechanical cut, preserve lock bytes/dependency pin and all native/offline proofs, and adjust owned paths/checker routing. No dependency upgrades, Octet changes, runtime cutover or live execution. The existing seventh task `TOOLSET-478-9a8d7ece` keeps its ID, outcome and six dependencies and also waits for C, so its next plan uses the new owner rather than racing relocation. Preserve its live-denied gate and round history. C can proceed independently of A/B once its real Rust inputs exist.

Prove Cargo metadata resolves only the new manifest, the same named binary and test inventory remain, no source exists under the retired crate path, and locked offline check/test pass from the new path and unrelated cwd. Reuse the first batch's exact bounded fake-runtime test/check registry; do not turn migration into model qualification. Missing already-locked dependencies are a setup input, not permission to update the lock or silently skip checks.

**D — Final ownership and release proof.** Depends on A, B and C. Extend the existing ownership/package tests rather than add a parallel registry: no product implementation/test remains in the old roots; retained outer files match the exact shared/host exception policy; all three language surfaces ship through their existing boundaries; production adapters do not import test helpers. Audit current commands/docs and test inventories, update component navigation and source-layout documentation, and prove source-only archives/fixtures cannot borrow the checkout. Historical citations stay historical. Record local source/check evidence separately from installation and live acceptance. Do not delete old worktrees or installed releases to satisfy an ownership assertion.

Proposed commands (UNRUN; exact task records assign subsets):

- `python3 scripts/affected_tests.py --run --base <task-base>` after inspecting the selection and command side effects; retain selected module/shard logs and immutable input hashes. A root checker change may legitimately select the full offline inventory; do not run a second broad suite for the same tree.
- Focused Python closure: `python3 scripts/check.py pi-autowork/tests/native/test_src_bootstrap.py pi-autowork/tests/native/test_src_native.py pi-autowork/tests/runner/test_src_entrypoints.py tests/test_check.py tests/test_affected_tests.py tests/test_portable_package.py`.
- `node --test tests/portable_pi.test.mjs`; archive probes run `npm pack --ignore-scripts --offline` only in disposable fixtures and do not install or invoke package hooks.
- `npm --prefix pi-autowork/integrations/paseo run check`; package smoke via the existing plugin-load suite and offline fixture pack. Use the existing locked dev environment, or an explicitly authorized offline `npm ci --ignore-scripts --offline` in an isolated checkout; missing cache is a reported setup blocker, not authority to install globally or fetch silently.
- `cargo metadata --locked --offline --no-deps --format-version 1 --manifest-path pi-autowork/rust/autowork/Cargo.toml`; `cargo check --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml`; `cargo test --locked --offline --manifest-path pi-autowork/rust/autowork/Cargo.toml`. Inspect the landed fixture suite first; no provider/model/live test is implied.

The repository checker can provision its own Python environment. Implementers inspect it and use the supported prepared environment under their execution authority; planning does not run it or install anything to make this document pass. Normal source integration/main gates and independent review still apply. Expected implementation cost: four task integrations and four independent task reviews if the continuous runner executes one task per candidate, plus its normal main gate; another supported execution method may combine compatible candidates but must keep all four acceptance reports. This is separate from one planning commit.

### Queue and safety

Tasks remain open in Now/Next without a planning-only hold. A has no logical task prerequisite; B waits for A, C waits for the Rust builders, and D waits for A/B/C. Selection priority, path/resource admission, ownership and capacity are separate. Recheck current source and active writers before execution. Preserve all live gates, stopped jobs and recovery worktrees; a placement change starts no service and grants no publication authority.

Completed-task reports and their historical replay tools are removed under the repository's retention policy, not relocated into a new archive. Current product tests and generic archive-import fixtures remain in scope. Required qualification inputs for unfinished work remain available through pinned Git revisions; cleanup is not proof of completion.
