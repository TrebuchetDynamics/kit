# Qualification record

## Mobile shell simplification (2026-11-05)

The Paseo client now wraps the six view tabs instead of hiding them in a horizontal scroll row. Repository views replace the repository scroll row with a **Switch repository** sheet that lists every matching repository with its state and counts; search appears when more than six match. Fleet rows keep **Open** and **Answer** and no longer hide Tasks and Planning behind **More**. Each confirmation names the prepared action's consequence in one sentence and keeps the frozen summary, 60-second expiry, single-use/no-retry warning and effective push state. `npm run check` passed: **122 tests across 7 test files** plus both strict TypeScript configurations. Three new Node-renderer tests pin the 12-repository picker and 48px option targets, the pause and owner-answer confirmation text, and the Fleet row action set.

Not performed: a fresh physical 0.15.0 Android or desktop pass. The 360dp wrapping, sheet gestures, keyboard behavior and real touch targets remain live checks under [follow-ups](follow-ups.md) item 4.

## Task-detail simplification (2026-11-05)

The owner's mobile critique showed a task sheet that contradicted the queue (OPEN in detail, BLOCKED in the list), refused to answer with “No answer action: this is not a current canonical owner question…”, filled evidence headers with accent green, dumped the selection payload as JSON and exposed every edit verb at once. `npm run check` passed: **119 tests across 7 test files** plus both strict TypeScript configurations. The queue row and the sheet now derive one state (`taskState`): owner question, then blocker, then record status, so a blocked task opened from Blockers keeps the BLOCKED pill and explains in plain words that no owner question is recorded. The redundant “Close details” button is gone because the host sheet owns dismissal; section metadata is labelled instead of reading as status. Disclosure headers are neutral chips with an icon, never accent-filled actions; “Contract and evidence” leads with the contract, notes sit behind “Task notes”, and the selection explanation renders as facts (`Eligible now`, reasons, closure provenance and time) with the raw payload behind a nested disclosure. “Edit task” asks which change to make — Placement, Hold, Close task, Supersede or Fields — and shows only that form. `relativeTime` also reads ISO timestamps.

Not performed: a fresh physical 0.15.0 Android or desktop pass with this client bundle. The critique's screenshots remain the owner's baseline.

## Paseo 0.15 app compatibility (2026-11-03)

The connected Android app reported **0.15.0** while the local daemon/CLI was **0.14.0**. The previous manifest range `>=0.13.0 <0.15.0` made the app's plugin card fail with `Plugin "paseo-autowork" requires Paseo >=0.13.0 <0.15.0. Your app is 0.15.0.` The 0.15.0 plugin SDK/server suite passes (**109 tests**, both TypeScript configurations), the plugin reloaded on the 0.14.0 daemon, and a live fleet read returned 11 repositories. The manifest is now `>=0.13.0 <0.16.0`; 0.16 remains untested. The app must reconnect or refresh the Plugin settings after the manifest change.

Not performed: a physical interaction pass on the 0.15.0 app after the manifest fix.

## Five-second follow-up (2026-11-03)

The owner's second critique identified the remaining low-hanging failures. `npm run check` passed: **114 tests across 7 test files** plus both strict TypeScript configurations. New Node-renderer tests pin the actual owner question as the decision headline, completed blocked work hidden until requested, completed tasks never labelled “blocked by DONE”, the request-limit failure reduced to one sentence with Retry and cached context, Controls before explanatory status, and maintenance hints. The decision headline extracts the text after `Question:`; the blocked queue defaults to actionable tasks with a completed toggle; the task closure line carries provenance only because the badge already shows the label; the planning options collapse so Start planning stays above the fold; the task detail opens in the host sheet, with notes buried inside Contract and evidence; blocked tasks show a BLOCKED pill and read blocker codes such as NEEDS_DECISION as words; +working renders as “working tree”; “Remove service” and “Update all runners” replace the ambiguous danger labels; the destructive restart mode is red and warns that interrupting merges can leave an integration incomplete; cached controls explain why they are disabled. An Impeccable polish pass then removed the colored left-stripe notices (full semantic border and icon instead), removed the nested task cards in favor of list rows, and stopped repeating “Autowork” as both the native title and the screen heading. The mechanical detector returned `[]`. The manifest was already widened to `>=0.13.0 <0.16.0`; the app card still needs its own refresh/reconnect.

Not performed: a fresh physical 0.15.0 app pass with the new client bundle. The screenshots remain the owner's baseline.

## Five-second surface (2026-11-03)

The client was reworked against a mobile critique (debug console rendered as an app: green *NOT RUNNING*, repeated unknown fields, raw hashes and Markdown, undifferentiated destructive controls, content under the navigation bar). `npm run check` passed: **109 tests across 7 test files** plus both strict TypeScript configurations. Seven new Node-renderer tests pin the semantic tone mapping, the one-banner-plus-single-blocker fleet, urgency ordering, the typed confirmation for Remove and Update, the decision card with rendered Markdown and Answer above the fold, completed work hidden behind one toggle with queue counts and a short revision, grouped health facts with relative times, and the bottom clearance. The daemon reloaded the plugin from the kit checkout after the change.

Not performed: Android or Linux Desktop visual interaction with the redesigned screens. The critique's screenshots are the owner's acceptance baseline; the next owner pass should confirm the five-second test on a 360dp phone and that the floating host control no longer covers the header.

## Management surface (2026-11-02)

`npm run check` passed: **102 tests across 7 test files**, plus both strict TypeScript configurations, after the plugin moved into the kit repository (`integrations/paseo/`) and gained every task verb, the tasks-only commit, every runner control and maintenance verb, planning modes, the goal/status/scorecard/models/store reads, the default policy file, the Settings screen and the long-poll change watch. New offline tests cover the server-authored argv for each action kind (flag values that start with `-`, `--` before positionals, stdin JSON for records), separate refusal per grant kind, refusal of a verb the installed release lacks, working-tree reads only under the `tasks` grant, the default policy path with its private-file rule, and a watch that answers after a task record changes.

A server-side exercise against the **live** fleet on this host (Autowork release `edb31eb1` from the kit checkout, Paseo 0.14.0 daemon, policy `~/.config/paseo-autowork/policy.json` with `all: true`) read 11 repositories including the kit checkout added through `repositories`, 227 working-tree task records and 27 goals for kit, an empty pending-edit set, a selection explanation, the runner status text, 342 models, a one-day scorecard with one missing-repository error row, and a 32-character watch digest. No mutation was dispatched. `paseo plugin reload` on the daemon reloaded the plugin from the kit path and logged `Plugin ready`.

Not performed through the app: Android or Linux Desktop visual interaction with the new cards, an authorized runner control, a task edit, a commit or a planning start from the UI, and the change watch's effect on a mounted screen. These remain pending live acceptance by the owner on the desktop app.

## Initial read-only build

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

> The plugin id and display name are now `kit-autowork`; earlier text in this record says
> `paseo-autowork` because that was the id at the time. The policy path follows each
> rename and still reads the earlier names while the current file is absent.
