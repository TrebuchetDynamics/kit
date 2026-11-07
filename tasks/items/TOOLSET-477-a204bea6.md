+++
schema = 1
id = "TOOLSET-477-a204bea6"
title = "Admit bounded read bursts without retrying mutations"
short = "Queue bounded Paseo read bursts"
status = "open"
goal = "PASEO-PLUGIN"
section = "Now"
rank = 3000
depends_on = []
touches = ["integrations/paseo/server/process.ts", "integrations/paseo/server/autowork-client.ts", "integrations/paseo/tests/server.test.ts", "integrations/paseo/docs/security.md"]
resources = []
kind = "implementation"
ownership = "worker"
scope = "Reuse the already-reviewed idle Paseo decision-repair candidate's server-only opt-in read admission. Keep the finite process pool; permit at most eight waiting reads for at most five seconds before spawn, with FIFO grant, abort/expiry/shutdown rejection and no command replay. Mark only server-authored read calls in AutoworkService for waiting. Mutations remain fail-fast; preserve release/revision/policy checks and all subprocess output/cancellation/redaction guards. Do not import unrelated UI draft or closure changes."
acceptance = ["Existing server fixture proves queued reads execute once when a slot frees, overflow/expiry/abort/shutdown never dispatch waiting commands, and mutation calls remain fail-fast/started=false under saturation without increasing concurrency.", "A concurrent fleet/task/detail/goals/models/pending read burst completes through the same finite pool; existing policy/release/uncertain-mutation/redaction/cancellation tests and typechecks remain passing. Security docs state exact bounds and no automatic retry."]
checks = ["npm run check --prefix integrations/paseo", "git diff --check"]
exclusions = ["No policy/grant changes, UI behavior changes, schema/manifest/lock changes, live Paseo/plugin/service operations, provider execution, installation or publication. Kit runner remains deliberately stopped.", "No unbounded queuing, increased process concurrency, or automatic retry after mutation dispatch/uncertain outcome. Preserve original dirty decision-repair candidate."]
+++
- Sources: Current server ProcessRunner immediately rejects all calls when the process pool is full; retained reviewed server read-admission candidate in .worktrees/paseo-decision-repair. The original candidate's base blobs for both server files and server.test.ts match this private branch exactly, so reuse does not overwrite newer behavior.
- Work search: Independent useful reliability slice after portable Work and recovery guard implementation; canonical landing remains blocked by an unrelated active Src-to-src migration. Queue currently has owner/live-only and Needs decision work; none of those gates are bypassed. Rejected replaying uncertain mutations or raising concurrency to mask burst failure.
- Decisions: Wait is opt-in only for server-authored read/preflight calls; hard queue8, hard admissionwait5000ms, existing process deadlines begin after admission, no replay. FIFO and lifecycle cleanup remain inside ProcessRunner. Test seeding avoids child-log readiness timing assumptions.
- Repo obligations triggered: Shared process/client transport, existing server tests and security boundaries doc. No native/Paseo permission or package version change. Offline fake-executable tests do not prove live plugin adoption.