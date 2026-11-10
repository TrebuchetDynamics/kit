"""Compatibility entry for the selected release's read-only YAML validator."""
import importlib.util as _util
from pathlib import Path as _Path

_spec = _util.spec_from_file_location(__name__ + '._bootstrap', _Path(__file__).with_name('autowork_bootstrap.py'))
_bootstrap = _util.module_from_spec(_spec)
_spec.loader.exec_module(_bootstrap)
_bootstrap.execute(globals(), 'pi-autowork/src/autowork_runtime/install/preflight_config.py')
