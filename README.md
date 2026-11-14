# Kit

[![Offline CI](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml/badge.svg)](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml)

<a id="a-toolset-of-skills-for-coding-agents"></a>

**Planning skills for coding agents. GitHub-native delivery through Orbi.**

Kit supplies skills for **Pi**, **Claude Code** and **Codex**, with optional
**Hermes** integration. Kit researches, decides and decomposes work; **GitHub
Issues** own the executable backlog; **Orbi** implements, tests, opens PRs, obtains
independent review and enforces merge gates.

All issues default to `ai-ready`, regardless of author. Kit publishes that label
last, after complete issue content and native dependencies exist. Epics do not
execute; explicit pauses and incomplete planning stay undispatched. CI, review
and sensitive-change protections remain separate from dispatch.

**The `pi-autowork` runner and its Paseo plugin are deprecated**, retained for
migration/recovery only. Do not start them for new work or run them alongside Orbi.
See [GitHub-native setup and cutover](docs/github-native.md).

[Install](#install) · [First use](#first-use-in-your-project) ·
[Development flow](#autowork-flow) · [Skills](#the-skills) ·
[Safety](#safety-before-installing) · [Docs](#documentation)

**Start with one skill.** Ask `/ask-kit` in Pi, `/kit:ask-kit` in Claude Code or
`$kit:ask-kit` in Codex. Planning does not start a service; an existing Orbi
deployment may consume newly published ready issues immediately.

## Install

> **Before you install:** Give unattended agents no production credentials.
> Hermes defaults to interactive approvals; autonomous policy requires explicit selection.
> Full setup targets every live profile.
> Review the [policy and opt-out](docs/installation.md#install) before enabling it,
> plus the full [safety notes](#safety-before-installing).

Start with Pi, Claude Code or Codex and configure that host's model. These are the
primary portable targets. Hermes is optional and adds a native fleet with its own
policy defaults; review its safety notes before enabling it. Paseo hosts any of the
three portable agents.

| Coding-agent host | Package | Example workflow |
| --- | --- | --- |
| **Pi** | Git package | `/plan-with-me` |
| **Claude Code** | Marketplace plugin | `/kit:plan-with-me` |
| **Codex** | Marketplace plugin | `$kit:plan-with-me` |
| **Hermes** | Optional native plugin | `/plan-with-me` |

Paseo has a [separate plugin](#paseo). To use the skills inside Paseo, install
Kit in the coding-agent host, then run that agent in a Paseo workspace.

### Pi

Requires Node 22 or later:

```sh
pi install git:github.com/TrebuchetDynamics/kit
```

### Claude Code

```sh
claude plugin marketplace add TrebuchetDynamics/kit
claude plugin install kit@autowork
```

### Codex

Requires a CLI with plugin support:

```sh
codex plugin marketplace add TrebuchetDynamics/kit --ref main
codex plugin add kit@autowork-marketplace
```

### Paseo

Use Kit skills inside a Paseo-hosted Pi, Claude Code or Codex session. The old
[Autowork Paseo plugin](pi-autowork/integrations/paseo/README.md) is deprecated;
keep existing installations only for legacy inspection/recovery, not Orbi control.

### Hermes (optional)

Hermes adds a native fleet, profile setup and scheduling. Fresh profiles default to
manual approvals, enabled confirmations and 90 turns. Autonomous policy requires
explicit selection; existing approval/turn values stay when no policy is selected.
Full setup targets every live profile. Read
[Hermes installation and policy](docs/installation.md#install) before enabling it.

Default-profile commands; add `-p work` after `hermes` for a named profile.
**Keep all your custom runtime settings?** Before enabling, run
`hermes config set plugins.entries.kit.settings.apply_runtime_defaults false`
([policy selection and opt-out details](docs/installation.md#install)). Otherwise
install with the interactive default:

```sh
hermes plugins install TrebuchetDynamics/kit
hermes plugins enable kit
hermes autowork doctor --core
```

The opt-out does not undo prior changes or stop full setup from configuring
external integrations. Existing memory providers and stores are preserved.

Restart your host session to discover the installed skills. See the
[cross-host guide](docs/cross-host.md) for reload commands, updates and removal.

<details>
<summary><strong>Install every available host and CLI component at once</strong></summary>

From a checkout, `install.sh` installs every available component with verbose output:
the Pi package, the `tx` tmux launcher, official stable
Octet native binaries with Kit skills, and the Hermes, Claude Code and Codex plugins with their complete
skill sets. A plugin host whose CLI is missing is skipped and explained; each plugin
item runs that host's own install command. `tx` keeps an existing `~/.tmux.conf`.

```sh
git clone https://github.com/TrebuchetDynamics/kit && cd kit
./install.sh                    # full suite, live output and exact commands
./install.sh --menu             # arrows, Space toggles, Enter installs
./install.sh --dry-run          # preview the full suite without installing
./install.sh --only pi,tx --dry-run
```

`--full` (`--all`) and `--verbose` (`-v`) are the defaults. Missing hosts are skipped,
while an explicitly requested missing host, such as `--only codex`, fails. Preview mode
installs nothing. The deprecated `autowork` recovery tools require explicit
`--only autowork`; full installs omit them. Install/update restarts active host
integrations, never legacy Autowork runners; paused/stopped services stay untouched.
See [restart scope and failure handling](docs/installation.md#full-suite-from-a-checkout).
Hermes still runs its complete fleet setup and its own dependency and
security prompts; use `--yes-deps` only when you intend to consent to them.

Ordinary installs reuse the installed Pi package and a working Octet binary in the
selected destination. `./install.sh update` explicitly refreshes both. Kit skill
and settings reconciliation still runs, as does the service-restart phase.

Octet bootstraps when its destination binary is absent or fails version verification.
Bootstrap and explicit updates use the
[official stable installer](https://octet.skaft.org/install); `--only octet` selects
it alone and `--skip octet` excludes it. It supports GNU/Linux x86-64 and macOS
x86-64/arm64, needs `curl`, `sh`, Python 3 and native verification utilities, and
reports the destination version. This installs upstream binaries and packaged docs,
plus Kit skill entrypoints in `~/.octet/skills/` referencing this checkout. Keep the
checkout in place. Kit also writes `/kit-*` prompt pointers in `~/.octet/prompts/`;
use `/kit-ask-kit` or `/kit-work`. Use `/reload` for prompts and `/skills reload` for
skills after updates. Optional
extensions, credentials and shell profiles are unchanged. See [installation limits and failure recovery](docs/installation.md#octet-native-binaries).

</details>

## First use in your project

Open **your project**, not this checkout. Start the host you installed (`pi`, `claude`,
`codex` or `hermes`), then use the planning command from the table above:

```text
/plan-with-me questions only: help me clarify a caching improvement; ask one question, then stop
```

Claude Code uses `/kit:plan-with-me`; Codex uses `$kit:plan-with-me`. The portable
hosts resolve the same skill.

Expected first success: one relevant question and no file changes. This is a live
smoke check **you perform**, not an outcome established by automated tests. Continue
with the [core-only interview](docs/onboarding.md#core-only-requirements-interview) or
the [full-workflow exercise](docs/onboarding.md#optional-see-decisions-become-a-task).

<a id="autowork-flow"></a>
## GitHub-native development flow

1. **Plan:** `/plan-with-me` resolves missing intent; `/plan-for-me` investigates and
   decides within accepted scope. Both publish complete GitHub Issues.
2. **Publish:** create the entire batch under `ai-planning`, link native `blockedBy`
   dependencies and optional `ai-epic` sub-issues, verify, then add `ai-ready` last.
3. **Deliver:** one Orbi deployment per repository owns Pi → tests → PR → independent
   review → merge gates. `/work` is an explicit, ownership-coordinated manual alternative.
4. **Observe:** `/pending`, GitHub Issues/PRs, `orbi status` and `orbi doctor`.
   `/autowork` is now a compatibility handoff, not a legacy service starter.
5. **Reconcile:** `/docs-sync` updates current requirements and issue evidence without
   duplicating the backlog or restarting a scheduler.

See [publication, migration and deployment](docs/github-native.md). Readiness,
pickup, passing checks, review and merge are separate observed outcomes.

## The skills

Every skill is explicit: you type its command, or a workflow hands off to it. Each
states its own boundaries and what "done" means.

**Plan and decide**

- `/plan-with-me` — plan together through focused questions and research.
- `/plan-for-me` — investigate and save a plan and tasks without an interview.
- `/grilling` — stress-test an idea in rounds, one recommendation per question.
- `/grill-with-docs` — the same interview, recording what it settles as ADRs and
  glossary terms.
- `/grill-me` — challenge a plan that already exists.

**Document and track**

- `/docs-sync` — maintain docs and GitHub issue handoffs from current source.
- `/pending` — read what is open, done and next without changing anything.
- `/blockers` — resolve held work and the questions only the owner can answer.
- `/unblock` — diagnose stalled runners and repair authorized causes autonomously.

**Execute and deliver**

- `/work` — auto-select and complete tasks in this session, including useful offline work when the queue is blocked.
- `/autowork` — inspect or hand off to GitHub and Orbi; the old runner is retired.
- `/goal` — keep one objective alive until evidence proves it done.
- `/lgtm` — say yes to the latest recommendation and continue.
- `/split-folder` — reorganize one folder without changing behavior.
- `/git-commit-push` — commit, sync and push owned changes; `all` also settles finished
  worktrees into the base branch.
- `/push` — commit all eligible changes, merge idle worktrees into `main`, sync upstream,
  and push. Live or unfinished work stays untouched and is reported.

**Improve the codebase**

- `/skill:state-machine` (Pi) — map implicit states and unsafe transitions, read-only.
  See [other hosts and usage](docs/workflows.md#state-machine).
- `/bug-harvest` — hunt evidence-backed defects, one candidate at a time.
- `/test-optimizer` — delete redundant tests and shrink the suite that remains.
- `/unused-code` — remove code whose unreachability is proven.
- `/improve-codebase-architecture` — expose waste and bugs; verify explicitly requested fixes.
- `/autonomous-codebase-improver` — work several improvement lanes in one campaign.
- `/autoresearch` — bounded research or a measured experiment loop.

**Design, capture and write**

- `/impeccable`, `/ui-taste` — design, audit and polish frontend and iOS interfaces.
- `/beautify-github-readme` — redesign or audit a README with project-native SVG.
- `/responsive-screenshots` — capture pages at breakpoints, report overflow.
- `/writing-for-agents` — write and prune skills and `AGENTS.md`.
- `/graphify` — query a local code graph before reading many files.
- `/ponytail`, `/ponytail-review`, `/ponytail-audit` and siblings — choose a simplicity
  level, review a change, audit a repository, list deferred shortcuts.

**Operate**

- `/ask-kit` — ask which of the above fits.
- `/autowork` runner — the optional section [below](#the-runner-autowork).

## Paseo interface

The retained [Autowork integration](pi-autowork/integrations/paseo/README.md) is a
legacy interface, not an Orbi dashboard. Its historical qualification does not
qualify the new delivery system. Use GitHub and Orbi diagnostics for current work.

## The runner (Autowork)

Deprecated. Historical source, tests and recovery tooling remain in `pi-autowork/`.
Do not enable its runner, plugin mutation controls or cron execution for new work.
Pause existing schedulers before enabling Orbi; preserve attempts and worktrees.

## Your work queue

GitHub Issues are the only executable backlog. Each issue names its outcome,
scope, exclusions, acceptance, exact verification and governing sources. Native
GitHub dependencies own ordering; epics coordinate larger plans without execution.
Merged PRs, checks, reviews and GitHub history preserve delivery evidence.

See [Plan Handoff](skills/shared/PLAN-HANDOFF.md) and the
[legacy migration guide](skills/shared/TODO-WORKCENTER.md). There is no local-main
task-store admission step and no synchronization with `tasks/`.

## Safety before installing

Portable hosts keep their own settings. Fresh Hermes profiles use interactive approvals
and 90 turns. Existing approval and turn values stay unless you explicitly select a
policy. Autonomous policy disables prompts and removes the turn cap. Full setup targets
every live profile and adds external integrations, but preserves existing memory settings. Read
[Hermes installation and policy](docs/installation.md) and
[removal and recovery](docs/uninstall.md) before enabling it. Give unattended agents no
production credentials, and start with repositories where an automatic local commit is
acceptable.

## Updating

**Pi:** update the package with
`pi update git:github.com/TrebuchetDynamics/kit`.

**Claude Code and Codex:** update the marketplace and plugin through their CLI. See
[cross-host updates](docs/cross-host.md) for the exact commands.

**Hermes:** `/autowork update` updates every live profile; the terminal form is
`hermes autowork update`, and `/autowork update --check` previews it. See
[update behavior and recovery](docs/installation.md#update-all-profiles). Files updated
does not mean a gateway is running the new code; check `/autowork update status` for
pending activation.

<details>
<summary><strong>Migrating from hermes-toolset</strong></summary>

### Renamed from hermes-toolset

This project was called hermes-toolset before 0.3.0, and its plugin was called
`autowork` until the Kit rename. There is no compatibility layer for the old plugin
name: the command namespace is `kit:` and the settings key is
`plugins.entries.kit`. Settings under `plugins.entries.autowork` keep being read for
one release, so an opt-out you already set still applies. Remove an older installation
and [install](#install) again in each host. Preserve existing job state during
migration; do not rewire legacy Autowork cron execution for new work.

</details>

## What verification proves

| Host | Evidence and limits |
| --- | --- |
| Pi | Earlier isolated installation and resource discovery, plus package/command tests; the current package still needs renewed native/live qualification. |
| Claude Code | Plugin validation and an earlier isolated install are recorded; no live model workflow is demonstrated in that record. |
| Codex | Earlier isolated installation and skill discovery, plus portable-package checks; the current package still needs renewed native/live qualification. |
| Hermes | Offline tests, native registration/integration checks and gateway activation receipts. Live model behavior and Telegram delivery require separate live checks. |
| Paseo | The plugin's offline checks (the real Paseo 0.15 compiler and an isolated runtime) and a live local daemon load with read-only reads are in [its qualification record](pi-autowork/integrations/paseo/docs/qualification.md). Physical client and live control qualification remain pending. |

Package contents have changed since some isolated-install runs. The
[cross-host verification record](docs/cross-host.md#behavior-and-verification) names the
tested versions and gaps; [testing and compatibility](docs/testing.md) covers host-specific checks.
Use GitHub issue/PR evidence and `orbi status`/`orbi doctor` for current delivery.
Legacy fleet diagnostics remain recovery-only. No registration or package test
proves model output quality, Git delivery or live messaging execution.

## Project status

The offline evidence is broad and the design is ambitious, but **sustained live
reliability is not yet proven**. An outside assessment (2026-10-21) rated the concept
and potential value highly and proven reliability at 5/10. Its warnings: do not spend
more effort improving the toolset than building products with it, and take
explicit autonomous policy and retained permissive profile settings seriously.
The next step is a 30-day evaluation on real repositories with controlled permissions — tasks completed without intervention,
regressions, owner attention, cost per verified task, time to merge and crash recovery.
Measure the new loop through GitHub history and Orbi diagnostics. The earlier
[Autowork assessment](docs/evaluation.md) remains historical context, not evidence
that the Orbi pilot or fleet is qualified.

## Documentation

| Start here | Go deeper |
| --- | --- |
| [Installation and policy opt-out](docs/installation.md) | [Command and configuration reference](docs/reference.md) |
| [Onboarding and first-use checks](docs/onboarding.md) | [Architecture and product scope](docs/project.md) |
| [Commands and workflows](docs/workflows.md) | [Cross-host behavior and verification](docs/cross-host.md) |
| [Skill standard](docs/skill-standard.md) | [Testing and compatibility](docs/testing.md) |
| [Troubleshooting](docs/troubleshooting.md) | [Removal and recovery](docs/uninstall.md) |
| [Dependencies, reproducibility and licensing](docs/dependencies.md) | [Assessment and 30-day evaluation](docs/evaluation.md) |

**Run and inspect:** [`autowork` runner controls](pi-autowork/README.md#the-autowork-command) ·
[`tx` tmux sessions](tmux/README.md) · [Changelog](CHANGELOG.md) ·
[Memory and retained data](docs/memory.md) · [Adding skills](docs/contributing.md)

All skills use the [shared writing rules](skills/shared/COMMUNICATION.md): ASD-STE100
plus the target project's glossary. Reports state what changed, what passed and what is
still pending; those instructions are not proof of full ASD-STE100 compliance.

Licensed under the [MIT License](LICENSE). Bundled third-party components keep their own
licenses and attribution; see [licensing details](docs/dependencies.md#licensing).
