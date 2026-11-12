"""Canonical runner package, bound to this release before loading its modules."""
import importlib.util as _util
from pathlib import Path as _Path

_root = _Path(__file__).resolve().parents[2]
_spec = _util.spec_from_file_location('_autowork_entry_bootstrap', _root / 'scripts/autowork_bootstrap.py')
_bootstrap = _util.module_from_spec(_spec)
_spec.loader.exec_module(_bootstrap)
_bootstrap.activate(_root)
