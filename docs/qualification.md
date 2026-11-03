# Qualification record

## Offline build result

`npm run check` passed: **91 tests across 7 test files**, plus both strict TypeScript configurations. Client code typechecks without DOM or Node globals. `git diff --check` passed. The packed source archive was audited to exclude node_modules, Git/worktrees, runtime artifacts, environment files, logs and session histories.

Versions inspected/tested:

- Official Paseo source: `72e3316f4f5dfe775c77dbf998968c92e2de9019` (0.13.0) and `d34d17a9072149320ace35ec2a2e5c7dcd992cb3` (0.14.0 npm gitHead).
- Official plugin SDK and isolated server compiler/runtime: **0.14.0**. The same suite passed on **0.13.0**. Manifest support is `>=0.13.0 <0.15.0`.
- Generated React **19.1.0**, React Native **0.81.5**; Node **24.19.0** on the development Linux host.
- Live local Autowork read-only capabilities: release **84f63bb6a70208a1b5d95adfc0ae81b465d42086**, prepare API **4**. The live fleet RPC returned **10 repositories** and the tasks RPC returned a **54-task** inventory for `fecim-lattice-tools` at revision `7c9960e54149a2e7b5a12cbc565167f0ea87a4d0`. One configured repository was reported unavailable. No raw private histories or prompts are copied here.

The official CLI scaffold command ran with an isolated PASEO_HOME. The original build found no `paseo` executable on PATH; the current host runs Paseo **0.14.0** and its local daemon. Installing development dependencies and running a temporary in-process runtime are not physical-client qualification.

## Real compiler and server load

`tests/plugin-load.test.ts` uses the pinned official **0.14.0** compiler, manifest reader and PluginRuntime from the dev-only `@getpaseo/server` package. It compiles both actual entries with Paseo's runtime/import boundary checks, starts the actual plugin server child against a disposable fake session host and fake Autowork executable, serves a fleet RPC, refuses mutation in read-only mode, rejects invalid input, unloads, reloads and rejects the previous generation. No user daemon, listener, real runner or provider is involved.

This proves plugin source compilation and isolated daemon-side registration/lifetime. The live section below also proves local daemon transport authentication. It does **not** prove actual Android/desktop visual rendering or a real planning/model turn.

## Live local daemon load and read-only RPC

On Paseo **0.14.0**, `paseo plugin install <the plugin checkout>` reported the plugin `enabled: true` and `status: running`. Plugin logs recorded `Loading plugin`, `Plugin ready`, and registration of `autowork.commit`, `autowork.fleet`, `autowork.logs`, `autowork.operation`, `autowork.planning`, `autowork.prepare`, `autowork.task` and `autowork.tasks`. `paseo plugin reload` stopped and restarted it cleanly. The runtime emitted one Node `DEP0129` deprecation warning; it did not fail loading.

A direct host-bound RPC exercise returned the live fleet (10 repositories, release `84f63bb6`, prepare API 4), a 54-task inventory for one repository, and a task detail. `autowork.prepare` for a `pause` control was refused with `Read-only: this runner operation is not allowed by the host operator`. During qualification the installed Autowork release advanced from `80b0b82f` to `84f63bb6`; the first fleet request failed closed with `Autowork source release changed; reload and requalify before another operation`, and `paseo plugin reload` restored read-only access. That fail-closed boundary is intentional. This proves the installed daemon load, plugin lifecycle, real Autowork fleet/tasks read and default-deny mutation boundary. It does not prove client rendering, an authenticated non-owner denial, planning/model execution or an authorized runner control.

The live fleet read also exposed Autowork's nullable runner counts. The wire contract initially rejected `running`/`waiting`/`stopped: null`; the server and shared contract now normalize null counts to zero, with a regression test. This was found by the live test, not by the fake fixtures.

## Test matrix

| Requirement | Evidence / boundary |
| --- | --- |
| Manifest/load and typechecking | 0.13/0.14 compiler and isolated runtime tests, both TypeScript configs and a live 0.14.0 daemon load pass |
| Desktop/Android appearance | Native-component fixtures and compiler pass; physical clients **pending** |
| Real structured fleet/tasks | Live local-daemon RPC returned 10 repositories and a 54-task inventory; no mutation/model invocation |
| Offline or wrong host | Native tests disable calls and never fall back to another host |
| Repository disappears/replaced | Identity tests reject stale/missing/symlinked targets |
| Historical in-flight records | Canonical paused/stalled facts retained; no liveness inferred by plugin |
| Owner vs technical/deferred work | Only existing canonical owner questions on open tasks expose Answer; details preserve recorded notes; no new health/deferral parser |
| Read-only cannot mutate | Live daemon refused a `pause` prepare; isolated RPC also refuses grants; transactional --worktree reads are explicitly refused |
| Shell/path injection | Literal argv test, positional `--` owner-answer test, exact known Git roots and opaque IDs |
| Time/output/invalid JSON | Deadlines, pool limits, UTF-8 chunking, output limits and explicit parse/exit errors tested |
| Multi-host cache isolation/reconnect | Host/generation query keys, connectivity epochs, late response rejection and no automatic commit replay tested |
| Task source/evidence identity | Source revision, contract hash, record hash, manual/verified/missing evidence labels tested |
| Planning unaccepted before Apply | Existing controller adapter and operation tests retain proposals; exact valid preview revision required |
| Apply/current authority | Autowork controller remains the mutation authority; generation/identity/record/service policy rechecked |
| No worker ownership theft | Read paths expose no worker controls; planning bridge rejects unowned/other-repository sessions |
| Incompatible installation | Explicit prepare-API mismatch and executable/release-change refusal tests |
| Disable/reload cleanup | Live reload stopped and restarted the plugin; finite command teardown, owned bridge lifecycle and isolated runtime stop/reload tests pass |
| Runner/publication/live policy | Default-deny operator grants, explicit confirmations, fixed service argv and no privilege-field/force/push endpoint |

## Independent review and repairs

A separate fresh-context reviewer inspected the implementation and reproduced one Important ownership defect: a transient planning-state read failure released the repository reservation while the turn could remain active. The repair retains uncertain reservations, permits explicit reconciliation/cancellation and releases only after authoritative settlement. A new regression failed before the repair and passes after it; UI regression also verifies uncertainty cannot start a duplicate turn and remains explicitly reconcilable.

The review also identified a confirmation-intent ambiguity when drafts change after preparation. The server now includes the exact frozen prepared answer/objective/follow-up/steering text in the confirmation; later draft edits cannot silently alter it. The literal-answer payload regression failed before and passes after this change.

The client implementation child timed out before committing its last two regressions. Its process was verified terminal; the parent adopted the preserved checkout, reproduced/fixed objective-navigation and repository-error action guards, ran its tests, and committed it. No claimed child completion was treated as proof.

## Explicit pending live acceptance

Performed on the local 0.14.0 daemon: installation, enable, load, reload, live fleet/tasks read and a refused read-only mutation. Not performed: real authenticated user/permission denial, Android or Linux Desktop visual interaction, remote host pairing, real provider/model planning, an authorized runner control, fleet runtime activation, battery measurements or remote publication.

These require the bounded permissions/targets in [follow-ups](follow-ups.md). The implementation must not be described as Android-qualified or production/fleet-qualified from the live read-only result. Missing actual transport/runtime release/last-delivery or full historical-attempt/receipt-chain data remains unknown until an authoritative upstream read contract supplies it.
