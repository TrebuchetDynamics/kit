# Claude Code, Codex and Pi installation

> **GitHub-native delivery:** GitHub Issues own executable work; Orbi owns delivery.
> See [setup and support](github-native.md).

Kit supports Claude Code, Codex, Pi and optional Hermes integration.
Claude Code, Codex and Pi use the portable adapters, not the Hermes plugin
loader. None requires Hermes installed.
These adapters expose the portable workflows: Plan With Me, Plan For Me, Docs Sync, Orbi, Update Kit,
Autoresearch, Impeccable, UI Taste, Beautify GitHub README,
LGTM, Git Commit Push, the six bundled Ponytail skills,
and Bug Harvest, Autonomous Codebase Improver, Skill Folder Refactor, Unused Code
and Test Optimizer, plus APK Get.
Grill Me is Plan With Me's challenge mode, not a separate skill.
The pinned engineering protocols are a **reference pack**, not a command or skill
on any host; retained workflows read them directly when a method gap needs one.
Every adapter is explicit-only: Claude Code and Pi read `disable-model-invocation: true`
in its frontmatter and Codex reads `agents/openai.yaml`, so the model never starts a
workflow on its own.
Plan For Me with no objective starts autonomous project discovery; an explicit
outcome keeps focused planning, and `read-only` saves nothing.
Supporting protocols are bundled and loaded only when needed. Hermes profile
creation, Telegram routing,
Kanban workers, fleet setup, memory and speech integrations remain Hermes-only.

