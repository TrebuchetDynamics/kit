# Service recovery

Use this branch for runner/process faults or activation after a verified repair.
Read the installed verb help and the [runner guide](../../../pi-autowork/README.md)
for the operation needed. Use supported commands, not direct runtime edits.

1. **Bind the target.** Match runner name, repository, service unit and state
   directory from current registration and status. Check deliberate-stop markers,
   service enablement, process birth identity and pending service jobs. Finish with
   failure distinguished from an explicit pause, disablement or owner stop.
2. **Repair the fault.** Read the exact error and its original log/exit evidence.
   Resolve missing paths and stale source selection through supported registration.
   For source defects, return to Unblock's repair step. Finish with a checked repair
   or the exact unavailable credential, checkout or installation source; retain the
   configured identity and source rather than substituting another.
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
   further mutation. Observe an existing restart instead of issuing another one.
   Finish with the operation's result or a named pending job. A SIGHUP and stop can
   race; neither a successful signal nor installed bytes proves activation.
5. **Preserve work.** When graceful reload is deferred, use the supported
   merge-safe restart only when target authority allows it. Immediate interruption
   (`--stop-workers --now`) requires explicit user authorization; a stuck timer is
   not that authorization. Preserve attempts, worker reports and pending check
   evidence. Keep an interrupted check unproved and schedule its required
   verification through the existing owner.
6. **Return to queue verification.** Confirm service-manager state and actual executable release.
   Complete [Unblock's verification step](../SKILL.md#recover-verify-continue);
   an active service alone does not prove that the repaired task resumed.
