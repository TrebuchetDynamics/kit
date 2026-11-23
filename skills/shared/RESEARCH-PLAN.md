# Autoresearch plan adaptations

Read this contract **before** the pinned `skills/autoresearch/upstream/plan.md`
and supporting methods. It governs Plan For Me, Plan With Me, Unslop, challenge/Grill Me
compatibility and every Autoresearch plan route on every host. Its planning
boundaries take precedence over generic method prompts, task-sizing shortcuts and
execution defaults; host tool mappings still apply. These are instructions, not a
hard tool sandbox. Use host restrictions when available; do not claim enforcement
that the host does not supply.

## Planning artifact and authority contract

Bind the current request before acting:

| Invocation | Allowed finish |
| --- | --- |
| Explicit standalone planning | Save the requested plan/batch, then stop. Earlier unrelated implementation permission does not widen this request. |
| Explicit standalone Plan For Me with no concrete objective in the request or relevant conversation, or only a vague direction | Run the [project-discovery protocol](../plan-for-me/references/discovery.md), then save the authorized planning batch and stop. |
| Orbi-owned planning substep | Return findings and saved tasks to that **same coordinator**; its existing execution authority continues outside this substep. No competing worker, dispatch or workflow restart. |
| Questions-only, read-only, chat-only, no-write, no changes or dry-run | Read and discuss only; save nothing, including queue metadata or research scratch. |
| Later explicit instruction to implement the accepted plan | End planning and enter the authorized execution workflow under repository checks, ownership and delivery limits. |

