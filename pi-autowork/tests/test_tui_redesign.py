"""Fleet presentation and More-menu regressions; fixture readers, no live commands."""
import asyncio
from contextlib import ExitStack, asynccontextmanager
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import fleet_view, task_snapshot
from test_tui_layout import run_pilot, settle
from offline_textual import textual_unavailable


@asynccontextmanager
async def fixture_app(size, *, view_only=False):
    from pi_autowork import tui
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        snap = task_snapshot.TaskSnapshot(str(root), str(root / '.git'), 'a' * 40,
            1, time.time(), counts=(1, 0, 0, 0, 0, 1), freshness='fresh',
            engine_freshness='fresh', pending_paths=())
        runner = fleet_view.Runner('fixture', repo=str(root), state_dir=str(root / 'state'),
            service='running', mode='service', state='running', model='fixture/alpha',
            snapshot=snap, lanes=[fleet_view.Lane('FIX-1-abcdef12', 'running')])
        snapshot = fleet_view.FleetSnapshot((runner,), (snap,), 1, time.time())
        command = Mock(side_effect=AssertionError('Presentation must not execute commands'))
        app = tui.FleetApp(command='fixture', script='fixture', state_root=root,
            env_dir=root, runner_cmd=command, view_only=view_only,
            list_models=lambda: ['fixture/alpha', 'fixture/beta'])
        with patch.object(fleet_view, 'collect_for_tui', return_value=snapshot), \
             patch.object(fleet_view, 'logs', return_value='[12:00] fixture journal'), \
             patch.object(fleet_view, 'readiness', return_value=fleet_view.Readiness(str(root))):
            async with run_pilot(app, size=size) as pilot:
                await settle(app, pilot)
                yield app, pilot
                command.assert_not_called()


def publisher_contract():
    from pi_autowork import tui
    from rich.text import Text
    widget = Mock()
    original = Text('same words', style='red')
    original.stylize('bold', 0, 4)
    tui.publish_text(widget, original)
    assert widget.update.call_count == 1
    tui.publish_text(widget, original.copy())
    assert widget.update.call_count == 1, 'Equivalent rich text must not invalidate the widget'
    # The retained comparison value must not alias the caller's mutable Text.
    original.append(' caller mutation')
    unchanged = Text('same words', style='red')
    unchanged.stylize('bold', 0, 4)
    tui.publish_text(widget, unchanged)
    assert widget.update.call_count == 1, 'Publisher must retain a detached copy'
    styled = unchanged.copy()
    styled.style = 'green'
    tui.publish_text(widget, styled)
    assert widget.update.call_count == 2, 'Base-style changes must repaint identical characters'
    styled.stylize('underline', 5, 10)
    tui.publish_text(widget, styled)
    assert widget.update.call_count == 3, 'Span changes must repaint identical characters'
    for attribute, value in (('justify', 'right'), ('overflow', 'crop'),
                             ('no_wrap', True), ('end', ''), ('tab_size', 4)):
        before = widget.update.call_count
        setattr(styled, attribute, value)
        tui.publish_text(widget, styled)
        assert widget.update.call_count == before + 1, f'{attribute} affects rendering'
        tui.publish_text(widget, styled.copy())
        assert widget.update.call_count == before + 1
    bar = tui.MenuBar()
    with patch.object(bar, 'update') as update:
        bar.show([('l', 'Log')])
        bar.show([('l', 'Log')])
        assert update.call_count == 1, 'MenuBar must use the same rich-text publisher'
        bar.show([('l', 'Log')], click_actions={'l': 'app.run("l")'})
        assert update.call_count == 2, 'Click metadata is part of the rendered value'


async def redraw_pilot():
    from pi_autowork import tui
    async with fixture_app((80, 24)) as (app, pilot):
        app.show_detail()
        await pilot.pause()
        with ExitStack() as stack:
            updates = {selector: stack.enter_context(patch.object(app.query_one(selector), 'update'))
                       for selector in ('#modelbar', '#overview', '#menubar', '#detail')}
            for _ in range(12):
                app.show_detail()
            assert {key: value.call_count for key, value in updates.items()} == dict.fromkeys(updates, 0), \
                {key: value.call_count for key, value in updates.items()}
            app.current().model = 'fixture/beta'
            app.show_detail()
            assert updates['#modelbar'].call_count == 1
            assert updates['#detail'].call_count == 1
        # Duplicate task lanes retain unique identities while formatting each activity once.
        runner = app.current()
        runner.lanes = [replace(runner.lanes[0], attempt=i + 1) for i in range(10)]
        with patch.object(tui, 'doing', return_value='fixture activity') as doing:
            app.show_lanes(runner)
            assert doing.call_count == 10, 'Activity formatting must run once per worker row'
        lanes = app.query_one('#lanes')
        expected = [f'{runner.lanes[0].task} [{i + 1}]' for i in range(10)]
        assert [str(lanes.get_row_at(i)[0]) for i in range(10)] == expected
        assert [key.value for key in lanes.rows] == expected
        # Snapshot acquisition remains independent of presentation deduplication.
        with patch.object(fleet_view, 'collect_for_tui', side_effect=AssertionError('redraw recollected')):
            app.show_detail()
            await pilot.pause()


