"""Offline contract for the responsive capture helper and its skill entry."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/responsive-screenshots/scripts/capture.py'


def load():
    spec = importlib.util.spec_from_file_location('capture_helper', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CaptureContractTests(unittest.TestCase):
    def setUp(self):
        self.capture = load()

    def test_breakpoints_are_validated_before_a_browser_starts(self):
        self.assertEqual(self.capture.parse_size('375x667'), (375, 667))
        self.assertEqual(self.capture.parse_size('1440 × 900'), (1440, 900))
        for bad in ('100x900', '3000x9000', 'wide', '375', '375x'):
            with self.subTest(size=bad):
                with self.assertRaises(argparse.ArgumentTypeError):
                    self.capture.parse_size(bad)

    def test_file_names_carry_the_breakpoint_class(self):
        self.assertEqual(self.capture.label_for(375), 'mobile')
        self.assertEqual(self.capture.label_for(768), 'tablet')
        self.assertEqual(self.capture.label_for(1440), 'desktop')
        self.assertEqual(self.capture.page_slug('https://example.com/'), 'index')
        self.assertEqual(self.capture.page_slug('https://example.com/settings/profile'),
                         'settings-profile')
        self.assertEqual(self.capture.page_slug('file:///tmp/rs/ok.html'), 'ok')

    def test_urls_with_credentials_or_odd_schemes_are_refused(self):
        for bad in ('https://user:pw@example.com/', 'javascript:alert(1)',
                    'data:text/html,hi', 'ftp://example.com/file'):
            with self.subTest(url=bad):
                with self.assertRaises(ValueError):
                    self.capture.validate_url(bad)
        for good in ('https://example.com/a', 'http://localhost:3000/', 'file:///tmp/a.html'):
            self.capture.validate_url(good)

    def test_a_png_size_reader_reads_width_and_height(self):
        # A 2x1 opaque PNG: width and height come from the IHDR block only.
        data = bytes.fromhex(
            '89504e470d0a1a0a0000000d4948445200000002000000010806000000'
            '0000000000000000')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'tiny.png'
            path.write_bytes(data + b'\0' * 32)
            self.assertEqual(self.capture.png_size(path), (2, 1))
            other = Path(folder) / 'not-a-png.png'
            other.write_bytes(b'not a png')
            self.assertEqual(self.capture.png_size(other), (0, 0))

    def test_the_script_refuses_a_credential_url_without_starting_a_browser(self):
        done = subprocess.run([sys.executable, str(SCRIPT), 'https://u:p@example.com/',
                               '--out', '/tmp/unused'],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn('embedded credentials', done.stderr)

    def test_an_absent_playwright_package_is_reported_not_installed(self):
        module = load()
        self.assertTrue(callable(module.main))
        source = SCRIPT.read_text()
        self.assertIn('Playwright is not installed for this Python', source)
        self.assertNotIn('pip install', source)
        self.assertNotIn('playwright install', source)

    def test_the_skill_entry_states_scope_and_evidence(self):
        text = (ROOT / 'skills/responsive-screenshots/SKILL.md').read_text()
        for phrase in ('## Boundaries', '**Done when:**', '--fail-on-overflow',
                       'horizontal overflow', 'Never put credentials in a URL',
                       'It installs'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
