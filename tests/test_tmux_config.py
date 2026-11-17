"""Load the SSH profile in an isolated tmux server, never the user's server."""
import os
from pathlib import Path
import shutil
import shlex
import time
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'tmux/tmux.conf'
COPY = ROOT / 'tmux/copy.sh'


@unittest.skipUnless(shutil.which('tmux'), 'tmux is not installed')
class TmuxConfigTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='aw-tmux-')
        self.addCleanup(self.folder.cleanup)
        self.socket = str(Path(self.folder.name) / 'socket')
        self.env = {**os.environ, 'HOME': self.folder.name, 'TMUX_SLOW': '0'}
        self.env.pop('TMUX', None)
        for name in ('DISPLAY', 'WAYLAND_DISPLAY'):
            self.env.pop(name, None)
        self.addCleanup(lambda: subprocess.run(
            ['tmux', '-S', self.socket, 'kill-server'], env=self.env,
            capture_output=True, timeout=10))
        self.tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'test')
        result = self.tmux('source-file', str(CONFIG))
        self.assertEqual(result.stderr, '')

    def tmux(self, *args):
        result = subprocess.run(['tmux', '-S', self.socket, *args],
                                env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_mouse_release_copies_and_exits(self):
        self.assertEqual(self.tmux('show-options', '-gv', 'mouse').stdout.strip(), 'on')
        for table in ('copy-mode', 'copy-mode-vi'):
            with self.subTest(table=table):
                binding = self.tmux('list-keys', '-T', table, 'MouseDragEnd1Pane').stdout
                self.assertIn('send-keys -X copy-pipe-and-cancel', binding)

    def test_copy_uses_helper_and_clipboard_remains_available_over_ssh(self):
        for key in ('y', 'Enter'):
            binding = self.tmux('list-keys', '-T', 'copy-mode-vi', key).stdout
            self.assertIn('copy-pipe-and-cancel', binding)
        self.assertEqual(self.tmux('show-options', '-sv', 'set-clipboard').stdout.strip(), 'external')
        self.assertIn('/.tmux/copy.sh', self.tmux('show-options', '-sv', 'copy-command').stdout)

    def test_drag_end_copies_line_using_session_display(self):
        home = Path(self.folder.name)
        helper = home / '.tmux/copy.sh'
        helper.parent.mkdir()
        shutil.copy2(COPY, helper)
        tools = home / 'bin'
        tools.mkdir()
        output = home / 'clipboard'
        xsel = tools / 'xsel'
        xsel.write_text('#!/bin/sh\n[ "$*" = "-ib" ] || exit 91\n'
                        '[ "$DISPLAY" = "session-display" ] || exit 92\n'
                        f'/bin/cat > {shlex.quote(str(output))}\n')
        xsel.chmod(0o755)
        self.tmux('set-environment', '-t', 'test', 'DISPLAY', 'session-display')
        self.tmux('set-environment', '-t', 'test', 'PATH', f'{tools}:' + os.environ['PATH'])
        self.assertNotIn('DISPLAY=', self.tmux('show-environment', '-g').stdout)
        probe = 'Kit clipboard probe'
        pane = self.tmux('new-window', '-d', '-P', '-F', '#{pane_id}',
                         f"printf '{probe}\\n'; exec sleep 60").stdout.strip()
        deadline = time.monotonic() + 5
        while probe not in self.tmux('capture-pane', '-p', '-t', pane).stdout:
            self.assertLess(time.monotonic(), deadline, 'probe never appeared in tmux pane')
            time.sleep(0.02)
        self.tmux('copy-mode', '-t', pane)
        for action in ('history-top', 'start-of-line', 'begin-selection', 'end-of-line'):
            self.tmux('send-keys', '-t', pane, '-X', action)
        binding = self.tmux('list-keys', '-T', 'copy-mode-vi', 'MouseDragEnd1Pane').stdout
        command = shlex.split(binding.split('MouseDragEnd1Pane', 1)[1])
        self.tmux(command[0], '-t', pane, *command[1:])
        deadline = time.monotonic() + 5
        while not output.exists():
            self.assertLess(time.monotonic(), deadline, 'drag-end did not invoke clipboard tool')
            time.sleep(0.02)
        # end-of-line includes the line terminator in tmux's vi selection.
        self.assertEqual(output.read_bytes(), (probe + '\n').encode())
        self.assertEqual(self.tmux('show-buffer').stdout, probe + '\n')
        self.assertEqual(self.tmux('display-message', '-p', '-t', pane,
                                   '#{pane_in_mode}').stdout.strip(), '0')

    def test_window_tabs_are_visible_without_idle_refresh(self):
        for option in ('window-status-format', 'window-status-current-format'):
            value = self.tmux('show-options', '-gv', option).stdout
            self.assertIn('#I', value)
            self.assertIn('#W', value)
        self.assertEqual(self.tmux('show-options', '-gv', 'status-interval').stdout.strip(), '0')
        self.assertEqual(self.tmux('show-options', '-gv', 'window-size').stdout.strip(), 'latest')


class TmuxCopyHelperTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='kit-copy-')
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name)
        self.env = {'PATH': str(self.home), 'HOME': str(self.home)}
        # Only the drain command is available; no real clipboard or tmux server.
        (self.home / 'cat').symlink_to(shutil.which('cat'))

    def fake(self, name):
        tool = self.home / name
        tool.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" > "$HOME/tool"\n'
                        '/bin/cat > "$HOME/clipboard"\n')
        tool.chmod(0o755)

    def copy(self):
        result = subprocess.run(['/bin/sh', str(COPY)], input=b'probe\nsecond line\n',
                                env=self.env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')
        return result

    def test_tmux_copy_without_desktop_or_tools_is_silent(self):
        self.copy()
        self.assertFalse((self.home / 'clipboard').exists())

    def test_tmux_copy_prefers_wayland(self):
        for name in ('wl-copy', 'xsel', 'xclip'):
            self.fake(name)
        self.env.update(WAYLAND_DISPLAY='wayland-test', DISPLAY='x-test')
        self.copy()
        self.assertEqual((self.home / 'tool').read_text(), 'wl-copy \n')
        self.assertEqual((self.home / 'clipboard').read_bytes(), b'probe\nsecond line\n')

    def test_tmux_copy_recovers_only_absent_session_variables(self):
        self.fake('xsel')
        tmux = self.home / 'tmux'
        tmux.write_text('#!/bin/sh\n[ "$1" = show-environment ] || exit 91\n'
                        'case "$2" in\n'
                        'DISPLAY) echo "DISPLAY=session-display" ;;\n'
                        'WAYLAND_DISPLAY) echo "-WAYLAND_DISPLAY" ;;\n'
                        'esac\n')
        tmux.chmod(0o755)
        self.env['TMUX'] = 'isolated-test'
        self.copy()
        self.assertEqual((self.home / 'tool').read_text(), 'xsel -ib\n')
        (self.home / 'tool').unlink()
        self.env['DISPLAY'] = ''  # Explicitly disabled: do not recover it.
        self.copy()
        self.assertFalse((self.home / 'tool').exists())

    def test_tmux_copy_x_tools_and_macos(self):
        for name, args in (('xsel', '-ib'), ('xclip', '-selection clipboard'), ('pbcopy', '')):
            with self.subTest(tool=name):
                self.fake(name)
                self.env['DISPLAY'] = 'x-test' if name != 'pbcopy' else ''
                self.copy()
                self.assertEqual((self.home / 'tool').read_text(), f'{name} {args}\n')
                self.assertEqual((self.home / 'clipboard').read_bytes(), b'probe\nsecond line\n')
                (self.home / name).unlink()


if __name__ == '__main__':
    unittest.main()
