"""The repository root is also an installable Paseo plugin source.

`paseo plugin add git:TrebuchetDynamics/kit` resolves the plugin at the checkout root, so the
root carries a manifest whose build commands materialise the layout Paseo compiles, and entry
files (Paseo checks for them before it runs build). pi-autowork/integrations/paseo stays the owner.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'pi-autowork/integrations/paseo'


class PaseoRootSourceTests(unittest.TestCase):
    def test_retired_product_owner_is_absent(self):
        self.assertFalse((ROOT / "integrations/paseo").exists())

    def test_root_build_stages_complete_owner_without_checkout_imports(self):
        manifest = json.loads((ROOT / 'paseo-plugin.json').read_text())
        with tempfile.TemporaryDirectory(prefix='kit staged plugin ') as folder:
            staged = Path(folder)
            destination = staged / 'pi-autowork/integrations/paseo'
            shutil.copytree(PLUGIN, destination, ignore=shutil.ignore_patterns('node_modules', '.cache'))
            for argv in manifest['build']:
                subprocess.run(argv, cwd=staged, check=True, capture_output=True)
            for name in ('client', 'server', 'shared'):
                for source in (PLUGIN / name).rglob('*'):
                    if source.is_file():
                        self.assertEqual(source.read_bytes(), (staged / name / source.relative_to(PLUGIN / name)).read_bytes())
            for name in ('index.client.tsx', 'index.server.ts'):
                self.assertEqual((staged / name).read_bytes(), (PLUGIN / name).read_bytes())

    def test_retired_component_roots_and_production_test_imports(self):
        for name in ('src', 'integrations/paseo', 'rust/autowork'):
            self.assertFalse((ROOT / name).exists(), name)
        for source in (ROOT / 'pi-autowork/src').rglob('*.py'):
            self.assertNotRegex(source.read_text(), r'(?m)^\s*(?:from|import) (?:tests|support\.store_fixture|support\.offline_fixtures)\b', str(source))
        workflow = (ROOT / '.github/workflows/paseo.yml').read_text()
        self.assertIn('working-directory: pi-autowork/integrations/paseo', workflow)
        self.assertIn('cache-dependency-path: pi-autowork/integrations/paseo/package-lock.json', workflow)

    def test_the_root_manifest_builds_the_layout_paseo_compiles(self):
        manifest = json.loads((ROOT / 'paseo-plugin.json').read_text())
        plugin = json.loads((PLUGIN / 'paseo-plugin.json').read_text())
        self.assertEqual(manifest['id'], 'kit-autowork')
        for key in ('name', 'description', 'requirements'):
            self.assertEqual(manifest[key], plugin[key], key)
        build = manifest.get('build')
        self.assertIsInstance(build, list)
        self.assertIn(['cp', '-R', 'pi-autowork/integrations/paseo/client', 'pi-autowork/integrations/paseo/server',
                       'pi-autowork/integrations/paseo/shared', '.'], build)
        self.assertIn(['cp', 'pi-autowork/integrations/paseo/index.client.tsx', 'pi-autowork/integrations/paseo/index.server.ts',
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
