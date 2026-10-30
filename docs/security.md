# Security and ownership model

## Trust boundary

Paseo plugins execute unsandboxed client and daemon code. This plugin is not a filesystem sandbox. Review its source and dependencies before installing it on a daemon with access to private repositories or provider credentials. No telemetry, public listener or extra durable service is implemented.

In the verified Paseo 0.13 source, `plugin.rpc.invoke.request` requires `daemon.manage` (packages/server/src/server/authorization/operation-permissions.ts). The public PluginHandlerContext exposes a PaseoApi but no end-user principal. This plugin does not invent `context.auth` or infer authorization from network encryption. Operator grants are shared by authenticated daemon managers. Mutually untrusted managers need an upstream principal-bearing API and per-user authorization before using execution grants.

## Read boundaries

- Server-side `autowork capabilities` and `ls --json` are the discovery/health authority. `autowork blockers` is intentionally never called because it starts an agent.
- Clients submit opaque discovered repository IDs, not arbitrary paths, executable names, environment variables, CLI arguments or shell commands. Workspace directory matching only filters the known fleet in the client.
- Git roots/common-directory identity and filesystem device/inode are revalidated before commands; symlink aliases, replacements and disappeared repositories refuse actions.
- Committed task records come from `tasks list/show --rev`. Read RPCs do **not** use `--worktree`: upstream transactional working-tree reads can recover interrupted writes. No second task parser is implemented.
- Logs are fixed, bounded `autowork logs --lines 150` snapshots. Credential-like strings are redacted. Streamed command stderr is buffered through complete lines before redaction, including cross-line Bearer prefixes; a successful exit flushes the final line, while failure withholds an incomplete final line from streaming callbacks. Buffering remains subject to the command output byte limit. Redaction is best-effort pattern matching, not a guarantee that arbitrary output contains no secrets. No unrestricted file/log path endpoint exists.
- Effective state, capture times, source revisions and missing evidence are kept distinct. Unknown transport/delivery/runtime metadata is never guessed from configured defaults or stale records.

## Mutation boundaries

- Default policy grants no planning, owner answers or controls. A server-only operator policy file supplies explicit grants; no UI settings RPC can write it.
- The executable is resolved to an absolute regular executable. Changes to its identity or reported Autowork release refuse further dispatch until reload/requalification.
- `prepare` refreshes canonical state and produces a 60-second ticket bound to generation, identity/revision, payload, service state and effective publication policy. `commit` consumes it before any asynchronous dispatch.
- A repository has one reserved writer. Duplicate confirmations retrieve the original operation, not another command; unknown generations cannot reuse old tickets. Buffers, subprocesses, outstanding requests, sessions and retained operations are bounded.
- Controls use fixed argv arrays with `shell: false`. No foreground run, force, stop-workers, model changes, live grants, push grants, task completion or Git commands are exposed.
- Owner direction uses `tasks decide --expect <record hash>` and literal positional text after `--`. Concurrent or uncommitted record changes cause refusal. An answer changes notes/optional section through Autowork, not typed privilege fields, and remains uncommitted.
- Exit status, actual service observation and uncertain outcomes are separate. An error after possible dispatch is retained as uncertain; no automatic retry follows it. Explicitly inspect canonical state before another action.
- The adapter strips inherited Git routing and ambient runner-policy overrides from command children, preventing an unrelated shell's push/live settings from becoming a new grant. Existing service grants remain Autowork's authority.

## Planning ownership

Only explicit operator-granted, owner-confirmed planning creates a bridge child. It loads the selected release's existing Planner and PlanningHub using the official bootstrap; no prompts, planning engine, provider or scheduler are duplicated. Python isolated mode ignores ambient Python paths and user site packages. The host passes an absolute trusted source and interpreter, never a client-selected one.

The planning state root is separate from source, repository and upstream/Paseo session stores, under a fresh plugin generation. Both sides enforce owned-session/canonical-repository binding. Reconnect reads reuse handles; reload refuses to adopt retained or externally-created sessions. Steering and cancellation address only this instance's planning turns. Workers, reviewers and Paseo-owned Pi sessions are never attached, adopted, terminated or steered.

Apply needs the valid nonempty preview revision and a consumed explicit ticket. The existing Planner validates staging, task contracts and authority. Planning completion does not call Apply or Start. Inspection does not interrupt workers. Existing authorized runners may subsequently execute applied accepted tasks; this is not new execution authority.

Shutdown closes the planning bridge's input so upstream PlanningHub cancels and joins its own turns. Cleanup has a deadline and signals only the owned direct child if necessary; a forced/incomplete shutdown is reported as uncertain. No PID read from runner state or process group is signalled. Retained histories/worktrees are preserved, not silently cleaned up. This is cooperative ownership, not containment of malicious trusted code or uninterruptible kernel tasks.

## Deployment restrictions

The build did not install, enable, reload or restart an existing Paseo daemon; make provider calls; operate real runners; alter credentials; or publish remotely. Android connectivity, actual authenticated permission denial and live planning/service behavior require separate qualification. Do not infer these from Node tests or a fake session host.
