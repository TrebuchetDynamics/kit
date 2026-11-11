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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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
        bar.show([('t', 'Tasks'), ('?', 'More actions')], explicit_keys=True)
        assert '[t] Tasks' in update.call_args.args[0].plain
        assert '[?] More actions' in update.call_args.args[0].plain


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
        assert [str(lanes.get_row_at(i)[0]) for i in range(10)] == [runner.lanes[0].task] * 10
        import json
        assert [json.loads(key.value) for key in lanes.rows] == [
            [runner.name, runner.repo, lane.task, lane.attempt] for lane in runner.lanes]
        # Snapshot acquisition remains independent of presentation deduplication.
        with patch.object(fleet_view, 'collect_for_tui', side_effect=AssertionError('redraw recollected')):
            app.show_detail()
            await pilot.pause()


def option_text(options):
    return '\n'.join(str(options.get_option_at_index(i).prompt) for i in range(options.option_count))


async def reading_surfaces_pilot():
    from pi_autowork import tui, planning_ui
    from textual.widgets import Button
    from pi_autowork.tui_common import ViewHeader
    for size in ((60, 18), (140, 40)):
        async with fixture_app(size) as (app, pilot):
            runner = app.current()
            with patch.object(fleet_view, 'action_log', return_value=[]), \
                 patch.object(app, 'request_blockers'), \
                 patch.object(planning_ui.PlanScreen, '_load_project'), \
                 patch.object(planning_ui.PlanScreen, 'poll_turn'):
                cases = [
                    (lambda: tui.LogScreen(runner, lambda *_: 'sample event'), '#full-log'),
                    (lambda: tui.WorkerScreen(runner, 'TASK-1'), '#worker-actions'),
                    (lambda: tui.BrowseScreen(runner.repo, lambda _: None), '#tree'),
                    (lambda: tui.BlockersScreen(runner), '#blockers-text'),
                    (lambda: planning_ui.PlanScreen(runner.repo), '#plan-controls'),
                ]
                for factory, content in cases:
                    screen = factory()
                    await app.push_screen(screen)
                    await settle(app, pilot)
                    header = screen.query_one(ViewHeader)
                    assert header.region.height >= 1 and header.region.bottom <= size[1], (type(screen).__name__, header.region)
                    region = screen.query_one(content).region
                    assert region.height >= 2 and region.bottom <= size[1], (type(screen).__name__, size, region)
                    for button in screen.query(Button):
                        assert button.region.right <= size[0] and button.region.bottom <= size[1], (type(screen).__name__, button.id, button.region)
                    app.pop_screen()
                    await pilot.pause()


