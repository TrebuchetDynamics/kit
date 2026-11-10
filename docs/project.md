# Product scope and architecture

Kit supplies coding-agent skills, an optional Autowork runner and a native Paseo
interface. Autowork coordinates repository planning, documentation and development.
This document specifies current product contracts and accepted planned directions,
not a delivery ledger. Operator procedures belong in [installation](installation.md),
[cross-host setup](cross-host.md) and [removal/recovery](uninstall.md); current work
and goal status belong in the [task store](../tasks/). Git history records past work.
Dated headings remain stable requirement anchors, not claims of fresh qualification.

## Accepted requirements

Status: Accepted

- Plan With Me asks for consequential missing intent and saves accepted decisions.
- Plan For Me investigates, chooses supported approaches and records executable
  plans/tasks. An explicit objective keeps planning focused; a bare or vague request
  starts evidence-based discovery without inventing product direction.
- Docs Sync maintains source-backed documents. Tasks and goals live in `tasks/`,
  edited with `autowork tasks`.
- Autowork executes authorized work, verifies it and makes scoped local commits
  unless prohibited. Stalled preparation invokes bounded planning and retries
  execution without demanding a separate planner command.
- Load supporting methods only when useful, not every skill on every task. Preserve
  explicit exclusions, concurrent work, caller limits and live gates.
- Support Hermes CLI/Telegram and native Claude Code, Codex and Pi packages.
  Workers, profiles, permissions, credentials and external integrations remain
  host-specific. The optional Linux runner and Paseo interface do not replace skills.
- Repository tasks are the work board; Kanban and historical cards are never
  prerequisites for execution, recovery, review, installation or integration.

These contracts are detailed in [workflows](workflows.md). Planning does not grant
implementation, publication or deployment authority. Accepted scope does not settle
unresolved owner-only decisions or qualify runtime behavior. Dispatch, useful
execution, verified acceptance and external delivery are distinct claims.

## Accepted Rust and Octet redesign

Status: Accepted direction; planned, not the current runtime.

The [Rust Autowork with Octet plan](plans/rust-octet-autowork.md) supersedes the
language-retention direction for future redesign. The intended coordinator uses
Octet's native Rust agent engine, with automatic planning re-entry for ordinary
decisions and recovery. Sudo and special credentials are routine owner-help cases;
safety gates still apply. The plan separates the first offline batch from UI,
services, migration and live qualification. It grants no Python-runtime authority,
service restart or live migration.

