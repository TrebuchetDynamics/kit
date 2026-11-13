"""`autowork`: the live view of every pi-autowork runner, with controls.

Bare `autowork` on a terminal runs this through `uv run --with textual==8.2.8`, so the
runner itself stays standard-library only. It reads runner state (status.json, engine
slots, systemd, logs, Pi transcripts) every few seconds and calls no model. Every
action runs an `autowork` command (or the runner script); there is no second way to
change a runner. `d` browses directories and starts a service for a repository that
has its tasks/ store committed on its main branch.

    python3 tui.py --command PATH --script PATH [--view-only]
"""
if __name__ == '__main__' and not __package__:
    import runpy
    import sys
    from pathlib import Path
    _root = Path(__file__).resolve().parents[2]
    _entry = runpy.run_path(str(_root / 'scripts/autowork_bootstrap.py'))
    raise SystemExit(_entry['run'](_root, 'pi_autowork.tui', sys.argv[1:]))

from pi_autowork.layout import LAYOUT
import argparse
import asyncio
from dataclasses import replace
import io
import json
import re
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

from pi_autowork import build, fleet_view, portal, tui_reads, blockers_report, command_results  # noqa: E402
from pi_autowork.planning_ui import PlanScreen, DecisionPrompt, QuestionPicker  # noqa: E402
from pi_autowork import pi_auth
from pi_autowork.tui_auth import ProviderAuth
from pi_autowork.tui_dialogs import Confirm  # noqa: E402
from pi_autowork.tui_common import (  # noqa: E402
    REFRESH, MenuBar, ViewHeader, ReadScreen, action_text, hotkeys, publish_text, read_input)
from pi_autowork.tui_tasks import (  # noqa: E402
    CommitEdits, DecisionScreen, NewTask, PickSection, TaskScreen, TasksScreen,
    TextPrompt, pending_edits)

from rich.style import Style
from rich.text import Text  # noqa: E402  (installed with textual)
from rich.cells import cell_len, set_cell_size  # noqa: E402
from textual.app import App, ComposeResult, SystemCommand  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Horizontal, Vertical, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen, Screen  # noqa: E402
from textual.widgets import (Button, DataTable, DirectoryTree, Header, Input, Label, OptionList,  # noqa: E402
                             RichLog, Select, Static, TextArea)

LOG_REFRESH = 5.0
CODE_CHECK = 30.0
CODE = Path(__file__).resolve().parent


def code_stamp():
    """The newest change to the TUI's own code: an update replaces these files, and a TUI left
    open kept showing the old release's readings for hours."""
    try:
        return max(path.stat().st_mtime for path in CODE.glob('*.py'))
    except (OSError, ValueError):
        return 0
QUESTIONS_SHOWN = 3


class ActionMenu(ModalScreen[str]):
    """Search existing actions without dispatching anything until selection."""
    BINDINGS = [Binding('escape', 'cancel', 'Back')]
    DEFAULT_CSS = '''
    ActionMenu { align: center middle; }
    ActionMenu > Vertical { width: 72; max-width: 100%; height: 80%; border: round $accent; background: $surface; padding: 0 2; }
    #actions { height: 1fr; min-height: 1; }
    #action-status { height: 1; }
    '''

    def __init__(self, actions):
        super().__init__()
        self.actions, self.shown = tuple(actions), list(actions)

    DESCRIPTIONS = {
        'l': 'View activity, worker output and the complete history.',
        't': 'See pending work, understand blockers and retry failed attempts.',
        'i': 'Inspect project status, checks and exact diagnostic evidence.',
        'm': 'Choose a provider and model; connect your account if needed.',
        'f': 'Choose the model to use when the primary model is unavailable.',
        'p': 'Start or pause work for the selected project.',
        's': 'Stop the service; unfinished work is preserved for the next start.',
        'r': 'Reload the runner configuration; this does not retry failed tasks.',
        'n': 'Browse folders and start Autowork on another project.',
        'u': 'Remove this stopped service; repository and worktrees stay.',
        'q': 'Close this interface. Running services continue in the background.',
    }

    @classmethod
    def option_text(cls, key, label):
        text = Text()
        text.append('[' + key + '] ', style='bold cyan')
        text.append(label + '\n', style='bold')
        text.append('    ' + cls.DESCRIPTIONS.get(key, 'Open this action.'), style='dim')
        return text

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text('What would you like to do?', style='bold'))
            yield Input(placeholder='Search: tasks, model, stop…', id='action-filter')
            yield OptionList(id='actions')
            yield Static('', id='action-status', markup=False)
            yield Label('↓ browse · Enter select · Esc back')

    def on_mount(self):
        field = self.query_one('#action-filter', Input)
        field.focus()
        self.on_input_changed(field)

    def on_input_changed(self, event):
        query = event.value.casefold()
        self.shown = [(key, label) for key, label in self.actions if query in f'{key} {label}'.casefold()]
        options = self.query_one('#actions', OptionList)
        options.clear_options()
        for key, label in self.shown:
            options.add_option(self.option_text(key, label))
        options.highlighted = 0 if self.shown else None
        self.query_one('#action-status', Static).update(
            f'{len(self.shown)} options · select one to continue' if self.shown else 'No matching actions. Change your search.')

    def on_input_submitted(self, event):
        if self.shown:
            self.dismiss(self.shown[0][0])

    def on_key(self, event):
        if event.key == 'down' and self.focused is self.query_one('#action-filter'):
            self.query_one('#actions', OptionList).focus()
            event.stop()

    def on_option_list_option_selected(self, event):
        if 0 <= event.option_index < len(self.shown):
            key, label = self.shown[event.option_index]
            if str(event.option.prompt) == self.option_text(key, label).plain:
                self.dismiss(key)

    def action_cancel(self):
        self.dismiss(None)


def detail_row(text, label, value, style=''):
    """One 'Label      value' line of a detail pane: the label dim in a fixed column."""
    text.append(f' {label:<11}' + (' ' if len(label) >= 11 else ''), style='dim')
    text.append(value + '\n', style=style)


def tilde(path):
    home = str(Path.home())
    return '~' + path[len(home):] if path and (path == home or path.startswith(home + '/')) else path


def doing(lane):
    """What a worker is doing, without what the row already says: its own task ID after
    "said:", and "said:" after "reviewer:"."""
    text = ' '.join(fleet_view.doing(lane).split())
    text = text.replace('reviewer: said: ', 'reviewer: ', 1)
    for prefix in ('said: ', 'reviewer: '):
        if text.startswith(prefix + lane.task):
            text = prefix + text[len(prefix + lane.task):].lstrip(' :,')
    return text


class PortalSetup(ModalScreen[dict]):
    """Preview a selected provider; a separate confirmation owns the write."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    PortalSetup { align: center middle; }
    PortalSetup > Vertical { width: 86; max-width: 100%; height: auto; max-height: 95%; border: round $accent; background: $surface; padding: 1 2; }
    #portal-fields { height: 1fr; }
    PortalSetup Input { margin-bottom: 1; }
    PortalSetup Horizontal { height: auto; align-horizontal: right; }
    '''

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label('Nous Portal through the local Hermes proxy')
            with VerticalScroll(id='portal-fields'):
                yield Label('No login, proxy start, model request or service change. Preview before consent.')
                yield Input(value='nous-local', placeholder='Selected Pi provider entry', id='portal-provider')
                yield Input(placeholder='Exact model ID from your Portal plan', id='portal-model')
                yield Input(value=portal.DEFAULT_ENDPOINT, placeholder='Loopback /v1 endpoint', id='portal-endpoint')
                yield Static('', id='portal-result', markup=False)
            with Horizontal():
                yield Button('Preview', id='portal-preview', variant='primary')
                yield Button('Cancel', id='portal-cancel')

    async def on_button_pressed(self, event):
        if event.button.id == 'portal-cancel':
            self.dismiss(None)
            return
        if event.button.id != 'portal-preview':
            return
        button = self.query_one('#portal-preview', Button)
        button.disabled = True
        try:
            proposal = await asyncio.to_thread(portal.propose,
                self.query_one('#portal-provider', Input).value,
                self.query_one('#portal-model', Input).value,
                self.query_one('#portal-endpoint', Input).value)
        except portal.SetupError as error:
            self.query_one('#portal-result', Static).update(str(error))
        else:
            self.query_one('#portal-result', Static).update(proposal.text())

            def consent(yes):
                if not yes:
                    self.query_one('#portal-result', Static).update(proposal.text() + '\nDeclined: no changes made.')
                    return
                try:
                    self.dismiss(portal.apply(proposal))
                except portal.SetupError as error:
                    self.query_one('#portal-result', Static).update(str(error))
            self.app.push_screen(Confirm(Text(proposal.text() + '\nApply this provider edit only?')), consent)
        finally:
            button.disabled = False

    def action_cancel(self):
        self.dismiss(None)


class PickModel(ReadScreen, ModalScreen[str]):
    """Choose a Pi provider, then search its available models."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel')]
    DEFAULT_CSS = '''
    PickModel { align: center middle; }
    PickModel > Vertical { width: 80; max-width: 100%; height: 90%; border: round $accent; background: $surface; padding: 0 2; }
    PickModel OptionList { height: 1fr; min-height: 1; }
    #model-actions { height: 3; }
    #model-actions Button { width: auto; min-width: 0; margin-right: 1; }
    #model-status { height: auto; max-height: 3; }
    '''

    def __init__(self, title, models, current, loader=None, identity=None, agent_dir=None, identity_valid=None, allow_none=False):
        super().__init__()
        self.allow_none = allow_none
        self.title_text, self.models, self.current = title, models, current
        self.loader, self.identity, self.agent_dir = loader, identity, agent_dir
        self.identity_valid = identity_valid or (lambda: True)
        self.providers, self.auth_error = {}, ''
        self.free_only, self.free_models, self.usable_models = False, set(), set()
        self.catalog_loading, self.load_error = bool(loader), ''
        self.provider = ''

    def compose(self) -> ComposeResult:
        from textual.widgets import Input
        with Vertical():
            yield ViewHeader(self.title_text, '1 Choose provider   2 Search models   3 Select a model'
                             if self.allow_none else
                             '1 Choose provider   2 Search or filter free models   3 Select a model')
            yield Label(Text(f'Current: {self.current}' if self.current else 'Choose a model available through Pi.'))
            yield Select([], prompt='1. Choose a Pi provider', id='provider', disabled=True)
            yield Input(placeholder='2. Search this provider\'s models', id='filter')
            yield OptionList(id='models')
            yield Static('Loading Pi models…' if self.loader else '', id='model-status', markup=False)
            with Horizontal(id='model-actions'):
                yield Button('Configure provider', id='model-login', disabled=not self.agent_dir)
                yield Button('Refresh models', id='model-refresh', disabled=self.loader is None)
                if self.allow_none:
                    yield Button('No fallback', id='model-none')
                else:
                    yield Button('Free models', id='model-free')
            yield Label('Choose a provider → Configure provider · Esc back')

    def on_mount(self):
        self.shown = []
        self.query_one('#filter', Input).focus()
        if self.loader:
            self.read('models', self.identity, self.loader, self.loaded_models, self.load_failed)
        else:
            self.loaded_models(self.models)

    def load_failed(self, error):
        self.catalog_loading, self.load_error = False, str(error)
        self.models, self.shown = [], []
        selector = self.query_one('#provider', Select)
        selector.set_options([])
        selector.disabled = True
        self.provider = ''
        self.query_one('#models', OptionList).clear_options()
        self.query_one('#model-status', Static).update(
            f'Cannot load Pi models: {error}\nRetry Refresh models or Configure provider.')

    def loaded_models(self, models):
        if not self.identity_valid():
            self.catalog_loading = False
            self.load_error = 'Pi profile or runner changed. Close and reopen the model picker.'
            self.models, self.shown = [], []
            self.query_one('#models', OptionList).clear_options()
            self.query_one('#model-status', Static).update(self.load_error)
            return
        self.catalog_loading, self.load_error = False, ''
        previous_provider = self.provider
        if isinstance(models, dict):
            self.providers = {p['id']: p for p in models.get('providers', [])}
            self.free_models = set(models.get('free_models', []))
            self.usable_models = set(models.get('usable_models', models['models']))
            self.auth_error = models.get('auth_error', '')
            self.load_error = models.get('model_error', '')
            models = models['models']
        self.models = models
        if not self.providers:
            self.usable_models = set(models)
        providers = sorted(set(self.providers) | {model.partition('/')[0] for model in models})
        selector = self.query_one('#provider', Select)
        available = {model.partition('/')[0] for model in self.usable_models}
        selector.set_options([(provider + (' · available' if provider in available else '')
                              + (' · ' + self.providers[provider]['state']
                                 if provider in self.providers else ''), provider)
                             for provider in providers])
        selector.disabled = not providers
        current_provider = self.current.partition('/')[0]
        self.provider = (previous_provider if previous_provider in providers else
                         current_provider if current_provider in providers else
                         providers[0] if len(providers) == 1 else '')
        selector.value = self.provider or Select.NULL
        self.on_input_changed(self.query_one('#filter', Input))
        (self.query_one('#filter', Input) if self.provider else selector).focus()

    def on_select_changed(self, event):
        if event.select.id != 'provider' or event.value != event.select.value:
            return
        provider = '' if event.value is Select.NULL else str(event.value)
        field = self.query_one('#filter', Input)
        if provider != self.provider:
            field.value = ''
        self.provider = provider
        self.on_input_changed(field)
        if self.provider:
            field.focus()

    def on_input_changed(self, event):
        provider_models = ([m for m in self.models if m in self.free_models] if self.free_only else
                           [m for m in self.models if m.partition('/')[0] == self.provider])
        query = event.value.lower().strip()
        self.shown = [m for m in provider_models if query in m.lower()]
        options = self.query_one('#models', OptionList)
        options.clear_options()
        options.add_options(self.shown)
        if self.catalog_loading:
            status = 'Loading Pi models…'
        elif self.load_error:
            status = f'Cannot load Pi models: {self.load_error}\nRetry Refresh models or Configure provider.'
        elif self.models and not self.provider:
            status = 'Choose a provider, or Configure provider to connect.'
        elif self.models:
            status = (f'{len(self.shown)} of {len(provider_models)} Pi models · {self.provider}'
                      if self.shown else 'No matching models. Clear or change your search.')
        else:
            status = 'No Pi models available. Choose a provider and configure login.'
        if self.free_only:
            status = (f'{len(self.shown)} free models across providers. Login may be required; limits apply.'
                      if self.shown else 'No free models match. Clear the search or Refresh models.')
        elif self.shown and any(m not in self.usable_models for m in self.shown):
            status = f'{len(self.shown)} catalog models. Select one to configure its provider if needed.'
        if self.auth_error:
            status = self.auth_error
        self.query_one('#model-status', Static).update(status)

    def refresh_models(self):
        if not self.loader:
            return
        self.invalidate_read()
        self.catalog_loading, self.load_error = True, ''
        self.query_one('#provider', Select).disabled = True
        self.query_one('#models', OptionList).clear_options()
        self.query_one('#model-status', Static).update('Refreshing models from Pi…')
        self.read('models', self.identity, self.loader, self.loaded_models, self.load_failed)

    def action_login(self):
        if not self.agent_dir or not self.is_current or not self.identity_valid() or self.app.view_only:
            return
        provider = self.providers.get(self.provider)
        if not provider:
            self.query_one('#model-status', Static).update(
                self.auth_error or 'Choose a configurable provider first. Refresh to load providers.')
            return
        if not provider['methods']:
            self.query_one('#model-status', Static).update(
                'This provider uses ambient configuration. Configure it through Pi settings or environment.')
            return
        self.invalidate_read()
        def authenticated(success):
            if success and self.is_mounted and self.is_current and self.identity_valid() and not self.app.view_only:
                self.refresh_models()
        self.app.push_screen(ProviderAuth(provider, self.agent_dir, identity_valid=self.identity_valid), authenticated)

    def on_button_pressed(self, event):
        if event.button.id == 'model-none':
            if self.allow_none and not self.app.view_only and self.identity_valid():
                self.dismiss('')
        elif event.button.id == 'model-free':
            self.free_only = not self.free_only
            event.button.label = 'All models' if self.free_only else 'Free models'
            self.query_one('#filter', Input).placeholder = ('Search free models across providers' if self.free_only
                                                           else 'Search this provider\'s models')
            self.on_input_changed(self.query_one('#filter', Input))
        elif event.button.id == 'model-refresh':
            self.refresh_models()
        elif event.button.id == 'model-login':
            event.stop()
            self.action_login()

    def on_input_submitted(self, event):
        """Enter in the filter takes the first match."""
        if self.shown:
            self.choose_model(self.shown[0])

    def on_key(self, event):
        if event.key == 'down' and self.focused is self.query_one('#filter'):
            self.query_one('#models', OptionList).focus()

    def on_option_list_option_selected(self, event):
        model = str(event.option.prompt)
        if model in self.shown:
            self.choose_model(model)

    def choose_model(self, model):
        if self.app.view_only or not self.identity_valid():
            return
        if model not in self.usable_models:
            self.provider = model.partition('/')[0]
            self.query_one('#provider', Select).value = self.provider
            self.action_login()
            return
        self.dismiss(model)

    def action_cancel(self):
        self.dismiss(None)


