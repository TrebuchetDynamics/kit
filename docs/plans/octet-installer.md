# Install upstream Octet through the suite installer

## Accepted scope

Status: Accepted.

The owner requests that Kit's `install.sh` install Octet from
`https://github.com/skaft-software/octet`. LGTM accepts the recommended official
stable-release channel, default/`--all` installation and `--only octet` selection.
Leave credentials and optional extensions unchanged. This is a planning batch,
not implementation, installation, publication or a runner start.

## Evidence and decisions

- Current source: `scripts/install_menu.py::items` declares Pi, Autowork, tx,
  Hermes, Claude Code and Codex. The shell entrypoint delegates selection and
  execution to this module. Reuse Item, Step, selection, streamed output and
  per-item failure accounting; do not create another installer framework.
- `tests/test_install_menu.py::InstallMenuTests` exercises default/all/update,
  explicit selection, unavailable components, dry runs and failure isolation in
  private HOME fixtures. Adding a downloadable component must keep these fixtures
  offline, including existing tests that invoke the full suite.
- Official [installation](https://skaft.org/octet/docs/installation/) and
  [distribution](https://skaft.org/octet/docs/distribution/) describe native release
  installers. npm publication is separate and was not available for the documented
  0.10.2 version. Source builds require Rust. Neither channel is needed here.
- The [upstream installer source](https://github.com/skaft-software/octet/blob/main/scripts/install.sh)
  declares `OCTET_INSTALL_DIR` (default `$HOME/.local/bin`), `OCTET_DATA_DIR`
  and `OCTET_NO_MODIFY_PATH`. Its binary route checks release source identity,
  Sigstore provenance, checksums and archive safety. Use the published release
  installer, not this unrendered source template with its source-commit placeholder.
- Current upstream pages show different version snapshots. Select the official
  stable installer at `https://octet.skaft.org/install`, which resolves to
  release-bound tooling, and report the actual selected version; do not hardcode
  a version copied from a mutable README or build upstream main.
- Planner call: download that HTTPS installer into a private temporary file with
  bounded network access, then execute it unchanged with `sh`. Use the native
  binary mode, absolute Kit BIN as `OCTET_INSTALL_DIR`, and
  `OCTET_NO_MODIFY_PATH=1`. Keep the upstream packaged-data location and its
  verification/collision refusals. Do not unlink existing files to force success.
  Verify the actual destination executable, not an unrelated Octet earlier on PATH.
- Include one `octet` item in default/all/update, with `--only`, `--skip`,
  list and dry-run parity. It bootstraps a missing Octet CLI: the CLI itself is
  not a prerequisite. Missing download prerequisites fail the selected item;
  independent items continue. For unsupported platforms, normal all/default
  selection skips with a reason and explicit selection fails. Initial native
  targets are GNU/Linux x86-64 and macOS x86-64/arm64. Do not silently build source
  or use an unpublished package-manager channel as a fallback.

## Existing candidate and ownership

An idle retained candidate exists at `.worktrees/octet-install`,
`feat/octet-install`, base `324917e3`. Its owner confirmed it installs native Kit
skill/prompt pointers into an already installed Octet, not the Octet executable.
It has no saved task ID. Preserve its seven edited files and its separate review
evidence; do not overwrite it with this plan or copy its older files over main.

This task installs the upstream executable only. If native Kit resource support
lands before implementation, add bootstrap as the first step of that same Octet
item and preserve its accepted resource behavior; do not register a second item
or retain an availability check that skips a missing executable. Otherwise add
only the binary item and leave the retained resource candidate separate. This
does not depend on the separate Rust Autowork/Octet redesign or alter its SDK pin.

## Implementation and verification

One implementation task owns `scripts/install_menu.py`,
`tests/test_install_menu.py`, `README.md`, `docs/installation.md` and
`docs/dependencies.md`. The current shell entrypoint needs no behavior change.
Update the documented component list, stable upstream source, prerequisites,
selection/update behavior, platform limits and native-install versus Kit-resource
boundary. Preserve every other host's selection and installation behavior.

Extend existing selection/full/update/dry-run fixtures and add bounded mocked
download/installer/version cases. In private fixtures, prove absent-CLI bootstrap,
native environment forwarding, expected-version readback, idempotent rerun,
unsupported platform handling and failure isolation. Preserve existing binaries on
pre-placement integrity/version refusals. Test a post-write failure separately:
report the component failed and partially installed, without claiming rollback or
success. Avoid separate tests for each documentation sentence. Every fixture,
including old full-suite cases, must avoid real downloads.

Builder finding resolved: the upstream installer places the two executables
separately, then packaged data, then performs final installed-version verification.
It is not a whole-install transaction. Preserve this upstream boundary rather than
inventing rollback: failures before placement keep the previous installation;
failures after placement can leave partial changes and must be reported as such.
This limit belongs in the implementation's failure message and installation docs.

Proposed checks, not run during planning:

- `python3 scripts/check.py tests/test_install_menu.py`
- `python3 skills/docs-sync/scripts/docs.py check .`
- `git diff --check`

A real native download/install and `octet --version` smoke are separate live
qualification, not established by fixture tests. No model call, extension
enablement, trust grant, credential import, service start or migration is needed.

## Handoff

Implementation acceptance is offline and source-bound. First extend the existing
full-suite selection fixture with a fake upstream installer and no preinstalled
Octet, show that current code lacks the item, then implement the stable binary
route and the failure/read-only cases. Keep existing native-resource work and all
live service state unchanged. One implementation merge and one independent review
are expected; planning's local commit is separate. No unresolved product choice
remains. Current-session execution is the proposed later mode; this planning pass
does not execute it.
