"""Model choice and first-service consent; pinned Textual, fixture readers only."""
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
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
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


async def finish_primary(app, pilot, *, confirm=True):
    """Explicitly disable fallback, then accept the staged summary if requested."""
    from pi_autowork import tui
    assert isinstance(app.screen, tui.PickModel) and app.screen.allow_none
    await pilot.click('#model-none')
    await settle(app, pilot)
    assert isinstance(app.screen, tui.Confirm)
    if confirm:
        await pilot.press('y')
        await settle(app, pilot)


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
        await pilot.press('m')
        await settle(app, pilot)
        picker = app.screen
        assert isinstance(picker, tui.PickModel), type(picker).__name__
        assert loads == [True]
        field = picker.query_one('#filter', Input)
        assert app.focused is field, 'Typing should immediately filter the model list'
        for selector in ('#filter', '#models', '#model-status'):
            visible(picker.query_one(selector), size)
        assert not picker.query_one('#model-login').disabled
        assert not picker.query_one('#model-refresh').disabled
        await pilot.click('#model-login')
        await settle(app, pilot)
        assert app.screen is picker and loads == [True]
        assert 'provider' in text(picker.query_one('#model-status')).lower()
        await pilot.click('#model-refresh')
        await settle(app, pilot)
        assert loads == [True, True], 'Manual refresh must reload the Pi catalog'
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
        await finish_primary(app, pilot)
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
        panel = app.query_one('#empty-card', Static)
        visible(panel, size)
        assert 'read only' in text(panel).lower(), text(panel)
        await pilot.press('m')
        app.action_pick_model('model')
        await pilot.pause()
        assert len(app.screen_stack) == 1 and len(loads) == 4
    # A read-only empty fleet still explains model choice without enabling it.
    async with fixture_app(size, view_only=True) as (app, pilot, ready, calls):
        visible(app.query_one('#modelbar'), size)
        app.action_pick_model('model')
        await pilot.pause()
        assert len(app.screen_stack) == 1


