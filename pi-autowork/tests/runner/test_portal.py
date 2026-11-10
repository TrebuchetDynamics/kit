"""Public setup and consumer seams with disposable config and a health-only proxy."""
from contextlib import contextmanager
import errno
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import portal, pi_runtime  # noqa: E402


class PortalTests(unittest.TestCase):
    @contextmanager
    def health_server(self, health, requests):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get('Authorization')))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps(health).encode())

            def log_message(self, *args):
                pass

        base = os.environ.get('AUTOWORK_PORT_BASE')
        # Match the CLI fixture: stay in the lease, reserving +3 for its wrong endpoint.
        ports = range(int(base) + 4, int(base) + 100) if base else (0,)
        for port in ports:
            try:
                server = http.server.HTTPServer(('127.0.0.1', port), Handler)
                break  # Keep the listening socket; never probe/close/rebind.
            except OSError as error:
                if error.errno != errno.EADDRINUSE or port == ports[-1]:
                    error.add_note(f'Portal health fixture could not bind within ports {ports}')
                    raise
        with server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                yield server
            finally:
                server.shutdown()
                thread.join()

    def test_health_only_preflight_has_actionable_errors_and_no_authentication(self):
        health = {'status': 'ok', 'upstream': 'Nous Portal', 'authenticated': True}
        requests = []
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, PI_CODING_AGENT_DIR=folder):
            with self.health_server(health, requests) as server:
                endpoint = f'http://127.0.0.1:{server.server_port}/v1'
                proposal = portal.propose('nous-selected', 'example', endpoint)
                portal.apply(proposal)
                self.assertEqual(proposal.proxy['state'], 'available')
                portal.check_model('nous-selected/example')
                health['authenticated'] = False
                self.assertEqual(portal.probe(endpoint)['state'], 'login_required')
                settings = pi_runtime.Settings(folder, {'PI_AUTOWORK_PRIMARY': 'nous-selected/example',
                                                       'PI_AUTOWORK_NO_FALLBACK': '1'})
                with mock.patch.object(pi_runtime, 'auth_ready', side_effect=AssertionError('Must not authenticate')):
                    chosen, reason = pi_runtime.choose(settings)
                self.assertIsNone(chosen)
                self.assertIn('hermes portal', reason)
                settings.fallback_enabled = True
                settings.fallback = 'ordinary/fallback'
                with mock.patch.object(pi_runtime, 'auth_ready', return_value=True):
                    self.assertEqual(pi_runtime.choose(settings)[0], 'ordinary/fallback')
                health.update(upstream='other', authenticated=True)
                self.assertEqual(portal.probe(endpoint)['state'], 'incompatible')
            self.assertEqual(portal.probe(endpoint)['state'], 'unavailable')
            with self.assertRaisesRegex(portal.SetupError, 'Proxy unavailable'):
                portal.check_model('nous-selected/example')
            self.assertEqual(set(requests), {('/health', None)})
            for bad in ('http://example.invalid:80/v1', 'http://127.0.0.1:8645/v1?token=SECRET',
                        'http://user:SECRET@127.0.0.1:8645/v1', 'http://localhost:8645/v1'):
                with self.subTest(endpoint=bad), self.assertRaises(portal.SetupError):
                    portal.propose('nous-selected', 'example', bad)

    def test_health_servers_are_isolated_and_close_on_assertion_failure(self):
        health = {'status': 'ok', 'upstream': 'Nous Portal', 'authenticated': True}
        requests = []
        with self.health_server(health, []) as occupied:
            occupied_endpoint = f'http://127.0.0.1:{occupied.server_port}/v1'
            with self.assertRaisesRegex(AssertionError, 'fixture failure'):
                with self.health_server(health, requests) as server:
                    endpoint = f'http://127.0.0.1:{server.server_port}/v1'
                    self.assertNotEqual(server.server_port, occupied.server_port)
                    self.assertEqual(portal.probe(endpoint)['state'], 'available')
                    raise AssertionError('fixture failure')
            self.assertEqual(server.socket.fileno(), -1)
            self.assertEqual(portal.probe(endpoint)['state'], 'unavailable')
            self.assertEqual(portal.probe(occupied_endpoint)['state'], 'available')
        self.assertEqual(occupied.socket.fileno(), -1)
        self.assertEqual(requests, [('/health', None)])

    def test_read_only_preflight_preserves_unrelated_symlinked_configuration(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, PI_CODING_AGENT_DIR=folder):
            source = Path(folder) / 'shared.json'
            original = b'{"providers":{"ordinary":{"apiKey":"not-a-portal-key"}}}\n'
            source.write_bytes(original)
            path = Path(folder) / 'models.json'
            path.symlink_to(source)
            portal.check_model('ordinary/example')
            self.assertTrue(path.is_symlink())
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaisesRegex(portal.SetupError, 'symlink'):
                portal.propose('nous', 'example')

    def test_model_overrides_cannot_bypass_the_selected_proxy(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, PI_CODING_AGENT_DIR=folder), \
                mock.patch.object(portal, 'probe', return_value={'state': 'available', 'message': 'offline stub'}):
            path = Path(folder) / 'models.json'
            for override in ({'baseUrl': 'https://example.invalid/v1'}, {'api': 'anthropic-messages'},
                             {'headers': {'Authorization': '!secret-command'}}, {'maxTokens': -1}):
                with self.subTest(override=override):
                    entry = {'baseUrl': portal.DEFAULT_ENDPOINT, 'api': 'openai-completions',
                             'apiKey': portal.PLACEHOLDER, 'models': [{'id': 'example', **override}]}
                    original = json.dumps({'providers': {'nous-selected': entry}}).encode()
                    path.write_bytes(original)
                    with self.assertRaises(portal.SetupError):
                        portal.propose('nous-selected', 'example')
                    settings = pi_runtime.Settings(folder, {'PI_AUTOWORK_PRIMARY': 'nous-selected/example',
                                                           'PI_AUTOWORK_NO_FALLBACK': '1'})
                    with mock.patch.object(pi_runtime, 'auth_ready', side_effect=AssertionError('Must not authenticate')):
                        chosen, reason = pi_runtime.choose(settings)
                    self.assertIsNone(chosen)
                    self.assertIn('model', reason.lower())
                    self.assertEqual(path.read_bytes(), original)

    def test_changed_proposal_and_failed_replace_leave_config_intact(self):
        with tempfile.TemporaryDirectory() as folder, mock.patch.dict(os.environ, PI_CODING_AGENT_DIR=folder), \
                mock.patch.object(portal, 'probe', return_value={'state': 'unavailable', 'message': 'offline'}):
            path = Path(folder) / 'models.json'
            path.write_text('{"providers":{}}\n')
            proposal = portal.propose('nous', 'example')
            changed = b'{"providers":{},"concurrent":"edit"}\n'
            path.write_bytes(changed)
            with self.assertRaisesRegex(portal.SetupError, 'changed since proposal'):
                portal.apply(proposal)
            self.assertEqual(path.read_bytes(), changed)
            proposal = portal.propose('nous', 'example')
            with mock.patch.object(portal.os, 'replace', side_effect=OSError('disk full')):
                with self.assertRaisesRegex(portal.SetupError, 'atomically'):
                    portal.apply(proposal)
            self.assertEqual(path.read_bytes(), changed)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ['.autowork-models.lock', 'models.json'])
