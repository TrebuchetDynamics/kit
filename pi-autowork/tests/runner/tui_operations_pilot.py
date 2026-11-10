"""Synthetic captures only: no service, model, task-store writes or host commands."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from pi_autowork import fleet_view, task_snapshot, tui
from test_tui_layout import run_pilot, settle
from textual.widgets import DataTable, Input

TITLE = 'Repair the descriptive duplicate task name without changing its identity'
IDS = ('TASK-100-aabbccdd', 'TASK-101-aabbccdd')
REASON = 'waiting for a check slot, 2 ahead'


def captured(repo):
    rows = tuple(task_snapshot.TaskRow(t, TITLE[:39] + '…', 'Now', 'Waiting · Check slot', 'working',
                                      REASON, bucket='Waiting') for t in IDS)
    lanes = [fleet_view.Lane(t, 'waiting for a check slot', attempt=1, detail='2 ahead') for t in IDS]
    snap = task_snapshot.TaskSnapshot(str(repo), str(repo / '.git'), 'a' * 40, 7, time.time(),
        store=SimpleNamespace(tasks={t: SimpleNamespace(title=TITLE) for t in IDS}),
        rows=rows, counts=(0, 0, 2, 0, 0, 2), freshness='fresh', engine_freshness='fresh',
        pending_paths=(), joined_lanes=tuple((l.task, l.attempt, l.phase) for l in lanes))
    return fleet_view.Runner('fixture', repo=str(repo), state='working', service='running', mode='service',
                             snapshot=snap, lanes=lanes, model='fixture/model')


@asynccontextmanager
async def fixture(size):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        runner = captured(root)
        envelope = fleet_view.FleetSnapshot((runner,), (runner.snapshot,), 7, time.time())
        def forbidden(*args, **kwargs):
            raise AssertionError('No external commands in operations pilot')
        app = tui.FleetApp(command='fixture', script='fixture', state_root=root, env_dir=root,
                           runner_cmd=forbidden)
        with patch.object(fleet_view, 'collect_for_tui', return_value=envelope), \
             patch.object(fleet_view.main_check, 'alive', return_value=True), \
             patch.object(fleet_view, 'logs', return_value='fixture journal'), \
             patch.object(fleet_view, 'action_log', return_value=[]), \
             patch.object(tui, 'pending_edits', return_value={}):
            async with run_pilot(app, size=size) as pilot:
                await settle(app, pilot)
                yield app, pilot, envelope


def selected_task(table):
    key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
    return json.loads(key.rstrip(':'))[2]


def painted(widget):
    return '\n'.join(widget.render_line(y).text for y in range(widget.content_size.height))


async def click_menu(app, pilot, label):
    bar = app.query_one('#menubar')
    for y in range(bar.content_size.height):
        line = bar.render_line(y).text
        if label in line:
            await pilot.click('#menubar', offset=(line.index(label) + bar.styles.padding.left, y))
            await pilot.pause()
            return
    raise AssertionError((label, painted(bar)))


async def truth():
    for size in ((80, 24), (120, 32), (160, 48), (60, 18)):
        async with fixture(size) as (app, pilot, envelope):
            runner = app.current()
            label = fleet_view.presentation(runner).label
            assert label == 'Waiting'
            assert label in str(app.query_one('#runners', DataTable).get_row_at(0)[1])
            summary = app.query_one('#overview')
            assert label in painted(summary), painted(summary)
            assert 'Details' in painted(app.query_one('#menubar'))
            assert 'Tasks' in painted(app.query_one('#menubar'))
            assert 'warnings' not in painted(summary)
            lanes = app.query_one('#lanes', DataTable)
            assert str(lanes.get_row_at(0)[0]).startswith('Repair the'), lanes.get_row_at(0)
            assert lanes.region.height >= 3 and lanes.region.bottom <= size[1], lanes.region
            assert app.query_one('#log').region.height >= 4
            if size[1] < 22:
                assert summary.region.height <= 3
            await pilot.press('i')
            await pilot.pause()
            detail = app.query_one('#detail')
            assert label in str(detail.render()) and REASON in str(detail.render())
            assert TITLE in str(detail.render()) and all(t in str(detail.render()) for t in IDS)
            pane = app.query_one('#detail-scroll')
            await pilot.press('end')
            await pilot.pause()
            assert pane.scroll_y > 0
            await pilot.press('i')
            # Duplicate display names must dispatch exact IDs, including after reorder.
            for task in IDS:
                lanes.move_cursor(row=next(i for i, key in enumerate(lanes.rows) if json.loads(key.value)[2] == task))
                lanes.focus()
                await pilot.press('enter')
                await settle(app, pilot)
                assert isinstance(app.screen, tui.WorkerScreen) and app.screen.task_id == task
                await pilot.press('escape')
            lanes.move_cursor(row=1)
            app.current().lanes.reverse()
            app.show_lanes(app.current())
            assert selected_task(lanes) == IDS[1]
            runner.lanes.append(replace(next(l for l in runner.lanes if l.task == IDS[1]), attempt=2))
            app.show_lanes(runner)
            assert selected_task(lanes) == IDS[1], 'another observation cannot change the selected task'
            runner.lanes = [l for l in runner.lanes if not (l.task == IDS[1] and l.attempt == 1)]
            app.show_lanes(runner)
            assert selected_task(lanes) == IDS[1], 'disappearing observation follows the same task'
            old_key = lanes.coordinate_to_cell_key(lanes.cursor_coordinate).row_key
            app.runners = [replace(runner, repo=runner.repo + '/replacement')]
            app.show_lanes(app.current())
            app.on_data_table_row_selected(SimpleNamespace(data_table=lanes, row_key=old_key))
            assert len(app.screen_stack) == 1, 'a stale event cannot target a replacement repository'
            app.runners = [runner]
            app.show_lanes(runner)
            await click_menu(app, pilot, 'More')
            assert isinstance(app.screen, tui.ActionMenu)
            assert {'s', 'r', 'm', 't', 'l', 'p', 'i', 'n', 'q'} <= {k for k, _ in app.screen.actions}
            await pilot.press('escape')
            # Useful live work and an owner question coexist; raw service state
            # must not replace the captured Working label in any fleet surface.
            runner = app.current()
            runner.questions = [fleet_view.Question(IDS[1], 'decision', 1, 'Choose the next input')]
            runner.snapshot = replace(runner.snapshot, counts=(1, 0, 1, 0, 0, 2),
                rows=(replace(runner.snapshot.rows[0], state='Active · Implementing', bucket='Active'),
                      runner.snapshot.rows[1]))
            runner.lanes = [replace(l, phase='implementing') if l.task == IDS[0] else l for l in runner.lanes]
            runner.snapshot = replace(runner.snapshot,
                joined_lanes=tuple((l.task, l.attempt, l.phase) for l in runner.lanes))
            app.render_fleet()
            await pilot.pause()
            assert 'Working' in painted(app.query_one('#overview'))
            assert 'Working' in str(app.query_one('#runners', DataTable).get_row_at(0)[1])
            await pilot.press('i')
            assert 'Working' in str(app.query_one('#detail').render())
    print('OPERATIONS OK truth')


async def evidence():
    for size in ((80, 24), (60, 18)):
        async with fixture(size) as (app, pilot, envelope):
            runner = app.current()
            notes = ('OLD-1: unmatched execution observation (closed)',) * 173 + ('session revision old',)
            runner.snapshot = replace(runner.snapshot, annotations=notes, errors=('source unreadable',) * 2,
                                      freshness='stale', engine_freshness='unknown')
            runner.lanes.append(fleet_view.Lane('UNKNOWN-1', 'running'))
            started = time.time() - 7200
            for state in ('red', 'running'):
                runner.main_check = dict(state=state, rev='b' * 40, main_head='c' * 40,
                    started=started, failures=['fixture'], pid=123, start_time=456,
                    check_slot=dict(state='running', started=time.time() - 300))
                app.show_detail()
                await pilot.pause()
                summary = painted(app.query_one('#overview'))
                assert '1 errors' in summary and '2 notes' in summary, summary
                assert 'Main:' in summary and '174 warnings' not in summary, summary
                assert ('running' if state == 'running' else 'red') in summary, summary
                assert fleet_view.presentation(runner).counts[0] == 0
                await pilot.press('i')
                await pilot.pause()
                detail = str(app.query_one('#detail').render())
                assert all(word in detail for word in ('Errors', 'Source notes', '174', 'source unreadable',
                                                      'OLD-1', 'UNKNOWN-1', 'bbbbbbb', 'ccccccc', '2h')) , detail
                assert ('main check running' if state == 'running' else 'main red') in detail, detail
                assert detail.count(notes[0]) == 173, 'Details must retain every original'
                await pilot.press('end')
                await pilot.pause()
                assert app.query_one('#detail-scroll').is_vertical_scroll_end
                await pilot.press('i')
            # Canonical reasons, not raw worker prose, keep the wait kinds distinct.
            for reason in ('waiting for review', 'waiting to integrate', 'dependency INPUT-1'):
                runner.snapshot = replace(runner.snapshot,
                    rows=(replace(runner.snapshot.rows[0], why=reason), runner.snapshot.rows[1]))
                app.show_detail()
                assert reason in str(app.query_one('#detail').render())
            runner.snapshot = replace(runner.snapshot, counts=None, freshness='unavailable')
            app.show_detail()
            await pilot.pause()
            assert 'unknown' in painted(app.query_one('#overview')).lower()
            await click_menu(app, pilot, 'More')
            app.screen.query_one('#action-filter', Input).value = 'Stop'
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()
            assert isinstance(app.screen, tui.Confirm)
            await pilot.press('escape')
    print('OPERATIONS OK evidence')


async def inputs():
    async with fixture((80, 24)) as (app, pilot, envelope):
        entered, release = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            entered.set()
            assert release.wait(15), 'barrier watchdog'
            return envelope
        with patch.object(fleet_view, 'collect_for_tui', side_effect=blocked):
            app.poll_refresh()
            assert await asyncio.to_thread(entered.wait, 5)
            try:
                await click_menu(app, pilot, 'More')
                await pilot.press('escape')
                await pilot.press('s')
                assert isinstance(app.screen, tui.Confirm)
                await pilot.press('escape')
                app.view_only = True
                await pilot.press('s', 'p')
                assert len(app.screen_stack) == 1
                await pilot.press('?')
                assert {k for k, _ in app.screen.actions} == {'l', 't', 'i', 'q'}
                await pilot.press('escape')
                app.view_only = False
                lanes = app.query_one('#lanes', DataTable)
                lanes.move_cursor(row=1)
                await pilot.pause()
                assert selected_task(lanes) == IDS[1]
                # Successful deletion is app-owned feedback; the blocked pre-action
                # capture cannot resurrect the row when its obsolete epoch returns.
                runner = app.current()
                identity = fleet_view.DeleteIdentity(runner.name, runner.repo, runner.snapshot.repository_identity, IDS[0])
                action = fleet_view.Action('d', 'Delete', [], deletion=identity)
                with patch.object(fleet_view, 'observe_deletions', return_value=()):
                    app.action_completed(action, True)
                    assert app.deletion_pending(app.current(), IDS[0])
                    assert IDS[0] not in {r.task for r in fleet_view.inventory_rows(app.current())}
                    await pilot.press('i')
                    await pilot.pause()
                    assert app.query_one('#detail-scroll').display and not release.is_set()
                    await pilot.press('i')
                    await app.push_screen(tui.NewTask([]))
                    await pilot.click('#title')
                    await pilot.press(*'draft')
                    field = app.screen.query_one('#title', Input)
                    assert field.value == 'draft' and not release.is_set()
                    release.set()
                    await settle(app, pilot)
                    assert field.value == 'draft', 'a stale refresh cannot replace an input draft'
                    await pilot.press('escape')
                    assert IDS[0] not in {r.task for r in fleet_view.inventory_rows(app.current())}
                    assert app.current().repo == runner.repo
                    assert selected_task(lanes) == IDS[1]
            finally:
                release.set()
    print('OPERATIONS OK input')


if __name__ == '__main__':
    asyncio.run({'truth': truth, 'evidence': evidence, 'input': inputs}[sys.argv[1]]())
