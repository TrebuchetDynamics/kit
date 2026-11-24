# Claude Code, Codex and Pi host contract

Use the [ASD-STE100 and project language rules](../../skills/shared/COMMUNICATION.md)
for user-facing text. Read the target project's glossary map and glossary when available.

For an authorized GUI action or a visual claim, read the
[shared GUI decision](../../skills/shared/COMMON-CONTRACT.md#gui-actions-and-visual-evidence).
This safety/evidence rule applies even when optional Ponytail coaching is off.

These adapters run repository workflows in the current Claude Code, Codex or Pi session.
Use this host's actual file, terminal, search, question and delegation tools.
Read repository instructions and user scope first; preserve unrelated work.
Apply the [shared source freshness and ownership contract](../../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership) before probes or handoffs; select the current mode rather than automatically syncing Git.
For standalone writable Plan With Me / Plan For Me, apply
[planner freshness](../../skills/shared/COMMON-CONTRACT.md#standalone-planner-freshness)
before code analysis; this is not a sync on skill loading.
Every bundled workflow applies the [shared Ponytail method](../../skills/shared/PONYTAIL.md)
within its own authority. The pinned suite is included on all hosts; no external
Ponytail plugin or persistent activation is required.
Do not require Hermes CLI, profiles, gateways, Kanban cards, native origin injection,
worker manifests, cron jobs, speech or another agent runtime. Those integrations
belong to the Hermes distribution, not portable prerequisites.

Installation exposes skill metadata, not all instructions in every request. Load
only the selected workflow and relevant references. Resolve links relative to the
loaded skill file. For a named command, use host-discovered skill metadata or an
explicit file link. Do not infer `skills/<command>/SKILL.md` from the command name.
The canonical primary workflows are Plan With Me, Plan For Me,
Docs Sync. Autoresearch remains independently discoverable with all
13 research selectors. Grill Me is Plan With Me's challenge mode, not a separate
public skill; Pi retains `/grill-me` as a compatibility command. In native skill
invocation (`/kit:plan-with-me` in Claude Code), select `plan-with-me`
and request challenge mode.
Shared source files are reference material; this contract takes
precedence over Hermes-specific execution procedures in linked upstream material.
Pi command aliases use hyphens, including `/autoresearch-<protocol>`; use these
spellings even when linked Hermes references show Telegram's underscore aliases.
Never change host permissions, memory configuration, model credentials or approval
policy to make a workflow run. A skill cannot promise unattended execution after
the current host session ends.

For task operations, load the [GitHub issue contract](../../skills/shared/PLAN-HANDOFF.md).
All issues default to `ai-ready`, regardless of author; planning publishes it last.
Preserve explicit pauses, incomplete planning, native dependencies and live ownership.
Legacy task-store writes, leases and scheduler instructions in older references are
superseded. GitHub Issues and Orbi are the only executable backlog and delivery executor.

Explicit invocation authorizes the documented default action within user scope.
Questions-only/read-only/no-write/no-commit/no-push restrictions propagate through
all handoffs. Product intent is distinct from proposals and current behavior.
GitHub Issues are the one executable backlog. Orbi owns automatic issue-to-PR
delivery; retained fix/apply modes keep their own accepted scope, coordinated
ownership, independent review and PR gates. Planning stops after publication. Never
fabricate completion, review, attribution or live qualification. Python 3 is needed
only for bundled helpers, not for a questions-only interview.

Use available independent review when required; if unavailable, state the missing
check rather than invent approval. A local commit, local integration, remote push,
release and deployment are separate outcomes. Preserve active work and paused jobs.
Report task, actual changes, checks, commit, next action and precise unresolved input.