async def login_pilot(size):
    from pi_autowork import tui, tui_auth
    from textual.widgets import Input, Select, Button
    provider = dict(id='fixture', name='Fixture', state='not stored', methods=['oauth', 'api_key'])
    loads = []
    def catalog():
        loads.append(True)
        return dict(models=MODELS[:] if len(loads) > 1 else [], providers=[provider])
    active = []
    class FakeBridge:
        def __init__(self, agent_dir):
            self.agent_dir = agent_dir
            self.answer_event = asyncio.Event()
            self.answers = []
            active.append(self)
        async def run(self, operation, receive, chosen, method):
            self.operation, self.chosen, self.method = operation, chosen, method
            await receive(dict(type='progress'))
            await receive(dict(type='info', message='Provider prerequisite: authenticate first', links=[dict(label='Setup guide', url='https://example.com/setup')]))
            if method == 'oauth':
                await receive(dict(type='url', url='https://example.com/authorize?state=private'))
            await receive(dict(type='prompt', kind='text', message='Host (blank for github.com)'))
            await self.answer_event.wait()
            assert self.answers[-1] == '', 'Provider text default must arrive unchanged'
            self.answer_event.clear()
            await receive(dict(type='prompt', kind='secret', message='Enter fixture credential'))
            await self.answer_event.wait()
            if self.answers[-1] == 'invalid-fixture-secret':
                await receive(dict(type='error', message='invalid-fixture-secret must never display'))
                return
            await receive(dict(type='success'))
        async def answer(self, value):
            self.answers.append(value)
            self.answer_event.set()
    async with fixture_app(size, loader=catalog) as (app, pilot, ready, calls):
        with patch.object(tui_auth.pi_auth, 'Bridge', FakeBridge):
            # Constructor defaults are bound at definition time; replace the screen factory.
            original = tui.ProviderAuth
            with patch.object(tui, 'ProviderAuth', side_effect=lambda p, d, **kw: original(p, d, FakeBridge, **kw)):
                app.action_pick_model('model')
                await settle(app, pilot)
                picker = app.screen
                assert picker.models == [] and picker.query_one('#provider', Select).value == 'fixture'
                await pilot.click('#model-login')
                await settle(app, pilot)
                screen = app.screen
                for selector in ('#auth-method', '#auth-status', '#auth-connect', '#auth-cancel'):
                    visible(screen.query_one(selector), size)
                screen.query_one('#auth-method', Select).focus()
                await pilot.press('enter', 'end', 'enter', 'tab', 'enter')
                await settle(app, pilot)
                assert active[-1].agent_dir == app.new_model_agent_dir
                assert 'Provider prerequisite' in text(screen.query_one('#auth-guidance'))
                assert 'https://example.com/setup' in text(screen.query_one('#auth-guidance'))
                field = screen.query_one('#auth-answer', Input)
                visible(field, size)
                visible(screen.query_one('#auth-status'), size)
                assert field.password and field.value == ''
                await pilot.press('enter')  # Blank text selects the provider-defined default.
                await settle(app, pilot)
                assert active[-1].answers == ['']
                await pilot.press('enter')  # Blank secrets must still be refused.
                await pilot.pause()
                assert active[-1].answers == [''] and field.display
                await pilot.press(*'fixture-secret-value')
                await pilot.pause()
                assert 'fixture-secret-value' not in str(field.render())
                await pilot.press('enter')
                await settle(app, pilot)
                assert app.screen is picker and len(loads) == 2
                assert picker.models == MODELS and app.new_model == ''
                assert active[-1].answers == ['', 'fixture-secret-value']

                # OAuth requires an explicit browser action; Escape preserves model/profile.
                app.new_model = 'fixture/alpha'
                await pilot.click('#model-login')
                await settle(app, pilot)
                screen = app.screen
                screen.query_one('#auth-method', Select).value = 'oauth'
                with patch.object(tui_auth.webbrowser, 'open', return_value=True) as browser:
                    await pilot.click('#auth-connect')
                    await settle(app, pilot)
                    assert not browser.called
                    assert not screen.query_one('#auth-browser', Button).disabled
                    await pilot.click('#auth-browser')
                    await settle(app, pilot)
                    browser.assert_called_once_with('https://example.com/authorize?state=private')
                await pilot.press('escape')
                await settle(app, pilot)
                assert app.screen is picker and app.new_model == 'fixture/alpha' and len(loads) == 2
                assert active[-1].answer_event.is_set() is False
                assert active[-1].answers == []

                await pilot.click('#model-login')
                await settle(app, pilot)
                screen = app.screen
                screen.query_one('#auth-method', Select).value = 'api_key'
                await pilot.click('#auth-connect')
                await settle(app, pilot)
                await pilot.press('enter')
                await settle(app, pilot)
                screen.query_one('#auth-answer', Input).value = 'invalid-fixture-secret'
                await pilot.press('enter')
                await settle(app, pilot)
                visible(screen.query_one('#auth-status'), size)
                shown = text(screen.query_one('#auth-status')).lower()
                assert 'failed' in shown and 'invalid-fixture-secret' not in shown
                assert screen.query_one('#auth-answer', Input).value == ''
                await pilot.press('escape')
                assert app.screen is picker
                # Profile switching cancels an in-flight login; stale success cannot refresh.
                await pilot.click('#model-login')
                await settle(app, pilot)
                screen = app.screen
                screen.query_one('#auth-method', Select).value = 'api_key'
                await pilot.click('#auth-connect')
                await settle(app, pilot)
                before = len(loads)
                app.new_model_agent_dir = '/tmp/different-fixture-profile'
                await screen.receive(dict(type='success'))
                await settle(app, pilot)
                assert app.screen is picker and len(loads) == before
                assert app.new_model == 'fixture/alpha'
                await pilot.press('escape')
                assert app.new_model == 'fixture/alpha'


