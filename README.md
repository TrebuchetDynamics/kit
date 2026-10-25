# Autowork for Paseo

Manage an existing Linux Autowork installation from Paseo's native interface: fleet, tasks, blockers, staged planning and confirmed runner controls. The same React Native contributions target Android, desktop and web. This is a plugin, not a provider, scheduler or bundled Autowork engine.

**Status:** working offline-tested implementation, including real Paseo compiler and isolated server loading. Physical Android and Linux Desktop UI qualification is **pending**. No existing daemon was installed, enabled or reloaded during development. See [qualification](docs/qualification.md).

## Requirements

- Paseo **0.13.x**, both daemon and connected app. The manifest intentionally refuses unqualified later minor versions.
- Linux daemon host, Node 24+, existing `autowork` on its trusted PATH, Git and Python 3.11+.
- Autowork capabilities `prepare_api: 4`, JSON fleet and task commands, and current planning controller interfaces. Development read-only smoke used installed release `01e37ea049c3153948ebfbbdb54aff38fe749266`.
- For opt-in planning: the existing configured Pi installation/provider and ignored canonical `.worktrees/`. The plugin neither installs a model/runtime nor edits credentials.

## Install, only after reviewing trusted code

Paseo plugins are **trusted and unsandboxed**. Installing one grants code execution as the daemon user. Review [security](docs/security.md) and install only into the intended host.

From a local checkout on the daemon machine:

```sh
npm ci --ignore-scripts
npm run check
paseo plugin install /absolute/path/to/paseo-autowork
paseo plugin ls
```

Select **Autowork** in Paseo's sidebar on that host. Use Paseo's existing host picker; inventories and caches never merge across hosts. Offline/unknown hosts show unavailable state, not another machine's fleet. The workspace/agent panels show only known repositories matching that workspace directory.

If plugins are globally disabled, enable them yourself only after consenting to Paseo's trust warning. These installation commands are instructions, **not actions performed by this repository**. No public Git source or registry release has been created yet; use the local directory until a separately reviewed publication exists.

## Read-only by default

Without configuration the plugin discovers repositories already known to `autowork ls --json`, reuses Autowork's health and owner-question interpretation and exposes committed task inventory, committed contract detail, logs and evidence labels. It makes no model calls and exposes no mutation grants. Missing transport, runtime-version or delivery evidence is shown as **unknown**, never inferred from configured defaults or historical in-flight records.

- Fleet and active task views refresh at most every 20 seconds while foregrounded and online, with bounded error backoff. Pull-to-refresh or use Refresh for a fresh read.
- The server shares a five-second collector cache and one in-flight fleet read per plugin installation. Capture time and source revision remain visible.
- `aw-status`, `aw-tasks`, `aw-plan` and `aw-blockers` open the native workspace. `/aw-plan` optional text is a draft objective, not permission to run a model.
- A healthy systemd process does not imply productive engineering. Canonical stalled/paused/waiting states remain distinct.
- Closure labels distinguish manual closure, verified closure, missing/invalid receipts and absent provenance. Uncommitted task edits are not presented as accepted committed scope.

## Opt-in host policy

The plugin deliberately has **no client toggle that grants execution**. An operator can provide a private JSON policy file and set `PASEO_AUTOWORK_CONFIG` in the **daemon's environment**:

```json
{
  "executable": "/usr/local/bin/autowork",
  "repositories": ["/srv/projects/example"],
  "planning": true,
  "decisions": true,
  "controls": ["pause", "resume", "stop", "restart", "start"]
}
```

Use an absolute, daemon-user-owned regular file, not a symlink; make it mode `0600`. Omit unneeded grants. `repositories` adds exact canonical Git roots to the known fleet; it does not start services. Executable resolution is server-side and must be absolute when configured. Unknown repository paths cannot be submitted through RPC.

An already-running daemon does not inherit a later shell export. Apply environment/startup changes through your existing, separately authorized Paseo deployment procedure, then explicitly reload this plugin. The plugin never changes daemon configuration, enables itself, installs services automatically on load or refreshes credentials. Inspect granted operations before use.

Paseo 0.13 requires `daemon.manage` for plugin RPC but its public handler has no end-user principal. Therefore these additional grants are **shared by authenticated daemon managers**, not a per-user ACL. Do not use this policy model with mutually untrusted managers.

## Planning and decisions

1. Choose Planning and optionally enter an objective. Empty objective uses existing autonomous `/plan_for_me` discovery.
2. Prepare and confirm Start; the existing Autowork Planner and PlanningHub own the turn, task staging and private histories.
3. Progress, follow-up, steering and cancellation apply only to sessions created by this plugin generation, never Autowork workers or Paseo-created agent sessions.
4. Read history/roadmap/preview. A proposal stays unaccepted until **Prepare Apply exact preview** and explicit confirmation; Autowork revalidates the exact revision and repository authority.
5. Apply creates a local commit through Autowork. It does not grant push or start a service. Existing authorized runners may pick up newly accepted tasks.

Planning state lives under the daemon user's `XDG_STATE_HOME/paseo-autowork/planning/<generation>/` (or `~/.local/state/...`). It contains upstream-owned planning records, not a new event database. On disable/reload, owned turns are cancelled and cleanup is bounded. Retained worktrees/history are not deleted. After reload the plugin refuses to adopt old sessions whose active ownership it cannot prove; use existing Autowork tools to reconcile them.

Only current canonical owner questions for open tasks expose Answer. Answers use `autowork tasks decide --expect <displayed record hash>` and leave an **uncommitted local task edit**. Free text never changes typed live/publication grants or manufactures completion. Technical holds and accepted deferrals remain inspection work, not invented owner questions.

## Runner controls

Allowed controls use fixed Autowork argv, never arbitrary shell: start, pause, resume, stop and default restart. Start may install/start a user service and incur model use; the confirmation says so. No force, stop-workers, process-group killing, model changes, task closure or Git operations are exposed.

Each action needs a short-lived single-use confirmation bound to the plugin generation, exact repository identity/revision, service state, payload and effective publication policy. Changed targets, expired confirmations and stale generations are refused. Duplicate submissions return the retained operation, not another dispatch. A command exit and observed service state are distinct. Unknown delivery/timeouts are never automatically retried.

## Development and packaging

```sh
npm ci --ignore-scripts
npm run typecheck              # native client without DOM/Node globals; separate Node server/test config
npm test                      # disposable repositories, fake CLI/controller and isolated real Paseo runtime
npm run package:check
npm pack --ignore-scripts     # creates an installable source archive; does not publish
```

Host modules are pinned development dependencies only; Paseo supplies its runtime instances. The source archive contains client/server/shared entries, no Autowork engine, node_modules, credentials or private runtime state. No build step or postinstall daemon activation is required.

For upgrades: review code and compatibility, run checks, then `paseo plugin reload paseo-autowork` on the chosen daemon. This is an explicit trusted-code operation. Remove with `paseo plugin remove paseo-autowork`; source repositories, Autowork services, tasks and retained planning work remain. No automatic restore, cleanup or worker interruption is performed.

See [architecture](docs/design.md), [security](docs/security.md), [qualification](docs/qualification.md) and [ranked follow-ups](docs/follow-ups.md).

## Official references

- https://paseo.sh/docs/plugins
- https://paseo.sh/docs/plugins/reference
- https://github.com/getpaseo/paseo/tree/72e3316f4f5dfe775c77dbf998968c92e2de9019/packages/plugin
- https://github.com/TrebuchetDynamics/autowork
