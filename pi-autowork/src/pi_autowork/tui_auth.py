"""Provider authentication without suspending the terminal or exposing secrets."""
import asyncio
import webbrowser
from urllib.parse import urlsplit

from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from pi_autowork import pi_auth
from pi_autowork.tui_common import ViewHeader


class ProviderAuth(ModalScreen[bool]):
    BINDINGS = [Binding('escape', 'cancel', 'Cancel', priority=True)]
    DEFAULT_CSS = '''
    ProviderAuth { align: center middle; }
    ProviderAuth > Vertical { width: 78; max-width: 100%; height: 95%; border: round $accent; background: $surface; padding: 0 1; }
    #auth-content { height: 1fr; }
    #auth-actions { height: 3; }
    #auth-actions Button { width: auto; min-width: 10; margin-right: 1; }
    #auth-status, #auth-guidance, #auth-prompt { height: auto; }
    ProviderAuth Select { margin-bottom: 0; }
    '''

    def __init__(self, provider, agent_dir, bridge_factory=pi_auth.Bridge, identity_valid=None):
        super().__init__()
        self.provider, self.agent_dir, self.bridge_factory = provider, agent_dir, bridge_factory
        self.bridge, self.worker, self.url = None, None, ''
        self.cancelled = False
        self.identity_valid = identity_valid or (lambda: True)

    def compose(self):
        with Vertical():
            yield ViewHeader('Connect provider · ' + self.provider['id'], 'Choose a sign-in method, then Connect. Credentials stay in your Pi profile.')
            with VerticalScroll(id='auth-content'):
                yield Static('Credentials save in the selected Pi profile. Esc cancels.', markup=False)
                yield Select([('OAuth' if m == 'oauth' else 'API key', m) for m in self.provider['methods']],
                             prompt='Choose authentication method', id='auth-method')
                yield Static('Choose a method, then Connect.', id='auth-status', markup=False)
                yield Static('', id='auth-guidance', markup=False)
                yield Static('', id='auth-prompt', markup=False)
                yield Input(password=True, id='auth-answer', placeholder='No stored secret is shown')
                yield Select([], id='auth-choice', prompt='Choose an option')
            with Horizontal(id='auth-actions'):
                yield Button('Connect', id='auth-connect', variant='primary')
                yield Button('Submit', id='auth-submit', disabled=True)
                yield Button('Browser', id='auth-browser', disabled=True)
                yield Button('Cancel', id='auth-cancel')

    def on_mount(self):
        self.query_one('#auth-answer').display = False
        self.query_one('#auth-choice').display = False
        selector = self.query_one('#auth-method', Select)
        if len(self.provider['methods']) == 1:
            selector.value = self.provider['methods'][0]
        selector.focus()
        self.set_interval(0.25, self.check_identity)

    def check_identity(self):
        if not self.cancelled and (getattr(self.app, 'view_only', False) or not self.identity_valid()):
            self.action_cancel()

    async def authenticate(self, method):
        self.bridge = self.bridge_factory(self.agent_dir)
        try:
            await self.bridge.run('login', self.receive, self.provider['id'], method)
        except asyncio.CancelledError:
            return
        except pi_auth.AuthError as error:
            if self.is_mounted and not self.cancelled:
                self.show_error(str(error))
        finally:
            if self.is_mounted and not self.cancelled:
                self.query_one('#auth-connect', Button).disabled = False
                self.query_one('#auth-method', Select).disabled = False

    def show_error(self, message):
        self.clear_prompt()
        self.url = ''
        self.query_one('#auth-browser', Button).disabled = True
        self.query_one('#auth-guidance', Static).update('')
        self.query_one('#auth-status', Static).update(message)

    def clear_prompt(self):
        field = self.query_one('#auth-answer', Input)
        field.value = ''
        field.display = False
        self.query_one('#auth-choice').display = False
        self.query_one('#auth-prompt', Static).update('')
        self.query_one('#auth-submit', Button).disabled = True

    async def receive(self, event):
        if not self.is_mounted or self.cancelled or not self.is_current:
            return
        if getattr(self.app, 'view_only', False) or not self.identity_valid():
            self.action_cancel()
            return
        kind = event.get('type')
        if kind == 'success':
            self.clear_prompt()
            self.dismiss(True)
        elif kind == 'error':
            # SDK exception messages can contain keys/tokens; only fixed local diagnostics.
            self.show_error('Pi authentication failed. Check credentials or provider access, then retry.')
        elif kind == 'info':
            # Explicit SDK guidance is user-facing; arbitrary SDK exceptions stay hidden.
            guidance = str(event.get('message', ''))
            self.url = ''
            for link in event.get('links', []):
                url = link.get('url', '')
                try:
                    parsed = urlsplit(url)
                except ValueError:
                    continue
                if parsed.scheme == 'https' and parsed.hostname and not parsed.username:
                    guidance += '\n' + str(link.get('label') or 'Documentation') + ': ' + url
                    self.url = self.url or url
            self.query_one('#auth-guidance', Static).update(guidance)
            self.query_one('#auth-browser', Button).disabled = not self.url
        elif kind == 'progress':
            self.query_one('#auth-status', Static).update('Connecting to Pi provider… Esc cancels.')
        elif kind in ('url', 'device'):
            url = event.get('url', '')
            parsed = urlsplit(url)
            self.url = url if parsed.scheme == 'https' and parsed.hostname and not parsed.username else ''
            self.query_one('#auth-browser', Button).disabled = not self.url
            # URL stays only in memory; OAuth callback codes are never echoed.
            guidance = 'Open Browser to authorize with the provider.'
            if kind == 'device':
                guidance += '\nDevice code: ' + str(event.get('code', ''))
            self.query_one('#auth-guidance', Static).update(guidance)
            self.query_one('#auth-status', Static).update('Waiting for authorization… Esc cancels.')
        elif kind == 'clear_prompt':
            self.clear_prompt()
        elif kind == 'prompt':
            self.clear_prompt()
            self.query_one('#auth-prompt', Static).update(event.get('message', 'Enter provider information'))
            if event.get('kind') == 'select':
                field = self.query_one('#auth-choice', Select)
                field.set_options([(item['label'], item['id']) for item in event.get('options', [])])
            else:
                field = self.query_one('#auth-answer', Input)
                # Mask every answer: OAuth codes and provider-specific text may also be sensitive.
                field.password = True
            field.display = True
            field.focus()
            self.query_one('#auth-submit', Button).disabled = False
            self.query_one('#auth-status', Static).update('Enter the requested information, then Submit.')

    async def submit(self):
        if getattr(self.app, 'view_only', False) or not self.identity_valid():
            self.action_cancel()
            return
        if not self.bridge or self.query_one('#auth-submit', Button).disabled:
            return
        choice = self.query_one('#auth-choice', Select)
        answer = choice.value if choice.display else self.query_one('#auth-answer', Input).value
        if answer is Select.NULL or not str(answer).strip():
            self.query_one('#auth-status', Static).update('Enter a value before submitting.')
            return
        self.clear_prompt()
        self.query_one('#auth-status', Static).update('Connecting to Pi provider… Esc cancels.')
        try:
            await self.bridge.answer(str(answer))
        except (OSError, RuntimeError):
            self.show_error('The Pi authentication connection closed. Retry Connect.')

    async def on_input_submitted(self, event):
        event.stop()
        await self.submit()

    async def on_button_pressed(self, event):
        event.stop()
        key = event.button.id
        if getattr(self.app, 'view_only', False) or not self.identity_valid():
            self.action_cancel()
            return
        if key == 'auth-cancel':
            self.action_cancel()
        elif key == 'auth-connect':
            method = self.query_one('#auth-method', Select).value
            if method is Select.NULL or method not in self.provider['methods']:
                self.query_one('#auth-status', Static).update('Choose an authentication method first.')
                return
            self.query_one('#auth-connect', Button).disabled = True
            self.query_one('#auth-method', Select).disabled = True
            self.query_one('#auth-status', Static).update('Connecting to Pi provider… Esc cancels.')
            self.worker = asyncio.create_task(self.authenticate(method))
        elif key == 'auth-submit':
            await self.submit()
        elif key == 'auth-browser' and self.url:
            try:
                opened = await asyncio.to_thread(webbrowser.open, self.url)
                if not opened:
                    self.query_one('#auth-status', Static).update('Browser unavailable. Retry Browser after configuring a browser.')
            except (OSError, webbrowser.Error):
                self.query_one('#auth-status', Static).update('Could not open browser. Retry Browser.')

    def action_cancel(self):
        self.cancelled = True
        self.clear_prompt()
        if self.worker:
            self.worker.cancel()
        self.dismiss(False)

    def on_screen_suspend(self):
        # An overlay must not leave a completed login callback targeting another screen.
        if self.worker and not self.worker.done():
            self.cancelled = True
            self.worker.cancel()
            self.clear_prompt()

    def on_screen_resume(self):
        if self.cancelled and self.is_mounted:
            self.call_after_refresh(lambda: self.is_current and self.dismiss(False))

    def on_unmount(self):
        self.cancelled = True
        if self.worker and not self.worker.done():
            self.worker.cancel()
