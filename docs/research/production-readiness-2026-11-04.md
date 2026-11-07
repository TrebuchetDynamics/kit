# Production-readiness requirements

This page retains current publication, recovery, security and live-qualification
boundaries. Completed audits, issue timelines, test runs and local scorecard samples
remain in Git history, not as a claim of current acceptance.

## Repository and publication

Reject inherited Git routing before repository/service writes and sanitize descendant
Git environments. Candidate and task-store reads must bind the selected repository,
not inherited `GIT_DIR`, `GIT_WORK_TREE`, index or replacement-ref overrides.

Publication requires effective `PI_AUTOWORK_PUSH=1`. Preserve saved-grant behavior,
explicit-negative conflicts, clear apply guidance and status readback of launch versus
saved settings. Source checks alone do not qualify an actual saved-grant/no-grant
systemd restart. A repository becoming unusable or changing identity must stop safely
before merge/push rather than continue or enter an uncontrolled restart loop.

## Interactive policy

The conservative-interactive versus explicit-autonomous policy remains an owner
security decision. Preserve `apply_runtime_defaults: false` as the no-write opt-out;
do not silently widen approvals, destructive-command confirmation, MCP reload or
turn limits for existing profiles. The bounded pending policy proposal requires
manual approvals and `max_turns=90` for a fresh interactive profile, explicit opt-in
for autonomous values and a preview naming the selected policy. This documentation
neither settles the owner question nor changes upstream Hermes or any profile.

## Qualification boundaries

- Prepare/Prepare-and-start and readiness refresh need offline fixture coverage;
  a headless pilot is not a real terminal/desktop session or live repository proof.
- Close/reopen, dependencies, question freshness and archive/import behavior have
  distinct acceptance bullets. Do not close a multi-part issue from one fixture.
- A real disposable-repository delivery requires actual authority, admission,
  independent review, checks, integration/closure and source-bound evidence. An
  interruption/restart must preserve the attempt without duplicate effects. Do not
  infer that live permission or successful execution from an offline source review.
- Retain open-slot receipts and unfinished-review evidence. Any separately authorized
  runtime retention cleanup must preserve actual work, recovery and private state;
  this repository's completed-record pruning is not runtime deletion authority.
- Onboarding should enable one verified change without introducing another skill or
  requiring knowledge of every internal command.

The 30-day multi-product evaluation remains unqualified. A local development
scorecard is not that trial. Keep measured, estimated and missing values distinct;
unavailable cost, owner time, delivery endpoints or uptime must never become zero.
No live model, service restart, profile write, deployment or publication is authorized
by these requirements or by removal of historical reports.
