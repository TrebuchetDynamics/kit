"""Offline JSON-lines bridge fixtures against the pinned Pi 1.5.0 API shape."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pi_autowork import pi_auth

# Contract fixture for ModelRuntime/AuthInteraction, not an alternate credential store.
SDK = r'''
import { writeFileSync } from 'node:fs';
export function readStoredCredential() { return undefined; }
export class ModelRuntime {
  static async create(options) {
    if (options.refreshOnCreate !== false || options.allowModelNetwork !== false) throw Error('network');
    return new ModelRuntime(options);
  }
  constructor(options) { this.options = options; }
  getModels() { return [{provider:'openrouter',id:'fixture/model:free',cost:{input:0,output:0,cacheRead:0,cacheWrite:0}}, {provider:'fixture',id:'paid',cost:{input:1,output:2,cacheRead:0,cacheWrite:0}}]; }
  getProviders() { return [{id: 'fixture', name: 'Fixture', auth: {
    oauth: {login(){}}, apiKey: {login(){}}
  }}]; }
  async login(provider, method, interaction, options) {
    if (provider !== 'fixture' || !options.signal) throw Error('invalid provider');
    interaction.notify({type:'progress', message:'progress secret must not leak'});
    interaction.notify({type:'info', message:'Run gcloud auth application-default login', links:[{label:'ADC docs',url:'https://example.com/adc'}]});
    if (method === 'oauth') interaction.notify({type:'auth_url', url:'https://example.com/oauth'});
    const key = await interaction.prompt({type:'secret', message:'Fixture key'});
    if (key === 'bad-secret') throw Error('Provider rejected ' + key);
    writeFileSync(this.options.authPath, JSON.stringify({provider, method}));
  }
}
'''


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for offline SDK bridge fixtures')
class PiAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sdk = self.root / 'sdk'
        (self.sdk / 'dist').mkdir(parents=True)
        (self.sdk / 'package.json').write_text(json.dumps(dict(
            name='@earendil-works/pi-coding-agent', version='1.5.0', type='module')))
        (self.sdk / 'dist/index.js').write_text(SDK)
        self.profile = self.root / 'selected-profile'
        self.profile.mkdir()
        self.env = patch.dict(os.environ, AUTOWORK_PI_SDK=str(self.sdk))
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_login(self, answer, method='api_key'):
        events = []
        bridge = pi_auth.Bridge(str(self.profile))
        async def receive(event):
            events.append(event)
            if event['type'] == 'prompt':
                await bridge.answer(answer)
        async def run():
            try:
                await bridge.run('login', receive, 'fixture', method)
                return None
            except pi_auth.AuthError as error:
                return str(error)
        return asyncio.run(run()), events, bridge

    def test_empty_catalog_advertises_methods_without_creating_profile_state(self):
        discovered = pi_auth.discovery(str(self.profile))
        self.assertEqual([m['id'] for m in discovered['models'] if m['free']], ['openrouter/fixture/model:free'])
        providers = pi_auth.catalog(str(self.profile))
        self.assertEqual(providers, [dict(id='fixture', name='Fixture', state='not stored',
                                          methods=['oauth', 'api_key'])])
        self.assertEqual(list(self.profile.iterdir()), [])

    def test_key_and_oauth_use_official_login_with_exact_profile_and_no_secret_output(self):
        for method in ('api_key', 'oauth'):
            error, events, bridge = self.run_login('literal-fixture-secret', method)
            self.assertIsNone(error)
            self.assertIn(dict(type='success'), events)
            self.assertIn(dict(type='info', message='Run gcloud auth application-default login', links=[dict(label='ADC docs', url='https://example.com/adc')]), events)
            self.assertNotIn('literal-fixture-secret', json.dumps(events))
            self.assertNotIn('progress secret', json.dumps(events))
            self.assertEqual(json.loads((self.profile / 'auth.json').read_text()),
                             dict(provider='fixture', method=method))
            if method == 'oauth':
                self.assertIn(dict(type='url', url='https://example.com/oauth'), events)
            self.assertEqual(bridge.process.returncode, 0)

    def test_invalid_key_and_command_key_fail_without_exposing_or_persisting_secret(self):
        for key in ('bad-secret', '!printf unsafe'):
            error, events, bridge = self.run_login(key)
            self.assertIsNotNone(error)
            self.assertIn('failed', error)
            self.assertNotIn(key, error + json.dumps(events))
            self.assertFalse((self.profile / 'auth.json').exists())
            self.assertNotEqual(bridge.process.returncode, 0)

    def test_cancel_reaps_helper_and_never_completes_authentication(self):
        async def run():
            prompted = asyncio.Event()
            events = []
            bridge = pi_auth.Bridge(str(self.profile))
            async def receive(event):
                events.append(event)
                if event['type'] == 'prompt':
                    prompted.set()
            task = asyncio.create_task(bridge.run('login', receive, 'fixture', 'oauth'))
            await asyncio.wait_for(prompted.wait(), 5)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIsNotNone(bridge.process.returncode)
            self.assertFalse(any(e['type'] == 'success' for e in events))
        asyncio.run(run())
        self.assertEqual(list(self.profile.iterdir()), [])

    def test_missing_provider_and_helper_fail_without_private_diagnostics(self):
        async def run():
            events = []
            async def receive(event):
                events.append(event)
            with self.assertRaises(pi_auth.AuthError):
                await pi_auth.Bridge(str(self.profile)).run('login', receive, 'unknown', 'oauth')
            self.assertTrue(any(e['type'] == 'error' for e in events))
        asyncio.run(run())
        with patch.object(pi_auth, 'sdk_root', side_effect=pi_auth.AuthError('SDK unavailable')):
            with self.assertRaisesRegex(pi_auth.AuthError, 'SDK unavailable'):
                pi_auth.catalog(str(self.profile))
        self.assertFalse((self.profile / 'auth.json').exists())

    def test_device_select_text_and_aborted_manual_prompt_keep_response_identity(self):
        extra = r'''
    interaction.notify({type:'device_code', verificationUri:'https://example.com/device', userCode:'FIXTURE-CODE'});
    const selected = await interaction.prompt({type:'select', message:'Region', options:[{id:'region',label:'Region'}]});
    if (selected !== 'region') throw Error('selection');
    const abort = new AbortController();
    const abandoned = interaction.prompt({type:'manual_code', message:'Optional callback', signal:abort.signal});
    abort.abort();
    await abandoned.catch(() => {});
    const text = await interaction.prompt({type:'text', message:'Account'});
    if (text !== 'fixture-account') throw Error('text');
'''
        (self.sdk / 'dist/index.js').write_text(SDK.replace(
            "    const key = await interaction.prompt", extra + "    const key = await interaction.prompt"))
        events = []
        bridge = pi_auth.Bridge(str(self.profile))
        async def receive(event):
            events.append(event)
            if event['type'] != 'prompt' or event['kind'] == 'manual_code':
                return
            await bridge.answer({'select': 'region', 'text': 'fixture-account', 'secret': 'literal-secret'}[event['kind']])
        asyncio.run(bridge.run('login', receive, 'fixture', 'oauth'))
        self.assertIn(dict(type='device', url='https://example.com/device', code='FIXTURE-CODE'), events)
        prompts = [e for e in events if e['type'] == 'prompt']
        self.assertEqual([e['kind'] for e in prompts], ['select', 'manual_code', 'text', 'secret'])
        self.assertEqual(len({e['id'] for e in prompts}), 4)
        self.assertIn(dict(type='success'), events)
        self.assertNotIn('literal-secret', json.dumps(events))

    def test_fixture_and_helper_pass_node_syntax_check(self):
        result = subprocess.run(['node', '--check', str(Path(pi_auth.__file__).with_suffix('.mjs'))],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
