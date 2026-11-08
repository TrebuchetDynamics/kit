"""Directory navigation acceptance; pinned Textual and fixture-only acquisition."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pi_autowork import fleet_view
from test_tui_layout import run_pilot, settle


def text(widget):
    return widget.render().plain


def visible(widget, size):
    assert widget.display and widget.region.width > 0 and widget.region.height > 0, widget.region
    assert widget.region.x >= 0 and widget.region.y >= 0, widget.region
    assert widget.region.right <= size[0] and widget.region.bottom <= size[1], widget.region


@asynccontextmanager
async def fixture_app(size):
    from pi_autowork import tui
    with tempfile.TemporaryDirectory() as folder:
        home = Path(folder) / 'home'
        start = home / 'projects' / 'start'
        child = start / 'child directory'
        target = home / 'target directory'
        child.mkdir(parents=True)
        target.mkdir()
        (start / 'fixture.txt').write_text('navigation must preserve this file\n')
        calls = []
        def command(argv, **kwargs):
            calls.append((argv, kwargs))
            raise AssertionError('Navigation must not execute an external command')
        def ready(path):
            return fleet_view.Readiness(str(path), repo=str(path), ready=True, branch='fixture')
        snapshot = fleet_view.FleetSnapshot((), (), 1, time.time())
        app = tui.FleetApp(command='fixture-autowork', script='unused', state_root=home,
                           env_dir=home, browse_root=str(start), runner_cmd=command,
                           list_models=lambda: ['fixture/model'])
        before = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob('*') if p.is_file()}
        with patch.dict(os.environ, {'HOME': str(home)}), \
             patch.object(Path, 'home', return_value=home), \
             patch.object(fleet_view, 'collect_for_tui', return_value=snapshot), \
             patch.object(fleet_view, 'readiness', side_effect=ready), \
             patch.object(fleet_view, 'logs', return_value='fixture journal'):
            async with run_pilot(app, size=size) as pilot:
                await settle(app, pilot)
                app.action_browse()
                await settle(app, pilot)
                browser = app.screen
                assert isinstance(browser, tui.BrowseScreen)
                yield app, pilot, browser, home, start, target
                assert calls == [], calls
        after = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob('*') if p.is_file()}
        assert after == before, 'Navigation changed fixture files'


async def jump(app, pilot, browser, value):
    from textual.widgets import Input
    await pilot.press('ctrl+l')
    field = browser.query_one('#browse-path', Input)
    assert app.focused is field, 'Ctrl+L must focus the address'
    field.value = value
    await pilot.press('enter')
    await settle(app, pilot)


def at(browser, expected):
    from textual.widgets import Input
    assert Path(browser.root) == expected, browser.root
    assert Path(browser.query_one('#tree').path) == expected
    shown = browser.query_one('#browse-path', Input).value
    assert Path(shown).expanduser() == expected, shown
    assert str(expected) in browser.title, browser.title
    assert browser.chosen is not None and Path(browser.chosen.path) == expected


async def paths_pilot(size):
    from textual.widgets import Input
    async with fixture_app(size) as (app, pilot, browser, home, start, target):
        for selector in ('#browse-path', '#browse-up', '#browse-home', '#browse-status', '#tree', '#info-scroll'):
            visible(browser.query_one(selector), size)
        await pilot.press('ctrl+l')
        field = browser.query_one('#browse-path', Input)
        assert app.focused is field
        selection = field.selection
        assert {selection.start, selection.end} == {0, len(field.value)}, selection
        # Typing replaces the selected address rather than appending to it.
        await pilot.press('c', 'h', 'i', 'l', 'd', 'space', 'd', 'i', 'r', 'e', 'c', 't', 'o', 'r', 'y', 'enter')
        await settle(app, pilot)
        at(browser, start / 'child directory')
        await pilot.press('alt+up')
        await settle(app, pilot)
        at(browser, start)
        await pilot.click('#browse-up')
        await settle(app, pilot)
        at(browser, start.parent)
        await jump(app, pilot, browser, '../target directory')
        at(browser, target)
        await jump(app, pilot, browser, '~/projects/start')
        at(browser, start)
        await pilot.click('#browse-home')
        await settle(app, pilot)
        at(browser, home)
        await jump(app, pilot, browser, str(target))
        at(browser, target)
        await pilot.press('alt+home')
        await settle(app, pilot)
        at(browser, home)


async def tree_errors_pilot(size):
    async with fixture_app(size) as (app, pilot, browser, home, start, target):
        tree = browser.query_one('#tree')
        # DirectoryTree owns arrow expansion/highlighting; Enter changes the browser root.
        tree.focus()
        await pilot.press('right', 'down')
        await settle(app, pilot)
        assert Path(browser.root) == start, 'Arrow navigation must not change the browser root'
        selected = tree.cursor_node
        assert selected and selected.data and selected.data.path == start / 'child directory'
        await pilot.press('enter')
        await settle(app, pilot)
        at(browser, start / 'child directory')
        await jump(app, pilot, browser, str(start))
        for invalid, reason in ((start / 'missing directory', ('exist', 'no such', 'missing')),
                                (start / 'fixture.txt', ('director',))):
            selected = tree.cursor_node
            chosen, chosen_path = browser.chosen, browser.chosen_path
            await jump(app, pilot, browser, str(invalid))
            assert Path(browser.root) == start and Path(tree.path) == start
            assert tree.cursor_node is selected, 'Failed navigation must preserve the tree selection'
            assert browser.chosen == chosen and browser.chosen_path == chosen_path
            status = text(browser.query_one('#browse-status')).lower()
            assert any(word in status for word in reason) and ('path' in status or str(invalid).lower() in status), status
            visible(browser.query_one('#browse-status'), size)
        await jump(app, pilot, browser, str(target))
        at(browser, target)
        status = text(browser.query_one('#browse-status')).lower()
        assert 'missing directory' not in status and 'fixture.txt' not in status, status


async def delayed_pilot(size):
    from textual.widgets import Input
    async with fixture_app(size) as (app, pilot, browser, home, start, target):
        original = browser.read
        release, started = threading.Event(), threading.Event()
        reads = []
        ui_thread = threading.get_ident()
        def read(kind, identity, loader, apply, failed=None):
            if kind == 'browse-path':
                actual = loader
                def loader():
                    reads.append(threading.get_ident())
                    if not started.is_set():
                        started.set()
                        assert release.wait(5), 'Test did not release delayed navigation'
                    return actual()
            return original(kind, identity, loader, apply, failed)
        with patch.object(browser, 'read', side_effect=read):
            try:
                await pilot.press('ctrl+l')
                browser.query_one('#browse-path', Input).value = str(target)
                await pilot.press('enter')
                assert await asyncio.to_thread(started.wait, 2), 'Navigation did not use browse-path reader'
                status = text(browser.query_one('#browse-status')).lower()
                assert 'load' in status or 'opening' in status, status
                with patch.object(browser, 'show_repository') as show_repository, \
                     patch.object(browser, 'plan') as plan:
                    browser.action_start()
                    browser.action_plan_selected()
                    assert not show_repository.called and not plan.called, \
                        'Pending navigation must not start or plan the previous directory'
                # A later address remains responsive while the first filesystem read is held.
                await pilot.press('ctrl+l')
                browser.query_one('#browse-path', Input).value = str(home)
                await pilot.press('enter')
            finally:
                release.set()
            await settle(app, pilot)
            at(browser, home)
            assert reads and all(thread != ui_thread for thread in reads), reads
            release.clear()
            started.clear()
            try:
                await pilot.press('ctrl+l')
                browser.query_one('#browse-path', Input).value = str(target)
                await pilot.press('enter')
                assert await asyncio.to_thread(started.wait, 2)
                await pilot.press('escape')
                assert len(app.screen_stack) == 1
            finally:
                release.set()
            await settle(app, pilot)
            assert Path(browser.root) == home, 'A dismissed browser must ignore pending navigation'


class TuiNavigationTests(unittest.TestCase):
    def run_case(self, case):
        self.assertIsNotNone(shutil.which('uv'), 'Navigation acceptance requires uv and pinned Textual cache')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
                                 'python', __file__, '--pilot', case], capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NAVIGATION PILOT OK ' + case, result.stdout)

    def test_address_paths_parent_and_home_controls(self):
        self.run_case('paths')

    def test_tree_enter_and_invalid_paths_preserve_selection(self):
        self.run_case('tree_errors')

    def test_navigation_is_async_latest_wins_and_dismissal_cancels(self):
        self.run_case('delayed')


async def main(case):
    for size in ((80, 24), (60, 18)):
        await globals()[case + '_pilot'](size)
        print('PASS', case, size)
    print('NAVIGATION PILOT OK', case)


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        asyncio.run(main(sys.argv[-1]))
    else:
        unittest.main()
