# Skill adherence and Definition of Done

Status: Accepted

## Scope

Borrow Addy Osmani's adherence mechanics without replacing Kit's task store,
explicit-only commands or `ask-autowork` router. Pilot the sections on three
high-risk skills, add the shared Definition of Done and operating behavior, and
cover the pilot with Tier 1 and Tier 2 checks.

## Task 1: pilot adherence sections

Add `## Common Rationalizations` and `## Red Flags` before `## Boundaries` in
`autowork`, `plan-for-me` and `ponytail-review`. Keep the single completion line.
Link the shared Definition of Done. Add the operating-behavior section to
`COMMON-CONTRACT.md`. Update `docs/skill-standard.md` and `writing-for-agents`.

Acceptance: the three pilot skills name their real excuses and red flags; each links
the shared Definition of Done; the standard and writing guide require the pattern;
Tier 1 structural and Tier 2 routing/description checks pass.

Checks:

```sh
python3 scripts/check.py tests/test_skill_standard.py tests/test_workflow_commands.py \
  tests/test_workflow_contract.py tests/test_skill_descriptions.py
```

## Task 2: roll out the pattern

After the pilot is reviewed, add the same sections to the remaining high-risk skills,
starting with `git-commit-push`, `docs-sync` and `plan-with-me`. Keep each table
specific to the skill's failure modes; do not copy a generic table.

Acceptance: the standard is applied beyond the pilot with skill-specific tables and
red flags, and the structural checks cover the added skills.

Checks: the skill-standard and routing checks for the expanded set.

## Out of scope

No new lifecycle commands, automatic activation, second router, Tier 3 model-trace
evals, packaging change or delivery authority. Pinned Addy bytes stay unchanged.
