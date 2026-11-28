"""Art CLI contracts; set KIT_ART_CHROMIUM to exercise the real Canvas renderer."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / 'skills/genart/scripts/verify_canvas.py'
SKETCH = ROOT / 'skills/genart/examples/seeded.html'
PREFLIGHT = ROOT / 'skills/procedural-drawing/scripts/preflight.py'


def run(*args):
    return subprocess.run([sys.executable, '-B', *args], capture_output=True,
                          text=True, timeout=60)


class ArtRuntimeTests(unittest.TestCase):
    def test_missing_operational_prerequisites_fail_without_installing(self):
        drawing = run('-S', PREFLIGHT, '--format', 'png')
        self.assertEqual(drawing.returncode, 1, drawing.stdout + drawing.stderr)
        self.assertIn('NumPy and Pillow', drawing.stderr)
        canvas = run(VERIFY, SKETCH, '--chromium', '/no/such/chromium')
        self.assertEqual(canvas.returncode, 1, canvas.stdout + canvas.stderr)
        self.assertIn('Chromium executable not found', canvas.stderr)
        self.assertIn('--chromium', canvas.stderr)

    @unittest.skipUnless(os.environ.get('KIT_ART_CHROMIUM'), 'set KIT_ART_CHROMIUM to an installed Chromium')
    def test_canvas_contract_against_real_chromium(self):
        chromium = os.environ['KIT_ART_CHROMIUM']
        result = run(VERIFY, SKETCH, '--chromium', chromium)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for check in ('repeatability', 'distinctness', 'A→B→A'):
            self.assertIn(f'ok {check}', result.stdout)

        source = SKETCH.read_text()
        marker = 'const offset = parseInt(hash.slice(2, 10), 16);'
        self.assertEqual(source.count(marker), 1)
        with tempfile.TemporaryDirectory() as directory:
            sketch = Path(directory) / 'fixture.html'
            for alteration, failed_check in (
                ('const offset = crypto.getRandomValues(new Uint32Array(1))[0];', 'repeatability'),
                ('const offset = parseInt(hash.slice(2, 10), 16) + ++window.draws;', 'A→B→A'),
                ('const offset = 0;', 'distinctness'),
            ):
                with self.subTest(check=failed_check):
                    sketch.write_text(source.replace(marker, alteration).replace(
                        'window.render =', 'window.draws = 0; window.render ='))
                    result = run(VERIFY, sketch, '--chromium', chromium)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(f'FAIL {failed_check}', result.stdout)

            # A one-pixel difference changes the digest but is not distinct art.
            sketch.write_text(source.replace('window.rendered = true;', '''
                ctx.fillStyle = hash.startsWith('0x1') ? '#fff' : '#000';
                ctx.fillRect(0, 0, 1, 1);
                window.rendered = true;
            ''').replace(marker, 'const offset = 0;'))
            result = run(VERIFY, sketch, '--chromium', chromium)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('FAIL distinctness', result.stdout)
            self.assertIn('ok repeatability', result.stdout)

            sketch.write_text(source.replace('<script>', '<script src="missing.js"></script>\n<script>', 1))
            result = run(VERIFY, sketch, '--chromium', chromium)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('script unavailable: http://localhost/missing.js', result.stderr)
