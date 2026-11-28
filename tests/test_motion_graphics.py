"""Exercise the published capture command; opt in to real Chromium with KIT_MOTION_BROWSER=1."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/motion-graphics/scripts/capture.py'
# CSS position derived entirely from time. The same page in normal (non-render)
# mode is deliberately different, so the receipt depends on ?render and seek.
PAGE = '''<!doctype html><meta charset="utf-8"><style>
body { margin: 0; background: #101827; }
#dot { position: absolute; top: 25px; width: 32px; height: 32px; background: #60dbb7; }
</style><div id="dot"></div><script>
const dot = document.querySelector('#dot');
let previous = 0;
if (location.search === '?render') window.seek = seconds => {
    dot.style.left = `${10 + Math.sin(Math.PI * seconds / 2) ** 2 * 90}px`;
};
else dot.hidden = true;
</script>'''

# Synthetic WOFF containing one glyph (A), with no system-font dependency.
FONT = (
    'd09GRgABAAAAAAJIAAoAAAAAAngAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAABPUy8yAAABZAAAACMAAABgQThB3WNt'
    'YXAAAAGQAAAAKQAAADQADACUZ2x5ZgAAAcQAAAAYAAAAGBje+3loZWFkAAAA9AAAADYAAAA2L86z9GhoZWEAAAEs'
    'AAAAHwAAACQFegH2aG10eAAAAYgAAAAGAAAABgK8AABsb2NhAAABvAAAAAYAAAAGAAwAAG1heHAAAAFMAAAAFgAA'
    'ACAABAAFbmFtZQAAAdwAAABcAAAAbMto2eBwb3N0AAACOAAAAA8AAAAmACgAAAABAAAAAQAA6gcBWV8PPPUAAwPo'
    'AAAAAOcwOCwAAAAA5zA4LABkAAAB9AK8AAAAAwACAAAAAAAAeJxjYGRgYFb4b8HAwBTBkMKQwviFASiCAhgBVP8D'
    'dQB4nGNgZGBgYGJgZgDRIBYaAAAA+QAKAAB4nGNgZopgnMDAysDCQBgwInPsgQBIOQIhLqDAwAAAjJMClwACWAAA'
    'AGQAAHicY2BgYGJgYGAGYhEgyQimWRgUgDQLEIL4jv//Q8j/B8B8BgBSlwadAAAAAAAAAAAMAAAAAQBkAAAB9AK8'
    'AAIAADMTE2TIyAK8/UR4nC2IMQqAMBRDX6sgIjg4ODt6Ao/QpVtv0KFIwenTQo/vrxhI8hJg5MLQZVi+7LJMugbM'
    'OOuzs/1sWTl9LofLrVRJId31iYInUzhw2k2pIiSC+lZ+iMgL99wO4nicY2BiwA9A8ioAAJ4AKQA='
)
FONT_PAGE = PAGE.replace('id="dot"></div>', 'id="dot">A</div>') + (
    f'<style>@font-face {{ font-family: Fixture; src: url(data:font/woff;base64,{FONT});'
    'unicode-range: U+0041; } #dot { font: 16px Fixture; }</style>'
)


def capture(folder, *args, site=True, env=None):
    return subprocess.run(
        [sys.executable, *([] if site else ['-S']), '-B', str(SCRIPT),
         str(folder / 'local motion.html'), '--out', str(folder / 'frames'),
         '--size', '160x80', '--duration', '2', '--at', '0.37', '1.28', *args],
        cwd=folder, env=env, capture_output=True, text=True, timeout=25)


class CaptureTests(unittest.TestCase):
    def test_missing_python_package_is_reported_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            page = folder / 'local motion.html'
            page.write_text(PAGE)
            result = capture(folder, site=False)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('Playwright is not installed for this Python', result.stderr)
            self.assertIn('provide an environment', result.stderr)
            self.assertEqual(list(folder.iterdir()), [page])

    @unittest.skipUnless(os.getenv('KIT_MOTION_BROWSER') == '1', 'requires an existing Playwright Chromium')
    def test_explicit_seek_on_real_chromium(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            page = folder / 'local motion.html'
            page.write_text(FONT_PAGE)
            success = capture(folder, '--loop', '--fps', '4', '--font', '16px Fixture', 'A')
            self.assertEqual(success.returncode, 0, success.stderr)
            self.assertIn('sample-001.png @ 0.37s', success.stdout)
            self.assertIn('sample-002.png @ 1.28s', success.stdout)
            self.assertIn('Repeat seeks match; loop endpoints match; motion detected.', success.stdout)
            out = folder / 'frames'
            samples = [p.read_bytes() for p in sorted(out.glob('sample-*.png'))]
            self.assertEqual(len(samples), 4)
            self.assertEqual(samples[0], samples[-1])
            self.assertEqual(len(set(samples)), 3)
            sequence = sorted(out.glob('frame-*.png'))
            self.assertEqual(len(sequence), 8, 'the 2.0s endpoint is not encoded twice')
            self.assertEqual(sequence[0].read_bytes(), samples[0])
            self.assertNotEqual(sequence[-1].read_bytes(), samples[0])

            import shutil
            shutil.rmtree(out)
            for source, flags, error, env in (
                (PAGE.replace('Math.sin(Math.PI * seconds / 2) ** 2 * 90', '0'),
                 ('--loop',), 'No intermediate frame differs', None),
                (PAGE.replace('Math.sin(Math.PI * seconds / 2) ** 2 * 90', 'seconds * 60'),
                 ('--loop',), 'Loop endpoints differ', None),
                (PAGE.replace('Math.sin(Math.PI * seconds / 2) ** 2 * 90', 'previous++ * 5'),
                 (), 'Repeat seek differs', None),
                (PAGE.replace('dot.style.left =', 'if (seconds === 0.37) throw Error("broken seek"); dot.style.left ='),
                 (), 'broken seek', None),
                (PAGE.replace('dot.style.left =',
                              'if (seconds === 2 && previous === 0) { dot.style.left = "70px"; return; }'
                              'previous = seconds; dot.style.left ='),
                 ('--loop',), 'Repeat seek differs at 2s', None),
                (FONT_PAGE, ('--font', '16px Fixture', 'B'), 'Missing required font', None),
                (PAGE, ('--font', '16px "Missing Kit Fixture Face"', 'A'), 'Missing required font', None),
                (PAGE, (), 'Matching Playwright Chromium is unavailable',
                 dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(folder / 'no-browser'))),
            ):
                with self.subTest(error=error):
                    page.write_text(source)
                    result = capture(folder, *flags, env=env)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(error, result.stderr)
                    self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
