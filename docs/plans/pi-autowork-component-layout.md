# Pi Autowork component layout

Status: Accepted placement amendment, 2026-11-07. The [one-product-root contract](#one-product-root-contract) below owns current scope and destinations. The earlier proposal is retained as history; its generic-engine exclusion and old task-store paths are superseded. This planning occurrence does not implement, publish, install or start anything.

## User direction and scope

The user wants continued study of open-source orchestrators, comparison against our existing pipeline, and a coherent place for tooling belonging to the Pi Autowork runner. Pi performs heavy automated coding; the component remains part of Autowork. `TODO.md` and `goals.json` remain the project work queue and its synchronized index.

The requested name is interpreted as **Pi Autowork**. My reversible naming choice is `pi-autowork/` for the source component and `pi_autowork` for its Python import package.

This is a layout/refinement proposal for the existing [TOOLSET-115-bf coordinator redesign](https://github.com/TrebuchetDynamics/autowork/blob/0e6f67b1a7d49e59868885d3312bbe9bc91361ee/docs/plans/2026-10-16-pi-autowork-coordinator.md), not another redesign or a replacement task. The accepted design currently names `scripts/pi_autowork/`; changing that destination is proposed here and must not rewrite an active worker's assigned contract. The [reference study](../research/pi-autowork-reference-architectures.md) provides the reuse evidence.

## Recommendation

**Create one Pi-specific component inside the existing repository and package. Keep the generic Autowork engine shared. Keep runtime state out of source control.**

Do not put every related file into one undifferentiated directory. Ownership matters more than physical proximity: runner source, project intent, generic engine, installed dependencies and mutable runtime state have different lifecycles.

### Proposed source tree

```text
autowork/
├── pi-autowork/                    # Pi runner component; ships with Toolset
│   ├── README.md                   # component entry points and ownership map
│   ├── cli.py                      # tiny Python launcher; no task state
│   ├── pi_autowork/
│   │   ├── __init__.py
│   │   ├── cli.py                  # option parsing, status and exit-code contract
│   │   ├── coordinator.py          # reconcile/call engine; no second task FSM
│   │   ├── engine_client.py        # versioned calls to the shared engine
│   │   ├── pi_runtime.py           # launch/observe/stop/resume Pi; model fallback
│   │   ├── verification.py         # project checks and reviewer launch adapter
│   │   ├── touches_inference.py    # existing Pi-specific scope inference behavior
│   │   ├── workspaces.py           # Pi-session provisioning through engine APIs
│   │   ├── project_config.py       # existing CLI/environment normalization
│   │   ├── health.py               # read-only status projections and stall signal
│   │   └── service.py              # systemd rendering; changes only when requested
│   ├── tests/                     # component tests and controlled subprocess fixtures
│   └── docs/                      # component runbook and interface reference
├── scripts/pi-autowork.sh          # compatibility/discovery shim, not another loop
├── skills/autowork/scripts/        # shared scheduler, leases, slots, Git integration
├── skills/docs-sync/scripts/      # shared TODO/goals parsing and maintenance
├── adapters/pi.mjs                 # Pi command registration
├── package.json                    # one Toolset distribution includes pi-autowork/
└── docs/                           # product-level cross-host/planning/research docs
```

These are planned paths, not files created by this research. A new standalone package, second lockfile, framework, database or installer is not needed for the initial consolidation. If a Node runtime adapter is later justified, put its owned bridge in this component and declare it explicitly rather than silently discovering arbitrary extensions.

## Boundaries and ownership

| Kind | Owner/location | Must not become |
| --- | --- | --- |
| Accepted project intent | Consumer `TODO.md`, existing docs and `goals.json` | A per-worker replacement task board |
| Generic task lifecycle | Shared Autowork engine | A second Bash/Pi-component FSM |
| Pi execution mechanics | `pi-autowork/pi_autowork/` | Product/task acceptance authority |
| Agent skills/commands | Existing `skills/` and `adapters/` | Copies embedded in each consumer project |
| Shared execution lease/slots/journal | Existing Git-common-dir state | Tracked component files or reset migration output |
| Runner sessions/costs/logs/worktrees | Existing per-repository private state | Source files, vendored data or fresh budget on restart |
| Service environment | Existing user config for pi-autowork | Repository credentials or implicit fleet configuration |
| Pi credentials/models | Pi's existing host configuration | Copied credentials in this component |
| Upstream source-research snapshots | Private research storage | A vendor folder of entire third-party repositories |

Current defaults observed in the runner:

- State root: `${XDG_STATE_HOME:-~/.local/state}/pi-autowork`, or `PI_AUTOWORK_STATE_DIR`, with existing project-specific resolution preserved.
- Shared engine state: `<git-common-dir>/autowork-execution/`.
- User service config: `${XDG_CONFIG_HOME:-~/.config}/pi-autowork/<instance>.env`, or the current `PI_AUTOWORK_ENV_DIR` override.
- User unit: `pi-autowork@<instance>.service`, with existing instance-ownership checks.

A source reorganization must not relocate, empty or renumber any of those stores, change service identities, reset attempts/cost windows, or restart running workers. Two repositories with the same basename must not silently share an instance; preserve the existing refusal until a separately specified identity migration is qualified.

![Proposed source, project and runtime file ownership](../research/pi-autowork-diagrams/component-files.svg)

## Alternatives considered

1. **Leave everything under `scripts/`.** Least immediate path churn, but retains a large mixed shell implementation and no coherent component owner. Keep the legacy entry point, not the scattered implementation.
2. **Use the accepted `scripts/pi_autowork/` destination.** Technically sound and the lowest-risk option if that work has already landed. The top-level component provides a clearer home for source, tests and runbook. Do not stop active correctness work just to rename it; if it lands first, make the later move mechanical and compatibility-tested.
3. **Make a separate repository/npm package now.** Reject for this stage: it adds release/version/discovery ownership without removing the need for the shared Toolset engine.
4. **Adopt a complete external orchestrator.** Reject as the default: inspected projects often introduce another task store, role hierarchy, runtime requirements, publication path or cleanup policy.
5. **Move all generic Autowork code into Pi Autowork.** Reject: Pi is the worker host, not the owner of the cross-host task model.

## Migration plan — proposals, not executed work

### 1. Fix authority before moving files

Build on TOOLSET-115-bf's accepted lifecycle work and landed report-outcome changes. Record one authoritative state schema in the engine. Runtime events, model fallback and status UIs report observations; they cannot independently mark a task done.

Keep execution success, candidate verification, integration into a session, canonical delivery, metadata closure and cleanup distinguishable. Do not change the task lifecycle solely to make the directory tree tidier.

### 2. Extract one component with compatibility entry points

Move Pi-specific mechanics into the component, leaving generic admission, slots, claims, scope checks, integration and closure in the shared engine. `coordinator.py` calls engine operations and reconciles their observed results; it does not persist its own task-state enum/counters that compete with the engine.

Keep `scripts/pi-autowork.sh` as a small compatibility shim. Preserve all existing flags, exit codes, environment overrides, copied-launcher use and package discovery:

1. Honor an explicitly selected valid `PI_AUTOWORK_TOOLSET`.
2. Preserve the existing ability to locate the Toolset package Pi actually loads.
3. Preserve an adjacent source-checkout fallback when applicable.
4. Resolve component source, shared engine and skills from **one versioned Toolset root**; never mix two installed releases.
5. Carry the consumer repository separately from the Toolset source root; launching from an arbitrary working directory must not select the Toolset repository accidentally.

Do not invent a new Pi `list --json` contract: the current discovery reads supported `pi list` output. If discovery is later replaced, verify that CLI/API contract explicitly.

Existing services keep their current launcher and environment; the shim remains supported rather than imposing a forced migration deadline. Signals should reach a task-scoped persistent coordinator identity, not a transient launcher or shared gateway. Reusing a session or budget is not reusing an OS PID.

Safe updates need more than same-root discovery. For the controlled updater, fence the release used by the component and engine together; do not let a long-lived old coordinator call newly replaced engine files unnoticed. Defer an update while affected live, reported or integrating slots exist, including other runners sharing that installed release. Check state-schema compatibility before changing code, and keep the prior release usable on refusal/failure. At a compatible idle checkpoint, switch/re-exec component and engine as one release without resetting state or consuming attempts. An old monolithic copied launcher does not become a new shim merely because the package changed: preserve its supported engine contract or require an explicit safe-checkpoint launcher migration, with an actionable compatibility refusal rather than partial execution. External manual package replacement is not made atomic by this plan; detect mismatches before further admission.

### 3. Ship the whole component, not only the wrapper

The current root `package.json.files` includes `scripts/pi-autowork.sh` but no `pi-autowork/` directory. Add the component explicitly during implementation. A repository checkout passing tests is insufficient when the installed Pi archive omits its Python modules.

Explicitly move the behavior of `scripts/pi_autowork_touches.py` into `pi_autowork/touches_inference.py` and update all owned callers; retaining its old path is optional compatibility work, not a second implementation. The current archive omits this helper, and the inspected runner silently skips inference when it is absent. Test functional inference from the archive, not merely help/status: two independent tasks start without authored Touches, deterministic fake Pi proposes bounded paths, the helper/engine validates the proposals, and both become parallel-eligible. Also test inference disabled and missing/invalid inference: retain the conservative solo policy and make the diagnostic explicit rather than silently claiming full parallel behavior.

Keep one Toolset release. Run the component launcher directly from an extracted npm archive without checkout files, with paths containing spaces and a different cwd. Keep `adapters/pi.mjs` resource registration unchanged unless an explicit integration change requires it.

Add component tests to `scripts/check.py`'s maintained offline inventory. Merely placing tests under a new folder will not make the current four-directory inventory discover them. Keep a root legacy-launcher regression until all compatibility entry points are intentionally retired.

### 4. Qualify adoption and restart behavior

Reuse the existing fake-Pi/real-Git fixture pattern. Compare legacy and component entry points for arguments, environment, stdout/status schema, exit codes, default source/consumer selection and no-write dry-run behavior.

Exercise interrupted launch, live-worker adoption, cancellation escalation, stale report rejection, task reorder while workers run, exactly-once closure recovery and state-schema compatibility. In particular, separate live-process reuse from transcript persistence and same-process extension reload from crash recovery; test generation-fenced settlement and a cancellation arriving before spawn completes. Apply capacity globally to async calls and retained idle workers, use bounded RPC deadlines, and test process-group TERM-to-KILL escalation. Qualify the selected Pi version's `agent_end`/`agent_settled` events rather than treating either as task acceptance. Do not stop a production service or launch a model just to test a file move.

Add controlled old/new-release fixtures for installed and copied entry points: each busy-slot stage defers update; incompatible schema preserves the old usable release and explains refusal; compatible idle update switches component/engine together while retaining attempts, leases, budgets and receipts. Cover the unchanged old monolithic copy separately from a copied new shim, so re-executing an old file cannot masquerade as successful migration. These are proposed offline fixtures, not executed upgrade evidence.

A live disposable-project run and any service migration require their own explicit scope. Linux-only supervision does not become portable merely because code moved from Bash to Python.

### 5. Evaluate one upstream execution seam

Only after the current runtime boundary is stable, compare the existing Pi CLI adapter against a pinned execution-only candidate. AgwaB is a candidate, not a dependency decision. Its current automatic worktree finalization must remain outside our workflow; Toolset owns workspace retention and canonical integration.

First reuse upstream invariants and negative fixtures that expose a real gap. Copy only reviewed, licensed portions or use a narrow dependency interface. If no measured benefit justifies another runtime, keep the current CLI.

## Observable acceptance

The proposed migration is ready only when:

- Every Pi-specific source file has one component owner and every generic engine responsibility remains shared.
- Existing commands, copied launchers and service entry points continue to resolve one compatible Toolset release.
- The extracted distribution contains and runs the Python component, engine and required resources without checkout-only files.
- Archive-based inference with two independent missing-Touches tasks is observed; disabled/invalid inference remains conservatively solo with an explicit diagnostic.
- Installed and copied-launcher update fixtures prove busy/schema refusal and coherent idle release switching without losing state; a mixed-generation component/engine cannot admit work silently.
- `TODO.md`, `goals.json`, worker attempts, leases, session/candidate receipts, budgets and existing service configuration preserve their meanings and identities.
- No migration path resets/cleans the canonical or session checkout, deletes retained candidate evidence, resumes a paused job or restarts a live worker.
- Canonical delivery and eligible worktree removal are separately verified; active, dirty, unmerged, locked and recovery-bearing worktrees remain.
- New tests are in the canonical offline inventory and cover both old and new entry points.

Planned verification during implementation: `python3 scripts/check.py`, existing `tests/test_pi_autowork.py`, new component tests, `node --test tests/portable_pi.test.mjs`, extracted-archive execution tests, documented dry-run/status checks and shell syntax/lint for any remaining wrapper. These new migration tests were **not run** because the component has not been implemented.

## Risks and non-goals

- A “read-only linked dependency” is not made OS-read-only by a symlink. Retain the accepted setup policy, but specify actual enforcement or explicitly label the boundary cooperative; no implicit mount/sudo/permission change is authorized.
- The existing shell-string validation environment variable is trusted executable configuration. Preserve its behavior; a future argv-based configuration must not silently reinterpret it with `shlex.split` or shell expansion.
- Do not introduce automatic installers, global model/approval changes, external telemetry, another task board, a vendor dump, remote publication or fleet deployment.
- This plan does not suspend independent accepted fixes or force active workers to reread a changed contract mid-run.

## Handoff

Attach this research/layout refinement to **TOOLSET-115-bf**. Preserve that task's accepted phases and current owner, and do not reopen the completed PARALLEL goal. The local checkout was behind the upstream task/plan during this study; a targeted metadata proposal accompanies the research rather than overwriting a stale canonical backlog.

Implementation remains a separate next step. This document makes the proposed boundary and migration checks concrete; it does not claim the folder exists, an upstream runtime was adopted, or a service was migrated.

## One-product-root contract

Status: Accepted, 2026-11-07. Owner request: **refactor all Autowork code, even tests, into one folder `pi-autowork`**. Plan For Me delegates the engineering choices below. This supersedes placement only in the earlier proposal, the [source-root plan](structural-audit-2026-10.md#sdd-maintainability-refactor), and the [Rust plan](rust-octet-autowork.md). Preserve their accepted behavior, task IDs, completed evidence, dependencies and live gates.

### Scope and decided architecture

`pi-autowork/` owns all editable Autowork implementation, product tests, fixtures, dedicated tools and UI. This includes the generic engine, native/Hermes runtime and Rust successor, not just the Pi process adapter. Retain Python import names and the current native-versus-runner loading models. The folder name is an ownership boundary, not a requirement that Rust use Pi.

```text
pi-autowork/
  src/
    autowork_bootstrap.py
    autowork_runtime/                 # native plugin, policy, install and update bodies
    pi_autowork/                      # runner, engine, legacy, supervision
  pi_autowork/                       # supported public Python compatibility entries
  engine/                            # supported flat entries and standalone hooks
  bin/                               # autowork and canonical shell launcher
  scripts/                           # product tools and copied native payloads
  tests/
    runner/                          # runner tests and UI pilots
    engine/                          # engine tests and manual fake-worker harness
    native/                          # product-native tests
    support/                         # shared product fixture helpers
    fixtures/                        # engine, fleet and migration fixtures
    evidence/                        # historical owner-cycle evidence tooling
  integrations/paseo/                 # TS source, tests, assets and existing package
  rust/autowork/                      # existing single crate, moved after its first batch
  docs/                              # source-layout, RPC and planning-console runbooks
```

No new distribution, import namespace, database, general registry or package framework. Keep the existing Paseo package/lock and Rust crate/lock. `Layout.root` continues to mean **Kit resource/release root**; `Layout.src` becomes `root/pi-autowork/src`. Derive locations from the selected release, never cwd. Keeping public adapters inside the component avoids replacing the two distinct loader models in a placement change. Delete the old root `src/` implementations; do not leave a second editable tree or a forwarding package there.

This improves locality. It does not by itself deepen modules, remove task-state complexity or fix the separately reproduced generic-commit race, retirement rollback, batch-cleanup refusal or dependency-display amplification. Those correctness changes are excluded.

### Fixed mapping and compatibility boundary

All paths below are repository-relative. Destination directories are proposed, not present-tense delivery claims.

| Current owner | Destination or retained boundary |
| --- | --- |
| `src/pi_autowork/**`, `src/autowork_runtime/**`, `src/autowork_bootstrap.py` | Same suffix under `pi-autowork/src/`; include every native install/update subtree. |
| `pi-autowork/pi_autowork/**`, production `pi-autowork/engine/*` | Stay as public adapters; actual `checkout_lock.py`, `worktree_paths.py` and `agent_commit.sh` stay standalone in engine. |
| `scripts/pi-autowork.sh` | Canonical body `pi-autowork/bin/pi-autowork.sh`; old path forwards. Preserve copied-launcher discovery, arguments, exit codes and selected release. |
| `scripts/install-pi-rpc.py`, `bench_parallel.py`, `migrate-autowork.py`, `wire-owner-cron.py`, `heal-owner-cron.py`, `profile-consult.py` | Same basename under `pi-autowork/scripts/`; old documented or installed paths are thin forwarding entries, not copied business logic. |
| `scripts/profile-audit-cron.py`, `skills/cron-autowork/scripts/autowork-start-notice.py` | Canonical payloads under `pi-autowork/scripts/`. Provision the real self-contained payload bytes. Keep old source paths only as compatibility dispatch, never copy a checkout-dependent shim into a profile. |
| `scripts/preflight_config.py` | `pi-autowork/src/autowork_runtime/install/preflight_config.py`; preserve standalone subprocess entry through its old adapter. |
| `src/README.md`, `docs/pi-rpc.md`, `docs/planning-console.md` | `pi-autowork/docs/source-layout.md`, `pi-rpc.md`, `planning-console.md`; update current navigation and local links. |
| `integrations/paseo/**` | `pi-autowork/integrations/paseo/**`, including all tests, manifests, existing lockfile, docs, assets and licenses; exclude generated/cache/dependency files. |
| `rust/autowork/**` | `pi-autowork/rust/autowork/**`, including Cargo manifests/lock, tests, fixtures and documentation; exclude target/cache/state. |
| `docs/plans/owner-cycle-reachability.py`, `owner-cycle-timing-readback.py` | `pi-autowork/tests/evidence/`, preserving immutable historical revisions and proof meaning; update invocation links and root discovery, not recorded past results. These remain manual historical readback tools, not current qualification checks. |

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

### Planning evidence, queue and safety

Inspected canonical source at `77be5faa`, including `src/autowork_bootstrap.py`, `src/pi_autowork/layout.py`, native bundle/defaults, all root test path/import references, checker/shard/selector code, copied payload consumers, current Paseo package/host contracts and accepted Rust tasks. Fresh read-only inventory confirmed the native runtime is also shared Kit implementation; moving its owner does not remove its consumers. Earlier architecture probes establish separate correctness work, not acceptance of this migration.

Docs Sync capability and read-only `tasks prepare --check` on this consumer reported `READY`, no refusals, with an active runner/coordinator and Rust foundation in flight. Preparation also reported existing diagnostics; it is not an execution admission receipt. Prior delivery sessions released canonical ownership; this planning session claimed the clean checkout for only these docs/task edits. No service was stopped, started or reloaded. Preserve earlier explicit pauses and all current workers.

Tasks remain open in Now/Next without a planning-only hold. A has no logical task prerequisite; B waits for A, C waits for the six Rust builders, and D waits for A/B/C. Actual selection priority, path/resource admission, live ownership and capacity are separate. The runtime can see a canonical committed batch under its existing authority; this planning session dispatches nothing. No source-migration receipt, model result, installation, push or running-release upgrade is claimed.

Fresh read-only builder review found one material omission: A's two Paseo source consumers required their existing planning fixture and path assertions to move in the same atomic cut. Resolution: A now explicitly owns `integrations/paseo/tests/planning.test.ts`, its new-root/bootstrap/bytecode assertions and the offline Paseo check before B. The reviewer also verified the corrected Rust dependency graph, narrowed write scope and preserved loading/test/host boundaries. No other material blocker was found in that review. This is contract review, not an implementation check. Final saved-task/validation/commit readback accompanies this batch. Standalone planning ends after that handoff. Resume implementation through the selected task's supported execution workflow; recheck actual ownership and current source first. There is no unresolved product choice requiring another layout interview.
