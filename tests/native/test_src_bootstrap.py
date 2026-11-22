"""Release-local native boundaries, exercised only in private source copies."""
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src_fixture import copy_sources


class SrcBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = copy_sources(self.base / 'release')

    def write(self, name, body):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def probe(self, body):
        result = subprocess.run([sys.executable, '-B', '-c', body], cwd=self.root,
                                env=dict(os.environ, PYTHONPATH=str(self.root / 'scripts')),
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(list(self.root.rglob('__pycache__')))

    def test_layout_is_frozen_bounded_and_reports_actual_owners(self):
        self.write('src/kit_runtime/nested/owner.py', 'VALUE = 1\n')
        self.write('src/kit_runtime/test_ignored.py', 'raise RuntimeError\n')
        self.write('src/kit_runtime/fixtures/ignored.py', 'raise RuntimeError\n')
        outside = self.base / 'outside.py'
        outside.write_text('raise RuntimeError\n')
        (self.root / 'src/kit_runtime/escape.py').symlink_to(outside)
        alias = self.base / 'linked'
        alias.symlink_to(self.root, target_is_directory=True)
        self.probe(f'''from pathlib import Path
from dataclasses import FrozenInstanceError
import kit_bootstrap as b
layout = b.Layout(Path({str(alias)!r}))
assert layout.root == Path.cwd()
assert layout.src == Path.cwd() / 'src'
assert layout.src.is_dir()
assert layout.entrypoint('plugin') == Path.cwd() / '__init__.py'
assert layout.entrypoint('runtime_defaults') == Path.cwd() / 'scripts/runtime_defaults.py'
assert layout.resource('skills') == Path.cwd() / 'skills'
assert layout.implementation('src/kit_runtime/nested/owner.py') == layout.runtime / 'nested/owner.py'
paths = b.Layout.python_sources(Path({str(alias)!r}))
assert paths == tuple(sorted(set(paths)))
assert layout.runtime / 'nested/owner.py' in paths
assert layout.runtime / 'install/preflight_config.py' in paths
assert all(p.name not in ('test_ignored.py', 'ignored.py', 'escape.py') for p in paths)
try: layout.root = Path('/')
except FrozenInstanceError: pass
else: raise AssertionError('mutable layout')
assert not any(hasattr(b, name) for name in ('activate', 'load', 'run'))
''')

    def test_native_namespace_and_release_local_peers_preserve_patches(self):
        shim = '''from pathlib import Path
import importlib.util
p = Path(__file__).parent / 'scripts/kit_bootstrap.py'
s = importlib.util.spec_from_file_location(__name__ + '._bootstrap', p)
b = importlib.util.module_from_spec(s)
s.loader.exec_module(b)
b.execute(globals(), 'src/kit_runtime/example.py')
'''
        self.write('example.py', shim)
        self.write('scripts/sibling.py', 'VALUE = "selected"\n')
        self.write('scripts/another.py', 'VALUE = 2\n')
        self.write('src/kit_runtime/example.py', '''ROOT = __file__
def value():
    return _KIT_COMPAT.peer(globals(), 'sibling').VALUE
''')
        other = copy_sources(self.base / 'other', source=self.root, entries=('scripts/sibling.py',))
        (other / 'scripts/sibling.py').write_text('VALUE = "other"\n')
        self.probe(f'''import importlib.util, sys, types
from pathlib import Path
sys.modules['sibling'] = types.SimpleNamespace(VALUE='poison')
def read(root, name):
    spec = importlib.util.spec_from_file_location(name, root / 'example.py',
        submodule_search_locations=[str(root)] if name == 'plugin' else None)
    module = importlib.util.module_from_spec(spec)
    if name == 'plugin': sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
one = read(Path.cwd(), 'plugin')
two = read(Path({str(other)!r}), 'other_plugin')
assert one.value() == 'selected' and two.value() == 'other'
assert one.value.__globals__ is one.__dict__
assert one.value.__module__ == one.__spec__.name == one.__package__ == 'plugin'
assert one.__path__ == [str(Path.cwd())]
assert one._KIT_COMPAT.peer(one.__dict__, 'sibling') is sys.modules['plugin.sibling']
assert one.ROOT == one.__file__ == str(Path.cwd() / 'example.py')
one._KIT_COMPAT.peer(one.__dict__, 'sibling').VALUE = 'patched'
assert one.value() == 'patched' and two.value() == 'other'
assert one._KIT_COMPAT.peer(one.__dict__, 'another').VALUE == 2
assert one._KIT_LAYOUT.root == Path.cwd()
''')

    def test_missing_poisoned_sources_and_cross_root_native_refuse(self):
        outside = self.base / 'outside'
        outside.mkdir()
        (outside / 'foreign.py').write_text('raise RuntimeError("foreign")\n')
        (self.root / 'src/kit_runtime/foreign.py').symlink_to(outside / 'foreign.py')
        self.write('scripts/sibling.py', 'VALUE = 1\n')
        self.probe('''from pathlib import Path
import sys, types
import kit_bootstrap as b
root = Path.cwd()
namespace = {'__file__': str(root / 'example.py'), '__name__': 'example'}
def refuses(call):
    try: call()
    except (ImportError, ValueError, FileNotFoundError): pass
    else: raise AssertionError('borrowed missing or foreign source')
refuses(lambda: b.Layout(root).entrypoint('unknown'))
refuses(lambda: b.execute(namespace, 'src/kit_runtime/missing.py'))
refuses(lambda: b.execute(namespace, 'src/kit_runtime/foreign.py'))
refuses(lambda: b.execute(namespace, '../outside.py'))
refuses(lambda: b.execute({'__file__': str(root.parent / 'example.py')}, 'src/kit_runtime/plugin.py'))
refuses(lambda: b.peer({'__file__': str(root.parent / 'example.py')}, 'sibling'))
refuses(lambda: b.peer(namespace, 'missing'))
refuses(lambda: b.peer(namespace, '../sibling'))
sibling = b.peer(namespace, 'sibling')
sibling.__file__ = '/foreign/sibling.py'
refuses(lambda: b.peer(namespace, 'sibling'))
''')


if __name__ == '__main__':
    unittest.main()
