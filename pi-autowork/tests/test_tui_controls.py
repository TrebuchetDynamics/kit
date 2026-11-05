"""Keyboard, click and compact-dialog contracts; no live services or devices."""
import asyncio
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from offline_textual import textual_unavailable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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
    from textual.widgets import Button, OptionList, Select, TextArea

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
            command = str(Path(__file__).resolve().parents[1] / 'bin/autowork')
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
                        await pilot.press('a')
                        await pilot.pause()
                        assert isinstance(app.screen, tui.QuestionPicker), 'Advertised Answer mnemonic must open the picker'
                        options = app.screen.query_one(OptionList)
                        visible(options, app.screen)
                        await pilot.press('end', 'enter')
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
                        assert len(app.screen_stack) == 1, 'Portable Save shortcut must complete the answer'
                        assert 'Use the bounded offline option' in second.read_text()
                        assert 'section = "Now"' in second.read_text(), \
                            'Answering a Needs decision task must move it out of that section'
                        assert fixture.git('rev-parse', 'HEAD') == baseline
                        assert 'live = "authorized"' not in second.read_text()
                        # An answer is an uncommitted record edit: the runner cannot read it yet,
                        # so the pipeline has to name that step instead of dismissing silently.
                        await pilot.press('t')
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
                        await pilot.press('escape')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen)
                        await pilot.press('escape')
                        await settle(app, pilot)
                        assert len(app.screen_stack) == 1, 'back on the fleet before the picker check'
                        await pilot.press('e')
                        assert isinstance(app.screen, tui.QuestionPicker), 'Keep the previous Answer key working'
                        await pilot.press('escape')
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
                        await pilot.press('b')
                        await app.workers.wait_for_complete()
                        await settle(app, pilot)
                        screen = app.screen
                        assert isinstance(screen, tui.BlockersScreen), type(screen).__name__
                        visible(screen.query_one('#answer-report', Button), screen)
                        await pilot.press('a')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), type(app.screen).__name__
                        assert app.screen.view == 'decisions', app.screen.view
                        # Reading the pending-edit state is allowed; changing anything is not.
                        assert not [c for c in calls if c[2] != 'commit' or '--dry-run' not in c], \
                            'opening the decision form must not execute a command'
                        await pilot.press('escape')
                        app.view_only = True
                        await pilot.press('b')
                        await app.workers.wait_for_complete()
                        await settle(app, pilot)
                        await pilot.press('a')
                        await settle(app, pilot)
                        assert isinstance(app.screen, tui.TasksScreen), 'view only still navigates'
                        assert not [c for c in calls if c[2] != 'commit' or '--dry-run' not in c], \
                            'view only must not execute a command'
                    elif case == 'menus':
                        # Mouse mode is opt-in in the real terminal; its advertised menu
                        # must route to the same screen/confirmation as the keyboard.
                        bar = app.query_one('#menubar', tui.MenuBar)
                        for label, expected in [('Log', tui.LogScreen), ('Stop', tui.Confirm),
                                                ('Answer', tui.QuestionPicker)]:
                            text = bar.render().plain
                            # Find its rendered cell after wrapping, rather than assume
                            # every action fits on the first line.
                            position = None
                            for y in range(bar.content_size.height):
                                line = bar.render_line(y).text
                                if label in line:
                                    position = (line.index(label) + bar.styles.padding.left, y + bar.styles.padding.top)
                                    break
                            assert position is not None, (label, text, bar.region)
                            await pilot.click('#menubar', offset=position)
                            await pilot.pause()
                            assert isinstance(app.screen, expected), (label, type(app.screen).__name__)
                            await pilot.press('escape')
                        assert not calls, 'Opening screens/declining must not execute control commands'
            print('PASS', case, size)
        finally:
            fixture.doCleanups()


class TuiControlsTests(unittest.TestCase):
    def run_case(self, case):
        if not shutil.which('uv'):
            self.skipTest('uv is needed for pinned Textual')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
                                 'python', __file__, '--pilot', case], capture_output=True, text=True, timeout=90)
        if textual_unavailable(result):
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


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        asyncio.run(controls_pilot(sys.argv[-1]))
    else:
        unittest.main()
