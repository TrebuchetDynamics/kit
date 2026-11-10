# Design

## Source of truth

Status: Active. Updated: 2026-11-07. Surface: the Python Autowork terminal UI.
The runtime and task contracts in `docs/plans/tui-responsiveness.md` take precedence
over presentation choices. This brief covers the fleet, action menu, provider/model
picker, and repository browser. It does not redesign the Paseo plugin or Rust UI.

Evidence: `pi-autowork/src/pi_autowork/tui.py`, `tui_reads.py`,
`pi-autowork/README.md`, and the fixture pilots in `pi-autowork/tests/runner/`,
including the bounded `tui_operations_pilot.py`.
Existing terminal captures show crowded commands and weak section separation.

## Brand

A calm operations console: precise, readable, and direct. Trust comes from visible
state, provenance, and guarded actions. Avoid decorative dashboards, animation,
color-only status, and optimistic interpretations of missing observations.

## Product goals

Make the selected runner, its next useful action, and its activity easy to find.
Support provider/model selection and directory navigation without memorized commands.
Reduce redundant widget updates without delaying fresh acquisition.
Success means keyboard completion at 60×18, readable wide layouts, stable selection,
and operation-count evidence for less repaint work.

Non-goals: changing scheduling, task authority, credentials, service admission,
approval boundaries, or the four-reader acquisition coordinator.

## Personas and jobs

Repository owners inspect work, answer questions, choose models, and start runners.
Operators inspect several runners and need exact diagnostics when something fails.
Read-only viewers inspect the same evidence without execution controls.
Terminals may be small, remote, keyboard-only, or configured for native text copying.

## Information architecture

