# Commands and repository workflows

GitHub Issues own executable work; Orbi owns delivery. Kit plans and supplies
explicit skills. **pi-autowork is retired and unsupported**: do not develop or
restart it. See [support, setup and migration](github-native.md).

## Unblock repairs blocked GitHub work

`/unblock` diagnoses GitHub issues, PR/check failures and actual ownership. It
repairs authorized local causes within its own recovery scope; it never revives the removed
executor or enables paused Orbi. See [Unblock](../skills/unblock/SKILL.md).

## Bundled Ponytail

All workflows apply the [shared Ponytail method](../skills/shared/PONYTAIL.md)
within their existing authority. `/ponytail [lite|full|ultra|off]` reports or changes
only the conversation's Kit preference. `/ponytail-review`, `/ponytail-audit`,
`/ponytail-debt`, `/ponytail-gain` and `/ponytail-help` are one-shot reports;
they do not implement, publish, start an extra reviewer or change persistent modes.
See [portable host invocations](cross-host.md#bundled-ponytail-on-every-host).
Existing external command owners keep their handlers; the bundled skills remain
available as `kit:ponytail` and `kit:ponytail-review` (and the other names).

All workflows inherit the [shared freshness and ownership contract](../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership).
Read-only/audit/questions/dry-run never fetch or mutate Git. Writable planning may
read fresh GitHub metadata/remote source, but does not sync or commit the checkout.
Implementation verifies baseline/ownership and isolates stale/shared source;
delivery/sync follows the invoked command's scope and caller restrictions.

`/push` saves every change, pulls `main` and pushes `main` without a second approval
round. It inventories local worktrees and paginated GitHub issue/PR evidence, including
remote-only Orbi work. Already-merged changes enter through verified upstream; passing
open PRs remain with their Orbi coordinator. Closed-unmerged, failed, paused and
unknown work stays untouched with its URL, reason and next action. Uncommitted changes
are committed before the pull, because they block a safe fast-forward. A stale base is
reconciled through normal merge and affected checks/review before publication, and the
repository's landing route (direct push or pull request) is used as policy allows. API
failures mean partial inventory, not an empty backlog; independently verified work may
proceed, but missing required protection/review holds publication. Receipts separate
local commits, incoming landed changes, pending URLs, source and selected/final SHAs,
checks, remote inclusion and remaining local synchronization.
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
| `/orbi [status\|setup\|start\|stop\|help]` | `/orbi` | [Repository-scoped lifecycle controls](../skills/orbi/SKILL.md): bare status is read-only, setup prepares without activation, authorized start prepares if absent then schedules, stop drains without killing workers; Linux controls, macOS status-only; help prints the action reference read-only on any platform |
| `/git-commit-push` | `/git_commit_push` | Commit, pull and merge upstream, then push scoped changes (`no pull` or `no push` narrows it); `pull`, `sync` or `merge <branch>` only integrates |
| `/git-commit-push all` | `/git_commit_push all` | Also merge every finished worktree into the base branch: inventory first, merge only eligible clean unmerged ones, keep owned, unknown, dirty and locked worktrees |
| `/push` | `/push` | Save all changes, pull `main`, then push `main` through the repository's landing route; report open Orbi work without takeover |
| `/lgtm` | `/lgtm` | [Continue within inherited authority](../skills/lgtm/SKILL.md): accept unambiguous choices, clarify only ambiguous planning choices; standalone plan approval does not authorize implementation |
| `/docs_sync` | `/docs_sync` | Maintain repository documentation |
| `/update-kit` (also `/update_kit`) | `/update_kit` | [Refresh dedicated upstream source and reinstall the suite](../skills/update-kit/SKILL.md); explicit only, full-suite/restart effects, restricted Hermes cascades refused; [preview and ownership](installation.md#update-kit) |
| `/plan_with_me` | `/plan_with_me` | Resolve missing intent, then publish complete GitHub Issues |
| `/plan_for_me` | `/plan_for_me` | Investigate accepted scope and publish complete GitHub Issues without an interview |
| `/grill-me` | `/grill_me` | Stress-test a plan through questions |
| `/autoresearch` | `/autoresearch` | Route a research goal or run a bounded metric loop |
| `/impeccable` | `/impeccable` | Design and front-end quality workflow |
| `/unslop` | `/unslop` | [Audit the UI and publish fixes as GitHub issues](../skills/unslop/SKILL.md) for Orbi; an existing deployment can pick up ready issues. Use `no-dispatch` to save without readiness, or `read-only` to preview. |
| `/ui-taste` | `/ui_taste` | Uizze's UI Taste playbooks for building, polishing and reviewing web and iOS interfaces |
| `/beautify-github-readme` | `/beautify_github_readme` | Redesign or audit a GitHub README with project-native SVG assets |

For the Orbi first-deployment journey, `/orbi help` gives context-free examples and
recovery. Only after explicit scheduling authority and resolved pauses/gates, use
`/orbi start --dry-run --pi-providers /path/to/models.json --pi-provider
PUBLISHED_PROVIDER_ID --pi-model PUBLISHED_MODEL_ID` to preview, then remove
`--dry-run` to prepare/validate and activate. New preparation defaults to installed
Pi-Bolt; `--harness pi` selects stock Pi. Existing valid targets skip preparation;
omit selectors to preserve their saved routing. Missing explicit `--config` and
partial targets require deliberate repair, not automatic setup/resume. An absent
preview defers staging-dependent checks; planned, prepared, activated and
live-qualified remain distinct. Standalone setup never schedules; status inspects
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
dependencies. Publication does not create a timer or enable paused Orbi. Read-only
and planning-only requests remain scoped.
Upstream flags and analytical methods are retained; host-specific tools, generic
confirmation prompts, experimental Git handling and documentation handoffs follow
the adapter. Claude-only hooks are not installed.

Retained Hermes terminal maintenance names and private state identities do not restore the removed runner.

## State machine

[State Machine](../skills/state-machine/SKILL.md) maps lifecycle rules scattered
across functions, fields and services. It reports state predicates, transition
rules, source-backed counterexamples and coverage gaps. The default is read-only
and inline; it neither repairs code nor writes task or report files.

| Host | Invocation |
| --- | --- |
| Hermes | `/state-machine` |
| Claude Code | `/kit:state-machine` |
| Codex | `$kit:state-machine` |
| Pi | `/skill:state-machine` |

In Pi, this is a native skill command, not a `/state-machine` extension alias.
After updating the installed package, reload skills in the host before use.

```text
/skill:state-machine find all implicit state machines in this app; no writes
/skill:state-machine inspect checkout retries and cancellation; read-only
```

### Fix the findings without another prompt

After the analysis, invoke Bug Harvest in the same conversation. In Pi:

```text
/skill:bug-harvest
```

Hermes also accepts `/bug-harvest`, Claude Code uses `/kit:bug-harvest`, and Codex
uses `$kit:bug-harvest`. No finding IDs, copied report or extra prompt are required:
the [contextual handoff](../skills/bug-harvest/SKILL.md#findings-from-the-preceding-response)
uses the preceding response as the bounded repair scope. It verifies and fixes
candidates one at a time, adds regression protection and runs affected checks.
Hypotheses are not automatically bugs; unclear product rules need `/plan-with-me`.
The campaign stops when the supplied findings are accounted for or a caller limit
or genuine blocker stops progress. It does not automatically commit or push.
Explicit user no-write and live-action restrictions remain binding; State Machine's
default read-only mode does not make the subsequent repair invocation read-only.

Planning, implementation and review use the shared contract's stateful-work trigger.
Bug Harvest, architecture review and Test Optimizer also link the
[analysis method](../skills/state-machine/PROTOCOL.md) at their relevant steps.
These are scoped reference loads, not automatic skill activation or wider authority.
The [online sources and example](../skills/state-machine/references/sources-and-example.md)
explain the method. Offline packaging checks do not prove exhaustive discovery or
live bug-finding effectiveness.

## Test optimizer

`/test-optimizer` actively reduces executed cases, test code and maintenance cost.
It reuses the existing [test-suite optimization protocol](../skills/engineering/local/test-suite-optimization/PROTOCOL.md).
Prioritize deleting proven redundant, vacuous and obsolete tests, then shrink the
remaining fixtures and cases. A constant assertion such as `assert 0 == 0` needs
no replacement when the whole test protects no product contract. Preserve distinct
supported risks, not test counts. Rare security, data-loss and named regression
cases are not expendable merely because they rarely fail. Unchanged code or tests
unrelated to today's diff are not automatically obsolete.

A bare invocation audits; `read-only` writes nothing. Explicit `apply`, a request
to reduce/optimize the suite, or an existing authorized implementation task permits
one supported batch without another approval ceremony. It preserves distinct
behavioral oracles and justifies deletions with retained equivalent checks, retired
obligations or evidence of no owned contract/invariant. It then validates and reports
real reductions and unknowns, without adding replacement tests just to preserve counts. It never optimizes by
silently skipping tests or weakening CI. This is an agent-guided skill, not an
automatic test-deletion script.

Examples (Hermes CLI; Pi uses `/test-optimizer`, Claude Code
`/kit:test-optimizer`, Codex `$kit:test-optimizer`):

```text
/test-optimizer tests/parser; read-only
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
waste. Default review writes an HTML candidate report to the OS temp directory; a
no-write request gets an inline report. Missing Graphify falls back to native search.
Explicit `fix`, `patch` or `optimize` requests implement one
bounded finding within the skill's accepted scope, with regression evidence, affected checks and Ponytail review in the
existing review lane. Unresolved design or ADR choices still need a decision; no new
commit, push or deployment authority is implied.

Examples (Hermes CLI; Pi uses the same hyphen names, Claude Code prefixes
`/kit:`, Codex prefixes `$kit:`):

```text
/grilling the retry design; recommend answers; read-only
/grill-with-docs the cache plan; record ADRs; no commit
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
criteria and write authority. Orbi remains paused pending live qualification;
do not start it or a second implementer for an already-owned issue.

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

Kit does not schedule or revive pi-autowork. Existing job IDs, settings, schedules,
pause state and recovery evidence remain intact. Orbi remains paused and live-unqualified.
Setup confirmation, actual execution and message delivery require separate evidence;
a changed prompt or installed skill proves none of them.

## Removed executor interfaces

The TUI, web UI and Paseo executor plugin are removed. Their
[prior interface and qualification requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/workflows.md#tui-confirmation-layout-and-refresh)
remain immutable evidence. Physical-client, transport and model qualification
are not satisfied by removal and must be reconciled if needed by the successor.
Orbi remains paused and live-unqualified; see [cutover](github-native.md).
