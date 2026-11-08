"""Model choice and first-service consent; pinned Textual, fixture readers only."""
import asyncio
from contextlib import asynccontextmanager
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

MODELS = ['fixture/alpha', 'fixture/beta']


def text(widget):
    return widget.render().plain


def visible(widget, size):
    assert widget.display and widget.region.width > 0 and widget.region.height > 0, widget.region
    assert widget.region.x >= 0 and widget.region.y >= 0, widget.region
    assert widget.region.right <= size[0] and widget.region.bottom <= size[1], widget.region


@asynccontextmanager
async def fixture_app(size, *, service=False, loader=None, view_only=False):
    from pi_autowork import tui
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        repo = root / 'repository'
        repo.mkdir()
        runner = fleet_view.Runner('fixture', repo=str(repo), service='running' if service else '',
                                   model='fixture/alpha' if service else '')
        snapshot = fleet_view.FleetSnapshot((runner,), (), 1, time.time())
        calls = []
        def command(argv, **kwargs):
            calls.append((argv, kwargs))
            raise AssertionError('Model pilots must never execute an external command')
        app = tui.FleetApp(command='fixture-autowork', script='unused', state_root=root, env_dir=root,
                           browse_root=str(repo), runner_cmd=command, view_only=view_only,
                           list_models=loader or (lambda: MODELS[:]))
        ready = fleet_view.Readiness(str(repo), repo=str(repo), ready=True, branch='main')
        with patch.object(fleet_view, 'collect_for_tui', return_value=snapshot), \
             patch.object(fleet_view, 'logs', return_value='fixture journal'), \
             patch.object(fleet_view, 'readiness', return_value=ready):
            async with run_pilot(app, size=size) as pilot:
                await settle(app, pilot)
                yield app, pilot, ready, calls
                assert calls == [], calls


async def session_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input, Label, OptionList, Static
    loads = []
    def models():
        loads.append(True)
        return MODELS[:]
    async with fixture_app(size, loader=models) as (app, pilot, ready, calls):
        assert app.new_model == ''
        bar = app.query_one('#modelbar', Static)
        visible(bar, size)
        assert 'choose model' in text(bar).lower(), text(bar)
        # The empty fleet must offer exactly the same session-level choice.
        app.runners = []
        app.render_fleet()
        await pilot.pause()
        await pilot.click('#modelbar', offset=(4, 0))
        await settle(app, pilot)
        picker = app.screen
        assert isinstance(picker, tui.PickModel), type(picker).__name__
        assert loads == [True]
        field = picker.query_one('#filter', Input)
        assert app.focused is field, 'Typing should immediately filter the model list'
        for selector in ('#filter', '#models', '#model-status'):
            visible(picker.query_one(selector), size)
        status = text(picker.query_one('#model-status')).lower()
        assert '2' in status and ('model' in status or 'match' in status), status
        await pilot.press('z', 'z', 'z')
        await pilot.pause()
        assert picker.query_one('#models', OptionList).option_count == 0
        status = text(picker.query_one('#model-status')).lower()
        assert 'no' in status and 'match' in status, status
        await pilot.press('enter')
        assert app.screen is picker and app.new_model == ''
        field.value = 'BETA'
        await pilot.pause()
        assert picker.query_one('#models', OptionList).option_count == 1
        await pilot.press('enter')
        await settle(app, pilot)
        assert len(app.screen_stack) == 1 and app.new_model == 'fixture/beta'
        assert 'fixture/beta' in text(bar), text(bar)
        # Cancelling a later choice preserves the selected session model.
        await pilot.press('m')
        await settle(app, pilot)
        current = next(label for label in app.screen.query(Label) if 'fixture/beta' in text(label))
        visible(current, size)
        await pilot.press('escape')
        assert app.new_model == 'fixture/beta'
        app.view_only = True
        app.render_fleet()
        visible(bar, size)
        assert 'read' in text(bar).lower(), text(bar)
        await pilot.press('m')
        app.action_pick_model('model')
        await pilot.pause()
        assert len(app.screen_stack) == 1 and len(loads) == 2
    # A read-only empty fleet still explains model choice without enabling it.
    async with fixture_app(size, view_only=True) as (app, pilot, ready, calls):
        visible(app.query_one('#modelbar'), size)
        app.action_pick_model('model')
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def status_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input, Select
    async with fixture_app(size) as (app, pilot, ready, calls):
        release = threading.Event()
        def delayed():
            assert release.wait(5), 'test did not release fixture model reader'
            return MODELS[:]
        try:
            await app.push_screen(tui.PickModel('Choose model', [], '', loader=delayed, identity='delayed'))
            await pilot.pause()
            picker = app.screen
            status = picker.query_one('#model-status')
            for selector in ('#provider', '#filter', '#models', '#model-status'):
                visible(picker.query_one(selector), size)
            assert picker.query_one('#provider', Select).disabled
            assert 'load' in text(status).lower(), text(status)
            assert app.focused is picker.query_one('#filter', Input)
        finally:
            release.set()
        await settle(app, pilot)
        visible(status, size)
        assert '2' in text(status), text(status)
        assert picker.query_one('#provider', Select).value == 'fixture'
        assert not picker.query_one('#provider', Select).disabled
        await pilot.press('escape')
        for loader, words in ((lambda: [], ('no', 'model', 'login')),
                              (lambda: (_ for _ in ()).throw(RuntimeError('fixture list unavailable')),
                               ('load', 'fixture list unavailable'))):
            await app.push_screen(tui.PickModel('Choose model', [], '', loader=loader, identity=repr(words)))
            await settle(app, pilot)
            status = app.screen.query_one('#model-status')
            visible(status, size)
            shown = text(status).lower()
            assert all(word in shown for word in words), shown
            provider = app.screen.query_one('#provider', Select)
            visible(provider, size)
            assert provider.disabled
            assert provider.value is Select.NULL
            await pilot.press('enter')
            assert isinstance(app.screen, tui.PickModel), 'An unavailable list cannot select a model'
            await pilot.press('escape')
        assert app.new_model == ''


