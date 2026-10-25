# Autowork Paseo plugin implementation plan

> **For agentic workers:** use executing-plans for inline execution; independent client work may be delegated into an isolated `.worktrees/` checkout. Owner explicitly authorizes autonomous execution, so do not request duplicate design/plan approval.

**Goal:** Deliver an installable native control/observation plugin with tested authority boundaries.
**Architecture:** Paseo host-bound client RPC -> bounded local Autowork adapter, no new service or engine.
**Tech stack:** official scaffold, Paseo SDK 0.13.0, React Native, Zod, TypeScript, Node subprocess API, Vitest.
**Spec:** [design.md](design.md).

## Global constraints

Read-only by default; no daemon installation/reload, actual model calls, real runner operations, secret/config changes or remote publication. Only daemon-side allowlisted subprocesses; native client with no DOM/Node imports. Runtime compatibility and source/evidence identity must be explicit. Preserve all existing Autowork state.

## Review focus

1. Host switch while a request or confirmation is pending: reject old instance/tickets; query caches remain host-scoped.
2. Repository is replaced or disappears after discovery: revalidate canonical root/common-dir identity before dispatch.
3. Timed-out accepted mutation or disconnected planning child: retain uncertain outcome; never replay automatically.
4. Multiple clients refresh/click concurrently: cache requests and serialize bounded operations; consume tickets first.
5. Plugin cleanup during a planning turn: cancel only the owned CLI process; preserve upstream histories and refuse unknown sessions after restart.

## Tasks and interfaces

### 1. Typed contracts and compatibility skeleton
- [x] Define shared fleet/task/detail/settings-free policy, operation, planning schemas and named RPC contracts in `shared/contracts.ts`.
- [x] Keep root entries runtime-separated; strict generated tsconfig; pin SDK/CLI compatibility.
- [x] Add tests for contribution IDs, schemas and package manifest. Run `npm test -- tests/contracts.test.ts`; observe RED before implementation and GREEN after.
- [x] Commit the connected skeleton/design and record official scaffold provenance.

### 2. Bounded read-only adapter
Files: `server/process.ts`, `server/autowork-client.ts`, `server/discovery.ts`, `server/config.ts`, `tests/server.test.ts`.
Consumes shared schemas. Produces `AutoworkClient` and `AutoworkService` methods fleet(), tasks(repoId), task(repoId,id), logs(repoId), close().
- [x] Write fake-command and disposable-Git tests: argv injection remains literal; unknown/symlink/replaced paths refused; invalid JSON/nonzero/oversize/timeout fail explicitly; one collector serves concurrent refreshes and invalidates after errors.
- [x] Implement fixed executable resolution, capabilities handshake, exact known-repo discovery, pinned task reads and canonical fleet projection.
- [x] Execute `npm test -- tests/server.test.ts` and typecheck; keep missing transport/delivery unknown.

### 3. Native surfaces
Files: `index.client.tsx`, `client/`, `tests/client.test.tsx`.
Consumes shared RPC contracts and host-aware SDK props. Produces native fleet, runner, tasks, blockers and planning views plus workspace/agent panels and command/slash registrations.
- [x] Test host-keyed query/cache behavior, offline failure, task/closure rendering, owner-question-only answer action and confirmation flow with a native test renderer.
- [x] Implement theme-token styles, accessibility, adaptive layouts, refresh, expansion and loading/error/cached states.
- [x] Keep queries disabled offline/background; no unsolicited planning or control dispatch.
- [x] Run typecheck and client/contribution tests.

### 4. Confirmed operations and owned planning
Files: `server/operations.ts`, `server/planning.ts`, `server/planning-bridge.ts`, `tests/operations.test.ts`, `tests/planning.test.ts`.
Consumes `AutoworkService` and fixed action schemas. Produces prepare(input), commit(ticket), planning start/read/send/preview/apply/cancel and close().
- [x] Test read-only policy, stale generations/revisions/repo identities, consumed-ticket replay, per-repo serialization and uncertainty after timeout.
- [x] Implement operator-only configuration, single-use bound confirmations, canonical owner decisions and existing service CLI argv.
- [x] Test plugin-owned session registration, bounded progress, reconnection handle reuse, no automatic Apply/Start, exact preview revision and cleanup limited to owned subprocesses.
- [x] Implement existing planning CLI supervision; fail closed for unsupported live steering rather than invent an API.
- [x] Run security/operation/planning tests and typecheck.

### 5. Real compiler/load verification and packaging
Files: `tests/plugin-load.test.ts`, `docs/qualification.md`, `README.md`, `OVERVIEW.md`, `docs/security.md`, `docs/follow-ups.md`.
- [x] Compile both runtime bundles with the official pinned Paseo compiler; validate manifest and load/unload the actual server entry in an isolated plugin runtime, no user daemon.
- [x] Run all project tests, `npm run typecheck`, package dry-run/content audit and `git diff --check`.
- [x] Independently review security/ownership/cleanup before closeout and fix actionable findings with regression tests.
- [x] Document install/configuration/upgrade/removal, exact supported versions, actual test evidence and pending Android/Linux live qualification. Do not publish or install into existing services.

## Progress / rulings

- Design approved for autonomous implementation by the mission itself; local repo scaffolding is authorized, not live plugin activation.
- Implementation ruling: CLI progress is not a structured steering protocol; use the selected upstream Planner/PlanningHub through a bounded owned stdio bridge instead. No alternate prompts/engine or upstream session adoption.
- Safety ruling: upstream `--worktree` reads can recover interrupted transactions, so read-only RPCs inspect committed records; mutations use --expect against the displayed record hash.
- Review repair: uncertain planning observations retain their repository reservation and can be reconciled/cancelled; only authoritative settlement releases ownership. Prepared confirmations display the exact frozen text payload.
- Paseo public RPC handler lacks end-user principal: enforce daemon.manage plus server-operator policy; do not invent per-user access control.
- Existing Autowork blockers command invokes an agent: observation must use fleet's canonical blocker/question data instead.
