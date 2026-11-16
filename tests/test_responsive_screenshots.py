"""Offline contract for the responsive capture helper and its skill entry."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/responsive-screenshots/scripts/capture.py'


def load():
    spec = importlib.util.spec_from_file_location('capture_helper', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def png_fixture(key, pixel_size=None):
    """IHDR fixture, not a rendered image; payload identifies the exact capture."""
    _, width, height, _ = key
    width, height = pixel_size or (width, height)
    return (bytes.fromhex('89504e470d0a1a0a0000000d49484452')
            + width.to_bytes(4, 'big') + height.to_bytes(4, 'big')
            + b'\0' * 9 + repr(key).encode())


class FakePage:
    def __init__(self, browser, options):
        self.browser, self.options = browser, options
        self.events = {}

    def set_default_timeout(self, value):
        pass

    def on(self, event, callback):
        self.events[event] = callback

    def goto(self, url, **kwargs):
        viewport = self.options['viewport']
        self.key = (url, viewport['width'], viewport['height'], self.options['color_scheme'])
        self.browser.calls.append(self.key)
        self.case = self.browser.cases.get(self.key, {})
        for text in self.case.get('console_errors', []):
            self.events['console'](SimpleNamespace(type='error', text=text))
        self.events['console'](SimpleNamespace(type='info', text='not an error'))
        for request in self.case.get('requests', []):
            self.events['requestfailed'](SimpleNamespace(**request))
        if self.case.get('error'):
            raise RuntimeError(self.case['error'])

    def wait_for_selector(self, *args, **kwargs):
        pass

    def wait_for_timeout(self, value):
        pass

    def evaluate(self, expression):
        return self.case.get('overflow', False) if 'scrollWidth' in expression else None

    def screenshot(self, path, **kwargs):
        Path(path).write_bytes(png_fixture(self.key, self.case.get('pixel_size')))


class FakeContext:
    def __init__(self, browser, options):
        self.page = FakePage(browser, options)
        self.closed = False

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, cases=None):
        self.cases = cases or {}
        self.calls, self.contexts = [], []
        self.closed = False

    def new_context(self, **options):
        context = FakeContext(self, options)
        self.contexts.append(context)
        return context

    def close(self):
        self.closed = True

    def __enter__(self):
        return SimpleNamespace(chromium=SimpleNamespace(launch=lambda: self))

    def __exit__(self, *args):
        pass


class CaptureContractTests(unittest.TestCase):
    def setUp(self):
        self.capture = load()

    def run_cli(self, out, urls, *options, cases=None):
        browser = FakeBrowser(cases)
        api = ModuleType('playwright.sync_api')
        api.sync_playwright = lambda: browser
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.dict(sys.modules, {'playwright': ModuleType('playwright'),
                                      'playwright.sync_api': api}), \
                patch.object(sys, 'argv', [str(SCRIPT), *urls, '--out', str(out), *options]), \
                redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                code = self.capture.main()
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue(), browser

    def test_distinct_inputs_keep_distinct_bytes_and_exact_duplicates_are_first_seen(self):
        urls = [
            'https://one.example/settings', 'https://two.example/settings',
            'file:///tmp/one/index.html', 'file:///tmp/two/index.html',
            'https://one.example/search?q=a+b', 'https://one.example/search?q=a-b',
            'https://one.example/search?q=' + 'x' * 1000 + 'a',
            'https://one.example/search?q=' + 'x' * 1000 + 'b',
            'https://one.example/settings#one', 'https://one.example/settings#two',
            'http://one.example/settings', 'https://one.example:8443/settings',
            'https://one.example/' + 'long-path/' * 100 + '?private=query',
        ]
        sizes = [(768, 1024), (375, 667), (375, 812), (1440, 900)]
        expected = [(url, width, height, scheme) for url in urls
                    for width, height in sizes for scheme in ('light', 'dark')]
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            args = ('--sizes', '768x1024', '375x667', '768×1024', '375x812', '1440x900',
                    '--scheme', 'both')
            code, stdout, stderr, browser = self.run_cli(out, [*urls, urls[0], urls[3]], *args)
            self.assertEqual(code, 0, stdout + stderr)
            self.assertEqual(browser.calls, expected)
            records = json.loads((out / 'captures.json').read_text())
            paths = [Path(record['path']) for record in records]
            self.assertEqual(len(set(paths)), len(expected))
            for key, record, path in zip(expected, records, paths):
                url, width, height, scheme = key
                with self.subTest(key=key):
                    self.assertEqual((record['url'], record['width'], record['height'],
                                      record['scheme']), key)
                    digest = hashlib.sha256(url.encode()).hexdigest()
                    suffix = f'-{digest}-{self.capture.label_for(width)}-{width}x{height}-{scheme}.png'
                    self.assertTrue(path.name.endswith(suffix), path.name)
                    self.assertLessEqual(len(path.name.removesuffix(suffix)), 48)
                    self.assertLess(len(path.name.encode()), 256)
                    self.assertNotIn('private', path.name)
                    self.assertEqual(path.read_bytes(), png_fixture(key))
                    self.assertEqual((record['pixel_width'], record['pixel_height']), (width, height))
            self.assertEqual(len({path.read_bytes() for path in paths}), len(expected))
            self.assertTrue(browser.closed)
            self.assertTrue(all(context.closed for context in browser.contexts))
            # Same-input reruns may replace the same names, but must not change identity.
            code, _, _, _ = self.run_cli(out, urls, *args)
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((out / 'captures.json').read_text()), records)

    def test_diagnostics_are_raw_in_json_and_safely_associated_in_markdown(self):
        url = 'https://example.com/<img src=x onerror=alert(1)>|`[page]\nnext'
        console = 'console | `code` <script>alert(1)</script>\n# injected'
        request = dict(method='GET', url='https://example.com/<bad>|`req`\nnext',
                       failure='failed | `why` <b>unsafe</b>\nnext')
        request_text = f"{request['method']} {request['url']} {request['failure']}"
        failure = 'navigation timed out | `oops` <img src=x>\nmore'
        cases = {
            (url, 375, 667, 'dark'): {'console_errors': [console], 'requests': [request]},
            (url, 768, 1024, 'light'): {'overflow': True},
            (url, 768, 1024, 'dark'): {'error': failure},
        }
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            code, stdout, _, _ = self.run_cli(out, [url], '--sizes', '375x667', '768x1024',
                                              '--scheme', 'both', cases=cases)
            self.assertEqual(code, 1)
            records = json.loads((out / 'captures.json').read_text())
            self.assertEqual(set(records[0]), {'url', 'scheme', 'label', 'width', 'height',
                                             'path', 'pixel_width', 'pixel_height', 'overflow',
                                             'console_errors', 'failed_requests', 'error'})
            self.assertEqual(records[1]['console_errors'], [console])
            self.assertEqual(records[1]['failed_requests'], [request_text])
            self.assertTrue(records[2]['overflow'])
            self.assertEqual(records[3]['error'], failure.splitlines()[0])
            for index in (0, 2, 3):
                self.assertEqual(records[index]['console_errors'], [])
                self.assertEqual(records[index]['failed_requests'], [])
            report = (out / 'report.md').read_text()
            self.assertIn('| Console errors | Failed requests |', report)
            rows = [line for line in report.splitlines() if line.startswith('| https')]
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row.count('|') == 10 for row in rows), rows)
            self.assertIn('| captured with diagnostics |', rows[1])
            self.assertIn('| 1 | 1 |', rows[1])
            self.assertIn('| 0 | 0 |', rows[0])
            # Literal expected escapes are an oracle independent of the implementation helper.
            escaped_console = ('console &#124; &#96;code&#96; &lt;script&gt;alert&#40;1&#41;'
                               '&lt;/script&gt;&#10;&#35; injected')
            self.assertIn(escaped_console, report)
            self.assertIn('&lt;img src=x onerror=alert&#40;1&#41;&gt;&#124;&#96;&#91;page&#93;'
                          '&#10;next', report)
            self.assertIn('GET https://example&#46;com/&lt;bad&gt;&#124;&#96;req&#96;&#10;next', report)
            self.assertIn('failed &#124; &#96;why&#96; &lt;b&gt;unsafe&lt;/b&gt;&#10;next', report)
            self.assertIn('navigation timed out &#124; &#96;oops&#96; &lt;img src=x&gt;', report)
            details = report.split('### Capture ')[1:]
            self.assertEqual(len(details), 4)
            for index, detail in enumerate(details):
                self.assertIn(f"{records[index]['width']}x{records[index]['height']}", detail)
                self.assertIn(records[index]['scheme'], detail)
                self.assertEqual(escaped_console in detail, index == 1)
                self.assertEqual('GET https:' in detail, index == 1)
            for raw in ('<script>', '<img', '`code`', '\n# injected', '[page]'):
                self.assertNotIn(raw, report)
            for text in ('Captured: 3 of 4', 'Horizontal overflow: 1', 'Console errors: 1',
                         'Failed requests: 1', 'not visual correctness', 'Exit status:'):
                self.assertIn(text, report)
            self.assertNotIn('ok ', stdout)
            self.assertIn('captured with diagnostics', stdout)
            self.assertIn('1 console error(s)', stdout)
            self.assertIn('1 failed request(s)', stdout)

    def test_cli_exit_limits_and_repair_after_navigation_failure(self):
        url = 'https://example.com/settings'
        key = (url, 375, 667, 'light')
        scenarios = [
            ('diagnostics', {'console_errors': ['broken script']}, [], 0, 'captured with diagnostics'),
            ('request diagnostics', {'requests': [dict(method='GET', url=url + '/api',
                                                       failure='net::ERR_FAILED')]},
             [], 0, 'captured with diagnostics'),
            ('failed', {'error': 'navigation timed out'}, [], 1, 'FAILED'),
            ('overflow', {'overflow': True}, [], 0, 'captured'),
            ('overflow gate', {'overflow': True}, ['--fail-on-overflow'], 2, 'captured'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            for name, case, options, expected, state in scenarios:
                with self.subTest(case=name):
                    out = Path(folder) / name
                    code, stdout, stderr, _ = self.run_cli(
                        out, [url], '--sizes', '375x667', *options, cases={key: case})
                    self.assertEqual(code, expected, stdout + stderr)
                    self.assertIn(state, stdout)
                    self.assertIn('Exit status:', stdout)
                    self.assertIn('not visual correctness', stdout)
                    if expected == 1:
                        self.assertIn('navigation timed out', stdout)
                        self.assertIn('navigation timed out', (out / 'report.md').read_text())
                        # User repairs page accessibility and reruns the same command.
                        repaired, output, _, _ = self.run_cli(out, [url], '--sizes', '375x667')
                        self.assertEqual(repaired, 0, output)
                        self.assertIn('captured', output)
            refused = Path(folder) / 'refused'
            code, _, stderr, browser = self.run_cli(refused, ['https://u:p@example.com/'])
            self.assertEqual(code, 2)
            self.assertIn('embedded credentials', stderr)
            self.assertEqual(browser.calls, [])
            self.assertFalse(refused.exists())

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
