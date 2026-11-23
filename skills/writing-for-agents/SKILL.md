---
name: writing-for-agents
description: "Write and prune skills and agent docs."
license: MIT
---

# Writing For Agents

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

Read the pinned [writing reference](upstream/PROTOCOL.md) before writing or editing a
skill, an `AGENTS.md`/`CLAUDE.md`, or a document an agent reaches through a pointer.
For a skill, resolve invocation before choosing metadata or applying the pinned
[skill mechanics](upstream/SKILL-MECHANICS.md):

- **Kit public skills** stay explicit-only, even when another workflow needs them.
  Name the explicit host command in the handoff (for example, `/docs-sync` on Pi
  or `/kit:docs-sync` on Claude Code). Put shared instructions in a plain reference
  file and link it instead of making an automatically activated skill.
  Portable adapters retain `disable-model-invocation: true` and Codex
  `policy.allow_implicit_invocation: false` in `agents/openai.yaml`; descriptions
  remain human-facing summaries, not model trigger lists.
  In a Kit checkout, follow the governing [skill standard](../../docs/skill-standard.md).
  These inline Kit rules also cover skills-only installations without that document
  and override upstream's advice to enable model invocation for composition.
- For **non-Kit projects**, use upstream's invocation guidance under the target
  project's conventions.

Apply the technique; keep the invoking workflow's scope, GitHub handoff, review
and delivery rules.

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

## Planning or read-only advice

For planning-only requests, return the proposed design or authorized issue handoff;
leave executable instructions (including `SKILL.md`), code and metadata unchanged.
For read-only requests, return advice inline and write nothing, including scratch
files or issues.

Example: “Plan a Kit skill that another workflow needs; do not edit.” Return the
proposed design inline: name the proposed skill's explicit host-command handoff,
or recommend a plain shared reference if only instructions need reuse. Retain the
Kit metadata rules above if a portable skill is needed. No file writes are needed.

## Editing an existing skill

Use these steps only for an authorized edit.

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

- `/agents-md-generator` owns instruction-chain discovery, source evidence and
  reconciliation; this reference owns wording and structure within that scope.
- Not a rewriter of pinned upstream bytes, a hosting dependency or a change to what a
  skill is authorized to do.
- Not a review or delivery authority: editing a document never widens scope.

**Done when:** an authorized edit reports actual changes, line delta and affected checks;
planning/read-only advice returns the requested design or handoff within caller scope,
without implementation or a line delta.

**Receipt:** for edits, report documents changed, lines before and after, meanings
moved/deleted/merged, pointers added and checks run. For advice, report the proposal,
sources checked and proposed/unrun checks. Separate source checks from model tests
and name unverified claims.

[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).
