---
name: writing-for-agents
description: "Write and prune skills and agent docs."
license: MIT
---

# Writing For Agents

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Read the pinned [writing reference](upstream/PROTOCOL.md) before writing or editing a
skill, an `AGENTS.md`/`CLAUDE.md`, or a document an agent reaches through a pointer.
Read [skill mechanics](upstream/SKILL-MECHANICS.md) only when the document is a skill.
Apply the technique; keep Autowork's scope, task store, review and delivery rules.

## The bar for a document

- Every always-loaded line is a **pointer** with sharp wording and one trigger per
  branch. The body carries steps; reference moves behind a pointer once only some
  branches need it.
- Each step ends on a completion criterion the agent can check. State the positive
  target; keep a prohibition only as a guardrail you cannot phrase positively.
- One meaning, one home. The environment is a source of truth, so do not cache a
  one-command lookup; cache the convention, reason or gotcha it cannot show.
- Hunt no-ops: a sentence the model already obeys pays load to say nothing. Delete
  the sentence, not its words.
- Prefer a pretrained **leading word** over a spelled-out triad. It recruits priors
  and anchors the behaviour in fewer tokens.
- For a high-risk skill, name the excuses that skip the process and the observable
  red flags. Link the [Definition of Done](../shared/DEFINITION-OF-DONE.md); keep
  the skill's single completion line as the only criterion.

## Editing an existing skill

1. Read the skill, its adapter, its references and the tests that read them.
2. Name what each paragraph does: step, in-file reference, disclosed reference or
   noise. Move branch-only reference behind a pointer; delete noise.
3. Keep every contract a test, host or user relies on, and move text rather than
   rewriting it when the meaning already holds.
   For a high-risk skill, check the rationalization table, red flags and Definition
   of Done link while you check the steps.
4. Check the result: the steps still read in order, each pointer has a live target,
   and no meaning now has two homes.
5. Run the tests for the files you touched. Report lines removed and what stayed.

## Boundaries

- Not a rewriter of pinned upstream bytes, a hosting dependency or a change to what a
  skill is authorized to do.
- Not a review or delivery authority: editing a document never widens scope.

**Done when:** the named document is edited or pruned with its line delta, and the
affected checks are reported.

**Receipt:** documents changed; lines before and after; meanings moved, deleted or
merged; pointers added; tests run; unverified claims.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).
