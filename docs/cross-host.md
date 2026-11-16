# Claude Code, Codex and Pi installation

> **GitHub-native delivery:** GitHub Issues own executable work; Orbi owns delivery.
> pi-autowork is retired and unsupported. See [setup and support](github-native.md).

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

## Planning and delivery

Both planners publish GitHub Issues and stop. Orbi owns automatic delivery.
Retained authorized fix/apply modes keep their scope, actual ownership, checks,
independent review and PR gates. Orbi remains paused and live-unqualified.

## Orbi lifecycle controls

Use `/kit:orbi [status|setup|start|stop|help]` in Claude Code, `$kit:orbi` in Codex,
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
Pi/Pi-Bolt bootstrap and active supported integration restarts. Restricted Hermes
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
no argument reports it (default `full`). The other commands report without edits.
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
legacy physical slots are discovery/migration inputs only: no supported Autowork
CLI or executor is restored. Setup/update refuse duplicate registrations, including
same-source aliases, before component mutation; preserve the paths and reconcile
ownership rather than reinstalling over them. See [slot identity and setup](installation.md#install).
Source delivery is not installed adoption, native loader qualification or live activation.


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

`./install.sh` validates both canonical `kit` and legacy `autowork` names in
settings/known-marketplace records and reads installed IDs with
`claude plugin list --json` during an actual install. It reuses an owned GitHub,
Git or verified Kit directory source. It does not remove/re-add that marketplace
or uninstall its cached plugin: an installed canonical plugin uses
`claude plugin update kit@kit --scope SCOPE`, keeping the selected installed scope.
A settings-only declaration uses its selected scope for install (user by default).
Foreign, conflicting, missing or unknown source records, stale directories and
legacy registrations stop this component with [migration guidance](#legacy-marketplace-migration).
A stale legacy path is not permission to delete its entry. The installer does not
rewrite registry/settings files itself. Unsupported installed-list output also
requires host qualification, not fallback reinstallation.

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
scope); remove with
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
codex plugin list --marketplace autowork-marketplace --json
codex plugin list --marketplace kit-marketplace --json
```

It requires supported JSON containing marketplace names, roots and
`marketplaceSource` metadata, plus resolved installed IDs, sources and enabled
state. Missing capabilities, failed/malformed reads, unknown/mismatched sources,
stale local sources and legacy/coexisting registrations stop the Codex component
before marketplace/plugin changes. There is no removal fallback. A qualified
canonical Git source uses `marketplace upgrade` without remove/re-add; a local
source stays local. An already installed canonical Kit plugin is not added again,
so its effective enablement and configuration scope are not rewritten. A fresh
plugin uses `plugin add kit@kit-marketplace`.

These lists describe **effective configuration**, not every persisted scope. They
do not prove shadowed registrations absent. CLI initialization may write cache or
auth state; these are not zero-side-effect probes. Dry-run invokes no registry
probes or mutations, reports migration/registry status as `NOT_CHECKED` and prints
planned validation. Independent installer components continue after a refusal.
This is offline-tested compatibility behavior, not live adoption evidence.

## Legacy marketplace migration

The deprecated marketplace names are Claude `autowork` (`kit@autowork`) and Codex
`autowork-marketplace` (`kit@autowork-marketplace`). Their replacements are `kit`
(`kit@kit`) and `kit-marketplace` (`kit@kit-marketplace`). The plugin name and
portable skill routing remain `kit`. Existing registrations are **not** migrated
automatically, even when their source directory is gone.

1. Stop Kit work in the affected host. In the **same effective configuration
   context** as the installer (working directory, environment and configuration
   selection), inspect registrations and installed plugins. For Claude use
   `claude plugin marketplace list --json` and `claude plugin list --json`; for
   Codex use the three filtered commands above. Also inspect inherited/project
   overrides and any other contexts you use. Effective lists cannot establish that
   every persisted scope was inspected. If a command is missing or its output lacks
   required source metadata, update to a supported host or use its documented manual
   setup. Do not guess alternate syntax or edit private registries.
2. Make private backups of configuration, plugin data/options/secrets, source
   directories and existing recovery evidence. Record old IDs, source kind, URL/path,
   ref/revision, scope and enabled state, plus unrelated plugins using either
   marketplace. Keep the old checkout/revision for rollback; do not overwrite the
   only copy. Backups may contain credentials: never commit or publish them.
3. Separately authorize each host removal. If canonical and legacy coexist, decide
   which source and scope to retain; do not blindly remove either. Marketplace
   removal can affect other plugins: do not proceed until unrelated plugins and
   user data have a safe preservation plan. For an intended legacy Claude removal,
   use the installed scope (replace `SCOPE` with `user`, `project` or `local`):

   ```sh
   claude plugin uninstall kit@autowork --scope SCOPE --keep-data
   claude plugin marketplace remove autowork --scope SCOPE
   ```

   `--keep-data` preserves the data directory, not a guarantee that options/secrets
   or ID-bound data transfer to `kit@kit`. Keep backups and follow your host version's
   documented behavior. Managed declarations require the administrator, not a bypass.
   For a separately authorized Codex removal in the reviewed context:

   ```sh
   codex plugin remove kit@autowork-marketplace
   codex plugin marketplace remove autowork-marketplace
   ```

   **Codex has no promised keep-data behavior here.** Removal/addition is not data
   migration or scope-complete cleanup. Recheck inherited/project overrides after
   removal; a hidden registration may become effective. Never delete recovery inputs
   or manually rewrite registry files to suppress that result.
4. After reviewing the new source, separately authorize adding its canonical
   marketplace and plugin with the fresh commands in the Claude/Codex sections.
   Preserve your original source kind, ref and scope: use the intended local source
   path instead of the published Git source when applicable, and retain a selected
   ref rather than blindly changing it to `main`. For Claude add/install at the
   selected `--scope`. Do not re-add an already intended canonical registration.
   Restore data/options deliberately using supported host procedures, preserving
   unrelated changes. On failure, stop and use the recorded source/revision and
   private backups with the host's supported commands to restore the old setup;
   there is no automatic rollback or guaranteed data transfer between IDs.
5. Repeat the effective-state checks in each relevant context and inspect overrides.
   Verify only one intended active Kit registration, with the correct source, scope
   and enablement, then reload/start a new session and verify discovery. Source
   deprecation alone does not establish disappearance of installed resources.

No live migration on installed host versions is qualified by these instructions or
the fake-host tests. Live removal, installation and workflow acceptance need separate
authorization and evidence.

## Pi coding agent

Requires Pi with package manifests and extension commands, and Node 22 or later. From
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
`/autoresearch`, `/impeccable`, `/ui-taste`, `/beautify-github-readme`,
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
filter on this package: a filter recorded in `pi config`, including one carried from
the package's previous `autowork` name, survives `pi install` and `pi update` and
hides every command and `/skill:<name>`. Non-empty filters are kept. Removing the
package leaves repository documents and commits intact.

### Pi-Bolt runtime

`./install.sh` also installs [Pi-Bolt](https://github.com/opensec-git/Pi-Bolt), Pi
compiled to one native executable, as `pi-bolt` in the Kit binary directory. It runs
the same commands and reads the same `~/.pi/agent` configuration and installed Pi
packages, so the Kit package above serves it without a second install. See
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

The pi-autowork executor, service installer, task CLI and Paseo integration are
removed. Do not start or install them. Preserve existing task records, worktrees,
attempts and recovery state; they are migration evidence, not an executable queue.

The [prior runner contracts and qualification gaps](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/cross-host.md#run-autowork-continuously)
remain immutable evidence. Removal does not satisfy outstanding live checks or
grant a replacement the same capabilities. Use [GitHub/Orbi delivery](github-native.md);
Orbi remains paused and live-unqualified until the cutover pilot succeeds.

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

Validated locally with Claude Code 2.1.300: `claude plugin validate . --strict`
passed, and a marketplace add and install into an isolated configuration directory
listed exactly the 13 adapter skills (no root `skills/` entries, hooks, agents or MCP
servers) with all adapter links resolving in the installed copy. No Claude Code model
session has run a workflow from it yet.

Validated locally with Codex CLI 0.162.1 and Pi 1.2.0: native marketplace/plugin
and Pi installation into isolated temporary homes, Codex app-server skill discovery
and Pi's installed resource loader discovered 11 portable skills and Pi loaded 25
commands, including the then-spelled `/grill_me` compatibility command and all 13
research selectors. That run
predates UI Taste, Beautify GitHub README and the Git Pull Merge merge into Git Commit
Push. Those historical counts do not describe the current package. Current adapter
discovery comes from `package.json`, the host manifests and `adapters/skills/`;
`tests/portable_pi.test.mjs` checks the current registered command set. Earlier host
installation records do not qualify the current package on every host.
Archive extraction tests check installed references, literal
arguments and queued commands without checkout files. No credentials or configured live accounts are used. These are
tested versions, not an established minimum-version guarantee.
These checks do not prove model output quality, Git delivery or Telegram execution.
The model smoke test is the questions-only invocation above: one useful question,
no repository edits. Follow it with planning and a bounded disposable-repo task
when you want to qualify end-to-end behavior with your configured model.

Host documentation: [Claude Code plugins](https://code.claude.com/docs/en/plugins/manifest-reference),
[Claude Code marketplaces](https://code.claude.com/docs/en/plugins/marketplace-reference),
[Codex plugin schema](https://github.com/openai/codex/blob/main/codex-rs/core-plugins/src/manifest.rs),
[Pi packages](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md),
[Pi extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md).
