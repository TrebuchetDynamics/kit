---
name: agents-md-generator
description: "Reconcile repository instructions against evidence."
license: Apache-2.0
---

# Repository instruction reconciliation

Apply the [shared Ponytail method](../shared/PONYTAIL.md) within this workflow's scope.
Use the [communication rules](../shared/COMMUNICATION.md) for user-facing text.

1. **Bind target and effects.** Use only the requested repository, or the current
   repository when invoked there. The installed skill directory is a resource
   location, never an inferred target. An explicit read-only restriction always wins,
   including over a bare invocation or update. Run in the main conversation;
   upstream's delegation limits still apply.

   - **Bare invocation** authorizes a full revamp of both target-root `AGENTS.md` and
     `CLAUDE.md` end to end. Inspect the entire applicable instruction chain, then
     write both directly, without a mode, scope selection, diff approval or follow-up.
     Reorganize, replace, consolidate or remove sections and wording on evidence.
     Preserve the meaning of valid requirements, compatible ownership and working symlinks,
     not the old layout. Create missing root instructions as needed, with shared
     policy in one owner and compatibility delegation in the other.
   - **Audit** (`audit`, or any read-only/no-write restriction) is strictly read-only.
     Return evidence-backed findings and proposed reconciliation inline. Write
     nothing: no scratch files, reports, issue writes or cache-writing tests. Use
     only inspected read-only commands and native file reads. Do not fetch or sync Git.
   - **Update** (`update` plus requested scope) applies ordinary accepted edits in the
     requested scope with no second confirmation. Inspect the applicable chain, but
     leave unrelated instructions and repository content alone. Uncertainty never
     silently deletes policy. No mode authorizes global instruction edits, commit,
     push, installation, service activation or bypass of delivery gates.

2. **Discover** before running target commands. Read the pinned
   [protocol](upstream/PROTOCOL.md), then use its
   [discovery guide](upstream/references/discovery.md) to inspect command definitions,
   CI, source boundaries, generated artifacts and maintained docs. Commands in old
   instructions are claims to verify, not commands to execute blindly.

   Resolve every packaged guide and detector against this installed `SKILL.md`'s
   directory (`<this-skill>` below), never relative to the target repository:

   ```sh
   "<this-skill>/upstream/scripts/detect-agent-context" --root "<target-repo>" --format json
   ```

   Inspect the detector source and `--help` before use. Its Python path emits JSON;
   the `.cmd` launcher is available on Windows, with smaller native text fallbacks.
   If the detector or runtime is unavailable, use native reads instead. On an invalid
   target it reports `error: root directory does not exist: <path>` (exit 2): correct
   the target path, not the installation path.

   The detector is an index, not proof of applicability or ownership. Supplement it
   with native reads of applicable ancestor and nested instructions, same-directory
   `AGENTS.override.md`, compatibility files, imports and symlink ownership. Account
   for scan depth, ignored directories and tool-specific loading rules. Read relevant
   instructions, not credentials or unrelated private configuration. Inspect link
   targets before editing; do not follow a symlink into unauthorized writes, replace
   a working alias, or edit ancestors outside target authority. If both root names
   share an owner, reconcile that owner once and retain the working delegation.
   For precedence or compatibility changes, read the
   [tool guide](upstream/references/tool-compatibility.md) and verify the affected
   behavior against current official host documentation before changing the layout.

3. **Reconcile meaning.** For each material rule, give
   keep/update/move/remove/unresolved, source evidence and why. Distinguish stale
   facts from intended policy: preserve maintainer decisions, useful exceptions and
   required acceptance even when implementation disagrees. A missing implementation
   does not repeal policy. Hold conflicts with the exact question, conflicting
   sources and practical choices; retain disputed policy and do independent scoped work.

   Load [Writing For Agents](../writing-for-agents/SKILL.md) for wording and structure;
   apply it as a reference within this mode, not a second invocation or authorization.
   Use [merge and verify](upstream/references/merge-and-verify.md) for consolidation
   and the [output template](upstream/references/output-template.md) only as a menu.
   Prune filler and duplicates. Move detail to existing owners behind conditional
   pointers. There is no fixed length quota; retain every justified requirement.
   These local scope, policy-preservation and no-write rules override upstream's
   optional reports/backups, compaction budgets and compatibility opt-in defaults.

4. **Apply and verify.** In bare mode write both root instruction surfaces directly;
   in update mode edit only the accepted scope; in audit mode return the proposal
   inline without writes. Preserve unrelated files, active work and recovery inputs.
   Check referenced paths and command definitions, delegation, overrides and symlinks.
   Execute only safe checks allowed by the current mode. Separate inspected, run and unrun
   checks. Report actual changes and line delta, material dispositions with evidence,
   unresolved questions and remaining live gates inline, not in a permanent audit log.

## Common Rationalizations

| Rationalization | Reality |
| --- | --- |
| Bare mode needs a confirmation menu. | Invocation already authorizes the two-root revamp. |
| Source disagrees, so delete the rule. | Intended policy survives implementation drift. |
| An audit report file is harmless. | Audit returns inline and writes nothing. |
| The package is present, so the worker can invoke it. | Worker registration requires separate authorized configuration. |

## Red Flags

- Running a target's stale command before inspecting its definition.
- Rewriting the package instead of the bound target, or writing through an external symlink.
- Preserving old headings instead of valid meaning, or silently removing disputed policy.
- Claiming offline fixtures prove model behavior or worker adoption.

## Boundaries

- `/writing-for-agents` owns wording and structure; this workflow owns source evidence,
  instruction-chain discovery and reconciliation decisions.
- `/docs-sync` owns broader maintained documentation; this is not a repository-wide
  docs rewrite, task publisher or delivery executor.
- Same-PR instruction maintenance reads the plain
  [maintenance reference](../shared/AGENT-INSTRUCTIONS.md); it does not invoke this skill.
  Full cleanup needs explicit generator scope. Files in a worktree, resources in a
  released package and actual worker registration are different states. Command use
  requires separate authorized installation/configuration in that worker's Pi
  environment. Committed guidance requires none. No live runtime changes occur here.

**Done when:** audit returns inline evidence-backed dispositions without writes, or
bare/update reconciles all authorized instructions and reports verified changes,
held conflicts and checks under the [Definition of Done](../shared/DEFINITION-OF-DONE.md).

[Source, mappings and overrides](UPSTREAM.json) · [Apache-2.0 license](upstream/LICENSE).