async def start_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input
    async with fixture_app(size) as (app, pilot, ready, calls):
        app.action_browse()
        await settle(app, pilot)
        browser = app.screen
        browser.show_repository(ready.repo)
        await settle(app, pilot)
        with patch.object(app, 'execute') as execute:
            app.start_repository(ready)
            await settle(app, pilot)
            assert isinstance(app.screen, tui.PickModel), 'First service must choose a model before consent'
            await pilot.press('escape')
            await settle(app, pilot)
            assert app.screen is browser and not execute.called
            assert ready.repo not in app.starting_repositories
            app.start_repository(ready)
            await settle(app, pilot)
            app.screen.query_one('#filter', Input).value = 'beta'
            await pilot.pause()
            await pilot.press('enter')
            await settle(app, pilot)
            assert isinstance(app.screen, tui.Confirm), type(app.screen).__name__
            assert not execute.called
            await pilot.press('n')
            await settle(app, pilot)
            assert app.screen is browser and not execute.called
            assert app.new_model == 'fixture/beta'
            # The retained model skips a second picker, but never skips consent.
            app.start_repository(ready)
            await settle(app, pilot)
            assert isinstance(app.screen, tui.Confirm)
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_count == 1
            action = execute.call_args.args[0]
            assert action.argv == ['fixture-autowork', 'start', ready.repo], action.argv
            assert action.env['PI_AUTOWORK_PRIMARY'] == 'fixture/beta', action.env
            assert action.env['PI_AUTOWORK_NO_FALLBACK'] == '1', action.env


async def existing_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input
    async with fixture_app(size, service=True) as (app, pilot, ready, calls):
        visible(app.query_one('#modelbar'), size)
        assert 'fixture/alpha' in text(app.query_one('#modelbar'))
        with patch.object(app, 'execute') as execute:
            app.action_pick_model('model')
            await settle(app, pilot)
            assert isinstance(app.screen, tui.PickModel)
            app.screen.query_one('#filter', Input).value = 'beta'
            await pilot.pause()
            await pilot.press('enter')
            await settle(app, pilot)
            assert isinstance(app.screen, tui.Confirm) and not execute.called
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_args.args[0].argv == ['fixture-autowork', 'model', 'fixture', 'fixture/beta']
            execute.reset_mock()
            # Existing env files retain their own settings even after a session choice.
            env = Path(app.env_dir) / (fleet_view.instance(ready.repo) + '.env')
            env.write_text('PI_AUTOWORK_PRIMARY=fixture/alpha\nPI_AUTOWORK_FALLBACK=fixture/fallback\n')
            before = env.read_bytes()
            app.new_model = 'fixture/beta'
            app.action_browse()
            await settle(app, pilot)
            app.screen.show_repository(ready.repo)
            await settle(app, pilot)
            app.start_repository(ready)
            await settle(app, pilot)
            assert isinstance(app.screen, tui.Confirm)
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_count == 1
            action = execute.call_args.args[0]
            assert 'PI_AUTOWORK_PRIMARY' not in action.env, action.env
            assert 'PI_AUTOWORK_NO_FALLBACK' not in action.env, action.env
            assert env.read_bytes() == before


