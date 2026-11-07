# Service recovery

Load this branch only for runner/process faults. Use the installed
`autowork --help`, verb help and the [runner guide](../../../pi-autowork/README.md)
for current command contracts. Prefer supported commands over direct runtime edits.

1. **Bind the target.** Match runner name, repository, service unit and state
   directory from current registration and status. Check deliberate-stop markers,
   service enablement, running processes and pending service jobs. Preserve
   explicitly paused, disabled or stopped registrations even when their dashboard
   looks stale. For a previously enabled failed service, distinguish failure from
   an owner stop before recovery.
2. **Repair the fault.** Read the exact error and its original log/exit evidence.
   Resolve missing paths and stale source selection from supported registration
   commands and known repository evidence. Reuse a retained candidate and its valid
   checks. Implement source defects through Autowork before activation. A missing
   credential, unavailable checkout or unclear installation source is a precise
   unresolved input, not permission to substitute a different identity or source.
3. **Activate only what is authorized.** Reload an active target with
   `autowork restart TARGET` first; this keeps workers running. Restart a failed,
   previously enabled target only after its cause is repaired and deliberate stop
   is excluded. Use supported installation/source selection only within an existing
   installation grant; updating a shared package can affect runners outside the
   target, so preserve that deployment boundary. Keep stopped and paused targets
   unchanged unless the user explicitly authorizes their resumption.
4. **Read back before retry.** A timeout or nonzero result can leave a queued restart
   or an already re-executed process. Inspect the service manager's pending jobs,
   process birth identity, runner record, running release and fresh logs before any
   further mutation. An old status snapshot does not prove that a service is dead.
   Observe an existing restart instead of issuing another one. A SIGHUP and stop
   can race: package bytes, a reload request and an active systemd unit are three
   different facts, none sufficient to prove the intended release is executing.
5. **Preserve work.** When graceful reload is deferred, use the supported
   merge-safe restart only when target authority allows it. Immediate interruption
   (`--stop-workers --now`) requires explicit user authorization; a stuck timer is
   not that authorization. Preserve attempts, worker reports and pending check
   evidence. Keep an interrupted check unproved and schedule its required
   verification through the existing owner.
6. **Verify the result.** Confirm service-manager state, actual executable release
   and an expected queue transition from fresh evidence. Recheck task eligibility
   with `autowork tasks why ID REPO`; observe dispatch, resumed review or integration
   where expected. If healthy but empty, report idle rather than inventing work.
   Separate service recovery from task completion and physical/live acceptance.