def option_text(options):
    return '\n'.join(str(options.get_option_at_index(i).prompt) for i in range(options.option_count))


async def menu_pilot():
    from pi_autowork import tui
    from textual.widgets import Input, OptionList
    async with fixture_app((60, 18)) as (app, pilot):
        await pilot.press('?')
        await pilot.pause()
        assert isinstance(app.screen, tui.ActionMenu), type(app.screen).__name__
        menu = app.screen
        field = menu.query_one('#action-filter', Input)
        options = menu.query_one('#actions', OptionList)
        assert app.focused is field, 'More must accept search immediately'
        for widget in (field, options):
            assert widget.region.width > 0 and widget.region.height > 0, widget.region
            assert widget.region.right <= 60 and widget.region.bottom <= 18, widget.region
        labels = option_text(options)
        for label in ('Log', 'Tasks', 'Stop', 'Restart', 'Details', 'Blockers', 'Browse', 'Quit'):
            assert label in labels, (label, labels)
        field.value = 'no matching fleet action'
        await pilot.pause()
        assert options.option_count == 0
        await pilot.press('enter')
        assert app.screen is menu, 'No search match must not dispatch an action'
        await pilot.press('escape')
        assert len(app.screen_stack) == 1
        bar = app.query_one('#menubar')
        for y in range(bar.content_size.height):
            line = bar.render_line(y).text
            if 'More' in line:
                await pilot.click('#menubar', offset=(line.index('More') + bar.styles.padding.left, y))
                break
        await pilot.pause()
        assert isinstance(app.screen, tui.ActionMenu), 'The visible More label must be clickable'
        await pilot.press('escape')
        # Selecting through the OptionList follows the same route as Enter in search.
        await pilot.press('?')
        await pilot.pause()
        app.screen.query_one('#action-filter', Input).value = 'log'
        await pilot.pause()
        await pilot.press('down', 'enter')
        await settle(app, pilot)
        assert isinstance(app.screen, tui.LogScreen), type(app.screen).__name__
        await pilot.press('escape')
        # Answer is a navigation action despite sharing the available-actions list.
        with patch.object(app, 'available', return_value=[fleet_view.Action('a', 'Answer', [])]), \
             patch.object(app, 'action_answer_question') as answer:
            await pilot.press('?')
            await pilot.pause()
            app.screen.query_one('#action-filter', Input).value = 'answer'
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()
            answer.assert_called_once_with()
        # More delegates to the existing action method, including Stop's consent.
        with patch.object(app, 'execute') as execute:
            await pilot.press('?')
            await pilot.pause()
            app.screen.query_one('#action-filter', Input).value = 'sToP'
            await pilot.pause()
            assert app.screen.query_one('#actions', OptionList).option_count == 1
            await pilot.press('enter')
            await pilot.pause()
            assert isinstance(app.screen, tui.Confirm), type(app.screen).__name__
            execute.assert_not_called()
            await pilot.press('escape')
            # Same display name, different repository: a stale selection is unsafe.
            await pilot.press('?')
            await pilot.pause()
            app.screen.query_one('#action-filter', Input).value = 'stop'
            await pilot.pause()
            app.runners = [replace(app.current(), repo=str(Path(app.current().repo) / 'replacement'))]
            await pilot.press('enter')
            await pilot.pause()
            assert len(app.screen_stack) == 1, 'Changed identity must cancel the deferred runtime action'
            execute.assert_not_called()
    async with fixture_app((60, 18), view_only=True) as (app, pilot):
        await pilot.press('?')
        await pilot.pause()
        assert isinstance(app.screen, tui.ActionMenu)
        options = app.screen.query_one('#actions', OptionList)
        labels = option_text(options)
        assert options.option_count == 5, labels
        for label in ('Log', 'Tasks', 'Details', 'Blockers', 'Quit'):
            assert label in labels, labels
        for label in ('Pause', 'Play', 'Stop', 'Restart', 'Uninstall', 'Plan', 'Browse', 'Model'):
            assert label not in labels, labels
        await pilot.press('escape')
        with patch.object(app, 'execute') as execute:
            await pilot.press('p', 's', 'r', 'u', 'm', 'g', 'n', 'a')
            await pilot.pause()
            assert len(app.screen_stack) == 1
            execute.assert_not_called()