The accepted [one-product-root contract](plans/pi-autowork-component-layout.md#one-product-root-contract)
places editable Python implementation, product tests, fixtures and dedicated tools
under `pi-autowork/`. Paseo package relocation remains a separate planned step.
Shared Kit resources and required host entrypoints stay outside. Preserve import
and package boundaries, selected-release identity, test inventories, locks and
runtime state. The Rust candidate's single crate, tests, fixtures and lockfile now
live in [`pi-autowork/rust/autowork/`](../pi-autowork/rust/autowork/README.md);
`rust/autowork/` is no longer an implementation owner. Other component placement
requirements remain governed by that contract. A directory move does not qualify
runtime behavior or permit deleting retained worktrees, restarting workers or
changing live gates.

## Current components

| Component | Source / contract | Responsibility |
| --- | --- | --- |
| Hermes registration | [entry point](../__init__.py), [workflow aliases](../scripts/workflow_commands.py), [research aliases](../scripts/autoresearch_commands.py) | Provision bundled skills/shared resources, defaults and cron scripts; register commands and literal arguments |
| Hermes diagnostics | [bundle](../scripts/bundle.py), [menu policy](../scripts/telegram_menu_policy.py) | Separate core registration from integration readiness and prioritize public commands |
| Fleet installation | [orchestrator](../scripts/setup_bundle.py), [preflight](../scripts/setup_preflight.py), [finalization](../scripts/setup_runtime.py) | Validate prerequisites, install resources/configuration, inspect profiles and refresh supported gateways |
| Autowork execution | [cycle](../pi-autowork/src/pi_autowork/engine/owner_cycle.py), [task execution](../pi-autowork/src/pi_autowork/engine/task_execution.py) | Select repository tasks, coordinate direct execution and protect live writers |
| Task store | [TaskStore](../pi-autowork/src/pi_autowork/engine/task_store.py), [selection](../pi-autowork/src/pi_autowork/engine/task_select.py), [task CLI](../pi-autowork/src/pi_autowork/task_commands.py), [converter](../pi-autowork/src/pi_autowork/task_migrate.py) | Read pinned contracts, select tasks, validate edits and convert legacy repositories once |
| Continuous runner | [runner guide](../pi-autowork/README.md) | Coordinate bounded workers, verification, local integration and recovery |
| Portable packages | [Claude marketplace](../.claude-plugin/marketplace.json), [Codex manifest](../.codex-plugin/plugin.json), [marketplace](../.agents/plugins/marketplace.json), [Pi manifest](../package.json), [Pi extension](../adapters/pi.mjs) | Discover explicit portable workflows without Hermes configuration dependencies |
| Portable behavior | [host contract](../adapters/skills/COMMON.md) | Use the current host's tools and preserve its permissions, memory and credentials |
| Paseo interface | [plugin guide](../pi-autowork/integrations/paseo/README.md) | Inspect the same tasks/runners and expose policy-gated actions; not a scheduler or provider |

Python owners live under `pi-autowork/src/`, with tests under `pi-autowork/tests/`. Root scripts and legacy entrypoints load those selected-release owners through the shared bootstrap, and Paseo planning uses the same source tree.

Hermes workflow registration requests skill loading in the current conversation;
`/autowork status` answers directly. Registration does not execute a workflow.
Codex and Claude Code load portable adapters. Pi commands read adapter instructions
and send a user message, queued as a follow-up when busy. Portable `/autowork`
defaults to runner startup; `/work` executes repeatedly in-session without starting
a service. The [current host spellings](cross-host.md) and [README](../README.md)
own the public catalog; engineering remains a reference pack, not another public
coordinator. Grill Me compatibility opens Plan With Me challenge behavior.
Independent Autoresearch and its selectors remain available; its Hermes plan
selector uses the pinned protocol with Plan For Me adaptations, while portable
adapters hand planning to Plan For Me. Shared helper/reference paths remain valid.
Package discovery is not model execution or cross-host live qualification.

## Interface and state contract

The [workflow registrar](../scripts/workflow_commands.py) and
[research registrar](../scripts/autoresearch_commands.py) own Hermes aliases and
literal routing; [Pi registration](../adapters/pi.mjs) owns its commands. These are
conversation interfaces, not an owned HTTP service or Toolset OpenAPI contract.
Command collisions preserve the existing owner ([rules](workflows.md#commands)).

Tasks and goals each have a Markdown file with schema-1 TOML frontmatter under
`tasks/`. [TaskStore](../pi-autowork/task-store.md) reads a pinned commit. An invalid
file refuses the whole snapshot with a `path:line` error; without `tasks/`, selection
names `autowork migrate` and selects nothing. Goal completion is the goal's typed
status and requires executed evidence, not an empty queue.

`autowork tasks` edits the working tree, refuses a file changed since reading and
keeps an edit only when the whole store validates. Text merges are per file;
integration judges execution validity by contract hash. Runtime closure carries a
sanitized receipt in `tasks/evidence/`; it is not a requirement to keep a permanent
completed-task archive. Current documentation retains requirements and unresolved
obligations; any reconciliation of satisfied records must preserve active attempts,
required proof, goal status, ownership and live gates.

Setup, upgrade, migration and removal remain governed by the runbooks. Preview
success is not rollback protection. Creating a task store initializes neither
installer/runtime stores nor live qualification.

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

The [task store](../tasks/) owns priorities, unresolved decisions and goal evidence.
Eligibility does not establish live ownership, execution, review or qualification.
[Testing](testing.md) owns executable checks and their limits. Clean installation,
actual model execution, Telegram delivery and task acceptance are separate outcomes;
offline helper tests prove none of those live outcomes by themselves. Measured native
qualification, model-driven recovery and original-environment delivery requirements
remain unqualified until their own evidence and authority exist.

## Faster ready-task startup

Status: Accepted default; measured native qualification remains pending.

### Outcome and scope

For accepted intent, a complete task body and usable sources, perform one batched
coordinator preflight, derive the handoff from that body and use the current-session
execution boundary. No separate validation-only round trip, Kanban transition,
fresh planning/docs pass or optional-method loading precedes normal ready work.
The real boundary still validates admission internally. Missing/conflicting input,
source drift, ownership conflict, failed admission or genuine ambiguity permits
bounded fallback. Reconcile pending review, integration and recovery before new work.

Keep routine source/check detail in private receipts and user status compact.
Distinguish queued, admitted, first useful action, failed/held startup and completed
work. A queue entry is neither useful implementation nor proof of a startup guard.
Keep errors and required user actions visible.

### Evidence and decision

Use [Autowork](../skills/autowork/SKILL.md),
[delivery batching](../skills/autowork/references/delivery-batches.md) and the
[current-session contract](../skills/autowork/references/owner-cycle.md#current-session)
for source-bound checks and actual owner identity. `EXECUTE` is a contract for the
session, not an implicit worker launch or useful action. Compose reusable controls
and move routine detail to receipts; do not reinstate a retired native handoff.
Fewer orchestration calls alone do not prove a universal runtime bottleneck or gain.

No opt-in fast mode, new schedule, extra parallel worker, relaxed budget, skipped
review, speculative cache or model/provider change is part of this requirement.

### Worker contracts and engineering protocols

- Give workers a short task-specific contract: objective, scope/exclusions, current
  evidence, acceptance/checks, ownership, immutable source and budget/stop conditions.
  Link detail rather than injecting the whole lifecycle reference. Do not omit an
  executable admission guard or make the worker guess constraints.
- Permit exact selection of one engineering protocol without mandatory phases or
  appended protocols. Explicit phase bundles remain supported; sufficient task
  instructions need no protocol. Load routing guidance only for a concrete selection
  need. Selected protocols/support files remain bound to vendored hashes.
- Autowork owns selection, dispatch, recovery, ownership, budgets, review, completion
  and publication. Upstream technique guidance creates no competing coordinator,
  approval ceremony or authority.
- Preserve required tests, independent review, active-writer protection, canonical
  authority, source freshness, integrity and task/commit identity. A smaller prompt
  or router reply is not evidence these gates passed.

### Task context simplification

Task bodies state remaining action, acceptance, checks, exclusions, dependencies,
ownership and next step directly, linking accepted contracts for detail. Remove
repeated rationale, not scope or completion criteria. Preserve ordering, real
ownership and remaining live gates. Less text is not a measured runtime speedup;
planning changes no dispatch, schedule or budget.

### Acceptance and measurement

One public coordinator entrypoint prepares normal ready work and derives required
handoff fields from authoritative context, without a separate validation command,
planner, docs audit, full suite or optional skill loader before dispatch. Missing
scope/acceptance yields a bounded diagnostic, never a fabricated contract. Admission
checks current source, dependencies, canonical authority, ownership, immutable base
and the applicable worker-start guard. Cover ready, stale, held, missing-context and
interrupted-handoff cases.

Runtime qualification separately measures request-to-handoff, queue wait, admission
and first useful worker action: a scoped test/reproduction or implementation after
admission, not a heartbeat or record creation. Compare routes using the same
disposable task, source, model, environment and cold/warm conditions; record elapsed
time, model/tool round trips, routine messages, exact receipts and failures.

Require fewer preparation round trips/messages with comparable source-bound runtime
evidence showing no startup-latency regression. No absolute or percentage target is
specified. Investigate contradictory timing rather than declaring success from
command count. Offline fixtures do not establish actual model startup or universal
latency. Native measurement needs an isolated configured environment with externally
enforced spending/descendant limits; its absence does not block independent offline
implementation. This measured qualification remains pending.

### Ordered work and exclusions

Offline implementation precedes runtime measurement. Preserve queue priorities and
leases. [Autonomous execution authority](#autonomous-execution-authority) settles
routine continuation without another permission round. Planning alone saves plans
and tasks; it does not dispatch, commit implementation, push, change live profiles/jobs
or claim faster operation.

## Autonomous execution authority

Status: Accepted

Planning handles consequential complexity; Autowork executes accepted outcomes
without repeatedly asking permission for already-authorized work.

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
[iteration rules](../skills/autowork/references/iteration-and-decisions.md),
[recovery](../skills/autowork/references/owner-cycle.md) and the
[standing decision policy](autonomy.md); add no permission framework or review lane.
Offline policy tests remain distinct from native/model qualification. These rules
supply no money, secret, publication, deployment, destructive or live authority.

## End-to-end original-task recovery

Status: Accepted

Recover existing product work through its task-store contract, accepted scope,
checks and attributable candidates. Helper delivery, installation, actual execution
and product acceptance remain separate. Card-free execution waives no tests,
independent review, real writer protection or explicit caller/task limits.

### Current frontier

Use the [current execution interface](../skills/autowork/references/owner-cycle.md),
not retired native handoff/card transitions. Adopt retained work only after actual
process-identity and overlapping workspace/source checks. Missing card operations
cannot veto repository work or scoped installation; supersession is not a native
acceptance pass.

Before a scoped update, preflight the intended immutable local source, real consumers
and customized skills; back up, apply through the supported path and read back hashes
and registration under existing deployment authority. Before delivery, refresh exact
review/candidate and local/remote evidence; do not repeat merges or reopen completed
work from an old report. Direct-main delivery needs its permitted policy; protected
PR requirements remain mandatory where applicable.

### Remaining verification and operating limits

Model-driven disposable recovery and useful-action startup measurement require
configured isolated environments and real external limits. Native no-agent fixtures
do not satisfy model acceptance or prove a speedup. Original reporting-environment
and Telegram-delivery requirements cannot be replaced by a new profile, schedule or
message. Retain them explicitly unqualified where that original target is unavailable.

Preserve task identity, dirty candidates, input-matched check receipts, independent
review and publication restrictions. Unknown usage is not zero; recurrence does not
replenish explicit allocations. Consider a supported runtime upgrade only for a
required, demonstrably supplied capability, without upstream patches; retired Kanban
prerequisites do not mandate an upgrade.

The owner's stop-all scheduling instruction remains in force. Preserve stopped and
paused schedules and intentionally paused product work. Installation, migration or
documentation never authorizes resumption. Missing attributable preview/source/owner
evidence holds its operation, not unrelated authorized local work.

## TODO-first execution without Kanban

Status: Accepted. The stable heading names the card-free contract; `tasks/` is now
the sole task store under [Task Store v2](#task-store-v2-2026-10-20).

### Authority and scope

- Repository task files own identity, intent, scope, acceptance, dependencies and
  priority. There is no second board or synchronized legacy execution index.
- Cron determines when an already-authorized agent runs. The session executes a
  bounded useful slice directly, using native delegation only when useful and
  authorized. Audits, maintenance and implementation need no card or assignee.
- No mandatory board lookup, import, release, continuation API or same-card
  registration gates selection, recovery, review, integration or deployment.
- Preserve real work, checks and constraints. Inspect process/workspace activity;
  historical cards are not leases. Migration does not kill workers, delete worktrees,
  change old cards or reset budgets. Superseded requirements are not marked passed
  or used to satisfy dependencies merely because their prerequisite was retired.

### Evidence and diagnosis

Use the same current-host-session model across hosts. Distinguish actual native
integration holds from other failures; do not attribute every failure to Kanban.
Scheduler capability, source inspection and registration are not proof of an installed
execution path, actual model behavior or message delivery.

### Minimal execution contract

Keep the task's existing ID. Necessary private evidence includes canonical
repository/workspace identity, actual session/worker identity and liveness, source
and candidate revisions, explicit limits/known usage, verified check/review receipts
and next action. Reuse suitable receipts; introduce no mandatory mirrored product
status, card-shaped machine or second task registry. Private coordination is not
product requirement authority.

Coordinate writers across profiles and worktrees of the same canonical repository.
Use actual process identity plus workspace/source inspection before adopting idle
work; elapsed time or a stale PID alone cannot prove release. Use supported locks
and isolated worktrees. Advisory local locks do not exclude noncooperating manual
writers or writers on other hosts; those require separate coordination.

Preserve explicit budgets and real host limits. Repeated cron ticks cannot replenish
an exhausted task allocation. Unknown usage is not zero; a prompt/receipt cannot
enforce spending. Use bounded host invocation/delegation controls without inventing
a universal lifetime-task budget to emulate cards. Missing cap enforcement holds
only the operation needing that cap; inspection and authorized verification/local
integration are separate from worker launch.

Required checks, independent review, source-bound reuse, serialized integration and
publication authority remain. Neither session completion nor a checkbox proves
acceptance; native review reassignment and card `done` are never prerequisites.

### Delivery sequence and acceptance

Direct selection must work without Hermes/Kanban setup and make zero default-path
Kanban calls. An unconverted repository follows Task Store v2 migration, not a
legacy alternate reader. Recovery ignores absent, malformed, blocked, done or
mismatched old cards without querying/changing them, preserves dirty candidates,
detects actual writers and reuses only still-valid checks. Explicit exhaustion
remains a real limit.

Skills, contributor guidance, cron prompts and scoped rollout use the same contract.
Preserve paused jobs, exact task filters, delivery bindings, authorized self-repair
bindings and publication limits. Do not force every invocation into planning,
audits or delegation. Contributors use ordinary Git edits, checks and review.

Required regression journeys cover ready work to useful action without card calls;
manual/cron contention; interrupted-check reuse and stale-input invalidation; crashes
before/after writes; repeat ticks without duplication; review changes and integration;
unavailable old-card recovery; explicit exhaustion; pause preservation; store/receipt
consistency and idempotent second pass. Retain failure evidence while required.
Focused offline checks, required normal gates and independent review bind to the
exact candidate. A bounded disposable cron journey needs its own configured host
and real limits, never a production target or duplicate schedule. Report source,
rollout, execution and Telegram separately. Rollback preserves candidates, receipts
and pauses and never silently restores Kanban prerequisites.

### Non-goals and remaining uncertainty

Do not patch upstream Hermes, repair consumer product code outside scope, discard
cards/candidates, weaken checks, broaden live/publication authority, reset allocations
or build another Kanban implementation. No optional Kanban backend is planned.
Exact host limit/liveness interfaces and migration races require source research
and qualification, not another product interview or waiting for a Kanban API.

### TODO-first delivery qualification

The current direct entrypoint selects repository contracts without native dispatch
or reconciliation. Its check boundaries include process identity, worktree/profile
contention, preserved dirty candidates, command failure/timeouts, explicit allowance
exhaustion, child cleanup, plan/dependency binding and source/executable freshness.
Generic command receipts record execution, not reusable acceptance or task completion.
Linux process-birth identity and Git-common-dir locks do not provide distributed
exclusion. Scoped installation observes direct leases and actual consumers, not
historical boards. Docs Sync permits normal branch-local edits under the shared lock.

Native script-only scheduler qualification is bounded to isolated job-store/due-job
selection, claiming, script execution and local result recording. It excludes model
calls, production jobs/product repositories, Telegram and unrelated upstream worktree
garbage collection. Profile installation, model-driven scheduled behavior and live
message delivery remain separate and unqualified by those offline/no-agent checks.

## TODO-owned task priority

Status: Superseded format; current priority is each task's `section` and `rank`.

### Ordering contract

[Task Store v2](#task-store-v2-2026-10-20) owns ordering: focused goal, section,
rank, goal priority, derived goal status, then ID, subject to mandatory dependencies.
Priority is human intent, not a lease or permission to bypass admission. Selection
does not rewrite files or maintain a second reconciled ordering record.

### Reconciliation and bootstrap

Use `autowork tasks` for ordering and `autowork migrate` for the one-time legacy
conversion. Preserve task bodies, acceptance, dependencies and ownership; require
validated unchanged inputs rather than silently favoring stale legacy order. Do not
revive legacy reorder/bootstrap commands as a parallel selection authority.

### Rollout

Consumer migration is separate from offline tool delivery. Convert repositories
under their owner's scope, preserving current inputs and deferred failures. No push
or fleet-wide mutation is inferred. Stopped/paused jobs remain stopped/paused.

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

The [manifest](roles.json) is not a fresh content-verification receipt. Preserve
its explicit unresolved gaps; this document cleanup does not reverify roles or
advance pins. Non-ancestor pins establish non-ancestry, not that an old review was
false or current source is verified. Structural checks do not qualify runtime.

| Role | Required evidence boundary / unresolved coverage |
| --- | --- |
| [Architecture](#current-components) | Registration, all covered skills and Pi adapter still need current-source reverification; linked engine/task-store sources lie outside `covers`. |
| [Test plan](testing.md) | Reconcile inventory and qualification claims with covered tests and documented engine/Docs Sync tests outside `covers`; listing tests is not running them. |
| [Workflows](workflows.md) | Recheck aliases, routing and menus, following registrars into their implementation sources; task-store skill/CLI instructions need separate coverage. |
| [Cross-host](cross-host.md) | Recheck adapter/package/runner claims; install/discovery evidence does not qualify current host/model behavior. |
| [Reference](reference.md) | `task_prepare.py` and `task_migrate.py` are outside current coverage. |
| [Troubleshooting](troubleshooting.md) | Task-store and Docs Sync remedies require unchecked sources beyond coverage. |
| [Memory](memory.md) | Externally owned capture-policy claims need live qualification; no store access/replay is implied. |
| [Dependencies](dependencies.md) | Impeccable/Beautify inventories and command dependency pins extend beyond current coverage. |
| [README](../README.md), [installation](installation.md) | Covered-source reviews and structural links do not execute commands, install profiles or establish current live behavior. |

[`docs.py`](../skills/docs-sync/scripts/docs.py) accepts `reason` on mapped roles;
`check` scans entire mapped documents, including combined roles; `stale` uses only
`covers`, `verified_at` and Git history. It does not consume these gap notes, inspect
content accuracy, uncommitted drift, external URLs or live behavior. The four
unresolved architecture/test-plan/workflows/cross-host non-ancestor findings remain
unqualified, not fresh/pass verdicts. Roles without coverage are not freshness-
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
upstream attribution/showcase submission unsolicited. Scheduled/Autowork invocation
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
Scheduled/cron/Autowork use only the read-only audit playbook unless scope authorizes
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

Status: Accepted. `tasks/` is the task authority; parallelize independent implementation,
not repository authority. Sequential mode remains supported.

- **Entry and hosts:** `owner_cycle.py REPO --parallel N` opts into parallel mode;
  bare `--parallel` defaults to 2, ordinarily capped at 4 unless `--max-workers`
  raises it, with hard limit 8. Never exceed runnable independent tasks. Workers are
  separate host CLI process groups with per-worker folders and recorded PID birth
  identity. Hermes/Codex/Pi templates preserve approval/sandbox policy. Claude Code
  needs an explicit usable custom command rather than selecting unattended approval
  mode for the user. JSON argv supports `{worktree}`, `{prompt_file}`, `{timeout}`.
  Missing usable template or Linux `/proc` produces explained sequential fallback.
  Expose commands/permissions; verify actual CLI compatibility before shipping.
- **One task per worker:** provide body, worktree, branch, immutable baseline and
  rules, without recursively loading task selection. Workers edit only their
  worktree, never coordinator-owned files or other worktrees; make the contracted
  local commit once, never push/merge. `report.json` identifies commit, changed files, checks/results, blockers
  and proposed changelog text. Native subagents are permitted within authority;
  workers do not start other coordinator workers. Every delegated agent has a fresh
  context and explicit scope/write/completion limits.
- **Coordinator ownership:** task/goal bookkeeping, completion receipts and changelog
  are coordinator-owned. Worker changes to protected authority/checks or bookkeeping
  hold integration; base authority cannot be enlarged from a candidate branch.
- **Concurrency:** concurrent tasks have no direct/transitive dependency or shared
  resource token. Ordinary `touches` overlap ranks work but does not block dispatch,
  regardless of task count. Workers use separate worktrees and integration resolves
  conflicts. Only `exclusive` requires running alone; `live` still needs authorization.
  Manifests, lockfiles, migration/schema folders and CI workflows are serial paths.
  Missing touches is no scheduling hint, not a reason to run alone. Undeclared
  protected paths still hold integration. Claims retain dependency and resource gates.
- **Priority:** backfill independent work only without conflicting with waiting work.
  A truly solo waiting task drains the pool instead of starving. The accepted
  [progress/independent-workers plan](plans/2026-10-16-pi-autowork-coordinator.md#useful-progress-and-independent-workers)
  retains admission gates while improving scope, candidate-preserving recovery,
  visible reasons, delivery stages and log navigation; planned additions are not
  evidence of implemented qualification.
- **Lease/journal:** `<git-common-dir>/autowork-execution/` owns `coordinator.json`,
  `slots/<TASK>.json` and append-only `journal.jsonl`, written under `writer.lock`.
  One live coordinator owns the repository; sequential and parallel claims exclude
  each other. A live worker lease never expires. Workers do not masquerade as the
  coordinator through `AUTOWORK_EXECUTION_COMMON`. Slot states remain private
  execution observations, not product completion authority.
- **Recovery:** reconcile before dispatch in either mode. Adopt a proven live worker,
  never duplicate it. Queue a dead worker's commit for validation/integration;
  preserve uncommitted candidates as interrupted; release clean no-result work.
  The bounded interrupted retry restarts once in the same worktree with a resume
  note (attempt 2). A held conflict/scope/report/validation result gets one fresh
  attempt after the pool drains, on `autowork/<TASK>-r2` from current canonical HEAD,
  retaining the first branch/worktree. A second failure stays held for supported
  fix-or-skip recovery. Preserve consumed attempt bounds; exhausted technical repair
  stays visible engineering work, not an invented owner decision. No failed worker
  removes another's result.
- **Worktrees:** create new task/integration worktrees under the canonical checkout's
  `.worktrees/`, not sibling directories. Branches retain task identity. Refuse
  foreign existing names unless recorded ownership permits reuse. Give slots their
  own `TMPDIR` and port allocation (`20000 + 100 × slot`). Preserve active, dirty,
  locked, unmerged and recovery-bearing worktrees. Apply the
  [closeout contract](../skills/autowork/references/worktree-closeout.md) to sequential
  and parallel results: verified work reaches configured `main`/`master`, and safely
  eligible finished worktrees/merged branches are removed. Cleanup eligibility
  requires clean, unlocked, unused, integrated work and the applicable quiet period
  (30 minutes for opportunistic cleanup), never elapsed time alone as release proof.
- **Integration:** serialize reported results in priority order in the owned
  integration worktree. Verify ancestry/scope/report, merge without automatic
  conflict resolution, run task plus combined checks through the bounded runner,
  then fast-forward canonical only if HEAD has not moved. Rebuild once on changed
  HEAD; preserve Git's dirty-file refusal. Only validated integrated work closes
  through TaskStore bookkeeping/receipt publication. Dependents wait for closure;
  a worker exit or isolated check pass is never completion/combined correctness.
- **Limits:** default worker timeout is 3600 seconds with process-group cleanup.
  Admit only when `MemAvailable` is at least twice `--min-free-mem-mb` (default
  1500) and one-minute load is below CPU count. Resource holds wait rather than
  fabricate failure. Wall-time/concurrency caps do not meter provider/token spend;
  unknown spend is not zero. Preserve any externally required stronger caps.
- **Observation:** `--parallel-status [--json]` reports state, slot, worktree, elapsed
  time, reason, checks, commit and integration; journal-derived metrics distinguish
  work, integration and waiting time, peak workers, conflicts and retries.
  `--wait --timeout S` waits in the helper without model polling. Unknown/unreliable
  timings must not become fabricated zeroes.
- **Owner and validation identity:** `--apply --parallel` requires the persistent
  coordinator's `--owner-pid`, reused by refill/wait/integrate/close. Without it,
  return `ACTION_REQUIRED`. Validation runs under that lease, not a competing
  sequential `active.json`; hold the writer lock only for state mutation. Preserve
  bounded subreaper/timeout/descendant-cleanup receipts and sequential behavior.
  Hermes workers use the coordinator profile/model unless explicitly overridden.

No remote queue/database/second board, automatic conflict rebase, default-mode change,
publication, deployment, history rewrite or inferred live LLM speedup is included.
Host concurrency and real-worker performance need their own qualification.

## Continuous Pi runner (2026-10-15)

Status: Accepted

A package/copyable launcher targets the caller's repository and selects work before
starting a bounded Pi run; an empty/non-runnable queue idles without model calls.
Defaults are `openai-codex/gpt-6.1-sol` with
`openrouter/deepseek/deepseek-v4.1-flash` fallback. Preserve configured overrides,
record the actual model and give fallback no broader authority. Parse Pi events because successful process exit alone does not
prove a successful model response. Use the supported skill/runtime invocation, not
an extension command presumed synchronous. The [runner guide](../pi-autowork/README.md)
and [RPC contract](../pi-autowork/docs/pi-rpc.md) own current transports and configuration.

Local locks alone do not coordinate Hermes cron: refuse conflicting Autowork cron
ownership of the same repository. Unconverted repositories follow Task Store v2's
zero-token migration wait. Fallback switching and multi-task continuous live behavior
require separate real-host qualification; fake-Pi tests do not prove them.

## Backlog replan (2026-10-15)

Current task records, not dated queue snapshots, control priority and dependencies.
Split offline implementation from installed-profile refresh, service migration,
model/authentication and external-delivery qualification. Check real writers before
adopting candidates; an old review does not prove current source freshness. Preserve
owner-only decisions, stopped schedules and original-environment obligations; a
replacement host/profile does not satisfy a missing original delivery target.

## Rename to Autowork (2026-10-16)

The current product is Kit; Autowork remains its execution/maintenance namespace.
Use current manifests and [installation](installation.md) for package names and
supported transitional settings. The retired `hermes-toolset` namespace has no
compatibility executor or automatic settings/cron migration.

Maintenance recognizes exact `/autowork update|status|list` forms; other arguments
remain workflow requests (for example, updating a README). Terminal maintenance
uses `hermes autowork`. Keep `AUTOWORK_EXECUTION_COMMON`, `# autowork:` cron markers,
and existing private `maintenance/toolset-update/` / `.toolset-imports.json` state
identities. A source rename does not reinstall profiles, reset private state or
restart hosts; live adoption remains a separately authorized operation.

## Pi agent harness bootstrap

Status: Accepted requirement; positive missing-harness installation remains planned.

A selected Pi install component must install a missing harness from pi.dev and then
the package in the same invocation, not silently skip Pi or require a preinstalled
CLI. Preserve existing working harnesses/packages, full/verbose defaults, menu/skips,
other missing-host rules and all credentials/settings.

Prefer the official managed installer: download first with HTTP failure checking,
run through captured output, verify and reuse its absolute executable. Resolve
managed/user-local paths without assuming child PATH changes reach the parent.
Respect native Node/npm prerequisite prompts/refusal; no automatic sudo, invented
unattended flag, forced shell-profile edits or global npm fallback. Captured startup
must not open an agent or call a model. Reimplementing Node provisioning or migrating
a working harness is outside scope.

Offline proof uses fake downloads/bootstrap/harnesses in isolated HOME/PATH: missing/
existing/off-PATH harness, extension idempotence, download/bootstrap/probe failure,
prerequisite refusal, skip/menu behavior and zero-write/no-download preview. Require
no agent/service startup and normal source gates. Live install/plugin rollout remains
separate; this requirement does not claim new tests or bootstrap qualification.

## Per-repository Pi models and accounts

Status: Accepted feature contract; real authentication is separately gated.

The TUI selects repository-specific primary/fallback models and connects API-key or
subscription accounts through the selected Pi installation's public library. Preserve
existing model configuration and outstanding service-migration gates.

- Extend Models with provider grouping/search, stable complete IDs (including slashes),
  selections, explicit fallback clearing, account status and Connect. Credential-
  requiring models stay visible. Repositories may configure before first start or
  before their queue is runnable; Start retains readiness gates.
- Reuse private per-instance env settings, not a second model database. Configuration
  is not service installation. Keep settings through first install and refuse
  repository-name collisions. Saving never installs/enables/starts/unpauses. For a
  running service, restart remains explicit; declining saves pending values for next
  start and leaves workers untouched.
- An account belongs to the runner's Pi user/agent context, never the repository.
  Resolve its executable, matching SDK/runtime, agent directory, model configuration
  and inherited provider environment. Show shared-context impact; preserve overrides.
  Do not authenticate another global Pi silently. Follow one stored credential per
  provider; replacement needs confirmation, with no multi-account vault or import.
- Use a small local JSON-lines Node bridge to the selected Pi's public SDK, keeping
  Python/Textual UI. Support managed and npm/symlink layouts with matching Node,
  capability/version checks and actionable failures. No network-installed second SDK,
  guessed global fallback or upstream patch. Include the bridge in release closure.
- The inspected public surface uses `ModelRuntime`/`ModelRegistry`, creation with
  `refreshOnCreate: false` and `allowModelNetwork: false`, structured provider/model/
  credential metadata and `login(providerId, type, interaction)`. Verify executable
  exports rather than typings alone. Show only LLM model kinds. Derive API-key/OAuth/
  subscription methods from provider metadata, not hardcoded registries or guessed
  CLI/RPC login contracts. Pi owns prompts, callbacks, refresh, locking and storage;
  internal `AuthStorage`/old OAuth snippets are not a supported contract.
- Passive display uses bundled/cached catalog and credential metadata, never resolved
  request auth, OAuth refresh, configured key-command execution, model calls or
  automatic catalog network. Include trusted configured custom providers/models but
  do not execute project extensions for display. Test disk/cache effects and forbid
  credential mutation during reads; visible account status proves no entitlement.
- Secret/text/select/code input is ephemeral and masked where appropriate, without
  history. Send through private pipes, never shell interpolation, argv, logs, receipts,
  repo files or service env. OAuth URLs/codes appear only transiently. Consume secret
  login results inside the bridge; return allowlisted non-secret status, never raw
  errors/causes/token responses. Clear prompt/widget references after completion.
- Request IDs and cancellable state prevent stale refresh/login results updating a
  different selection. Handle prompt/overall cancellation, timeout, child exit and
  UI close; abort callbacks/resources. Before credential commit, preserve the old
  account. After commit, report saved/refresh-pending rather than deleting valid
  credentials or claiming no change. Handle `CredentialSynchronizationError` without
  serializing its credential property or automatically repeating login.
- Account mutation is native-terminal-only. `autowork web` supplies an explicit
  served-origin denial even if its PTY looks local; `--view-only` denies mutation.
  Enforce handlers and bridge, not buttons alone. Web model selection retains its
  access rules; remote secret entry is separate. Successful login refreshes metadata,
  not model choices, work dispatch, service restarts, jobs or paid validation calls.

Offline checks use fake services/providers/callbacks, private disposable stores and
headless UI: distinct repository settings, collision refusal, configuration-before-
install, correct contexts/custom models, unsupported API denial, Pi-owned key/OAuth
commit, cancel/error/late results, secret absence from every output surface, committed-
but-refresh-failed handling, web/view-only backend denial, both layouts, release closure
and restart-decline behavior. Bind tests to the real public SDK surface, not merely
self-consistent fakes. New planned checks are not execution evidence.

Live qualification requires owner-authorized credential use and a selected provider/
context, preferably an isolated agent directory without imported production secrets.
Qualify only methods/providers actually exercised; no model call, service migration
or cron operation is included. Keep this independent of unrelated live migration.

## Compact task ledger

Status: Superseded by [Task Store v2](#task-store-v2-2026-10-20).

The [compact ledger plan](plans/compact-task-ledger.md) is not a second current file
format or conversion authority. Current tasks/goals use the single Git-native store;
future format adoption requires compatible tooling and explicit migration scope.

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

Status: Accepted

| Headline | Meaning | Detail examples |
| --- | --- | --- |
| Active | Being worked now | Starting, Implementing, Verifying, Reviewing, Merging |
| Mergeable | Required checks/review passed; only merge remains | Verified, Reviewed |
| Waiting | Queued behind a prerequisite/capacity/turn without an unresolved obstacle | Implemented, Merged, Paused, named resource/dependency |
| Blocker | An obstacle needs resolution | Cause plus Agent repair, Needs you or External owner |

Progress words are details. Implemented is not checked; Merged names a branch, not
Done; Done requires acceptance. Mergeable needs check/review evidence, not a commit
or engine state. Waiting always names why. A wait rooted in a repair/person, claim,
non-runnable entry, external condition, owner decision or dependency cycle is a
Blocker; identify the root and affected tasks. Automatically lifted overlap is
Waiting. An open owner question in `BLOCKERS.md` shows Needs you; do not invent an
External mapping where the implementation has none.

A live, attempt-matched merge resolver shows **Active · Resolving conflict**, not
failure. Its engine slot stays held until adoption; this display grants no merge
or closure authority. Queued recovery is not a running resolver. After adoption,
the commit waits for verification; recovery alone is not checked or complete.
Absent, finished or stale recovery evidence leaves the engineering hold visible.

Failure type and resolution owner are separate typed fields shared by engine,
health, questions and TUI. Exhausted review rework, dead workers, timeouts, conflicts
and dependency waits remain engineering/recovery holds even after retries end;
only consequential product/scope/authority/unavailable human input creates
`USER_DECISION`. Keep technical findings/next steps visible, not discarded or
relabelled as owner questions.

Slot names stay internal; evidence derives display headlines. Runner
working/paused/stopped/unavailable is a separate axis. Fleet totals partition every
open task exactly once into Active, Mergeable, Waiting, Blocker or Decision; those
sum to Total. Waiting reason/phase subtotals sum to Waiting.

## Interactive checkout writer (2026-10-20)

One interactive session writes a checkout at a time. Its first edit holds the main
checkout until its edits are committed/reverted or the session ends; another session
stays read-only or uses canonical `.worktrees/<task>/`. Claude uses `EnterWorktree`
with the configured hook. Preserve other writers' dirty/unmerged work and commit
only attributable changes; do not treat historical claims as proof of current use.

## Task Store v2 (2026-10-20)

Status: Accepted current task architecture.

`tasks/items/<ID>.md` and `tasks/goals/<ID>.md` are Markdown under `+++` TOML frontmatter;
`tasks/evidence/` carries sanitized runtime closure receipts. Goals are optional
multi-task outcomes; an ungrouped task is a first-class record, not an implicit goal.
Ordinary authoring supplies title, scope, acceptance and checks; tooling derives
IDs, list labels and scheduling defaults. The coordinator still resolves bounded
write scope and shared resources before dispatch, with denied live authority by
default. Reference shared specifications instead of copying task contracts; routine
tasks need no separate plan, goal or completion report. BLOCKERS.md managed questions
are a task/runtime projection, and no TODO.md view is created by default. The engine reads only
`tasks/`. `autowork migrate <repo>` converts once. An unconverted one-shot exits with
that instruction; a service waits at zero tokens. There is no legacy second reader,
generated index or dual write.

- One TaskStore interface supplies immutable records from a pinned Git commit to
  selection, dispatch, integration, closure, runner and TUI. Uncommitted edits are
  pending, not admitted contracts. Planning edits through `autowork tasks`, not its
  own parser. Private legacy parsers belong only to migration.
- Record revision fingerprints every byte; execution contract hash covers scope,
  acceptance, checks, dependencies, exclusions and execution authority. Title, notes,
  rank and moves within Now/Next do not invalidate work; Needs decision/supersession
  and real contract changes do. Touches-only edits schedule work without invalidating
  the admitted contract. Keep scope/authority checks distinct from scheduling hints.
- Resources, ownership, live authorization and kind are typed; absence grants nothing.
  A declared check is not permission to run it with coordinator rights. Authority
  comes only from the admitted base. Worker-added tasks or authority/check changes
  are held for the coordinator, never merged as harmless bookkeeping.
- Git status (`open`, `done`, `superseded`) is not a worker lease. Private engine state
  owns running/held/integrating identity. Closure publishes one bookkeeping-only
  status/receipt commit through the journal exactly once. After session merges,
  reopen a done task with a receipt for another contract before canonical moves;
  prompt guidance is not enforcement. Manual evidence-note closure without a receipt
  does not obtain that receipt-hash check.
- Selection is focused goal, section, rank, goal priority, derived goal status, ID,
  with mandatory dependencies and admission. `autowork tasks why ID` explains reasons.
  A corrupt snapshot fails closed; an incomplete draft remains visible, not runnable.
- Read TOML with `tomllib`; schema-bound writes preserve every valid record and refuse
  unsupported data. Whole-store validation and expected-input checks protect edits.
  Holds are notes, not automatically owner questions; TUI answers use the task CLI.

No distributed lease/SQLite redesign is included. Convert consumer repositories
under their owners' scope, without changing identities, goals, active attempts,
leases, receipts, budgets or pauses. Current-record reconciliation must preserve
verified-dependency evidence and unresolved qualification; deleting satisfied history
never proves goal completion or authorizes a running-contract change.

## Fleet TUI action surface

Status: Accepted narrow interaction contract.

Remove Fallback and Nous Portal global hotkeys/menu/help/palette exposure in selected-
runner and empty-fleet states. Filter fleet actions, not shared CLI/backend capability.
Keep Model, normal runner/task/navigation actions and read-only fallback information;
child screens retain unrelated local `f`/`o` keys and ordinary typing.

Preserve fallback execution/configuration, `autowork model --fallback`, `setup-portal`,
opt-in consent, stored settings and Portal privacy/confirmation checks. Test Portal
components directly without restoring shortcuts. No service/provider writes, policy
redesign, queue cleanup, branding or remote-host actions follow from this requirement.

Rendered isolated pilots cover running/stopped/paused selection, empty fleet,
view-only, absent active shortcuts and usable remaining controls at 80/120 columns.
Pressing removed keys invokes no modal/probe/configuration/runner command. Preserve
mouse/copy and child keys. Actual rendered coverage must run, not count a skipped
Textual dependency as a visual pass. Source checks do not prove installed delivery.

## Fleet blockers report

Status: Accepted read-only diagnostic contract.

`b Blockers`, clickable and available view-only, reports the selected repository's
full recorded questions/reasons/IDs, startup/dispatch refusals, resources, main-check
state, holds/dependency roots, worker waits/quiet observations and committed eligibility/
owner notes. Preserve setup Backlog as `g Backlog`. Separate runtime observations
from committed rules. Missing/invalid/old data never establishes health/admission;
quiet does not mean dead. Exclude env, credentials, provider configuration and whole
logs/transcripts.

The selectable scrollable report has `c / Copy report`, explicit `r` refresh and Esc
return. Preserve terminal drag selection/opt-in mouse. SSH clipboard delivery is
terminal-dependent, not proven by source checks. Open/refresh/copy starts no repair
agent, changes no repo/task/service/provider state, answers no question and controls
no runner. Collect off the event loop, serialize physical reads across reopen,
coalesce requests and reject closed-screen/wrong-runner results. Do not restore the
removed Fallback/Portal controls.

Offline proof uses committed-store/read-only/error fixtures and pinned Textual pilots
at 80/120 columns for keys/click/copy, view-only, empty fleet, denied controls and
Event-barrier stalled-reader/closed-screen/identity races. It does not qualify actual
remote clipboard transport.

## Runner observation resilience

Status: Accepted diagnostic requirements; installed adoption/live recovery remain
unqualified. Saving or editing these requirements proves no implementation checks.

### Working brief and boundaries

Make diagnostics robust to absent optional check values and unreliable wall-clock
ordering. Keep coordinator activity, successful task observation and owned jobs
separate. Change Autowork only, never another repository, its configuration or
upstream Hermes. No service/restart/install/model call, runtime-record rewrite or
change to scheduling, admission, ownership, verification, publication or live gates
is implied. Display improvements grant no execution authority.

### Evidence and inventory

The relevant seams are optional check fields written by supervision, health
validation, journal append/read, parallel status, fleet projection and idle-cycle
logging. Health write time and successful snapshot time are different provenance;
verified runner/job identity is not proof of current task observation. Wall-clock
inversions do not establish NTP, corruption or another writer as their cause.
Preserve malformed-observation isolation and source/stale-working guards. Use stable
public imports and disposable fixtures rather than modifying real fleet records.

### Decisions and complete batch

1. Permit null only on actually optional check fields such as `crashed`/`gated`.
   Required fields and wrong non-null types still fail. Exercise writer-to-health-
   to-fleet round trips and a healthy sibling, not blanket validation relaxation.
2. Preserve physical append order, event deduplication and historical bytes. Keep
   strict ordered reads available; status tolerates timestamp inversions with explicit
   diagnostics. For anomalous timing, including observation before latest event,
   report all four duration metrics and journal-derived row elapsed values as
   null/unknown, preserving event counts and task/slot state. Display-only
   `journal_timing` has `reliable`, `backwards`, `observation_before_latest`; ordered
   histories retain numbers. Never sort/rewrite/clamp history or fabricate zeroes.
3. Fleet JSON/shared CLI/TUI derive display-only `observation`: verified
   `runner_alive`, `health_written_at`, `snapshot_at`, `snapshot_age_seconds`,
   `task_state` (current/stale/unavailable/unknown), `error` (string/null); keep `job`
   separately verified. Reuse freshness/failure-grace rules, not a new timer/uptime.
   A live runner/fresh health write may mean cycling, not reconciled task state.
   Never derive current worker counts from stale rows. Keep canonical inventory
   independently available. Failed observations say task state unavailable, not
   Queue empty; a successfully empty observation retains ordinary idle behavior.
   Legacy missing provenance stays unknown and malformed bytes remain intact.

These concerns may be implemented independently with real source/test overlap and
serialized integration; no fabricated dependency or promised simultaneous admission.

### Verification, pre-mortem and handoff

Use focused failing regressions on the actual implementation baseline, disposable
repositories/fake collectors and affected checks; normal final gates and independent
review remain. No fabricated performance baseline or new numeric target. Cover
field-specific nulls plus corruption, append-order/state plus unknown timing, and
failed/stale reads with live/dead jobs and a nonempty cached snapshot in idle logging.

Offline completion is not installed adoption or live recovery. Later live verification
needs its own authorized Autowork scope and cannot operate another project's runner.
Existing goals, ownership, pending qualification and active contracts remain unchanged.

## Planning authority and shared protocol (2026-11-01)

Status: Accepted

`pi-autowork/src/pi_autowork/planning_authority.py` owns allowed paths, proposal size and secret
checks and generates the console prompt block. TaskStore's `planner_authority` owns
record schema/authority diffs: closure, owner attestations, holds, live authorization,
ownership, task status and goal status. Console policy and proposal validation call
these owners, not copies. Retain prose guards only for non-executable rules and test
machine rules at authority/CLI seams.

Plan With Me and Plan For Me adapt the single
[shared planning interface](../skills/shared/RESEARCH-PLAN.md#shared-planning-interface),
including sequence, rolling plans and task requirements. Plan For Me remains
decisive; Plan With Me interviews for consequential missing intent. Neither gains
execution, dispatch or publication authority. Routine delegated operating decisions
follow existing policy without another permission round; protected owner-only status
and authority decisions remain protected. No document cleanup marks an old goal met.

## Skill adherence and Definition of Done (2026-11-01)

Status: Accepted

High-risk skills use `## Common Rationalizations` and `## Red Flags`, retain one
`**Done when:**` line and link the shared
[Definition of Done](../skills/shared/DEFINITION-OF-DONE.md). It owns Kit-specific gates
and points to pinned Addy guidance for correctness, quality, integration, docs and
ship criteria; do not add another verification checklist/coordinator.

Apply the rule to Autowork, Plan For Me, Ponytail Review, Git Commit Push, Docs Sync
and Plan With Me, and to later high-risk skills through [skill standard](skill-standard.md)
and Writing for Agents. Shared operating behavior lives in
`skills/shared/COMMON-CONTRACT.md`, not a second meta-skill. Keep commands explicit,
Ask Kit the sole router, and lifecycle phases mapped to existing owners.

Structural/routing checks and `scripts/skill_trace_eval.py` provide layered evidence.
Checked-in Tier 3 traces under `evals/tier3/<skill>.json` are synthetic fixtures;
live traces stay outside Git and use the same grader. These checks create no queue,
command, automatic activation, live qualification or delivery authority.
