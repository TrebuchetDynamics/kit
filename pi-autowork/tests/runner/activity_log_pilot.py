"""Offline journal pilots. No services, models or terminal transport required."""
import asyncio
from dataclasses import replace
from pathlib import Path
import sys
from threading import Event
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import fleet_view, tui
from test_tui_redesign import fixture_app
from test_tui_layout import settle


CAPTURE = '\n'.join([
    'PI AUTOWORK', 'Transport: pi-rpc', 'Push: enabled',
    '[12:00] TASK-1: pending — dependency: TASK-2',
    '[12:01] TASK-1: failed — first detail',
    '[12:02] TASK-1: failed — second detail',
    '[12:03] TASK-1: failed — second detail',
    '', '  traceback detail', *[f'original diagnostic {i:02}' for i in range(45)]])


def painted(log):
    return '\n'.join(line.text for line in log.lines)


async def click(screen, pilot, label):
    bar = screen.query_one('#menubar')
    for y in range(bar.content_size.height):
        line = bar.render_line(y).text
        if label in line:
            await pilot.click('#menubar', offset=(line.index(label) + bar.styles.padding.left, y))
            await pilot.wait_for_scheduled_animations()
            return
    raise AssertionError(f'{label} is not visible in {bar.render()}')


async def view():
    for size in ((60, 18), (80, 24), (120, 32)):
        entered, release = Event(), Event()
        def blocked(runner, lines):
            assert lines == 1000
            entered.set()
            assert release.wait(10), 'blocked-reader watchdog'
            return 'obsolete capture from previous screen'
        async with fixture_app(size, view_only=True) as (app, pilot):
            with patch.object(tui.LogScreen, 'set_interval'), \
                 patch.object(app, 'execute', side_effect=AssertionError('root action')), \
                 patch.object(app, 'action_run', side_effect=AssertionError('root shortcut')):
                loader = Mock(return_value=CAPTURE)
                screen = tui.LogScreen(app.current(), loader)
                app.push_screen(screen)
                try:
                    await settle(app, pilot)
                    initial_reads = loader.call_count
                    log = screen.query_one('#full-log')
                    assert 'Summary' in screen.query_one('#menubar').render().plain
                    assert '×2' in painted(log) and 'Transport:' not in painted(log)
                    assert app.reads.executor._max_workers == 4
                    with patch.object(log, 'write', wraps=log.write) as write:
                        await pilot.press('v')
                        assert screen.raw
                        assert [call.args[0].plain for call in write.call_args_list] == CAPTURE.splitlines()
                    assert 'Raw' in screen.query_one('#menubar').render().plain
                    assert 'Transport: pi-rpc' in painted(log)
                    await pilot.pause()
                    await pilot.press('home')
                    await pilot.wait_for_scheduled_animations()
                    assert not log.is_vertical_scroll_end
                    row = log.scroll_y
                    await click(screen, pilot, 'Summary')
                    assert not screen.raw and log.scroll_y == row, (screen.raw, log.scroll_y, row, screen.query_one('#menubar').render())
                    await pilot.press('end')
                    await pilot.pause()
                    await pilot.wait_for_scheduled_animations()
                    assert log.is_vertical_scroll_end, (log.scroll_y, log.scroll_target_y, log.max_scroll_y, screen.focused)
                    await pilot.press('v')
                    await pilot.pause()
                    await pilot.wait_for_scheduled_animations()
                    assert log.is_vertical_scroll_end
                    assert loader.call_count == initial_reads, 'view toggle acquired data'
                    screen.logs = Mock(side_effect=blocked)
                    token = screen.refresh_log()
                    assert await asyncio.to_thread(entered.wait, 3)
                    await pilot.press('v')
                    await click(screen, pilot, 'Raw')
                    await pilot.resize_terminal(size[0] + 1, size[1] + 1)
                    await pilot.resize_terminal(*size)
                    assert screen.logs.call_count == 1, 'toggle/resize read again'
                    assert screen.cached_text == CAPTURE and screen.raw
                    await pilot.press('q')
                    await pilot.pause()
                    assert app.screen is not screen
                    # A new runner/screen may publish while the obsolete reader is held.
                    current = tui.LogScreen(replace(app.current(), name='second'), Mock(return_value='current evidence'))
                    app.push_screen(current)
                    await pilot.pause()
                    current_token = current.refresh_log()
                    await current_token.wait()
                    await pilot.pause()
                    assert current.cached_text == 'current evidence'
                    release.set()
                    await token.wait()
                    await settle(app, pilot)
                    assert current.cached_text == 'current evidence'
                    assert 'obsolete' not in painted(current.query_one('#full-log'))
                    await pilot.press('escape')
                    await pilot.pause()
                    assert app.screen is not current
                finally:
                    release.set()