async def incremental_catalog_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Select
    provider = dict(id='fixture', state='not stored', methods=['api_key'])
    public = dict(providers=[provider], models=[dict(id=MODELS[0], free=True)])

    async def until(predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait(), 10)
        await pilot.pause()

    # Exercise the production loader selection, not just PickModel's test seam.
    entered, release = threading.Event(), threading.Event()
    def unavailable(**kwargs):
        entered.set()
        assert release.wait(10), 'test did not release available-model reader'
        raise RuntimeError('fixture availability failed')
    with patch.object(fleet_view, 'models', unavailable), \
         patch.object(tui.pi_auth, 'discovery', return_value=public) as discovery:
        async with fixture_app(size, loader=unavailable) as (app, pilot, ready, calls):
            app.action_pick_model('model')
            picker = app.screen
            try:
                await until(lambda: entered.is_set() and bool(picker.providers))
                selector = picker.query_one('#provider', Select)
                visible(selector, size)
                assert not selector.disabled and picker.models == [MODELS[0]]
                assert picker.catalog_loading and not picker.usable_models
                selector.focus()
                await pilot.press('enter')
                assert selector.expanded
                await pilot.press('end', 'enter')
                assert picker.provider == 'fixture' and picker.shown == [MODELS[0]]
                with patch.object(picker, 'action_login') as login:
                    picker.choose_model(MODELS[0])
                    login.assert_called_once()
                assert app.new_model == ''
                # Cancelling auth must resume availability checks invalidated by
                # suspension, even when authentication itself did not succeed.
                with patch.object(tui, 'ProviderAuth', side_effect=lambda *a, **kw: tui.Confirm('Fixture auth')):
                    picker.action_login()
                    await pilot.pause()
                    assert isinstance(app.screen, tui.Confirm)
                    await pilot.press('escape')
                    await until(lambda: discovery.call_count == 2
                                and 'catalog' not in picker._model_pending)
                    assert app.screen is picker and not picker.usable_models
            finally:
                release.set()
            await settle(app, pilot)
            assert picker.models == [MODELS[0]] and not picker.usable_models
            assert not picker.query_one('#provider', Select).disabled
            assert picker.load_error and not picker.catalog_loading
            assert 'could not be loaded' in text(picker.query_one('#model-status'))
            assert discovery.call_count == 2
            await pilot.press('escape')

    # Refresh publishes new public metadata without overlapping a retired physical
    # availability read. Neither its late result nor a changed profile may select.
    entered, release = threading.Event(), threading.Event()
    second_entered, second_release = threading.Event(), threading.Event()
    loads = []
    def available(**kwargs):
        loads.append(True)
        signal, gate = (entered, release) if len(loads) == 1 else (second_entered, second_release)
        signal.set()
        assert gate.wait(10), 'test did not release available-model reader'
        return MODELS[:]
    with patch.object(fleet_view, 'models', available), \
         patch.object(tui.pi_auth, 'discovery', return_value=public) as discovery:
        async with fixture_app(size, loader=available) as (app, pilot, ready, calls):
            app.new_model = MODELS[0]
            app.action_pick_model('fallback')
            picker = app.screen
            assert picker.allow_none
            try:
                await until(lambda: entered.is_set() and bool(picker.providers))
                picker.refresh_models()
                await until(lambda: discovery.call_count == 2 and bool(picker.providers)
                            and 'catalog' not in picker._model_pending)
                assert len(loads) == 1 and not picker.usable_models
                assert not picker.query_one('#provider', Select).disabled
                release.set()
                await until(second_entered.is_set)
                assert picker.usable_models == set(), 'Retired result must not confer usability'
                app.new_model_agent_dir = '/fixture/changed-profile'
            finally:
                release.set()
                second_release.set()
            await settle(app, pilot)
            assert not picker.usable_models
            assert picker.query_one('#provider', Select).disabled
            assert 'changed' in picker.load_error
            await pilot.press('escape')

    with patch.object(fleet_view, 'models', return_value=MODELS[:]) as available, \
         patch.object(tui.pi_auth, 'discovery', side_effect=tui.pi_auth.AuthError('fixture discovery failed')):
        async with fixture_app(size, loader=available) as (app, pilot, ready, calls):
            app.action_pick_model('model')
            await settle(app, pilot)
            picker = app.screen
            assert picker.models == MODELS and picker.usable_models == set(MODELS)
            assert not picker.query_one('#provider', Select).disabled
            assert 'fixture discovery failed' in text(picker.query_one('#model-status'))
            app.view_only = True
            picker.choose_model(MODELS[0])
            assert app.screen is picker and app.new_model == ''
            await pilot.press('escape')


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
            await finish_primary(app, pilot)
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
            await finish_primary(app, pilot, confirm=False)
            assert isinstance(app.screen, tui.Confirm) and not execute.called
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_args.args[0].argv == ['fixture-autowork', 'model', 'fixture', 'fixture/beta', '--no-fallback']
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


