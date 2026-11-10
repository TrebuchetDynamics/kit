+++
schema = 1
id = "SUPERVISION-PLAN-001"
title = "Plan the next supervision-reducing changes from the owner's 2026-11-10 review"
short = "Plan supervision-reducing batch"
status = "open"
section = "Next"
rank = 27000
depends_on = []
touches = ["tasks/items/"]
resources = []
kind = "plan"
ownership = "worker"
scope = "The owner's 2026-11-10 review of Autowork names one target, less supervision per delivered change, and five weaknesses. The first, a Verified close that overstates its evidence, is CLOSE-EVIDENCE-001 and is out of scope here. For each of the other four, read the current source and decide from evidence whether it is already handled, and if not write at most one bounded worker task. (1) Landing before adequate verification: a merge check passed while a test asserting removed content failed only at deployment; find whether the check run on a landing candidate is bound to the exact combined tree and whether excluded or unselected tests are visible before the landing rather than only in a receipt. (2) Parallel isolation: runner merges changed a checkout while a gate was running in it; find which checks run in a checkout the runner can still move, and what resource admission exists beyond declared resources and ports. (3) One authoritative state: a task shown as a planning blocker was later ready for planning after a completed recovery; find whether the task views show the state's time, its latest transition and the recovery action from one source. (4) Recovery ambiguity: set-aside attempts, replacement commits and patch-equivalent worktrees are hard to classify; find whether an attempt records superseded by, landed as, still active or retained for recovery. Planning churn itself is the fifth: this task adds no successor planning task and no proof matrix."
acceptance = ["Each of the four areas has a short finding with file and line references stating what the code does today; an area the code already handles is recorded as handled with the evidence, not turned into a task.", "At most four new worker implementation tasks exist, each with bounded touches, runnable checks, acceptance a regression can prove and no dependency on an owner answer; anything that needs an owner decision is one Question under Needs decision.", "No successor planning task is created, and CLOSE-EVIDENCE-001 is neither duplicated nor edited."]
checks = ["autowork tasks validate --worktree ."]
exclusions = ["No production code, tests, installs, model execution beyond this planning run, service changes or publication in this planning task."]
+++