async def task_workspace_pilot():
    from types import SimpleNamespace
    from pi_autowork import tui, tui_tasks
    from textual.widgets import DataTable
    rows = (task_snapshot.TaskRow('TASK-1', 'Short label', 'Now', 'Blocker · No result', 'held',
                                 'No result · Agent repair', bucket='Blocker'),)
    record = SimpleNamespace(title='A full descriptive task title that is not shortened in the reading panel',
                             scope='Implement the requested outcome.', acceptance=('A meaningful check passes.',))
    async with fixture_app((180, 45)) as (app, pilot):
        runner = app.current()
        runner.snapshot = replace(runner.snapshot, rows=rows, counts=(0, 0, 0, 1, 0, 1),
                                  store=SimpleNamespace(tasks={'TASK-1': record}))
        with patch.object(tui_tasks, 'pending_edits', return_value={'files': []}), \
             patch.object(fleet_view, 'task_entry', return_value='RAW SOURCE RECORD'), \
             patch.object(fleet_view, 'recent_actions', return_value=[]):
            await app.push_screen(tui.TasksScreen(runner.name))
            await settle(app, pilot)
            screen = app.screen
            queue, selected = screen.query_one('#task-list'), screen.query_one('#task-selection')
            assert selected.region.x >= queue.region.right
            body = screen.query_one('#task-detail').render().plain
            assert record.title in body and 'What is happening' in body and 'What you can do' in body
            assert 'previous attempt ended without a usable result' in body
            owner_row = replace(rows[0], why='owner action required; perform the check outside the runner')
            assert not {'r', 'c', 'a'} & {action.key for action in screen.actions(owner_row)}
            quota_row = replace(rows[0], why='Daily free-model quota exhausted (HTTP 429)')
            happened, next_step = tui_tasks.task_guidance(quota_row)
            assert 'daily free-model quota' in happened and 'Retry only after that' in next_step
            # The list's Why column shows the row's own reason, not one generic sentence on every row.
            table = screen.query_one('#tasks', DataTable)
            labels = [str(column.label) for column in table.columns.values()]
            listed = [str(cell) for cell in table.get_column_at(labels.index('Why'))]
            assert any(rows[0].why[:12] in cell for cell in listed), (rows[0].why, listed)
            await pilot.press('space')
            assert app.focused is selected
            await pilot.resize_terminal(60, 18)
            await pilot.pause()
            assert selected.region.bottom <= 18 and queue.region.width >= 58, (queue.region, selected.region)
            screen.query_one('#tasks', DataTable).focus()
            await pilot.press('enter')
            await settle(app, pilot)
            assert isinstance(app.screen, tui.TaskScreen)
            text = app.screen.query_one('#task-body').render().plain
            assert 'Work requested' in text and record.scope in text
            assert 'RAW SOURCE RECORD' not in text
            await pilot.press('i')
            await pilot.pause()
            assert 'RAW SOURCE RECORD' in app.screen.query_one('#task-body').render().plain
            await pilot.press('i')
            assert 'RAW SOURCE RECORD' not in app.screen.query_one('#task-body').render().plain


async def details_layout_pilot():
    async with fixture_app((180, 45)) as (app, pilot):
        await pilot.press('i')
        await pilot.pause()
        pane = app.query_one('#detail-scroll')
        sidebar = app.query_one('#project-context')
        assert pane.region.x >= sidebar.region.right, (pane.region, sidebar.region)
        assert pane.region.width > 100, pane.region
        assert pane.region.height > 25, pane.region
        assert not app.query_one('#log').display and not app.query_one('#lanes').display
        for _ in range(3):
            app.render_fleet()
        await pilot.pause()
        assert pane.display and pane.region.width > 100
        await pilot.resize_terminal(60, 18)
        await pilot.pause()
        assert pane.region.width >= 58 and pane.region.bottom <= 18, pane.region
        assert not app.query_one('#overview').display
        await pilot.press('3')
        await pilot.pause()
        assert not pane.display and app.query_one('#log').display
        assert app.focused.id == 'log'


