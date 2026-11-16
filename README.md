# Kit

[![Offline CI](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml/badge.svg)](https://github.com/TrebuchetDynamics/kit/actions/workflows/test.yml)

<a id="a-toolset-of-skills-for-coding-agents"></a>

**Plan with Kit. Deliver through Orbi.**

Kit supplies planning skills for **Pi**, **Claude Code** and **Codex**, with optional
**Hermes** integration. Kit researches, decides and decomposes accepted intent into
complete **GitHub Issues**, the executable backlog. **Orbi** is a separate delivery
project, not Kit's bundled executor: it uses Pi to implement and test, opens PRs,
obtains independent review and applies merge gates. Planning stops after publication.

![Conceptual workflow: Kit planning to GitHub Issues to Orbi and Pi delivery to PR, review and merge gates](assets/readme/workflow.svg)

**Conceptual workflow, not live delivery evidence:** Kit planning → complete GitHub
Issues → Orbi/Pi implementation and tests → PR, independent review and merge gates.

[Install](#install) · [First use](#first-use-in-your-project) ·
[Using Orbi](#using-orbi) · [Development flow](#github-native-development-flow) ·
[Skills](#the-skills) · [Safety](#safety-before-installing) · [Docs](#documentation)

**Orbi remains paused and live-unqualified** pending the
[pilot and cutover gates](docs/github-native.md#cutover). Installing Kit or publishing
an issue does not authorize activation. `pi-autowork` is retired and unsupported;
[preserve existing work and recovery evidence](#the-runner-autowork), never restart it.

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

To use the skills inside Paseo, install
Kit in the coding-agent host, then run that agent in a Paseo workspace.

Pi-Bolt is a native build of Pi. It runs the same commands and reads the same
`~/.pi/agent` configuration and Pi packages, so one Kit install serves both.

### Pi

With Pi already installed:

```sh
pi install git:github.com/TrebuchetDynamics/kit
```

From a Kit checkout, `./install.sh --only pi` also installs a missing Pi harness
through the official pi.dev installer, then installs and enables Kit. Upstream
requires Node.js 22.19.0 or newer and npm; its prerequisite prompts/refusal remain
in force. See [Pi bootstrap and recovery](docs/installation.md#pi-harness-bootstrap).

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

Use Kit skills inside a Paseo-hosted Pi, Claude Code or Codex session.
Kit no longer ships a Paseo executor plugin or an Orbi dashboard.

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

## First use in your project

Start the host you installed (`pi`, `claude`, `codex` or `hermes`). Ask for the
read-only Orbi action reference first. No repository or deployment is needed:

| Host | Read-only help |
| --- | --- |
| Pi / Hermes | `/orbi help` |
| Claude Code | `/kit:orbi help` |
| Codex | `$kit:orbi help` |

Expected result: the supported actions, their effects and limits, with no deployment
reads or writes. To choose a planning skill, use `/ask-kit` in Pi,
`/kit:ask-kit` in Claude Code or `$kit:ask-kit` in Codex.

Next, open **your project**, not this checkout, and try the questions-only command:

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
   review → merge gates.
4. **Observe:** GitHub Issues/PRs and read-only
   `orbi status`/`orbi doctor` ([usage](#using-orbi)).
5. **Reconcile:** `/docs-sync` updates current requirements and issue evidence without
   duplicating the backlog or restarting a scheduler.

All issues default to `ai-ready`, regardless of author. Publish readiness last,
after complete content and native `blockedBy` prerequisites exist. Epics do not
execute; explicit pauses and incomplete planning stay undispatched. An existing
Orbi deployment may pick up newly ready issues immediately, but a label is not
pickup, passing tests, independent review or protected merge.

**Activation is a separate gate.** Orbi stays paused and live-unqualified until the
[pilot and cutover checks](docs/github-native.md#cutover) pass. Keep scoped
credentials, strict required CI, enforced branch protection, independent review,
sensitive-change controls and human-only acceptance. Dispatch does not replace them.
See [publication, migration and deployment](docs/github-native.md).

### Using Orbi

One Orbi deployment owns one repository. The suite installer adds only the CLI
(`./install.sh --only orbi`, needs `uv`); a working Orbi installation is kept.

Use `/orbi [status|setup|start|stop|help]` in Pi or Hermes, `/kit:orbi` in Claude
Code, or `$kit:orbi` in Codex. The [Orbi skill](skills/orbi/SKILL.md) provides:

| Action | Effect and boundary |
| --- | --- |
| Bare skill invocation or `status` | Read-only status for the repository; missing evidence is unavailable, not an empty queue. |
| `help` | Read-only action reference, without a repository or deployment. |
| `setup` | Prepare source/configuration without scheduling or timer activation. |
| `start` | Activate scheduling only with explicit authorization and resolved pauses, cutover and human-only gates. |
| `stop` | Disable owned timers without killing active workers; report draining while they finish. |

Linux supports lifecycle changes. macOS supports status and help only.
Never run bare `orbi` to inspect: it runs a Runner tick, not status.

The upstream CLI remains available for diagnostics:

```sh
orbi check  --config /path/to/orbi.toml   # configuration and provider checks
orbi status --config /path/to/orbi.toml   # current delivery state
orbi doctor --config /path/to/orbi.toml   # read-only diagnostics
```

Upstream `orbi setup` and `orbi install-units` can activate timers. Prefer the
Kit lifecycle skill for preparation; deployment changes require a separate
checkout and their own authorization. Installing or updating files is not runtime
activation, and installing the CLI does not start workers or qualify delivery.

Read [GitHub-native deployment](docs/github-native.md#one-repository-per-deployment)
and the [current lifecycle reference](skills/orbi/references/lifecycle.md) for
prerequisites and preparation. For a first deployment, supply credential-free Pi
provider metadata with `--pi-providers PATH --pi-provider ID --pi-model ID` and
optional `--pi-thinking LEVEL`, or reuse a verified selection from a visible
deployment; see [provider bootstrap](skills/orbi/references/lifecycle.md#first-deployment-provider-bootstrap).
Pi authentication must already work; setup does not automate login or guarantee
provisioning. New configs derive `git_transport` from the verified SSH/HTTPS origin
without rewriting it; existing selections and pins are preserved.

For interrupted preparation, follow [partial-failure recovery](skills/orbi/references/lifecycle.md#partial-failure-and-recovery).
The [bounded `--resume-setup` path](skills/orbi/references/lifecycle.md#explicit-bounded-legacy-resume)
is only for an existing config's missing deployment-local provider file, with
`--config PATH` and matching provider inputs; other incomplete states need deliberate
repair. Setup does not activate scheduling or qualify live recovery, isolation or
delivery. Keep credentials out of Git and preserve workers and recovery state.

<details>
<summary><strong>Install every available host and CLI component at once</strong></summary>

From a checkout, `install.sh` installs every available component with verbose output:
the Pi package, the Pi-Bolt native Pi executable, the Orbi CLI, the `tx` tmux
launcher, and the Hermes, Claude Code and Codex plugins with their complete skill sets. A plugin host whose CLI is missing is skipped and explained; each plugin
item runs that host's own install command. Pi is the exception: a missing harness
is bootstrapped from pi.dev before installing the package. `tx` keeps an existing `~/.tmux.conf`.

```sh
git clone https://github.com/TrebuchetDynamics/kit && cd kit
./install.sh                    # full suite, live output and exact commands
./install.sh --menu             # arrows, Space toggles, Enter installs
./install.sh --dry-run          # preview the full suite without installing
./install.sh --only pi,tx --dry-run
```

`--full` (`--all`) and `--verbose` (`-v`) are the defaults. Missing hosts other than
Pi are skipped, while an explicitly requested missing host, such as `--only codex`, fails. Preview mode
installs nothing. The old `autowork` installer component is removed.
Install/update restarts active host integrations, never legacy Autowork runners;
paused/stopped services stay untouched.
See [restart scope and failure handling](docs/installation.md#full-suite-from-a-checkout).
Hermes still runs its complete fleet setup and its own dependency and
security prompts; use `--yes-deps` only when you intend to consent to them.

Orbi is included by default; use `./install.sh --only orbi` or `--skip orbi`.
A missing CLI is installed user-locally from the pinned
[XelHaku/orbi fork](https://github.com/XelHaku/orbi/tree/1a8b2f9603f6258cb105293f238a8d3f775f3393)
with `uv` and Python 3.14 (`uv` and Git must be installed first).
Existing Orbi installations and source pins are kept,
even during `update`. This installs the CLI only: no repository setup, credentials,
scheduler activation or worker starts. See [Orbi CLI installation](docs/installation.md#orbi-cli).

Pi-Bolt is included by default; use `./install.sh --only pi-bolt` or `--skip pi-bolt`.
It installs the upstream native Pi build through the
[official installer](https://pi-bolt.opensec.in/install.sh) and links `pi-bolt` in the
Kit binary directory. Every install and `./install.sh update` refresh it with the
upstream installer rather than keeping an existing build. The upstream run is
non-interactive and installs no optional extensions. See [Pi-Bolt installation](docs/installation.md#pi-bolt-native-executable).

Every install refreshes the installed Pi package with `pi update`, and so does
`./install.sh update`: a complete-looking skill folder set is not proof of current
content, so a kept package is never an option. Settings reconciliation still runs,
as does the service-restart phase.

</details>

## The skills

Every skill is explicit: you type its command, or a workflow hands off to it. Each
states its own boundaries and what "done" means.

**Plan and decide**

- `/plan-with-me` — clarify intent together, then publish complete GitHub Issues.
- `/plan-for-me` — investigate and publish complete GitHub Issues without an interview.
- `/grilling` — stress-test an idea in rounds, one recommendation per question.
- `/grill-with-docs` — the same interview, recording what it settles as ADRs and
  glossary terms.
- `/grill-me` — challenge a plan that already exists.

**Document and track**

- `/docs-sync` — maintain docs and GitHub issue handoffs from current source.
- `/unblock` — diagnose blocked GitHub work and repair authorized causes without releasing pauses.

**Execute and deliver**

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
- `/orbi` — inspect or explicitly manage one repository's Orbi deployment.
- GitHub Issues and Orbi diagnostics — see [delivery setup](docs/github-native.md).

## Paseo interface

The executor plugin is removed. Paseo remains a host for ordinary Kit agent
sessions. Use GitHub and Orbi diagnostics for delivery status; historical plugin
checks do not qualify the new delivery system.

<a id="the-runner-autowork"></a>
## Retired executor and compatibility names

**`pi-autowork` is retired and unsupported. Its executor, CLI and Paseo plugin
are removed. Do not develop, repair, reinstall or restart them.** Contributors and
agents working from older branches must stop executor work and reconcile any
still-required outcome into GitHub Issues for Orbi; do not discard their changes.
Existing task records, worktrees and attempts/recovery evidence are preserved,
not executed. Historical contracts and
unresolved qualification are available at the
[immutable pre-removal revision](https://github.com/TrebuchetDynamics/kit/tree/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/pi-autowork).
This is evidence, not an installation fallback. Hermes terminal maintenance
(`hermes autowork`) and marketplace identifiers retain their current names.
Use GitHub Issues/PRs and read-only Orbi diagnostics for delivery status.

Preserve task data, attempts, worktrees and recovery state. Orbi stays paused
until separately qualified.

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

**Hermes:** `hermes autowork update` updates every live profile;
`hermes autowork update --check` previews it. See
[update behavior and recovery](docs/installation.md#update-all-profiles). Files updated
does not mean a gateway is running the new code; inspect the printed receipt for
pending activation. Old profile skills require an authorized normal update and reload;
source deletion or reinstall alone does not retire preserved native copies.

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
| Paseo | The executor plugin is removed. Its [prior qualification record](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/pi-autowork/integrations/paseo/docs/qualification.md) does not qualify Orbi; physical-client/live-control gaps remain historical evidence, not success claims. |

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

**Run and inspect:** [GitHub/Orbi delivery](docs/github-native.md) ·
[`tx` tmux sessions](tmux/README.md) · [Changelog](CHANGELOG.md) ·
[Memory and retained data](docs/memory.md) · [Adding skills](docs/contributing.md)

All skills use the [shared writing rules](skills/shared/COMMUNICATION.md): ASD-STE100
plus the target project's glossary. Reports state what changed, what passed and what is
still pending; those instructions are not proof of full ASD-STE100 compliance.

Licensed under the [MIT License](LICENSE). Bundled third-party components keep their own
licenses and attribution; see [licensing details](docs/dependencies.md#licensing).
