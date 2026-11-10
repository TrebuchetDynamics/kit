"""Shared read lifetimes and text widgets; application state stays on self.app."""
from copy import deepcopy as _deepcopy

from rich.text import Text
from rich.style import Style
from textual.widgets import Static

from pi_autowork import fleet_view

REFRESH = 3.0


def read_input(value):
    """Detach mutable runner data; frozen TaskSnapshots are safe to share with readers."""
    runners = value.runners if isinstance(value, fleet_view.FleetSnapshot) else (value,)
    snapshots = list(value.snapshots) if isinstance(value, fleet_view.FleetSnapshot) else []
    snapshots.extend(r.snapshot for r in runners if isinstance(r, fleet_view.Runner) and r.snapshot is not None)
    return _deepcopy(value, {id(snapshot): snapshot for snapshot in snapshots})


def hotkeys(text, keys, click_actions=None):
    """Append 'Log  Pause  Stop', each word's key letter highlighted in it (the first letter
    by convention; a key the word lacks is shown before it)."""
    for number, (key, label) in enumerate(keys):
        text.append('  ' if number else '')
        start = len(text)
        at = label.lower().find(key.lower())
        if at < 0:
            text.append(key, style='bold underline cyan')
            text.append(' ' + label)
        else:
            text.append(label[:at])
            text.append(label[at], style='bold underline cyan')
            text.append(label[at + 1:])
        if click_actions and key in click_actions:
            text.stylize(Style(meta={'@click': click_actions[key]}), start, len(text))


def publish_text(widget, text):
    """Avoid redundant paint requests; include styling and click metadata in equality."""
    previous = getattr(widget, '_published_text', None)
    presentation = ('style', 'justify', 'overflow', 'no_wrap', 'end', 'tab_size')
    if previous is not None and text == previous and all(
            getattr(text, key) == getattr(previous, key) for key in presentation):
        return False
    widget._published_text = text.copy()
    widget.update(text)
    return True


class MenuBar(Static):
    """A screen's keys under its title, wrapping rather than hiding narrow-screen actions."""
    DEFAULT_CSS = 'MenuBar { dock: top; height: auto; max-height: 3; background: $boost; padding: 0 1; }'

    def show(self, keys, prefix='', click_actions=None):
        text = Text(overflow='fold')
        if prefix:
            text.append(prefix + '  ', style='dim')
        hotkeys(text, keys, click_actions)
        publish_text(self, text)


class ReadScreen:
    """Owner-bound subscriptions; workers never receive widgets or the runner list."""
    def read(self, kind, identity, loader, apply, failed=None):
        if not self.is_current:
            return None
        if not hasattr(self, '_reader'):
            self._reader = self.app.reads.owner(self._read_done)
        token = self._reader.request(kind, identity, (self.app.read_epoch, getattr(self, '_read_epoch', 0)), loader)
        token.apply, token.failed = apply, failed
        self.__dict__.setdefault('_read_requests', {})[kind] = token.generation
        return token

    def _read_done(self, token, value, error):
        if not self.app.is_running or not self.is_current:
            return
        if not self.is_mounted:
            # A screen's first read can finish while Compose/Mount is still running.
            # Keep the accepted result for publication after mounting; a changed
            # owner, epoch or screen clears it before it can be applied.
            self.__dict__.setdefault('_pending_reads', {})[token.kind] = (token, value, error)
            self.call_after_refresh(self._flush_pending_reads)
            return
        self._publish_read(token, value, error)

    def _on_mount(self, event):
        # Mount dispatch finishes after this hook, so publish pending reads after
        # Textual has marked the screen mounted and completed its first refresh.
        if self.__dict__.get('_pending_reads'):
            self.call_after_refresh(self._flush_pending_reads)

    def _flush_pending_reads(self):
        pending = self.__dict__.get('_pending_reads')
        if not pending or not self.app.is_running or not self.is_current or not self.is_mounted:
            return
        self._pending_reads = {}
        owner, requests = getattr(self, '_reader', None), self.__dict__.get('_read_requests', {})
        for kind, (token, value, error) in pending.items():
            # The coordinator records an applied generation before publish, so
            # accepts() is already false by the time a pre-mount result is applied.
            if owner is None or owner.closed or token.cancelled or requests.get(kind) != token.generation:
                continue
            if owner.current.get(kind) == (token.identity, token.epoch):
                self._publish_read(token, value, error)

    def _publish_read(self, token, value, error):
        errors = self.__dict__.setdefault('_read_errors', {})
        if error:
            errors[token.kind] = str(error)
            self.sub_title = ' · '.join(f'{kind}: stale / unavailable: {message}' for kind, message in errors.items())
            self.notify(self.sub_title, severity='warning')
            if token.failed:
                token.failed(error)
        else:
            errors.pop(token.kind, None)
            self.sub_title = ' · '.join(f'{kind}: stale / unavailable: {message}' for kind, message in errors.items())
            token.apply(value)

    def invalidate_read(self):
        self.__dict__.pop('_pending_reads', None)
        self.__dict__.pop('_read_requests', None)
        self._read_epoch = getattr(self, '_read_epoch', 0) + 1
        if hasattr(self, '_reader'):
            self._reader.invalidate()

    def on_screen_suspend(self):
        self.invalidate_read()

    def on_screen_resume(self):
        if self.is_mounted:
            for method in ('refresh_record', 'refresh_tasks', 'refresh_actions', 'refresh_log'):
                if hasattr(self, method):
                    getattr(self, method)()
                    break

    def on_unmount(self):
        self.__dict__.pop('_pending_reads', None)
        self.__dict__.pop('_read_requests', None)
        if hasattr(self, '_reader'):
            self._reader.close()


def action_text(line, width=0, stamp=None):
    """One action as a colored line (fleet_view.action_style), cut to ``width`` (0: whole)."""
    text = Text()
    if stamp is not None:
        text.append(stamp + '  ', style='dim')
        width = max(0, width - len(stamp) - 2) if width else 0
    text.append(fleet_view.fit_line(line, width), style=fleet_view.action_style(line))
    return text
