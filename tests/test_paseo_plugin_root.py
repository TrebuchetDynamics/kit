"""The repository root is also an installable Paseo plugin source.

`paseo plugin add git:TrebuchetDynamics/kit` resolves the plugin at the checkout root, so the
root carries a manifest whose build commands materialise the layout Paseo compiles, and entry
files (Paseo checks for them before it runs build). integrations/paseo stays the owner.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'integrations/paseo'


class PaseoRootSourceTests(unittest.TestCase):
    def test_the_root_manifest_builds_the_layout_paseo_compiles(self):
        manifest = json.loads((ROOT / 'paseo-plugin.json').read_text())
        plugin = json.loads((PLUGIN / 'paseo-plugin.json').read_text())
        self.assertEqual(manifest['id'], 'paseo-autowork')
        for key in ('name', 'description', 'requirements'):
            self.assertEqual(manifest[key], plugin[key], key)
        build = manifest.get('build')
        self.assertIsInstance(build, list)
        self.assertIn(['cp', '-R', 'integrations/paseo/client', 'integrations/paseo/server',
                       'integrations/paseo/shared', '.'], build)
        self.assertIn(['cp', 'integrations/paseo/index.client.tsx', 'integrations/paseo/index.server.ts',
                       '.'], build)

    def test_the_root_entries_stay_identical_to_their_owner(self):
        # Paseo rejects a module outside client/, server/ or shared/, so the root entry cannot
        # re-export the owner's entry; it is a copy that build rewrites at install time. This
        # test stops the copy from becoming a stale lie.
        for entry in ('index.client.tsx', 'index.server.ts'):
            with self.subTest(entry=entry):
                self.assertEqual((ROOT / entry).read_bytes(), (PLUGIN / entry).read_bytes())


if __name__ == '__main__':
    unittest.main()
