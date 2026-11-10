---
name: ask-kit
description: "Find the skill that fits the situation."
license: MIT
---

# Ask Kit

For task operations, load the [task CLI policy](../shared/TODO-WORKCENTER.md#task-cli-policy).

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

You do not remember every command, so ask. This map names the skill for a situation; it
never replaces reading it. Before you describe what a skill does or recommend skipping
a step, read that skill's `SKILL.md`: a summary here is orientation only.

## Before you answer or act

Check this map before a non-trivial response or action. A short request or a question
can still match a skill. If one fits, name it, read its `SKILL.md` and follow it. If
none fits, say so. This map grants no authority and does not start work the user did
not ask for.

## Main flow: idea to delivered work

1. **Sharpen the idea.** `/grilling` interviews you in rounds and stops when the
   decision tree is empty. Working in a repository? `/grill-with-docs` also records the
   settled decisions as ADRs and glossary terms. A plan that already exists gets
   `/grill-me`, the plan-specific branch.
2. **Make the plan executable.** `/plan-for-me` investigates and saves goals and tasks
   without an interview; `/plan-with-me` asks only what it cannot find.
3. **Do the work here.** `/work` selects and completes tasks in this session.
   It continues automatically and finds useful offline work when the queue is gated.
   On portable hosts, `/autowork` starts the runner by default.
   For one objective that must stay in view across many turns, use `/goal`. For many
   lanes at once, `/autonomous-codebase-improver`.
4. **Deliver.** `/git-commit-push` commits, syncs and pushes when the request allows.
   `/lgtm` says yes to the latest recommendation, including recommended answers to a
   question round, and continues.

## On-ramps

| Situation | Skill |
| --- | --- |
| Something is broken and you cannot yet reproduce it | `/bug-harvest` |
| The suite is bloated, slow or full of low-value tests | `/test-optimizer` |
| Code looks unused and you want it gone | `/unused-code` |
| Merge every finished worktree into main | `/git-commit-push all` |
| Commit all eligible changes, merge worktrees, sync and push main | `/push` |
| Execute an accepted refactoring task in this session | `/work` |
| One folder needs splitting without behavior change | `/split-folder` |
| Modules are shallow or seams leak | `/improve-codebase-architecture` |
| One objective needs many turns and an evidence audit | `/goal` |
| Queue work is held and the owner must decide | `/blockers` |
| A runner is stalled or waiting and needs autonomous repair | `/unblock` |
| Docs or task records drifted | `/docs-sync` |
| A question needs measured evidence | `/autoresearch` |
| One engineering method is missing (TDD, review, debugging) | Read [engineering](../engineering/REFERENCE.md) directly; no command |
| A compact Android release build is needed | `/apk-get` |

## Design and writing

| Situation | Skill |
| --- | --- |
| Interface design, polish or frontend audit | `/impeccable` |
| Uizze's UI playbooks | `/ui-taste` |
| README visuals and SVG assets | `/beautify-github-readme` |
| Responsive captures at chosen breakpoints | `/responsive-screenshots` |
| Writing or pruning a skill, `AGENTS.md` or agent doc | `/writing-for-agents` |
| Orientation in code before reading many files | `/graphify` |
| Ponytail guidance, review, audit, debt or benchmarks | `/ponytail`, `/ponytail-review`,
  `/ponytail-audit`, `/ponytail-debt`, `/ponytail-gain`, `/ponytail-help` |
| What is open, done or next | `/pending` |

## How to answer

1. Name the one command that fits, then the next concrete step it implies.
2. When two fit, read both `## Boundaries` sections and pick the narrower one.
3. Say plainly when a request needs no skill, or when it needs an owner decision
   rather than a command.
4. This map grants no authority: scope, review gates, publication and live operations
   keep their own rules.

## Boundaries

- Not a dispatcher: it recommends a command, and the user or caller runs it.
- Not a queue or status report; use `/pending` or `/blockers`.
- Not a substitute for the chosen skill's instructions; read that file.
- Not an always-on meta-skill: it runs when invoked; the shared contract asks for a
  check, not automatic activation.

**Done when:** one command is named with its next step, or the request is reported as
needing no skill or an owner decision.
