"""Package import adapter for the standalone Claude worktree hook."""
import importlib.util

from pi_autowork.layout import LAYOUT

_spec = importlib.util.spec_from_file_location('_autowork_worktree_paths', LAYOUT.root / 'pi-autowork/engine/worktree_paths.py')
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

canonical_root = _module.canonical_root
worktree_path = _module.worktree_path