All hosts inherit the [shared mode-aware freshness and ownership contract](../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
through canonical Ponytail and the portable common entry point. No automatic
fetch/sync is added to skill loading: read-only/audit and writable planning do not
mutate Git. `/push` includes already-merged Orbi changes through verified upstream
and reports open Orbi issues/PRs without taking over their coordinator/review route.
Caller restrictions and host permissions propagate across every handoff.

## Planning and delivery

Both planners publish GitHub Issues and stop. Orbi owns automatic delivery.
Retained authorized fix/apply modes keep their scope, actual ownership, checks,
independent review and PR gates. Orbi remains paused and live-unqualified.

## Orbi lifecycle controls

Use `/kit:orbi [status|setup|start|update|stop|help]` in Claude Code, `$kit:orbi` in Codex,
or `/orbi` in Pi or Hermes. All hosts load the same
[Orbi workflow](../skills/orbi/SKILL.md); default status is read-only. `help` prints the action reference read-only and needs no repository.
Linux lifecycle changes require the workflow's ownership and authorization gates;
macOS is status-only. Installing the skill does not activate a deployment or
qualify live delivery. Existing pauses and cutover gates remain in force.

## Update Kit on every host

Explicit `/update-kit` in Pi or Hermes (`/update_kit` also works in Hermes),
`/kit:update-kit` in Claude Code and `$kit:update-kit` in Codex load the same
[Update Kit workflow](../skills/update-kit/SKILL.md) and bundled helper. It refreshes
the persistent `${XDG_DATA_HOME:-$HOME/.local/share}/kit/source` checkout and reruns
that revision's installer. Default scope is the full suite, including possible
Pi-Bolt bootstrap and active supported integration restarts. Restricted Hermes
cascades/no-restarts requests hold before mutation; preview writes/probes nothing.
See [source ownership, nested updates and recovery](installation.md#update-kit).
Refresh does not reload the current agent: reopen/reload its session and verify
activation separately. Discovery/package tests are not installed-host/model or
live qualification. No automatic schedule or Orbi activation is added.

## Bundled Ponytail on every host

Every Kit skill applies the [shared Ponytail method](../skills/shared/PONYTAIL.md)
within its own scope: smallest complete result, reuse first, no weakened safety or
verification. Planning remains planning; read-only stays read-only. Detailed
protocols load once when relevant; there is no extra review loop or global activation.

`install.sh` includes the pinned six-skill suite and optional read-only map helper
in each host's existing Kit package, not a second plugin install. The method
needs only host tools; the map helper needs Node and is optional on non-Pi hosts.
No hooks, telemetry, transcript import, UI band or global mode config are enabled.
Existing external Ponytail installations are left alone; check command collisions.

| Host | Example review invocation |
| --- | --- |
| Hermes | `/ponytail-review` (or bundled `kit:ponytail-review` via skill tools if another plugin owns the command) |
| Claude Code | `/kit:ponytail-review` |
| Codex | `$kit:ponytail-review` |
| Pi | `/ponytail-review` or `/skill:ponytail-review` |

The suite also includes `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`
and `ponytail-help`; Pi command aliases use the same hyphenated names.
`ponytail lite|full|ultra|off` changes the conversation's Kit preference only;
no argument reports it (default `full`).
[`ponytail-audit`](../skills/ponytail-audit/SKILL.md) publishes warranted issues by
default; explicit report-only/no-write returns inline findings without writes.
The remaining commands report without edits.
Gain displays attributed upstream benchmarks, never inferred local savings.
See [provenance and refresh](dependencies.md#bundled-ponytail) and
[the bundled help](../skills/ponytail-help/SKILL.md).

## Shared response language

Every native and portable skill entry links to the
[shared writing rules](../skills/shared/COMMUNICATION.md). Use ASD-STE100
Simplified Technical English for user-facing English. Keep enough context to
explain the result and the next action. The rule also applies when Ponytail is off.

Read the target project's `GLOSSARY-MAP.md` first, when present. Follow it to the
glossary for the task's area. If no map exists, use the glossary that governs that
area. If no glossary exists, use terms from the current project documentation.
Do not borrow unrelated terms from the package that stores the skill.

Keep code, commands, exact errors and required output formats unchanged.
A request to explain a result does not permit new work. Reports must keep local
changes, passing checks, review, commits, merge, push and installation separate.

The existing Docs Sync language profile now points to the shared rules.
Source changes require the normal host update before installed skills use them.
Offline tests check the links and packaged files. They do not prove formal
ASD-STE100 compliance or that every live model response follows the rules.

## Test optimizer

The locally authored [Test Optimizer](../skills/test-optimizer/SKILL.md) reuses
Engineering's existing test-suite optimization protocol. Bare invocation audits;
explicit reduction/apply permits a bounded verified batch. It prioritizes deleting
proven redundant, vacuous and obsolete tests, then shrinking the remaining suite.
Meaningless tests need no replacement. Distinct supported risks remain protected,
including rare consequential cases and valid tests of unchanged code. No new
executable helper or external dependency is installed.

| Host | Example |
| --- | --- |
| Hermes | `/test-optimizer tests/parser; apply one batch; no push` |
| Claude Code | `/kit:test-optimizer tests/parser; apply one batch; no push` |
| Codex | `$kit:test-optimizer tests/parser; apply one batch; no push` |
| Pi | `/test-optimizer tests/parser; apply one batch; no push` |

Portable invocation is explicit-only; `read-only` changes nothing. See
[workflow and evidence requirements](workflows.md#test-optimizer).
This skill is local Kit content, not an imported pi-toolset protocol.

## Graphify

[Graphify](https://github.com/Graphify-Labs/graphify) turns a project into a local
knowledge graph. Hermes installs the official skill and CLI through its plugin
installer, so `/graphify` there is upstream content. Claude Code, Codex and Pi use
the local [adapter](../adapters/skills/graphify/SKILL.md), which calls the same
`graphify` command with Kit scope, evidence and limit rules.

| Host | Example |
| --- | --- |
| Hermes | `/graphify src/parser; explain parse_statement; read-only` |
| Claude Code | `/kit:graphify src/parser; explain parse_statement; read-only` |
| Codex | `$kit:graphify src/parser; explain parse_statement; read-only` |
| Pi | `/graphify src/parser; explain parse_statement; read-only` |

Portable invocation is explicit-only. The adapter never installs `graphifyy`, adds
hooks, changes settings or requests a semantic pass. It reuses a graph that matches
the current revision or whose queried nodes no changed file touches, or builds
code-only output into an ignored directory, and it reports the declared state, the
tool version, graph path, counts and exit codes. A graph is orientation,
not proof: `EXTRACTED` and `INFERRED` edges still need live-source checks, and Unused
Code keeps its own liveness rules. `graphify-out/` is never committed. See
[workflow and evidence requirements](workflows.md#graphify).

## Repository instruction reconciliation

The explicit [Agents MD Generator](../skills/agents-md-generator/SKILL.md) command
reconciles evidence and instruction ownership. It uses Writing For Agents for
wording and structure, rather than replacing that reference.

| Host | Full revamp | Read-only audit | Scoped update |
| --- | --- | --- | --- |
| Pi | `/agents-md-generator` | `/agents-md-generator audit` | `/agents-md-generator update only src/AGENTS.md` |
| Claude Code | `/kit:agents-md-generator` | `/kit:agents-md-generator audit` | `/kit:agents-md-generator update only src/AGENTS.md` |
| Codex | `$kit:agents-md-generator` | `$kit:agents-md-generator audit` | `$kit:agents-md-generator update only src/AGENTS.md` |
| Hermes CLI | `/agents-md-generator` | `/agents-md-generator audit` | `/agents-md-generator update only src/AGENTS.md` |

Hermes Telegram normalizes the generic command as `/agents_md_generator`; existing
command collisions retain their owner. Hermes discovers immediate canonical skill
children; Claude Code and Codex load portable adapters; Pi uses the existing generic
dispatch route. The nested upstream `PROTOCOL.md` is not another public entry.
Upstream `agents/openai.yaml` is inert provenance; only the local portable policy
controls implicit invocation (disabled). No new discovery roots, hooks or dependencies.

The target is the current repository unless explicitly named, for example
`/agents-md-generator audit /path/to/target`. Guides and detector resolve from the
installed canonical skill directory, not the target. After inspecting its source/help,
run `"<installed-skill>/upstream/scripts/detect-agent-context" --root "/path/to/target" --format json`.
Native reads supplement the detector's ancestor, symlink and depth limitations, or
replace it when unavailable. Audit writes nothing; explicit read-only always wins
and scoped update needs no second approval. See [mode and evidence requirements](workflows.md#repository-instruction-reconciliation).

Files in a worktree are not a released package, and packaged resources are not actual
worker registration. Command use requires separate authorized installation/configuration
in that worker's Pi environment. This change installs no worker package, changes no
live runtime and does not qualify model behavior or Orbi delivery. The committed
[maintenance reference](../skills/shared/AGENT-INSTRUCTIONS.md) works by reading
Markdown with no skill registration. Installing/registering the command does not
rewrite any target instructions. Offline archive, detector and source-contract checks
prove resource closure and routing, not observed model adherence.

## Writing for agents

[Writing For Agents](../skills/writing-for-agents/SKILL.md) pins mattpocock's
skill-writing reference, formerly `writing-great-skills`, with an MIT license and
byte-exact files. It is reference, not a generator: the skill edits documents you
name, within their accepted scope.

| Host | Example |
| --- | --- |
| Hermes | `/writing-for-agents skills/unblock; remove no-ops; read-only` |
| Claude Code | `/kit:writing-for-agents skills/unblock; remove no-ops; read-only` |
| Codex | `$kit:writing-for-agents skills/unblock; remove no-ops; read-only` |
| Pi | `/writing-for-agents skills/unblock; remove no-ops; read-only` |

The reference covers pointer wording, progressive disclosure, completion criteria,
leading words, positive instruction and pruning. The local adapter keeps Kit
scope, GitHub issue authority, review gates and delivery limits. The current upstream name
is `writing-for-agents`; upstream retired `writing-great-skills` without an alias.
See [workflow and evidence requirements](workflows.md#writing-for-agents).

## Unslop

Use `/unslop audit the checkout flow` in Pi or Hermes, `/kit:unslop` in Claude Code,
or `$kit:unslop` in Codex. The [same workflow](../skills/unslop/SKILL.md) publishes
UI improvements as GitHub issues for Orbi. Add `read-only` for an inline preview.

## Responsive screenshots

[Responsive Screenshots](../skills/responsive-screenshots/SKILL.md) captures pages at
chosen breakpoints and verifies each result. It runs a bundled script against the
installed Playwright Python package; when that package is absent, the adapter uses the
host's MCP browser tools or its Playwright CLI and says which path it used. It installs
no browser, refuses credential URLs, keeps captures out of Git unless asked, and treats
a file as evidence of a render, not of a correct layout.

| Host | Example |
| --- | --- |
| Hermes | `/responsive-screenshots https://localhost:3000; 375, 768, 1440; both schemes` |
| Claude Code | `/kit:responsive-screenshots https://localhost:3000; 375, 768, 1440` |
| Codex | `$kit:responsive-screenshots https://localhost:3000; 375, 768, 1440` |
| Pi | `/responsive-screenshots https://localhost:3000; 375, 768, 1440` |

See [workflow requirements](workflows.md#responsive-screenshots). Design review stays
with `/ui-taste` and `/impeccable`.

## Ask Kit

[Ask Kit](../skills/ask-kit/SKILL.md) is the router over the bundle: it names
the skill for a situation, then the next step. It reads the chosen skill before
describing it and names one command. Use it when you know the outcome you want but not
the command.

| Host | Example |
| --- | --- |
| Hermes | `/ask-kit I need to stress-test a plan` |
| Claude Code | `/kit:ask-kit I need to stress-test a plan` |
| Codex | `$kit:ask-kit I need to stress-test a plan` |
| Pi | `/ask-kit I need to stress-test a plan` |

The map is orientation, not authority: the named skill keeps its own scope, review and
delivery rules. See [workflow requirements](workflows.md#ask-kit).

## Grilling and architecture review

Three mattpocock/skills references are pinned byte-exact with their MIT license:
[Grilling](../skills/grilling/SKILL.md) owns the interview mechanic,
[Grill With Docs](../skills/grill-with-docs/SKILL.md) records what it settles as ADRs
and glossary terms, and
[Improve Codebase Architecture](../skills/improve-codebase-architecture/SKILL.md)
scans for shallow modules and writes one HTML report to the temp directory.

| Host | Example |
| --- | --- |
| Hermes | `/grilling the retry design; read-only` |
| Claude Code | `/kit:grilling the retry design; read-only` |
| Codex | `$kit:grilling the retry design; read-only` |
| Pi | `/grilling the retry design; read-only` |

The upstream entries call sibling skills by name. Portable hosts expose commands
rather than a Skill tool, so the local workflows state the composition directly:
Grill With Docs runs Grilling and then the Docs Sync write rules, and the architecture
review runs Grilling on the chosen candidate. Delegation is optional and uses the
host's own sub-agent tool. A report is advice, not implementation authority: edits,
commits and delivery still need their own accepted scope. See
[workflow and evidence requirements](workflows.md#grilling-and-architecture-review).

## APK Get

[APK Get](../skills/apk-get/SKILL.md) builds an existing Flutter or React Native
Android application as an ARM64-only release APK, then uploads it with the host's
installed `s3upload`. Use `/apk-get` in Pi, `/kit:apk-get` in Claude Code,
or `$kit:apk-get` in Codex. Hermes discovers the same named skill
through its existing plugin registration. No host requires Hermes installation.

No app-path argument is required. The skill finds apps in the current repository;
one app is selected automatically. Multiple apps without a default require a choice.
The skill uses project tooling and existing signing configuration, then checks
actual native ABIs with its Python helper. Release mode is separate from signing:
an unsigned artifact is reported as not install-ready, not silently replaced with
a debug build. Missing prerequisites are reported without global SDK installation.
Build evidence, APK path, size/hash, signing status and the reported download link,
expiry and deletion window are returned. Upload failures retain the verified local
APK and report the failed delivery. Explicit no-network/no-upload restrictions
remain binding. Device installation and app-store publication are not authorized.

## pi-toolset specialists

Four instruction-only specialists from [pi-toolset](https://github.com/TrebuchetDynamics/pi-toolset)
extend the suite without installing that package or its extensions:

| Skill | Use it for | Boundary |
| --- | --- | --- |
| `bug-harvest` | Continuing hunts for unknown, reproducible defects | One active bug; explicit bug/slice limits win |
| `autonomous-codebase-improver` | Evidence-ranked improvement across applicable work lanes | Current session, one writer, independent review; not a new runner |
| `split-folder` | Splitting one named folder by responsibility | Move-only → validate → proven extraction → cleanup |
| `unused-code` | Removing proven unreachable code | Dynamic/public consumers must be checked; retain uncertain code |

Invoke with the existing host prefix:

| Host | Example |
| --- | --- |
| Hermes | `/bug-harvest one bug in the parser; no push` |
| Claude Code | `/kit:bug-harvest one bug in the parser; no push` |
| Codex | `$kit:bug-harvest one bug in the parser; no push` |
| Pi | `/bug-harvest one bug in the parser; no push` |

Pi also exposes `/autonomous-codebase-improver`, `/split-folder` and
`/unused-code`; native `/skill:<hyphenated-name>` invocation remains available.
Portable entries are explicit-only. Existing bare command/skill collisions are
not overwritten: select the verified Kit namespace or installed adapter path,
not an unrelated same-named personal skill.

[Kit adaptations](../skills/shared/PI-TOOLSET.md) govern upstream scope,
task state, tools and delivery. Missing Pi-specific tools do not require installing
extensions; missing required independent review blocks implementation. Explicit
read-only, pause, time/budget and one-slice limits win. All four use Ponytail and the
existing task store; no shell controller, scanner, service, hooks or global
activation is imported. Normal package installation includes the new files;
no installer changes or personal-skill updates are needed.

See [selection, source pins and licensing](dependencies.md#bundled-pi-toolset-specialists).
Offline packaging and decision probes do not prove live host/model behavior.

## Full-suite partial failures

From a checkout, `./install.sh` reports each component independently. A failed
Hermes update does not undo successful Pi, command/TUI, tx, Claude Code or Codex
installation; the aggregate exit remains nonzero. Its summary extracts the updater's
structured cause and next action, including per-profile recovery errors. Truncated
or non-JSON output gets a bounded text fallback.

If the installer's Python is missing PyYAML, the terminal warns that Kit left the
Hermes plugin unchanged. Hermes still counts as failed in the summary and JSONL
receipt, and the command exits nonzero. The installer evaluates service restarts
in its separate restart phase.

Fix the reported cause, then retry only that component:

```sh
./install.sh --only hermes --dry-run
./install.sh --only hermes
```

Keep the original `--hermes-home` when using an alternate root. Verified clean
managed Hermes checkouts can recover from rewritten upstream history through the
[backed-up native transaction](installation.md#managed-checkout-recovery); unknown,
dirty, locally advanced or active/shared-unsafe sources defer. Recovery preserves
compatible native skill edits and requests no runtime restart. `--skip hermes`
leaves Hermes out; preview runs no updater or recovery network operation. This
Hermes-specific path does not replace portable hosts' own update commands below.
Fresh Hermes installation/probes use `plugins/kit` and enable `kit`. Verified
physical slots are discovery inputs only. Setup/update refuse duplicate registrations, including
same-source aliases, before component mutation; preserve the paths and reconcile
ownership rather than reinstalling over them. See [slot identity and setup](installation.md#install).
Source delivery is not installed adoption, native loader qualification or live activation.


<a id="legacy-marketplace-migration"></a>

## Automatic marketplace replacement

Normal `./install.sh --only claude,codex` and `./install.sh update --only claude,codex`
converge on the checked-in manifest names: `kit@kit` in Claude Code and
`kit@kit-marketplace` in Codex. No migration flag or alternative install name is used.

If the official Git source is registered under another name, the installer
**automatically removes that registration and its affected Kit plugin**, then adds
`TrebuchetDynamics/kit` under the canonical name if absent. It permits one replacement
attempt per host per invocation. This can discard the replaced plugin's cached copy
and enabled state. Canonical installed plugins retain their existing source and scope.

Removal requires one unambiguous, writable Git registration for the official source,
structured source and configuration evidence, and Kit-only affected installed plugins
and declarations. A marketplace name, local folder or successful/already-present add
message is not deletion authority. Managed, foreign, conflicting, multi-scope or
unknown ownership, another affected plugin, and a canonical name with a foreign source
stop the component before removal. Local sources are not replacement candidates.
The installer never edits private registries, purges caches broadly or removes unrelated
marketplaces/plugins.

After add/removal, structured readback must show the canonical name and owned source
before update/upgrade. The installed canonical plugin ID is checked at the end.
A false-success add cannot lead to an update of a nonexistent marketplace. Failure
reports partial state and returns nonzero; no rollback is attempted. Repair the
reported network, capability or ownership error, then rerun the same command. A rerun
after removal but before add resumes from the observed state without another removal;
a rerun after success updates the canonical install without replacement.

Dry-run runs no registry probe or mutation and reports `NOT_CHECKED`. Actual host CLI
initialization can write cache/auth state. Independent installer components continue
after a refusal. Stateful fake-host tests cover these boundaries through `install.sh`;
this is not live adoption evidence. Live replacement acceptance remains unrun and
requires an authorized disposable host with a prepared wrong-name fixture. Run
`./install.sh --only claude,codex` twice and compare marketplace names/sources and IDs
with `claude plugin marketplace list --json`, `claude plugin list --json`,
`codex plugin marketplace list --json` and
`codex plugin list --marketplace kit-marketplace --json` after each run.
Do not use a user's live configuration as a fixture.

## Claude Code

Requires Claude Code with plugin marketplaces. From this checkout:

```sh
claude plugin marketplace add .
claude plugin install kit@kit
```

Install the published Git source with:

```sh
claude plugin marketplace add TrebuchetDynamics/kit
claude plugin install kit@kit
```

`./install.sh` validates Kit identities in
settings/known-marketplace records and reads installed IDs with
`claude plugin list --json` during an actual install. It reuses an owned GitHub,
Git or verified Kit directory source. A valid canonical marketplace is not removed/re-added,
and its cached plugin is not uninstalled: an installed canonical plugin uses
`claude plugin update kit@kit --scope SCOPE`, keeping the selected installed scope.
A settings-only declaration uses its selected scope for install (user by default).
A mismatched official Git registration follows the replacement contract above.
Claude removal uses `claude plugin marketplace remove NAME --scope SCOPE`, which can
uninstall marketplace plugins. The installer checks installed IDs across scopes and
refuses other plugins, managed declarations, multiple affected scopes or installed
project records outside the current project. A replacement retains its single writable
user/project/local scope when installing the canonical plugin and adding the marketplace.
Foreign, conflicting, missing or unknown source records and stale directories stop
this component with ownership diagnostics. A stale path is not permission to delete
its entry. The installer does not rewrite registry/settings files itself. Unsupported
installed-list output requires host qualification, not fallback reinstallation.

Inside a session, `/plugin marketplace add TrebuchetDynamics/kit` and
`/plugin install kit@kit` do the same; run `/reload-plugins` or
start a new session. Add `--scope project` to the install to record it in the
repository's `.claude/settings.json` for everyone who works there. Invoke the
namespaced skills:

```text
/kit:plan-with-me questions only: ask one question about this project
/kit:plan-with-me challenge this plan; read-only, no implementation
/kit:plan-for-me investigate the next useful improvement; save the plan
/kit:plan-for-me
/kit:docs-sync update the docs and tasks
/kit:autoresearch debug the failing test
```

The marketplace entry lists `./adapters/skills/` as the plugin's only skills folder,
so the Hermes-only skills in the repository's root `skills/` folder are never loaded;
the plugin itself ships no hooks, agents, MCP servers or settings. Claude Code copies
the whole repository into its plugin cache, so adapter links into `skills/` resolve
there. Update with `claude plugin marketplace update kit` and then
`claude plugin update kit@kit --scope SCOPE` (use the original user, project or local
scope). The Claude manifest and its marketplace entry declare no `version`, so
Claude Code uses the source commit as the plugin version and each new commit is an
update; a pinned version would keep the cached copy until that string changed.
Remove with
`claude plugin uninstall kit@kit` (add the same `--scope` used
to install) and `claude plugin marketplace remove kit`. Removal does not
undo repository work or delete plans.

## Codex

Requires a Codex CLI with `codex plugin` support. The suite installer also requires
the effective-state list interfaces described below; older versions must be updated
or configured manually. From this checkout:

```sh
codex plugin marketplace add .
codex plugin add kit@kit-marketplace
```

Install the published Git source with:

```sh
codex plugin marketplace add TrebuchetDynamics/kit --ref main
codex plugin add kit@kit-marketplace
```

Start a new Codex session in your project. Invoke the namespaced native skills:

```text
$kit:plan-with-me questions only: ask one question about this project
$kit:plan-with-me challenge this plan; read-only, no implementation
$kit:plan-for-me investigate the next useful improvement; save the plan
$kit:plan-for-me
$kit:docs-sync update the docs and tasks
$kit:autoresearch debug the failing test
```

Use `$kit:docs-sync` in Codex; the Hermes spelling `/docs_sync`
is not a Codex slash command. Adding package files to a Git repository does not
install that plugin into your Codex configuration. After installation, use the
next turn if the client refreshes skill discovery; otherwise start a new session.

Codex uses skill invocation, not Hermes slash-command registration. The adapters
are explicit-only in Codex (`allow_implicit_invocation: false` in each
`agents/openai.yaml`) so installation does not automatically invoke a workflow.
Update a Git install with `codex plugin marketplace upgrade kit-marketplace`
(it refreshes Git marketplace snapshots only); remove with
`codex plugin remove kit@kit-marketplace`. Removal does not
undo repository work or delete plans. The marketplace registration remains until
`codex plugin marketplace remove kit-marketplace`.

During an authorized actual install/update, `./install.sh` first runs:

```sh
codex plugin marketplace list --json
codex plugin list --marketplace kit-marketplace --json
```

It requires supported JSON containing marketplace names, roots and
`marketplaceSource` metadata, plus resolved installed IDs, sources and enabled
state. Missing capabilities, failed/malformed reads, unknown/mismatched sources,
and stale local sources stop the Codex component before marketplace/plugin changes.
A mismatched official Git registration follows the replacement contract above. Because
these lists do not include configuration-layer ownership, replacement also requires
native `codex app-server` `config/read` with `includeLayers: true` for the current
working directory. This is a bounded configuration probe, not a model/session run.
Only an exact base-user registration in the effective Codex home's `config.toml`
qualifies. Shadowed, project, profile, system/managed or unknown registrations and
non-user affected plugin declarations hold before removal. Unsupported layer probing
also holds. The native commands are `codex plugin remove kit@NAME` when installed,
then `codex plugin marketplace remove NAME`; no configuration file is edited by Kit.
A qualified canonical Git source uses `marketplace upgrade` without remove/re-add; a local
source stays local. An already installed canonical Kit plugin is not added again,
so its effective enablement and configuration scope are not rewritten. A fresh
plugin uses `plugin add kit@kit-marketplace`.

These lists describe **effective configuration**, not every persisted scope. They
do not prove shadowed registrations absent; replacement additionally checks native
configuration layers. Dry-run prints planned validation without starting either CLI.
See the shared replacement and recovery contract above for failure and live limits.

## Pi coding agent

Pi-Bolt is the only Pi harness Kit installs. From this checkout, use
`./install.sh --only pi-bolt,pi` to refresh/install Pi-Bolt then the Kit package
through its verified destination executable. `--only pi` requires that destination;
on failure run `./install.sh --only pi-bolt,pi`. No stock `pi` is run by the installer,
and no Node/npm bootstrap is needed for this native path. Stock Pi installed by
you remains supported and shares the package store; it is never replaced by Kit.

For manual package management in an already installed stock Pi with package
manifests and extension commands (its own Node prerequisites still apply), from
this checkout:

```sh
pi install .
```

Install the published Git source with:

```sh
pi install git:github.com/TrebuchetDynamics/kit
```

Use `/reload` in an existing Pi session, or start a new one inside your project.
Local installs refer to this checkout; keep it in place. The extension registers:

```text
/plan-with-me questions only: ask one question about this project
/grill-me challenge this plan; questions only, no implementation
/plan-for-me investigate the next useful improvement; save the plan
/plan-for-me
/docs-sync update the docs and tasks
/autoresearch-debug diagnose the failing test
```

All 13 `/autoresearch-<protocol>` commands are available. The other commands are
`/autoresearch`, `/impeccable`, `/ui-taste`, `/unslop`, `/beautify-github-readme`,
`/lgtm` and `/git-commit-push` (`/git-commit-push pull` or `merge <branch>` integrates
upstream changes). The engineering pack is a reference, not a command; no
`/engineering` or `/skill:engineering` entry is registered. Native `/skill:<name>`
invocation is available for the registered skills; both skill names and command
aliases use hyphens. Underscore aliases
are no longer registered in Pi; update saved prompts and shortcuts, then `/reload`
after updating the package. Hermes Telegram aliases are unchanged.
Command arguments remain literal prompt text.
`/grill-me` loads Plan With Me with explicit challenge mode and preserves the
request unchanged. The old standalone `grill-me` skill is no longer discoverable;
use `$kit:plan-with-me` in Codex or `/skill:plan-with-me` in Pi with
`challenge` in the request. Autoresearch stays independent; its `plan` selector
routes to Plan For Me, which reads the pinned plan protocol directly, never back
through Autoresearch. All other selectors retain their shipped protocols.
A command entered during an active turn is queued as a follow-up, not injected as
shell code. A same-name third-party skill keeps the first one discovered and Pi
warns; same-name extension commands are all kept but renamed `/name:1`, `/name:2`
without a warning. Check `/` completions rather than assuming this package replaced them.

Use Pi's package controls (`pi list`, `pi update --extensions`, `pi remove <source>`)
for management. `./install.sh` also refreshes a registered package that lacks a skill
folder this checkout ships (a release that added `orbi` left `/skill:orbi` and `/orbi`
missing until then) and clears an empty `skills: []` or `extensions: []`
filter on this package: a filter recorded in `pi config` survives `pi install` and `pi update` and
hides every command and `/skill:<name>`. Non-empty filters are kept. Removing the
package leaves repository documents and commits intact.

### Pi-Bolt runtime

`./install.sh` installs [Pi-Bolt](https://github.com/opensec-git/Pi-Bolt), Pi
compiled to one native executable, as `pi-bolt` in the Kit binary directory. It runs
the same commands and reads the same `~/.pi/agent` configuration and installed Pi
packages. The `pi-bolt` item runs before the `pi` package item, which uses only
that destination Pi-Bolt for install/update. A stock Pi also sees this package
without a second install. See
[Pi-Bolt installation](installation.md#pi-bolt-native-executable).

### Nous Portal through the local proxy

The executor's `setup-portal` command and TUI provider bridge are removed. Ordinary
Pi model/provider configuration and Hermes subscription-proxy functionality remain
upstream-owned; Kit does not copy credentials, start proxies or configure a runner.
Consult [Hermes proxy documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/subscription-proxy)
and [Pi compatible endpoints](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md#configure-a-compatible-endpoint)
for a separately authorized interactive setup. The
[prior setup and qualification limits](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/cross-host.md#nous-portal-through-the-local-proxy)
remain evidence; no live login, inference or delivery is established by removal.

### Removed executor

Use [GitHub/Orbi delivery](github-native.md); Orbi remains paused and
live-unqualified until the cutover pilot succeeds. Preserve existing task records,
worktrees, attempts and recovery state; they are not an executable queue.

## Behavior and verification

The adapters ask native questions, inspect files and publish GitHub issue handoffs
through [Plan Handoff](../skills/shared/PLAN-HANDOFF.md). Explicit manual execution
retains its own accepted scope, ownership, checks and PR/review gates. There are
no bundled parallel-worker templates, service installers or provider setup CLI.

Package installation does not install external integrations, change approval
policies, copy credentials or alter model/memory settings. Host permissions and
repository instructions still apply. Ordinary Pi provider setup belongs to Pi.
Skills are discoverable instructions, not proof of executed workflows. Orbi stays
paused and live-unqualified until [cutover](github-native.md) is separately verified.

Offline checks:

```sh
python3 -m pip install -r requirements-test.txt
python3 -m unittest discover -s tests -p test_portable_package.py
node --test tests/portable_pi.test.mjs
claude plugin validate . --strict   # needs the Claude Code CLI
```

Installed checks on Linux at source `61e8e4b7` used Pi 1.5.2, Claude Code
2.1.322 and Codex CLI 0.167.2 in separate configuration directories. Native Git
installation and update commands succeeded on all three. Claude's component
inventory listed 34 adapter skills, zero agents, hooks, MCP servers and LSP
servers; the Codex installed payload also contained 34 adapter entries. Pi RPC
reported 47 Kit extension commands. These are tested versions and counts for that
source, not minimum-version guarantees or evidence that every workflow ran.

Claude's ordinary `plugin validate` passed with a warning that root `CLAUDE.md`
is not loaded as plugin project context. `--strict` returned 1 for that warning;
it must not be reported as passing on this version. The validator also reported
an advisory missing directory-listing icon. Kit's adapters load their own shared
and canonical instructions; they do not rely on root `CLAUDE.md` being injected.
No Claude model workflow was run: the isolated host reported no authentication.

Pi and Codex each ran the installed Plan With Me adapter with `gpt-6.1-sol`, low
reasoning, and the explicit questions-only caching prompt above. Pi used
`openai-codex`, RPC dispatch and read-only tools; Codex used a read-only sandbox.
Each returned one relevant question and left the initially empty target directory
empty. Existing authentication was referenced through owner-local links, not copied
into the package. This establishes one bounded installed model smoke per host,
not full planning publication, response quality across tasks, Orbi delivery,
Hermes/Telegram execution or production acceptance. Real host profiles were not
selected as install/update targets.

Archive extraction tests separately check installed references, literal arguments
and queued commands without checkout files or configured live accounts. Follow
the question-only smoke with a separately scoped planning/publication and delivery
exercise to qualify those remaining behaviors. Earlier versions and package counts
remain in Git history; they do not qualify the current source.

Host documentation: [Claude Code plugins](https://code.claude.com/docs/en/plugins/manifest-reference),
[Claude Code marketplaces](https://code.claude.com/docs/en/plugins/marketplace-reference),
[Codex plugin schema](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/manifest.rs),
[Pi packages](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md),
[Pi extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md).
