# GitHub-native development

Kit researches, records decisions and decomposes work. GitHub Issues own the
executable backlog, priority, native dependencies and dispatch. One Orbi deployment
per repository owns Pi implementation, tests, PR creation, independent review and
merge gates. Merged PRs and GitHub history retain delivery evidence.

## Freshness and delivery ownership

The [shared mode contract](../skills/shared/COMMON-CONTRACT.md#source-freshness-and-delivery-ownership)
applies to every skill. `/push` saves eligible changes in the invoking checkout
only, pulls verified `main` and delivers to `main`. Other local worktrees are not
inspected, saved or integrated; minimal Git metadata supports boundaries and safe
landing. Explicit `/git-commit-push all` retains its sweep. `/push` still inventories
paginated issue/PR evidence, synchronizes already-merged upstream Orbi changes, and
reports unfinished remote work by URL, owner, reason and next action. A clean local
checkout does not prove remote `main` is current. Names and bot authors are hints, not ownership proof;
default-branch ancestry proves inclusion.
An open Orbi-owned PR stays with its coordinator even if checks pass. No worker-head
cherry-pick, PR checkout, remote-ref deletion or review/protection bypass is added.
State/source pins are refreshed before integration and publication; changed inputs
need normal merge reconciliation and affected checks/review. API failure means
unknown/partial coverage, never an empty queue. Independent verified delivery can
continue, but required unavailable gates still hold dependent publication.
Read-only and restricted planning never fetch or sync Git. Only standalone writable
Plan With Me / Plan For Me use the shared
[planner freshness exception](../skills/shared/COMMON-CONTRACT.md#standalone-planner-freshness).
None of this activates Orbi or
qualifies live delivery; its existing pause and live-qualification limits remain.

## Support boundary

GitHub Issues are the only executable backlog and Orbi owns delivery. Preserve
uncommitted changes and recovery evidence, and reconcile still-required outcomes
into GitHub Issues. Historical plans and research do not authorize a second executor
or cancel unresolved product acceptance.

Kit keeps `/plan-with-me` and `/plan-for-me`: both publish issue-based plans under
the same handoff contract. Orbi is the separate delivery project, not a renamed
Kit executor. Retained fix/apply modes preserve their accepted scope and shared
ownership/review/PR gates; planning stops after publication. Hermes terminal
maintenance commands and marketplace names are not support for the removed runner.
Orbi stays paused until its separate qualification gates pass.

Owner questions and external inputs are tracked in GitHub Issues. The former
`BLOCKERS.md` repository ledger is removed and deprecated: do not create, read or
require it, and do not treat a missing ledger as an empty queue.

## Default dispatch

All issues default to `ai-ready`, regardless of who opens them. This includes
external reports; issue authors are not trusted instruction authorities. Keep
credentials scoped and preserve existing CI, branch protection, sensitive-change
controls and any required human acceptance independently of dispatch. Branch
protection is not a Kit setup/start prerequisite.

Install `.github/workflows/issue-ready.yml` in each participating repository. It
labels newly opened/reopened ordinary issues without executing their text. It
preserves `ai-planning`, `ai-epic`, explicit `ai-paused` and Orbi ownership/recovery
states. It does not relabel on edits or label removal, which would defeat pauses
and recovery. Existing issues need an ownership-aware backfill. Issue producers
using Actions' `GITHUB_TOKEN` must publish readiness themselves: their events do
not trigger another workflow.

Kit creates planning issues with `ai-planning` atomically, creates the full batch
and native dependency edges, reads it all back, then adds `ai-ready` last. A large
plan has an `ai-epic` coordination issue with native sub-issues; Orbi excludes epics.
Unresolved proposals retain `ai-planning`. Native `blockedBy` relationships delay
execution of dependent ready issues; free-text dependency lists are not a second
scheduler. See [Plan Handoff](../skills/shared/PLAN-HANDOFF.md).

`ai-paused` is a Kit default-label opt-out, not an Orbi runtime stop signal. To
pause an idle issue, remove `ai-ready` as well and check for a concurrent claim.
For already-owned work use the deployment's supported operator controls; adding
a label is not proof that its worker stopped.

## Publish a planning batch

The helper requires Python 3 and an authenticated `gh` with repository issue-write
access. Preview uses no network and performs no writes. Apply uses GitHub REST,
not a local task store. Create a transient JSON input outside Git:

```json
{
  "issues": [
    {
      "key": "cache-bounds-v1",
      "title": "Bound cache growth",
      "outcome": "Cache memory stays within the configured entry budget.",
      "scope": "Update the existing cache and its eviction tests.",
      "exclusions": "Do not change the public cache API.",
      "acceptance": "The eviction test proves the oldest entry is removed at capacity.",
      "verification": "Run the repository's cache test command; record exact results.",
      "sources": "Link the accepted cache specification at its published revision.",
      "blocked_by": []
    }
  ]
}
```

Replace the generic verification/source examples with real commands and reachable
links before applying. `blocked_by` accepts batch keys or existing issue numbers in
the target repository. Depend on executable children rather than an open epic;
use `epic` for coordination membership. A ready issue may wait on an undispatched
prerequisite: its native edge preserves that wait. The helper resolves numeric
issue IDs for the native REST API. `kind: "epic"` creates coordination-only work; `epic: "KEY"` links a child.
`ready: false` requires `pending_reason` and keeps the issue undispatched.

```sh
python3 scripts/github_issues.py --repo OWNER/REPO --batch /tmp/batch.json
python3 scripts/github_issues.py --repo OWNER/REPO --batch /tmp/batch.json --apply
```

Keep stable keys across retries. The helper inventories all issue states and
refuses duplicates and changed contracts. A matching closed or owned issue is
already published: the helper reports it without writes and keeps its identity
for dependencies. It creates and verifies all remaining issues and edges before
any readiness publication. Immediately before each issue's `ai-ready` POST, it freshly
checks title/body, open state, readiness/ownership, epic classification, the exact
native `blockedBy` ID set and native parent against the complete saved spec.
Observed drift or a failed read stops publication with an issue-specific error;
the final check never repairs changed dependencies or parents.

A failed apply can leave an undispatched partial batch, or leave earlier issues
ready while a later issue remains `ai-planning`. Earlier readiness and foreign
edits are preserved, not rolled back. Inspect actual ownership and reconcile the
cause through supported GitHub tools before retrying the same stable-key input;
do not blindly replay it to overwrite drift. Publication is still non-atomic:
another client can edit after a final read and before the separate label write.
Serialize publishers of the same batch; this rule is not cross-client exclusion,
and GitHub offers no atomic issue-create idempotency key or read/label transaction.
Do not use this helper to overwrite an existing edited issue.

## Cutover

1. Inventory old services, cron jobs, task data, worktrees, existing PRs and actual
   workers. Installed-executor removal must verify legacy processes stopped and
   registrations removed, while preserving recovery evidence. Do not reinstall the
   removed CLI to inspect state. Do not stop unrelated gateways.
2. Report actual host inventory separately; source changes alone do not prove host
   service removal. Ordinary Kit/Pi/Hermes/Claude/Codex functionality remains.
   **Orbi remains paused and live-unqualified.** Removal does not authorize enabling it.
3. Reconcile unfinished local tasks against open/closed issues, PRs and merged
   evidence, following [Plan Handoff](../skills/shared/PLAN-HANDOFF.md).
   Preserve legacy IDs and immutable sources. Never redispatch completed or owned
   work. Do not synchronize two queues or prune worktrees as part of migration.
4. Pilot one repository only after ownership is settled. Verify actual issue pickup,
   PR creation, independent review, required CI, merge and failed-run recovery.
   Offline contract tests and `doctor` alone do not qualify that loop.
5. Expand only after the pilot passes. Give each repository a distinct deployment,
   non-overlapping task pool and measured resource budget. Leave the remaining
   fleet paused until its migration and capacity checks are complete.

## One repository per deployment

Use Orbi's supported external single-repository mode. Verify current upstream
prerequisites before installation: its documented baseline includes GitHub CLI
2.94+, Python 3.14 (provisionable with uv), Node 22.19+, Pi with a working model
provider and a user scheduler session. Install Orbi from its release channel in a
separate deployment checkout, not inside Kit or a delivery worktree. Inspect the
installer or follow upstream's editable `uv tool` installation instructions.
Do not patch upstream Hermes or change agent credentials to make setup pass.

The [suite installer](installation.md#orbi-cli) does not create repository
deployments. Selecting Orbi explicitly authorizes a host-wide stop, stable release
update and restart of verified local Linux installations, including paused ones.
For this installer path, verified manager/unit/file ownership, a validated release
pin and a passing `orbi check` are the activation checks; no separate cutover or
human approval record is required. Use `--skip orbi` if scheduling must stay paused.
This is a maintenance path, not a live-qualification procedure.

Example configuration shape (merge with the shipped Orbi example):

```toml
source_repos = ["OWNER/REPO"]
repo_dir = "/path/to/repo"
deploy_home = "/path/to/orbi-repo"
workspace_root = "/path/to"
unit_name = "repo"
engine_source_track = "release"
max_concurrency = 1
```

`source_repos` contains exactly one repository. Each additional repository gets
its own deployment/configuration/checkout and unique `unit_name`. Use supported
`orbi setup` / `orbi install-units`, not hand-written unit-name substitutes.
Setup can enable timers: inspect its options and keep dispatch disabled until
cutover checks pass. Respect this repository's worktree placement: all new task
worktrees must be under the canonical repository's `.worktrees/`. Verify the
selected Orbi release meets that rule before enabling it; `workspace_root` alone
must not be assumed to control task-worktree placement.

```sh
orbi check --config /path/to/orbi.toml
orbi status --config /path/to/orbi.toml
orbi doctor --config /path/to/orbi.toml
```

Orbi has no cross-deployment ownership lock or machine-wide capacity guarantee.
`max_concurrency` is per deployment. Start with one pilot slot; before fleet rollout,
configure and test aggregate CPU/memory/model budgets (for example systemd slice
limits) rather than multiplying that slot count across every repository. `doctor`
can diagnose overlapping pools; it does not establish a global resource budget.
Do not serve one repository from multiple deployments or machines.

### Kit lifecycle skill

Use [`/orbi [status|version|setup|start|update|stop|help]`](../skills/orbi/SKILL.md) for one
repository's deployment. `/orbi status all [--json]` instead inventories observable
local host services from any directory, without repo/config selectors, GitHub auth
or network fan-out. Preserve literal `all` in one helper call and never inject
`--repo-dir`; partial/denied manager coverage is not an empty host. See
[host inventory](../skills/orbi/references/lifecycle.md#host-inventory).
`/orbi version [--json]` identifies the selected deployment engine release/revision
and verification evidence without full status, bootstrap or network probes. Missing
deployment is unconfigured; unverifiable metadata is unknown, never the global CLI.
Bare invocation reads status; `--repo-dir` selects the
canonical repository and `--config` selects its existing native configuration.
Public `setup` starts by default, mapping to helper `start`; explicit invocation
expresses scheduling intent, not a waiver of existing pauses and cutover gates.
`setup --prepare-only` prepares without activating scheduling (direct helper `setup`
remains non-activating). Missing/failed gates hold with the specific blocker and
next safe check/repair; never silently fall back to preparation or ask for a second
approval for already-authorized activation whose gates are evidenced. If genuinely absent
and no explicit config was supplied, start first uses the same setup preparation,
validates non-activating, then rebinds/revalidates under the activation lock. Existing
valid/active targets skip preparation and reject bootstrap/harness selectors; partial,
foreign or missing explicit configs require deliberate recovery, never silent resume. Stop and update disable
owned timers, cancel verified queued starts and stop owned workers through systemd.
Missing evidence is unavailable, not stopped. Linux supports lifecycle changes; macOS supports read-only status/version. `help` prints the action reference read-only and needs no repository.

On Linux, status names the state it observed: `absent` when no deployment owns
the repository, and `unavailable` when scheduler evidence cannot be verified. With
readable scheduler evidence, it reports `running` while any service is active,
activating or reloading; `draining` when no service is running but one is
deactivating. Otherwise it reports `prepared` when an owned timer is enabled or
active, and `stopped` when services are inactive or failed and no owned timer is
enabled or active. macOS status reports local deployment metadata but leaves
active scheduler state `unavailable`.

New lifecycle setup (including absent-start preparation) defaults to an installed
Pi-Bolt executable; `--harness pi` explicitly selects stock Pi for new preparation. A deployment-local `.orbi/harness-bin/pi`
exec launcher and namespaced fields in `.orbi/env` persist the choice for both
workers and reviewers. No native Orbi harness field, global alias, automatic
harness install or fallback is used. Existing managed selections are reused;
legacy deployments keep their stored routing and are not silently migrated.
Setup/status/start report `deployment.harness` as configured/resolved-now evidence,
not observed running-process use. Drift/unavailable targets and incompatible
final extension PATH/HOME/agent-directory overrides block managed activation.

Declared provider key/header references must be available in persisted deployment
env and compatible final extension env, not just the caller shell. This reports
`references_available`, not successful authentication/inference. A custom deployment
catalog need not exist in the global catalog for this route. With no references,
the selected executable must pass its supported non-refreshing stored-auth check
in the pinned user auth home; otherwise preflight holds as `auth_unverified`.
No temporary auth profile, credential copying or user-catalog mutation is used.
See [harness evidence](../skills/orbi/references/lifecycle.md#harness-selection-and-evidence)
for serialization, legacy/unknown reporting and repair boundaries. Native Pi-Bolt
extensions, streaming/recovery and installed worker/reviewer compatibility remain
live-unverified; static routing does not qualify delivery or release pauses.

`update` is the deliberate release channel: under lock it quiesces the deployment,
then lets `sync-engine-source` resolve the newest official semver release and pins
it as `sha:<commit>`. After non-activating validation, it restores eligible
scheduling through the existing start gates. `update --stop` leaves scheduling
stopped and defers unit refresh to the next authorized start. Tracked checkout
changes refuse as `source_dirty` before quiescing. Uncertain ownership or scheduler
evidence blocks sync; partial failures retain completed operations and failed steps
without claiming stopped. Update preserves origin, provider, harness
and slots; rollback is a deliberate owner edit of `engine_source_track`.
It never refreshes Kit itself: that stays `/update-kit`.

For a first authorized deployment, preview with `/orbi setup --dry-run
--pi-providers /path/to/models.json --pi-provider PUBLISHED_PROVIDER_ID
--pi-model PUBLISHED_MODEL_ID`, then remove `--dry-run` only within that authority.
Use actual published IDs and metadata, not invented limits or credentials. Without
selectors, verified donor metadata is reused or the exact missing input is reported.
An absent preview is write-free and explicitly defers staging-dependent source,
validation and activation checks. `/orbi setup --dry-run` previews the start route;
`/orbi setup --prepare-only --dry-run` previews preparation only.
`/orbi setup --harness pi` selects stock Pi for a new target then starts it;
add `--prepare-only` to opt out of activation. Public `setup --resume-setup` requires
explicit `--prepare-only`; otherwise reject before mutation with corrected
`setup --prepare-only --resume-setup` and the original arguments.
Use `/orbi status` to inspect and `/orbi stop` for an authorized worker interruption.
Context-free `/orbi help` reports the loaded helper path/default policy, parseable
examples and recovery guidance, not the installed selected harness.

Each helper mutation reports its own outcome: direct helper `setup` (public
`setup --prepare-only`) says `prepared` (staging, not scheduler activation),
helper `start` (public default setup or start) says `started` or `already-running`, `update` says
`updated` or `up_to_date`, and `stop` says `stopped` after verified inactivity;
`--dry-run` says `planned` for all four. Stop and update name the disabled timers
and stopped workers and preserve attempt files, worktrees and recovery inputs.
Update syncs only after quiescing and restores eligible scheduling unless `--stop`
is used. The read-only `status` still describes current activity, not intent.
Start also retains `preparation.state` (`skipped`, `planned`, `prepared`, `failed`).
Preparation failure never activates; later failure preserves successful preparation,
actual/possible mutation evidence and the original failed operation. Activation
timeout can mean timers/workers already run: inspect status, never automatically
retry, roll back or stop workers. Prepared/activated is not live-qualified.

The [lifecycle reference](../skills/orbi/references/lifecycle.md) owns prerequisite,
retention, pinned-source and deployment-local uv isolation details. Native units
still depend on a compatible shared bootstrap: this is not a self-contained
executable per deployment. Installing the skill or passing offline checks does
not prove live isolation or release the pilot gates.

## Qualify the model provider

The diagnostics below were checked against Orbi 0.7.41. Re-check the release you
actually deploy: the output and accepted configuration are release-scoped, and a
green local diagnostic is not delivery evidence.

`orbi check` and `orbi doctor` compare Orbi's configured provider path with the
selected provider/model. They send no model request and do not inspect Pi's own
provider directory.

- **Native Pi provider (`pi_providers` unset).** Pi uses its own agent directory.
  This path can be fully configured while Orbi's provider status still says
  `NOT CONFIGURED` (setup/doctor) and `orbi check` fails at `check=model_provider`
  with `model provider not configured`: those diagnostics mean Orbi has no
  explicit provider file or selection to inspect, not that Pi has no working
  provider. Verify it with Pi's own check and one real response:

  ```sh
  pi auth check --provider PROVIDER_ID
  pi --print "reply with the single word: ok"
  ```

- **Explicit Orbi selection (`pi_providers`, `pi_provider`, `pi_model` set).**
  Point `pi_providers` at a JSON file in Pi's `models.json` shape, then select the
  provider and model in `orbi.toml`:

  ```toml
  pi_providers = ".orbi/pi-providers.json"
  pi_provider = "PROVIDER_ID"
  pi_model = "MODEL_ID"
  ```

  The file may reference a secret as `$PROVIDER_API_KEY`; keep its value in the
  gitignored state file or the service environment, never in the repository or a
  worktree. Copy the provider entry, including `id`, `name`, `contextWindow` and
  `maxTokens`, from the provider's published model catalog. Do not invent
  capabilities or reuse metadata from an unrelated model.

With an explicit provider file, Orbi materializes
`<worktree>/.orbi/pi-agent/` (gitignored) at run start: it merges the user and
file providers into the per-run `models.json`, writes the selected
provider/model into `settings.json`, and links `auth.json` to Pi's user agent
directory when that file exists. Stored authentication for a built-in
provider therefore remains usable without copying the token into the worktree;
the user's Pi catalog and auth file are not modified.

### Offline check, inference, and live delivery

- **Offline configuration check.** `orbi check` and `orbi doctor` validate file
  shape, selector presence, endpoint/API fields and key references. A status such
  as `key=PROVIDER_API_KEY=set` only proves the referenced environment variable is
  non-empty; `key=literal=set` only proves a literal value is present. Neither
  authenticates the credential nor proves the model can answer.
- **Inference through the configured path.** One real model response is required
  through the same provider/model and per-run agent directory a delivery uses.
  With an explicit Orbi selection, run one bounded test issue and inspect
  `orbi status --follow` plus the run journal's `provider_config_loaded` line. A
  bare `pi --print` is not proof of that path: it uses Pi's own agent directory
  and never reads `pi_providers`. A successful call proves the provider, model and
  credential path work; it does not qualify issue-to-merge delivery.
- **Live delivery.** The pilot must then show issue → PR → independent review →
  required CI → protected merge, plus failed-run recovery. Only that protected
  merge, not a provider call or an offline test, is the delivery qualification
  evidence.

Record only non-secret evidence: provider/model identifiers, a pass/fail status,
elapsed time, the non-secret journal `provider_config_loaded` line and the PR URL.
Never paste a key, token, `auth.json`, session transcript or private account
identity into an Issue, PR, test, log or document.

## Read protection diagnostics safely

Branch protection is not a Kit setup/start prerequisite. Known unprotected branches
and protection/rules endpoint HTTP 403 are informational, not scheduling blockers.
A protection-specific 403 means details are unknown, not absent; it does not prove
failure to authenticate or access the repository. Report each observed state with
its source. No protection read/repair, PR-only mode, special opt-in, no-base-write
engine proof, paid GitHub plan, engine release or second approval is required on
that basis. Normal setup-as-start and start use the same activation path, including
preparation and the first tick, when scheduling is authorized and other prerequisites
pass. Do not add a protection probe to the shared preflight.

Authentication, repository access, deployment ownership, explicit pauses and all
other startup gates still apply. Prepare-only and dry-run never activate. Helper
status preserves `doctor.state=failed` as a diagnostic outcome, not itself a Kit
scheduling gate; distinguish protection diagnostics from other failed prerequisites.
Successful startup does not imply successful merge or live qualification. Ordinary
engine behavior and the engine pin are unchanged; existing protections, required CI,
review and merge requirements remain in force.

`orbi doctor` may report
`merge_gate: FAILED classic protection enforces admins` when the target branch
enables `enforce_admins`. The merge executor uses an ordinary
`gh pr merge --match-head-commit <SHA>` with the configured GitHub identity; it
does not use an administrator override. The blocker therefore describes the
configured merge identity, not a defect in the protection.

Resolve it through the repository's supported governance path: a different
approving reviewer or ruleset where policy allows, or a human maintainer
performing the protected merge. Keep enforced administrators, strict required CI
status checks, independent review and any human-only label in place. Never
disable branch protection, required checks, administrator enforcement or the
review gate to make `doctor` green, never use an administrator override, and
never manufacture an approval or a human confirmation. If protection
legitimately blocks the deployment identity, record the exact blocker and leave
the PR unmerged. The actual protected merge of the reviewed head remains the
qualification evidence.

## Human acceptance is a separate gate

New deployments prepared by `/orbi setup` default to `human_review_gate = false`,
disabling the optional human-acceptance label gate, not required CI or independent
AI review. Setup preserves an existing deployment's explicitly selected policy.
Branch/admin protections, credential isolation and external authorization rules
remain unchanged, including any operations-specific human-only gates.

The optional supported host setting `human_review_gate = true` posts one acceptance
checklist when a PR opens and holds a delivery whose machine-unverifiable column
is non-empty. Only a human applies `ai-human-review`; the agent and Runner must
never add or remove it. An empty machine-unverifiable column is the intended pass
state. The setting does not replace branch protection, required CI, independent
review, credential isolation or sensitive-change controls, and a satisfied
checklist is not a substitute for the protected merge or live-delivery evidence.

## Verification and rollback

The pilot must show issue → PR → independent review → required checks → merge in
GitHub and matching Orbi run diagnostics. Exercise failure recovery without losing
the original PR/worktree or duplicating work. Preserve any repository-required
human acceptance and never mark it from an automated review.

If qualification fails, disable that deployment's timers and preserve its issues,
PRs and recovery state. Report the exact missing input or failed gate. Do not
reinstall or resume the removed executor. Keep the replacement paused until
ownership and qualification are reconciled. Installing a CLI or passing offline tests is not live delivery.

## Remaining requirements after executor removal

Removal is not completion, cancellation of product acceptance or live qualification.
The original requirements are retained through immutable Git sources, not a new
completed-task archive. Reconcile still-required outcomes into GitHub Issues
without recreating the executor, duplicating finished work or losing source proof:

- [Planning authority and preservation of accepted intent](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/planning-authority-2026-11-01.md)
  and [decision/blocker coverage](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/decision-blocker-coverage.md).


These sources establish prior intent/evidence only. Preserve their still-applicable
human/live gates and unresolved proof, while the new pilot and fleet stay paused.

## Upstream contracts

The diagnostic details above were checked against these pinned Orbi 0.7.41
sources. Use the release you deploy and re-check its corresponding files.

- [Orbi 0.7.41 getting started: model provider](https://github.com/orbi-build/orbi/blob/v0.7.41/docs/getting-started.mdx#4-configure-the-model-provider)
- [Orbi 0.7.41 provider status](https://github.com/orbi-build/orbi/blob/v0.7.41/src/orbi/setup_config.py)
- [Orbi 0.7.41 per-run Pi agent directory](https://github.com/orbi-build/orbi/blob/v0.7.41/src/orbi/pi_session.py)
- [Orbi 0.7.41 merge gate](https://github.com/orbi-build/orbi/blob/v0.7.41/src/orbi/merge_gate.py)
- [Orbi 0.7.41 merge executor](https://github.com/orbi-build/orbi/blob/v0.7.41/src/orbi/merge_exec.py)
- [Orbi 0.7.41 example config](https://github.com/orbi-build/orbi/blob/v0.7.41/src/orbi/example_config.toml)
- [Orbi operations](https://github.com/orbi-build/orbi/blob/main/docs/operations.mdx)
- [Orbi workflow and labels](https://github.com/orbi-build/orbi/blob/main/docs/workflow.mdx)
- [GitHub issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies)
- [GitHub sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