async def failures():
    async with fixture_app((80, 24)) as (app, pilot):
        runner = app.current()
        activity = app.query_one('#log')
        with patch.object(fleet_view, 'logs', return_value='') as acquisition:
            await app.refresh_log().wait()
            acquisition.assert_called_once_with(runner, lines=400, journalctl=app.journalctl, since='-60min', strict=True)
        assert 'nothing in the last hour' in painted(activity)
        with patch.object(fleet_view, 'logs', return_value='') as acquisition, patch.object(tui.LogScreen, 'set_interval'):
            app.action_run('l')
            await settle(app, pilot)
            assert acquisition.call_count
            for call in acquisition.call_args_list:
                assert call.kwargs == dict(lines=1000, journalctl=app.journalctl, strict=True)
            await pilot.press('escape')
            await pilot.pause()
        for text in (None, '[12:01] TASK-1: failed — retained evidence'):
            # Reset selection-owned Activity cache to exercise initial unavailable and stale.
            app._journal_lines, app._log = None, None
            if text is not None:
                app.show_log(runner.name, fleet_view.log_lines(text))
            with patch.object(fleet_view, 'logs', side_effect=OSError('journal denied')):
                await app.refresh_log().wait()
                await pilot.pause()
            assert 'stale' in app.sub_title and 'journal denied' in painted(activity)
            assert 'reading journal' not in painted(activity).lower()
            assert 'nothing in the last hour' not in painted(activity)
            if text is not None:
                assert 'retained evidence' in painted(activity) and 'Last good journal' in painted(activity)
            with patch.object(tui.LogScreen, 'set_interval'):
                loader = Mock(side_effect=OSError('journal denied'))
                screen = tui.LogScreen(runner, loader)
                app.push_screen(screen)
                await settle(app, pilot)
                log = screen.query_one('#full-log')
                assert 'Journal unavailable' in screen.query_one('#journal-status').render().plain
                assert 'no output yet' not in painted(log)
                # Successful empty is distinct from an acquisition failure.
                loader.side_effect, loader.return_value = None, ''
                await screen.refresh_log().wait()
                assert 'no output yet' in painted(log) and not screen.sub_title
                screen.show_log(CAPTURE)
                with patch.object(log, 'write', wraps=log.write) as write:
                    screen.show_log(CAPTURE)
                    assert write.call_count == 0
                    screen.log_failed(OSError('retained stale'))
                    assert write.call_count > 0
                    write.reset_mock()
                    screen.log_failed(OSError('retained stale'))
                    assert write.call_count == 0
                    await pilot.press('v')
                    assert write.call_count > 0
                    assert screen.cached_text == CAPTURE
                    assert 'stale' in screen.query_one('#journal-status').render().plain
                # Style is part of the cached summary value, not just its characters.
                await pilot.press('v')
                styled = [(line, 'magenta') for line, _ in fleet_view.log_lines(CAPTURE)]
                with patch.object(fleet_view, 'log_lines', return_value=styled), patch.object(log, 'write') as write:
                    screen.render_log()
                    assert write.call_count and write.call_args.args[0].style == 'magenta'
                await pilot.press('escape')
                await pilot.pause()
        with patch.object(fleet_view, 'logs', return_value=''):
            await app.refresh_log().wait()
            await pilot.pause()
        assert 'journal:' not in app.sub_title and 'nothing in the last hour' in painted(activity)
        lines = fleet_view.log_lines('[12:00] unchanged')
        app.show_log(runner.name, lines)
        with patch.object(activity, 'write') as write:
            app.show_log(runner.name, lines)
            assert write.call_count == 0
            app.show_log(runner.name, [(lines[0][0], 'red')])
            assert write.call_count == 1
            app.show_log(runner.name, lines, 'new read failure')
            assert write.call_count > 1


if __name__ == '__main__':
    asyncio.run({'view': view, 'failures': failures}[sys.argv[1]]())