class LogScreen(ReadScreen, Screen):
    """A bounded journal capture; Raw/Summary changes presentation, never acquisition."""
    BINDINGS = [Binding('escape,q', 'back', 'back'), Binding('v', 'toggle_view', 'Raw/Summary')]
    DEFAULT_CSS = '#journal-status { height: auto; max-height: 3; padding: 0 1; } #full-log { border: round $panel; }'

    def __init__(self, runner, logs):
        super().__init__()
        self.runner, self.logs = runner, logs
        self.raw, self.cached_text, self.journal_error = False, None, ''
        self.captured_at = ''

    def compose(self) -> ComposeResult:
        yield Header()
        yield ViewHeader(f'Activity log · {self.runner.name}', 'Follow events here. Summary groups repeats; Raw keeps every original line.')
        yield MenuBar(id='menubar')
        yield Static('Reading journal…', id='journal-status', markup=False)
        yield RichLog(id='full-log', wrap=True, highlight=False, markup=False)

    def on_mount(self):
        self.title = f'{self.runner.name}: log'
        self.query_one('#full-log').border_title = 'Activity · PgUp/PgDn scroll'
        self.show_mode()
        self.refresh_log()
        self.set_interval(LOG_REFRESH, self.refresh_log)

    def refresh_log(self):
        runner, logs = read_input(self.runner), self.logs
        return self.read('full-log', (runner.name, runner.repo),
                         lambda: logs(runner, 1000), self.show_log, self.log_failed)

    def action_back(self):
        self.app.pop_screen()

    def action_toggle_view(self):
        self.raw = not self.raw
        self.show_mode()
        self.render_log()
        self.query_one('#full-log', RichLog).focus(scroll_visible=False)

    def show_mode(self):
        self.query_one('#menubar', MenuBar).show(
            [('v', 'Summary' if self.raw else 'Raw'), ('esc', 'Back')],
            prefix='Raw' if self.raw else 'Summary',
            click_actions={'v': 'screen.toggle_view', 'esc': 'screen.back'}, explicit_keys=True)

    def log_failed(self, error):
        self.journal_error = str(error)
        self.render_log()

    def show_log(self, text):
        self.cached_text, self.journal_error = text, ''
        self.captured_at = time.strftime('%H:%M:%S')
        self.render_log()

    def render_log(self):
        text = self.cached_text
        lines = ([(line, '') for line in text.splitlines()] if self.raw else fleet_view.log_lines(text)) if text is not None else []
        status = (f'Captured excerpt · last successful read {self.captured_at}' if text is not None else 'Reading journal…')
        if self.journal_error:
            status = (f'Last good capture {self.captured_at} · stale' if text is not None else 'Journal unavailable') + ': ' + self.journal_error
        publish_text(self.query_one('#journal-status', Static), Text(status, style='yellow' if self.journal_error else 'dim'))
        key = (self.raw, lines, self.journal_error)
        if key == getattr(self, '_lines', None):
            return
        self._lines = key
        log = self.query_one('#full-log', RichLog)
        follow, at = log.is_vertical_scroll_end, log.scroll_y
        log.clear()
        for line, style in lines:
            log.write(Text(line, style=style), scroll_end=follow)
        if not lines:
            log.write('(journal unavailable)' if self.journal_error else '(no output yet)' if text is not None else 'Reading journal…',
                      scroll_end=follow)
        if not follow:
            log.call_after_refresh(log.scroll_to, y=at, animate=False, force=True)


class WorkerScreen(ReadScreen, Screen):
    """One worker's actions as a log: oldest first, stamped with the time, new ones appended at the
    bottom so the view keeps its place while you scroll back; refreshed. Each action is colored by
    its kind and kept to one line; w shows long ones whole."""
    BINDINGS = [Binding('escape,q', 'app.pop_screen', 'back'), Binding('w', 'toggle_wrap', 'wrap')]
    DEFAULT_CSS = '#worker-actions { border: round $panel; }'

    def __init__(self, runner, task):
        super().__init__()
        self.runner, self.task_id = runner, task  # Screen.task is Textual's own, read-only
        self.shown = []
        self.cached_actions = []
        self.wrap = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield ViewHeader(f'Worker · {self.task_id}', 'Read the worker’s observed actions. No output does not prove progress.')
        yield MenuBar(id='menubar')
        yield RichLog(id='worker-actions', wrap=True, highlight=False, markup=False)

    def action_toggle_wrap(self):
        self.wrap = not self.wrap
        self.shown = []  # rewrite cached lines, without a read
        self.show_actions(self.cached_actions)

    def on_resize(self, event):
        if not self.wrap:
            self.shown = []  # cut cached lines again to the new width
            self.show_actions(self.cached_actions)

    def on_mount(self):
        self.title = f'{self.runner.name}: {self.task_id}'
        self.query_one('#worker-actions').border_title = 'Observed actions · w expand lines'
        self.query_one('#menubar', MenuBar).show([('w', 'Expand lines'), ('esc', 'Back')], explicit_keys=True)
        self.refresh_actions()
        self.set_interval(LOG_REFRESH, self.refresh_actions)

    def refresh_actions(self):
        runner, task = read_input(self.runner), self.task_id
        return self.read('actions', (runner.repo, task),
                         lambda: [(at, line) for line, _, at in fleet_view.action_log(runner, task)], self.show_actions)

    def show_actions(self, actions):
        self.cached_actions = actions
        if not self.is_mounted:
            return
        log = self.query_one('#worker-actions', RichLog)
        follow, at_row = log.is_vertical_scroll_end, log.scroll_y
        last = self.shown[-1] if self.shown else None
        if last in actions:  # append only what is new; a full redraw would lose the scroll position
            fresh = actions[len(actions) - actions[::-1].index(last):]
        else:
            log.clear()
            fresh = actions
            if not actions:
                log.write('No actions recorded yet.', scroll_end=follow)
        width = 0 if self.wrap else max(20, self.size.width - 4)  # border and scrollbar
        for at, line in fresh:
            stamp = time.strftime('%H:%M:%S', time.localtime(at)) if at is not None else '--:--:--'
            log.write(action_text(line, width, stamp), scroll_end=follow)
        if not follow:
            log.call_after_refresh(log.scroll_to, y=at_row, animate=False, force=True)
        if fresh:
            self.shown = actions


class PrepareRepository(ModalScreen[str]):
    """Preparation may commit a legacy conversion; starting is a separate choice."""
    BINDINGS = [Binding('escape', 'cancel', 'cancel'),
                Binding('left', 'focus_previous', 'previous', show=False),
                Binding('right', 'focus_next', 'next', show=False)]
    DEFAULT_CSS = '''
    PrepareRepository { align: center middle; }
    PrepareRepository > Vertical { width: 84; max-width: 100%; height: auto; border: thick $warning; background: $surface; padding: 1 2; }
    PrepareRepository Horizontal { height: auto; margin-top: 1; }
    PrepareRepository Button { margin-right: 1; }
    '''

    def __init__(self, ready):
        super().__init__()
        self.ready = ready

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(f'{self.ready.repo}\nNot ready: {", ".join(self.ready.problems)}'))
            yield Label('Run autowork tasks prepare? A legacy conversion makes one local commit.\n'
                        'Plan opens the embedded planning console; proposals require separate Review and Apply. '
                        'Neither opening Plan nor Prepare starts a model or invents goals/tasks.')
            yield Label(Text('Choose with ←/→ or Tab; Enter runs it; Esc cancels.', style='dim'))
            with Horizontal():
                yield Button('Prepare', variant='primary', id='prepare')
                yield Button('Prepare and start', id='prepare-start')
                yield Button('Plan', id='plan')
            with Horizontal():
                yield Button('Force', variant='warning', id='force')
                yield Button('Cancel', id='cancel')

    def on_button_pressed(self, event):
        self.dismiss(None if event.button.id == 'cancel' else event.button.id)

    def action_cancel(self):
        self.dismiss(None)

    def action_focus_next(self):
        self.focus_next()

    def action_focus_previous(self):
        self.focus_previous()


