# Kit

### A toolset of skills for coding agents.

Kit gives an agent a set of practised workflows: plan a decision, document it, execute
accepted work, review a change, shrink a test suite. The skills run in **Hermes**,
**Claude Code**, **Codex** and **Pi**, and they share one work queue: a Git-versioned
`tasks/` store in your own repository.

**Autowork is one tool in the kit**, not the whole set: an optional Linux runner that
keeps working through that queue after a session ends. Everything else works without
it.

[Install](#install) · [The skills](#the-skills) · [First use](#first-use-in-your-project) ·
[The runner](#the-runner-autowork) · [Safety](#read-before-installing) ·
[Evidence and limits](#what-verification-proves) · [Docs](#documentation)

| Your host | Install | Ask for a workflow |
| --- | --- | --- |
| **Hermes** | [Native plugin](#hermes) | `/plan-with-me` |
| **Claude Code** | [Marketplace plugin](#claude-code) | `/kit:plan-with-me` |
| **Codex** | [Marketplace plugin](#codex) | `$kit:plan-with-me` |
| **Pi** | [Git package](#pi) | `/plan-with-me` |

Not sure which skill fits? `/ask-kit` names one for your situation, then the next
step it implies (`/kit:ask-kit` in Claude Code, `$kit:ask-kit` in Codex).

<p align="center">
  <img src="assets/readme/workflow.svg" width="100%" alt="Plan accepted work, queue it in tasks/, execute an eligible task, and report checks and delivery. Further work requires the caller's authority; this diagram does not promise a background scheduler.">
</p>

**A skill invocation is not a background service.** The skills act in your session and
stop when it ends. Hermes scheduler integration is native-only; the Pi runner is the
one continuous option, and you start it yourself.

---

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
- `/lgtm` — continue the concrete step you just approved.
- `/split-folder` — reorganize one folder without changing behavior.
- `/git-commit-push` — commit, sync and push owned changes; `all` also settles finished
  worktrees into the base branch.

**Improve the codebase**

- `/bug-harvest` — hunt evidence-backed defects, one candidate at a time.
- `/test-optimizer` — delete redundant tests and shrink the suite that remains.
- `/unused-code` — remove code whose unreachability is proven.
- `/improve-codebase-architecture` — find shallow modules and report the candidates.
- `/autonomous-codebase-improver` — work several improvement lanes in one campaign.
- `/engineering` — load one method for a concrete gap (TDD, review, debugging).
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

## Install

Choose one host and configure its model. The portable adapters need no Hermes
installation. Review [what installing changes](#read-before-installing) first: the
Hermes defaults are designed for an autonomous fleet, not a policy-neutral bridge.

### Hermes

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
external integrations. A native install stays in one profile; full setup expands to
**every live profile**.

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

### Pi

Requires Node 22 or later:

```sh
pi install git:github.com/TrebuchetDynamics/kit
```

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

Open **your project**, not this checkout. Start your configured host there (`hermes`,
`claude`, `codex` or `pi`), then use the planning invocation from the table above:

```text
questions only: help me clarify a caching improvement; ask one question, then stop
```

In **Hermes CLI** that is:

```text
/plan-with-me questions only: help me clarify a caching improvement; ask one question, then stop
```

Expected first success: one relevant question and no file changes. This is a live smoke
check **you perform**, not an outcome established by automated tests. Hermes'
`doctor --core` checks registrations, not a model or live messaging. Continue with the
[core-only interview](docs/onboarding.md#core-only-requirements-interview) or the
[full-workflow exercise](docs/onboarding.md#optional-see-decisions-become-a-task).
See [onboarding](docs/onboarding.md) for Telegram and project binding; a profile is not
a filesystem sandbox.

## The runner (Autowork)

The runner is the only part of Kit that keeps going without you. It reads the same
`tasks/` store, admits dependency-ready tasks in parallel, verifies each one, and merges
the result into `main`/`master`. It is Linux-only and entirely optional: the skills above
already do the work one task at a time.

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
(`tasks/goals/<ID>.md`), edited only through `autowork tasks` (`list`, `show`, `add`,
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

## Read before installing

These defaults apply to Hermes; the [Claude Code, Codex and Pi adapters](docs/cross-host.md)
keep their hosts' settings. **They are designed for an autonomous fleet, not a
policy-neutral command bridge.**

- Full setup targets **every existing live profile**. There is no general
  `--profile` selector; `--hermes-home` selects a Hermes installation root.
- Loading the plugin sets `approvals.mode: off`, disables destructive slash-command
  and MCP-reload confirmations, removes the per-turn iteration cap
  (`agent.max_turns: unlimited`) and enables gateway injection in its owning profile.
  Explicit deny rules and Hermes hard blocks remain. In profiles with OMH it disables the
  OMH skills outside a measured keep list (your own disabled skills stay).
- Full setup installs external integrations and selects **OMH memory with auto-safe
  capture** in separate profile stores. Conflicting stores are refused; another
  selected memory provider is left in place, and OMH memory stays off until you clear it.
- External imports are **not fully locked**. Some are pinned; others follow current
  upstream sources. Scans or missing dependencies can leave setup incomplete.
- There is **no automatic restoration of previous configuration** on uninstall.
  Back up profile configurations first; see [removal and recovery](docs/uninstall.md).
- With approvals off and unattended runners, **give agents no production
  credentials** and start with repositories where an automatic local commit and
  push is acceptable.

The runtime-policy opt-out prevents policy changes **during plugin loading and
setup**. Full setup still applies OMH memory defaults and external integrations;
there is currently no policy-neutral full-installation mode. See
[installation](docs/installation.md), and [memory and retained data](docs/memory.md)
before enabling memory capture.

## Updating

**Hermes:** `/autowork update` in chat updates every live profile; the terminal form is
`hermes autowork update`, and `/autowork update --check` previews it. Updates normally
fast-forward clean plugin checkouts; verified managed checkouts can recover from
rewritten upstream history through a backed-up transaction that keeps compatible
installed-skill edits. Dirty or unproven sources defer. Ordinary updates reapply
runtime and menu defaults except where opted out; recovery does not.

**Files updated does not mean the gateway is running updated code.** A busy root gateway
can defer its restart for up to six hours, then expire without restarting. Check
`/autowork update status` for pending or deferred activation. See
[update behavior and recovery](docs/installation.md#update-all-profiles); portable hosts
use their [own package update commands](docs/cross-host.md).

<details>
<summary><strong>Migrating from hermes-toolset</strong></summary>

### Renamed from hermes-toolset

This project was called hermes-toolset before 0.3.0, and its plugin was called
`autowork` until the Kit rename. There is no compatibility layer for the old plugin
name: the command namespace is `kit:` and the settings key is
`plugins.entries.kit`. Settings under `plugins.entries.autowork` keep being read for
one release, so an opt-out you already set still applies. Remove an older installation
and [install](#install) again in each host; in Hermes, rewire existing cron jobs with
`scripts/wire-owner-cron.py --apply`.

</details>

## What verification proves

| Host | Evidence and limits |
| --- | --- |
| Hermes | Offline tests, native registration/integration checks and gateway activation receipts. Live model behavior and Telegram delivery require separate live checks. |
| Claude Code | Plugin validation and an earlier isolated install are recorded; no live model workflow is demonstrated in that record. |
| Codex | Earlier isolated installation and skill discovery, plus portable-package checks; the current package still needs renewed native/live qualification. |
| Pi | Earlier isolated installation and resource discovery, plus package/command tests; the current package still needs renewed native/live qualification. |

Package contents have changed since some isolated-install runs. The
[cross-host verification record](docs/cross-host.md#behavior-and-verification) names the
tested versions and gaps; [testing and compatibility](docs/testing.md) covers Hermes.
`/autowork status` reads the runner fleet; `/autowork plugin status` reports
registrations and setup gaps. No registration or package test proves model output
quality, Git delivery or live Telegram execution.

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
