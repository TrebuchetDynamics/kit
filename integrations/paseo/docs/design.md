# Autowork for Paseo: implementation brief

## Accepted mission and execution authority

The owner authorizes autonomous design, implementation and offline testing of a separate native Paseo plugin. No installation, enablement, daemon reload, production access, provider calls, publication or existing service change is authorized by this build. Existing Autowork workers, Pi sessions, task records and repositories remain untouched. Deliver working Fleet, Tasks and Blockers first, followed by staged planning and opt-in confirmed runner controls. Do not create another engine, scheduler, task store, Git integrator or network service.

## Verified compatibility

Official Paseo source inspected at `72e3316f4f5dfe775c77dbf998968c92e2de9019` (0.13.0) and `d34d17a9072149320ace35ec2a2e5c7dcd992cb3` (0.14.0 npm gitHead). The scaffold was generated with `@getpaseo/cli@0.13.0 plugin init` under an isolated PASEO_HOME. The 0.13 and 0.14 SDK/compiler/runtime suites both pass; a live Paseo 0.14.0 daemon load and read-only fleet/tasks RPC also passed. Manifest support is `>=0.13.0 <0.15.0`; a 0.15 release needs its own test before widening. Keep generated React 19.1.0/RN 0.81.5 and SDK-generated types, no DOM library.

Installed Autowork capabilities report prepare API 4 and source release `01e37ea049c3153948ebfbbdb54aff38fe749266`. Resolve the daemon-host executable and handshake dynamically; never assume the developer checkout is installed. `ls --json` delegates live classification to fleet_view. Tasks list/show emit JSON without an output --json flag. `blockers` starts an agent and MUST NOT be used for observation. The plugin displays canonical questions, roots, held records and accepted decision counts from fleet data, not its own health classifier. Missing transport/delivery evidence stays unknown.

## Architecture and alternatives

Chosen: native React Native client + installation-bound typed Paseo RPC + a bounded daemon-side CLI adapter. Alternative generic Paseo-agent prompting would duplicate planning ownership. Alternative HTTP service would add credentials, deployment and scheduler-like lifetime unnecessarily. Use native screens, workspace/agent panels, Command Center and four collision-resistant `aw-*` slash contributions. Paseo owns navigation and host selection; the plugin uses surface host identity and never routes plugin RPC to another host.

Shared Zod contracts are runtime-neutral. server/ owns local executable resolution, known repository discovery/realpath/Git-common-directory identity, bounded subprocesses, shared TTL/in-flight caches, operation reservations and planning CLI children. client/ owns presentation and query state, keyed by selected host. No polling while backgrounded/offline. Normal queries use bounded stale times, exponential error backoff and manual pull-to-refresh. A request must not silently switch hosts or return stale data as current authority.

## Authority and mutations

Paseo 0.13 and 0.14 plugin RPC dispatch require `daemon.manage` (`operation-permissions.ts`); the public handler context exposes only PaseoApi, NOT caller identity. Do not invent user-based permissions. All authenticated daemon managers share an operator-configured grant. Read-only is the default. Server-only operator configuration (not client-editable settings) names extra repositories, executable and allowed actions. UI confirmation is additional intent, not authorization. Do not deploy this model to mutually untrusted daemon managers.

Requests address opaque repository IDs derived from canonical root and Git-common-directory identity, never arbitrary executable/argv/path. Mutation preparation refreshes state and returns a short-lived, single-use ticket bound to plugin generation, repo identity, revision, action, payload and effective push policy. Commit consumes that ticket BEFORE dispatch, revalidates identity/state and never auto-replays ambiguous failures. Per-repository serialization and finite in-memory reservations prevent double taps/reconnect from duplicating actions; reload invalidates all tickets. Outcomes distinguish dispatched exit status from observed state; timed-out mutations remain uncertain, not successful.