The fleet uses an adaptive workspace. Below 130 columns or 26 rows it remains
a vertical stack. At 130×26 and above, a 42-column project/context pane sits beside
the current-work and activity pane. Keep widget identities and action dispatch
unchanged across both arrangements; resize reflows cached observations only.
A fixed one-row footer exposes 1 Projects, 2 Work, 3 Activity, Help and Quit.
Numbers move focus only on the fleet screen; they never intercept child prompts.
The h Guide explains Model → Project → Tasks → Execution → Checks → Local merge,
what waiting/attention/unconfirmed mean, and that publishing is separate. Task
progress labels derive from verified counts and freshness, not merely a running
service or background maintenance. A service with zero active tasks must never be
presented as task execution in progress. Keep the raw process state in Details.
Panel borders and an accent border on focus establish grouping without relying
on color alone. This takes navigation cues from
[Lazygit](https://github.com/jesseduffield/lazygit) and restrained hierarchy from
[Glow](https://github.com/charmbracelet/glow), using existing Textual components. Number the three navigation regions: Projects,
Current work and Recent activity. The project table keeps only Project/Status/Tasks
at every width. The selected summary separates the next useful action from task
counts; omit zero-error/freshness boilerplate when observations are healthy. Keep
resource waits visible. Worker rows retain task/state/activity, with unjoined
observations labelled Unconfirmed. Attempts, elapsed/quiet time and all original
source status text remain in scrollable Details. The fleet menu shows the useful Next action,
Log, Tasks, Details and More, without duplicates. More exposes secondary actions
and shortcuts at every size; direct keys remain available. Details holds complete
task names/IDs, phases and wait reasons, source errors and grouped notes (including
all original observations), and main-check revisions with original start age. Ctrl+P
opens Textual's searchable command palette with fleet actions, Pi model controls,
and the built-in theme switcher, scoped to the active screen and access mode.
Model selection follows provider → search → model → existing change/start confirmation.
Configure provider hosts Pi SDK OAuth/API-key interaction inside the TUI, including
masked answers, explicit Browser action, progress/errors and Escape cancellation.
Providers remain selectable with an empty authenticated model catalog. Pi persists
credentials in the captured runner/session profile; successful setup refreshes models.
A changed profile/runner or read-only mode cancels setup and rejects stale callbacks.
Opening the picker changes no credential state and launches no login or browser.
Browse exposes the current path, Parent/Home, folder navigation, and readiness.
Escape returns from a secondary screen; opening a menu changes no runner state.
Activity shows a journal summary. Full-screen Log defaults to Summary and labels
its local **v Raw / v Summary** control. Raw exposes every original line in the
captured excerpt, including startup settings and suppressed pending lines. It does
not promise all historical logs. The dashboard alone groups consecutive memory
waits with identical task/reason context and required memory into one range:
latest/minimum/maximum available MB, update count and original first/last stamps.
Different task contexts, thresholds, failures and intervening events break groups.
Full-screen Summary and Raw retain the original individual memory samples. Keyboard and menu clicks use the same screen-local
action; Escape/q returns. Adjacent identical recognized events fold with a count
and original first/last timestamps. Changed failure details, task/revision/target
identity and unknown multiline diagnostics remain ordered. Missing outcomes stay
unknown: integration, closure, timeout and historical green checks prove neither
remote publication nor acceptance of current main.
Tasks is the fleet's task-management entry. Its numbered views use bracketed
counts and clickable labels. The table separates short state labels from activity
or wait reasons, reserving reason space at normal widths. Compact tables retain
state and put full reasons in selected details/Info. Short queues place details
immediately after their rows, without a large empty gap; activity is not labelled
as an owner next action. Task IDs remain in details and drive every action. Matched
worker rows use committed descriptive names, never titles as keys. Duplicate names
preserve exact repository/task
identity and selection across refresh/reorder. Unmatched lanes remain explicit source
observations and cannot increase active-task counts.

## Current work summary

The selected-project summary answers three questions: what is happening now,
what action was last observed, and whether the owner needs to act. Only fresh,
identity-matched lanes may supply current activity. Process liveness alone must
not claim implementation progress. Five minutes without an observed action is
labelled a quiet worker, not a failure or a confirmed hang. Other blocked tasks
remain separate from active work. Main checks and automatic publication are
shown independently; missing change evidence never becomes a zero-file claim.
Compact terminals retain the three-line provenance/check summary and Details route.
The Tasks view offers guarded Retry for held work through the supported CLI,
which enforces eligibility and preserves earlier attempts. Repeated overflow
points to the model picker rather than suggesting repeated service restarts.

The dashboard journal prefers the latest runner start found in its last-hour
window. Full Log retains earlier runs; if no start is captured, the dashboard
keeps the available window rather than guessing a session boundary.

## Design principles

Prioritize actions and evidence over decoration. Summaries disclose uncertainty.
Keep long paths and prose in scrollable views. Preserve the selected identity,
focus, and journal position across refresh. Treat read-only mode as an execution
boundary. Reuse existing command dispatch and confirmation flows.

## Visual language

Use Textual's existing theme tokens: surface for panels, panel for separators,
accent for navigation/focus. Retain literal state labels alongside activity/wait/
failure colors. Terminal typography stays monospaced; hierarchy uses bold headings,
muted supporting text, and labelled section rules. Avoid extra boxed cards and
spacer rows. No imagery, motion, custom fonts, or additional dependencies.

## Components

Reuse MenuBar, DataTable, Static, RichLog, PickModel, and BrowseScreen.
Keep the searchable ActionMenu and add Textual's built-in command palette for
cross-screen discovery without adding a package.
Label the existing runner, worker, and journal separators without adding rows.
Keep provider/model and browse controls in their established locations.
Shared text publication compares full Rich Text, including styles and click spans.

## Action navigation

Fleet and Tasks menus show explicit bracketed shortcuts beside each label,
with separators between actions. Model selection uses the same visible shortcut
convention. The fleet exposes More actions and, when there is room, Guide.
More actions keeps search and keyboard selection while adding a short description
under every option. Descriptions distinguish closing the interface from stopping
the service, and restarting a service from retrying a failed task. Descriptive
rows keep the existing action identity, confirmation and read-only guards.

## Accessibility

Keep all operations keyboard-accessible and focus visible. More lists readable
shortcut labels. Do not intercept text entry with root commands or let root actions
leak into child screens. Preserve mouse opt-in and native terminal selection.
Keep status text and diagnostics available independently of color. Test focus
return and contrast visually with the existing terminal theme; do not claim formal
assistive-technology qualification from fixture pilots.

## Responsive behavior

At heights below 22 rows or widths below 80 columns, use an action-first compact
menu. Short-height summaries use at most three rows and prioritize the main-check
result when present. Keep at least four journal rows and one selectable worker row.
At 60×18 and 80×24, bounded task/state cells keep the Details route visible for full
identity and reasons. Errors and source notes are separate counts, not a warning wall.
Unknown inventory is unavailable, never zero; superseded checks never qualify current main.
At 80×24 preserve the stacked hierarchy; at 150×45 use the two-pane workspace with bounded table widths.
Resize uses cached observations and performs no filesystem or service acquisition.
Log's mode toggle also uses cached text only, preserving scroll/follow behavior and
reader identity/epoch guards. Activity captures up to 400 lines from the last hour;
Log captures up to 1000 lines. Both retain the 20-second journal bound and shared
four-reader ownership. Failed reads show unavailable or stale last-good evidence
with acquisition errors, never successful empty output.

## Interaction states

Distinguish loading, valid empty, unavailable, and stale states. An empty fleet
uses a centered welcome panel with model choice and Browse steps; read-only views
explain their boundary without showing unavailable actions. Loading and discovery
failures keep their diagnostic view.
More/filter with no matches cannot dispatch an action. Provider/catalog failures
retain login guidance. Invalid directories preserve the previous location.
Action selection rechecks runner identity before dispatch; confirmations remain.

## Content voice

Use short, literal labels: Runners, Workers, Activity, Details, More, Provider,
Parent, Home. Explain what to do next. Avoid implementation jargon in primary
navigation. Keep complete technical evidence in Details and reports.

## Implementation constraints

Keep Python and pinned Textual 8.2.8. No framework migration or new dependencies.
Do not split screen ownership merely for appearance. Performance work follows:
lock unchanged/style-only publication with regressions, skip identical writes,
then replace repeated lane-name scans with one per-render count map. Recompute
presentation from every accepted snapshot; this is not a new data cache.
Verify focused pilots, existing blocked-reader tests, typecheck/source guards,
and rendered captures at compact and wide sizes. Use operation counts rather
than invented SSH latency or flaky wall-clock performance assertions.

## Open questions

No design-critical questions block this bounded redesign. Live SSH transport and
assistive-technology qualification remain separate from offline terminal evidence.