“Yes”, “looks good”, an easy fix, an accepted/saved plan and a supporting skill
urging coding are not transitions to implementation. Acceptance of a plan is not
execution authority. Do not ask an already-authorized coordinator to approve again.
This limits the planning session, not the queue: writable planning publishes
complete issues with `ai-ready` automatically, so an existing Orbi deployment may
start them. Explicit no-dispatch requests and unresolved intent retain `ai-planning`.
All issue authors receive the same readiness default. See the
[publication policy](PLAN-HANDOFF.md#publication-and-dependencies).

First resolve [conversation findings](PLAN-HANDOFF.md#conversation-findings-to-issues)
when the request follows an analysis or discussion. A standalone Plan For Me
invocation without a concrete objective in either request or relevant conversation
authorizes project-wide planning, not product direction. It may refine accepted
goals and establish evidence-backed engineering goals inside the accepted direction; new
product strategies remain proposals until the owner accepts them. Plan With Me
keeps its interactive missing-intent behavior, and an Orbi-owned substep stays
inside its named task and authorized prerequisites.

Classify each proposed write by **artifact role**, not filename or extension:

| Role | During writable planning |
| --- | --- |
| Existing plan/spec/requirements owners and GitHub Issues | Save in-scope evidence and decisions in their owners and executable work in GitHub Issues. Preserve issue numbers, history, active contracts and unrelated batches. |
| Temporary research notes/results | Only bounded, allowed scratch; never implementation disguised as a spike. No scratch in no-write mode. |
| Production code, tests, fixtures, executable instructions (including Markdown `SKILL.md`), CI, manifests and lockfiles | Implementation: describe future changes in tasks; do not write them during planning. |

Investigate with reads and safe checks. Inspect commands for generated files,
cache writes and live effects before running them; a command called “dry-run” may
mutate. Do not repair implementation, generate tests, install dependencies, alter
services, commit or push to make a planning check pass. Name future tests/checks as
proposed/unrun. Preserve someone else's dirty work. If this occurrence crosses its
own boundary, stop the offending action and report attributable changes; do not
hide them with reset/clean or overwrite unrelated work.


For every writable planning route, complete
[GitHub publication](PLAN-HANDOFF.md#publication-and-dependencies) before claiming
persistence. No local-main commit or `tasks/` validation is required. If GitHub is
unavailable, continue permitted research and show complete proposals as **UNSAVED**
with the exact missing input and retry command; never create a second local queue.

## Shared planning interface

Plan With Me and Plan For Me are two adapters over one sequence. The mode changes
who answers consequential intent. It does not change the sequence.

1. **Brief.** Inventory every requested outcome, existing task ID, accepted decision
   and unresolved choice. For a discovery request, inventory accepted goals, the
   existing backlog and the evidenced gaps before adding anything. A clear one-line
   task still gets a complete saved record; “no interview” means no unnecessary
   questions, not “implement now”.
2. **Investigate and decide.** Read the actual source, tests, docs and current task
   state. Resolve consequential engineering choices within delegated scope. Ask the
   owner only for missing intent, authority or an external input. For a concrete
   method gap, select one technique through [engineering](../engineering/REFERENCE.md);
   routine planning needs no experiment loop. Apply
   [decision closure](PLANNING-CRAFT.md#decision-closure) before calling a task ready.
3. **Preview and save.** Show the [issue preview](PLAN-HANDOFF.md#progress-and-final-receipt)
   in chat before publication. Write accepted decisions in their existing owners
   and complete GitHub Issues with outcome, scope/exclusions, acceptance, exact
   verification and sources. For a user-visible change, name the capability and
   what is added, modified, removed or renamed relative to today. In the issue’s
   acceptance criteria, give a concrete WHEN (situation) / THEN (observable result).
   If the project uses or explicitly adopts OpenSpec, link the exact native spec
   and scenario instead of copying its text. A behavior-preserving refactor
   needs verification, not a fictional behavior change or new spec. No OpenSpec
   CLI, parallel task list or separate model pass is required.
   Use native `blockedBy` dependencies and `ai-epic` coordination for larger plans.
   Follow the [single-pass handoff](PLAN-HANDOFF.md#one-planning-pass-one-handoff).
4. **Validate and report.** Read back the whole batch and dependencies, then publish
   `ai-ready` last. Report issue URLs, ready/waiting/proposed state and actual checks.
   Publication is not execution evidence.

| Mode | Unique behavior |
| --- | --- |
| Plan With Me | Interviews the owner for consequential missing intent, then saves the answered plan. |
| Plan For Me | Investigates and chooses within delegated scope; project discovery applies only when neither request nor relevant conversation supplies a concrete objective. |

### Rolling plans and issue records

Save the first evidence-backed batch when later work depends on implementation
findings. Keep future expansion in the epic; do not create an automatic legacy
rolling-planning chain. Every executable issue has an observable outcome, bounded
scope and exclusions, acceptance, exact verification commands and governing sources.
Use descriptive titles. Keep unresolved intent only on affected work with its exact
missing input and resume condition. Native GitHub dependencies own ordering.
See [the issue contract](PLAN-HANDOFF.md#one-planning-pass-one-handoff).

## Full requested batch

1. Inventory **every requested outcome**, existing task ID and unresolved choice.
   For a discovery request, inventory accepted goals, existing backlog and the
   evidenced gaps before adding anything. Group shared decisions/evidence once. A
   clear one-line task still gets a complete saved record; “no interview” means no
   unnecessary questions, not “implement now”.
2. Save one coherent batch with complete task records: scope/exclusions, decisions,
   sources/evidence, observable acceptance, exact checks, bounded implementation paths and
   actual shared-resource constraints where needed. Use the
   [handoff](PLAN-HANDOFF.md#one-planning-pass-one-handoff). Do not stop when the
   first task becomes clear or substitute a roadmap/count for requested records.
3. Order by real prerequisites. Keep independent ready lanes; overlapping writes
   constrain scheduling but do not by themselves create product dependencies.
   Re-cut ownership where useful, or report overlap honestly rather than promise
   parallel execution. Keep unresolved intent pending only on affected tasks.
4. Distinguish the complete requested batch from future evidence-dependent roadmap
   expansion. Rolling planning may defer that unknown expansion, not silently drop
   specified outcomes. At handoff, map each requested outcome to saved IDs or its
   explicitly scoped open choice, then report paths, checks and the next action
   without starting it. For optional scoped `Skills:` recommendations, follow the
   [existing convention](PLAN-HANDOFF.md#scoped-skills-convention); no new required field.

## Research and persistence method

1. Resume the requested goal, relevant repository source/tests and existing plans.
   If no goal was supplied, use the current authorized task or repository-development
   objective when unambiguous. A standalone Plan For Me request without a concrete
   objective in the request or relevant conversation runs the
   [project-discovery protocol](../plan-for-me/references/discovery.md):
   investigate the repository first, then derive accepted and engineering goals from
   evidence. Do not ask for a goal before that investigation and do not invent
   product intent. Plan With Me asks for the missing goal; an Orbi-owned substep
   stays inside its named task.
2. Investigate the actual uncertainty. Record source paths and concrete observations;
   fetch primary external sources when the decision depends on external behavior or
   current facts. Reading this protocol alone is not research. Reuse still-valid
   evidence and choose ordinary engineering details within delegated scope.
   Resolve consequential design/dependency choices here so Orbi receives an
   executable task, not an instruction to repeat the investigation. Record the
   chosen approach and checks in the existing task; leave reversible coding
   details to the worker. Apply [decision closure](PLANNING-CRAFT.md#decision-closure)
   to choices and builder findings before readiness, then follow the
   [handoff](PLAN-HANDOFF.md#one-planning-pass-one-handoff).
3. Apply upstream scope, metric, Verify, Guard and bounded-iteration analysis where
   meaningful. A qualitative plan needs observable acceptance, not a fabricated
   numeric metric. If feature tests do not exist yet, record proposed commands as
   unrun and add their implementation to the task. Do not retry nonexistent tests
   until they print a number or call missing tests a measured zero baseline.
   Inspect commands before running them; a Verify 'dry-run' can still mutate files.
   Explicit no-write/dry-run requests allow only nonmutating checks.
4. Replace upstream Phase 7's config-only finish and generic 'Run now?' question
   with persistence: save the supported decision, alternatives rejected and why,
   evidence and remaining uncertainty in their document owners, and actionable
   GitHub Issues and native dependencies through the
   [publication protocol](PLAN-HANDOFF.md#publication-and-dependencies).
   Reuse existing document owners and task IDs; do not create an experiment config
   or handoff.json as a substitute for the repository plan and work queue.
5. Read back affected documents and task records and run applicable consistency
   checks and GitHub readback. Report actual saved paths/issue URLs, checks and next action. If persistence
   fails, report what remains unsaved; a chat answer is not a saved plan. Unchanged
   conclusions may reuse existing durable evidence, citing its location. New
   material reasoning must be saved even if implementation scope stays unchanged.
6. Finish according to the artifact/authority contract above. Return an
   Orbi-owned handoff to its same coordinator, not into execution inside this
   planning substep. In no-write mode show proposed updates inline and state that
   nothing was saved.

Apply the existing [single-pass handoff](PLAN-HANDOFF.md#one-planning-pass-one-handoff)
for acceptance, batching and reuse. Preserve genuine missing product intent as a
scoped question, not a reason to stop unrelated authorized planning.

## Existing execution is not a new planning problem

When Orbi already has a card and partial work, distinguish product uncertainty
from a session-continuation, accounting or runtime failure. If no product decision
is missing, return the exact failed operation and evidence to the same coordinator
for supported recovery. Do not create a replacement implementation task, rerun this
plan protocol or present another product plan as progress. Save
new technical findings to its existing issue only when they add evidence.

## Interactive planning: Plan With Me

Only in interactive or challenge mode, follow the interview steps in
[Plan With Me](../plan-with-me/SKILL.md). If that workflow is already loaded,
continue there without rereading it. Other planning modes use the common method
above without loading the interview.
