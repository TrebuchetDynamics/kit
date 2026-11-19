# Product scope and architecture

Kit supplies coding-agent skills and optional native Hermes integration.
GitHub Issues own executable work; Orbi is the delivery successor, still paused
and live-unqualified. The pi-autowork executor and Paseo plugin are removed.
This document specifies current product contracts and accepted planned directions,
not a delivery ledger. Operator procedures belong in [installation](installation.md),
[cross-host setup](cross-host.md) and [removal/recovery](uninstall.md); current work
and goal status belong in GitHub Issues. Git history records past work.
Dated headings remain stable requirement anchors, not claims of fresh qualification.

## Accepted requirements

Status: Accepted

- Plan With Me asks for consequential missing intent and saves accepted decisions.
- Plan For Me investigates, chooses supported approaches and records executable
  GitHub Issues. An explicit objective keeps planning focused; a bare or vague request
  starts evidence-based discovery without inventing product direction.
- Unslop audits a user-facing flow and publishes accepted UI changes as GitHub Issues for Orbi; it does not implement the redesign.
- Docs Sync maintains source-backed documents and GitHub issue handoffs.
- Planning stops after publication. Retained authorized fix/apply and recovery modes
  preserve their own scope, ownership, checks, independent review and PR gates.
- Load supporting methods only when useful, not every skill on every task. Preserve
  explicit exclusions, concurrent work, caller limits and live gates.
- Support Hermes CLI/Telegram and native Claude Code, Codex and Pi packages.
  Workers, profiles, permissions, credentials and external integrations remain
  host-specific. Paseo can host these agents without a Kit executor plugin.
- GitHub Issues are the work board; Kanban and historical local records are never
  prerequisites for execution, recovery, review, installation or integration.

All first-party skills and portable adapters reach the
[shared freshness and ownership contract](../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership).
Mode controls effects, not automatic synchronization on every invocation. `/push`
saves all changes, pulls `main` and pushes `main`; it includes landed Orbi changes
through the verified upstream and reports outstanding issue/PR candidates without
taking coordinator-owned heads or bypassing review.
Read-only/audit and writable planning do not fetch or sync Git; authorized edits
inspect ownership and isolate stale/shared baselines. Delivery retains caller scope.

These contracts are detailed in [workflows](workflows.md). Planning does not grant
implementation, publication or deployment authority. Accepted scope does not settle
unresolved owner-only decisions or qualify runtime behavior. Dispatch, useful
execution, verified acceptance and external delivery are distinct claims.

## Accepted Rust and Octet redesign

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#accepted-rust-and-octet-redesign)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Current components

| Component | Source / contract | Responsibility |
| --- | --- | --- |
| Hermes registration | [entry point](../__init__.py), [workflow aliases](../scripts/workflow_commands.py), [research aliases](../scripts/autoresearch_commands.py) | Provision bundled skills/shared resources, defaults and cron scripts; register commands and literal arguments |
| Hermes maintenance | [bundle](../scripts/bundle.py), [menu policy](../scripts/telegram_menu_policy.py) | Own `hermes kit` maintenance registration; separate core registration from integration readiness and prioritize public commands |
| Fleet installation | [orchestrator](../scripts/setup_bundle.py), [preflight](../scripts/setup_preflight.py), [finalization](../scripts/setup_runtime.py) | Validate prerequisites, install resources/configuration, inspect profiles and refresh supported gateways |
| Portable packages | [Claude marketplace](../.claude-plugin/marketplace.json), [Codex manifest](../.codex-plugin/plugin.json), [marketplace](../.agents/plugins/marketplace.json), [Pi manifest](../package.json), [Pi extension](../adapters/pi.mjs) | Discover explicit portable workflows without Hermes configuration dependencies |
| Portable behavior | [host contract](../adapters/skills/COMMON.md) | Use the current host's tools and preserve its permissions, memory and credentials |
| Issue publication | [publisher](../scripts/github_issues.py), [handoff](../skills/shared/PLAN-HANDOFF.md) | Publish complete GitHub Issues and native dependencies before readiness; preserve existing ownership |
| Explicit suite refresh | [Update Kit](../skills/update-kit/SKILL.md), [helper](../skills/update-kit/scripts/update_kit.py) | Maintain dedicated persistent trusted upstream source and delegate installation; no automatic schedule, host-update fork or live qualification |
| Orbi lifecycle client | [helper](../skills/orbi/scripts/orbi_control.py), [workflow](../skills/orbi/SKILL.md) | Inspect or explicitly prepare/start/stop one deployment; the separate Orbi project owns implementation and delivery |

