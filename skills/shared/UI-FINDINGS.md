# UI findings handoff

Impeccable and UI Taste use this reference for their default findings route, not
for an explicit design/edit request. It uses [Unslop's](../unslop/SKILL.md)
screen evidence and repeatable acceptance rules without invoking that skill or
changing its behavior.

1. **Scope and mode.** Use the named screen or flow, otherwise the relevant
   conversation findings, otherwise the main user-facing flow in the target repo.
   A bare invocation analyzes and publishes eligible outcomes in one pass through
   the [single-invocation specialist handoff](PLAN-HANDOFF.md#single-invocation-specialist-handoff),
   without selection, confirmation or a second command. Explicit design/edit
   requests keep the selected skill's playbooks and existing delivery gates; do
   not turn them into issue-only work or automatically publish extra findings.
   Explicit report-only, read-only, dry-run or no-write returns proposals inline
   with no writes, including GitHub, labels, documents and scratch files.
   Scheduled, cron or unattended runs audit only unless their accepted task scope
   explicitly authorizes the requested writes. No-dispatch permits authorized
   issue publication under `ai-planning`, not `ai-ready`. Preserve pauses and live
   ownership in every mode.
2. **Ground the finding.** Read the project's design decisions and the screen's
   user task. Record route, state, viewport and source for each finding; distinguish
   observed renders/interactions from behavior inferred from code. Reuse available
   sanitized capture evidence after checking its freshness against current source,
   fixture, viewport and state. A capture proves a render, not correctness. Missing
   evidence stays unknown: hold that finding with the missing input and resume
   condition (for example, a route or synthetic screenshot), and continue independent
   eligible outcomes. Preserve established features, content, order and identity
   unless the accepted request changes them. A broad redesign needs an accepted
   direction; hold owner-only brand/product choices rather than inventing them.
3. **Bound the outcome.** Publish supported defects or accepted design changes,
   not unaccepted visual preferences: do not publish a new palette simply because
   the reviewer prefers it. Each issue needs the screen location/current evidence,
   user cost, smallest chosen change, what stays intact, and a repeatable check:
   route template, synthetic fixture, viewport, starting state, interaction steps,
   expected result, exact test command or manual procedure. Include keyboard,
   contrast and reduced-motion checks where affected. Mark unrun checks explicitly.
   Screenshot inspection is not permission to attach it to GitHub: never attach a
   private capture by default. Use sanitized route templates, synthetic data and
   durable source/revision links; only attach evidence with explicit publication
   permission after privacy review. Temporary capture paths are not durable sources.
4. **Reconcile once.** Follow [finding intake](PLAN-HANDOFF.md#conversation-findings-to-issues)
   against current source, open and closed issues, linked PRs and actual ownership.
   Match the user-visible outcome, affected route/state and same fix and acceptance
   check, regardless of which skill found it; skill names are not duplicate keys.
   Group common fixes, split independently verifiable outcomes. If existing work
   covers the finding, report its verified link and disposition instead of opening
   another issue. Completed work is not reopened; owned work is not rewritten or
   redispatched. A changed or recurrent defect needs fresh evidence of the uncovered
   delta, not automatic reuse or a replacement ticket. Unsupported findings stay
   held without blocking independent supported work. Zero eligible outcomes means
   zero new issues.
5. **Publish and stop.** The shared handoff owns preview, complete bounded issue
   contracts, whole-batch readback and native `blockedBy` dependencies, then
   `ai-ready` last with a fresh per-issue ownership/contract/graph check. Respect
   no-dispatch; stop after publication. Report verified links, reused/completed/owned
   dispositions, holds, readiness/dependencies and unrun checks. Use its failure and
   partial receipts: **UNSAVED** for creation never attempted, **UNKNOWN** for an
   inconclusive write; preserve the exact error and reconcile by stable key and
   fresh readback before retrying. Publication is not implementation, pickup or
   permission to start Orbi, edit UI, commit or launch another worker.

## Shared keyboard case

At `/checkout`, with a synthetic cart, 375px viewport and a validation error,
Tab from the address field to the primary action, then press Enter. If focus
cannot reach the action, record the actual focus sequence and failing state.
The bounded outcome restores keyboard completion while preserving validation;
acceptance repeats those steps and verifies visible focus and keyboard activation
without losing the error message. Name the fixture and regression command.
If Impeccable publishes this failure first, UI Taste reports that issue's verified
link instead of opening another (and vice versa), even if their critiques use
different wording. An unaccepted suggestion to recolor that action stays held.
