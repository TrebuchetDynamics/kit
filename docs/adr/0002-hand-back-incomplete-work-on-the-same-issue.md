# 0002 — Hand back incomplete work on the same issue when requirements change

**Status:** Accepted design. This decision does not establish that Orbi resumed work or that the revised behavior passed its tests.

When an accepted requirement changes after a delivery attempt, keep useful work on the original issue. A handoff must identify the retained commit, the behavior still missing against the revised requirement, and the test that would prove it. Check current ownership and pauses: route the handoff to the existing delivery owner, not a second implementer. If binding decisions conflict, hold only the work affected by that conflict.

For example, [#125’s retained commit](https://github.com/TrebuchetDynamics/kit/issues/125#issuecomment-7083114011) passed tests for the old requirement. **WHEN** the revised requirement distinguishes a documented answer from a conflict between authorities, **THEN** the handoff names both cases: use the documented answer in the first, and ask for a decision only on the conflicting part in the second. The delivery owner must demonstrate those outcomes before claiming delivery, not before accepting the handoff.

Requiring a finished fix before handoff would make the recovery operator do the delivery owner’s work. Requeuing the old commit without naming the gap would send the owner back to the same incomplete result. Report [handed back](../GLOSSARY.md#handed-back) only for the handoff; report resumed only after observing continued work on the issue.

References: [Unblock workflow](../../skills/unblock/SKILL.md), [GitHub delivery contract](../github-native.md).
