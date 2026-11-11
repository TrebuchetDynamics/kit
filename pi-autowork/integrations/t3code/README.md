# Autowork for T3 Code — experimental native plugin

A native **Autowork right panel** and **Autowork: refresh overview** palette command.
Inspect configured repositories, the runner's next action, blockers, committed tasks,
selected-task guidance and recent logs. Everything is read-only. This is a separate
visual integration; it does not use an MCP bridge, install skills, run models or
start/control Autowork runners.

**Stock T3 Code is unsupported.** This targets the experimental
[ashx-j/t3code `feat/plugin-system` branch](https://github.com/ashx-j/t3code/tree/eefaf41b7188fdaf619cdb47a4ad922a8209bb22),
associated with [upstream PR #33606](https://github.com/pingdotgg/t3code/pull/33606).
Compatibility is pinned to commit `eefaf41b7188fdaf619cdb47a4ad922a8209bb22`,
not a released official plugin contract. The manifest version range alone cannot
identify whether a host contains this branch. No installed T3 application is modified
by building this folder.

## Build and package

Requires Node 24+ (the experimental server's requirement), npm and network access
for the pinned SDK source bootstrap. The SDK is not published on npm. Its actual
source files and Vite preset are fetched from the reviewed commit and verified with
SHA-256 digests in `sdk-source.json`; no SDK declarations are reproduced or mocked.
The upstream package's monorepo build scripts and catalog dev dependencies are omitted
from the temporary `.sdk/package.json`; its exports and actual source stay intact.

From this folder:

```sh
npm run sdk:fetch
npm ci --ignore-scripts
npm run check
npm run package:check
```

`npm run check` typechecks the server against the real SDK, builds the web entry
with the actual SDK Vite preset, and runs boundary, subprocess, native registration
and React rendering tests. The renderer emits its upstream deprecation notice; it
is a development-only test dependency. Dependency versions and integrity hashes
are locked. Rolldown is pinned to a compatible cached version within Vite's declared
range; the renderer's dependencies use integrity-locked registry tarballs.
On a provisioned cache, `npm ci --offline --ignore-scripts` works after SDK bootstrap.

`npm run package:check` creates and extracts the tarball, checks manifest entries and
loads the CJS server without development dependencies. The resulting tarball contains `t3-plugin.json`, `server.cjs`, `core.cjs` and
`dist/web.js`. It includes no `node_modules`, SDK source, private settings or runtime
state. Extract it and use its `package/` folder, or use this built folder directly.
The build shares T3's React via the real SDK preset rather than shipping another copy.

## Use only with a separately prepared experimental host

Follow that branch's [plugin user guide](https://github.com/ashx-j/t3code/blob/eefaf41b7188fdaf619cdb47a4ad922a8209bb22/docs/user/plugins.md).
In that host, open **Settings → Plugins → Add plugin → Link a plugin folder**, enter
this built folder's absolute path, configure it and enable it. Alternatively install
the extracted package folder through **Add plugin**. Reload after rebuilding a linked
plugin. This repository does not install or replace the user's host.

Settings:

- `executable`: absolute path to an existing, trusted `autowork` executable.
- `repositories`: up to 32 absolute repository paths to expose to this environment.

Use the thread's right panel add menu to choose **Autowork**. Select a repository,
then select a task for its engine-provided guidance. Expand recent activity to read
logs. **Refresh** and the palette command refresh open panels; when none is open,
the command explains how to open one. The pinned SDK has no programmatic panel-open
API, so the command does not navigate through guessed routes.

The CLI must support these existing read contracts:

```text
autowork ls --json
autowork tasks list ABSOLUTE_REPOSITORY
autowork logs ABSOLUTE_REPOSITORY --lines 60
```

The adapter expects `runners[].display` (`state`, `needs`, `blockers`) and task
`display` (`state`, `why`) from the repository's current canonical presentation.
It does not infer readiness, completion or next actions from status text. Missing
presentation is shown as unavailable. Repository settings also allow inspecting a
task store without a registered runner. Task reads use the CLI's committed-store
default. The three reads form an explicitly refreshed snapshot, not an atomic
transaction; records can change between them.

## Boundaries and current qualification

These are trusted plugins running with the server user's access. The host's
permissions list is descriptive, not a sandbox. Every session with environment read
access, including a guest, may read configured repository labels, tasks and logs.
Configure only repositories suitable for those readers. Settings paths are likewise
visible to environment readers under the host contract.

Only opaque configured repository identifiers cross the RPC selection boundary.
The server rechecks configuration per request. It executes fixed argv arrays with
no shell, strips ambient Git/Autowork authority overrides, allows at most two active
snapshot reads, and stops children on caller cancellation or plugin deactivation.
Each command has an 8-second deadline and 192 KB combined-output limit; returned
snapshots must fit 240 KB. At most 100 tasks, 128 blockers and 60 log lines are shown.
Larger/unsupported responses fail explicitly rather than claiming the repository
is empty. No private Autowork state files are parsed.

Common credential patterns and control characters are removed from displayed text;
this is best-effort redaction, not a guarantee that arbitrary logs contain no secrets.
Raw stderr and malformed CLI JSON are not sent to clients. React renders output as
text. UI errors provide generic configuration/retry guidance instead of host paths.

Offline checks cover the real pinned SDK types and preset, generated bundle
registration/rendering, a fake executable's literal argv, missing executables,
output/time bounds, cancellation, malformed payloads and redaction. **Native loading
in an actual experimental T3 host, browser accessibility/visual inspection, remote
sessions and sustained live CLI operation remain unqualified.** No model execution,
runner control, service installation or live acceptance is implied by these checks.
