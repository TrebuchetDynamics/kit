# Qualification record

## Offline build result

`npm run check` passed: **76 tests across 7 test files**, plus both strict TypeScript configurations. Client code typechecks without DOM or Node globals. `git diff --check` passed. The packed source archive was audited to exclude node_modules, Git/worktrees, runtime artifacts, environment files, logs and session histories.

Versions inspected/tested:

- Official Paseo source: `72e3316f4f5dfe775c77dbf998968c92e2de9019`.
- Official generated scaffold, plugin SDK and isolated server compiler/runtime: **0.13.0**. Manifest support is `>=0.13.0 <0.14.0`.
- Generated React **19.1.0**, React Native **0.81.5**; Node **24.19.0** on the development Linux host.
- Existing installed Autowork read-only capabilities: release **01e37ea049c3153948ebfbbdb54aff38fe749266**, prepare API **4**. Read-only integration returned **7 repositories/runners**, a **161-task** inventory and a task detail with source revision/contract hash. No raw repository identities, fleet inventory, prompts or private histories are copied here.

The official CLI scaffold command ran with an isolated PASEO_HOME. No pre-existing `paseo` executable was found on PATH; no existing daemon or installed Android app version was established. Installing development dependencies and running a temporary in-process runtime are not installed-daemon or physical-client qualification.

## Real compiler and server load

`tests/plugin-load.test.ts` uses the pinned official compiler, manifest reader and PluginRuntime from the dev-only `@getpaseo/server` package. It compiles both actual entries with Paseo's runtime/import boundary checks, starts the actual plugin server child against a disposable fake session host and fake Autowork executable, serves a fleet RPC, refuses mutation in read-only mode, rejects invalid input, unloads, reloads and rejects the previous generation. No user daemon, listener, real runner or provider is involved.

This proves plugin source compilation and isolated daemon-side registration/lifetime. It does **not** prove actual Android/desktop visual rendering, transport authentication or a real planning/model turn.

## Test matrix

| Requirement | Evidence / boundary |
| --- | --- |
| Manifest/load and typechecking | Official compiler/isolated runtime tests and both TypeScript configs pass |
| Desktop/Android appearance | Native-component fixtures and compiler pass; physical clients **pending** |
| Real structured fleet/tasks | Read-only installed Autowork integration passed; no mutation/model invocation |
| Offline or wrong host | Native tests disable calls and never fall back to another host |
| Repository disappears/replaced | Identity tests reject stale/missing/symlinked targets |
| Historical in-flight records | Canonical paused/stalled facts retained; no liveness inferred by plugin |
| Owner vs technical/deferred work | Only existing canonical owner questions on open tasks expose Answer; details preserve recorded notes; no new health/deferral parser |
| Read-only cannot mutate | Actual isolated plugin RPC refuses grants; transactional --worktree reads are explicitly refused |
| Shell/path injection | Literal argv test, positional `--` owner-answer test, exact known Git roots and opaque IDs |
| Time/output/invalid JSON | Deadlines, pool limits, UTF-8 chunking, output limits and explicit parse/exit errors tested |
| Multi-host cache isolation/reconnect | Host/generation query keys, connectivity epochs, late response rejection and no automatic commit replay tested |
| Task source/evidence identity | Source revision, contract hash, record hash, manual/verified/missing evidence labels tested |
| Planning unaccepted before Apply | Existing controller adapter and operation tests retain proposals; exact valid preview revision required |
| Apply/current authority | Autowork controller remains the mutation authority; generation/identity/record/service policy rechecked |
| No worker ownership theft | Read paths expose no worker controls; planning bridge rejects unowned/other-repository sessions |
| Incompatible installation | Explicit prepare-API mismatch and executable/release-change refusal tests |
| Disable/reload cleanup | Finite command teardown, owned bridge lifecycle and real isolated runtime stop/reload tests |
| Runner/publication/live policy | Default-deny operator grants, explicit confirmations, fixed service argv and no privilege-field/force/push endpoint |

## Independent review and repairs

A separate fresh-context reviewer inspected the implementation and reproduced one Important ownership defect: a transient planning-state read failure released the repository reservation while the turn could remain active. The repair retains uncertain reservations, permits explicit reconciliation/cancellation and releases only after authoritative settlement. A new regression failed before the repair and passes after it; UI regression also verifies uncertainty cannot start a duplicate turn and remains explicitly reconcilable.

The review also identified a confirmation-intent ambiguity when drafts change after preparation. The server now includes the exact frozen prepared answer/objective/follow-up/steering text in the confirmation; later draft edits cannot silently alter it. The literal-answer payload regression failed before and passes after this change.

The client implementation child timed out before committing its last two regressions. Its process was verified terminal; the parent adopted the preserved checkout, reproduced/fixed objective-navigation and repository-error action guards, ran its tests, and committed it. No claimed child completion was treated as proof.

## Explicit pending live acceptance

Not performed: installation/enable/reload on an existing daemon, real authenticated user/permission denial, Android or Linux Desktop app interaction, remote host pairing, real provider/model planning, actual runner controls, fleet runtime activation, battery measurements or remote publication.

These require the bounded permissions/targets in [follow-ups](follow-ups.md). The implementation must not be described as Android-qualified or production/fleet-qualified from these offline results. Missing actual transport/runtime release/last-delivery or full historical-attempt/receipt-chain data remains unknown until an authoritative upstream read contract supplies it.