async def progress_pilot():
    from textual.widgets import Static
    async with fixture_app((150, 40)) as (app, pilot):
        runner = app.current()
        runner.snapshot = replace(runner.snapshot, counts=(1, 0, 1, 1, 0, 3),
                                  joined_lanes=(('FIX-1-abcdef12', 1, 'running'),))
        runner.lanes[0].activity = 'Reading source'
        runner.lanes[0].activity_age = 20
        app.show_detail()
        await pilot.pause()
        summary = app.query_one('#overview', Static).render().plain
        assert 'Now: Working' in summary and 'Reading source' in summary, summary
        assert 'none for active work' in summary and 'other tasks need attention' in summary, summary
        assert 'automatic push disabled' in summary, summary
        runner.lanes[0].activity_age = 600
        app.show_detail()
        summary = app.query_one('#overview', Static).render().plain
        assert 'Quiet worker' in summary and 'progress not confirmed' in summary, summary
        runner.push = True
        app.show_detail()
        assert 'automatic push enabled' in app.query_one('#overview', Static).render().plain


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
        assert 'Running services continue in the background' in labels, labels
        assert 'does not retry failed tasks' in labels, labels
        assert '[t] Tasks' in labels, labels
        for label in ('Log', 'Tasks', 'Stop', 'Restart', 'Details', 'Browse', 'Quit'):
            assert label in labels, (label, labels)
        for label in ('Answer', 'Plan', 'Blockers'):
            assert label not in labels, (label, labels)
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
        # Tasks is the only task-management entry from the fleet, including Ctrl+P.
        commands = {item.title for item in app.get_system_commands(app.screen)}
        assert 'Open task inventory' in commands
        assert not {'Plan work', 'Inspect blockers', 'Answer owner question'} & commands
        await pilot.press('a', 'e', 'b', 'g')
        await pilot.pause()
        assert len(app.screen_stack) == 1
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
        assert options.option_count == 4, labels
        for label in ('Log', 'Tasks', 'Details', 'Quit'):
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
                assert sum(c.get_render_width(table) for c in table.columns.values()) <= table.region.width - 2
            log = app.query_one('#log')
            assert log.region.height >= 4 and log.region.bottom <= height, log.region
            footer = app.query_one('#nav-footer')
            assert footer.region.height == 1 and footer.region.bottom <= height
            for key, target in [('1', 'runners'), ('2', 'lanes'), ('3', 'log')]:
                await pilot.press(key)
                await pilot.pause()
                assert app.focused.id == target, (key, app.focused)
            if width >= 130 and height >= 26:
                assert log.region.x >= app.query_one('#runners').region.right
            else:
                assert log.region.y >= app.query_one('#runners').region.bottom

            bar = app.query_one('#menubar')
            painted = '\n'.join(bar.render_line(y).text for y in range(bar.content_size.height))
            assert 'More' in painted and '?' in painted, (width, height, painted)
            assert bar.region.bottom <= height
            if height < 22:
                assert app.query_one('#overview').region.height <= 3
            if height < 22 or width < 80:
                assert 'Details' in painted and 'Tasks' in painted
                assert 'Browse' not in painted and 'Quit' not in painted  # secondary routes live in More
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
        assert '1 errors' in painted and '0 notes' in painted and 'Main:' in painted, painted
        await pilot.press('m')
        await settle(app, pilot)
        from textual.widgets import Input
        field = app.screen.query_one('#filter', Input)
        field.focus()
        await pilot.press('h', '1', '2', '3')
        await pilot.pause()
        assert field.value == 'h123' and app.focused is field
        await pilot.press('escape')
        await pilot.press('h')
        await pilot.pause()
        from pi_autowork.tui import WorkflowGuide
        assert isinstance(app.screen, WorkflowGuide)
        await pilot.press('escape')
        assert len(app.screen_stack) == 1


async def mixed_freshness_pilot():
    from textual.widgets import DataTable
    async with fixture_app((150, 40)) as (app, pilot):
        runner = app.current()
        for counts, fresh_label in (((1, 0, 0, 0, 0, 1), 'In progress'),
                                    ((0, 1, 0, 0, 0, 1), 'Ready to merge')):
            for freshness in ('fresh', 'stale'):
                runner.snapshot = replace(runner.snapshot, counts=counts,
                                          freshness=freshness, engine_freshness='fresh')
                app.render_fleet()
                await pilot.pause()
                label = str(app.query_one('#runners', DataTable).get_row_at(0)[1])
                summary = app.query_one('#overview').render().plain
                assert label == (fresh_label if freshness == 'fresh' else 'Unconfirmed'), (label, summary)
                assert f'fixture · {label}' in summary, summary
                assert f'1 open · {counts[0]} in progress · {counts[1]} ready to merge' in summary, summary
                if freshness == 'stale':
                    assert 'Now: Unconfirmed' in summary and 'Last observed:' in summary, summary
                    assert 'Inventory stale · execution fresh' in summary, summary
                    await pilot.resize_terminal(60, 18)
                    await pilot.pause()
                    compact = app.query_one('#overview').render().plain
                    assert 'fixture · Unconfirmed' in compact and 'Inventory stale' in compact, compact
                    await pilot.resize_terminal(150, 40)


