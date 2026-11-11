"""Fleet-owned Pi configuration. Never include configuration contents in diagnostics."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

REFILL = 'autowork update --only autowork'


def state_root(env=os.environ):
    return Path(env.get('PI_AUTOWORK_STATE_DIR') or
                Path(env.get('XDG_STATE_HOME') or Path.home() / '.local/state') / 'pi-autowork')


def directory(root):
    return Path(root) / 'pi-agent'


def environment(root):
    return {'PI_CODING_AGENT_DIR': str(directory(root))}


def problem(root):
    home = directory(root)
    if not home.is_dir():
        return f'Private Pi directory is missing; refill with: {REFILL}'
    if not (home / 'auth.json').is_file():
        return f'Private Pi login is missing; refill with: {REFILL}'
    if (home / 'login-refused').exists():
        return f'Private Pi login was refused; refill with: {REFILL}'
    return None


def fill(root, source, *, refresh=False):
    """Copy only runtime settings and model configuration/login, never packages or sessions."""
    target = directory(root)
    if target.is_symlink():
        raise RuntimeError('Refusing a symlinked private Pi directory')
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    inside = subprocess.run(['git', '-C', str(target), 'rev-parse', '--is-inside-work-tree'],
                            capture_output=True, text=True)
    if inside.returncode == 0 and inside.stdout.strip() == 'true':
        raise RuntimeError('Private Pi configuration must be outside repository worktrees')
    target.chmod(0o700)
    source = Path(source)
    if source.resolve() == target.resolve():
        raise RuntimeError('Refill needs the interactive Pi directory, not the private directory')
    for name in ('settings.json', 'models.json', 'auth.json'):
        dest = target / name
        if dest.is_symlink():
            raise RuntimeError('Refusing a symlinked private Pi configuration file')
        if dest.exists() and not refresh:
            dest.chmod(0o600)
            continue
        try:
            data = (source / name).read_bytes()
            if name == 'settings.json':
                settings = json.loads(data)
                data = json.dumps({k: settings[k] for k in ('defaultProvider', 'defaultModel', 'defaultThinkingLevel')
                                   if k in settings}).encode()
        except FileNotFoundError:
            continue
        except (OSError, ValueError, TypeError):
            raise RuntimeError('Cannot read interactive Pi configuration (contents withheld)') from None
        fd, temporary = tempfile.mkstemp(dir=target)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
            os.replace(temporary, dest)
        finally:
            Path(temporary).unlink(missing_ok=True)
    (target / 'login-refused').unlink(missing_ok=True)


def install(root, source):
    """An independent Git checkout, not a worktree tied to the interactive package clone."""
    target = Path(root) / 'installed'
    source = Path(source).resolve()
    if source == target.resolve():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    def git(*args):
        result = subprocess.run(['git', *map(str, args)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Cannot install the independent Autowork release')
        return result.stdout.strip()
    if not target.exists():
        git('clone', '--quiet', '--depth', '1', source.as_uri(), target)
    else:
        git('-C', target, 'fetch', '--quiet', source, 'HEAD')
        git('-C', target, 'merge', '--ff-only', 'FETCH_HEAD')
    remote = git('-C', source, 'remote', 'get-url', 'origin')
    git('-C', target, 'remote', 'set-url', 'origin', remote)
    return target
