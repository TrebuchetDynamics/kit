# Maintain affected repository instructions

Read this committed Markdown when accepted work changes a documented command,
source-of-truth path, architectural boundary or durable convention. No registered
skill or automatic skill invocation is required.

1. Find only the guidance affected by the change, including applicable instruction
   files and their existing document owners. Compare the rule with the accepted
   requirement and changed source. No affected guidance means no edit.
2. Reconcile affected guidance in the same PR. Keep shared policy in its existing
   owner, with conditional repository-relative pointers for detail. Add only durable,
   verified lessons; failure logs and speculation are not instructions.
3. Preserve maintainer policy, useful exceptions, ownership, pauses, acceptance and
   review gates. Source disagreement alone does not revoke policy. Explain unresolved
   policy conflicts with both sources and effects; ask the precise blocking question.
   Hold dependent changes and continue independent accepted work.
4. Verify affected links and command definitions. Report what changed, checks run
   versus inspected/unrun, and unresolved input in the normal delivery receipt.

This procedure does not broaden permissions or require a routine whole-repository
instruction audit. Full cleanup requires explicit generator scope through
[agents-md-generator](../agents-md-generator/SKILL.md), not an implicit invocation.
