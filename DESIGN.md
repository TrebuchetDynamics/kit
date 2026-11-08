# Design

## Source of truth

Status: Active. Updated: 2026-11-07. Surface: the Python Autowork terminal UI.
The runtime and task contracts in `docs/plans/tui-responsiveness.md` take precedence
over presentation choices. This brief covers the fleet, action menu, provider/model
picker, and repository browser. It does not redesign the Paseo plugin or Rust UI.

Evidence: `src/pi_autowork/tui.py`, `tui_reads.py`, `pi-autowork/README.md`, and
the fixture pilots in `pi-autowork/tests/test_tui_*.py` and `tui_pilot.py`.
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

The fleet remains a full-width stack: commands, model, runners, selected summary,
worker observations, and activity. Details holds long diagnostics. The More menu
exposes secondary actions and shortcuts; direct keys remain available. Ctrl+P
opens Textual's searchable command palette with fleet actions, Pi model controls,
and the built-in theme switcher, scoped to the active screen and access mode.
Model selection follows provider → search → model → existing change/start confirmation.
Login opens Pi against the same agent directory and refreshes the model catalog on return.
Browse exposes the current path, Parent/Home, folder navigation, and readiness.
Escape returns from a secondary screen; opening a menu changes no runner state.

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
At 80×24 preserve the stacked hierarchy; at 150×45 show wider columns and more rows.
Resize uses cached observations and performs no filesystem or service acquisition.

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
