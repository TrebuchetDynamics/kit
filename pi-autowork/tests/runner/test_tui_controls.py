"""Keyboard, click and compact-dialog contracts; no live services or devices."""
import argparse
import asyncio
from dataclasses import replace
import os
import tempfile
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from offline_textual import textual_unavailable

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import fleet_view, task_snapshot
import test_task_history
from test_tui_layout import run_pilot, settle


def visible(widget, screen):
    region = widget.region
    assert region.width > 0 and region.height > 0, (widget, region)
    parent = widget.parent
    while parent is not None:
        assert parent.content_region.contains_region(region), (widget, region, parent, parent.content_region)
        if parent is screen:
            break
        parent = parent.parent


async def controls_pilot(case):
    from pi_autowork import tui
    from textual.widgets import Button, Input, OptionList, Select, TextArea

    for size in ((80, 24), (60, 18)):
        fixture = test_task_history.TaskHistoryTests()
        fixture.setUp()
        try:
            second = fixture.repo / 'tasks/items/T-2.md'
            second.write_text((fixture.repo / 'tasks/items/T-1.md').read_text()
                              .replace('id = "T-1"', 'id = "T-2"')
                              .replace('section = "Now"', 'section = "Needs decision"'))
            fixture.git('add', '.')
            fixture.git('commit', '-qm', 'two questions')
            baseline = fixture.git('rev-parse', 'HEAD')
            runner = fixture.runner
            runner.snapshot = task_snapshot.capture(fixture.repo, engine_observation=None, generation=2)
            runner.service, runner.mode = 'running', 'service'
            runner.questions = [fleet_view.Question(t, 'decision', 1, 'Choose a local direction. ' * 20,
                                                     kind='decision') for t in ('T-1', 'T-2')]
            envelope = fleet_view.FleetSnapshot((runner,), (runner.snapshot,), 2, time.time())
            command = str(Path(__file__).resolve().parents[2] / 'bin/autowork')
            calls = []
            def run(argv, **kwargs):
                assert argv[:2] == [command, 'tasks'] and argv[2] in ('show', 'decide', 'commit'), argv
                # The tasks screen may only read the pending-edit state; a commit is a question later.
                assert argv[2] != 'commit' or '--dry-run' in argv, argv
                calls.append(argv)
                return subprocess.run(argv, **kwargs)
            app = tui.FleetApp(command=command, script='unused', state_root=fixture.repo, env_dir=fixture.repo,
                               runner_cmd=run)
            with patch.object(fleet_view, 'collect_for_tui', return_value=envelope), \
                 patch.object(fleet_view, 'logs', return_value='fixture log'):
                async with run_pilot(app, size=size) as pilot:
                    await settle(app, pilot)
                    if case == 'answers':
                        await pilot.press('a', 'e', 'b', 'g')
                        await pilot.pause()
                        assert len(app.screen_stack) == 1, 'Removed fleet shortcuts must be inert'
                        await pilot.press('t')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen)
                        await pilot.press('6', 'e')
                        await settle(app, pilot)
                        screen = app.screen
                        assert isinstance(screen, tui.DecisionScreen) and screen.task_id == 'T-2'
                        assert screen.ready
                        assert screen.query_one('#decision-section', Select).value == 'Now', \
                            'A task in Needs decision must default to moving back to Now'
                        visible(screen.query_one('#decision-text', TextArea), screen)
                        visible(screen.query_one('#decision-save', Button), screen)
                        visible(screen.query_one('#decision-cancel', Button), screen)
                        visible(screen.query_one('#decision-status'), screen)
                        screen.query_one('#decision-text', TextArea).load_text('Use the bounded offline option')
                        await pilot.press('ctrl+s')
                        await app.workers.wait_for_complete()
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), 'Save must return to the owning Tasks screen'
                        assert 'Use the bounded offline option' in second.read_text()
                        assert 'section = "Now"' in second.read_text(), \
                            'Answering a Needs decision task must move it out of that section'
                        assert fixture.git('rev-parse', 'HEAD') != baseline
                        committed = fixture.git('show', 'HEAD:tasks/items/T-2.md')
                        assert 'Use the bounded offline option' in committed and 'section = "Now"' in committed
                        assert '--commit' in next(c for c in reversed(calls) if c[2] == 'decide')
                        assert 'live = "authorized"' not in second.read_text()
                        # CLI/local edits still have an explicit, revision-bound review path.
                        subprocess.run([command, 'tasks', 'decide', 'T-2',
                                        'Use the bounded offline option; follow-up', str(fixture.repo)],
                                       check=True, capture_output=True, text=True)
                        app.screen.refresh_tasks()
                        app.screen.read_pending()
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), type(app.screen).__name__
                        pending = app.screen.query_one('#task-pending', tui.Static)
                        assert pending.display and 'not committed' in pending.render().plain, pending.render().plain
                        await pilot.press('C')
                        await settle(app, pilot)
                        editor = app.screen
                        assert isinstance(editor, tui.CommitEdits), type(editor).__name__
                        visible(editor.query_one('#commit-message'), editor)
                        assert editor.query_one('#commit-message').value == 'tasks: record owner answers'
                        assert 'Use the bounded offline option' in editor.query_one('#commit-diff', TextArea).text
                        shown_revision = editor.revision
                        assert len(shown_revision) == 64
                        # A refresh behind the modal must not silently accept a newer snapshot.
                        task_screen = app.screen_stack[-2]
                        task_screen.pending_snapshot = {'pending_revision': 'b' * 64, 'diff': 'newer edits'}
                        with patch.object(app, 'execute') as execute:
                            await pilot.click('#commit-save')
                            await pilot.pause()
                            argv = execute.call_args.args[0].argv
                            assert argv[argv.index('--expect-pending') + 1] == shown_revision
                        assert isinstance(app.screen, tui.TasksScreen)
                        task_screen.pending_snapshot = {}
                        with patch.object(app, 'notify') as notify:
                            task_screen.action_commit_tasks()
                            assert isinstance(app.screen, tui.TasksScreen)
                            assert notify.called, 'A legacy backend must not allow an unprotected commit'
                        await pilot.press('escape')
                        await settle(app, pilot)
                        assert len(app.screen_stack) == 1, 'back on the fleet before the picker check'
                        await pilot.press('a', 'e', 'b', 'g')
                        await pilot.pause()
                        assert len(app.screen_stack) == 1, 'No duplicate task entry shortcuts'
                        app.view_only = True
                        before = len(calls)
                        await pilot.press('a', 'e')
                        assert len(app.screen_stack) == 1 and len(calls) == before
                    elif case == 'dialogs':
                        for screen, accept, cancel in ((tui.NewTask([('G', 'Goal')]), '#add', '#cancel'),
                                                       (tui.PortalSetup(), '#portal-preview', '#portal-cancel')):
                            await app.push_screen(screen)
                            await pilot.pause()
                            visible(screen.query_one(accept), screen)
                            visible(screen.query_one(cancel), screen)
                            await pilot.click(cancel)
                            assert len(app.screen_stack) == 1, (type(screen).__name__, screen.query_one(cancel).region)
                        created = []
                        await app.push_screen(tui.NewTask([]), created.append)
                        await pilot.pause()
                        for key, value in {'title': 'Independent fix', 'scope': 'Bounded change',
                                           'acceptance': 'Works', 'checks': 'python3 -c "assert \'a  b\' != \'a b\'"'}.items():
                            app.screen.query_one(f'#{key}', Input).value = value
                        await pilot.click('#add')
                        await pilot.pause()
                        assert created and created[0]['goal'] is None, (
                            created, type(app.screen).__name__,
                            {key: app.screen.query_one(f'#{key}', Input).value for key in
                             ('title', 'scope', 'acceptance', 'checks')} if not created else {})
                        assert created[0]['checks'] == 'python3 -c "assert \'a  b\' != \'a b\'"'
                        assert created[0]['touches'] == ''
                        decisions = []
                        await app.push_screen(tui.Confirm('\n'.join(f'Consent detail {i}' for i in range(80))), decisions.append)
                        await pilot.pause()
                        screen = app.screen
                        visible(screen.query_one('#yes'), screen)
                        visible(screen.query_one('#no'), screen)
                        body = screen.query_one('#confirm-body')
                        body.focus()
                        await pilot.press('end')
                        await pilot.pause()
                        assert body.scroll_y == body.max_scroll_y > 0, 'All consent details must be reachable'
                        await pilot.click('#no')
                        assert decisions == [False] and not calls
                    elif case == 'blockers':
                        # The report lists every recorded question. Before this route it offered
                        # no way to answer them, so an owner reading it was stuck.
                        await pilot.press('t')
                        await settle(app, pilot)
                        task_screen = app.screen
                        bar = task_screen.query_one('#menubar', tui.MenuBar)
                        for y in range(bar.content_size.height):
                            line = bar.render_line(y).text
                            if 'Report' in line:
                                await pilot.click('#menubar', offset=(
                                    line.index('Report') + bar.styles.padding.left, y))
                                break
                        else:
                            raise AssertionError('Report must be visible and clickable in Tasks')
                        await app.workers.wait_for_complete()
                        await settle(app, pilot)
                        screen = app.screen
                        assert isinstance(screen, tui.BlockersScreen), type(screen).__name__
                        visible(screen.query_one('#answer-report', Button), screen)
                        await pilot.press('a')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), type(app.screen).__name__
                        assert app.screen is task_screen and len(app.screen_stack) == 2, \
                            'Report Answer must reuse its Tasks screen, not nest another one'
                        assert app.screen.view == 'decisions', app.screen.view
                        # Reading the pending-edit state is allowed; changing anything is not.
                        assert not [c for c in calls if c[2] != 'commit' or '--dry-run' not in c], \
                            'opening the decision form must not execute a command'
                        await pilot.press('escape')
                        app.view_only = True
                        await pilot.press('t')
                        await settle(app, pilot)
                        await pilot.press('B')
                        await app.workers.wait_for_complete()
                        await settle(app, pilot)
                        await pilot.press('a')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), 'view only still navigates'
                        assert not [c for c in calls if c[2] != 'commit' or '--dry-run' not in c], \
                            'view only must not execute a command'
                        # A same-name replacement must not route a frozen report to another repo.
                        task_screen = app.screen
                        await pilot.press('B')
                        await settle(app, pilot)
                        report_screen = app.screen
                        app.runners = [replace(runner, repo=str(fixture.repo / 'replacement'))]
                        app.view_only = False
                        before = len(calls)
                        with patch.object(app, 'notify') as notify:
                            await pilot.press('a')
                            await settle(app, pilot)
                            assert app.screen is report_screen and len(app.screen_stack) == 3
                            assert notify.called
                        await pilot.press('escape')
                        await settle(app, pilot)
                        assert app.screen is task_screen and task_screen.runner() is None
                        await pilot.press('e', 'B')
                        await settle(app, pilot)
                        assert app.screen is task_screen and len(calls) == before
                    elif case == 'menus':
                        # Mouse mode is opt-in in the real terminal; its advertised menu
                        # must route to the same screen/confirmation as the keyboard.
                        bar = app.query_one('#menubar', tui.MenuBar)
                        for label, expected in [('Log', tui.LogScreen), ('Stop', tui.Confirm),
                                                ('Tasks', tui.TasksScreen)]:
                            text = bar.render().plain
                            shown_label = 'More' if label == 'Stop' and size[1] < 22 else label
                            # Find its rendered cell after wrapping, rather than assume
                            # every action fits on the first line.
                            position = None
                            for y in range(bar.content_size.height):
                                line = bar.render_line(y).text
                                if shown_label in line:
                                    position = (line.index(shown_label) + bar.styles.padding.left, y + bar.styles.padding.top)
                                    break
                            assert position is not None, (label, text, bar.region)
                            await pilot.click('#menubar', offset=position)
                            await pilot.pause()
                            if shown_label == 'More':
                                assert isinstance(app.screen, tui.ActionMenu)
                                app.screen.query_one('#action-filter', Input).value = label
                                await pilot.pause()
                                await pilot.press('enter')
                                await pilot.pause()
                            assert isinstance(app.screen, expected), (label, type(app.screen).__name__)
                            await pilot.press('escape')
                        assert all(c[2] == 'commit' and '--dry-run' in c for c in calls), \
                            'Opening screens/declining may only read pending edits'
            print('PASS', case, size)
        finally:
            fixture.doCleanups()