Only allowlisted start/pause/resume/stop/restart/remove/update commands (restart with explicit stop-workers/now toggles), the model, clear-held and attention maintenance verbs, every `autowork tasks` verb and the tasks-only commit, each behind its own operator grant; no force, direct process killing, worktree mutation or publication grants. Existing effective push policy remains visible and unchanged. Owner answers use canonical `tasks decide` with the displayed committed record hash (uncommitted/concurrent changes are refused by --expect); no privileged typed fields are changed by answer prose. Only a current canonical owner question for an open task is answerable. Existing deferrals and technical holds are not new owner questions.

## Planning

Use the existing Autowork Planner/PlanningHub, including empty-objective discovery. The CLI cannot safely expose structured live steering/state, so a narrow supervised stdio Python bridge loads those exact controllers through the selected release's bootstrap. It is not a Paseo provider, new planning engine or attachment to Autowork workers. Return an operation handle immediately; expose bounded structured snapshots through polling only while the planning view is active. Register only newly created sessions in this plugin generation; follow-up/review/apply never adopt another system's sessions. Plugin reload retains upstream histories but refuses adoption/control of sessions whose ownership it cannot prove. No automatic resubmission on reconnect. Apply requires the exact preview revision plus an explicit consumed confirmation ticket and canonical controller validation. Planning completion never invokes runner Start. Cancel calls PlanningHub.cancel only for the registered owned session; steering calls its existing Planner.steer. Cleanup closes the owned bridge and, on deadline, signals only that direct child. It never signals runners or another system's sessions.

## Native presentation

A compact mobile dashboard using Paseo theme tokens, native typography and monospaced task IDs. The first screen is a fleet summary with repository cards, not a stack of full-width controls. A horizontal repository picker keeps the selected repository visible on narrow and wide layouts. Each runner has a navigation and action bar (Tasks, Blockers, Planning, Logs, and Prepare controls when granted), four compact count stats, key/value status, a one-line main-check summary and collapsible evidence/contracts. Read-only hosts show an explicit badge and the exact operator-policy reason; no client toggle grants authority. Evidence objects are formatted as human-readable fields, never dumped as raw JSON. Minimum 48px touch targets, accessible roles/labels and theme tokens are enforced by the Node render contract. Do not infer healthy progress from service liveness. Fleet/runner/task/planning/blocker views label capture time, cached observations, configured release versus observed runtime, manual versus verified closure and unavailable evidence.

## Validation and delivery boundaries

Test with disposable Git repositories and fake executable fixtures: allowlisted argv/literal shell metacharacters, symlinks/path replacement, bounded output/timeouts/concurrency, bad JSON/nonzero status, capability mismatch, stale/missing hosts, shared-cache invalidation, historical in-flight data, canonical owner/deferred distinction, revision-bound single-use confirmation, planning ownership/apply staging and disable cleanup. Compile with official pinned Paseo compiler and load the real server bundle through an isolated runtime harness; do not enable the user's daemon. Typecheck without DOM, validate package contents and native surface registration. Node render fixtures are not Android or desktop visual qualification.

Physical Android/Linux app connection, background/reconnect/battery/touch/clipboard behavior and actual model planning/service operations are pending explicit live qualification. Record these as bounded follow-ups rather than mark the combined product qualified.

## Official evidence

- https://paseo.sh/docs/plugins
- https://paseo.sh/docs/plugins/reference
- https://github.com/getpaseo/paseo/blob/72e3316f4f5dfe775c77dbf998968c92e2de9019/packages/cli/src/commands/plugin/scaffold.ts
- https://github.com/getpaseo/paseo/blob/72e3316f4f5dfe775c77dbf998968c92e2de9019/packages/plugin/src/server/contracts.ts
- https://github.com/getpaseo/paseo/blob/72e3316f4f5dfe775c77dbf998968c92e2de9019/packages/server/src/server/authorization/operation-permissions.ts
- Autowork: Src/pi_autowork/{command,task_commands,fleet_view,planning_commands,planning,planning_hub}.py, canonical sources inspected without modifying them.
