---
name: update-kit
description: "Refresh upstream Kit and reinstall the suite."
disable-model-invocation: true
license: MIT
---

# Update Kit

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this scope and the
[communication rules](../shared/COMMUNICATION.md) to user-facing text.

## Workflow

1. **Scope.** Run only after explicit invocation. Read the caller's restrictions.
   Before execution explain: default scope includes all available components, may
   bootstrap Pi-Bolt, and may restart active supported integrations.
   Pi-Bolt is the only Pi harness Kit installs; the Kit Pi package is installed or
   refreshed through the verified destination Pi-Bolt, never stock Pi. Native
   dependency/security prompts remain in force. Missing hosts and partial failures
   follow the [suite installer contract](../../docs/installation.md#full-suite-from-a-checkout).
   An explicit no-restarts restriction cannot be honored: `--no-reload` does **not**
   suppress the final restart phase. Refuse incompatible restrictions before any
   source/host mutation; never translate them into weaker flags.
2. **Preview branch.** For read-only, questions-only or dry-run requests, run only
   the helper's `--dry-run` with applicable literal flags, or explain without tools.
   Show intended path/argv; remote revision, host availability and activation are
   `NOT_CHECKED`. No clone, fetch, directory/lock creation, host probes or caches.
   Do not run the installer to preview.
3. **Ownership.** Use only `${XDG_DATA_HOME:-$HOME/.local/share}/kit/source`.
   `XDG_DATA_HOME` must be absolute and persistent; unset an invalid value or correct
   it before continuing. The helper clones the **complete** official
   `https://github.com/TrebuchetDynamics/kit.git`, branch `main`, not `install.sh`
   alone. Never substitute the current project, `/tmp`, `/home/xel/git/kit`, an
   arbitrary developer checkout or a host package/plugin cache. Keep source after
   installation: native installs can link to it. Establish that preexisting source
   consumers and native update owners are idle using their native receipts; unknown
   ownership holds. The destination lock serializes update-kit only, not Hermes.
4. **Selection.** Forward documented installer flags as separate argv, preserving
   literal values: `--only`, `--skip`, `--all`/`--full`, verbosity/color, and explicit
   Hermes options. The outer `--only`/`--skip` do not constrain Hermes's nested
   full-suite refresh. If a restriction selects Hermes but excludes any other
   component, refuse before mutation. Offer excluding Hermes (`--skip hermes`) or
   separately authorizing an unrestricted native cascade. Menu selection cannot
   be preflighted here; use explicit selection. Add no consent, sudo, autonomous
   policy, service activation or restart-control flags.
5. **Execute.** Resolve [the helper](scripts/update_kit.py) from this **loaded skill's
   resources**, never cwd. Use Python 3.11+ on Linux/macOS, Git, bash and lsof:

   ```text
   python3 -B <this-skill>/scripts/update_kit.py [literal caller flags]
   ```

   The helper stages a fresh clone in a unique sibling and retains failed staging
   evidence. Existing source must have updater provenance, same-user ownership,
   fixed origin, clean attached `main`, no extra worktrees, and no ahead/diverged
   history. A busy invocation reports retry. Preserve edits/history/evidence on
   every hold; never reset, stash, clean, force, repin, adopt or delete source.
   It fetches fixed upstream, fast-forwards only, then invokes that checkout's
   `bash install.sh update --no-pull` exactly once even at equal SHA. `--no-pull`
   suppresses only the outer automatic pull. Unrestricted Hermes native updates
   may fetch their installed source and launch another full-suite refresh.
6. **Receipt.** Report persistent source path, old/helper-selected/final SHA, any
   secondary source advance, native component outcomes and installer exit code.
   Partial successes remain installed; preserve diagnostics and repair/retry only
   the reported failures. Do not claim rollback. Reopen/reload the current agent
   session to discover resources: package refresh does not reload a running agent.
   Installation, activation, model adherence and live qualification are separate.
   Apply the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to claims, not as
   authority to activate Orbi or perform additional work.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| The current checkout is more convenient. | Only the dedicated persistent source is updater-owned. |
| Same SHA means nothing to do. | Host installation can be stale; rerun the installer. |
| `--no-reload` means no restarts. | The final restart phase still runs; refuse a no-restarts request. |
| `--only hermes` contains the update. | Hermes can launch a broader refresh; restricted cascades hold. |
| A successful install proves the session is updated. | Reload and live checks are separate evidence. |

## Red Flags

- Choosing another checkout/cache, repairing dirt with force, or deleting failed staging.
- Running source/network/host probes in preview or scheduling background updates.
- Hiding secondary source changes, partial failures or native ownership uncertainty.
- Starting Orbi or treating installation as live qualification.

## Boundaries

- Not a project updater, native-host logic fork or background scheduler.
- For choosing a skill, use `/ask-kit`; for repository plans, use `/plan-with-me`.
- For Orbi lifecycle operations, use `/orbi` with its own authority and paused gates.

**Done when:** the invocation has a source/installer/reload receipt or a precise
preserving refusal with a repair action; unrun live facts remain `NOT_CHECKED`.
