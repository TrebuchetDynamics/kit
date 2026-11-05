# Standing decision policy

Status: accepted by the owner on 2026-11-05. This document is an owner decision
for this repository and for any workspace that adopts it. It does not change task
acceptance, publication, live or security authority.

## Purpose

Autowork already decides routine engineering choices inside accepted work. This
policy names the remaining choices that the coordinator may settle without a new
owner question. It prevents a reversible engineering choice from stopping the
queue. It keeps product, live and irreversible decisions with the owner.

## Delegated decisions

The coordinator may decide these without asking when the task's accepted scope,
checks and exclusions leave the choice open:

- Implementation mechanics: file layout, naming, helper extraction, error-message
  wording, test seam and test placement inside `touches`.
- UI composition: use existing primitives and theme tokens; keep 48px targets;
  prefer fewer controls and a clear hierarchy; add no dependency.
- Dependency choice: reuse existing dependencies; add no new runtime dependency
  unless the task explicitly requires one.
- Ordering: rank independent ready tasks and choose the next ready task.
- Documentation: update the existing document owner and keep claims tied to
  evidence.
- Local repair: fix a cause that blocks the task's own checks, inside the task's
  scope and exclusions.

Record the choice and evidence on the task. Record it as a planner call under this
policy, not as a new owner answer.

## Owner-only decisions

Keep the task in `Needs decision` and ask the owner for:

- A new goal, product direction, scope expansion or changed acceptance.
- A change to an exclusion, live or publication grant, deployment, credential,
  secret, money, destructive action or history rewrite.
- A security or legal exception, or an external commitment.
- A choice that this policy does not clearly cover, or one that is hard to
  reverse.
- Any decision that would weaken a check, invent evidence or claim qualification.

## Applying the policy to a question

1. Name the exact choice and the task it affects.
2. If a delegated domain covers it and the choice is reversible, choose the
   smallest complete option that preserves accepted behavior and checks.
3. Record a `Standing policy:` note on the task with the policy anchor, the
   choice, the reason and the evidence. Do not write an `Owner decision:` note
   for a planner call.
4. Move a covered `Needs decision` task to `Now` or `Next`. Preserve its
   acceptance, exclusions, dependencies and history.
5. If the choice is owner-only, leave the task in `Needs decision` with its
   `Question:`.

Do not create an `owner_waiver` or `owner_qualification` from a planner call. Only
the owner writes those attestations.

## What autodecision does not mean

- It is not a blanket approval.
- It is not an automatic answer for every `Needs decision` question.
- It is not permission to push, deploy, operate live systems, spend money or
  access secrets.
- It is not permission to change acceptance or claim qualification.

## Change control

Only the owner changes the rules in this document. An agent may propose a change as
a task. The coordinator may append dated audit results to the audit log below.

## Audit log

The coordinator may append dated audit results to this section. An audit entry
names the audited task IDs, each delegated or owner-only disposition, the moved IDs
and the remaining owner questions.

- 2026-11-05: Policy accepted. No queue audit recorded yet.
- 2026-11-05: Standing-policy audit of open Needs decision tasks. Audited: TOOLSET-431-47a7152e (owner-only: live-profile proof authorization), TOOLSET-450-e643cb7a (owner-only: security-default policy change), TOOLSET-451-ba324296 (owner-only: authorized spend and target for live delivery). Moved IDs: none. Remaining owner questions: TOOLSET-431-47a7152e needs owner authorization for a live Hermes profile write; TOOLSET-450-e643cb7a needs an owner decision on the default Hermes approvals security stance; TOOLSET-451-ba324296 needs owner authorization for model spend and a disposable-repository target.
