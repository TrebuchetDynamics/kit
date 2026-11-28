# Troubleshooting

Symptom-first fixes for installing and using Kit. Each entry links to
the owning guide; procedures are not repeated here. Start with the installer:

```sh
./install.sh --list       # which components are available on this machine
./install.sh --dry-run    # what a refresh would do, without changing anything
```

For a first check in a project, follow [first use](../README.md#first-use-in-your-project).
Use GitHub Issues/PRs and read-only Orbi diagnostics for delivery status.
Installer output never proves that a model ran or a worker is available.

## Commands

### A workflow command is not recognized

- **Wrong spelling for this host:** Claude Code uses `/kit:NAME`, Codex `$kit:NAME`
  and Pi `/NAME`; see [cross-host setup](cross-host.md).
- **Package not installed or not current:** run `./install.sh --only HOST` (for
  example `--only claude`) and read its result; see [installation](installation.md).
- **Running session predates the update:** a host session keeps the skills it
  discovered at start. Start a new session.
- **Hermes:** Kit no longer supports Hermes. Use Claude Code, Codex or Pi.

### The agent follows old skill instructions after an update

Existing conversations keep instructions they already loaded. Open a new
conversation.

## Installation

### A component failed or was held

Read the component's line in the summary: it names the cause and the retry
command. Successful components stay installed; there is no automatic rollback.
Fix the reported cause and rerun only that component with
`./install.sh --only ITEM`. Add `--verbose` to see each step and helper command.
See [full suite from a checkout](installation.md#full-suite-from-a-checkout).

### The Orbi refresh held or left deployments stopped

The summary names the deployment and step. Repair it, then rerun
`./install.sh --only orbi`; a deployment that a failed refresh left on the release
tag it was applying is resumed. See [Orbi CLI](installation.md#orbi-cli).

## Workflows

### `/docs-sync` changed documents but nothing was implemented

By design: documentation and planning never start implementation. Publish complete issues for Orbi; retained fix/apply modes keep their own scope
and PR/review gates; see [workflows](workflows.md#commands).

### A workflow asks for the old task CLI

The executor and task CLI are removed. Reload the current Kit skills and use
[GitHub-native handoff](github-native.md). Preserve existing local tasks, attempts,
worktrees and recovery evidence; do not reinstall the old executor or create a new
store. This error does not authorize activation.

### `docs.py check` reports findings

Each line names the role and the problem, and the document where one applies: a
manifest validation error, a missing mapped document or anchor, a broken link or
anchor, a documented script that does not exist, a missing covered path, or a
baseline role that is neither mapped nor recorded as not applicable. Fix the document or the manifest; see the
[role manifest](../skills/docs-sync/references/document-scaffold.md#optional-role-manifest).

### `docs.py stale` reports an unverifiable historical pin

`stale` exits 1 when a covered role has no `verified_at`, an unknown commit, or a
commit that is not an ancestor of the checkout's HEAD. An existing commit on a
different history is not current-source proof. Preserve its identifier and record
the role's source-evidence gap; do not replace a pin with HEAD merely to remove a
warning. Reverify the document against its full current source closure before
recording new verification, retaining the old identifier as historical evidence.
This repository's [role provenance inventory](project.md#role-source-evidence-gaps)
distinguishes the retained pins from current gaps. A passing `check` verifies
structure and local references, not content accuracy or runtime qualification.

## Still stuck

Collect the installer output (rerun with `--verbose`), the relevant receipt or
log and the exact command you ran. Run `python3 scripts/check.py` from a source
checkout to rule out a local regression; see [testing](testing.md).
