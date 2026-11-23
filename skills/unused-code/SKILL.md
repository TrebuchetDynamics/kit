---
name: unused-code
description: "Publish proven dead-code cleanup issues."
license: MIT
---

# Unused Code

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../shared/COMMUNICATION.md) for user-facing text.

## Route the invocation

An ordinary `/unused-code` invocation without a publication directive analyzes the
requested scope and publishes warranted cleanup issues in the same invocation.
With no area supplied, inspect the current repository. Follow the
[single-invocation specialist handoff](../shared/PLAN-HANDOFF.md#single-invocation-specialist-handoff)
for reconciliation, the non-blocking chat preview, publication and stopping.
Default publication does not delete or implement locally.

Explicit `report only`, `read-only`, `no-write` or `dry-run` requests
report inline and write nothing, including scratch files and graphs.
Only an explicitly requested and authorized local fix/apply mode enters
[Authorized local fixes](#authorized-local-fixes).

Read these routing rules and the [host and authority adaptations](../shared/PI-TOOLSET.md)
before reading the pinned [unused-code protocol](upstream/PROTOCOL.md).
They take precedence over its deletion loop and owner-question defaults.
This is not dependency pruning, speculative simplification or a repository
architecture rewrite.

## Prove liveness boundaries first

Inspect status, instructions, entrypoints, manifests, package exports and baseline
checks. Rank candidates with a local code graph when one exists, and record its
[declared graph state](../shared/COMMON-CONTRACT.md#graph-state); build a code-only
graph only when graph generation is in scope, keeping one shared graph per repository.
A graph or map is orientation and must be verified against live source.
An empty graph, a state other than `graphify_fresh`, zero inbound edges, `INFERRED`
edges, low coverage and zero search matches never prove unreachability. The pinned protocol's Understand Anything
graph pass applies only when a legacy `.understand-anything` graph is the sole index.

For every candidate check:
- callers, imports, re-exports, public package/CLI/API entrypoints;
- string/config/template references, runtime discovery, registries, reflection,
  dependency injection and serializers;
- generators, migrations, schemas, fixtures, tests, docs and examples;
- cross-package and external consumers, ownership and compatibility promises.

Require a known ownership boundary and no plausible live path.
Unknown public or dynamic consumers mean **retain and explain**, not “unused.”
Prefer private leaves with corroborating compiler/linter and reference evidence.
Record each candidate as `path:symbol`, its liveness checks, boundary risk,
replacement if any, and validation command. Require at least one executable
post-delete signal in the proposed verification before accepting removal.
Only candidates that pass this proof gate qualify for cleanup issues.
Uncertain liveness is held, not a speculative cleanup issue; name the missing
evidence and resume condition while independent proven candidates continue.

## Publish and stop

Use the linked handoff to reconcile all in-scope candidates against current source,
open and closed issues, linked PRs and ownership. Publish all supported, buildable,
uncovered outcomes; group candidates that share a fix and acceptance check.
Carry the reachability proof, ownership boundary and exact verification command
into each issue. A planned post-delete check is not a passed check.

Preview in chat without waiting. Publish through Plan Handoff with native
`blockedBy` dependencies and `ai-ready` last. Preserve explicit no-dispatch,
pauses, live ownership and human-only gates. Report verified issue links,
covered/held dispositions, checks run versus proposed, and stop. Zero qualifying
findings means zero new issues. On failure, use the
[shared publication receipt](../shared/PLAN-HANDOFF.md#publication-receipt)
for unsaved proposals or partial/unknown writes and safe recovery.
Publication neither starts Orbi nor authorizes local implementation.

## Authorized local fixes

Keep this route separate from default publication. Confirm scope and actual
ownership, review, PR and human-only gates before editing. Save the narrowest
meaningful baseline check and apply the same proof gate above.
Delete one coherent batch, remove only newly orphaned support, rerun candidate
checks and affected validation, and inspect stale references and the actual diff.
A regression stops further deletion. Repair or restore only this batch's
attributable delta after comparing against its saved baseline and current files;
never use blanket Git restore/clean or overwrite intervening edits.

**Receipt:** candidates and evidence; removed `path:symbol` with proof; retained
candidates with exact uncertainty; baseline/post-delete checks; review; net removal
when measured; stop reason and next action. No proven candidate means delete
nothing. Honor read-only, batch and delivery limits.

No automatic commit or push.

**Example:** keep an exported plugin hook with unknown external consumers; publish
an issue for an independently proven private helper. Remove it locally only in
explicitly authorized fix/apply mode and only if its checks pass.

## Boundaries

- Not a refactor inside a file or a module extraction; publish a GitHub issue with a task
  and a check that passes before and after.
- Not a folder topology change; use `/split-folder`.
- Not an architecture review; use `/improve-codebase-architecture`.

**Done when:** every qualifying outcome has a verified issue or an exact publication
failure receipt, with uncertain candidates retained and explained; report-only
returns findings inline without writes; authorized fix/apply has post-delete checks.
Use the [Definition of Done](../shared/DEFINITION-OF-DONE.md) to separate these claims.
[Source and hashes](UPSTREAM.json) · [MIT license](upstream/LICENSE).