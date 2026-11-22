"""Stdlib-only, release-local paths and loaders for the native Hermes plugin.

Native sources execute in their public caller's dictionary. Peers resolve only
within that selected release, never through cwd or an executor installation.
"""
from dataclasses import dataclass
import hashlib
import importlib.abc
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]
NATIVE = {
    '__init__.py': 'plugin.py',
    **{name + '.py': name + '.py' for name in (
        'bundle', 'autoresearch_commands', 'workflow_commands', 'runtime_defaults',
        'telegram_menu_policy', 'install_skills', 'setup_bundle', 'setup_preflight',
        'setup_runtime', 'preflight_config', 'update_bundle', 'update_bundle_native')},
    'install-graphify.py': 'install_graphify.py',
}


def _inside(root, relative, *, required=False):
    relative = Path(relative)
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or not path.resolve().is_relative_to(root):
        raise ValueError(f'path escapes selected release: {relative}')
    if required and not path.is_file():
        raise ImportError(f'missing selected-release source: {path}')
    return path


@dataclass(frozen=True)
class Layout:
    root: Path

    def __post_init__(self):
        object.__setattr__(self, 'root', Path(self.root).resolve())

    @property
    def src(self):
        return self.root / 'src'

    @property
    def runtime(self):
        return self.src / 'kit_runtime'

    def resource(self, relative):
        return _inside(self.root, relative)

    def entrypoint(self, name):
        """Native launch paths; explicit relative public paths are also accepted."""
        if '/' in name or name.endswith('.py'):
            return _inside(self.root, name)
        native = {'plugin': '__init__.py', **{Path(p).stem.replace('-', '_'): 'scripts/' + p
                                            for p in NATIVE if p != '__init__.py'}}
        if name not in native:
            raise ValueError(f'unknown native entrypoint: {name}')
        return _inside(self.root, native[name])

    def implementation(self, relative):
        """Resolve a native adapter to its declared owner."""
        entry = _inside(self.root, relative)
        if entry.is_relative_to(self.runtime):
            return entry
        if entry.is_file():
            import ast
            tree = ast.parse(entry.read_bytes(), str(entry))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'execute' and len(node.args) == 2
                        and isinstance(node.args[1], ast.Constant)
                        and isinstance(node.args[1].value, str)):
                    return _inside(self.root, node.args[1].value, required=True)
        return entry

    @staticmethod
    def python_sources(root):
        """Sorted, bounded production Python; no tests, fixtures or escaping links."""
        layout = Layout(root)
        paths = set(layout.root.glob('*.py'))
        paths.update(layout.root / 'scripts' / name for name in (*NATIVE, 'kit_bootstrap.py')
                     if name != '__init__.py')
        paths.update(layout.src.rglob('*.py'))
        excluded = {'tests', 'test', 'fixtures', 'fixture', '__pycache__'}
        return tuple(sorted({layout.implementation(p.relative_to(layout.root).as_posix())
                             for p in paths if p.is_file()
                             and p.resolve().is_relative_to(layout.root)
                             and not excluded.intersection(p.relative_to(layout.root).parts)
                             and not p.name.startswith('test_')
                             and p.name not in ('store_fixture.py', 'offline_fixtures.py')}))


def _origin(module, expected):
    origin = getattr(module, '__file__', None)
    if not origin or Path(origin).resolve() != expected.resolve():
        raise ImportError(f'foreign module {module.__name__}: {origin}; expected {expected}')


class _SourceLoader(importlib.abc.Loader):
    def __init__(self, path):
        self.path = path

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.path.read_bytes(), str(self.path), 'exec'), module.__dict__)


def execute(namespace, source_relative):
    """Execute a native owner in its existing public module/patch namespace."""
    entry = Path(namespace['__file__']).resolve()
    layout = Layout(_ROOT)
    if entry.parent not in (layout.root, layout.root / 'scripts'):
        raise ImportError('native entry and bootstrap roots differ')
    source = _inside(layout.root, source_relative, required=True)
    if not source.is_relative_to(layout.runtime):
        raise ValueError('native source must be under src/kit_runtime')
    namespace['_KIT_LAYOUT'] = layout
    namespace['_KIT_COMPAT'] = sys.modules[__name__]
    exec(compile(source.read_bytes(), str(source), 'exec'), namespace)


def peer(namespace, name):
    """A native peer belongs to the caller's release and plugin package, not cwd."""
    if not name.isidentifier():
        raise ValueError(f'invalid native peer: {name}')
    layout = namespace.get('_KIT_LAYOUT') or Layout(Path(namespace['__file__']).resolve().parent)
    if layout.root != _ROOT:
        raise ImportError('native peer and bootstrap roots differ')
    source = _inside(layout.root, 'scripts/' + name + '.py', required=True)
    package = namespace.get('__package__')
    parent = sys.modules.get(package) if package else None
    if parent is None or not hasattr(parent, '__path__'):
        package = '_kit_native_' + hashlib.sha256(str(layout.root).encode()).hexdigest()
        if package not in sys.modules:
            parent = ModuleType(package)
            parent.__path__ = [str(layout.root)]
            sys.modules[package] = parent
    elif [Path(p).resolve() for p in parent.__path__] != [layout.root]:
        raise ImportError('foreign native plugin package')
    qualified = package + '.' + name
    if qualified in sys.modules:
        module = sys.modules[qualified]
        _origin(module, source)
        return module
    spec = importlib.util.spec_from_file_location(qualified, source, loader=_SourceLoader(source))
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(qualified, None)
        raise
    setattr(sys.modules[package], name, module)
    return module
