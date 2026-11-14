# Shared skill contract

Use the [ASD-STE100 and project language rules](COMMUNICATION.md) for user-facing text.
Read the target project's glossary map and glossary when available.

Apply the [shared Ponytail method](PONYTAIL.md) within each workflow's authority.
Reuse existing code and artifact owners; choose the smallest complete result,
without weakening accepted behavior, safety or verification.

## Operating behavior

Apply these with [Ponytail](PONYTAIL.md) and the [communication rules](COMMUNICATION.md).

- Check whether a bundled skill fits before a non-trivial response or action; use
  [`/ask-kit`](../ask-kit/SKILL.md), then read the named skill.
- For lifecycle rules, asynchronous effects or shared-state changes, apply the
  [state-machine analysis](../state-machine/PROTOCOL.md) to the affected paths.
  Reuse a current map; keep the caller's scope, mode and report format.
- Surface assumptions before non-trivial work; mark guesses.
- Name confusion and conflicting requirements; stop and resolve them.
- Disagree with evidence; propose the alternative.
- Preserve scope and unrelated work.
- Verify before claim; name unrun checks and missing coverage.

User instructions and repository rules define the authorized scope. Read the
relevant instructions, current source, tests and existing documentation before
changing their owners. Keep proposals distinct from accepted requirements and
implemented behavior. An explicit skill invocation authorizes its documented default
actions within the user's scope: planning commands may save docs/tasks, and Autowork
may implement, test and commit locally. Loading a supporting skill adds no authority.
Installation, publication, third-party contact and destructive actions require their
own authorization; specific no-write/no-commit restrictions always take precedence.

For task operations, load the [task CLI policy](TODO-WORKCENTER.md#task-cli-policy),
including its unavailable-tool fallback; this does not widen workflow authority.

Follow [task holds](TODO-WORKCENTER.md#task-holds-require-an-explicit-user-request):
leave tasks active by default. Only an explicit user request permits a skill to add
or renew a task hold. Session scope does not pause the queue; existing safety gates
and live ownership remain in force.

Inspect status and preserve pre-existing edits, untracked files and live ownership.
Use [worktree isolation](WORKTREE-ISOLATION.md) when a separate writing checkout
is required. Do not reset, clean, stage or overwrite unrelated work. Keep secrets
and generated scratch out of deliverables.

Run the checks that discriminate the claimed change. Record actual commands,
results and the source they exercised; label missing coverage NOT_CHECKED.
Static policy checks and offline fixtures do not prove model adherence, native
worker execution, provider behavior or delivery. Review scoped diffs and links,
and reconcile affected documentation and task state without inventing evidence.
Report changed artifacts, verified behavior, limitations and remaining work.

## Graph state

A code graph never describes its input perfectly. When a workflow uses one, report
exactly one state: `graphify_fresh` (version keys readable, nonzero nodes and links,
queried inputs unchanged, tool version recorded), `graphify_stale` or
`graphify_partial` (a changed or unknown input, an uncommitted or excluded file, or an
integrity warning), or `graphify_unavailable` (the tool, the skill or the extraction
failed; name the failure). Under any state except `graphify_fresh`, a graph result is
orientation: verify it in live source before a conclusion, and claim no unreachability,
runtime behavior, severity or effort saved. The Graphify workflow in
`adapters/skills/graphify/SKILL.md` owns how this tool reaches each state.

Resolve helper paths from the actual loaded skill directory, not an assumed
Hermes home. Sibling bundled skills and this support directory retain their
relative layout. Quote absolute paths and repository arguments in shell commands.
Before creating or refining repository tasks, read
[ordinary authoring](TODO-WORKCENTER.md#ordinary-authoring) for task text and grouping,
then use the [work center](TODO-WORKCENTER.md) for `autowork tasks` edits and selection.
See [plan handoff](PLAN-HANDOFF.md) for accepted backlog boundaries.
