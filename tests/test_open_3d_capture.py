"""Opt-in: KIT_TEST_OPEN_3D=1 python3 -m unittest discover -s tests -p test_open_3d_capture.py."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
import unittest

RECORD = Path(__file__).resolve().parents[1] / 'skills/open-3d/runtime/record.py'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(os.environ.get('KIT_TEST_OPEN_3D') == '1', 'requires Playwright Chromium and FFmpeg')
class Open3DCaptureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=self.root))
        self.addCleanup(server.server_close)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        self.url = f'http://127.0.0.1:{server.server_port}/'
        self.output = self.root / 'capture.mp4'

    def record(self, script, env=None):
        # The fixture becomes ready only after rAF runs during pre-roll.
        (self.root / 'index.html').write_text('''<!doctype html>
<link rel="icon" href="data:,">
<style>body { margin: 0; display: flex }
section { width: 32px; height: 64px }
#css { animation: reveal 1ms steps(1, end) forwards }
@keyframes reveal { from { background: red } to { background: blue } }
</style><section id="raf"></section><section id="hook"></section><section id="css"></section>
<script>
const start = performance.now();
function paint(now) {
  raf.style.background = now === start ? 'red' : 'blue';
  window.ready = true;
  requestAnimationFrame(paint);
}
requestAnimationFrame(paint);
window.__recordFrame = t => { hook.style.background = t === 0 ? 'red' : 'blue'; };
''' + script + '\n</script>')
        return subprocess.run([sys.executable, '-B', RECORD, self.url, self.output,
                               '--size', '96x64', '--fps', '4', '--seconds', '1',
                               '--ready', 'window.ready', '--settle', '0.1', '--preset', 'ultrafast'],
                              env=env, capture_output=True, text=True, timeout=30)

    def test_encoded_frame_zero_uses_initial_raf_hook_and_css_state(self):
        result = self.record('')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        frames = subprocess.run(['ffmpeg', '-v', 'error', '-i', self.output, '-f', 'rawvideo',
                                 '-pix_fmt', 'rgb24', '-threads', '1', '-'],
                                check=True, capture_output=True, timeout=10).stdout
        stride = 96 * 64 * 3
        self.assertEqual(len(frames), 4 * stride)
        for x in (16, 48, 80):
            pos = (32 * 96 + x) * 3
            r, g, b = frames[pos:pos + 3]
            self.assertGreater(r - max(g, b), 150, f'first frame at x={x}')
            r, g, b = frames[stride + pos:stride + pos + 3]
            self.assertGreater(b - max(g, r), 150, f'second frame at x={x}')
        self.assertIn('4 encoded fps', result.stdout)

    def test_missing_encoder_is_reported_before_capture(self):
        result = self.record('', dict(os.environ, PATH=str(self.root)))
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('missing ffmpeg; make an existing FFmpeg build available on PATH', result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('.open-3d-*')))

    def test_invalid_captures_fail_without_replacing_output(self):
        short_bin = self.root / 'short-bin'
        short_bin.mkdir()
        encoder = short_bin / 'ffmpeg'
        real = shutil.which('ffmpeg')
        self.assertIsNotNone(real, 'test prerequisite: FFmpeg on PATH')
        encoder.write_text(f'#!{sys.executable}\n'
                           'import subprocess, sys, tempfile\n'
                           f'cmd = [{real!r}, *sys.argv[1:]]\n'
                           'if "image2pipe" not in cmd:\n'
                           '    sys.exit(subprocess.call(cmd))\n'
                           'with tempfile.TemporaryFile() as f:\n'
                           '    f.write(sys.stdin.buffer.read())\n'
                           '    f.seek(0)\n'
                           '    sys.exit(subprocess.call([*cmd[:-1], "-frames:v", "1", cmd[-1]], stdin=f))\n')
        encoder.chmod(0o755)
        short_env = dict(os.environ, PATH=f'{short_bin}{os.pathsep}{os.environ["PATH"]}')
        for script, env, message in (
            ('window.__recordFrame = async () => { throw Error("broken choreography"); };',
             None, '__recordFrame: broken choreography'),
            ('window.__recordFrame = () => requestAnimationFrame(() => { throw Error("broken rAF"); });',
             None, 'requestAnimationFrame: broken rAF'),
            ('throw Error("broken page");', None, 'page error: broken page'),
            ('', short_env, 'incomplete encoding: expected 4 frames, decoded 1'),
        ):
            with self.subTest(message=message):
                self.output.write_bytes(b'previous delivery')
                result = self.record(script, env)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn('wrote ', result.stdout)
                self.assertEqual(self.output.read_bytes(), b'previous delivery')
