# GitHub-native development

Kit researches, records decisions and decomposes work. GitHub Issues own the
executable backlog, priority, native dependencies and dispatch. One Orbi deployment
per repository owns Pi implementation, tests, PR creation, independent review and
merge gates. Merged PRs and GitHub history retain delivery evidence.

## Support boundary

`pi-autowork` is retired and unsupported, not a fallback or an active redesign.
Do not develop, repair, reinstall, restart or restore its executor, CLI or Paseo
plugin. Contributors with older assignments must stop executor work, preserve
uncommitted changes and recovery evidence, and reconcile still-required outcomes
into GitHub Issues. Historical plans and research do not authorize new executor
work or cancel unresolved product acceptance.

Kit keeps `/plan-with-me` and `/plan-for-me`: both publish issue-based plans under
the same handoff contract. Orbi is the separate delivery project, not a renamed
Kit executor. `/work` supports explicit manual implementation. `/autowork` is only
a compatibility redirect; retained Hermes maintenance commands and marketplace
names are not support for the removed runner. No command rename is implied.
Orbi stays paused until its separate qualification gates pass.

## Default dispatch

All issues default to `ai-ready`, regardless of who opens them. This includes
external reports; issue authors are not trusted instruction authorities. Keep
credentials scoped and enforce CI, branch protection, sensitive-change controls
and any required human acceptance independently of dispatch.

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

Keep stable keys across retries. The helper inventories all issue states, reuses
exact matches, refuses duplicates/changed contracts/closed or owned work, creates
all issues and edges before readiness, and reads back the graph. A failed apply
can leave an undispatched partial batch; retry the same input after fixing the
cause. Readiness publication itself is not atomic: a failure there can leave some
complete issues ready, but their complete graph already exists. Inspect actual
ownership before retrying. Serialize publishers of the same batch; GitHub offers
no atomic issue-create idempotency key. Do not use this helper to overwrite an
existing edited issue; reconcile that issue fresh through supported GitHub tools.

## Cutover

1. Inventory old services, cron jobs, task data, worktrees, existing PRs and actual
   workers. Installed-executor removal must verify legacy processes stopped and
   registrations removed, while preserving recovery evidence. Do not reinstall the
   removed CLI to inspect state. Do not stop unrelated gateways.
2. The pi-autowork executor, source, CLI, Paseo plugin and installer component are
   removed. Ordinary Kit/Pi/Hermes/Claude/Codex functionality remains. Source removal
   alone does not prove host service removal; report actual host inventory separately.
   **Orbi remains paused and live-unqualified.** Removal does not authorize enabling it.
3. Reconcile unfinished local tasks against open/closed issues, PRs and merged
   evidence, following the [migration guide](../skills/shared/TODO-WORKCENTER.md).
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

Use [`/orbi [status|setup|start|stop]`](../skills/orbi/SKILL.md) for one
repository's deployment. Bare invocation reads status; `--repo-dir` selects the
canonical repository and `--config` selects its existing native configuration.
Setup prepares without activating scheduling. Start requires separate scheduling
authorization with existing pauses and cutover gates resolved. Stop disables only
owned timers and reports draining until active workers finish; missing evidence
is unavailable, not stopped. Linux supports lifecycle changes; macOS is status-only.

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

The supported host setting `human_review_gate = true` posts one acceptance
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

- [Recovery, integration and independent-worker acceptance](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/2026-10-16-pi-autowork-coordinator.md)
  and [safe landing/worktree ownership](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/2026-10-17-runner-landing-and-worktrees.md).
- [Planning authority and preservation of accepted intent](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/planning-authority-2026-11-01.md)
  and [decision/blocker coverage](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/decision-blocker-coverage.md).
- [Interface freshness and physical-client qualification](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/tui-responsiveness.md)
  and [Paseo qualification gaps](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/pi-autowork/integrations/paseo/docs/qualification.md).
- [State-preserving uninstall requirements](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans/autowork-uninstall-retirement.md)
  and the [remaining original plan contracts](https://github.com/TrebuchetDynamics/kit/tree/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/docs/plans).

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
