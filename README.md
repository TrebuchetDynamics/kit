# Kit

[![Offline CI](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml/badge.svg)](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml)

<a id="a-toolset-of-skills-for-coding-agents"></a>

**Coding-agent skills. A native Paseo plugin. An optional background runner.**

Kit is a kit of skills for **Pi**, **Claude Code** and **Codex**, with an optional
**Hermes** integration. Use it to plan work, document decisions, implement tasks,
review changes and improve a codebase.

The **Paseo plugin** brings Autowork's tasks, goals, runners and owner questions
into Paseo. Inspect work in read-only mode, or enable specific actions through a
daemon-side operator policy.

| Choose a part | What you get |
| --- | --- |
| [Skills](#the-skills) | Explicit workflows in your coding-agent session. No background runner required. |
| [Paseo plugin](#paseo) | A native interface for an existing Linux Autowork installation. Read-only by default. |
| [Autowork runner](#the-runner-autowork) | Optional Linux automation that works through accepted tasks after your session ends. |

[Install](#install) · [First use](#first-use-in-your-project) ·
[Skills](#the-skills) · [Paseo interface](#paseo-interface) ·
[Safety](#safety-before-installing) · [Evidence](#what-verification-proves) ·
[Docs](#documentation)

**Start with one skill.** Not sure which fits? Ask `/ask-kit` in Pi,
`/kit:ask-kit` in Claude Code or `$kit:ask-kit` in Codex.

**A skill invocation is not a background service.** The skills act in your session and
stop when it ends. The Pi runner is the continuous option, and you start it yourself.
Hermes adds native scheduling for its own profiles. Paseo can host agents, but
installing the Kit plugin does not start an Autowork service.

## Install

> **Before you install:** Give unattended agents no production credentials.
> Hermes changes approval settings, and full setup targets every live profile.
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

Install the **Autowork Paseo plugin** on the intended daemon host. It requires
Paseo 0.13, 0.14 or 0.15 and an existing Linux Autowork installation.
See the [full requirements](integrations/paseo/README.md#requirements).

> **Trusted, unsandboxed code:** a Paseo plugin runs as the daemon user.
> Review the [security notes](integrations/paseo/docs/security.md) before installation.
> It is read-only by default. Execution grants are shared by authenticated daemon
> managers, not isolated per user.

```sh
paseo plugin add git:TrebuchetDynamics/kit
paseo plugin ls
```

Confirm that `kit-autowork` is running. Open **Autowork** in Paseo's sidebar and
select **Refresh** to inspect repositories already known to Autowork.
Installation does not start a runner or grant mutations.
See [Paseo interface](#paseo-interface) for controls and planning.

### Hermes (optional)

Hermes adds a native fleet, profile setup, scheduling and memory integrations. Its
defaults change approvals and target every live profile on full setup. Read
[Hermes installation and policy](docs/installation.md#install) before enabling it.

Default-profile commands; add `-p work` after `hermes` for a named profile.
**Keep your approval settings?** Before enabling, run
`hermes config set plugins.entries.kit.settings.apply_runtime_defaults false`
([opt-out details](docs/installation.md#install)). Otherwise accept the defaults with:

```sh
hermes plugins install TrebuchetDynamics/kit
hermes plugins enable kit
hermes autowork doctor --core
```

The opt-out does not undo prior changes or stop full setup from configuring memory and
external integrations.

Restart your host session to discover the installed skills. See the
[cross-host guide](docs/cross-host.md) for reload commands, updates and removal.

<details>
<summary><strong>Install every available host and CLI component at once</strong></summary>

From a checkout, `install.sh` installs every available component with verbose output:
the Pi package, the `autowork` command and TUI, the `tx` tmux launcher, and the Hermes,
Claude Code and Codex plugins with their complete skill sets. A host whose CLI is
missing is skipped and explained; each item runs that host's own install command. `tx`
keeps an existing `~/.tmux.conf`.

```sh
git clone https://github.com/TrebuchetDynamics/kit && cd kit
./install.sh                    # full suite, live output and exact commands
./install.sh --menu             # arrows, Space toggles, Enter installs
./install.sh --dry-run          # preview the full suite without installing
./install.sh --only pi,autowork,tx --dry-run
```

`--full` (`--all`) and `--verbose` (`-v`) are the defaults. Missing hosts are skipped,
while an explicitly requested missing host, such as `--only codex`, fails. Preview mode
installs nothing. Hermes still runs its complete fleet setup and its own dependency and
security prompts; use `--yes-deps` only when you intend to consent to them.

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

- `/docs-sync` — maintain the docs and the `tasks/` store from current source.
- `/pending` — read what is open, done and next without changing anything.
- `/blockers` — resolve held work and the questions only the owner can answer.

**Execute and deliver**

- `/autowork` — implement and verify one ready task, then close it.
- `/goal` — keep one objective alive until evidence proves it done.
- `/lgtm` — say yes to the latest recommendation and continue.
- `/split-folder` — reorganize one folder without changing behavior.
- `/git-commit-push` — commit, sync and push owned changes; `all` also settles finished
  worktrees into the base branch.

**Improve the codebase**

- `/bug-harvest` — hunt evidence-backed defects, one candidate at a time.
- `/test-optimizer` — delete redundant tests and shrink the suite that remains.
- `/unused-code` — remove code whose unreachability is proven.
- `/improve-codebase-architecture` — find shallow modules and report the candidates.
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

The [Autowork Paseo plugin](integrations/paseo/README.md) lives in `integrations/paseo/`.
Install it from Git with the [command above](#paseo), or follow the
[local checkout instructions](integrations/paseo/README.md#install-only-after-reviewing-trusted-code).

- **See the work:** inspect runners, tasks, goals, owner questions, logs and the scorecard.
- **Review the plan:** prepare staged planning proposals, then review and explicitly apply them.
- **Confirm the action:** edit tasks and goals, commit only task files, answer owner questions,
  or control runners with the required operator grants and exact-action confirmations.

The plugin uses the existing Autowork engine. It is not a model provider or scheduler.
Planning does not start a runner. Physical client and live control qualification
remain pending. See the [qualification record](integrations/paseo/docs/qualification.md).

Developer checks use `npm --prefix integrations/paseo run check` after
`npm --prefix integrations/paseo ci --ignore-scripts`.
See [testing](docs/testing.md#paseo-plugin-checks).

## The runner (Autowork)

The runner is the only part of Kit that keeps going without you. It reads the same
`tasks/` store, admits dependency-ready tasks in parallel, verifies each one, and merges
the result into `main`/`master`. It is Linux-only and entirely optional: the skills above
already do the work one task at a time.

<p align="center">
  <img src="assets/readme/workflow.svg" width="100%" alt="Plan accepted work, queue it in tasks/, execute an eligible task, and report checks and delivery. Further work requires the caller's authority; this diagram does not promise a background scheduler.">
</p>

The diagram shows the optional task workflow, not a background service started by a skill.

```sh
autowork                      # the live TUI: runners, workers, blockers, questions
autowork start                # this repository: install the service if needed and start it
autowork status india         # one repository's tasks, workers and what blocks them
```

- **Parallel where safe.** Overlapping file scopes, shared resources and dependencies
  limit admission. An empty queue waits without a model call rather than inventing work.
- **Evidence before closure.** Worker commits and reports are claims; project checks and
  a separate review gate integration and closure.
- **Local delivery is automatic, push is opt-in.** Each closed task merges into
  `main`/`master`. Publishing needs an explicit `PI_AUTOWORK_PUSH=1` grant; workers never
  push. What cannot land is reported as `Merge pending`.
- **Configure checks and limits before unattended use.** The runner defaults to the
  SDK-backed Pi RPC transport; see [RPC setup](docs/pi-rpc.md).

Deeper material, including every command, model fallback, service controls and recovery:
the [runner guide](pi-autowork/README.md) and
[continuous operation](docs/cross-host.md#run-autowork-continuously).

## Your work queue

`tasks/` is the one queue: one file per task (`tasks/items/<ID>.md`) and per goal
(`tasks/goals/<ID>.md`), edited only through `autowork tasks` (`list`, `goals`, `show`, `add`,
`field`, `move`, `done`, …). The store is read from a commit, so a run's decisions are
reproducible, and `/docs-sync` prepares or converts it.

<details>
<summary><strong>An illustrative task record</strong></summary>

This is a consumer-project example, not a task to run here. Replace the goal, source,
paths and check with your project's values; `autowork tasks add` writes the fields for
you. See the [file schema](pi-autowork/task-store.md#file-schema).

```markdown
+++
schema = 1
id = "CACHE-01"
title = "Add bounded cache storage"
short = "Bounded cache storage"
status = "open"
goal = "CACHE"
section = "Now"
rank = 1000
depends_on = []
touches = ["src/cache/", "tests/test_cache.py", "docs/cache.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Bound cache memory by evicting the oldest entry; no new dependencies."
acceptance = ["entries beyond the limit are evicted oldest-first"]
checks = ["pytest tests/test_cache.py"]
exclusions = []
+++
- Sources: [Accepted cache design](docs/cache.md#accepted-cache-design)
```

`COMPLETED` means verified acceptance and closure, not merely a passing build. See the
[task-record rules](skills/shared/TODO-WORKCENTER.md) and the
[reporting contract](skills/autowork/references/dispatch-and-reporting.md).

</details>

## Safety before installing

Portable hosts keep their own settings. Hermes is different: its native plugin changes
approvals, iteration limits and gateway behavior, and full setup targets every live
profile, installs memory capture and adds external integrations. Read
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
and [install](#install) again in each host; in Hermes, rewire existing cron jobs with
`python3 scripts/wire-owner-cron.py --root DEFAULT_HERMES_HOME --apply`.

</details>

## What verification proves

| Host | Evidence and limits |
| --- | --- |
| Pi | Earlier isolated installation and resource discovery, plus package/command tests; the current package still needs renewed native/live qualification. |
| Claude Code | Plugin validation and an earlier isolated install are recorded; no live model workflow is demonstrated in that record. |
| Codex | Earlier isolated installation and skill discovery, plus portable-package checks; the current package still needs renewed native/live qualification. |
| Hermes | Offline tests, native registration/integration checks and gateway activation receipts. Live model behavior and Telegram delivery require separate live checks. |
| Paseo | The plugin's offline checks (the real Paseo 0.15 compiler and an isolated runtime) and a live local daemon load with read-only reads are in [its qualification record](integrations/paseo/docs/qualification.md). Physical client and live control qualification remain pending. |

Package contents have changed since some isolated-install runs. The
[cross-host verification record](docs/cross-host.md#behavior-and-verification) names the
tested versions and gaps; [testing and compatibility](docs/testing.md) covers host-specific checks.
`/autowork status` reads the runner fleet; `/autowork plugin status` reports
registrations and setup gaps. No registration or package test proves model output
quality, Git delivery or live messaging execution.

## Project status

The offline evidence is broad and the design is ambitious, but **sustained live
reliability is not yet proven**. An outside assessment (2026-10-21) rated the concept
and potential value highly and proven reliability at 5/10. Its warnings: do not spend
more effort improving the toolset than building products with it, and take the
permissive defaults seriously. The next step is a 30-day evaluation on real
repositories with controlled permissions — tasks completed without intervention,
regressions, owner attention, cost per verified task, time to merge and crash recovery.
`autowork scorecard` measures part of it today. See
[Is Autowork worth it?](docs/evaluation.md) for the assessment and the gaps still to
instrument.

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
[`tx` tmux sessions](tmux/README.md) · [Work queue](tasks/) · [Changelog](CHANGELOG.md) ·
[Memory and retained data](docs/memory.md) · [Adding skills](docs/contributing.md)

All skills use the [shared writing rules](skills/shared/COMMUNICATION.md): ASD-STE100
plus the target project's glossary. Reports state what changed, what passed and what is
still pending; those instructions are not proof of full ASD-STE100 compliance.

Licensed under the [MIT License](LICENSE). Bundled third-party components keep their own
licenses and attribution; see [licensing details](docs/dependencies.md#licensing).
