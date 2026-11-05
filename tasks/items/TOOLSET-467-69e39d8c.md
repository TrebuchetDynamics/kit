+++
schema = 1
id = "TOOLSET-467-69e39d8c"
title = "Record the standing autonomy policy audit of open owner questions"
short = "Record the policy audit"
status = "open"
goal = "PLANNING-AUTHORITY"
section = "Next"
rank = 8000
depends_on = []
touches = ["docs/autonomy.md", "tasks/items/TOOLSET-431-47a7152e.md", "tasks/items/TOOLSET-450-e643cb7a.md", "tasks/items/TOOLSET-451-ba324296.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Audit every open task in section Needs decision against docs/autonomy.md. The open tasks at planning time are TOOLSET-431-47a7152e, TOOLSET-450-e643cb7a and TOOLSET-451-ba324296. For each question, record on the task whether it is a delegated decision or an owner-only decision. A choice is delegated only when docs/autonomy.md#delegated-decisions covers it and it is reversible; otherwise it is owner-only. For a delegated, reversible choice, choose the smallest complete option that preserves accepted behavior and checks, record a Standing policy: note with the policy anchor, the chosen option, the reason and the evidence, and move the task to Now or Next without changing its acceptance, exclusions, dependencies or history. For an owner-only question, keep the task in Needs decision and add a Question: note that names the missing owner input and the resume condition. Do not write an Owner decision: note for a planner call. Do not create an owner_waiver or owner_qualification. Do not answer a question outside the delegated domains. Append one dated entry to docs/autonomy.md#audit-log naming the audited IDs, each delegated or owner-only disposition, the moved IDs and the remaining owner questions. Do not change code. Report the audited IDs, the moved IDs and the remaining owner questions."
acceptance = ["docs/autonomy.md is linked from AGENTS.md and names the delegated domains, owner-only decisions, the Standing policy recording rule and change control; python3 skills/docs-sync/scripts/docs.py check . passes.", "Every open Needs decision task at audit time has either a Standing policy: note naming a delegated domain and the chosen option, reason and evidence, or a Question: note naming its owner-only reason. No acceptance, exclusion, dependency, owner decision or live authorization is invented or weakened. The dated audit entry is appended to docs/autonomy.md#audit-log and names the audited IDs, each disposition, the moved IDs and the remaining owner questions.", "autowork tasks validate --worktree . passes and the read-back report lists each audited task ID, the moved IDs and the remaining owner questions."]
checks = ["autowork tasks validate --worktree .", "python3 skills/docs-sync/scripts/docs.py check ."]
exclusions = ["No product, live, publication, deployment, credential, money, secret or destructive change.", "No change to task acceptance, exclusions, dependencies, ownership or history.", "No Owner decision note, owner waiver or owner qualification for a planner call.", "No automatic answer for a question outside the delegated domains in docs/autonomy.md."]
+++
- Sources: docs/autonomy.md#applying-the-policy-to-a-question; docs/autonomy.md#audit-log; docs/autonomy.md#delegated-decisions; AGENTS.md#autowork-autonomous-local-progress; docs/project.md#planning-authority-and-shared-protocol-2026-11-01
- Audit starting point (planner read; verify against docs/autonomy.md): TOOLSET-431-47a7152e, TOOLSET-450-e643cb7a and TOOLSET-451-ba324296 were the open Needs decision tasks at planning time. Each appears owner-only to the planner (a repository rename and npm scope plus a live-profile proof; a Hermes approval security default; an authorized spend-and-target live delivery). Record the disposition from the policy, not from this note.
- Queue disposition: open in Next, no hold. This implementation carries the audit described by the plan record TOOLSET-466-7865eb37; it edits the audited task records and docs/autonomy.md#audit-log.
