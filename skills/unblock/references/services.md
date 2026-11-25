# Service boundaries

An Unblock invocation does not enable a deployment, release deliberate-stop state
or authorize interruption.

For separately authorized operations on a supported deployment:

1. Bind the exact repository, deployment, service and actual executable release.
   Read explicit pauses, process birth identity and pending service jobs first.
2. Repair the evidenced cause, keeping original attempts, logs and candidates.
   Do not treat missing credentials as permission to change identities.
3. Before any mutation, verify its target and existing authority. Resumption and
   interruption require explicit user authorization when the deployment is paused.
   Updating a shared package can affect targets outside the requested repository.
4. Observe an existing restart rather than retrying blindly. A timeout may leave
   a pending job; inspect process identity, logs and service state before retry.
5. Verify the operation and consumption separately. An active process does not
   prove issue pickup, successful checks, review, merge or failure recovery.

Use [the cutover guide](../../../docs/github-native.md). Preserve unrelated Hermes
gateways and ordinary Pi/Claude/Codex sessions. Never delete task data, worktrees
or attempts/recovery state to make a service appear healthy.