async def execution_copy_pilot():
    from textual.widgets import DataTable
    async with fixture_app((80, 24)) as (app, pilot):
        runner = app.current()
        runner.state = 'working'  # Service maintenance is not task execution.
        runner.snapshot = replace(runner.snapshot, counts=(0, 0, 0, 1, 0, 1))
        app.render_fleet()
        await pilot.pause()
        assert str(app.query_one('#runners', DataTable).get_row_at(0)[1]) == 'Needs attention'
        shown = str(app.query_one('#overview').render())
        assert 'service running' in shown and '0 in progress' in shown, shown
        assert 'Working' not in shown, shown
        for state, refusal, expected in (
                ('running', 'Live authorization denied [fixture]', 'Needs attention'),
                ('running', '', 'Waiting'), ('paused', '', 'Paused'),
                ('not running', '', 'Not running'), ('running', '', 'Unavailable')):
            runner.state, runner.stop_reason = state, refusal
            runner.snapshot = replace(runner.snapshot, counts=None if expected == 'Unavailable' else (0, 0, 0, 0, 0, 0))
            for size in ((150, 40), (60, 18)):
                await pilot.resize_terminal(*size)
                app.render_fleet()
                await pilot.pause()
                label = str(app.query_one('#runners', DataTable).get_row_at(0)[1])
                shown = app.query_one('#overview').render().plain
                assert label == expected and f'fixture · {expected}' in shown, (label, shown)
                if refusal:
                    assert refusal in shown and 'Waiting' not in shown, shown
                    assert ('service running' if size[1] >= 22 else 'Why:') in shown, shown


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


async def palette_pilot():
    from pi_autowork import tui
    from textual.command import CommandList, CommandPalette
    from textual.widgets import Input
    async with fixture_app((80, 24)) as (app, pilot):
        titles = {command.title for command in app.get_system_commands(app.screen)}
        assert {'Refresh Autowork fleet', 'Search fleet actions', 'Choose provider and model',
                'Browse repositories', 'Open activity log', 'Open task inventory'} <= titles, titles
        await pilot.press('ctrl+p')
        await pilot.pause()
        assert isinstance(app.screen, CommandPalette), type(app.screen).__name__
        command_list = app.screen.query_one(CommandList)
        await pilot.pause(0.5)
        discovered = [str(command_list.get_option_at_index(i).prompt)
                      for i in range(command_list.option_count)]
        assert any('Choose provider and model' in result for result in discovered), discovered
        search = app.screen.query_one(Input)
        search.value = 'choose provider and model'
        await pilot.pause(0.5)
        results = [str(command_list.get_option_at_index(i).prompt)
                   for i in range(command_list.option_count)]
        assert results and any('Choose provider and model' in result for result in results), results
        await pilot.press('enter')
        await settle(app, pilot)
        assert isinstance(app.screen, tui.PickModel), type(app.screen).__name__
        model_commands = {command.title for command in app.get_system_commands(app.screen)}
        assert {'Configure Pi provider', 'Refresh Pi models'} <= model_commands, model_commands
        await pilot.press('escape')
        app.view_only = True
        read_only = {command.title for command in app.get_system_commands(app.screen)}
        assert 'Browse repositories' not in read_only and 'Choose provider and model' not in read_only


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

    def test_service_activity_does_not_claim_task_progress(self):
        self.run_case('execution')

    def test_progress_requires_fresh_inventory_and_qualifies_retained_counts(self):
        self.run_case('freshness')

    def test_empty_fleet_has_responsive_guided_welcome(self):
        self.run_case('welcome')

    def test_reading_surfaces_have_orientation_and_reachable_controls(self):
        self.run_case('surfaces')

    def test_tasks_explain_selected_work_and_disclose_raw_record(self):
        self.run_case('tasks')

    def test_details_use_readable_workspace_and_survive_refresh(self):
        self.run_case('details')

    def test_progress_card_separates_activity_intervention_and_publication(self):
        self.run_case('progress')

    def test_command_palette_exposes_contextual_autowork_actions(self):
        self.run_case('palette')


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        case = sys.argv[-1]
        if case == 'publisher':
            publisher_contract()
        else:
            asyncio.run({'redraw': redraw_pilot, 'menu': menu_pilot,
                         'layout': layout_pilot, 'welcome': welcome_pilot, 'progress': progress_pilot, 'details': details_layout_pilot, 'tasks': task_workspace_pilot, 'surfaces': reading_surfaces_pilot,
                         'palette': palette_pilot, 'execution': execution_copy_pilot,
                         'freshness': mixed_freshness_pilot}[case]())
    else:
        unittest.main()
