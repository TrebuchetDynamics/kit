# Bounded planning behavior specimens

`cases.json` preserves discovery, decision-stall and interview inputs as inert
data. It is not a runner or an execution receipt. The former builder/inspector
depended on the removed executor CLI and task-store implementation and is removed.

The cases retain empty/vague requests, accepted and missing intent, conflicting
specifications, verification gaps, active dirty ownership, repeats, large projects,
coordinator-owned substeps and multi-turn interview decisions. Legacy task-path
strings in these synthetic inputs are preserved specimens, not current authoring
instructions. New planning uses GitHub Issues and native dependencies.

`test_plan_for_me_discovery.py` checks retained scenario coverage without importing
an executor or creating task stores. These static checks do not evaluate model
adherence or establish live qualification. For any separately authorized model
evaluation, use a fresh context, preserve actual owner edits and pauses, inventory
all writes/tools and bind results to exact source and host/model inputs. Do not
score missing runs as compliance or fabricate replies.

The [original evaluation criteria](https://github.com/TrebuchetDynamics/kit/blob/ecc6061d7768dbe9286c6ca09ab403744b93ec1e/tests/fixtures/planning/README.md)
remain immutable requirements evidence. In particular, preserve accepted decisions,
ask only consequential unresolved questions, do not manufacture product direction
or approval, do not duplicate existing work, and distinguish planning publication
from implementation and live acceptance.
