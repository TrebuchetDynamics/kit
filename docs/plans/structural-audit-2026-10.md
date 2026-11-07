# Autowork source layout and maintainability contract

## SDD maintainability refactor

Status: Accepted behavior contract. Current Python owners use lowercase `src/`.
The [one-product-root contract](pi-autowork-component-layout.md#one-product-root-contract)
owns the planned destination, complete migration batch and test relocation. This
page retains required behavior, not the completed audit or its task reports.
No relocation, runtime activation or live qualification is implied by documentation.

### Layout and source-loading contract

- The release-local bootstrap loads only the selected tree's bootstrap and sources.
  Never borrow cwd, another installation, site-packages or a foreign cached module.
- `activate(root) -> Layout`, `load(root, module)` and `run(root, module, argv)` form
  the runner boundary. `root` is the selected Kit resource/release root, not the
  consumer repository. Layout resolves actual sources, public entrypoints and
  resources separately. Source discovery is sorted and bounded, excludes tests,
  fixtures and caches, rejects escaping symlinks, and supports a linked root.
- Canonical runner names are `pi_autowork.*` and `pi_autowork.engine.*`. Public flat
  engine imports alias the same module objects in either import order, preserving
  classes, exceptions, mutable globals and monkeypatches. A bound foreign runner
  package refuses; supported release switching execs before importing the new tree.
- Preserve selected-release locks, pruning and child inheritance, and the meanings
  of `PI_AUTOWORK_TOOLSET`, `COMPONENT`, `PACKAGE` and `SCRIPT`. Keep state schema
  literals at the public `parallel_state.py` path for older text-reading callers.
- Public executable adapters preserve signatures, argv/stdin, exceptions,
  KeyboardInterrupt and exit behavior without executing a canonical body twice.
  Do not spoof canonical implementation `__file__`. Launch main checks and TUI
  reloads through Layout's public entries; hash actual source bytes and modes.
- Native `execute(namespace, source_relative)` compiles the owner with its real
  filename into the caller's existing dictionary. Deliberately retain native public
  entry `__file__`, name/package/spec and module-global patch seams. Inject the
  captured root's Layout/compatibility objects; do not detach function globals.
- Native `peer(namespace, name)` resolves siblings in that captured root and plugin
  package, or its root-keyed standalone package. Two native releases may coexist;
  this is distinct from the runner's single active release per process. Missing
  declared sources fail closed; no legacy-body or installed-code fallback.
- Copied native entrypoints need their complete selected bootstrap/source/resource
  closure. Missing payloads refuse before writes. Shell-only fixtures remain shell
  fixtures; a test cannot silently import missing files from the host checkout.
- `worktree_paths.py` and `checkout_lock.py` stay independently copyable standalone
  hooks. Canonical and flat hook imports share identity. `agent_commit.sh` retains
  its public entry. These explicit exceptions do not authorize fallback sources.
- The portable Pi archive includes its runner/engine closure but excludes native-only
  runtime payloads. Archive help/read probes differ from runner admission, which
  still requires a committed immutable release. Preserve native copied closure too.

### Main-check supervision

Coordinator facades retain their original signatures and late-bound dependencies.
The leaf `supervision/main_checks.py` receives owner/current `git`; the reuse helper
also receives current `planning_path`. Internal phases call owner methods so
patches/overrides remain effective. No copied owner state, mixin or reverse import.
Keep port leasing, batch ownership, regression mutation and task recovery in the
coordinator. Preserve process birth identity, waitpid/reaping, inherited port-lock
FDs, receipt semantics, cleanup and result-publication order. Leaf imports remain
stdlib, `main_check`, `optimistic` and `common.LOG`, not the Coordinator facade.

### Closure preparation

`engine/integration/closure_documents.py` prepares task/receipt/live-followup maps;
it does not write or acquire transaction authority. Frozen `ClosurePorts` contains
exactly `git`, `passed`, `task_path`, `live_items`, bound fresh by the integration
facade. Dependency-using helpers accept keyword-only ports; pure helpers keep their
arguments. Preserve committed task reads, exact TOML ordering/redaction/contract and
tree binding, working-backlog-before-HEAD fallback, deduplication, suffix allocation
and notes/backlog/none/unknown follow-up modes.

Changelog composition remains in the integration facade, outside the leaf. Preserve
replay deduplication, dirty-owner refusal, transaction/lock order and second-writer
checks; no display, integration, recovery, retry or cleanup authority moves into the
preparation module. Allowed leaf imports are stdlib, canonical TaskStore and lazy
check_receipt, not coordinator/dispatch/state/execution facades. Repository retention
cleanup follows `AGENTS.md`; it is separate from truthful runtime closure.

### Current-source preservation

Preserve snapshot membership pinned to a committed revision, repository/contract/
attempt joins, independent pending/question provenance, stale-versus-empty states,
workspace/revision cache keys and legacy JSON exclusions. Maintain same-object
TaskStore, StoreError, task_queue and TaskRow identities.

TUI reload/fingerprints and coordinator review fingerprints observe actual selected
implementation bytes. Four physical reader slots, replaceable pending tokens,
epoch/generation admission and UI-thread-only publication remain: cancellation does
not free a running physical thread. Keep manual/verified/unknown closure distinctions,
copyable diagnostics, read-only Blockers, task-delete warnings, interrupted deletion
recovery, recreated-record protection, technical retry budgets and Git-read failures.
Preserve command discovery/routing, native settings opt-outs and setup/update rollback.

### Verification boundaries

Use the existing bootstrap, entrypoint, native, supervision, closure, package,
snapshot/reader/history, transaction and integration suites. Source-reading and AST
checks inspect actual owners, not just adapters. Discovery/shards and affected-test
mapping retain initializer, deletion/rename, duplicate-stem and conservative unknown
cases. Tests use complete isolated closures; optional renderer dependencies do not
leak into stdlib checks. A skipped renderer is not a rendered pass.

Retain import-order, foreign/missing-payload, nested syntax, source-byte fingerprint,
late-bound facade, exact preparation-map, real-Git replay/partial-commit, changed
contract, writer-arrival and rollback oracles. Shared-file changes serialize writers;
shared checks alone do not invent task dependencies. No test removal or weakened
assertion may substitute for a move. Required independent review and normal gates
remain, separate from installed-profile, model, device or live qualification.