async def repository_identity_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Select
    loads, bridges = [], []
    provider = dict(id='fixture', methods=['oauth'], state='not stored')
    def catalog():
        loads.append(True)
        return dict(models=MODELS[:], providers=[provider])
    class FakeBridge:
        def __init__(self, agent_dir):
            self.cancelled = False
            bridges.append(self)
        async def run(self, *args):
            try:
                await asyncio.Event().wait()
            finally:
                self.cancelled = True
    original = tui.ProviderAuth
    with patch.object(tui, 'ProviderAuth', side_effect=lambda p, d, **kw: original(p, d, FakeBridge, **kw)):
        async with fixture_app(size, service=True, loader=catalog) as (app, pilot, ready, calls):
            with patch.object(app, 'execute') as execute:
                for stage in ('selection', 'confirmation', 'authentication'):
                    runner = app.current()
                    app.action_pick_model('model')
                    await settle(app, pilot)
                    picker = app.screen
                    assert picker.identity_valid()
                    if stage == 'confirmation':
                        picker.choose_model(MODELS[1])
                        await settle(app, pilot)
                        await finish_primary(app, pilot, confirm=False)
                        assert isinstance(app.screen, tui.Confirm)
                    elif stage == 'authentication':
                        picker.action_login()
                        await settle(app, pilot)
                        auth = app.screen
                        assert not bridges, 'Opening a dialog must not start authentication'
                        auth.query_one('#auth-method', Select).value = 'oauth'
                        await pilot.click('#auth-connect')
                        await settle(app, pilot)
                    before = len(loads)
                    # Mutate the captured object too: identity must be an immutable snapshot.
                    runner.repo = ready.repo + '-replacement'
                    assert not picker.identity_valid(), 'Same name/profile is not the same repository'
                    if stage == 'selection':
                        picker.loaded_models(catalog())
                        before += 1
                        assert picker.shown == []
                        picker.choose_model(MODELS[1])
                        assert app.screen is picker
                        picker.dismiss(MODELS[1])  # A late selection callback must also be refused.
                    elif stage == 'confirmation':
                        await pilot.press('y')
                    else:
                        await auth.receive(dict(type='success'))
                        await settle(app, pilot)
                        assert app.screen is picker and bridges[-1].cancelled
                        picker.action_login()
                        assert app.screen is picker
                        await pilot.press('escape')
                    await settle(app, pilot)
                    assert len(loads) == before and not execute.called
                    runner.repo = ready.repo


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
        await finish_primary(app, pilot)
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
        await finish_primary(app, pilot)
        assert len(app.screen_stack) == 1 and app.new_model == 'nous-local/openai/unique'


