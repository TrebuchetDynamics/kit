"""Real TUI answer/save flow in disposable Git repositories; no services or models."""
import asyncio
from pathlib import Path
import subprocess
import threading
import tomllib
from unittest.mock import patch

from test_task_history import TaskHistoryTests
from pi_autowork import fleet_view, task_snapshot, tui
from textual.widgets import Button, OptionList, Select, Static, TextArea


async def main():
    for width in (80, 120):
        fixture = TaskHistoryTests()
        fixture.setUp()
        try:
            second = fixture.repo / 'tasks/items/T-2.md'
            second.write_text((fixture.repo / 'tasks/items/T-1.md').read_text()
                              .replace('id = "T-1"', 'id = "T-2"').replace('depends_on = []', 'depends_on = ["T-1"]'))
            fixture.git('add', '.')
            fixture.git('commit', '-qm', 'second question fixture')
            runner = fixture.runner
            runner.snapshot = task_snapshot.capture(fixture.repo, engine_observation=None, generation=2)
            runner.prepare_state = 'converted'
            runner.questions = [fleet_view.Question('T-1', 'decision', 2, 'Which design should we use?',
                                                    'Choose the smaller design', kind='decision')]
            baseline = fixture.git('rev-parse', 'HEAD')
            calls, notices = [], []
            started, release = threading.Event(), threading.Event()
            show_started, show_release = threading.Event(), threading.Event()
            release.set()
            command = str(Path(__file__).resolve().parents[1] / 'bin/autowork')

            def run(argv, **kwargs):
                assert argv[:2] == [command, 'tasks'], argv
                assert argv[2] in ('show', 'decide'), argv
                calls.append(argv)
                if argv[2] == 'show':
                    show_started.set()
                    assert show_release.wait(10), 'test read barrier was not released'
                if argv[2] == 'decide':
                    started.set()
                    assert release.wait(10), 'test save barrier was not released'
                return subprocess.run(argv, **kwargs)

            class FixtureApp(tui.FleetApp):
                def refresh_fleet(self, cached):
                    self.runners = [runner]
                    self.selected = runner.name
                    self.show_detail()

            app = FixtureApp(command=command, script='/unused', state_root='/missing', env_dir='/missing',
                             runner_cmd=run)
            with patch.object(app, 'logs', return_value=''):
                async with app.run_test(size=(width, 30)) as pilot:
                    try:
                        await pilot.press('e')
                        assert await asyncio.to_thread(show_started.wait, 3)
                        # A previously started action can complete while this modal loads.
                        app.action_completed()
                    finally:
                        show_release.set()
                    await pilot.pause(.3)
                    assert isinstance(app.screen, tui.DecisionPrompt), 'Fleet e must open the only question directly'
                    screen = app.screen
                    for _ in range(100):
                        if not screen.query_one('#decision-save', Button).disabled:
                            break
                        await pilot.pause(.05)
                    assert screen.record is not None, 'Invalidation during load must reschedule the current record read'
                    assert screen.focused is screen.query_one('#decision-text', TextArea), 'The answer editor must own first focus'
                    context = screen.query_one('#decision-context', TextArea).text
                    assert 'Which design should we use?' in context and 'Choose the smaller design' in context
                    assert '2' in context and 'T-1' in context
                    assert 'T-2' in context, 'Show the dependent task, not only an unblock count'
                    assert screen.query_one('#decision-text', TextArea).text == '', 'Never silently accept a suggestion'
                    form = screen.query_one('#decision-form')
                    assert form.region.width <= width, form.region
                    assert form.region.height < 29, form.region
                    assert screen.query_one('#decision-save', Button).region.bottom <= 30
                    await pilot.press('ctrl+enter')
                    assert app.screen is screen and not any(a[2] == 'decide' for a in calls)
                    screen.query_one('#decision-text', TextArea).load_text('Use the smaller design')
                    # A concurrent owner edit after opening must refuse, retaining the draft.
                    record = fixture.repo / 'tasks/items/T-1.md'
                    record.write_text(record.read_text() + '\n- Other owner: preserve this edit\n')
                    with patch.object(app, 'notify', side_effect=lambda message, **kw: notices.append(str(message))):
                        await pilot.press('ctrl+enter')
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                    assert app.screen is screen, 'A stale refusal must retain the answer editor'
                    assert screen.query_one('#decision-text', TextArea).text == 'Use the smaller design'
                    assert 'Owner decision:' not in record.read_text()
                    assert any('--expect' in a for a in calls if a[2] == 'decide'), calls
                    assert 'stale' in screen.query_one('#decision-status', Static).render().plain.lower() or notices
                    await pilot.press('escape')
                    await pilot.press('e')
                    await pilot.pause(.3)
                    screen = app.screen
                    for _ in range(100):
                        if not screen.query_one('#decision-save', Button).disabled:
                            break
                        await pilot.pause(.05)
                    screen.query_one('#decision-text', TextArea).load_text('Use the smaller design')
                    started.clear()
                    release.clear()
                    with patch.object(app, 'notify', side_effect=lambda message, **kw: notices.append(str(message))):
                        try:
                            await pilot.press('ctrl+enter')
                            assert await asyncio.to_thread(started.wait, 3)
                            count = len([a for a in calls if a[2] == 'decide'])
                            await pilot.press('ctrl+enter', 'escape')
                            assert app.screen is screen, 'An in-flight mutation cannot be cancelled as if it never ran'
                            assert screen.query_one('#decision-text', TextArea).disabled, 'Do not lose edits typed during save'
                            assert len([a for a in calls if a[2] == 'decide']) == count
                        finally:
                            release.set()
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                    assert not isinstance(app.screen, tui.DecisionPrompt)
                    assert any('committed locally' in n.lower() for n in notices), notices
                    assert 'Owner decision:' in record.read_text() and 'Other owner:' in record.read_text()
                    assert fixture.git('rev-parse', 'HEAD') != baseline, 'Save must commit the answer'
                    committed = fixture.git('show', 'HEAD:tasks/items/T-1.md')
                    assert 'Use the smaller design' in committed and 'Other owner:' not in committed
                    assert '--commit' in next(a for a in reversed(calls) if a[2] == 'decide')
                    assert 'live = "authorized"' not in record.read_text()
                    # Section intent is saved explicitly; no close, release or permission grant.
                    for section in ('Next', 'Needs decision'):
                        await pilot.press('e')
                        await pilot.pause(.3)
                        screen = app.screen
                        for _ in range(100):
                            if not screen.query_one('#decision-save', Button).disabled:
                                break
                            await pilot.pause(.05)
                        assert screen.query_one('#decision-text', TextArea).text.endswith(
                            'Use the smaller design' if section == 'Next' else 'Keep the same scope'), \
                            'Reopening must restore the actual saved answer, never an empty replacement'
                        assert screen.query_one('#decision-context', TextArea).text.startswith(
                            'Saved answer (working record):')
                        screen.query_one('#decision-text', TextArea).load_text('Keep the same scope')
                        screen.query_one('#decision-section', Select).value = section
                        await pilot.click('#decision-save')
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        data = tomllib.loads(record.read_text().split('+++', 2)[1])
                        assert data['section'] == section and data['status'] == 'open'
                        assert data.get('live', 'denied') == 'denied'
                    assert fixture.git('rev-parse', 'HEAD') != baseline
                    assert 'section = "Needs decision"' in fixture.git('show', 'HEAD:tasks/items/T-1.md')
                    # A stale generic approval question must not hide the real saved answer
                    # or imply that another approval can execute an owner-only task.
                    record.write_text(record.read_text().replace('ownership = "worker"', 'ownership = "owner"'))
                    runner.questions = [fleet_view.Question('T-1', 'decision', 2,
                                                            'T-1 requires owner action or recorded live authorization; '
                                                            'an unattended runner cannot run it.', kind='outside')]
                    before_owner_read = record.read_bytes()
                    before_owner_head = fixture.git('rev-parse', 'HEAD')
                    await pilot.press('e')
                    await pilot.pause(.3)
                    screen = app.screen
                    for _ in range(100):
                        if not screen.query_one('#decision-save', Button).disabled:
                            break
                        await pilot.pause(.05)
                    assert screen.query_one('#decision-text', TextArea).text.endswith('Keep the same scope')
                    context = screen.query_one('#decision-context', TextArea).text
                    assert context.startswith('Saved answer (working record):')
                    assert 'Another approval is not required' in context
                    assert 'owner-performed action still outstanding' in screen.query_one(
                        '#decision-status', Static).render().plain
                    await pilot.press('escape')
                    assert record.read_bytes() == before_owner_read
                    assert fixture.git('rev-parse', 'HEAD') == before_owner_head
                    # A new planning/input question is not resolved by that historic answer.
                    runner.questions = [fleet_view.Question('T-1', 'decision', 2,
                                                            'Choose the changed planning scope', kind='decision')]
                    show_started.clear()
                    show_release.clear()
                    try:
                        await pilot.press('e')
                        assert await asyncio.to_thread(show_started.wait, 3)
                        await pilot.press(*'new draft')
                    finally:
                        show_release.set()
                    await pilot.pause(.3)
                    screen = app.screen
                    for _ in range(100):
                        if not screen.query_one('#decision-save', Button).disabled:
                            break
                        await pilot.pause(.05)
                    context = screen.query_one('#decision-context', TextArea).text
                    assert 'Choose the changed planning scope' in context
                    assert 'Another approval is not required' not in context
                    assert 'Keep the same scope' in context
                    assert screen.query_one('#decision-text', TextArea).text == 'new draft', \
                        'Loading a saved answer must not overwrite a draft typed during the read'
                    await pilot.press('escape')
                    assert record.read_bytes() == before_owner_read
                    # An ordinary outside Needs-decision root also still needs its input.
                    runner.questions = [fleet_view.Question('T-1', 'decision', 2,
                                                            'Choose the missing API scope', kind='outside')]
                    await pilot.press('e')
                    await pilot.pause(.3)
                    screen = app.screen
                    for _ in range(100):
                        if not screen.query_one('#decision-save', Button).disabled:
                            break
                        await pilot.pause(.05)
                    context = screen.query_one('#decision-context', TextArea).text
                    assert 'Choose the missing API scope' in context
                    assert 'Another approval is not required' not in context
                    await pilot.press('escape')
                    assert record.read_bytes() == before_owner_read
                    # Several questions use a keyboard picker; unrelated historic annotations stay read-only.
                    runner.questions = [fleet_view.Question('MAIN', 'decision', 0, 'No editable task'),
                                        *runner.questions, fleet_view.Question('T-1', 'input', 0, 'Duplicate')]
                    await pilot.press('e')
                    await pilot.pause(.3)
                    assert isinstance(app.screen, tui.DecisionPrompt), 'Duplicate IDs must not add picker rows'
                    await pilot.press('escape')
                    # A stale inventory may still offer a task deleted since its capture.
                    runner.questions.append(fleet_view.Question('T-2', 'decision', 1, 'Another question'))
                    second.unlink()
                    await pilot.press('e')
                    await pilot.pause()
                    # Picker includes questions even if task vanished; actual opening must fail closed.
                    assert isinstance(app.screen, tui.QuestionPicker)
                    options = app.screen.query_one(OptionList)
                    options.highlighted = 1
                    await pilot.press('enter')
                    await pilot.pause(.4)
                    assert isinstance(app.screen, tui.DecisionPrompt)
                    assert app.screen.query_one('#decision-save', Button).disabled
                    await pilot.press('escape')
                    app.view_only = True
                    before = len(calls)
                    await pilot.press('e')
                    await pilot.pause()
                    assert not isinstance(app.screen, (tui.DecisionPrompt, tui.QuestionPicker)) and len(calls) == before
            print('PASS decisions', width, 'context, keyboard, stale edit, scoped answer commit, picker, view-only')
        finally:
            fixture.doCleanups()


if __name__ == '__main__':
    asyncio.run(main())
