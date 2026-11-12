"""Which Autowork runtime this process runs, and which one is installed.

The fleet can run several copies of this repository: a source checkout, the installed
toolset that `autowork` resolves by default, and immutable `releases/<rev>` snapshots
under the runner state directory. A report names the running copy and the installed
copy, so a stale viewer or a stale runner is visible instead of silent.
"""
from functools import lru_cache
import os
from pathlib import Path
import re
import subprocess

SNAPSHOT = re.compile(r'[0-9a-f]{7,64}')


def state_root(env=os.environ):
    """The runner state directory; the installed toolset lives below it."""
    return Path(env.get('PI_AUTOWORK_STATE_DIR') or
                Path(env.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'pi-autowork')


def installed_root(env=os.environ):
    return state_root(env) / 'installed'


@lru_cache(maxsize=None)
def revision(root):
    """Short Git revision of a checkout, or the revision an immutable snapshot is named after."""
    root = Path(root)
    try:
        found = subprocess.run(['git', '-C', str(root), 'rev-parse', '--short', 'HEAD'],
                               capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        found = None
    if found is not None and found.returncode == 0 and found.stdout.strip():
        return found.stdout.strip()
    return root.name[:8] if SNAPSHOT.fullmatch(root.name) else ''


def viewer_root():
    """The repository or release root of the code this process loaded."""
    return Path(__file__).resolve().parents[2]


def report(env=os.environ, viewer=None):
    """The running copy and the installed copy; `installed` is None when there is none."""
    viewer = Path(viewer) if viewer is not None else viewer_root()
    installed = installed_root(env)
    usable = (installed / 'pi-autowork/pi_autowork/command.py').is_file()
    return {'viewer': {'root': str(viewer), 'revision': revision(viewer)},
            'installed': ({'root': str(installed), 'revision': revision(installed)} if usable else None)}


def skew(found):
    """Whether the running copy differs from the installed one."""
    installed = found['installed']
    return bool(installed and found['viewer']['revision'] != installed['revision'])


def warning(found=None):
    """Short skew warning for a narrow pane, or '' when the copies agree."""
    found = report() if found is None else found
    if not skew(found):
        return ''
    return (f"viewer {found['viewer']['revision'] or 'unknown'} is not installed "
            f"{found['installed']['revision'] or 'unknown'}: run autowork update")


def line(found=None):
    """One line naming both runtimes, and the repair when they differ."""
    found = report() if found is None else found
    text = f"viewer {found['viewer']['revision'] or 'unknown'} ({found['viewer']['root']})"
    installed = found['installed']
    if installed is None:
        return text + ' · no installed toolset'
    text += f" · installed {installed['revision'] or 'unknown'} ({installed['root']})"
    return text + (' · not in sync: run autowork update' if skew(found) else '')