async def play_pilot():
    from pi_autowork import command, tui
    fixture = test_task_history.TaskHistoryTests()
    fixture.setUp()
    try:
        fixture.git('branch', '-M', 'main')
        fixture.git('checkout', '-q', '--detach')
        before = fixture.git('show-ref', '--heads'), fixture.git('rev-parse', 'HEAD')
        calls, installs = [], []
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as runtime:
            paths = dict(env_dir=runtime, state_root=runtime, unit=Path(runtime) / 'unit', systemctl='unused')
            def effects(argv, **kwargs):
                if argv[0] == 'git':
                    return real_run(argv, **kwargs)
                assert argv == ['bash', 'fixture-installer', '--install-service', '--repo', str(fixture.repo)], argv
                installs.append(argv)
                return subprocess.CompletedProcess(argv, 0)
            def run(argv, **kwargs):
                assert argv == ['fixture-autowork', 'start', str(fixture.repo)], argv
                assert kwargs['env']['PI_AUTOWORK_PRIMARY'] == 'fixture/model'
                assert kwargs['env']['PI_AUTOWORK_NO_FALLBACK'] == '1'
                calls.append(argv)
                with patch.object(command, 'systemctl', return_value=subprocess.CompletedProcess([], 1)), \
                     patch.object(command, 'package_script', return_value='fixture-installer'), \
                     patch.object(command.subprocess, 'run', side_effect=effects):
                    code = command.cmd_start(argparse.Namespace(target=str(fixture.repo)), paths)
                return subprocess.CompletedProcess(argv, code, '', '')
            app = tui.FleetApp(command='fixture-autowork', script='unused', state_root=runtime, env_dir=runtime,
                               browse_root=str(fixture.repo), runner_cmd=run)
            app.new_model = 'fixture/model'
            envelope = fleet_view.FleetSnapshot((), (), 1, time.time())
            with patch.object(fleet_view, 'collect_for_tui', return_value=envelope), \
                 patch.dict(os.environ, PI_AUTOWORK_STATE_DIR=runtime):
                async with run_pilot(app, size=(80, 24)) as pilot:
                    await settle(app, pilot)
                    app.action_browse()
                    await settle(app, pilot)
                    browser = app.screen
                    browser.show_repository(fixture.repo)
                    await settle(app, pilot)
                    assert browser.chosen.start_branch == 'main' and not browser.chosen.ready
                    assert fixture.git('show-ref', '--heads') == before[0]
                    app.view_only = True
                    await pilot.press('p')
                    await settle(app, pilot)
                    assert app.screen is browser and not calls
                    app.view_only = False
                    await pilot.press('p')
                    await settle(app, pilot)
                    assert isinstance(app.screen, tui.Confirm), type(app.screen)
                    assert 'switch' in app.screen.question and 'local main' in app.screen.question
                    await pilot.press('n')
                    await settle(app, pilot)
                    assert app.screen is browser and not calls
                    # Selection changed while confirmation was open: do not reselect or start it.
                    await pilot.press('p')
                    await settle(app, pilot)
                    browser.chosen_path = runtime
                    await pilot.press('y')
                    await settle(app, pilot)
                    assert app.screen is browser and not calls
                    browser.show_repository(fixture.repo)
                    await settle(app, pilot)
                    assert fixture.git('show-ref', '--heads') == before[0]
                    assert fixture.git('rev-parse', 'HEAD') == before[1]
                    assert real_run(['git', '-C', str(fixture.repo), 'symbolic-ref', '-q', 'HEAD']).returncode == 1
                    await pilot.press('p')
                    await settle(app, pilot)
                    await pilot.press('y')
                    await settle(app, pilot)
                    for worker in list(app.workers):
                        if worker.group == 'actions':
                            await worker.wait()
                    await settle(app, pilot)
                    assert len(calls) == len(installs) == 1, (calls, installs)
                    assert fixture.git('symbolic-ref', '--short', 'HEAD') == 'main'
                    assert fixture.git('show-ref', '--heads') == before[0]
        print('PASS play: composed Browse confirmation -> cmd_start, no live service')
    finally:
        fixture.doCleanups()


class TuiControlsTests(unittest.TestCase):
    def run_case(self, case):
        if not shutil.which('uv'):
            if case == 'play':
                self.fail('Play acceptance requires uv and the pinned Textual cache')
            self.skipTest('uv is needed for pinned Textual')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
                                 'python', __file__, '--pilot', case], capture_output=True, text=True, timeout=90)
        if textual_unavailable(result) and case != 'play':
            self.skipTest('textual==8.2.8 is not in the offline cache')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_answer_mnemonic_portable_save_and_small_screen(self):
        self.run_case('answers')

    def test_compact_forms_and_long_confirmations_keep_controls_visible(self):
        self.run_case('dialogs')

    def test_fleet_menu_clicks_match_keyboard_without_running_commands(self):
        self.run_case('menus')

    def test_the_blockers_report_routes_to_the_decision_form(self):
        self.run_case('blockers')

    def test_play_routes_safe_branch_switch(self):
        self.run_case('play')


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        asyncio.run(play_pilot() if sys.argv[-1] == 'play' else controls_pilot(sys.argv[-1]))
    else:
        unittest.main()
