# Ranked follow-ups

Offline implementation and live qualification are separate. No pending item grants execution authority.

## 1. Qualify Android and Linux Desktop against one owned development daemon

**Value:** highest; **dependency:** access to the actual Android/Desktop clients. Local Paseo 0.14.0 installation, load, reload and read-only fleet/tasks RPC are recorded in [qualification](qualification.md); physical clients remain untested. Installing into another existing user daemon still needs explicit permission.

Acceptance: record exact app/daemon versions; native navigation and touch targets; real host selection/offline behavior; background/foreground and reconnect without operation replay; long task/log expansion; normal read-only fleet/task/blocker use; plugin disable/reload/removal with no orphaned owned children. Keep existing user daemons/services untouched. Node renderer and compiler evidence do not close this item.

## 2. Qualify real planning and opt-in controls on a disposable repository

**Dependency:** item 1, explicit target/operator window and bounded model/time budget; no production credentials or remotes.

Acceptance: empty-objective upstream `/plan_for_me`, progress/follow-up/steer/cancel, exact reviewed Apply, stale revision refusal, interrupted/reconnected client with no duplicate operations, service start/pause/resume/stop/default restart and unchanged publication/live policy. Verify actual engine activity separately from command exit. Do not run this during an offline build.

## 3. Expose richer authoritative runtime and delivery provenance

**Value:** medium; the runner view now shows the observation, maintainer, fallback and max-workers fields from `ls --json`, but the CLI still omits some source/provenance details available in Autowork's native view. Transport, actual runtime release, last verified delivery, full historical attempts and structured receipt commit chains remain explicitly unknown/not available when absent from the CLI response.

Acceptance: add or consume a small versioned upstream read API for those existing facts, including actual process identity/freshness; no second health classifier, new event database, copied private state parser or inferred delivery. Keep configured/source release separate from executed release, and manual closure separate from receipt-valid verified closure.

## 4. Mobile scale and presentation qualification

**Value:** medium; **dependency:** measured physical-device behavior from item 1.

Acceptance: representative large queues/logs, virtualized task rows or bounded pagination if needed, physical-device validation of goal grouping and Done/Held runtime filters, narrow-layout one-handed navigation, long-input/keyboard behavior, accessibility screen-reader traversal and measured network/battery impact. Current UI has a compact fleet dashboard, horizontal repository picker, per-runner action bar, human-readable evidence, repository/task/goal/section/runtime filtering, result counts, resettable filters, 25-row task summary pages and expandable details (see [pattern study](plugin-patterns.md)). The Node render contract checks the compact layout and 48px targets; this bounds rendered task summaries, not snapshot transfer size or owner-question rows, and does not claim measured large-queue mobile performance.

## 5. Publication and compatibility maintenance

**Dependency:** qualification evidence and explicit remote publication authority.

Acceptance: the source now lives in the public kit repository under `integrations/paseo/`; a registry entry still needs real approved interface screenshots/registry media, a reviewed artifact with reproducible package contents, and a test of each newer Paseo minor before widening the manifest range. Paseo 0.14.0 is tested and the range is `>=0.13.0 <0.15.0`; 0.15 remains untested. No registry entry was created by this build.

## 6. Reconcile retained planning sessions across plugin generations

**Value:** medium, after ordinary lifecycle qualification. Current reload behavior deliberately fails closed rather than adopting an active foreign session.

Acceptance: a source-backed explicit ownership-transfer/retained-session reconciliation flow through existing Autowork APIs, with process birth identity and uncertainty handling. Do not merely import session IDs from disk or steer another system's Pi process.

## 7. Replace the long-poll change watch with daemon subscriptions

**Value:** medium; **dependency:** a Paseo release that ships plugin subscriptions (`defineSubscription`/`useSubscription`, absent from the 0.14 SDK) and a tested manifest range that includes it.

Acceptance: one shared daemon watcher pushes change events to every mounted surface; the `autowork.watch` RPC and its one-second client pacing are removed; reconnect and plugin reload resubscribe without replaying operations. Keep the 20-second polling fallback for older hosts.

## 8. Per-workspace header button for pending decisions

**Value:** low; the sidebar row already shows the host total.

Acceptance: a header button per workspace whose label is that repository's pending-decision count, registered and updated from an owned workspace-list observation and removed on cleanup; no extra RPC per workspace beyond the shared fleet read.