async def layout_pilot():
    from textual.widgets import DataTable
    async with fixture_app((60, 18)) as (app, pilot):
        for width, height in ((60, 18), (150, 45), (60, 24), (80, 18)):
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            for selector in ('#runners', '#lanes'):
                table = app.query_one(selector, DataTable)
                assert table.region.height >= 3, (selector, table.region)
                assert not table.show_horizontal_scrollbar, (selector, table.max_scroll_x)
                assert sum(c.get_render_width(table) for c in table.columns.values()) <= width - 2
            log = app.query_one('#log')
            assert log.region.height >= 4 and log.region.bottom <= height, log.region
            bar = app.query_one('#menubar')
            painted = '\n'.join(bar.render_line(y).text for y in range(bar.content_size.height))
            assert 'More' in painted and '?' in painted, (width, height, painted)
            assert bar.region.bottom <= height
            if height < 22:
                assert app.query_one('#overview').region.height <= 3
            if height < 22 or width < 80:
                assert 'Browse' in painted and 'Quit' in painted
                for label in ('Restart', 'Uninstall', 'Plan', 'Blockers'):
                    assert label not in painted, (width, height, painted)
        # A green main check never makes stale observations look current.
        await pilot.resize_terminal(60, 18)
        runner = app.current()
        runner.snapshot = replace(runner.snapshot, freshness='stale', engine_freshness='unknown')
        runner.main_check = {'state': 'green'}
        app.show_detail()
        await pilot.pause()
        overview = app.query_one('#overview')
        painted = '\n'.join(overview.render_line(y).text for y in range(overview.content_size.height))
        assert 'Inventory stale' in painted and 'execution unknown' in painted, painted
        assert 'Main:' in painted and overview.region.height <= 3, painted
        runner.snapshot = replace(runner.snapshot, freshness='fresh', engine_freshness='fresh')
        runner.acquisition_errors = ('fixture observation error',)
        app.show_detail()
        await pilot.pause()
        painted = '\n'.join(overview.render_line(y).text for y in range(overview.content_size.height))
        assert '1 warnings' in painted and 'Main:' in painted, painted


async def welcome_pilot():
    from pi_autowork import tui
    from textual.widgets import Static
    async with fixture_app((60, 18)) as (app, pilot):
        app.runners = []
        app.fleet_snapshot = fleet_view.FleetSnapshot((), (), 1, time.time())
        app.render_fleet()
        await pilot.pause()
        panel = app.query_one('#empty-state')
        card = app.query_one('#empty-card', Static)
        assert panel.display and card.display
        content = str(card.render())
        for expected in ('GETTING STARTED', 'Start your first runner',
                         'Choose provider and model', 'Browse for a project',
                         'checks the project before starting'):
            assert expected in content, (expected, content)
        for width, height in ((60, 18), (100, 30), (150, 45)):
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            assert panel.region.bottom <= height and panel.region.width <= width
            assert card.region.bottom <= height and card.region.right <= width
            assert not app.query_one('#runners').display and not app.query_one('#log').display
        await pilot.press('m')
        await pilot.pause()
        assert isinstance(app.screen, tui.PickModel)
        await pilot.press('escape')
        app.runners = [fleet_view.Runner('fixture', service='running', state='running')]
        app.render_fleet()
        await pilot.pause()
        assert not panel.display and app.query_one('#runners').display
    async with fixture_app((60, 18), view_only=True) as (app, pilot):
        app.runners = []
        app.fleet_snapshot = fleet_view.FleetSnapshot((), (), 1, time.time())
        app.render_fleet()
        await pilot.pause()
        content = str(app.query_one('#empty-card').render())
        assert 'READ ONLY' in content and 'no runners' in content.lower(), content
        assert 'Browse for a project' not in content and 'Choose provider' not in content
        assert app.query_one('#empty-card').region.bottom <= 18


class TuiRedesignTests(unittest.TestCase):
    def run_case(self, case):
        if not shutil.which('uv'):
            self.skipTest('uv is needed for pinned Textual')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with',
            'textual==8.2.8', 'python', __file__, '--pilot', case],
            capture_output=True, text=True, timeout=90)
        if textual_unavailable(result):
            self.skipTest('textual==8.2.8 is not in the offline cache')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rich_text_publisher_copies_and_compares_styles(self):
        self.run_case('publisher')

    def test_unchanged_redraw_has_no_static_updates(self):
        self.run_case('redraw')

    def test_more_search_cancel_confirm_identity_and_view_only(self):
        self.run_case('menu')

    def test_compact_and_wide_layout_keep_help_and_journal_visible(self):
        self.run_case('layout')

    def test_empty_fleet_has_responsive_guided_welcome(self):
        self.run_case('welcome')


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        case = sys.argv[-1]
        if case == 'publisher':
            publisher_contract()
        else:
            asyncio.run({'redraw': redraw_pilot, 'menu': menu_pilot,
                         'layout': layout_pilot, 'welcome': welcome_pilot}[case]())
    else:
        unittest.main()