async def free_models_pilot(size):
    from textual.widgets import Button, Input
    from pi_autowork import tui
    free = 'openrouter/fixture/a:free'
    other = 'openrouter/fixture/b:free'
    public = dict(models=[MODELS[0], free, other], usable_models=[MODELS[0]],
                  free_models=[free, other], providers=[
                      dict(id='fixture', methods=['api_key'], state='stored api_key'),
                      dict(id='openrouter', methods=['api_key'], state='not stored')])
    def empty_authenticated_catalog():
        raise ValueError('No authenticated models')
    with patch.object(tui.pi_auth, 'discovery', return_value=dict(providers=public['providers'], models=[dict(id=free, free=True)])):
        discovered = tui.FleetApp.model_catalog(empty_authenticated_catalog, '/fixture/profile', 'fixture-pi')
    assert discovered['models'] == [free] and discovered['usable_models'] == []
    assert discovered['free_models'] == [free] and discovered['model_error'] == ''
    async with fixture_app(size, loader=lambda: public) as (app, pilot, ready, calls):
        app.action_pick_model('model')
        await settle(app, pilot)
        picker = app.screen
        visible(picker.query_one('#model-free', Button), size)
        await pilot.click('#model-free')
        await pilot.pause()
        assert picker.shown == [free, other], picker.shown
        field = picker.query_one('#filter', Input)
        field.value = 'a:free'
        field.focus()
        await pilot.pause()
        assert picker.shown == [free]
        with patch.object(picker, 'action_login') as login:
            await pilot.press('enter')
            await pilot.pause()
            login.assert_called_once()
            assert app.new_model == '', 'Unconfigured model must not be silently selected'
        public['usable_models'] = [MODELS[0], free]
        picker.loaded_models(public)
        field.value = 'a:free'
        field.focus()
        await pilot.pause()
        await pilot.press('enter')
        await settle(app, pilot)
        await finish_primary(app, pilot)
        assert app.new_model == free


async def independent_fallback_pilot(size):
    from pi_autowork import tui
    from textual.widgets import Input, Select
    primary, fallback = 'first/paid/model-a', 'second/nested/model-b'
    async with fixture_app(size, loader=lambda: [primary, fallback]) as (app, pilot, ready, calls):
        async def select(model):
            picker = app.screen
            assert isinstance(picker, tui.PickModel) and not picker.free_only
            picker.query_one('#provider', Select).value = model.partition('/')[0]
            await pilot.pause()
            picker.query_one('#filter', Input).value = model.partition('/')[2]
            picker.query_one('#filter', Input).focus()
            await pilot.pause()
            await pilot.press('enter')
            await settle(app, pilot)
        app.action_pick_model('model')
        await settle(app, pilot)
        await select(primary)
        assert app.new_model == '' and app.new_fallback == ''
        visible(app.screen.query_one('#model-none'), size)
        await pilot.press('escape')
        await settle(app, pilot)
        assert app.new_model == '' and app.new_fallback == ''
        app.action_pick_model('model')
        await settle(app, pilot)
        await select(primary)
        await select(fallback)
        assert isinstance(app.screen, tui.Confirm)
        assert primary in app.screen.question and fallback in app.screen.question
        await pilot.press('n')
        await settle(app, pilot)
        assert app.new_model == '' and app.new_fallback == ''
        app.action_pick_model('model')
        await settle(app, pilot)
        await select(primary)
        await select(fallback)
        await pilot.press('y')
        await settle(app, pilot)
        assert (app.new_model, app.new_fallback) == (primary, fallback)
        # The start action receives the whole configuration, including explicit enablement.
        app.action_browse()
        await settle(app, pilot)
        app.screen.show_repository(ready.repo)
        await settle(app, pilot)
        with patch.object(app, 'execute') as execute:
            app.start_repository(ready)
            await settle(app, pilot)
            assert primary in app.screen.question and fallback in app.screen.question
            await pilot.press('y')
            await settle(app, pilot)
            action = execute.call_args.args[0]
            assert action.env['PI_AUTOWORK_PRIMARY'] == primary
            assert action.env['PI_AUTOWORK_FALLBACK'] == fallback
            assert action.env['PI_AUTOWORK_NO_FALLBACK'] == '0'
            # Existing service edits apply both settings with a single command.
            app.current().service = 'running'
            execute.reset_mock()
            app.action_pick_model('model')
            await settle(app, pilot)
            await select(primary)
            await select(fallback)
            assert not execute.called
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_args.args[0].argv == [
                'fixture-autowork', 'model', 'fixture', primary, '--fallback', fallback]
            execute.reset_mock()
            await pilot.press('f')
            await settle(app, pilot)
            await select(fallback)
            assert not execute.called
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_args.args[0].argv == [
                'fixture-autowork', 'model', 'fixture', '--fallback', fallback]
            execute.reset_mock()
            await pilot.press('f')
            await settle(app, pilot)
            assert isinstance(app.screen, tui.PickModel) and app.screen.allow_none
            await pilot.click('#model-none')
            await settle(app, pilot)
            await pilot.press('y')
            await settle(app, pilot)
            assert execute.call_args.args[0].argv == ['fixture-autowork', 'model', 'fixture', '--no-fallback']
            # Late view-only and target changes invalidate the fallback and summary stages.
            for stage in ('fallback', 'summary'):
                execute.reset_mock()
                app.action_pick_model('model')
                await settle(app, pilot)
                await select(primary)
                if stage == 'summary':
                    await select(fallback)
                    app.view_only = True
                    await pilot.press('y')
                else:
                    app.current().repo += '-changed'
                    app.screen.dismiss(fallback)
                await settle(app, pilot)
                assert not execute.called
                app.view_only = False
                app.current().repo = ready.repo


