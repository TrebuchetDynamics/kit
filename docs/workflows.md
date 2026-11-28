# Commands and repository workflows

GitHub Issues own executable work; Orbi owns delivery. Kit plans and supplies
explicit skills. See [support, setup and migration](github-native.md).

## Unblock repairs blocked GitHub work

`/unblock` checks open issues and PRs, fixes actionable causes, and reconciles
recovery labels without asking again for routine decisions. It reports the count
and oldest open `owner-task` separately. It
[cleans stale labels on closed worker issues and rechecks base-red blocks after a base advance](../skills/unblock/SKILL.md#stale-issue-state).
Base-red recovery requeues the existing delivery with `ai-fix-needed`. Other
eligible `ai-planning` or `ai-blocked` issues use `ai-ready` only after the plan
is complete or the blocker is repaired (both when both labels apply). It verifies
whether work resumed. Read-only requests, explicit pauses,
existing PR ownership and human gates remain binding; the skill does not grant
GitHub access or activate Orbi. `/unblock all` starts with the
[read-only inventory of repositories in local Orbi deployment configs](../skills/unblock/references/inventory.md).

When requirements change, [hand the retained work back on the same issue](../skills/unblock/SKILL.md#changed-requirements-hand-back-on-the-same-issue).
Name the commit, the missing behavior, and how to verify it. A handoff is not
evidence of resumed work. See [ADR 0002](adr/0002-hand-back-incomplete-work-on-the-same-issue.md).

Its [PR phase](../skills/unblock/SKILL.md#blocked-prs-owner-first-repair-records)
accounts for every scoped open PR, including those without linked issues. It reuses
the exact repair's existing issue, owner and branch, with deduplicated evidence
comments for live workers. Only uncovered actionable repairs or independent
prerequisites need linked issues under the existing publication contract. Held,
pending and unknown gates stay explicit. Publishing a repair issue is not recovery.
See [Unblock](../skills/unblock/SKILL.md) for the full workflow.

## Bundled Ponytail

All workflows apply the [shared Ponytail method](../skills/shared/PONYTAIL.md)
within their existing authority. `/ponytail [lite|full|ultra|off]` reports or changes
only the conversation's Kit preference. `/ponytail-review`,
`/ponytail-gain` and `/ponytail-help` are one-shot reports;
they do not implement, publish, start an extra reviewer or change persistent modes.
[`/ponytail-debt`](../skills/ponytail-debt/SKILL.md) checks shortcut markers against
revisit triggers and publishes supported, uncovered outcomes in the same invocation.
It keeps the ledger as context, not a queue. Unreached or missing triggers create no
issue. Explicit read-only/dry-run/no-write reports inline; no-dispatch holds readiness.
It stops after publication and does not implement or activate services.

An ordinary [`/ponytail-audit AREA`](../skills/ponytail-audit/SKILL.md) analyzes the
requested scope and publishes warranted issues through Plan Handoff in the same
invocation, without selection or confirmation. It reports verified links and held
reasons, then stops; zero qualifying findings means zero new issues. Explicit
report-only/read-only/no-write/dry-run returns inline findings without writes.
No-dispatch, ownership and human gates remain binding. Default publication does not
implement findings or activate services; explicitly authorized local fix/apply
modes remain separate.
See [portable host invocations](cross-host.md#bundled-ponytail-on-every-host).
Existing external command owners keep their handlers; the bundled skills remain
available as `kit:ponytail` and `kit:ponytail-review` (and the other names).

All workflows inherit the [shared freshness and ownership contract](../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership).
Read-only/audit/questions/dry-run never fetch or mutate Git. Standalone writable
Plan With Me / Plan For Me apply the shared
[planner freshness exception](../skills/shared/COMMON-CONTRACT.md#standalone-planner-freshness).
Other planning routes read permitted remote source without syncing. Planning never commits.
Implementation verifies baseline/ownership and isolates stale/shared source;
delivery/sync follows the invoked command's scope and caller restrictions.

`/push` saves eligible changes in the invoking checkout only, pulls verified `main`
and delivers to `main` without a second approval round. An unrestricted invocation
includes staged, unstaged, deleted and ordinary non-ignored untracked files there.
Git identifies that checkout; invoking from a linked checkout does not authorize
canonical checkout inspection or writes. Other registered worktrees, including
nested roots, are boundaries, not content to read or stage. No separate completion
note or marker is required. The [Push save step](../skills/push/SKILL.md#fast-path)
verifies scope, provenance, actual inactivity and the invoking checkout's project
rules, then rechecks HEAD/index/file baselines before staging explicit paths. Secrets, private runtime state, ignored output,
active or uncertain ownership, pauses and recovery holds stay untouched and are
reported by path and reason, without contents. Baseline drift reports `Save pending`;
re-inventory the affected paths and resolve ownership before staging. Narrower
requests still win; `/git-commit-push` and its standalone clean-worktree sweep keep
their existing scope.

It inventories only invoking-checkout changes locally, plus paginated GitHub
issue/PR evidence, including remote-only Orbi work. Minimal Git metadata supports
safe landing, placement and registered-root boundaries; sibling files, status,
activity and unique tips are not inspected or integrated. It never calls the sweep
helper. A clean invoking checkout still requires remote/upstream verification.
Use the existing isolated candidate/PR route instead of accessing another checkout;
if no safe route exists, preserve work and report the blocker and repair action. Already-merged changes enter through verified upstream; passing
open PRs remain with their Orbi coordinator. Closed-unmerged, failed, paused and
unknown work stays untouched with its URL, reason and next action. Uncommitted changes
are committed before the pull, because they block a safe fast-forward. A stale base is
reconciled through normal merge and affected checks/review before publication, and the
repository's landing route (direct push or pull request) is used as policy allows. API
failures mean partial inventory, not an empty backlog; independently verified work may
proceed, but missing required protection/review holds publication. Receipts separate
local scope (invoking checkout path), local commits, incoming landed changes, pending
URLs, source and selected/final SHAs, checks, remote inclusion and remaining local
synchronization. Say other worktrees were not inspected, not that they were clean or
shipped. A candidate-branch
push alone is not main delivery. Missing checks/review or an unmerged protected PR
remain pending: report the exact gate and next action, then verify remote `main`
inclusion after the permitted landing route completes.
These are instruction contracts; offline traces do not prove live model delivery.

## Commands

Use GitHub Issues/PRs and read-only `orbi status`/`orbi doctor` for current
delivery status. For Hermes inventory and plugin setup diagnostics, use terminal
`hermes kit doctor --json`; `--core` checks only bundled registration.
`hermes kit update` and `hermes kit update --check` run synchronously
and print their receipt. No chat-maintenance command is provided. Imported native
commands keep their handlers; existing owners win collisions. Telegram menu capacity
is limited, so some commands must be typed directly.

| Hermes CLI chat | Telegram | Purpose |
| --- | --- | --- |
| `/orbi [status\|version\|setup\|start\|stop\|help]` | `/orbi` | [Lifecycle controls and host inventory](../skills/orbi/SKILL.md): `status all [--work] [--verbose\|--json]` summarizes observable local deployments and GitHub API budget without repo selectors (partial coverage is explicit); `--work` adds per-repo issue counts; `version` reads the selected deployment engine release/revision without full status or bootstrap probes; bare status is read-only, setup starts by default via the existing start path; setup --prepare-only prepares without activation; authorized setup/start prepares if absent then schedules, stop drains without killing workers; Linux controls, macOS read-only status/version; help prints the action reference read-only on any platform |
| `/git-commit-push` | `/git_commit_push` | Commit the current branch, sync and push its verified upstream with scoped changes (`no pull` or `no push` narrows it); `pull`, `sync` or `merge <branch>` only integrates |
| `/git-commit-push all` | `/git_commit_push all` | Also merge every finished worktree into the base branch: inventory first, merge only eligible clean unmerged ones, keep owned, unknown, dirty and locked worktrees |
| `/push` | `/push` | Save eligible invoking-checkout changes only, pull verified `main`, then deliver to `main` through the repository's landing route; other worktrees uninspected, open Orbi work reported without takeover |
| `/lgtm` | `/lgtm` | [Continue within inherited authority](../skills/lgtm/SKILL.md): accept unambiguous choices, clarify only ambiguous planning choices; standalone plan approval does not authorize implementation |
| `/docs_sync` | `/docs_sync` | Maintain repository documentation |
| `/update-kit` (also `/update_kit`) | `/update_kit` | [Refresh dedicated upstream source and reinstall the suite](../skills/update-kit/SKILL.md); explicit only, full-suite/restart effects, restricted Hermes cascades refused; [preview and ownership](installation.md#update-kit) |
| `/plan_with_me` | `/plan_with_me` | Resolve missing intent, then publish complete GitHub Issues |
| `/plan_for_me` | `/plan_for_me` | Investigate accepted scope and publish complete GitHub Issues without an interview |
| `/grill-me` | `/grill_me` | Stress-test a plan through questions |
| `/autoresearch` | `/autoresearch` | Route a research goal or run a bounded metric loop |
| `/100x <brief>` | `/100x` | [Build a prototype in this session](../skills/100x/SKILL.md); requires 100x CLI 0.1.1 on PATH. Kit does not install it. |
| `/impeccable` | `/impeccable` | Publish actionable UI findings; explicit requests design or refine |
| `/unslop` | `/unslop` | [Audit the UI and publish fixes as GitHub issues](../skills/unslop/SKILL.md) for Orbi; an existing deployment can pick up ready issues. Use `no-dispatch` to save without readiness, or `read-only` to preview. |
| `/ui-taste` | `/ui_taste` | Publish actionable UI findings; explicit requests use Uizze's build/polish playbooks |
| `/forever-components` | `/forever_components` | Search the Forever index and retrieve only selected pinned components |
| `/genjutsu` | `/genjutsu` | Design motion for an interface's interactions |
| `/motion-graphics` | `/motion_graphics` | Build and verify a seekable timeline |
| `/brand-identity` | `/brand_identity` | Compare brand directions and export the selected kit |
| `/styleseed` | `/styleseed` | Create or maintain a project design system |
| `/procedural-drawing` | `/procedural_drawing` | Draw a CPU-rendered illustration from a selected style |
| `/genart` | `/genart` | Create seeded art and check Canvas 2D output locally |
| `/beautify-github-readme` | `/beautify_github_readme` | [Audit README reader paths and publish verified issues](../skills/beautify-github-readme/SKILL.md); explicit redesign/hero and audit-only requests keep their scope. Use `no-dispatch` to withhold readiness, or `read-only` for an inline report without writes. |

For the Orbi first-deployment journey, `/orbi help` gives context-free examples and
recovery. Use `/orbi setup --dry-run --pi-providers /path/to/models.json --pi-provider
PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID` to preview, then remove
`--dry-run` to prepare/validate and activate. New preparation defaults to installed
Pi-Bolt; `--harness pi` selects stock Pi. Existing valid targets skip preparation;
omit selectors to preserve their saved routing. Missing explicit `--config` and
partial targets require deliberate repair, not automatic setup/resume. An absent
preview defers staging-dependent checks; planned, prepared, activated and
live-qualified remain distinct. Public setup expresses scheduling intent and starts
by default, subject to the same technical checks as start. A failed check reports
the blocker, not a silent prepare-only result. Use `setup --prepare-only` for non-activating preparation
(direct Python helper `setup` stays unchanged). Public `--resume-setup` requires
`setup --prepare-only --resume-setup`; otherwise reject before mutation and show
that corrected command with the original arguments. Status inspects
configured harness/slots separately from process/observed-unit evidence, and stop
drains without killing workers. See the [lifecycle reference](../skills/orbi/references/lifecycle.md#start).

Both planners use the pinned Autoresearch planning method and shared
[planning craft](../skills/shared/PLANNING-CRAFT.md). They save decisions in their
existing document owners and executable plans as GitHub Issues, not local task
stores. A clear task needs no interview. Resolve consequential choices and run a
builder check before publishing the full batch under
[Plan Handoff](../skills/shared/PLAN-HANDOFF.md): native `blockedBy` dependencies,
optional `ai-epic` coordination, readback and `ai-ready` last.

`/plan_with_me` asks the highest-impact unresolved intent question, researches
repository facts itself and marks guesses. A bare "yes" or LGTM accepts the clear
recommendations in the latest round, including a batch; only genuinely ambiguous
choices need clarification. `/plan_for_me` investigates and chooses
within delegated scope without an interview. Both reuse accepted answers and
existing issues. Questions-only/read-only/no-write/dry-run requests save nothing,
locally or on GitHub. Explicit no-dispatch requests retain `ai-planning`; ordinary
writable planning can publish work an existing Orbi deployment consumes immediately.
Neither planner implements or starts a service.

After a state-machine analysis, grill discussion, bug harvest or UI review, invoke
`/plan_for_me` to turn the conversation's concrete findings into scoped GitHub
Issues. You do not need to paste the report again. Both planners reuse accepted
answers and current evidence, skip completed fixes, and keep unsupported proposals
separate. Distinct buildable outcomes become separate issues, not one ticket per
message or one giant ticket for the whole conversation.

Before publication, chat shows a **Plan preview**: each proposed issue's title,
observable change, acceptance signal and dependencies, plus reused issues and held
questions. After publication, the receipt replaces proposed keys with verified
links and ready/waiting/held states. The preview is not another approval round.
Use `/plan_for_me preview only, no writes: plan these findings` to inspect without
publishing. Planning never claims that a ready label proves Orbi pickup or delivery.
See [conversation intake and preview](../skills/shared/PLAN-HANDOFF.md#conversation-findings-to-issues).

`/plan_for_me` with no concrete objective in either the request or relevant
conversation starts project discovery instead of asking you for a goal. It reads the
repository's accepted intent, code, tests and task history, separates accepted and
derived engineering goals from new product proposals, and saves only the highest
value executable frontier. It does not promote a speculative feature into runnable
work or invent a roadmap for a project with no accepted objective. An explicit
outcome keeps focused planning; `read-only` writes nothing; an Orbi-owned
substep returns to its same coordinator and named issue. Repeated invocations reconcile the last plan and
changed evidence, so unchanged inputs add no duplicate tasks or empty planning
commit. The [discovery protocol](../skills/plan-for-me/references/discovery.md)
defines the evidence labels, gap classes and report.

For example, type `/docs_sync update the architecture documentation` in Hermes
CLI chat, or `/git_commit_push only src/; no push` in Telegram. Arguments are
passed as text to the skill, never executed as a shell command by the plugin.
These are conversational slash commands, not new `hermes <skill>` shell
subcommands. The agent loads the skill through `skill_view` and performs its
instructions using the current conversation and tools.

Bundled skills also remain available by their qualified names, such as
`kit:docs-sync`. Supporting files stay next to their `SKILL.md`. Shared contracts live in
[`skills/shared`](../skills/shared/COMMON-CONTRACT.md), alongside the skill folders;
the legacy skill copier preserves that support directory too. Resolve helper
commands from the loaded bundle rather than assuming `~/.hermes/shared-skills`.
An existing built-in or previously registered plugin command wins a name
collision; the skipped alias produces a warning and the qualified skill remains
available. Choose distinctive names to avoid collisions with other plugins,
local skills, and configured quick commands.

Public skill names match the workflow names. Source directories stay stable for helper links:

| Primary command | Public skill ID | Compatibility command |
| --- | --- | --- |
| `/plan_with_me` | `plan-with-me` | None |
| `/plan_for_me` | `plan-for-me` | `/autoresearch:plan` (CLI), `/autoresearch_plan` (Telegram); runs the Autoresearch skill's plan protocol with the same planning adaptations |
| `/docs_sync` | `docs-sync` | None |
| `/update_kit` | `update-kit` | `/update-kit` (same literal arguments) |

Grill Me is the challenge mode of Plan With Me; its old command still works but
is not advertised as a separate plugin skill. Autoresearch protocols remain
accessible through their commands and the Plan For Me adapter. Autoresearch compatibility command
spellings remain typeable but are deliberately omitted from Telegram menu
advertising, not merely displaced by capacity. Plan With Me and Docs Sync do not
register the old repo-interview or repo-docs aliases. The Telegram menu prioritizes
the three current planning/documentation workflow commands, then `/ui_taste`, `/beautify_github_readme`,
`/impeccable`, `/lgtm` and `/git_commit_push`.
Hermes' default menu holds 60 entries and its built-ins alone exceed that, so each
prioritized command displaces the lowest-ranked built-in (currently `/yolo`,
`/approvals`, `/fast`, `/voice`, `/busy`, `/memory` and `/bundles`), which stays
typeable. Do not rename helper paths or saved receipt keys for presentation. Autogoal references in migration code preserve old state;
they do not register a live command. Hindsight is not a bundle integration; its
negative tests prevent accidental reintroduction. Updating source does not refresh
an already-running gateway's command registry: use supported plugin reload and
verify activation before claiming the new names work in messaging.

Docs Sync and retained fix/apply modes decide routine engineering choices autonomously within the
accepted scope. The executing session (or an optional authorized delegate) works
from the selected task, accepted decisions, scope, checks
and completion rules. For a concrete method gap or explicit request, they select one
[Addy protocol](../skills/engineering/REFERENCE.md). The executing workflow retains authority;
protocols supply techniques within its contract. Handoffs record methods that
materially changed a decision or artifact, with their check results.
Missing owner intent or authority remains an explicit question;
loading a skill alone is not proof of applying it.

The [engineering cycle](../skills/shared/ENGINEERING-CYCLE.md) is an optional routing
reference when method selection is unclear. A ready task needs no routing prepass.
A documentation-only `/docs_sync` request does not launch workers. To continue
through a spec, publish complete issues for Orbi. Already-authorized fix/apply modes preserve
their stated scope and actual ownership.
Manual implementation includes authorized recovery and closeout. Review acceptance and
executed evidence precede canonical closure; no push or deployment is implied.
Skill availability and support files are checked at use time; a missing skill is
reported with its safe fallback, not silently treated as loaded.

At verified closeout, assess the actual diff, issue acceptance and affected docs.
Update current behavior and operating instructions where needed; report remaining
documentation gaps with their resume condition. GitHub issues, PRs, checks and
reviews retain delivery evidence. A docs pass is not worker execution, merge or
live acceptance, and no retired executor report schema is required.

## Autoresearch

The bundle vendors [uditgoenka/autoresearch](https://github.com/uditgoenka/autoresearch)
v2.2.2 at the revision in [UPSTREAM.json](../skills/autoresearch/UPSTREAM.json), with
its MIT license and runtime scripts. Installing the bundle makes it available in
every configured profile; no separate Claude/Codex installation is required.

Use `/autoresearch` for goal routing or a metric-driven loop. All 13 upstream
subcommands are available:

`plan`, `debug`, `fix`, `security`, `ship`, `probe`, `scenario`, `predict`,
`reason`, `learn`, `improve`, `evals`, `regression`.

Use `/plan_for_me` in CLI or Telegram for planning. Legacy `/autoresearch:plan`
and `/autoresearch_plan` remain available. Other subcommands retain their names:
for example, `/autoresearch:debug` in CLI and `/autoresearch_debug` in Telegram.
`/autoresearch plan ...` also works. Autoresearch compatibility commands, including
the base and underscore spellings, are intentionally not advertised in Telegram's
menu; type the desired command with its request text. This is separate from the
menu capacity limit and does not remove the typed handlers. Existing command
owners keep precedence.

```text
/plan_for_me reduce cache latency; document findings and schedule tasks; do not implement yet
/autoresearch Goal: reduce parser time Scope: src/parser Metric: milliseconds Verify: python bench.py Iterations: 10
```

GitHub Issues own executable plans and progress. Autoresearch persists accepted
findings through [Plan Handoff](../skills/shared/PLAN-HANDOFF.md); do-not-implement
still permits that planning handoff, while explicit read-only/chat-only/no-write
or dry-run writes nothing. Existing legacy records stay migration evidence.
Retained authorized implementation never uses the removed executor.

The [Hermes adapter](../skills/autoresearch/SKILL.md) connects research to docs-sync:
findings update existing documents, matching issues are reused, and accepted gaps
become complete issues with outcome, scope, acceptance, verification and native
dependencies. Publication does not create a timer or activate Orbi. Read-only
and planning-only requests remain scoped.
Upstream flags and analytical methods are retained; host-specific tools, generic
confirmation prompts, experimental Git handling and documentation handoffs follow
the adapter. Claude-only hooks are not installed.

Retained Hermes terminal maintenance names and private state identities do not restore the removed runner.

## State machine

[State Machine](../skills/state-machine/SKILL.md) maps lifecycle rules scattered
across functions, fields and services. It reports state predicates, transition
rules, source-backed counterexamples and coverage gaps, then publishes all supported,
buildable, uncovered outcomes in the same invocation through
[Plan Handoff](../skills/shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff).
It reconciles existing/owned work, groups findings that share a fix, previews in chat
without waiting for selection or approval, reports verified issue links and stops.
The default route neither repairs code locally nor starts Orbi.

| Host | Invocation |
| --- | --- |
| Hermes | `/state-machine` |
| Claude Code | `/kit:state-machine` |
| Codex | `$kit:state-machine` |
| Pi | `/skill:state-machine` |

In Pi, this is a native skill command, not a `/state-machine` extension alias.
After updating the installed package, reload skills in the host before use.

```text
/skill:state-machine inspect checkout retries and cancellation
/skill:state-machine find all implicit state machines in this app; no writes
/skill:state-machine inspect checkout retries and cancellation; report only
```

Each actionable finding needs the trigger, initial and resulting state, violated
invariant, source location and regression sequence. Undecided product rules are held
with the missing input; independent qualifying findings continue. Zero qualifying
findings means zero new issues. Explicit report-only, read-only, no-write or dry-run
returns findings inline with no GitHub, document or scratch writes. No-dispatch,
ownership, pauses and human-only gates still apply. Publication failures use Plan
Handoff's unsaved/partial receipts and reconciliation, not a replacement queue.

### Publish contextual findings

After a state-machine report, a bare Bug Harvest invocation in the same conversation
uses its findings as the bounded publication scope. In Pi:

```text
/skill:bug-harvest
```

Hermes also accepts `/bug-harvest`, Claude Code uses `/kit:bug-harvest`, and Codex
uses `$kit:bug-harvest`. No finding IDs, copied report or extra prompt are required:
the [contextual handoff](../skills/bug-harvest/SKILL.md#findings-from-the-preceding-response)
reuses the state map and evidence, then verifies each defect's reproducer,
observed/expected behavior, impact and regression check. It does not start local
repairs, and it reconciles any issues already published by State Machine.

An ordinary `/bug-harvest AREA` likewise analyzes and publishes in one invocation.
Bug Harvest reconciles existing work, groups shared fixes and publishes every
supported, buildable, uncovered outcome through Plan Handoff. The preview does not
wait for approval: native dependencies precede `ai-ready`, and verified issue links
end the invocation. Uncertain findings are held with reasons while independent work
continues. Zero qualifying findings means zero new issues.

Explicit report-only, no-write or dry-run returns findings inline without writes.
Explicit no-dispatch, ownership and human gates remain binding; a prior read-only
analysis does not by itself impose a continuing no-write limit. Publication does
not activate Orbi or prove delivery.

### Explicit local fixes

An explicitly requested and authorized fix/apply mode uses Bug Harvest with the map
and findings as its bounded repair scope in that invocation, separate from default
issue publication. To request repairs after a report, explicitly name the fix mode:

```text
/skill:bug-harvest fix these findings locally
```

The [authorized local fix branch](../skills/bug-harvest/SKILL.md#authorized-local-fixes)
verifies and fixes candidates one at a time, adds regression protection and runs
affected checks. It preserves ownership, review, PR and human-only gates, and does
not automatically commit or push. Explicit continuing user no-write and live-action
restrictions remain binding.

Planning, implementation and review use the shared contract's stateful-work trigger.
Bug Harvest, architecture review and Test Optimizer also link the
[analysis method](../skills/state-machine/PROTOCOL.md) at their relevant steps.
These are scoped reference loads, not automatic skill activation or wider authority.
The [online sources and example](../skills/state-machine/references/sources-and-example.md)
explain the method. Offline packaging checks do not prove exhaustive discovery or
live bug-finding effectiveness.

## Test optimizer

`/test-optimizer` finds justified reductions in executed cases, test code and maintenance cost
and publishes GitHub issues for Orbi in the same invocation.
It reuses the existing [test-suite optimization protocol](../skills/engineering/local/test-suite-optimization/PROTOCOL.md).
Prioritize deleting proven redundant, vacuous and obsolete tests, then shrink the
remaining fixtures and cases. A constant assertion such as `assert 0 == 0` needs
no replacement when the whole test protects no product contract. Preserve distinct
supported risks, not test counts. Rare security, data-loss and named regression
cases are not expendable merely because they rarely fail. Unchanged code or tests
unrelated to today's diff are not automatically obsolete.

A bare invocation analyzes the requested/current scope without editing tests. It
uses [Plan Handoff](../skills/shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
to reconcile existing work, preview without waiting, publish supported uncovered
outcomes and report verified links. It holds uncertain findings and continues
independent work; no qualifying findings means no new issues. Each proposed removal
names its retained equivalent detector and oracle, retired obligation or evidence
of no owned contract/invariant.

Explicit report-only/read-only/no-write/dry-run returns findings inline with no writes.
Only explicitly requested and authorized local fix/apply uses a separate supported
batch with existing ownership, review, PR and human gates. No-dispatch and pauses
remain binding. The default route does not implement findings or activate Orbi.
Actual reductions and measured runtime stay separate from proposals and unknowns;
neither mode silently skips tests or weakens CI.

Examples (Hermes CLI; Pi uses `/test-optimizer`, Claude Code
`/kit:test-optimizer`, Codex `$kit:test-optimizer`):

```text
/test-optimizer tests/parser
/test-optimizer tests/parser; report only
/test-optimizer tests/parser; apply one batch; no commit or push
```

The [skill](../skills/test-optimizer/SKILL.md) defines the rare-scenario evidence
gate and before/after receipt. Offline packaging and decision probes do not
establish a measured suite speedup or live host effectiveness.

## Graphify

`/graphify` maps a project into a local knowledge graph, then answers questions
against `graphify-out/graph.json` instead of long file reads. Hermes uses the
official skill that its plugin installer adds from
[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify); Claude Code,
Codex and Pi load the local [adapter](../adapters/skills/graphify/SKILL.md).

The adapter requires the `graphify` command (PyPI `graphifyy`, Python 3.10+) and
never installs it, adds hooks or asks a model for a semantic pass. It reuses a graph
whose commit matches the current revision or whose queried nodes no changed file
touches, or builds code-only output into an ignored directory, then verifies the
file, node and link counts, schema and tool version. One shared graph serves a
repository; later readers query it instead of rebuilding. `explain`, `path`,
`affected`, `query` and `god-nodes` accept the usual exit codes `0`, `3` (several
candidates) and `4` (no match).

A graph is never perfectly current, so the adapter reports `graphify_fresh`,
`graphify_stale`, `graphify_partial` or `graphify_unavailable` and says which reuse
condition the state rests on. Only `graphify_fresh` supports a topology claim without a
live-source check. The vocabulary is one home in the
[shared contract](../skills/shared/COMMON-CONTRACT.md#graph-state).

A graph is orientation. `EXTRACTED` edges are explicit in the source and `INFERRED`
edges are resolved by Graphify; neither is runtime proof, and absent inbound edges
never prove dead code. Unused Code keeps its own proof rules and uses the graph only
to rank candidates. Unused Code, Bug Harvest, Improve Codebase Architecture, Split
Folder and Test Optimizer record that declared state; other skills do not need a
graph and pay nothing for its absence. `graphify-out/` is a generated artifact and stays uncommitted.
A read-only request builds nothing.

Examples (Hermes CLI; Pi uses `/graphify`, Claude Code `/kit:graphify`, Codex
`$kit:graphify`):

```text
/graphify src/parser; explain parse_statement; read-only
/graphify this repository; who calls validate_config; no commit
```

Link and packaging checks do not qualify a live graph build, dead-code finding or
model behavior.

## Repository instruction reconciliation

[Agents MD Generator](../skills/agents-md-generator/SKILL.md) owns instruction-chain
inspection, source evidence and reconciliation. Writing For Agents owns wording
and structure and is applied by reference, not copied into a second method.

From the target repository in Pi:

```text
/agents-md-generator
/agents-md-generator audit
/agents-md-generator update only src/AGENTS.md
```

Bare invocation inspects the whole applicable chain and directly revamps both root
`AGENTS.md` and `CLAUDE.md` end to end, creating missing instructions as needed.
It can reorganize, consolidate or remove sections without a mode menu, diff approval
or follow-up. Valid requirements and compatible shared ownership survive, not the
old layout. A working symlink stays intact; it never grants writes outside the target.
Explicit `audit` or any read-only restriction returns findings and proposals inline
with no writes, including scratch, reports, issues or cache-writing tests. `update`
edits the requested scope without a second confirmation.

Inspect applicable ancestor/nested instructions, overrides, compatibility files,
commands, CI, generated ownership, source boundaries and maintained docs first.
Give each material rule a keep/update/move/remove/unresolved disposition with evidence
and reason. Preserve intended maintainer policy even when source disagrees; hold
conflicts with the precise question and continue independent accepted work.
There is no fixed length quota. Verify referenced paths/commands and separate checks
inspected, run and unrun. Report the actual diff and dispositions inline, not in a
permanent audit log. [Host spellings and package boundaries](cross-host.md#repository-instruction-reconciliation)
include Hermes and explicit external target use.

During ordinary delivery, read the committed
[same-PR maintenance procedure](../skills/shared/AGENT-INSTRUCTIONS.md) only when
accepted work changes an instruction-bearing fact. Reconcile affected guidance in
the same PR; no affected guidance means no instruction edit. This is not a routine
full audit or automatic skill invocation. Full cleanup requires explicit generator
scope. Existing ownership, pauses, acceptance and PR/review gates remain.

## Writing for agents

`/writing-for-agents` applies mattpocock's skill-writing reference, the skill formerly
called `writing-great-skills`. Use it to write or prune a skill, an `AGENTS.md` or a
document an agent reaches through a pointer. Claude Code uses
`/kit:writing-for-agents`, Codex `$kit:writing-for-agents` and Pi
`/writing-for-agents`.

The pinned [reference](../skills/writing-for-agents/upstream/PROTOCOL.md) owns the
technique: pointer wording and branches, context and cognitive load, the information
hierarchy, completion criteria, leading words, positive instruction, progressive
disclosure and pruning of no-ops. [Skill mechanics](../skills/writing-for-agents/upstream/SKILL-MECHANICS.md)
answers only the skill-specific questions: model- versus user-invocation and router
skills. The local [adapter](../skills/writing-for-agents/SKILL.md) adds Kit scope,
GitHub issue authority, review and delivery limits.

Editing a document is not new authority. Keep every tested contract, move text
instead of rewriting meaning, and report lines removed with the tests you ran.
Offline link and packaging checks do not qualify model behavior.

## Brand identity and design systems

These commands run only when selected. `/ui-taste` remains the default for UI
work that names no design skill. Claude Code exposes `/kit:brand-identity` and
`/kit:styleseed`; use `$kit:brand-identity` or `$kit:styleseed` on Codex.

- [`/brand-identity`](../skills/brand-identity/SKILL.md): start with a brief or
  an approved identity. Compare directions before choosing; the final PDF,
  logo files and tokens come from the chosen set only. The operation-specific
  preflight checks Python, Chromium and local font inputs without installing them.
- [`/styleseed`](../skills/styleseed/SKILL.md): start with the project design
  contract, compile effective rules and tokens, and inspect the selected artifact.
  The 22 workflows are internal to one skill. The bundled compiler uses `--agent pi`
  or `--agent hermes` on those hosts. The preflight verifies the pinned runtime and
  checks Playwright Chromium and its encoder only if the operation needs them.

Prepare any missing prerequisite explicitly and rerun the reported check. A
successful preflight or compile does not prove a render or a model outcome.

## UI findings

Bare `/impeccable` and `/ui-taste` invocations analyze the current flow and publish
supported, uncovered outcomes through the [shared UI handoff](../skills/shared/UI-FINDINGS.md),
then stop. They reuse existing issues across both skills, with screen/state evidence
and repeatable acceptance; unaccepted visual preferences stay held. Captures are not
attached by default. Explicit design/edit requests retain their playbooks and delivery
gates. Read-only/dry-run/no-write returns inline findings without saving; unattended
runs remain audit-only unless the accepted scope authorizes writes. No-dispatch
keeps published issues undispatched.

## Visual reference workflows

| Command | Example | Result |
| --- | --- | --- |
| [`/forever-components`](../skills/forever-components/SKILL.md) | `/forever-components Find a lightweight CSS loader and adapt it to our tokens` | Shortlist up to three matches; retrieve selected sources with their provenance and notices |
| [`/tastemaker`](../skills/tastemaker/SKILL.md) | `/tastemaker study screenshot.png` | Composition and measured palette from a supplied reference |
| `/tastemaker` | `/tastemaker audit src/page.html` | Ranked findings without edits, issue publication or taste-memory changes |
| `/tastemaker` | `/tastemaker compositions two hero directions` | Inline briefs, not generated images |
| [`/dembrandt`](../skills/dembrandt/SKILL.md) | `/dembrandt review this form against DESIGN.md` | Advice from the relevant entries in the [45-topic index](../skills/dembrandt/references/corpus.md) |
| `/dembrandt` | `/dembrandt extract https://example.com` | Measured tokens from an authorized page, without installing tools or applying exports |

For Forever, use `/kit:forever-components` in Claude Code and
`$kit:forever-components` in Codex. Search uses the local index and Python 3.9+
without a network connection. Retrieval needs access to the pinned GitHub source;
adaptation uses the project's browser checks, not the catalog's accessibility labels.

Use `/kit:tastemaker` and `/kit:dembrandt` in Claude Code, `$kit:tastemaker`
and `$kit:dembrandt` in Codex, and bare slash commands in Pi and Hermes. The
workflows load only after selection; `/ui-taste` remains the unnamed UI default.
Project branding, tokens, frameworks and motion constraints take precedence.

Reading the references needs no runtime. Tastemaker's local helpers need Python 3;
image palette extraction also needs Pillow. Dembrandt site extraction needs an
already connected Dembrandt MCP server, matching Chromium and the site's loaded
fonts for typography evidence. Each workflow checks its own prerequisites and
reports missing ones without installing anything. The linked wrappers identify the
commands, repair paths, source pins and MIT notices.

## Motion workflows

| Command | Example | Result |
| --- | --- | --- |
| [`/genjutsu`](../skills/genjutsu/SKILL.md) | `/genjutsu specify enter and exit motion for this drawer; no edits` | A brief grounded in the existing stack, including the reduced-motion behavior |
| [`/motion-graphics`](../skills/motion-graphics/SKILL.md) | `/motion-graphics check ./motion.html, a 640×360 two-second loop; sample 0.37s and 1.28s` | PNGs from direct seeks, with repeatability, matching loop endpoints and visible change checked |

Use bare slash commands in Pi and Hermes, `/kit:genjutsu` and `/kit:motion-graphics`
in Claude Code, or `$kit:genjutsu` and `$kit:motion-graphics` in Codex.
The commands load only on selection; `/ui-taste` is still the unnamed UI default.
Genjutsu uses the current host's capabilities; team workflows need both user scope
and a delegation tool. A motion brief needs no browser or encoder.

For timeline rendering and optional export, see [capture prerequisites and
commands](../skills/motion-graphics/references/capture.md). Kit does not install
missing dependencies, change project design constraints or qualify model behavior
or device performance.

## Procedural browser 3D

Use [`/open-3d`](../skills/open-3d/SKILL.md) explicitly for a procedural scene,
exploded view, scroll film or scene capture. Use `/kit:open-3d` in Claude Code,
`$kit:open-3d` in Codex and `/open_3d` in Telegram. The eight upstream protocols
are references, not separate commands. Keep the project's own stack and design
constraints. [Preflight and capture](../skills/open-3d/references/runtime.md)
explain the read-only requirements, viewport checks and time-zero MP4 workflow.
Encoded fps describes the file, not device performance.

## Responsive screenshots

`/responsive-screenshots` captures one or more pages at chosen viewport widths and
reports what each capture proves: the file, its real pixel size, whether the page
scrolls horizontally, console errors and failed requests. Its bundled
[capture script](../skills/responsive-screenshots/scripts/capture.py) drives the
installed Playwright library, so it works on every host without host-specific browser
tools.

Standard widths are `375x667`, `768x1024` and `1440x900`; `--scheme both` adds a dark
capture. Each capture fixes the viewport, device scale and reduced motion, waits on
network idle, an optional selector and document fonts rather than a fixed sleep, and
writes `report.md` plus `captures.json`. Exit status is `0` captured, `1` a capture
failed, `2` a usage refusal or horizontal overflow under `--fail-on-overflow`.

The workflow installs nothing, refuses URLs with embedded credentials, keeps captures
out of Git unless the request publishes them, and leaves design judgement to
`/ui-taste` or `/impeccable`. A capture file proves a render happened, not that a layout
is correct.

```text
/responsive-screenshots src/app preview at 375x667 768x1024 1440x900; both schemes
/responsive-screenshots https://staging.example.com/pricing; fail on overflow
```

## Ask Kit

`/ask-kit` is the map over this bundle: one router that names the skill for a
situation and the next step it implies. It answers "which command do I want?", never
"what does that command decide?". It reads the chosen skill before describing it, names
one command, and sends you to that skill's `## Boundaries` when two look close.

The main flow is `/grilling` (or `/grill-with-docs` in a repository, `/grill-me` for an
existing plan), then `/plan-for-me` or `/plan-with-me` to publish GitHub Issues,
then Orbi delivery. `/git-commit-push`
handles separately authorized local publication. On-ramps cover a bug (`/bug-harvest`), a bloated suite
(`/test-optimizer`), dead code (`/unused-code`), a folder split
(`/split-folder`), shallow modules (`/improve-codebase-architecture`), a held
queue (`/unblock` within its recovery scope), drifted docs (`/docs-sync`) and measured research
(`/autoresearch`).

The router grants no authority. Scope, review gates, publication and live operations
keep their own rules, and a map is not a substitute for the skill it names.

## Grilling and architecture review

Three pinned mattpocock/skills references now run on every host.

`/grilling` is the interview engine: a design tree, a frontier of decisions whose
prerequisites are settled, one numbered round per frontier with a recommended answer
for each question, and an empty frontier as the done condition. Facts are the agent's
job; decisions are the owner's.

`/grill-with-docs` runs that interview for a plan or design, then records what it
settles: an ADR for a decision with alternatives and a reason, a glossary entry for a
named concept or resolved ambiguity. It follows Docs Sync for the write rules.

`/improve-codebase-architecture` uses Graphify for scoped discovery and Ponytail to
challenge shallow modules, leaking seams, duplicated rules, concrete bugs and measured
performance costs. It verifies graph leads in source and ranks defects before structural
waste. The architecture publication pilot uses the shared
[single-invocation specialist handoff](../skills/shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff):
one ordinary invocation analyzes and publishes warranted GitHub Issues, previews in
chat without waiting for selection or confirmation, reports links and stops. It
requires affected callers, failure or measured cost, the smallest compatible fix,
risk and a check. Existing/owned work is reconciled; uncertain findings, speculative
refactors and unresolved ADR decisions stay held with reasons while independent work
continues. No qualifying findings means no new issues. Other skills' defaults do not change.

Writable modes also produce a temporary HTML report, never a governing issue source.
Explicit `report only`, `read-only`, `no-write` or `dry-run` returns inline findings
without GitHub, document or scratch writes. Missing Graphify falls back to native
search. Default publication does not implement findings or activate Orbi; no-dispatch,
ownership and human gates still apply. Explicit `fix`, `apply`, `patch` or `optimize`
requests instead implement one bounded finding within the skill's accepted scope,
with regression evidence, affected checks and Ponytail review in the existing review
lane. Unresolved design or ADR choices still need a decision; no new
commit, push or deployment authority is implied.

Examples (Hermes CLI; Pi uses the same hyphen names, Claude Code prefixes
`/kit:`, Codex prefixes `$kit:`):

```text
/grilling the retry design; recommend answers; read-only
/grill-with-docs the cache plan; record ADRs; no commit
/improve-codebase-architecture src/runner
/improve-codebase-architecture src/runner; report only
/improve-codebase-architecture src/cache; fix the highest-severity verified finding; no commit
```

Grill Me remains Plan With Me's challenge mode; it loads Grilling for the mechanic and
adds only the plan-specific question branches. Offline link and packaging checks do not
qualify a live interview or a rendered report.

## Pinned engineering reference

The engineering pack is a **reference**, not a command: there is no `/engineering`
entry in Hermes, Claude Code, Codex or Pi. Work, Docs Sync and Autoresearch read
it on demand; ready tasks need no separate invocation. Select a technique when a
method gap is concrete:

```sh
python3 "<toolset>/skills/engineering/scripts/route.py" --protocol performance-optimization
python3 "<toolset>/skills/engineering/scripts/route.py" --protocol code-review-and-quality
```

The [reference](../skills/engineering/REFERENCE.md) provides 25 pinned protocols and
their shared references. Its router's `--protocol NAME` selects exactly one method;
explicit phase commands remain available as optional bundles. Both modes verify
selected protocol and shared reference hashes. It translates upstream plan/task
paths into existing task records and preserves prior authorization,
explicit restrictions and actual review requirements. Its protocols are not extra
workers or independently registered slash commands. See [provenance and updates](dependencies.md#refresh-the-pinned-engineering-pack).

### Automatic planning during execution

Planning resolves consequential design, dependency and product choices and saves
an executable issue with scope, decisions, acceptance and checks. The existing execution owner implements
that task without another permission round: choose reversible details, implement,
test, repair and finish authorized closeout. It can adapt a failed implementation
on the same task while preserving accepted behavior and checks.

Only a newly discovered consequential choice or missing decomposition invokes
bounded Plan For Me, automatically and within existing authority. Save the decision
in the current GitHub issue and resume only within the same accepted scope. Known recovery steps,
ordinary candidate changes and debugging stay in execution. Named task-family
scope, no-commit restrictions and live ownership remain. A planning receipt is not
proof that a worker ran or a task completed.

### Direct repository execution

Retained fix/apply modes implement only their accepted scope. GitHub Issues own
scope and native dependencies. Coordinate actual ownership, use isolated task
worktrees under the canonical `.worktrees/`, run affected checks and required
review and PR gates, and preserve candidates/recovery evidence. No retained skill
is a replacement implementation coordinator.

### Parallel workers

Dispatch every delegated worker in a fresh context with explicit scope, completion
criteria and write authority. Do not activate Orbi as part of delegation or start
a second implementer for an already-owned issue.

### Delivery batches and partial completion

Explicit manual work executes one coherent outcome in the current session: connected consumers,
runners and tests share a batch when their dependencies and authority permit it.
One useful slice is not a one-file limit. The coordinator chooses routine batch
boundaries and reuses valid exact-source evidence where repository policy allows;
required review and changed-input checks still run. Use the current
[shared completion contract](../skills/shared/DEFINITION-OF-DONE.md), not retired executor protocols.

A delivered slice is reported by its behavior and commit/integration stage, with
parent status and remaining acceptance separately. An open parent is not evidence
of zero progress. These rules do not promise a completion rate or eliminate real
worker, live-environment or runtime constraints.

### Planning without repeated setup

Plan With Me asks only unresolved user choices; Plan For Me resolves the specific
engineering uncertainty; Docs Sync persists the affected batch. They share the
[single-pass handoff](../skills/shared/PLAN-HANDOFF.md#one-planning-pass-one-handoff).
Orbi or an explicitly authorized manual session consumes the saved issue contract
and verifies current source and actual ownership before implementation. No changed
evidence means no repeat planning/docs pass. An unanswered choice holds only its
affected work. Standalone planning does not implement or start services.

Record repository obligations, bounded paths, exact checks and governing sources
in each issue. Builder review resolves consequential gaps before readiness. Publish
the full batch and native dependencies before `ai-ready`; an epic coordinates
children and never executes. Explicit pauses, live ownership, CI, sensitive-change
controls and human-only gates remain binding. See the
[publication and pause policy](../skills/shared/PLAN-HANDOFF.md#publication-and-dependencies).
No local-main planning commit, local task-store admission or legacy lease is required.

### Planning-only bulk handoff and skill recommendations

Both planners prepare complete issue batches rather than drift into implementation.
The [artifact and authority contract](../skills/shared/RESEARCH-PLAN.md#planning-artifact-and-authority-contract)
owns writable outputs and standalone/coordinator boundaries. The
[planning craft](../skills/shared/PLANNING-CRAFT.md) owns question quality, decision
closure, decomposition, source-backed scope and supporting-skill recommendations.

Inventory every requested outcome, reuse existing issues and decisions, preserve
independent lanes and record real prerequisites as native GitHub dependencies.
Keep only unresolved work under `ai-planning`, with its missing input and resume
condition. A supporting skill cannot widen scope, authorize implementation or
create a second coordinator. Required capabilities follow actual acceptance;
optional methods have scoped fallbacks. Planning installs no external skill.

The [behavioral specimens](../tests/fixtures/planning/README.md) define checks for
standalone planning, full batches, questions-only scope, prior unrelated authority,
later explicit implementation and return to the same execution coordinator.
Inspect actual tool actions, writes, complete issue bodies and dependency readback,
not just wording or wrapper registration. Earlier local-task fixtures are historical
evidence, not qualification of the GitHub handoff. Installed host/model behavior,
recommendation application and Telegram delivery still need their own live proof.
Preserve unresolved acceptance from the
[original planning requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/workflows.md#planning-only-bulk-handoff-and-skill-recommendations);
they are not instructions to resume executor development.

### Source names and compatibility

Docs Sync lives in `skills/docs-sync/`; Plan With Me lives in
`skills/plan-with-me/`. Neither workflow registers legacy command aliases.
Retired host-local worker snapshots are not installed, packaged or registered as skills.

Plan For Me lives in `skills/plan-for-me/` and is registered as its own skill.
It applies the pinned planning protocol from `skills/autoresearch/`, which remains
the separate Autoresearch skill and protocol suite. `/plan_for_me` selects planning;
`/autoresearch` selects the research router. Non-planning protocols remain available.
Legacy worker receipt fields remain preserved evidence, not current interfaces or
additional commands.

## Tasks query skill

Use GitHub Issues/PRs and existing read-only Orbi status for backlog inspection. Legacy local
records are preserved migration evidence. The [earlier task-query requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/workflows.md#tasks-query-skill)
retain unresolved obligations; their executor interfaces no longer ship.

## Telegram reporting qualification

Status: Accepted

The existing reporting requirement and TOOLSET-011 retain the requested Telegram
destination and separate setup confirmation, actual execution and scheduled
message delivery. Verify one setup confirmation in the intended chat/topic and
attributable scheduled execution/delivery on the original host/profile/job.
Setup or command registration alone cannot close that qualification. Preserve the
owner's stop-all instruction: this scope creates no replacement job, immediate run
or permission to resume a schedule.

## Scheduling behavior

Existing job IDs, settings, schedules,
pause state and recovery evidence remain intact.
Setup confirmation, actual execution and message delivery require separate evidence;
a changed prompt or installed skill proves none of them.

## Removed executor interfaces

The TUI, web UI and Paseo executor plugin are removed. Their
[prior interface and qualification requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/workflows.md#tui-confirmation-layout-and-refresh)
remain immutable evidence. Physical-client, transport and model qualification
are not satisfied by removal and must be reconciled if needed by the successor.
