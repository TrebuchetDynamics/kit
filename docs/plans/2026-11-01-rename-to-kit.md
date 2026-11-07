# Kit identity and settings compatibility

## Decision

Kit is the toolset; Autowork is its runner and skill. Current identity is distinct
from compatibility with existing installed profiles. This document keeps that
contract and outstanding live proof, not completed rename-stage reports.

## Target identity

| Surface | Current contract |
| --- | --- |
| Repository | `TrebuchetDynamics/kit` |
| Hermes plugin | `kit` |
| Namespaced skills | `kit:<skill>`; Claude `/kit:<skill>` and Codex `$kit:<skill>` |
| Pi commands | Unprefixed |
| Local package metadata | `@trebuchet/kit` |
| New settings writes | `plugins.entries.kit` |
| Compatible settings input | Existing `plugins.entries.autowork` values remain readable |
| Runner CLI and private state | `autowork`, `~/.local/state/pi-autowork/`; unchanged |

No npm publication is required. Install from the Git source and existing host
marketplaces. Neither registry publication nor a scope/deprecation operation is
part of the remaining qualification.

## Why the stages exist

Manifest admission, public command namespace and per-profile settings are separate
boundaries. Preserve all three consistently; a source rename cannot reset approvals,
menu priority, gateway injection, installed profile identity or private runtime state.

## Stage 1: dual-read settings key

The runtime owns canonical/legacy key selection. Read both entries per key:
canonical values win and legacy values supply keys absent from the canonical entry.
Write new settings under `plugins.entries.kit`. Where the actually loaded legacy
plugin still reads its old gateway-injection entry, preserve that supported bridge
and report which entry is effective. No profile with neither key loses defaults.

Fixtures cover legacy-only, both-key and neither-key profiles, including approvals,
menu priority and opt-out. They prove read/write logic, not real-profile migration.

## Stage 2: plugin identity and namespace

Manifest validation and host registration must agree on Kit identity. Preserve the
same public skill set across supported hosts, portable explicit invocation and
unprefixed Pi commands. Runner CLI, private state and execution behavior do not
change with the toolset namespace. The separate one-product-root plan owns future
source placement; it does not migrate installed state.

## Stage 3: documentation and installers

Current README, runbooks, catalogs and installer labels use supported Kit install
commands and explain the legacy settings bridge. Do not tell users to invoke the
retired namespaced skill spelling. Keep current compatibility instructions, not a
completed-stage checklist or dated migration report.

## Stage 4: rename and live proof

The remaining requirement is pre-rename profile preservation. Under its separately
authorized live scope, run the renamed plugin against a profile configured under
`plugins.entries.autowork` and prove approvals mode, menu priority and opt-out stay
unchanged. Offline fixtures do not satisfy this requirement. A saved owner answer
is not live execution or proof, and this cleanup does not mark the goal met.

## Verification that closes the rename

1. Capture the selected profile's relevant old-key settings without exposing secrets.
2. Run the renamed plugin under the existing owner/qualification authority.
3. Read back unchanged effective settings, canonical new-key writes and explicit
   legacy-key handling. Preserve unrelated profile settings and pauses.

## Rollback

Use supported source/configuration rollback with preserved prior inputs. Removing
the new key restores the compatible old-key read where applicable. Do not reset,
rewrite or discard customized profiles, installed state or recovery evidence.

## What this plan does not cover

No runner/CLI/state rename, task-store behavior change, npm release, implicit profile
write, publication, deployment, service restart or credential operation. Preserve
the current live task's ownership, acceptance and authorization gates.
