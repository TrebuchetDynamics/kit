# Definition of Done

A standing bar every change clears before it counts as done. It complements task
acceptance criteria; it does not replace them.

General correctness, quality, integration, documentation and ship criteria live in
the [pinned Addy checklist](../engineering/upstream/references/definition-of-done.md).
This file owns the Kit-specific gates.

## Kit gates

- [ ] Task acceptance is met and the exact checks ran on the changed candidate.
- [ ] Required review passed; no fabricated approval.
- [ ] Scope and `touches` were respected; unrelated dirty work was preserved.
- [ ] Task-store closure or manual close records the real reason and evidence; no
  false verified claim.
- [ ] Documentation impact is assessed as `not_needed`, `updated` or `pending`.
- [ ] Local commit, integration, push and deployment are reported separately.
- [ ] Live, device or production qualification stays separate and is labelled
  `NOT_CHECKED` when unrun.
- [ ] No secrets, generated scratch or unrelated changes are in the deliverable.

## Apply

- **Planning:** use it to test whether a task is ready.
- **Autowork:** use it before closing a task.
- **Review:** use it as the standing bar beyond the changed diff.
- **Delivery:** use it to separate a local commit from push or deployment.

## Red flags

- "Done" before the required checks ran.
- Task acceptance treated as the whole bar.
- A different bar applied under time pressure.
- Push or deployment claimed from a local commit.
- Live qualification implied by an offline pass.
