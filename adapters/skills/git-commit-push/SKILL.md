---
name: git-commit-push
description: "Commit current branch, sync and push its upstream."
disable-model-invocation: true
---

# Git Commit Push

Apply the [shared Ponytail method](../../../skills/shared/PONYTAIL.md) within this workflow's scope.

Use the [ASD-STE100 and project language rules](../../../skills/shared/COMMUNICATION.md) for user-facing text.

Read the [host-neutral Git Commit Push workflow](../../../skills/git-commit-push/SKILL.md) first.

Read the [host contract](../COMMON.md).

Use this host's native Git and file tools, not another host's commit helpers.
The canonical workflow owns scope, mode-aware inspection, sync and publication;
this adapter adds no fetch, commit or push default. For inbound requests, load its
[pull and merge procedure](../../../skills/git-commit-push/references/pull-merge.md)
within the same mode and caller limits.