async def providers_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input, Label, OptionList, Select
    catalog = ['fixture/shared', 'fixture/beta', 'another/shared',
               'nous-local/openai/shared', 'nous-local/openai/unique']
    async with fixture_app(size, loader=lambda: catalog[:]) as (app, pilot, ready, calls):
        app.action_pick_model('model')
        await settle(app, pilot)
        picker = app.screen
        provider = picker.query_one('#provider', Select)
        field = picker.query_one('#filter', Input)
        options = picker.query_one('#models', OptionList)
        for widget in (provider, field, options, picker.query_one('#model-status')):
            visible(widget, size)
        assert provider.region.bottom <= field.region.y
        assert provider.value is Select.NULL and not provider.disabled
        assert options.option_count == 0 and app.new_model == ''
        status = text(picker.query_one('#model-status')).lower()
        assert 'provider' in status, status
        field.focus()
        await pilot.press('enter')
        assert app.screen is picker and app.new_model == ''

        # Exercise the real provider menu, including the narrow terminal layout.
        provider.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert provider.expanded
        await pilot.press('end', 'enter')
        await pilot.pause()
        assert provider.value == 'nous-local', provider.value
        assert app.focused is field
        assert picker.shown == catalog[3:], picker.shown
        assert options.option_count == 2
        status = text(picker.query_one('#model-status')).lower()
        assert '2' in status and ('model' in status or 'match' in status), status
        field.value = 'OPENAI/SHARED'
        await pilot.pause()
        assert picker.shown == ['nous-local/openai/shared']

        # A provider switch clears search without persisting any model choice.
        provider.value = 'fixture'
        await pilot.pause()
        assert field.value == '' and app.focused is field
        assert picker.shown == catalog[:2], picker.shown
        assert app.new_model == ''
        field.value = 'shared'
        await pilot.pause()
        assert picker.shown == ['fixture/shared']
        await pilot.press('enter')
        await settle(app, pilot)
        assert len(app.screen_stack) == 1 and app.new_model == 'fixture/shared'

        app.action_pick_model('model')
        await settle(app, pilot)
        picker = app.screen
        provider = picker.query_one('#provider', Select)
        assert provider.value == 'fixture'
        assert picker.shown == catalog[:2]
        current = next(label for label in picker.query(Label) if 'fixture/shared' in text(label))
        visible(current, size)
        provider.value = 'another'
        await pilot.pause()
        assert picker.shown == ['another/shared']
        await pilot.press('escape')
        assert app.new_model == 'fixture/shared'

        # A stored model absent from Pi's catalog must not choose another provider.
        app.new_model = 'missing/shared'
        app.action_pick_model('model')
        await settle(app, pilot)
        picker = app.screen
        assert picker.query_one('#provider', Select).value is Select.NULL
        assert picker.query_one('#models', OptionList).option_count == 0
        await pilot.press('escape')
        assert app.new_model == 'missing/shared'

        # Nested model IDs retain their complete provider/model value when the
        # model list (rather than the search field) submits the choice.
        app.new_model = 'nous-local/openai/shared'
        app.action_pick_model('model')
        await settle(app, pilot)
        picker = app.screen
        assert picker.query_one('#provider', Select).value == 'nous-local'
        picker.query_one('#filter', Input).value = 'unique'
        await pilot.pause()
        options = picker.query_one('#models', OptionList)
        assert options.option_count == 1
        options.focus()
        options.highlighted = 0
        await pilot.press('enter')
        await settle(app, pilot)
        assert len(app.screen_stack) == 1 and app.new_model == 'nous-local/openai/unique'


class TuiModelsTests(unittest.TestCase):
    def run_case(self, case):
        self.assertIsNotNone(shutil.which('uv'), 'Model acceptance requires uv and pinned Textual cache')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
                                 'python', __file__, '--pilot', case], capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('MODEL PILOT OK ' + case, result.stdout)

    def test_session_choice_filter_and_read_only_modelbar(self):
        self.run_case('session')

    def test_model_loading_empty_and_error_status(self):
        self.run_case('status')

    def test_first_service_model_choice_precedes_consent_and_reaches_start(self):
        self.run_case('start')

    def test_existing_service_model_consent_and_settings_are_preserved(self):
        self.run_case('existing')

    def test_provider_selection_scopes_search_and_preserves_cancelled_choice(self):
        self.run_case('providers')


async def main(case):
    for size in ((80, 24), (60, 18)):
        await globals()[case + '_pilot'](size)
        print('PASS', case, size)
    print('MODEL PILOT OK', case)


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        asyncio.run(main(sys.argv[-1]))
    else:
        unittest.main()
