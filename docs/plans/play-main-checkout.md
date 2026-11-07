# Safe main checkout for Play

## Accepted outcome

Status: Accepted

The owner reports that Play fails with “Check out main … the runner works only from the main branch checkout” and requests automatic, smart switching. Scope: explicit Play/start only, in the existing Python runner. Planning does not switch the reported checkout or start a service. Goal: PLAY-START; task: PLAY-001-1c9535c5.

## Evidence and planner calls

At Kit source 7da18ec9, `src/pi_autowork/command.py:cmd_start` rejects `fleet_view.readiness` before checking service state. `fleet_view.py:readiness` requires main/master; its `how_to_fix` produces the quoted refusal. Browse's `tui.py:ready_to_start` also gates on that read-only result, so a command-only repair is insufficient. Existing fleet Play calls start for stopped runners; resume for paused runners is a separate path and must not change.

Read-only inspection of the reported landing submodule found a clean detached HEAD equal to local main (dcb11c2d); this establishes the immediate safe case, not current service ownership or live acceptance. Its worktree inventory contains a submodule administrative path rather than the ordinary visible root. Resolve identity through Git, not by treating the first inventory path as a usable worktree. Keep that private repository path out of public examples and fixtures.

Planner's selected approach:

- Reuse cmd_start as the mutation boundary. Readiness, browsing, refresh, status, resolve and view-only controls stay nonmutating. No new dependency, workflow, service identity, worktree, or config store.
- Keep an already checked-out main or master. Otherwise prefer an existing local main, falling back to existing local master only when main is absent. Never infer a target from a remote or create a branch.
- On explicit start, switch a clean named feature branch using ordinary non-forced Git switching; its branch and commits remain intact. For detached HEAD require that HEAD is reachable from the selected target so no detached-only commit loses its reference. The reported equal-commit case is supported, including a real submodule fixture.
- Refuse tracked/index/untracked changes (including dirty submodules) and any ignored-file collision with the target tree, unresolved Git operations, a target checked out or locked in another worktree, and an observed active runner/writer. Explicitly prevent Git's default ignored-file overwrite behavior. Do not silently redirect to another checkout or change its saved service identity. Give the exact reason and safe manual next step. Preserve all existing admission/ownership guards; use available existing state/lease observations rather than inventing proof of arbitrary editor inactivity.
- Recheck branch, target ref, dirtiness and Git-operation state immediately before switching; if captured inputs drift, refuse rather than retry with new assumptions. Handle ordinary Git switch failure without service effects. This does not promise an atomic lock against arbitrary external Git/editor processes.
- After successful switching rerun uncached readiness, including committed task-store preparation. Only then allow existing service installation/start logic. A later readiness failure leaves the successful switch visible and reports it; no blind rollback. No pause/stop marker is cleared on refusal.
- Browse Play reaches this same explicit start boundary after a confirmation that names the target branch and possible switch. It must not require readiness to be already true for a recoverable branch-only issue, nor weaken task-store/root checks. Fleet Play and direct CLI start share the behavior; ordinary start confirmation is sufficient, no second approval ceremony. Paused resume, raw runner startup guard, forced preparation, and other UI/host permissions remain unchanged.

Rejected: removing the main-only invariant, switching during readiness, force checkout/stash/reset, remote fetch/branch creation, automatic worktree creation or redirection. These either endanger work, introduce identity changes, or exceed this repair. No product question remains; helper placement and ordinary reversible coding details belong to the implementer.

## Verification and delivery

One cohesive task owns the command, readiness presentation and Browse gate because they form one start transition. Add disposable real-Git fixtures to the existing command tests and a composed Browse test to existing TUI controls. Existing readiness tests continue proving read-only inspection. Tests must stub systemctl/install/process effects; never run against the owner's landing checkout or live service.

Proposed, unrun implementation checks:

- `python3 scripts/check.py tests/test_autowork_command.py pi-autowork/tests/test_fleet_view.py pi-autowork/tests/test_tui_controls.py`
- `python3 scripts/affected_tests.py --run`
- `git diff --check`

Builder check: fresh read-only review found two material gaps, both resolved here. Extend test_start_preserves_unsafe_checkout with an ignored-file collision fixture; ordinary non-forced switching alone can overwrite ignored files. Require test_play_routes_safe_branch_switch to execute, not dependency-skip. Follow docs/testing.md#prepare-the-pinned-textual-cache: first check the pinned cache with `uv run --offline --no-project --with textual==8.2.8 python3 -c 'import textual; print(textual.__version__)'`. If absent, the implementation task includes bounded test-only cache preparation via the documented `uv run --no-project --with textual==8.2.8 python3 -c 'import textual; print(textual.__version__)'`, then repeat the offline check with the same interpreter/cache. This is a future worker setup step, not performed in planning. No service/package activation is involved. If network/cache preparation is unavailable, report that exact input missing; a skipped pilot does not meet UI acceptance.

Premortem: refresh switches branches (read-only guard); dirty/detached/other-worktree content is lost (real-Git preservation fixtures); Browse still rejects before command execution (composed Play regression). Invariants: no forced Git operation, no task-store bypass, no hidden service identity change, no loss of local work.

First execution action: add the failing clean-detached-at-main command regression, then the composed Browse regression. Expected delivery is one implementation merge and one independent review gate under the existing execution workflow, separate from this planning commit. No background start is requested. Offline fixture evidence will not qualify native UI behavior or the owner's actual service; live confirmation remains unassessed and requires later authority.
