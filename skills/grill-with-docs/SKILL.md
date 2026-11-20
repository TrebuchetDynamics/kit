---
name: grill-with-docs
description: "Grill a plan and record ADRs and terms."
license: MIT
---

# Grill With Docs

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

The pinned [upstream entry](upstream/PROTOCOL.md) is a router: it asks a host to call
a `grilling` skill and a `domain-modeling` skill. Kit hosts have no such skill
call, so this adapter states the composition directly. Run the interview with
[Grilling](../grilling/SKILL.md), then record what it settles with the repository's
own documentation owners.

## Compose the two jobs

1. Run [Grilling](../grilling/SKILL.md) on the plan or design. Do not write documents
   during the rounds; the decisions are not settled yet. For a user-visible change,
   identify the current behavior and test the proposed difference with a WHEN/THEN
   example. If two interpretations still fit, ask about the case where their outcomes
   differ. Use the existing spec when one exists; do not create one for the interview.
2. After the owner confirms the shared understanding, record each durable decision. For an explicitly read-only interview, show the proposed records inline and stop without writing:

   - a decision with alternatives, a chosen option and a reason becomes an ADR in the
     repository's ADR folder, following its existing numbering and template;
   - a named domain concept or a resolved ambiguity becomes one glossary entry with the
     term, its meaning and the words to avoid.
3. Follow [Docs Sync](../../skills/docs-sync/SKILL.md) for the write rules: source-backed
   claims, the existing owners, and its validation and report contract. Create a missing
   glossary or ADR folder once, lazily, and say you did.
4. Skip a record when it would be ephemeral ("not worth it now") or self-evident. Never
   reverse an accepted ADR silently; surface the conflict and let the owner decide.

One message per settled decision group, not a document per question. Keep the ADR and
glossary vocabulary out of code identifiers unless the repository already uses it.

**Receipt:** decisions recorded with their paths; terms added; decisions left open;
validation run; anything intentionally unrecorded and why.


## Boundaries

- Not implementation; publish accepted work through the planners for Orbi.
- Not a record for every passing thought: ephemeral and self-evident reasons are named and skipped.

**Done when:** settled decisions are recorded and validated, or shown inline for a read-only request. Name skipped records and any validation still pending.
[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).