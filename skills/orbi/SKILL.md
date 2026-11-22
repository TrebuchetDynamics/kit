---
name: orbi
description: "Prepare, start, inspect or stop one Orbi deployment."
license: MIT
---

# Orbi

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[shared communication rules](../shared/COMMUNICATION.md) within this workflow's
scope. The [GitHub-native contract](../../docs/github-native.md) owns delivery
gates. This skill is a lifecycle client for one repository, not an executor.

## Common path

Keep the host LLM: interpret the current request once, using the conversation's
scope, restrictions and authorization. No separate model routes, validates, polls
or paraphrases a routine command. Extra reasoning or clarification requires a
concrete unmet need, not a fixed sequence of model turns.

1. **Resolve intent.** `/orbi [status|setup|start|update|stop|help]` uses
   `python3 -B <this-skill>/scripts/orbi_control.py` with the same action.
   Bare `/orbi` means `status`. **Help first.** For help or command inventory, run
   the helper's `help` and return its observed output; it needs no repository,
   config, environment or scheduler reads. For lifecycle actions, use the requested
   repo/config or known current checkout. The helper resolves the canonical
   worktree and verifies GitHub origin, deployment discovery and unit ownership;
   do not duplicate those reads in host tools. If target or intent is genuinely
   ambiguous, ask one focused question before mutation. Never run bare `orbi`
   (the Runner's one-tick entry), guess a typo alias or silently select an action.
2. **Authorize.** Preserve read-only/no-write restrictions and literal `--dry-run`.
   Preparation, activation and live delivery are distinct. Orbi remains paused
   and live-unqualified: `start` needs an owner scheduling request and resolved
   explicit pauses, cutover requirements and human-only gates for that deployment.
   Missing authority means hold and name the missing gate, not probe by mutation.
   `update` advances one prepared deployment only after an authorized stop/drain;
   it does not authorize a preceding stop or a following start. Other mutations
   likewise require accepted scope. Installation and offline checks grant none.
3. **Invoke once.** Preserve literal argument values, quoting, paths, provider/model
   IDs, `--config`, `--repo-dir` and all restrictions. Build argv, never interpolate
   user text as shell code; shell-only hosts must safely quote every argv element.
   Pass supported flags unchanged; add a known `--repo-dir` only when needed to
   bind the requested repository. Use `--json` for structured receipts unless the
   requested text/help output is preferable. Do not add/remove `--dry-run`, expand
   a literal path's shell substitutions, invent selectors or copy credentials.
   The existing ACTIONS-backed helper owns deterministic checks and composition:

   | Action | Single-call result and guard |
   | --- | --- |
   | bare/status | Read-only state/source/harness/scheduler/queue; absent is unconfigured, unavailable is not empty. |
   | help | Authoritative command reference, no deployment binding; accepts and ignores lifecycle inputs. |
   | setup | Non-activating preparation at the supported pin; `prepared`, `activated: false` is not proof of scheduler inactivity. Preview only when requested. |
   | start | Existing valid target skips preparation; genuinely absent target with no explicit config prepares internally then activates. No separate setup call. Partial/foreign/missing-explicit targets require deliberate repair. |
   | stop | Disable only owned timers; active services finish. `draining` is not `stopped`; never kill/restart workers. |
   | update | Preserve origin/provider/harness/slots; sync newest official release, lock `sha:<commit>`, refresh owned units and restore inactivity. `update_busy` or `source_dirty` holds without implicit stop/cleanup. Keep literal `/orbi update`, distinct from `/update-kit`. |

   No routine pre-status, help lookup, extra setup, preview-then-apply, polling or
   post-validation call. Helper ownership, safety, authentication and evidence
   checks still run. New setup/absent start accept installed `--harness {pi-bolt,pi}`
   (default Pi-Bolt) and complete `--pi-providers PATH --pi-provider ID --pi-model ID`
   with optional `--pi-thinking LEVEL`. Reuse existing selections without bootstrap
   flags. Missing prerequisites are repair inputs, not authority to install/login.
   Linux is the only mutation platform; macOS supports status/help.
4. **Relay receipt.** Return the helper's safe result directly wherever the host
   supports it. If a tool-result model turn is mandatory, relay only observed
   outcome, target and relevant evidence; no new plan or paraphrase pass. Preserve
   errors, `error.fix`, `error.mutated`, completed/failed `steps`, confirmed timer
   lists, `preparation`, `activation` and scheduler uncertainty. Exit success is
   not live qualification; harness resolution is not running-worker evidence;
   configured slots, enabled/active timers and running services are different.
   Never expose credentials, auth files, environment values or raw child stderr.
   On failure, stop and return the safe error and repair action. No blind retry,
   implicit repair, compensating timer changes or worker stops. An unchanged
   timeout is not retryable; killed processes have no receipt.

## Exceptional paths

Load only the relevant section of the [lifecycle reference](references/lifecycle.md)
when a concrete need arises: missing provider/harness inputs, explicit bounded
legacy `--resume-setup`, installed-helper flag mismatch, ownership ambiguity,
partial mutation, scheduler inventory interpretation or deliberate recovery.
It owns detailed discovery, isolation and action semantics. Do not preload it
for routine commands. For a stale helper, report its absolute loaded path and
available Kit revision; recommend a separately authorized Kit update/reload,
never an origin rewrite or activating upstream setup as repair.

For host/fixture measurement limits, use the reference's
[round-trip evidence](references/lifecycle.md#host-round-trips-and-evidence).

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| "One more model should route or rephrase this." | Interpret once; the helper owns checks, and its safe receipt is the answer. Host-mandated continuations only relay it. |
| "I remember help, so I can compose the table." | Run the helper's `help`; report observed output. |
| "Start needs setup first; update needs an automatic stop." | Absent start composes preparation internally. Update holds on busy state; another mutation needs its own authority. |
| "Passing checks releases the pause." | Owner scheduling authority and live gates remain separate. |
| "The command failed, so nothing changed and retry is safe." | Preserve mutation/activation evidence and repair deliberately; failure can be partially applied. |

## Red Flags

- Extra routing/validation/paraphrase models, routine polling or duplicate host probes.
- A guessed alias, shell interpolation, changed literal selectors or removed dry-run.
- Setup/dry-run enables timers, status writes, or stop kills/restarts a service.
- Missing ownership/authorization, silently changed pin/provider/harness/origin,
  or an automatic install/login/repair/retry after a refusal.
- An empty queue or stopped state inferred from unavailable evidence, or secrets
  and raw child stderr exposed in a receipt.

## Boundaries

- Not an executor/scheduler: no tick, claim, review or merge. No worker-inference
  or independent-review reduction.
- Not `/unblock`: recovery follows [service boundaries](../unblock/references/services.md).
- Not `/git-commit-push`: no commit, push or PR for the managed repository.
- Not `/plan-with-me` or `/plan-for-me`: planning grants no live service authority.
- Not `/update-kit`: update moves one deployment's engine, not Kit or this helper.
- Local visibility only: no cross-machine lock or global capacity guarantee.

The standing [Definition of Done](../shared/DEFINITION-OF-DONE.md) applies beyond
this task's acceptance.

**Done when:** the helper's observed state or precise refusal and evidence are
reported, with only authorized scoped mutations and active workers preserved.