class RepoTree(DirectoryTree):
    """Directories only; a repository is marked ready (a committed tasks/ store) or not."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.readiness_cache = {}

    def filter_paths(self, paths):
        return [p for p in paths if p.is_dir() and not p.name.startswith('.')]

    def _populate_node(self, node, content):
        # filter_paths ran on DirectoryTree's loader: every returned path is a
        # directory. Avoid its second synchronous is_dir() pass on the UI loop.
        paths = tuple(content)
        node.remove_children()
        for path in paths:
            node.add(path.name, data=type(node.data)(path), allow_expand=True)
        node.expand()
        self.screen.read_labels(paths)

    def update_readiness(self, ready):
        path = Path(ready.path)
        self.readiness_cache[path] = ready

        def repaint(node):
            if node.data and node.data.path == path:
                node.refresh()  # invalidate Textual's cached row, not just the widget's paint
            else:
                for child in node.children:
                    repaint(child)
        repaint(self.root)

    def render_label(self, node, base_style, style):
        label = super().render_label(node, base_style, style)
        path = node.data.path if node.data else None
        if path in self.readiness_cache:
            ready = self.readiness_cache[path]
            label.append('  ' + ready.mark, style='bold green' if ready.ready else 'yellow')
        return label


class BrowseScreen(ReadScreen, Screen):
    """Pick a repository and start its service."""
    BINDINGS = [Binding('p', 'start', 'Play'), Binding('g', 'plan_selected', 'Plan'),
                Binding('ctrl+l', 'edit_path', 'Path', priority=True),
                Binding('alt+up', 'parent', 'Parent', priority=True),
                Binding('alt+home', 'home', 'Home', priority=True),
                Binding('enter', 'open_directory', 'Open folder', priority=True, show=False),
                Binding('escape,q', 'app.pop_screen', 'back')]
    CSS = '''
    #browser-location { height: 3; }
    #browse-path { width: 1fr; }
    #browser-location Button { width: 9; min-width: 9; padding: 0; }
    #browse-status { height: auto; max-height: 2; padding: 0 1; }
    #browser-body { height: 1fr; }
    #tree, #info-scroll { width: 1fr; }
    #info-scroll { border: round $panel; }
    #tree { border: round $panel; }
    #info { height: auto; padding: 0 1; }
    BrowseScreen.compact #browser-body { layout: vertical; }
    BrowseScreen.compact #tree, BrowseScreen.compact #info-scroll { width: 100%; height: 1fr; }
    BrowseScreen.compact #info-scroll { border-left: none; border-top: solid $panel; }
    '''

    def __init__(self, root, start):
        super().__init__()
        self.root, self.start = root, start
        self.chosen = None
        self.preparing = False
        self.prepare_result = None
        self.chosen_path = None
        self.starting = False
        self.navigating = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield ViewHeader('Choose a project', '1 Open a folder   2 Review readiness   3 Start work')
        yield MenuBar(id='menubar')
        with Horizontal(id='browser-location'):
            yield Input(value=str(self.root or Path.home()), placeholder='Directory path · Enter to open', id='browse-path')
            yield Button('Parent', id='browse-up', tooltip='Open the parent directory (Alt+Up)')
            yield Button('Home', id='browse-home', tooltip='Open your home directory (Alt+Home)')
        yield Static('Enter opens a folder · Ctrl+L edits the path · Alt+↑ goes up', id='browse-status', markup=False)
        with Horizontal(id='browser-body'):
            yield RepoTree(self.root or str(Path.home()), id='tree')
            with VerticalScroll(id='info-scroll'):
                yield Static('Move to a repository; ready ones have a committed tasks/ store.', id='info')

    def on_mount(self):
        self.set_class(self.size.width < 100, 'compact')
        self.title = f'start a runner: {self.root or Path.home()}'
        self.query_one('#menubar', MenuBar).show([('p', 'Start'), ('g', 'Plan'), ('ctrl+l', 'Path'), ('esc', 'Back')], explicit_keys=True)
        self.query_one('#tree', RepoTree).focus()
        if self.root is None:
            home = Path.home()
            def loaded(root):
                self.root = str(root)
                self.query_one('#tree', RepoTree).path = root
                self.query_one('#browse-path', Input).value = str(root)
                self.title = f'start a runner: {root}'
            self.read('browse-root', str(home), lambda: home / 'git' if (home / 'git').is_dir() else home, loaded)

    def on_resize(self, event):
        self.set_class(event.size.width < 100, 'compact')

    def action_edit_path(self):
        address = self.query_one('#browse-path', Input)
        address.focus()
        address.action_select_all()

    def action_parent(self):
        self.navigate_to(Path(self.root or Path.home()).parent)

    def action_home(self):
        self.navigate_to(Path.home())

    def on_button_pressed(self, event):
        if event.button.id in ('browse-up', 'browse-home'):
            event.stop()
            (self.action_parent if event.button.id == 'browse-up' else self.action_home)()

    def on_input_submitted(self, event):
        if event.input.id == 'browse-path':
            event.stop()
            self.navigate_to(event.value)

    def check_action(self, action, parameters):
        if action == 'open_directory':
            return self.focused is self.query_one('#tree', RepoTree)
        return True

    def action_open_directory(self):
        node = self.query_one('#tree', RepoTree).cursor_node
        if node is not None and node.data is not None:
            path = node.data.path
            if str(path) != str(self.root):
                self.navigate_to(path)
            else:
                node.expand()

    def navigate_to(self, value):
        """Change the browser root after a read-only, off-loop directory check."""
        value = str(value).strip()
        self.invalidate_read()
        self.navigating = bool(value)
        if not value:
            self.query_one('#browse-status', Static).update('Enter a directory path, for example ~ or /home.')
            return
        base = Path(self.root or Path.home())
        self.query_one('#browse-status', Static).update(f'Opening {value}…')
        def load():
            path = Path(value).expanduser()
            path = (path if path.is_absolute() else base / path).resolve(strict=True)
            if not path.is_dir():
                raise NotADirectoryError(f'{path} is not a directory')
            with os.scandir(path) as entries:
                next(entries, None)  # also verify permission to list it
            return path
        def loaded(path):
            self.navigating = False
            self.root = str(path)
            self.chosen, self.chosen_path, self.starting = None, None, False
            self.prepare_result = None
            self.query_one('#browse-path', Input).value = str(path)
            tree = self.query_one('#tree', RepoTree)
            tree.path = path
            tree.focus()
            self.title = f'start a runner: {path}'
            self.query_one('#browse-status', Static).update(
                'Enter opens a folder · Ctrl+L edits the path · Alt+↑ goes up')
            self.show_repository(path)
        def failed(error):
            self.navigating = False
            self.query_one('#browse-status', Static).update(f'Cannot open directory: {error}')
        token = self.read('browse-path', (str(base), value), load, loaded, failed)
        self.navigation_read = token
        if token is not None:
            def finished(future):
                if token.cancelled and self.navigation_read is token:
                    self.navigating = False
                    if self.is_mounted and self.is_current:
                        self.query_one('#browse-status', Static).update('Navigation cancelled. Enter a directory path to retry.')
            token.done.add_done_callback(finished)
        return token

    def read_labels(self, paths):
        def load():
            return tuple(fleet_view.readiness(path) for path in paths if (path / '.git').exists())
        def loaded(results):
            tree = self.query_one('#tree', RepoTree)
            for ready in results:
                tree.update_readiness(ready)
        return self.read('directory-labels', tuple(map(str, paths)), load, loaded)

    def on_tree_node_highlighted(self, event):
        node = event.node
        if node.data is None:
            return
        self.show_repository(node.data.path)

    def show_repository(self, path, after=None, failed=None):
        if after:  # a pre-action check must not reuse any read admitted before consent
            self.invalidate_read()
        path = str(path)
        if self.chosen_path != path:
            self.chosen = None
            self.starting = False
        self.chosen_path = path
        self.query_one('#info', Static).update(f'{path}\nReading readiness…')
        def load():
            ready = fleet_view.readiness(path)
            root = bool(ready.repo and Path(ready.path).resolve() == Path(ready.repo).resolve())
            return ready, root
        def loaded(value):
            self.chosen, self.chosen_is_root = value
            self.render_repository(path)
            if after:
                after(self.chosen)
        def unavailable(error):
            self.starting = False
            self.query_one('#info', Static).update(f'{path}\nReadiness unavailable: {error}')
            if failed:
                failed(error)
        return self.read('readiness', path, load, loaded, unavailable)

    def render_repository(self, path):
        if not self.chosen:
            return
        tree = self.query_one('#tree', RepoTree)
        tree.update_readiness(self.chosen)
        info = Text()
        info.append(str(path) + '\n', style='bold')
        if self.chosen.ready:
            info.append('ready', style='bold green')
            info.append(f' on {self.chosen.branch}. Press p to play (start) its service.\n')
        elif not self.chosen.repo:
            info.append('not a Git repository\n', style='dim')
        else:
            info.append(f'not ready: needs {", ".join(self.chosen.problems)}\n', style='bold yellow')
            for hint in fleet_view.how_to_fix(self.chosen):
                info.append(f'  {hint}\n')
            if self.chosen.start_branch:
                info.append(f'Press p to confirm start: safely select local {self.chosen.start_branch}, then recheck readiness.\n')
            else:
                info.append('Press p for Prepare, Prepare and start, Plan (an agent plans the tasks), or Force.\n')
        if self.preparing:
            info.append('\nPreparing repository…\n', style='yellow')
        if self.prepare_result and self.prepare_result[0] == str(path):
            report = self.prepare_result[1]
            info.append('\n' + report['outcome'] + '\n', style='bold')
            for refusal in report.get('refusals', []):
                info.append(str(refusal) + '\n')
            if report.get('forced'):
                info.append('Forced conversion:\n', style='bold')
                step = report['forced'].get('step', {})
                for key in ('stopped', 'set_aside', 'landed', 'committed', 'commit'):
                    if key in step:
                        info.append(f'{key}: {step[key]}\n')
            info.append((report.get('next') or 'Resolve the reported problem, then run Prepare again.') + '\n')
            if report['outcome'] == 'NO_STORE':
                info.append('Plan accepted intent with /docs-sync; no goals or tasks were created.\n')
        self.query_one('#info', Static).update(info)

    def action_start(self):
        if self.app.view_only or self.preparing or self.starting or self.navigating:
            return
        if self.chosen_path is None:
            self.notify('Choose a repository first.', severity='warning')
            return
        self.starting = True
        token = self.show_repository(self.chosen_path, self.ready_to_start)
        if token is not None:
            token.done.add_done_callback(lambda future: setattr(self, 'starting', False))

    def ready_to_start(self, ready):
        self.starting = False
        if not self.chosen_is_root:
            self.notify('Choose a Git repository root.', severity='warning')
        elif self.chosen.ready or self.chosen.start_branch:
            self.start(self.chosen)
        else:
            ready = self.chosen
            self.app.push_screen(PrepareRepository(ready), lambda choice: choice and (
                self.plan(ready.path) if choice == 'plan' else
                self.confirm_force(ready.path) if choice == 'force' else
                self.prepare(ready.path, choice == 'prepare-start')))

    def action_plan_selected(self):
        if self.chosen and self.chosen.repo and not self.navigating:
            self.plan(self.chosen.repo)

    def plan(self, path):
        """Open embedded planning, independent of execution readiness or service state."""
        if not self.app.view_only and not self.preparing:
            self.app.open_plan(str(path))

    def confirm_force(self, path):
        self.app.push_screen(Confirm(Text(
            f'Force conversion of {path}?\n'
            'Force stops the service and live workers, sets attempts aside with worktrees, '
            'branches and files kept, commits planning edits, converts, and restarts the service.')),
            lambda yes: yes and self.prepare(path, False, force=True))

    def prepare(self, path, start, force=False):
        if self.app.view_only or self.preparing:
            return
        self.preparing = True
        self.prepare_result = None
        self.show_repository(path)
        self.run_worker(lambda: self.run_prepare(path, start, force), thread=True, group='prepare')

    def run_prepare(self, path, start, force=False):
        """Run the supported CLI, not a second implementation of conversion or bootstrap."""
        try:
            result = self.app.runner_cmd([self.app.command, 'tasks', 'prepare', *(['--force'] if force else []), path],
                                         env=dict(os.environ), capture_output=True, text=True)
            try:
                report = json.loads(result.stdout)
                if not isinstance(report, dict) or not isinstance(report.get('outcome'), str) or not report['outcome']:
                    raise ValueError('missing preparation outcome')
            except ValueError:
                report = dict(outcome='PREPARE_FAILED', next=(result.stdout or '') + (result.stderr or ''))
            ok = result.returncode == 0 and report.get('ok') and report['outcome'] in ('READY', 'MIGRATED')
        except OSError as error:
            report, ok = dict(outcome='PREPARE_FAILED', next=str(error)), False
        self.app.call_from_thread(self.prepared, path, report, bool(start and ok))

    def prepared(self, path, report, start):
        self.preparing = False
        self.prepare_result = (str(path), report)
        if not self.is_mounted:  # leaving the browser does not undo a CLI conversion in flight
            return
        self.app.invalidate_reads()
        if self.chosen_path == str(path):
            self.show_repository(path, lambda ready: start and ready.ready and self.start(ready))


def save_report(text, directory):
    """Explicit export only: a unique private file, never the repository or clipboard."""
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(prefix='blockers-', suffix='.txt', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(text)
    except BaseException:
        Path(filename).unlink(missing_ok=True)
        raise
    return Path(filename)


class BlockersScreen(Screen):
    """A frozen, copyable report. Refresh is explicit so selection is not disturbed."""
    BINDINGS = [Binding('escape', 'back', 'Back'),
                Binding('a', 'answer_question', 'Answer', priority=True),
                Binding('c', 'copy_report', 'Copy report', priority=True),
                Binding('d', 'toggle_diagnostics', 'Details', priority=True),
                Binding('e', 'export_report', 'Export', priority=True),
                Binding('r', 'refresh_report', 'Refresh', priority=True)]
    DEFAULT_CSS = '''
    BlockersScreen #report-state { height: auto; padding: 0 1; }
    BlockersScreen TextArea { height: 1fr; }
    BlockersScreen Horizontal { height: 3; }
    BlockersScreen Button { margin-right: 0; min-width: 7; width: 1fr; height: 3; padding: 0; }
    '''

    def __init__(self, runner):
        super().__init__()
        self.runner = read_input(runner)
        self.report_text = self.full_report_text = None
        self.diagnostics = self.exporting = False

    def compose(self):
        yield ViewHeader(f'Attention report · {self.runner.name}', 'Read what is blocked. Answer a task, copy the report or inspect evidence.')
        yield MenuBar(id='report-menu')
        yield Static(Text(f'{self.runner.name} — read only; loading…'), id='report-state')
        yield TextArea(read_only=True, show_cursor=False, id='blockers-text')
        with Horizontal():
            yield Button('Answer', id='answer-report', variant='primary')
            yield Button('Copy', id='copy-report', disabled=True)
            yield Button('Details', id='details-report', disabled=True)
            yield Button('Export', id='export-report', disabled=True)
            yield Button('Refresh', id='refresh-report')
            yield Button('Back', id='back-report')

    def on_mount(self):
        self.query_one(MenuBar).show([('a', 'Answer'), ('escape', 'Back'), ('c', 'Copy'), ('d', 'Details'),
                                      ('e', 'Export'), ('r', 'Refresh')], prefix='Blockers', explicit_keys=True)
        self.action_refresh_report()

    def action_refresh_report(self):
        self.query_one('#report-state', Static).update(Text(f'{self.runner.name} — read only; loading…'))
        self.app.request_blockers(self)

    def present_report(self, text):
        self.full_report_text = text
        self.show_report()
        for name in ('copy', 'details', 'export'):
            self.query_one(f'#{name}-report', Button).disabled = name == 'export' and self.exporting

    def show_report(self):
        text = self.full_report_text
        self.report_text = (blockers_report.summary(text)
                            if not self.diagnostics and blockers_report.DIAGNOSTICS in text else text)
        self.query_one(TextArea).load_text(self.report_text)
        self.query_one('#details-report', Button).label = 'Summary' if self.diagnostics else 'Details'
        self.query_one('#report-state', Static).update(Text(
            f'{self.runner.name} — read only report; {"full diagnostics" if self.diagnostics else "summary"}. '
            'Copy/export uses this view. Answer (a) opens these questions in Tasks.'))

    def action_answer_question(self):
        # The report is a frozen read: answering happens in the tasks screens, which own the
        # decision form, its default section and the one-pass dispatch.
        self.app.open_tasks(self.runner, 'decisions')

    def action_toggle_diagnostics(self):
        if self.full_report_text is not None:
            self.diagnostics = not self.diagnostics
            self.show_report()

    def action_copy_report(self):
        if self.report_text is not None:
            try:
                self.app.copy_to_clipboard(self.report_text)
            except Exception as error:
                self.notify(f'Clipboard request failed: {error}. Use Export (e).', severity='error')
            else:
                self.notify('Clipboard requested; paste to verify. If empty, use Export (e).')

    def action_export_report(self):
        if self.report_text is None or self.exporting:
            return
        self.exporting = True
        self.query_one('#export-report', Button).disabled = True
        # App-owned: Escape/Refresh remain responsive, without cancelling an in-flight file write.
        return self.app.run_worker(self._export_report(self.report_text))

    async def _export_report(self, text):
        try:
            if self.app.is_web:
                content = io.StringIO(text)
                try:
                    key = self.app.deliver_text(content, save_filename=f'blockers-{uuid.uuid4().hex}.txt',
                                                encoding='utf-8', mime_type='text/plain', name='blockers-report')
                except Exception:
                    content.close()
                    raise
                if key is None:
                    content.close()
                    raise OSError('no download transport available')
                self.notify('Download requested; completion is not yet confirmed.')
            else:
                path = await asyncio.to_thread(save_report, text, Path(self.app.state_root) / 'reports')
                self.notify(f'Saved on app host (not the SSH client): {path}', timeout=15)
        except Exception as error:
            self.notify(f'Export failed: {error}', severity='error')
        finally:
            self.exporting = False
            if self in self.app.screen_stack and self.is_mounted:
                self.query_one('#export-report', Button).disabled = False

    def action_back(self):
        self.app.pop_screen()

    def on_button_pressed(self, event):
        event.stop()
        {'copy-report': self.action_copy_report, 'details-report': self.action_toggle_diagnostics,
         'export-report': self.action_export_report, 'refresh-report': self.action_refresh_report,
         'answer-report': self.action_answer_question, 'back-report': self.action_back}[event.button.id]()


class WorkflowGuide(ModalScreen):
    """Plain-language orientation; opening help performs no runner action."""
    BINDINGS = [Binding('escape,q', 'close', 'Back')]
    DEFAULT_CSS = """
    WorkflowGuide { align: center middle; }
    WorkflowGuide > Vertical { width: 76; max-width: 100%; height: 90%; border: round $accent; background: $surface; padding: 1 2; }
    #workflow-copy { height: 1fr; }
    """

    def compose(self):
        with Vertical():
            yield ViewHeader('How Autowork works', 'Start with a task. Follow its progress. Act only when the task needs you.')
            with VerticalScroll(id='workflow-copy'):
                yield Static('Model → Project → Tasks → Execution → Checks → Local merge', markup=False)
                yield Static('\nSET UP\nChoose a provider/model and a project. Tasks is your queue of work. Add bounded tasks there; starting a service does not create a task.', markup=False)
                yield Static('\nRUN\nPlay starts the service. It chooses tasks whose dependencies and permissions allow execution. In progress means a task is active. Service running alone does not mean tasks are progressing.', markup=False)
                yield Static('\nREVIEW\nChecks and review must pass before work merges into local main. A failed worker or failed checks needs attention; it is not completed work. An older check does not qualify a newer revision.', markup=False)
                yield Static('\nWHAT TO DO NEXT\nNeeds attention: open Tasks for questions and Details for failures. Waiting: inspect dependencies or resource limits. Unconfirmed: execution observations are not fresh enough to claim progress.', markup=False)
                yield Static('\nPUBLISH\nA local merge is not a GitHub push. The runner publishes only when push is explicitly enabled. Read-only mode disables execution controls.', markup=False)
            yield Button('Back · Esc', id='workflow-back')

    def action_close(self):
        self.dismiss()

    def on_button_pressed(self, event):
        if event.button.id == 'workflow-back':
            event.stop()
            self.dismiss()


class FleetApp(App):
    TITLE = 'autowork'
    # Keep project selection beside work on wide terminals; stack on narrow ones.
    CSS = '''
    Header { background: $panel; }
    #workspace-body { height: 1fr; layout: vertical; }
    #project-context { width: 100%; height: auto; }
    #work-context { width: 100%; height: 1fr; }
    .wide #workspace-body { layout: horizontal; }
    .wide #project-context { width: 25%; min-width: 36; max-width: 40; height: 1fr; }
    .wide #work-context { width: 1fr; height: 1fr; }
    .wide #overview { max-height: 100%; }
    #nav-footer { dock: bottom; height: 1; background: $panel; color: $text-muted; }

    #modelbar { height: 1; padding: 0 1; background: $surface; }
    #empty-state { display: none; height: 1fr; align-horizontal: center; align-vertical: middle; }
    #empty-card { width: 72; max-width: 100%; height: auto; padding: 1 2; border: round $accent; background: $surface; content-align: center middle; }
    #runners, #lanes { background: $surface; }
    #runners, #lanes, #log { border-title-color: $text; border-title-style: bold; }
    #runners { border: round $accent; }
    #runners { height: auto; min-height: 3; max-height: 6; }
    #overview { height: auto; max-height: 6; margin: 0; padding: 0 1; background: $surface; }
    #detail-scroll { display: none; height: 1fr; min-height: 4; border: round $accent; }
    #detail { height: auto; padding: 0 1; }
    #lanes { height: auto; min-height: 3; max-height: 6; border: round $accent; }
    #log { height: 1fr; min-height: 4; border: round $accent; }
    .short #runners, .short #lanes { max-height: 3; }
    .short #overview { max-height: 3; margin: 0; }
    .short #detail-scroll { height: 1fr; }
    '''
    BINDINGS = [
        Binding('h', 'workflow_help', 'Guide', show=False),
        Binding('1', 'focus_panel("runners")', 'Projects', show=False),
        Binding('2', 'focus_panel("lanes")', 'Current work', show=False),
        Binding('3', 'focus_panel("log")', 'Activity', show=False),
        # One key per action, the first letter of its word, shown highlighted in the detail
        # pane (the footer repeated them, cut short). Enter on a runner opens its log too.
        # show=False: the log, worker and browse screens' footers list their own keys, not
        # these (the log's footer offered Play/Pause and Stop, cut off at 'Fallba').
        Binding('l', 'run("l")', 'Log', show=False),
        Binding('p', 'run("p")', 'Play/Pause', show=False),
        Binding('s', 'run("s")', 'Stop', show=False),
        Binding('r', 'run("r")', 'Restart', show=False),
        Binding('m', 'pick_model("model")', 'Model', show=False),
        Binding('f', 'pick_model("fallback")', 'Fallback', show=False),
        Binding('t', 'run("t")', 'Tasks', show=False),
        Binding('i', 'toggle_details', 'Details', show=False),
        Binding('u', 'run("u")', 'Uninstall', show=False),
        Binding('n', 'browse', 'Browse', show=False),
        Binding('?', 'more', 'More', show=False),
        Binding('q', 'quit', 'Quit', show=False),
    ]
    CONTROL = {'run', 'browse', 'pick_model', 'more'}

    def get_system_commands(self, screen):
        yield from super().get_system_commands(screen)
        if isinstance(screen, PickModel):
            if screen.agent_dir and not self.view_only:
                yield SystemCommand('Configure Pi provider', 'Authenticate with OAuth or API key in this TUI',
                                    screen.action_login)
            if screen.loader:
                yield SystemCommand('Refresh Pi models', 'Reload providers and models from Pi',
                                    screen.refresh_models)
            return
        # The palette itself is an overlay; `screen` is the screen that was
        # active when Ctrl+P was pressed, not the palette currently on top.
        if not self.screen_stack or screen is not self.screen_stack[0]:
            return
        runner = self.current()
        yield SystemCommand('Refresh Autowork fleet', 'Read the latest runner state', self.action_refresh)
        yield SystemCommand('Search fleet actions', 'Open the searchable actions menu', self.action_more)
        if not self.view_only:
            yield SystemCommand('Choose provider and model', 'Select a Pi model for a runner',
                                lambda: self.action_pick_model('model'))
            yield SystemCommand('Choose fallback provider and model', 'Select or disable the independent fallback',
                                lambda: self.action_pick_model('fallback'))
            yield SystemCommand('Browse repositories', 'Find and prepare a repository', self.action_browse)
        if runner is not None:
            yield SystemCommand('Open activity log', 'Read recent runner output', lambda: self.action_run('l'))
            yield SystemCommand('Open task inventory', 'Inspect the runner task queue', lambda: self.action_run('t'))
            yield SystemCommand('Toggle runner details', 'Show or hide runner details', self.action_toggle_details)

    def __init__(self, *, command, script, state_root, env_dir, systemctl='systemctl',
                 journalctl='journalctl', agent=None, runner_cmd=subprocess.run, view_only=False, browse_root=None,
                 list_models=fleet_view.models):
        super().__init__()
        self.list_models = list_models
        self.command, self.script = command, script
        self.state_root, self.env_dir = state_root, env_dir
        self.systemctl, self.journalctl = systemctl, journalctl
        self.agent = agent
        self.runner_cmd = runner_cmd
        self.view_only = view_only
        self.browse_root = browse_root
        self.runners = []
        self.fleet_snapshot = None
        self.generation = 0
        self.read_epoch = 0
        self.selected = None
        self.starting_repositories = set()
        self.pending_deletions = {}  # captured identity -> (request generation, success time, recreated)
        self.completed_deletions = {}  # retain action objects: duplicate callbacks are harmless
        self._report_busy = False
        self._report_pending = None
        self.details_open = False
        self.new_model = ''
        self.new_fallback = ''
        self.new_model_agent_dir = portal.service_agent_dir(os.environ)

    def check_action(self, action, parameters):
        """View-only (for example served to a browser on a shared network): no control keys."""
        if action in ('focus_panel', 'workflow_help'):
            return len(self.screen_stack) == 1
        if action == 'more':
            return len(self.screen_stack) == 1
        if action == 'toggle_details':
            return len(self.screen_stack) == 1 and self.current() is not None
        if self.view_only and action in self.CONTROL and parameters not in (('l',), ('t',)):  # read-only views
            return False
        # Over the log, worker or browse screen, the runner keys are off: s while reading a log
        # asked to stop the runner, and p on the browse screen is its own Play.
        if len(self.screen_stack) > 1 and action in self.CONTROL:
            return False
        return True

    # -- layout -----------------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        yield MenuBar(id='menubar')
        yield Static(id='modelbar')
        with Vertical(id='empty-state'):
            yield Static(id='empty-card', markup=False)
        with Vertical(id='workspace-body'):
            with Vertical(id='project-context'):
                yield DataTable(id='runners', cursor_type='row', zebra_stripes=True)
                yield Static(id='overview')
            with Vertical(id='work-context'):
                with VerticalScroll(id='detail-scroll'):
                    yield Static(id='detail')
                yield DataTable(id='lanes', cursor_type='row', zebra_stripes=True)
                yield RichLog(id='log', wrap=True, highlight=False, markup=False)
        yield MenuBar(id='nav-footer')

    # Compact project selection; the selected overview and Details retain all counts.
    # Every open task is in one count bucket. Decision is Needs-decision membership,
    # not necessarily an unanswered owner question.
    RUNNER_COLUMNS = ('Project', 'Status', 'Tasks')
    LANE_COLUMNS = ('Task', 'Status', 'Try', 'For', 'Quiet')
    LANE_TEXT = ('Doing',)
    STATUS_STYLE = {fleet_view.ACTIVE: 'bold green', fleet_view.MERGEABLE: 'bold cyan',
                    fleet_view.WAITING: 'bold yellow', fleet_view.BLOCKER: 'bold red'}

    def on_mount(self):
        self.reads = tui_reads.ReadCoordinator()
        self.reader = self.reads.owner(self.read_done)
        table = self.query_one('#runners', DataTable)
        table.border_title = '1 · Projects — select a project'
        table.add_columns(*self.RUNNER_COLUMNS)
        self.query_one('#lanes', DataTable).add_columns(*self.LANE_COLUMNS, *self.LANE_TEXT)
        self.query_one('#detail-scroll', VerticalScroll).border_title = 'Project details · i back · PgUp/PgDn scroll'
        self.query_one('#log', RichLog).border_title = '3 · Recent activity · Enter full log'
        self.show_navigation()
        self.action_refresh()
        self.refresh_log()
        self.set_interval(REFRESH, self.poll_refresh)
        self.set_interval(LOG_REFRESH, self.refresh_log)
        self.code = None
        self.reload_if_updated()
        self.set_interval(CODE_CHECK, self.reload_if_updated)

    def show_navigation(self):
        focused = getattr(self.focused, 'id', None)
        hint = ('i Back · PgUp/PgDn scroll' if focused == 'detail-scroll' else
                'PgUp/PgDn scroll' if focused == 'log' else '↑↓ select · Enter log') if self.size.width >= 80 else ''
        self.query_one('#nav-footer', MenuBar).show(
            [('1', 'Projects'), ('2', 'Work'), ('3', 'Activity'), ('h', 'Guide'), ('?', 'More'), ('q', 'Quit')],
            prefix=hint, click_actions={'1': 'app.focus_panel("runners")', '2': 'app.focus_panel("lanes")',
                           '3': 'app.focus_panel("log")', 'h': 'app.workflow_help', '?': 'app.more', 'q': 'app.quit'})

    def on_descendant_focus(self, event):
        if self.is_mounted and len(self.screen_stack) == 1:
            self.show_navigation()

    def action_workflow_help(self):
        if len(self.screen_stack) == 1:
            self.push_screen(WorkflowGuide())

    def action_focus_panel(self, panel):
        if len(self.screen_stack) != 1 or panel not in ('runners', 'lanes', 'log'):
            return
        if self.details_open and panel in ('lanes', 'log'):
            self.action_toggle_details()
        widget = self.query_one('#' + panel)
        if widget.display:
            widget.focus()

    async def action_quit(self):
        if hasattr(self, 'planning_hub'):
            await asyncio.to_thread(self.planning_hub.close)
        self.exit()

    def on_unmount(self):
        self.reader.close()
        self.reads.close()
        if hasattr(self, 'planning_hub'):
            self.planning_hub.close()

    def read(self, kind, identity, loader, apply, failed=None):
        token = self.reader.request(kind, identity, self.read_epoch, loader)
        token.apply, token.failed = apply, failed
        return token

    def read_done(self, token, value, error):
        if not self.is_running:
            return
        errors = self.__dict__.setdefault('_read_errors', {})
        if error:
            errors[token.kind] = str(error)
            self.sub_title = ' · '.join(f'{kind}: stale / unavailable: {message}' for kind, message in errors.items())
            self.notify(self.sub_title, severity='warning')
            if token.failed:
                token.failed(error)
        else:
            previous_error = errors.pop(token.kind, None)
            token.apply(value)
            if token.kind == 'journal' and previous_error:
                self.render_fleet()  # remove stale journal provenance without another acquisition

    def invalidate_reads(self):
        self.read_epoch += 1
        self.reader.invalidate()
        for screen in self.screen_stack:
            if hasattr(screen, '_reader'):
                screen._reader.invalidate()
            if isinstance(screen, DecisionScreen):
                screen.refresh_record()

    def action_completed(self, action=None, ok=False):
        if action is not None and action.deletion is not None and ok and id(action) not in self.completed_deletions:
            self.completed_deletions[id(action)] = action
            self.pending_deletions[action.deletion] = (self.generation, time.time(), False)
            self.project_deletions()
            self.render_fleet()
        # Invalidate subscriptions, not physically running slots. Feedback above is
        # already painted before any asynchronous replacement observation can finish.
        self.action_refresh()
        screen = self.screen
        if isinstance(screen, (TasksScreen, TaskScreen)):
            screen.refresh_tasks(getattr(screen, 'follow', None))

    def project_deletions(self):
        projected = []
        for runner in self.runners:
            snap = runner.snapshot
            matching = [(identity.task, state[2]) for identity, state in self.pending_deletions.items()
                        if snap is not None and identity.workspace == snap.workspace
                        and identity.repository_identity == snap.repository_identity]
            deleted = tuple(task for task, recreated in matching if not recreated)
            recreated = tuple(task for task, recreated in matching if recreated)
            projected.append(replace(runner, display_deleted=deleted, display_recreated=recreated)
                             if (deleted, recreated) != (runner.display_deleted, runner.display_recreated) else runner)
        self.runners = projected

    def deletion_pending(self, runner, task):
        return runner is not None and task in runner.display_deleted

    def on_resize(self, event):
        self.screen_stack[0].set_class(event.size.height < 22, 'short')
        self.screen_stack[0].set_class(event.size.width >= 110, 'wide')
        self._shown = {}  # the columns fit the new width
        if self.query_one('#runners', DataTable).columns:  # the first resize comes before on_mount
            # App.size may still be the previous viewport during the resize event.
            self.call_after_refresh(self.render_fleet)  # cached only; never recollect

    @staticmethod
    def fit(text, room):
        """``text`` in ``room`` columns: cut at a word, or mid-word when that keeps far more."""
        if cell_len(text) <= room:
            return text
        if room <= 1:
            return '…' if room else ''
        cut = set_cell_size(text, room - 1).rstrip()
        words = cut.rsplit(' ', 1)[0]
        return (words if len(words) > room * 2 // 3 else cut).rstrip(' ,;:·') + '…'

    def fill(self, table, rows, fixed, text, minimum=16, limits=None, budget=None):
        """Show ``rows`` ({column: (text, style)}) in ``table``. The fixed columns always show,
        whole; the text columns share what the terminal has left, each cut to fit, and the last
        named goes first when fewer than ``minimum`` columns would be left for each. Redrawn only
        when something changed, since a clear-and-rewrite every refresh made the panes flicker."""
        limits = limits or {}
        budget = budget or self.size.width
        width = lambda column: min(limits.get(column, self.size.width),
                                   max([cell_len(column), *(cell_len(row[column][0]) for row in rows)])) + 2
        left = budget - sum(width(c) for c in fixed) - 4  # border and scrollbar
        shown = list(text)
        while shown and left // len(shown) - 2 < minimum:
            shown.pop()
        room = left // max(1, len(shown)) - 2
        columns = (*fixed, *shown)
        cells = [tuple((self.fit(row[c][0], room if c in shown else limits[c])
                        if c in shown or c in limits else row[c][0], row[c][1]) for c in columns)
                 for row in rows]
        shown_before = self.__dict__.setdefault('_shown', {})
        keys = [row.get('_key', row[columns[0]][0]) for row in rows]
        if shown_before.get(table.id) == (columns, cells, keys):
            return False
        shown_before[table.id] = (columns, cells, keys)
        # Auto-sized columns otherwise retain a previous, wider content width.
        table.clear(columns=bool(limits) or tuple(str(c.label) for c in table.columns.values()) != columns)
        if not table.columns:
            table.add_columns(*columns)
        for key, values in zip(keys, cells):
            table.add_row(*(Text(value, style=style) for value, style in values), key=key)
        return True

    def reload_if_updated(self):
        """Start again on new code, between actions and with no dialog open."""
        def loaded(stamp):
            if self.code is None:
                self.code = stamp
            elif stamp != self.code and len(self.screen_stack) == 1 and not any(w.is_running for w in self.workers):
                self.exit('reload')
        return self.read('code', str(CODE), code_stamp, loaded)

    # -- data -------------------------------------------------------------------
    def action_refresh(self):
        # Explicit refresh/action return invalidates diagnostics, not inventory authority.
        self.invalidate_reads()
        return self.refresh_fleet(None)

    def poll_refresh(self):
        return self.refresh_fleet(self.fleet_snapshot)

    def refresh_fleet(self, cached):
        self.generation += 1
        state, env, systemctl, generation = self.state_root, self.env_dir, self.systemctl, self.generation
        previous = read_input(self.fleet_snapshot)
        cached = read_input(cached)
        identities = tuple(self.pending_deletions)
        def load():
            snapshot = fleet_view.collect_for_tui(state, env, systemctl=systemctl, generation=generation,
                                                  cached_preparation=cached, last_good=previous)
            return snapshot, fleet_view.observe_deletions(identities)
        return self.read('fleet', (str(state), str(env), systemctl), load,
                         lambda value: self.publish_fleet(value[0], value[1], generation))

    def publish_fleet(self, snapshot, observations=(), generation=0):
        observation_errors = []
        reconciled = False
        for identity, present, error in observations:
            pending = self.pending_deletions.get(identity)
            if pending is not None and generation > pending[0] and error:
                observation_errors.append(f'{identity.task}: {error}')
            snap = next((s for s in snapshot.snapshots if s.workspace == identity.workspace
                         and s.repository_identity == identity.repository_identity), None)
            if (pending is None or generation <= pending[0] or snap is None
                    or snap.captured_at <= pending[1] or snap.freshness != 'fresh'
                    or snap.pending_paths is None or snap.store is None or present is None):
                continue
            if present and identity.task not in snap.store.tasks:
                # A working-only recreation is disclosed, never added to inventory.
                self.pending_deletions[identity] = (*pending[:2], True)
                reconciled |= not pending[2]
            elif present or identity.task not in snap.store.tasks:
                del self.pending_deletions[identity]
                reconciled = True
        errors = self.__dict__.setdefault('_read_errors', {})
        if observation_errors:
            errors['deletion observation'] = '; '.join(observation_errors)
        elif observations:
            errors.pop('deletion observation', None)
        self.fleet_snapshot = snapshot
        self.runners = list(snapshot.runners)
        self.project_deletions()
        self.render_fleet()
        if reconciled:
            # Pending reads captured their last-good input at request time. Once
            # an overlay retires, do not let those old inputs resurrect its row.
            # The replacement inherits this newly published committed snapshot.
            self.action_refresh()
        self.refresh_log()
        screen = self.screen
        if isinstance(screen, (TasksScreen, TaskScreen)):
            screen.refresh_tasks(getattr(screen, 'follow', None))

    def pane_width(self, *, projects=False):
        """Budget the pending layout too: widget regions lag a terminal resize."""
        width = self.size.width
        if width < 110:
            return width
        sidebar = min(40, max(36, width // 4))
        return sidebar if projects else width - sidebar

    def render_fleet(self):
        self.show_navigation()
        table = self.query_one('#runners', DataTable)
        snapshot_errors = self.fleet_snapshot.errors if self.fleet_snapshot else ()
        read_errors = self.__dict__.get('_read_errors', {})
        welcome = (not self.runners and self.fleet_snapshot is not None
                   and not snapshot_errors and not read_errors)
        self.query_one('#empty-state').display = welcome
        self.query_one('#workspace-body').display = not welcome
        self.query_one('#modelbar').display = not welcome
        for selector in ('#runners', '#overview', '#lanes', '#log'):
            self.query_one(selector).display = not welcome
        keep = self.selected
        budget = self.pane_width(projects=True)
        rows = fleet_view.runner_rows(self.runners)
        for runner, row in zip(self.runners, rows):
            row['Project'] = row['Runner']
            row['Status'] = self.execution_state(runner)
            row['Tasks'] = row['Total']
        task_width = max([len('Tasks'), *(cell_len(row['Tasks'][0]) for row in rows)])
        state_room = min(15, budget - task_width - len('Project') - 10,
                         max([len('Status'), *(cell_len(row['Status'][0]) for row in rows)]))
        name_room = max(1, min(32, budget - state_room - task_width - 10))
        self.fill(table, rows, self.RUNNER_COLUMNS, (),
                  limits={'Project': name_room, 'Status': state_room}, budget=budget)
        names = [r.name for r in self.runners]
        if names:
            row = names.index(keep) if keep in names else 0
            if table.cursor_row != row:
                table.move_cursor(row=row)
            self.selected = names[row]
        else:
            self.selected = None
        counts = ', '.join(f'{n} {state}' for state, n in fleet_view.summary(self.runners))
        attention = fleet_view.attention(self.runners)
        errors = (*(self.fleet_snapshot.errors if self.fleet_snapshot else ()),
                  *(f'{kind}: stale / unavailable: {message}' for kind, message in self.__dict__.get('_read_errors', {}).items()))
        if errors:
            self.sub_title = 'discovery unavailable: ' + ' · '.join(errors)
        elif attention:
            labels = ', '.join(
                f'{r.name} {fleet_view.state_label(r)}'
                for r in attention[:3])
            more = f' +{len(attention) - 3}' if len(attention) > 3 else ''
            self.sub_title = (f'{len(self.runners)} runners · {len(attention)} need attention: '
                              f'{labels}{more}')
        else:
            self.sub_title = (f'{len(self.runners)} runners: {counts}' if self.runners else
                              ('loading runners…' if self.fleet_snapshot is None else 'no runners'))
        self.show_detail()

    def current(self):
        return next((r for r in self.runners if r.name == self.selected), None)

    def on_data_table_row_highlighted(self, event):
        if event.data_table.id == 'runners' and event.row_key is not None and event.row_key.value != self.selected:
            self.selected = event.row_key.value
            self.show_detail()
            self.refresh_log()

    def on_data_table_row_selected(self, event):
        """Enter on a runner (the table takes the key itself): its full-screen log; on a
        worker: its last actions."""
        if event.data_table.id == 'runners':
            self.action_run('l')
        elif event.data_table.id == 'lanes' and event.row_key is not None and self.current() is not None:
            target = self.__dict__.get('_lane_targets', {}).get(event.row_key.value)
            runner = self.current()
            if target and target[:2] == (runner.name, runner.repo):
                self.push_screen(WorkerScreen(runner, target[2]))

    def action_toggle_details(self):
        self.details_open = not self.details_open
        pane = self.query_one('#detail-scroll', VerticalScroll)
        pane.display = self.details_open
        self.query_one('#overview').display = not self.details_open
        (pane if self.details_open else self.query_one('#runners')).focus()
        self.show_detail()

    def primary_action(self, runner):
        view = fleet_view.presentation(runner)
        if runner.setup_label:
            # Starting a runner without a task store only reproduces the refusal.
            return 'i', 'Details'
        if not self.view_only and runner.state in ('paused', 'not running'):
            return 'p', 'Play'
        if self.answerable_questions(runner) or view.label == 'Waiting':
            return 't', 'Tasks'
        if view.label in ('Blocked', 'Task inventory unavailable'):
            return 'i', 'Details'
        return 'l', 'Log'

    @staticmethod
    def execution_state(runner, view=None):
        """Task progress is distinct from the service/maintenance process being alive."""
        view = view or fleet_view.presentation(runner)
        if runner.stop_reason or runner.state in ('paused', 'not running'):
            return view.label, view.style
        if view.counts is None:
            return 'Unavailable', 'yellow'
        if view.inventory_freshness != 'fresh' or view.execution_freshness != 'fresh':
            return ('Unavailable' if view.error_count else 'Unconfirmed'), 'yellow'
        active, mergeable, waiting, blocker, decision, total = view.counts
        if active:
            return 'In progress', 'bold cyan'
        if blocker or decision or runner.questions:
            return 'Needs attention', 'bold yellow'
        if mergeable:
            return 'Ready to merge', 'cyan'
        return 'Waiting', 'yellow'

    def next_hint(self, runner):
        return ' '.join(self.primary_action(runner))

    @staticmethod
    def task_name(runner, task):
        snap = runner.snapshot
        record = snap.store.tasks.get(task) if snap and snap.store else None
        if record and getattr(record, 'title', ''):
            return record.title
        return next((row.short for row in fleet_view.inventory_rows(runner) if row.task == task), task)

    @staticmethod
    def main_check_text(runner, view):
        # Keep process-identity validation in the receipt renderer, not in this UI.
        text = fleet_view.main_check.line(runner.main_check)
        if not text:
            return ''
        check = view.main_check
        if check.superseded and check.current_revision[:7] not in text:
            text += f'; superseded by main at {check.current_revision[:7]}'
        if check.started is not None:
            text += ' · original start ' + fleet_view.ago(max(0, int(time.time() - check.started)))
        return text

    def show_overview(self, runner):
        """Bounded preview only; Details retains complete identity and original evidence."""
        if runner is None:
            return
        view = fleet_view.presentation(runner)
        text = Text()
        def line(value, style=''):
            text.append(self.fit(value, max(1, self.size.width - 2)) + '\n', style)
        label, style = self.execution_state(runner, view)
        service = fleet_view.service_text(runner)
        context = (f' · Next: {self.next_hint(runner)}' if self.size.height < 22
                   else f' · service {service or "not observed"}')
        phase, evidence, intervention = fleet_view.progress_summary(runner, view)
        line(f'{runner.name} · {label}' + context, style)
        counts = view.counts
        diagnostics = f'{view.error_count} errors · {view.source_note_count} notes'
        provenance = f'Inventory {view.inventory_freshness} · execution {view.execution_freshness}'
        if counts is None:
            count_line = fleet_view.count_text(runner)
        else:
            active, mergeable, waiting, blocker, decision, total = counts
            count_line = f'{total} open · {active} in progress · {mergeable} ready to merge'
            if view.inventory_freshness != 'fresh' or view.execution_freshness != 'fresh':
                count_line = 'Last observed: ' + count_line
        check = self.main_check_text(runner, view)
        why = view.explanation
        skew_text = build.warning()
        if self.size.height < 22:
            if counts is None:
                line(count_line + ' · ' + diagnostics, 'yellow')
            elif (view.error_count or view.source_note_count or view.inventory_freshness != 'fresh'
                  or view.execution_freshness != 'fresh'):
                line(diagnostics + ' · ' + provenance, 'yellow' if view.error_count else 'dim')
            else:
                line(count_line + ' · ' + provenance, 'dim')
            line('Main: ' + check if check else 'Why: ' + why)
            if skew_text:
                line('Build: ' + skew_text, 'bold yellow')
        else:
            line('Now: ' + phase + ' · ' + count_line, 'bold cyan')
            if view.execution_freshness != 'fresh' or view.inventory_freshness != 'fresh' or view.error_count:
                evidence = diagnostics + ' · ' + provenance
            line(evidence, 'yellow' if phase in ('Quiet worker', 'Unconfirmed') else '')
            line(intervention, 'dim' if counts and counts[0] else 'bold yellow')
            line('Main: ' + check if check else 'Main: no check result observed',
                 'bold red' if runner.main_check.get('state') in ('red', 'broken') else '')
            line('Publish: ' + ('automatic push enabled' if runner.push else 'local only · automatic push disabled'), 'dim')
            if skew_text:
                line('Build: ' + skew_text, 'bold yellow')
        text.rstrip()
        publish_text(self.query_one('#overview', Static), text)

    def show_detail(self):
        detail = self.query_one('#detail', Static)
        runner = self.current()
        menubar = self.query_one('#menubar', MenuBar)
        # Mouse mode and keyboard use the same bindings and check_action guards.
        clicks = {key: 'app.' + binding.action for binding in self.BINDINGS for key in binding.key.split(',')}
        modelbar = Text(no_wrap=True, overflow='ellipsis')
        if not self.view_only:
            modelbar.append('[m] Choose model', style=Style(bold=True, color='cyan', meta={'@click': 'app.pick_model("model")'}))
            modelbar.append(' · ')
            modelbar.append('[f] Fallback', style=Style(bold=True, color='cyan', meta={'@click': 'app.pick_model("fallback")'}))
            modelbar.append(' · ')
        else:
            modelbar.append('Model (read only) · ', style='dim')
        model = runner.model if runner and runner.has_service else self.new_model
        modelbar.append(model or 'Select a Pi model for a new runner', style='bold' if model else 'dim')
        if model:
            fallback = runner.fallback if runner and runner.has_service else self.new_fallback
            if runner and runner.has_service and fleet_view.read_env(
                    Path(self.env_dir) / f'{runner.name}.env').get('PI_AUTOWORK_NO_FALLBACK') == '1':
                fallback = ''
            modelbar.append(' · fallback ' + (fallback or 'disabled'), style='dim')
        publish_text(self.query_one('#modelbar', Static), modelbar)
        welcome = self.query_one('#empty-state')
        welcome.display = (runner is None and self.fleet_snapshot is not None
                           and not self.fleet_snapshot.errors
                           and not self.__dict__.get('_read_errors', {}))
        self.query_one('#modelbar').display = not welcome.display
        self.query_one('#workspace-body').display = not welcome.display
        self.query_one('#nav-footer').display = not welcome.display
        self.query_one('#overview').display = not welcome.display and not self.details_open
        self.query_one('#detail-scroll').display = self.details_open and runner is not None
        self.query_one('#log').display = not welcome.display and not self.details_open
        self.show_overview(runner)
        if runner is None:
            errors = (*(self.fleet_snapshot.errors if self.fleet_snapshot else ()),
                      *(f'{kind}: stale / unavailable: {message}'
                        for kind, message in self.__dict__.get('_read_errors', {}).items()))
            if errors:
                message = 'Discovery unavailable: ' + ' · '.join(errors)
            elif self.fleet_snapshot is None:
                message = 'Loading pi-autowork runners…'
            else:
                message = ('No runners are available to inspect.\nThis fleet view is read only.' if self.view_only else
                           'No runners are available yet.')
            if welcome.display:
                card = Text()
                if self.view_only:
                    card.append('READ ONLY  /  EMPTY FLEET\n\n', style='bold cyan')
                    card.append('No runners are available to inspect.\n', style='bold')
                    card.append('This view is read only.', style='dim')
                else:
                    card.append('AUTOWORK  /  GETTING STARTED\n\n', style='bold cyan')
                    card.append('Start your first runner\n', style='bold')
                    card.append('Choose a model and a project to get going.\n\n', style='dim')
                    card.append('m', style='bold underline cyan')
                    card.append('  Choose provider and model\n')
                    card.append('n', style='bold underline cyan')
                    card.append('  Browse for a project\n\n')
                    if self.new_model:
                        card.append('Selected model  ', style='dim')
                        card.append(self.new_model + '\n', style='bold green')
                    card.append('Autowork checks the project before starting.', style='dim')
                publish_text(self.query_one('#empty-card', Static), card)
            publish_text(detail, Text(message))
            publish_text(self.query_one('#overview', Static), Text(message))
            self.query_one('#lanes', DataTable).display = False
            menubar.show([('ctrl+p', 'Commands'), ('?', 'Help'), ('q', 'Quit')] if self.view_only else
                         [('m', 'Model'), ('n', 'Browse'), ('ctrl+p', 'Commands'),
                          ('?', 'Help'), ('q', 'Quit')],
                         click_actions=clicks)
            return
        primary = self.primary_action(runner)
        routes = [primary, ('l', 'Log'), ('t', 'Tasks'),
                  ('i', 'Summary' if self.details_open else 'Details'), ('?', 'More actions')]
        if self.size.width >= 100:
            routes.append(('h', 'Guide'))
        menubar.show(list(dict(routes).items()), prefix='view only' if self.view_only else '',
                     click_actions=clicks, explicit_keys=True)
        text = Text()
        view = fleet_view.presentation(runner)
        text.append(f'{runner.name}  ', style='bold')
        text.append(view.label + (' — ' + view.explanation if view.explanation else '') + '\n', style=view.style)
        detail_row(text, 'Next', self.next_hint(runner))
        vector = fleet_view.task_counts(runner)
        if vector is None:
            detail_row(text, 'Tasks', fleet_view.count_text(runner), 'bold yellow')
        else:
            active, mergeable, waiting, blocker, decision, total = vector
            detail_row(text, 'Tasks', f'{total} open · {active} active · {mergeable} mergeable · {waiting} waiting · {blocker} blocker'
                       + f' · {decision} in Needs decision')
        snap = runner.snapshot
        detail_row(text, 'Inventory', f'{view.inventory_freshness} · revision {view.revision or "unknown"}'
                   f' · generation {view.generation} · captured {fleet_view.ago(max(0, int(time.time() - view.captured_at)))}'
                   f' · execution {view.execution_freshness}', 'dim')
        if snap.engine_source.observed_at is not None:
            detail_row(text, 'Execution', fleet_view.ago(max(0, int(time.time() - snap.engine_source.observed_at))), 'dim')
        detail_row(text, 'Pending', 'unknown' if snap.pending_paths is None else
                   f'{len(snap.pending_paths)} paths (working tree, independently observed)', 'dim')
        if snap.questions_workspace:
            detail_row(text, 'Questions', snap.questions_workspace + '/BLOCKERS.md (working tree, independently observed)', 'dim')
        if runner.display_deleted:
            detail_row(text, 'Deletion', 'pending commit: ' + ', '.join(runner.display_deleted), 'yellow')
        if runner.display_recreated:
            detail_row(text, 'Restored', 'pending record (not committed): ' + ', '.join(runner.display_recreated), 'yellow')
        for row in fleet_view.inventory_rows(runner):
            detail_row(text, 'Task', f'{self.task_name(runner, row.task)} · {row.task}')
            detail_row(text, 'State', row.state + ' · ' + row.why)
        for lane in runner.lanes:
            detail_row(text, 'Observation', f'{lane.task} · {fleet_view.lane_status(runner, lane)[0]} · {doing(lane)}'
                       f' · attempt {lane.attempt} · {fleet_view.duration(lane.minutes)} elapsed · {fleet_view.quiet(lane)}')
        if runner.triage_failures:
            detail_row(text, 'Recovery', fleet_view.recovery_detail(runner), 'bold yellow')
        if runner.preparation is not None:
            audit = runner.preparation
            detail_row(text, 'Preparation', f'{audit.state} · diagnostic audit {fleet_view.ago(max(0, int(time.time() - audit.observed_at)))}'
                       + ' (30s max cache; not Start authority)', 'dim')
        waiting = fleet_view.waiting_detail(runner)
        if waiting:
            detail_row(text, 'Waiting', waiting)
        blockers = fleet_view.blocker_parts(runner, {q.id for q in runner.questions})
        if blockers:
            detail_row(text, 'Blocker', blockers, 'bold red')
        if runner.questions:  # what the owner can answer, easiest first (BLOCKERS.md)
            count = len(runner.questions)
            detail_row(text, 'Questions', fleet_view.question_summary(runner)
                + '  (t Tasks opens questions and reports)', 'bold yellow')
            for q in runner.questions[:QUESTIONS_SHOWN]:
                text.append(' ' * 12)
                text.append(q.id, style='bold')
                text.append(f'  {q.effort}, unblocks {q.unblocks}\n', style='dim')
                text.append(' ' * 14 + q.needs + '\n')
            if count > QUESTIONS_SHOWN:
                text.append(' ' * 12 + f'+{count - QUESTIONS_SHOWN} more\n', style='dim')
        checked = self.main_check_text(runner, view)
        if checked:
            detail_row(text, 'Main', checked, 'bold red' if checked.startswith('main red') else '')
            detail_row(text, 'Check source', f'{view.main_check.checked_revision or "unknown"}'
                       f' · current main {view.main_check.current_revision or "unknown"}', 'dim')
        repair = fleet_view.maintainer_line(runner)
        if repair:
            detail_row(text, 'Maintainer', repair, 'cyan')
        # Short model names; full identifiers remain in the model picker.
        detail_row(text, 'Repository', tilde(runner.repo) or '(unknown)', 'dim')
        if runner.model:
            detail_row(text, 'Model', f'{runner.model.rsplit("/", 1)[-1]} · fallback {runner.fallback.rsplit("/", 1)[-1]}', 'dim')
        detail_row(text, 'Push', 'enabled' if runner.push else 'disabled', 'dim')
        runtimes = build.report()
        detail_row(text, 'Build', build.line(runtimes), 'bold yellow' if build.skew(runtimes) else 'dim')
        if runner.toolset_problem:
            detail_row(text, 'Toolset', runner.toolset_problem, 'bold red')
        elif runner.toolset:  # a development checkout instead of the Pi package: say so
            detail_row(text, 'Toolset', f'{runner.toolset} (PI_AUTOWORK_TOOLSET, not the Pi package)', 'yellow')
        if view.diagnostics:
            detail_row(text, 'Diagnostics', f'{view.error_count} errors · {view.source_note_count} source notes'
                       f' · {sum(len(g.originals) for g in view.diagnostics if g.kind == "source")} source observations')
        for group in view.diagnostics:
            label = 'Errors' if group.kind == 'error' else 'Source notes'
            detail_row(text, label, f'{group.category}: {len(group.messages)} unique / {len(group.originals)} observations',
                       'bold red' if group.kind == 'error' else 'dim')
            for original in group.originals:
                text.append('  ' + original + '\n')
        publish_text(detail, text)
        self.show_lanes(runner)

    def show_lanes(self, runner):
        """Names are display only; stable keys and action targets retain repository/task identity."""
        table = self.query_one('#lanes', DataTable)
        keep = (table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value if table.rows else None)
        selected = self.__dict__.get('_lane_targets', {}).get(keep)
        rows, targets = [], {}
        joined = set(runner.snapshot.joined_lanes)
        tasks = {row.task for row in fleet_view.inventory_rows(runner)}
        for lane in runner.lanes:
            activity = doing(lane)
            matched = lane.task in tasks and (lane.task, lane.attempt, lane.phase) in joined
            key = json.dumps([runner.name, runner.repo, lane.task, lane.attempt])
            while key in targets:
                key += ':'  # identical duplicate observations still target the same task
            targets[key] = (runner.name, runner.repo, lane.task)
            rows.append({'_key': key, 'Task': (self.task_name(runner, lane.task) if matched else lane.task, ''),
                         'Status': fleet_view.lane_status(runner, lane),
                         'Try': (str(lane.attempt), ''), 'For': (fleet_view.duration(lane.minutes), ''),
                         'Quiet': (fleet_view.quiet(lane).removeprefix('quiet '), 'bold yellow'),
                         'Doing': (activity, fleet_view.action_style(activity))})
        self._lane_targets = targets
        table.border_title = (f'2 · Current work · {len(runner.lanes)} observed · Enter log' if runner.lanes
                              else '2 · Current work · no workers observed')
        budget = self.pane_width()
        compact = budget < 120
        for row in rows:
            status, style = row['Status']
            if status.startswith('Annotation · '):
                row['Status'] = ('Unconfirmed · ' + status.removeprefix('Annotation · ').removesuffix(' (unmatched execution)'), style)
        # One shared width budget: names cannot push state or navigation off screen.
        name_room = max(12, budget // 2 - 5) if compact else min(48, budget // 3)
        state_room = max(12, budget - name_room - 8) if compact else 32
        if self.fill(table, rows, ('Task', 'Status') if compact else self.LANE_COLUMNS,
                     () if compact else self.LANE_TEXT,
                     limits={'Task': name_room, 'Status': state_room}, budget=budget) and rows:
            keys = list(targets)
            fallback = next((i for i, key in enumerate(keys) if targets[key] == selected), 0)
            table.move_cursor(row=keys.index(keep) if keep in keys else fallback)
        table.display = not self.details_open

    def logs(self, runner, lines=200, since=None):
        return fleet_view.logs(runner, lines=lines, journalctl=self.journalctl, since=since, strict=True)

    def refresh_log(self):
        """The last hour, folded and counted (fleet_view.log_lines); rewritten only when it changed."""
        log = self.query_one('#log', RichLog)
        runner = self.current()
        if runner is None:
            self.reader.current.pop('journal', None)
            self.reads.retire()
            self._log_identity, self._log, self._journal_lines = None, None, None
            log.clear()
            return
        identity = (runner.name, runner.repo)
        if identity != getattr(self, '_log_identity', None):
            self._log_identity, self._log, self._journal_lines = identity, None, None
            log.clear()
            log.write(f'{runner.name}: reading journal…')
        runner, journal = read_input(runner), self.journalctl
        return self.read('journal', (runner.name, runner.repo),
                         lambda: fleet_view.activity_lines(fleet_view.logs(runner, lines=400, journalctl=journal, since='-60min', strict=True), current_session=True),
                         lambda lines: self.show_log(runner.name, lines),
                         lambda error: self.show_log(runner.name, self._journal_lines, str(error)))

    def show_log(self, name, lines, error=''):
        log = self.query_one('#log', RichLog)
        if not error:
            self._journal_lines = lines
            self._journal_at = time.strftime('%H:%M:%S')
        key = (name, lines, error)
        if key == getattr(self, '_log', None):
            return
        self._log = key
        follow, at = log.is_vertical_scroll_end, log.scroll_y
        log.clear()
        if error:
            source = f'Last good journal {self._journal_at} · stale' if lines is not None else 'Journal unavailable'
            log.write(Text(f'{source}: {error}', style='yellow'), scroll_end=follow)
        for line, style in lines or []:
            log.write(Text(line, style=style), scroll_end=follow)
        if not lines and not error:
            log.write('(nothing in the last hour; Enter shows the whole log)', scroll_end=follow)
        if not follow:
            log.call_after_refresh(log.scroll_to, y=at, animate=False, force=True)

    # -- actions ----------------------------------------------------------------
    def action_more(self):
        if len(self.screen_stack) != 1:
            return
        runner = self.current()
        identity = (runner.name, runner.repo) if runner else None
        if self.view_only:
            actions = ([('l', 'Log'), ('t', 'Tasks'), ('i', 'Details')] if runner else [])
        else:
            actions = ([(action.key, action.label) for action in self.available(runner)]
                       + [('i', 'Summary' if self.details_open else 'Details')]
                       if runner else [('m', 'Choose provider and model')])
            if not any(key == 'm' for key, label in actions):
                actions += [('m', 'Choose provider and model')]
            if not any(key == 'f' for key, label in actions):
                actions += [('f', 'Choose fallback provider and model')]
            actions += [('n', 'Browse repositories')]
        actions += [('q', 'Quit')]
        keys = {key for key, label in actions}

        async def chosen(key):
            if key not in keys:
                return
            current = self.current()
            if key not in ('n', 'q') and ((current.name, current.repo) if current else None) != identity:
                self.notify('Runner selection changed. Reopen More for the current runner.', severity='warning')
                return
            action = {'m': 'pick_model("model")', 'f': 'pick_model("fallback")', 'i': 'toggle_details',
                      'n': 'browse', 'q': 'quit'}.get(key, f'run("{key}")')
            await self.run_action(action)
        self.push_screen(ActionMenu(actions), chosen)

    def available(self, runner):
        return [action for action in fleet_view.actions(
            runner, command=self.command, script=self.script, agent=self.agent)
            if action.key not in ('a', 'b', 'e', 'f', 'g')]

    def answerable_questions(self, runner):
        editable = {row.task for row in fleet_view.inventory_rows(runner)}
        found = {}
        for question in runner.questions:
            if question.id in editable and not self.deletion_pending(runner, question.id):
                found.setdefault(question.id, question)
        return list(found.values())

    def open_plan(self, repo, task=None, mode='plan'):
        if not self.view_only:
            self.push_screen(PlanScreen(repo, task=task, mode=mode))

    def open_tasks(self, runner, view='all'):
        """One owner for opening a runner's tasks, so the read-only blockers report can route
        to the decision form instead of leaving every recorded question unreachable."""
        if not any((r.name, r.repo) == (runner.name, runner.repo) for r in self.runners):
            self.notify('Runner repository changed. Reopen Tasks for the current repository.', severity='warning')
            return
        if isinstance(self.screen, BlockersScreen):
            self.pop_screen()
            if (isinstance(self.screen, TasksScreen)
                    and (self.screen.runner_name, self.screen.repo) == (runner.name, runner.repo)):
                self.screen.action_show_view(view)
                return
        self.push_screen(TasksScreen(runner.name, view, repo=runner.repo))

    def decide_task(self, runner, task):
        current = next((r for r in self.runners if (r.name, r.repo) == (runner.name, runner.repo)), None)
        if self.view_only or current is None or self.deletion_pending(current, task):
            return
        question = next((q for q in current.questions if q.id == task), None)
        self.push_screen(DecisionScreen(current, task, question))

    def on_delivery_complete(self, event):
        if event.name == 'blockers-report':
            event.prevent_default()
            self.notify('Report download transfer completed; check your browser downloads.')

    def on_delivery_failed(self, event):
        if event.name == 'blockers-report':
            event.prevent_default()
            self.notify(f'Report download failed: {event.exception}', severity='error')

    def open_blockers(self, runner):
        """Open a read-only report for the task screen's captured runner."""
        self.push_screen(BlockersScreen(runner))

    def request_blockers(self, screen):
        # One app-owned physical read survives closing a screen. New requests coalesce;
        # cancelling/dismissing a screen must not pretend a blocking read has finished.
        runner = next((r for r in self.runners if (r.name, r.repo) ==
                       (screen.runner.name, screen.runner.repo)), screen.runner)
        self._report_pending = (screen, read_input(runner))
        if not self._report_busy:
            self._start_report()

    def _start_report(self):
        request = self._report_pending
        if request is None:
            return
        screen, runner = request
        self._report_pending = None
        self._report_busy = True
        self.run_worker(self._collect_report(screen, runner), group='blockers-report')

    async def _collect_report(self, screen, runner):
        try:
            text = await asyncio.to_thread(blockers_report.build, runner)
        except asyncio.CancelledError:
            # App shutdown may cancel the await, not the thread. Do not release its slot.
            raise
        except Exception as error:
            text = f'Report unavailable for {runner.name}: {error}\nNo runner action was taken.'
        self._report_busy = False  # the blocking read has actually returned
        if screen in self.screen_stack and screen.is_mounted:
            screen.present_report(text)
        if self._report_pending is not None:
            if self._report_pending[0] in self.screen_stack and self._report_pending[0].is_mounted:
                self._start_report()
            else:
                self._report_pending = None

    def action_run(self, key):
        runner = self.current()
        if runner is None:
            if key == 'p':
                self.action_browse()
            return
        if key == 'l':
            journal = self.journalctl
            self.push_screen(LogScreen(read_input(runner), lambda runner, lines: fleet_view.logs(
                runner, lines=lines, journalctl=journal, strict=True)))
            return
        if key == 't':  # view-only shows the tasks too, without their actions
            self.open_tasks(runner)
            return
        if self.view_only:
            return
        action = next((a for a in self.available(runner) if a.key == key), None)
        if action is None:
            self.notify(f'Nothing to do with "{key}" for {runner.name} right now.', severity='warning')
            return
        if action.confirm:
            self.push_screen(Confirm(action.confirm), lambda yes: yes and self.execute(action))
        else:
            self.execute(action)

    def choose_model_configuration(self, title, current, fallback, *, load, identity, agent_dir, valid, chosen,
                                   fallback_only=False):
        """Stage both choices; publish them together only after summary consent."""
        def usable():
            return not self.view_only and valid()

        def select_fallback(primary):
            if primary is None or not usable():
                chosen(None)
                return
            def selected(value):
                if value is None or not usable():
                    chosen(None)
                    return
                summary = f'{title}\nPrimary: {primary}\nFallback: {value or "disabled (only the primary model)"}'
                def confirmed(yes):
                    chosen((primary, value) if yes and usable() else None)
                self.push_screen(Confirm(summary + '\nApply these model settings?'), confirmed)
            self.push_screen(PickModel(title + ': fallback provider and model', [], fallback,
                                       loader=load, identity=identity, agent_dir=agent_dir,
                                       identity_valid=valid, allow_none=True), selected)

        if fallback_only:
            select_fallback(current)
        else:
            self.push_screen(PickModel(title + ': primary provider and model', [], current,
                                       loader=load, identity=identity, agent_dir=agent_dir,
                                       identity_valid=valid), select_fallback)

    def action_pick_model(self, which):
        if self.view_only:
            return
        runner = self.current()
        if runner is None or not runner.has_service:
            self.pick_new_model(fallback_only=which == 'fallback' and bool(self.new_model))
            return
        name, repo = runner.name, runner.repo
        settings_path = Path(self.env_dir) / f'{name}.env'
        settings = fleet_view.read_env(settings_path)
        list_models, pi = self.list_models, os.environ.get('AUTOWORK_PI', 'pi')
        agent_dir = portal.service_agent_dir(settings)
        def valid():
            selected = self.current()
            return (selected is not None and (selected.name, selected.repo) == (name, repo) and
                    portal.service_agent_dir(fleet_view.read_env(settings_path)) == agent_dir)
        def load():
            if list_models is fleet_view.models:
                return self.model_catalog(lambda: list_models(pi=pi, agent_dir=agent_dir), agent_dir, pi)
            return list_models()
        current = runner.model
        fallback = '' if settings.get('PI_AUTOWORK_NO_FALLBACK') == '1' else runner.fallback
        running = runner.service == 'running'
        def chosen(configuration):
            if configuration is None or self.view_only or not valid():
                return
            primary, fallback = configuration
            argv = [self.command, 'model', name]
            if which == 'model':
                argv.append(primary)
            argv += ['--fallback', fallback] if fallback else ['--no-fallback']
            self.execute(fleet_view.Action('m', f'model settings for {name}', argv))
        self.choose_model_configuration(f'{name}: model settings' + (' (service restarts)' if running else ''),
            current, fallback, load=load, identity=(name, repo, str(settings_path), agent_dir),
            agent_dir=agent_dir, valid=valid, chosen=chosen, fallback_only=which == 'fallback')

    def pick_new_model(self, on_chosen=None, *, fallback_only=False):
        list_models, pi = self.list_models, os.environ.get('AUTOWORK_PI', 'pi')
        agent_dir = self.new_model_agent_dir
        selected = self.current()
        target = (selected.name, selected.repo) if selected else None
        origin = self.screen
        path = getattr(origin, 'chosen_path', None)
        def valid():
            current = self.current()
            return (origin.is_mounted and getattr(origin, 'chosen_path', None) == path and
                    self.new_model_agent_dir == agent_dir and
                    ((current.name, current.repo) if current else None) == target)
        def load():
            return (self.model_catalog(lambda: list_models(pi=pi, agent_dir=agent_dir), agent_dir, pi)
                    if list_models is fleet_view.models else list_models())
        def chosen(configuration):
            if configuration is not None and not self.view_only and valid():
                self.new_model, self.new_fallback = configuration
                self.show_detail()
                if on_chosen:
                    on_chosen(configuration)
            elif on_chosen:
                on_chosen(None)
        self.choose_model_configuration('New runner model settings', self.new_model, self.new_fallback,
            load=load, identity=('new-runner', target, agent_dir), agent_dir=agent_dir,
            valid=valid, chosen=chosen, fallback_only=fallback_only)

    @staticmethod
    def model_catalog(load_models, agent_dir, pi):
        # A failed/empty available-model list must not hide configurable providers.
        model_error = ''
        try:
            models = load_models()
        except Exception:
            models = []
            model_error = 'Pi model catalog unavailable. Configure a provider or retry Refresh models.'
        try:
            catalog = pi_auth.discovery(agent_dir, pi)
            public = catalog.get('models', [])
            return dict(models=sorted(set(models) | {m['id'] for m in public}),
                        usable_models=models, free_models=[m['id'] for m in public if m.get('free')],
                        providers=catalog.get('providers', []), model_error='' if public else model_error)
        except pi_auth.AuthError as error:
            return dict(models=models, providers=[], auth_error=str(error), model_error=model_error)

    def action_browse(self):
        self.push_screen(BrowseScreen(str(self.browse_root) if self.browse_root else None, self.start_repository))

    def start_repository(self, ready):
        if self.view_only or ready.repo in self.starting_repositories:
            return
        self.starting_repositories.add(ready.repo)
        browser = self.screen
        action = fleet_view.Action('a', f'start {Path(ready.repo).name}', [self.command, 'start', ready.repo],
                                   confirm=f'Start a pi-autowork service for {ready.repo}?\n'
                                   'Flow: queued task → isolated worker → checks → merge into main.\n'
                                   'Starting does not guarantee a runnable task or a successful model call.\n'
                                   'Publication follows this repository’s saved push setting; inspect Publish after start.\n'
                                   + (f' Start will safely switch this checkout to local {ready.start_branch} '
                                      'and recheck readiness before starting.' if ready.start_branch else ''))

        def go(yes):
            if not yes:
                self.starting_repositories.discard(ready.repo)
                return
            path = ready.path
            def checked(current):
                self.starting_repositories.discard(ready.repo)
                if (self.view_only or current.repo != ready.repo or current.branch != ready.branch or
                        current.start_branch != ready.start_branch or not (current.ready or current.start_branch)):
                    self.notify('Repository changed or is no longer ready: ' + ', '.join(current.problems), severity='warning')
                    return
                if browser.is_mounted and self.screen is browser:
                    self.pop_screen()
                    self.execute(action)
            if browser.is_mounted and self.screen is browser and browser.chosen_path == path:
                token = browser.show_repository(path, checked)
                if token is not None:
                    # Completion also releases reservations for discarded selection/
                    # owner/epoch results, whose publication callbacks never run.
                    token.done.add_done_callback(lambda future: self.starting_repositories.discard(ready.repo))
                else:
                    self.starting_repositories.discard(ready.repo)
            else:
                self.starting_repositories.discard(ready.repo)
        def model_chosen(configuration):
            if not configuration or self.view_only or not browser.is_mounted or self.screen is not browser:
                self.starting_repositories.discard(ready.repo)
                return
            model, fallback = configuration
            action.env.update(PI_AUTOWORK_PRIMARY=model, PI_AUTOWORK_FALLBACK=fallback,
                              PI_AUTOWORK_NO_FALLBACK='0' if fallback else '1',
                              PI_CODING_AGENT_DIR=self.new_model_agent_dir)
            action.confirm += f' Primary: {model}. Fallback: {fallback or "disabled"}.'
            self.push_screen(Confirm(action.confirm), go)

        async def prepare_model():
            try:
                env_dir, repo = self.env_dir, ready.repo
                def has_settings():
                    return (Path(env_dir) / f'{fleet_view.instance(repo)}.env').is_file()
                saved = await asyncio.to_thread(has_settings)
                if (self.view_only or not browser.is_mounted or self.screen is not browser
                        or browser.chosen_path != ready.path):
                    self.starting_repositories.discard(ready.repo)
                elif saved:
                    self.push_screen(Confirm(action.confirm), go)
                elif self.new_model:
                    model_chosen((self.new_model, self.new_fallback))
                else:
                    self.pick_new_model(model_chosen)
            except OSError as error:
                self.starting_repositories.discard(ready.repo)
                self.notify(f'Cannot read service settings: {error}', severity='error')
            except asyncio.CancelledError:
                self.starting_repositories.discard(ready.repo)
                raise
        self.run_worker(prepare_model(), group='start-model')

    def execute(self, action, on_complete=None):
        env = {**os.environ, **action.env}
        if action.interactive:
            with self.suspend():
                self.runner_cmd(action.argv, env=env)
            self.action_refresh()
            return
        # A restart or stop waits for the runner to stop gracefully (up to the unit's 150 s):
        # run it off the event loop, or the whole TUI freezes and looks crashed.
        self.notify(f'{action.label}: running...', timeout=4)
        self.run_worker(lambda: self.finish_action(action, env, on_complete), thread=True, group='actions')

    def finish_action(self, action, env, on_complete=None):
        """In a worker thread: run the command, then report it on the event loop."""
        try:
            result = self.runner_cmd(action.argv, env=env, capture_output=True, text=True)
        except Exception as error:
            result = error
        outcome = command_results.interpret(action.argv, action.label, result)
        ok, message = outcome.ok, outcome.message
        self.call_from_thread(self.notify, message[:300], severity='information' if ok else 'error',
                              title=f'{action.label}: {"done" if ok else "failed"}', timeout=10 if outcome.decision else 3)
        if on_complete is not None:
            self.call_from_thread(on_complete, ok, message)
        self.call_from_thread(self.action_completed, action, ok)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--command', required=True, help='The autowork launcher, for every action.')
    parser.add_argument('--script', required=True, help='pi-autowork.sh, for set-aside.')
    config = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    state = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local' / 'state')
    parser.add_argument('--state-root', default=os.environ.get('PI_AUTOWORK_STATE_DIR') or f'{state}/pi-autowork')
    parser.add_argument('--env-dir', default=os.environ.get('PI_AUTOWORK_ENV_DIR') or f'{config}/pi-autowork')
    parser.add_argument('--browse-root', default=os.environ.get('AUTOWORK_BROWSE_ROOT'))
    parser.add_argument('--mouse', action='store_true', help='Capture mouse clicks instead of terminal text selection.')
    parser.add_argument('--view-only', action='store_true', help='Show runners; disable every control key.')
    args = parser.parse_args(argv)
    result = FleetApp(command=args.command, script=args.script, state_root=args.state_root, env_dir=args.env_dir,
                      systemctl=os.environ.get('PI_AUTOWORK_SYSTEMCTL', 'systemctl'),
                      journalctl=os.environ.get('AUTOWORK_JOURNALCTL', 'journalctl'),
                      agent=fleet_view.blockers_agent(), view_only=args.view_only, browse_root=args.browse_root).run(mouse=args.mouse)
    if result == 'reload':  # the code was updated: the same view, on the new release
        os.execv(sys.executable, [sys.executable, str(LAYOUT.entrypoint('tui')),
                                  *(sys.argv[1:] if argv is None else argv)])
    return 0


def _compat_main(argv):
    import sys
    previous = sys.argv
    sys.argv = [previous[0], *argv]
    try:
        raise SystemExit(main())
    finally:
        sys.argv = previous