class TuiModelsTests(unittest.TestCase):
    def run_case(self, case):
        self.assertIsNotNone(shutil.which('uv'), 'Model acceptance requires uv and pinned Textual cache')
        result = subprocess.run(['uv', 'run', '--offline', '--quiet', '--no-project', '--with', 'textual==8.2.8',
                                 'python', __file__, '--pilot', case], capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('MODEL PILOT OK ' + case, result.stdout)

    def test_independent_primary_and_fallback_are_staged_and_applied_atomically(self):
        self.run_case('independent')

    def test_free_models_can_be_found_before_login_and_selected_after_configuration(self):
        self.run_case('free')

    def test_session_choice_filter_and_read_only_modelbar(self):
        self.run_case('session')

    def test_authentication_inside_tui_uses_selected_profile_masks_and_refreshes(self):
        self.run_case('login')

    def test_public_catalog_is_visible_during_slow_available_read_and_survives_failure(self):
        self.run_case('incremental')

    def test_model_loading_empty_and_error_status(self):
        self.run_case('status')

    def test_first_service_model_choice_precedes_consent_and_reaches_start(self):
        self.run_case('start')

    def test_existing_service_model_consent_and_settings_are_preserved(self):
        self.run_case('existing')

    def test_same_name_and_profile_cannot_retarget_repository_callbacks(self):
        self.run_case('repository')

    def test_provider_selection_scopes_search_and_preserves_cancelled_choice(self):
        self.run_case('providers')


async def main(case):
    for size in ((80, 24), (60, 18), (120, 32)):
        await {'session': session_pilot, 'login': login_pilot,
               'status': status_pilot, 'start': start_pilot,
               'existing': existing_pilot, 'repository': repository_identity_pilot,
               'providers': providers_pilot, 'free': free_models_pilot,
               'independent': independent_fallback_pilot,
               'incremental': incremental_catalog_pilot}[case](size)
        print('PASS', case, size)
    print('MODEL PILOT OK', case)


if __name__ == '__main__':
    if '--pilot' in sys.argv:
        asyncio.run(main(sys.argv[-1]))
    else:
        unittest.main()
