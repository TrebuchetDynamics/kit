# Goal research notes

Research date: 2026-11-01. These notes record what this skill adopted and what it
deliberately leaves to the host.

## Sources

- OpenAI Cookbook, [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).
  The guide defines a goal as a scoped completion contract with an outcome, a
  verification surface, constraints, boundaries, an iteration policy and a blocked
  stop condition. It states that goals are thread-scoped, continue only at safe
  boundaries, and complete only from concrete evidence. It also warns that a budget
  limit is not completion.
- Hermes Agent, [Persistent Goals](https://hermes-agent.nousresearch.com/docs/user-guide/features/goals).
  Hermes implements `/goal` as a single-session continuation loop with a judge,
  pause/resume/clear controls, completion contracts and deterministic quality gates.
  The documentation separates `/goal` from Kanban and states that a goal does not
  create or move board work.
- Joseph Thacker, [claude-goal](https://github.com/jthack/claude-goal) and its
  [Codex research notes](https://github.com/jthack/claude-goal/blob/main/goal/references/codex-goal-research.md).
  This Claude Code adaptation stores per-session state in SQLite, adds a Stop hook,
  and requires a real completion audit before marking a goal complete. It also
  documents soft token budgets and the runaway-continuation guard.

## Adopted

- The six-part completion contract.
- The active, paused, blocked, complete and cleared states.
- Pause, resume, clear, status and complete commands.
- Continuation in verified slices instead of repeated user prompts.
- Evidence-based completion and a completion audit.
- A no-progress guard and a soft budget checkpoint.
- Honest separation of local checks from live or production qualification.

## Not adopted

- No SQLite database, hidden state file, Stop hook or background process.
- No second judge model. The agent audits its own evidence, and the host's native
  goal loop keeps its own judge where it exists.
- No project-level `GOAL.md` or instruction file. Codex and Hermes keep goal state
  in the thread or session, not in project instructions.
- No automatic Kanban or task creation. Durable repository work stays in `tasks/`
  through the planning and execution skills.
- No exact token metering. A token budget is a user-declared soft limit because a
  skill cannot observe reliable per-turn usage on every host.

## Limits

This is instruction, not a runtime. It cannot force a new host turn after the agent
stops. On Hermes, use the native `/goal` loop with its judge and gates. On hosts
without native continuation, the skill keeps the objective visible and continues
within the current turn and session.

Offline checks can prove that the skill files, links, command registration and
adapter metadata are present. They cannot prove that a live model follows the
contract, completes a real objective or reports evidence honestly.