Native Hermes Python owners live under `src/autowork_runtime/`, loaded through
`src/autowork_bootstrap.py` by the existing thin entrypoints. The executor source
and integrations are absent; native maintenance is not a replacement executor.
The [bootstrap](../src/autowork_bootstrap.py) resolves peers and resources within
the selected release. Native owners are split into
[installation](../src/autowork_runtime/install/),
[updates](../src/autowork_runtime/update/) and
[commands](../src/autowork_runtime/commands/); `scripts/` also contains standalone
portable installers, publication and verification helpers. Keep those helpers and
the selected release together; an entrypoint alone is not the native payload.

Hermes workflow registration requests skill loading in the current conversation.
Registration does not execute a workflow.
Codex and Claude Code load portable adapters. Pi commands read adapter instructions
and send a user message, queued as a follow-up when busy. The [current host spellings](cross-host.md) and [README](../README.md)
own the public catalog; engineering remains a reference pack, not another public
coordinator. Grill Me compatibility opens Plan With Me challenge behavior.
Independent Autoresearch and its selectors remain available; its Hermes plan
selector uses the pinned protocol with Plan For Me adaptations, while portable
adapters hand planning to Plan For Me. Shared helper/reference paths remain valid.
Update Kit is explicit-only across these hosts. Its durable source lives at
`${XDG_DATA_HOME:-$HOME/.local/share}/kit/source`, outside project and host package
caches. It delegates full-suite effects (including supported active-integration
restarts) to the fetched installer; restricted Hermes cascades and no-restarts
requests hold before mutation. Nested native refresh can advance source again;
selected/final SHA reporting does not imply immutable installation or reload of
an already-running agent. See [installation boundaries](installation.md#update-kit).
Package discovery is not model execution or cross-host live qualification.

## Interface and state contract

The [workflow registrar](../scripts/workflow_commands.py) and
[research registrar](../scripts/autoresearch_commands.py) own Hermes aliases and
literal routing; [Pi registration](../adapters/pi.mjs) owns its commands. These are
conversation interfaces, not an owned HTTP service or Toolset OpenAPI contract.
Command collisions preserve the existing owner ([rules](workflows.md#commands)).

GitHub Issues, native dependencies and PR/check/review evidence own execution.
Existing local tasks, attempts and recovery state are preserved migration inputs,
not a second queue. Follow [migration](../skills/shared/TODO-WORKCENTER.md).
No store cleanup, setup preview or source change proves live qualification.

## Data and trust boundaries

Project documents and tasks belong to the target repository. Hermes receipts and
profile stores belong to its configured home and must not enter Git. Portable
packages do not configure those stores. [Memory](memory.md) owns capture/storage
behavior; [dependencies](dependencies.md) owns source pins and licenses.

Hermes defaults intentionally change approval settings; portable adapters do not.
Preserve the runtime-default opt-out. Preflight prevents installer-stage writes on
prerequisite failure, but CLI plugin loading may precede it and later failures are
not transactionally rolled back. [Installation's boundary](installation.md#preflight-before-fleet-writes)
is authoritative. No document or source-only change grants live, secret,
publication, money, destructive or deployment authority.

## Planned work and verification

GitHub Issues own priorities, unresolved decisions and goal evidence.
Eligibility does not establish live ownership, execution, review or qualification.
[Testing](testing.md) owns executable checks and their limits. Clean installation,
actual model execution, Telegram delivery and task acceptance are separate outcomes;
offline helper tests prove none of those live outcomes by themselves.
Measured native qualification remains pending. Model-driven recovery, original-environment delivery
and externally enforced spending/descendant limits still require their own evidence
and authority. Offline checks do not establish actual model startup or universal
latency. Removal does not satisfy these obligations or enable paused Orbi.

## Faster ready-task startup

<a id="outcome-and-scope"></a>
<a id="evidence-and-decision"></a>
<a id="worker-contracts-and-engineering-protocols"></a>
<a id="task-context-simplification"></a>
<a id="acceptance-and-measurement"></a>
<a id="ordered-work-and-exclusions"></a>

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#faster-ready-task-startup)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Autonomous execution authority

Status: Accepted

Planning handles consequential complexity; Orbi and already-authorized in-session
fix/apply modes execute accepted outcomes without repeatedly asking permission for
already-authorized work.

- Resolve design, decomposition, interfaces, migration and acceptance before handoff.
  Supply a short executable outcome/sources/checks/exclusions/stop contract, not an
  unresolved interview or mandatory chain of planning phases.
- The executor chooses reversible implementation details, fixes tests/fixtures and
  user-space tools, reconstructs attributable inputs and changes a failing approach
  without asking to proceed or restarting planning. Preserve accepted behavior and
  record material deviations. Complexity, a first failed test or missing fixture is
  work, not a permission blocker. Invent no inspect-only or one-rerun limits.
- The coordinator reconciles the original task with retained source/workspace
  evidence, preserves consumed budgets and pins, uses supported repair/alternate
  routes, finishes reviewed local closeout and continues eligible non-overlapping
  work. Do not repeat an unchanged audit or declare a whole profile blocked.
- Keep required tests, independent review, ownership, integrity/source checks and
  actual approvals. Run discriminating checks while editing; reuse only matching
  receipts and run required changed-input/final gates once. Observe an interrupted
  existing check instead of restarting it or calling it passed.
- Escalate only missing external input/authority or a consequential product conflict
  the accepted outcome cannot resolve. Name the held operation/input once, retain its
  resume step and continue independent authorized work. Do not bypass approval,
  fabricate credentials/evidence, seize live work or reset exhausted budgets.

Existing caller scope and saved stop/batch limits control continuation. Recurrence
authorizes the saved occurrence, not extra budget or scope. An at-most-one-new-batch
job keeps that limit; authorized closeout/work inside it needs no new approval.
An explicit multi-batch/whole-spec mandate continues within its existing limits.
Resolve a routine operating-policy question without another user permission round. Reuse
[recovery provenance](../skills/shared/PLANNING-CRAFT.md#recovery-provenance-and-qualification) and the
[standing decision policy](autonomy.md); add no permission framework or review lane.
Offline policy tests remain distinct from native/model qualification. These rules
supply no money, secret, publication, deployment, destructive or live authority.

## End-to-end original-task recovery

<a id="current-frontier"></a>
<a id="remaining-verification-and-operating-limits"></a>

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#end-to-end-original-task-recovery)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## TODO-first execution without Kanban

<a id="authority-and-scope"></a>
<a id="evidence-and-diagnosis"></a>
<a id="minimal-execution-contract"></a>
<a id="delivery-sequence-and-acceptance"></a>
<a id="non-goals-and-remaining-uncertainty"></a>
<a id="todo-first-delivery-qualification"></a>

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#todo-first-execution-without-kanban)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## TODO-owned task priority

<a id="ordering-contract"></a>
<a id="reconciliation-and-bootstrap"></a>
<a id="rollout"></a>

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#todo-owned-task-priority)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Checkable core-document completeness

Status: Accepted

- A tracked role manifest maps each role to a document/combined section, outcome
  status, covered sources and last-verified commit. Checks find broken local links/
  anchors, nonexistent documented repository commands and missing applicability.
- Git-only staleness checking reports covered source changes since verification
  without rewriting documents.
- Service, library, CLI/plugin, application and infrastructure profiles define
  baseline roles, including reference, glossary, troubleshooting and installation/
  upgrade where applicable. Do not reconsider applicability on every run.
- Adoption is opt-in; without a manifest Docs Sync retains prose behavior and creates
  no empty documents. The helper defaults to `docs/roles.json`, overridable with
  `--manifest`, and exposes `validate`, `check`, `stale` and `profiles`.

### Role source-evidence gaps

The [manifest](roles.json) records the source baseline for each reviewed role.
Architecture, test-plan, workflow and cross-host source maps cover the current
registration, CI inventory, native implementations and portable manifests. Their
baseline is a source review, not installed-host or model qualification. Other
roles retain their own recorded baseline or missing verification; they are not
silently marked current by this review.

| Role | Required evidence boundary / unresolved coverage |
| --- | --- |
| [Architecture](#current-components) | Current entrypoints, native registration, issue publication and lifecycle-client ownership are source-checked; workflow instruction adherence needs model evaluation. |
| [Test plan](testing.md) | Checker, CI and bundled Docs Sync test coverage are mapped; the inventory is not a full-suite execution or live qualification. |
| [Workflows](workflows.md) | Alias/routing/menu claims are checked against native implementations and Pi dispatch; actual model behavior and Telegram delivery remain separate. |
| [Cross-host](cross-host.md) | Adapter/package contracts are source-checked; historical install/discovery records do not qualify every current host/model. |
| [Reference](reference.md) | Current issue publication is mapped; historical task-store interfaces are retired, not missing implementation. |
| [Troubleshooting](troubleshooting.md) | Current remedies still need their target's actual environment and recovery evidence. |
| [Memory](memory.md) | Externally owned capture-policy claims need live qualification; no store access/replay is implied. |
| [Dependencies](dependencies.md) | Impeccable/Beautify inventories and command dependency pins extend beyond current coverage. |
| [README](../README.md), [installation](installation.md) | Covered-source reviews and structural links do not execute commands, install profiles or establish current live behavior. |

[`docs.py`](../skills/docs-sync/scripts/docs.py) accepts `reason` on mapped roles;
`check` scans entire mapped documents, including combined roles; `stale` uses only
`covers`, `verified_at` and Git history. It does not consume these gap notes, inspect
content accuracy, uncommitted drift, external URLs or live behavior. A known source
baseline replaces unavailable historical pins only after the role's current source
map is reviewed. It does not approve runtime behavior. Roles without coverage are not freshness-
assessed; silence for PRD, changelog, user-guide, removal or contributing is no proof.

## Reliability bug harvest (2026-10-15)

Status: Accepted ongoing reliability scope, not a completed-findings ledger.

Use evidence-backed, high-value bounded fixes with offline regressions; rank impact,
likelihood and fix cost without claiming live qualification. Preserve input tolerance
without losing task fields/prose, actual writer detection, approval opt-outs, robust
skill discovery, truthful updater/process status, supported config parsing, per-chat
menu isolation and accurate documentation checks.

Remaining defect leads require fresh reproduction, not presumed completion or new
acceptance: merged local-skill drift, task field/sub-bullet ambiguity, legacy prose
preservation, receipt timeouts/shell-status enforcement, nested worktree coordination,
status argument handling, executable modes, malformed facts and leftover skill
folders. Keep owner repair distinct from routine engineering repair.

## Vendored UI Taste skill

Status: Accepted

Vendor only `ui-taste`, using immutable upstream revision
`afd703a14a5db5f2fe6c2860badbe811058aa9e5` as source of record and per-file hashes in
`UPSTREAM.json`. Keep licensed upstream bytes, LICENSE/NOTICE and attribution intact
behind the toolset-owned adapter; upstream `SKILL.md` becomes `PROTOCOL.md` so it is
not independently registered. Preserve Apache-2.0 and incorporated attributions;
[dependencies](dependencies.md) owns the inventory. Refresh through documented
`git show <revision>:skills/ui-taste/<file>` plus hash verification, not runtime fetch.

Do not add the other Uizze skills, rewrite upstream text, run `npx` on install/update,
configure Uizze MCP, require an account or imply author endorsement. The optional
paid tools remain optional. Expose portable explicit invocation and Pi `/ui_taste`;
current menu priority may advertise UI Taste, README design, Impeccable, LGTM and
Git Commit Push. Engineering stays a reference pack. The adapter/routing safety
rules below supersede an unadapted upstream entrypoint.

## README design skill (2026-10-15)

Status: Accepted

Vendor `oil-oil/beautify-github-readme` at
`d6562a5f5c484d069f8560b39c215c9cda4b5a55` (MIT): a toolset-owned entrypoint, byte-exact
upstream under `upstream/` with `SKILL.md` renamed `PROTOCOL.md`, and tested hashes in
`UPSTREAM.json`. Exclude showcase images, translated READMEs and upstream Codex
manifest. Preserve explicit-only Codex/Pi adapters and the hyphen/underscore commands.

README claims remain source-backed through Docs Sync; run its checks after edits.
Pure SVG is the default; no bundled Hermes image generator is assumed. Never offer
upstream attribution/showcase submission unsolicited. Scheduled invocation
audits only unless task scope authorizes edits. Use the normal commit workflow.

## README polish (2026-11-05)

Status: Accepted root README presentation contract.

Keep the plain Kit heading, dark workflow diagram, one CI badge with HTTPS/alt text,
short pre-install warning and full Safety section. Component READMEs are outside
this bounded scope. Avoid unused hero/title assets and duplicate Paseo setup text.
Preserve every heading/incoming anchor, especially `#paseo-interface`,
`#first-use-in-your-project` and `#safety-before-installing`. A durable relative-link/
heading-anchor test complements the README audit and Docs Sync checks.

Do not change status, verification, host commands or policy claims, add logos/badges/
benchmarks/live-reliability claims, or touch another writer's candidate. Use checks
proportional to actual files; a structural/visual source edit proves no live outcome.

## New skill review (2026-10-15)

Status: Accepted adapter and audit requirements.

The README audit handles dark-mode `<picture><source srcset>`, reference-style
images, root-relative assets and angle-bracket paths with spaces, reusing upstream
SVG checks rather than modifying vendored bytes. Skill descriptions put meaningful
triggers first so host truncation does not hide their purpose.

Load one design skill per task, chosen by the user. An unnamed UI request uses UI
Taste; Impeccable owns its named commands, design-context setup and detector.
Scheduled/cron use only the read-only audit playbook unless scope authorizes
UI edits. Paid Uizze tools may be used only if already exposed by the host; never
configure MCP, request credentials or send private code in a query. Windows is not
a documented target; line-ending conversion must not be treated as passing vendored
hash integrity.

## Claude Code package (2026-10-15)

Status: Accepted portable marketplace support.

The root marketplace exposes the portable adapters, not an accidental default scan
of Hermes-only root skills. The copied plugin must retain adapter reference closure.
Portable adapters use `disable-model-invocation: true` and Codex explicit-only policy;
Pi registered commands read their instructions directly. Keep host package versions
consistent and add no hooks, agents, MCP servers or settings merely for packaging.
Current package names/install commands are in [cross-host setup](cross-host.md).
An installed real Claude Code workflow run is separate from manifest/discovery proof.

## Test-suite optimization method (2026-10-15)

Status: Accepted

Keep the pinned engineering TDD method; do not vendor a competing TDD skill or require
user confirmation of routine test seams. Use public seams and reject tautological
assertions. The toolset-owned
[`test-suite-optimization` protocol](../skills/engineering/local/test-suite-optimization/PROTOCOL.md)
is selected through `route.py --protocol`, not a new coordinator. Audit first;
changes become bounded authorized tasks. The [suite-thinning plan](test-suite-audit.md#suite-thinning-plan-2026-10-16)
adds thinner fixtures and fewer unnecessary tests, not a target test count.

Preserve touched line/branch coverage, measured critical mutation protection and
named regression risks. Per-test coverage contexts supply leads, not deletion
proof; missing subprocess coverage remains unknown. Mutation tools are optional
and disposable, never mandatory dependencies, network access or paid tools. Do not
delete tests to pass a gate or meet a count, weaken assertions or lower thresholds.

### Discoverable test-optimization-suite skill

Minimum means minimum sufficient protection against real regressions: measure value,
prune duplicate behavior, consolidate fixtures/cases and resist regrowth.

#### Reuse and distribution

Thin native/portable entrypoints share the existing protocol and
[test budget](../skills/shared/ENGINEERING-CYCLE.md#test-budget); retain the protocol
path/selector, explicit-only policy, Codex metadata and Pi command compatibility.
Verify archive/install reference closure instead of adding another installer or
copying the method. Do not change vendored protocols, scheduling or Telegram policy.

Default invocation audits the named/current repository and records supported findings
in its existing plan/queue. Explicit read-only saves nothing. Explicit apply or an
already-authorized implementation task permits bounded pruning with validation, not
another planning/permission ceremony. Reuse existing audit/tasks. “All my repos”
means a reusable method, not filesystem-wide deletion; identify targets and preserve
instructions and active writers.

#### Method contract

1. Build a behavior/risk matrix first: public contract, representative edges, layer,
   existing detector, unique boundary risk and cost. Use unit tests for pure logic,
   real integration for DB/HTTP/queue/serialization boundaries and a small critical
   smoke/E2E set. The lowest layer wins only if it protects the same risk; mocks do
   not prove a real handoff.
2. Bind evidence to source/tests, environment, command, collected count and outcome.
   Measure test/file timing, available CI history and bounded flake samples
   (failures/runs/window). Missing history is unknown, not zero. Inspect touched
   line/branch coverage and useful per-test contexts; total coverage is context.
   Mark subprocess/native blind spots. Avoid unconditional repeated whole-suite
   baselines; quantitative speedups need comparable passing measurements. Missing
   evidence blocks only dependent removals, not independent fixture improvements.
3. Map every deletion to a retained detector/oracle or a removed product obligation.
   Preserve incident traceability, unique branches, security, authorization, data-loss
   and qualification protection. A named regression may be consolidated only with
   an explicit equivalent-risk mapping. No recorded failures, matching coverage,
   low mutation score, mock calls or assertless syntax alone justify deletion.
   No-exception smoke, contractual logs, ordering and visible interactions can be
   valid oracles. Remove incidental internals/framework checks only if they protect
   no owned contract; deleted behavior may retain compatibility obligations.
4. Prefer labeled table cases, small builders and immutable shared setup, not mutable
   database/process sharing. Fakes/real boundary tests should improve fidelity.
   Combine assertions for one coherent behavior; property tests need useful
   generators/invariants/reproducible counterexamples and retain critical named
   examples. Golden outputs need an intentional stable contract and reviewable diffs.
   File splitting or fewer declared methods alone is not pruning.
5. Mutants survive, not tests. Record mutant-to-detector maps where available;
   preserve uniquely detected non-equivalent faults and compare the same source/
   operators. Equal killed sets are only leads beside the risk matrix. Separate
   uncovered, equivalent, invalid, ignored, pending and timed-out mutants; timeout
   detection is not proof of a meaningful assertion. Unavailable maps/tools stay
   unknown. No engine is mandated.
6. Set repository-specific CI time and justified new-case budgets with environment,
   baseline and exception review for distinct risks. Default to one appropriate
   regression for a bug, extending an existing case when sufficient, without banning
   necessary boundary coverage. No test-per-line/function quotas or mirroring TDD
   loops. Names/matrices identify risk without boilerplate; duplicate layers name
   their integration risk. Config/parser/migration changes can need checks even
   when prose/renames do not. Quarterly slow/noisy-suite review uses existing
   maintenance, not an unauthorized new timer.
7. Separate product races from test flakes. Quarantine requires owner, reason, expiry,
   issue and explicit lost protection. At expiry repair, or delete only after a
   supporting risk review; otherwise escalate visibly. Never hide critical failure.
   Impact-based CI selection is optional with sound mapping, retained full/periodic
   gates and fallback for unknown impact, never blanket skipping.

Output a compact keep/consolidate/remove/repair/quarantine/investigate map with
source-bound before/after evidence, retained risks, unknowns, budgets and next tasks.
Keep private CI history/credentials out of Git. Apply one supported batch, validate
focused behavior and the normal gate, and claim saved time only when measured.
Explain retained integration risk when a slower test stays.

#### Delivery and validation

Extend executable routing/package/install cases instead of phrase tests per rule.
Qualification fixtures cover equivalent table cases, same-coverage distinct auth
branches, valuable never-failed regression, assertless smoke, a real boundary missing
from mocks, flaky critical checks, equivalent/surviving mutants and missing CI/mutation
evidence. Exercise read-only versus authorized apply and unique-risk budget exceptions.
Check decisions/artifacts, not wording. No unsupported deletion, fabricated measurement,
live suite or repeated routine permission question is acceptable. Controlled fixture
or benchmark results are not installed adoption, model execution or live qualification.

## Gentler update rollout (2026-10-15)

Status: Accepted

Updater-requested restarts wait for a quiet gateway and report `deferred` rather than
force a drain. Quiet means no chat/API turn in flight, not no cron run: subtract
claimed restart-safe external cron workers from `active_agents`; unknown activity
is busy. Preserve Hermes' documented cron behavior without changing upstream code
or global timeout settings.

Coalesce bursts into one restart, expose concurrent-update ownership/wait clearly,
and report restart outcome, new process identity and menu resends rather than leaving
`requested` as final status. Report linked profiles and offer pinned clones so a
restart does not silently deploy unreleased checkout state. Preserve rollout scope,
active consumers and genuine pauses. Files updated is not running-code activation.

## Retired external-memory catalog policy (2026-10-15)

External-memory provisioning and catalog trimming are not Kit responsibilities.
Preserve existing providers, disabled-skill settings and stores.

## Parallel Autowork (2026-10-15)

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#parallel-autowork-2026-10-15)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Continuous Pi runner (2026-10-15)

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#continuous-pi-runner-2026-10-15)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Backlog replan (2026-10-15)

Current GitHub Issues and native dependencies, not dated queue snapshots or
local task records, control priority and ordering.
Split offline implementation from installed-profile refresh, service migration,
model/authentication and external-delivery qualification. Check real writers before
adopting candidates; an old review does not prove current source freshness. Preserve
owner-only decisions, stopped schedules and original-environment obligations; a
replacement host/profile does not satisfy a missing original delivery target.

## Rename to Autowork (2026-10-16)

The current product is Kit. Hermes terminal maintenance uses `hermes kit`;
`hermes autowork` is unavailable, with no functional alias, redirect or replacement
chat skill. Existing internal state/package identifiers remain compatibility
contracts, not an executable Autowork interface. pi-autowork is retired and
unsupported, not an execution namespace or development target.
Use current manifests and [installation](installation.md) for package names and
supported transitional settings. The retired `hermes-toolset` namespace has no
compatibility executor or automatic settings/cron migration.

Terminal maintenance uses `hermes kit doctor --json` for inventory and
`hermes kit update [--check]` for synchronous maintenance with a printed receipt.
The existing setup/update/pin/doctor/finalize actions, options, scopes, exit codes
and profile selection are unchanged. Hermes owns foreign-command collision rules;
Kit does not overwrite another owner or patch Hermes. No chat-maintenance
replacement is registered. Keep `AUTOWORK_EXECUTION_COMMON`, `# autowork:` cron markers,
and existing private `maintenance/toolset-update/` / `.toolset-imports.json` state
identities. A source rename does not reinstall profiles, reset private state or
restart hosts; live adoption remains a separately authorized operation.

<a id="pi-agent-harness-bootstrap"></a>

## Pi-Bolt-only harness installation (2026-11-16)

Status: Accepted. Replaces the previous Pi agent harness bootstrap requirement.
Real installation and live rollout remain separately unqualified.

Pi-Bolt is the only Pi harness Kit installs. The suite never downloads a stock Pi
installer or executes a stock `pi`, and never removes or updates an existing stock
Pi installation. Pi-Bolt's upstream installer, version policy and optional-extension
policy (off) remain unchanged.

Keep both component keys: `pi-bolt` bootstraps or refreshes the native executable
first; `pi` installs or refreshes `git:github.com/TrebuchetDynamics/kit` through that
verified destination `pi-bolt` only, never a CLI found on PATH. Both items have
Pi-Bolt's supported-platform availability. An absent or unusable destination fails
the package item with `./install.sh --only pi-bolt,pi` as repair; the package item
does not bootstrap a harness itself. `--skip hermes,pi` remains valid for nested
Hermes refreshes and leaves package installation/refresh untouched.

Every package install/update verifies registration and shipped skills before the
existing package-filter reconciliation. Stock Pi shares `~/.pi/agent` and sees
the same refreshed package; manual stock Pi package installation remains supported,
not installation of stock Pi by Kit. Preserve credentials, sessions, unrelated
settings, menu/skips, preview purity and other missing-host/restart rules.

Offline fixtures exercise the setup entry point, install/update ordering,
destination-only execution, missing/broken prerequisite failures, post-refresh
proof and settings repair. They do not qualify real upstream installation,
model workflows or live skill discovery. See [installation and recovery](installation.md#kit-pi-package-through-pi-bolt).

## Per-repository Pi models and accounts

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#per-repository-pi-models-and-accounts)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Compact task ledger

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#compact-task-ledger)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Managed Hermes checkout recovery

Status: Accepted recovery contract; no live host operation is implied.

When a verified managed checkout cannot fast-forward, recover automatically only
when safety checks pass, preserving original source/profile edits. Classify ancestry
exit 1 separately from Git failure; distinguish shallow/incomplete history, local
ahead/divergence and unrelated histories rather than guessing corruption/rewrite.
Allow bounded supported deepening only from the fixed trusted source; no arbitrary
remote/helper or network loop. Preserve pre-fetch provenance before it changes.

Replacement requires a same-user standalone registered managed path with expected
plugin identity/trusted binding, clean tracked/untracked source, installed HEAD
matching recorded managed provenance, and no live/unknown consumer or extra linked
worktree that would be unsafely rebound. URL/cleanliness alone proves neither
provenance nor absence of local commits. Ahead/local commits, unknown clones, unsafe
paths, dirt or uncertain ownership hold with precise recovery instructions; no force
flag weakens checks. Customized profile skills use evidence-based three-way merge.

Stage the exact trusted fetched revision; preflight native admission/scanning, profile
merges, source identity, shared consumers and permissions. Back up the complete old
checkout and necessary original merge source, not unrelated secrets/runtime state.
Publish through existing lock/freshness/transaction/backup/receipt machinery. Preserve
manifest metadata, modes, settings, opt-outs, selected profiles and pauses. Recover a
shared source once without expanding mutation to unselected consumers. Active users
defer; no kill, restart or repin is implied. No hard reset, stash, forced merge/push
or arbitrary old-source deletion.

Failures retain per-target evidence and resumable state. Resume reuses the original
backup/base, not a partially switched baseline. Rollback refuses newer foreign edits.
Read back source HEAD, managed bytes and preserved profile edits; unchanged repeat is
a no-op. Actual Git/network/native-scan errors stay actionable failures, not blanket
replacement triggers.

Installer summaries consume structured status/error/action receipts with bounded
text fallback. Show the actual cause/next action, not a JSON brace; preserve successful
component results and continue-after-component-failure behavior, with nonzero partial
failure. Retry only selected failed components. Respect skips and dry-run: preview
performs no recovery/network/write operation.

Offline proof uses disposable Git/fake homes/subprocesses for equal/fast-forward,
trusted rewrite, shallow history, local divergence, unknown/dirty/unrelated sources,
shared/live consumers, custom skills and scan denial. Inject fetch/stage/backup/switch/
publication failures and stale edits; prove resumable/no-op retry, source/profile
preservation, exact revision and unchanged pauses/config/successful components. No real
profiles, credentials, network or installers. Normal integration checks and independent
review remain required; source acceptance is not installed adoption.

<a id="task-status-vocabulary"></a>

## Task status vocabulary (2026-10-20)

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#task-status-vocabulary-2026-10-20)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Interactive checkout writer (2026-10-20)

One interactive session writes a checkout at a time. Its first edit holds the main
checkout until its edits are committed/reverted or the session ends; another session
stays read-only or uses canonical `.worktrees/<task>/`. Claude uses `EnterWorktree`
with the configured hook. Preserve other writers' dirty/unmerged work and commit
only attributable changes; do not treat historical claims as proof of current use.

## Task Store v2 (2026-10-20)

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#task-store-v2-2026-10-20)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Fleet TUI action surface

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#fleet-tui-action-surface)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Fleet blockers report

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#fleet-blockers-report)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Runner observation resilience

<a id="working-brief-and-boundaries"></a>
<a id="evidence-and-inventory"></a>
<a id="decisions-and-complete-batch"></a>
<a id="verification-pre-mortem-and-handoff"></a>

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#runner-observation-resilience)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Planning authority and shared protocol (2026-11-01)

The executor implementation/operating direction is superseded by removal.
The [original requirements and remaining qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/project.md#planning-authority-and-shared-protocol-2026-11-01)
are immutable migration evidence, not current runner instructions. Any still-required
product outcome must be reconciled into GitHub Issues with its original scope,
proof and human/live gates; removal is not acceptance or completion.
See [paused GitHub/Orbi cutover](github-native.md).

## Skill adherence and Definition of Done (2026-11-01)

Status: Accepted

High-risk skills use `## Common Rationalizations` and `## Red Flags`, retain one
`**Done when:**` line and link the shared
[Definition of Done](../skills/shared/DEFINITION-OF-DONE.md). It owns Kit-specific gates
and points to pinned Addy guidance for correctness, quality, integration, docs and
ship criteria; do not add another verification checklist/coordinator.

Apply the rule to Plan For Me, Ponytail Review, Git Commit Push, Docs Sync
and Plan With Me, and to later high-risk skills through [skill standard](skill-standard.md)
and Writing for Agents. Shared operating behavior lives in
`skills/shared/COMMON-CONTRACT.md`, not a second meta-skill. Keep commands explicit,
Ask Kit the sole router, and lifecycle phases mapped to existing owners.

Structural/routing checks and `scripts/skill_trace_eval.py` provide layered evidence.
Checked-in Tier 3 traces under `evals/tier3/<skill>.json` are synthetic fixtures;
live traces stay outside Git and use the same grader. These checks create no queue,
command, automatic activation, live qualification or delivery authority.
