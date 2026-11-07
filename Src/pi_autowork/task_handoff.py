"""Output-only decision handoff, derived from the exact reviewed task snapshot.

No file reads, mutations, selection, permission inference or runner acknowledgement.
The caller supplies validated committed/candidate stores from one commit preview.
"""


def answers(record):
    return tuple(line for line in record.body.splitlines()
                 if line.startswith('- Owner decision:') and line.partition(':')[2].strip()) if record else ()


def describe(committed, saved, paths, revision, workspace, baseline_error=None):
    from pi_autowork.engine.task_queue import deferred
    deferrals = deferred(saved) if saved else set()
    old_tasks = committed.tasks if committed else {}
    new_tasks = saved.tasks if saved else {}
    changed = set(paths)
    rows = []
    for tid in sorted(set(old_tasks) | set(new_tasks)):
        before, after = old_tasks.get(tid), new_tasks.get(tid)
        if not any(record and record.status == 'open' for record in (before, after)):
            continue
        if not (answers(before) or answers(after)
                or any(record and record.section == 'Needs decision' for record in (before, after))):
            continue
        pending = any(record and record.path in changed for record in (before, after))
        new_answer = committed is not None and bool(answers(after)) and answers(after) != answers(before)
        if pending:
            state, action = ('pending_commit' if new_answer else 'pending_edit'), 'review_commit'
        elif after and after.section == 'Needs decision':
            state, action = ('deferred', 'wait_for_input') if tid in deferrals else ('answer_required', 'answer')
        else:
            state, action = 'committed', 'inspect_selection'
        rows.append(dict(task=tid, state=state, next_action=action,
                         committed_section=before.section if before else None,
                         saved_section=after.section if after else None,
                         committed_record_revision=before.record_revision if before else None,
                         saved_record_revision=after.record_revision if after else None))
    return dict(workspace=workspace, committed_revision=revision,
                committed_inventory_available=committed is not None, baseline_error=baseline_error,
                decisions=rows, execution_evaluated=False,
                message='A saved answer is not a commit; a commit is not runner acceptance. '
                        'Selection, holds, dependencies and typed live permissions still apply.')
