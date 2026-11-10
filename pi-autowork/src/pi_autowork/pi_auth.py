"""Bounded JSON-lines bridge to Pi's official credential owner (SDK 1.5.0).

Secrets travel only over anonymous stdin, never argv, environment or diagnostics.
"""
import asyncio
import json
import os
from pathlib import Path
import shutil


class AuthError(RuntimeError):
    pass


def sdk_root(pi='pi'):
    explicit = os.environ.get('AUTOWORK_PI_SDK')
    candidates = [Path(explicit).expanduser()] if explicit else []
    candidates.append(Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) /
                      'kit/pi-auth-sdk/1.5.0/node_modules/@earendil-works/pi-coding-agent')
    executable = shutil.which(pi)
    if executable:
        path = Path(executable).resolve()
        candidates += [path.parent, path.parent.parent, path.parent.parent.parent]
    node = shutil.which('node')
    if node:
        candidates.append(Path(node).resolve().parent.parent / 'lib/node_modules/@earendil-works/pi-coding-agent')
    if explicit:
        candidates = [Path(explicit).expanduser()]
    for root in candidates:
        try:
            package = json.loads((root / 'package.json').read_text())
            if (package.get('name') == '@earendil-works/pi-coding-agent' and
                    package.get('version') == '1.5.0' and (root / 'dist/index.js').is_file()):
                return root
        except (OSError, ValueError):
            pass
    raise AuthError('Pi SDK 1.5.0 unavailable. Install the matching SDK (runner guide), then Refresh. '
                    'AUTOWORK_PI_SDK may select its package directory.')


class Bridge:
    def __init__(self, agent_dir, pi=None):
        self.agent_dir, self.pi, self.process = agent_dir, pi or os.environ.get('AUTOWORK_PI', 'pi'), None
        self.prompt_id = None

    async def run(self, operation, receive, provider='', method=''):
        root = sdk_root(self.pi)
        node = shutil.which('node')
        if not node:
            raise AuthError('Node.js is unavailable; the Pi SDK authentication helper needs Node.js.')
        env = dict(os.environ, AUTOWORK_PI_SDK=str(root), PI_CODING_AGENT_DIR=self.agent_dir, PI_OFFLINE='1')
        try:
            self.process = await asyncio.create_subprocess_exec(
                node, str(Path(__file__).with_suffix('.mjs')), operation, provider, method,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, env=env, cwd=str(Path.home()), limit=262144)
            async with asyncio.timeout(600 if operation == 'login' else 20):
                while line := await self.process.stdout.readline():
                    event = json.loads(line)
                    if event.get('type') == 'prompt':
                        self.prompt_id = event.get('id')
                    elif event.get('type') == 'clear_prompt':
                        if event.get('id') != self.prompt_id:
                            continue
                        self.prompt_id = None
                    await receive(event)
                rc = await self.process.wait()
                if rc:
                    raise AuthError('Pi authentication failed. Check the provider and credentials, then retry.')
        except asyncio.CancelledError:
            raise
        except AuthError:
            raise
        except (OSError, ValueError, TimeoutError):
            raise AuthError('Pi authentication helper unavailable or timed out. Retry setup.') from None
        finally:
            await self.close()

    async def answer(self, value):
        if self.process and self.process.returncode is None:
            self.process.stdin.write((json.dumps({'type': 'answer', 'id': self.prompt_id, 'value': value}) + '\n').encode())
            self.prompt_id = None
            await self.process.stdin.drain()

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()


def catalog(agent_dir, pi='pi'):
    """Read non-secret provider metadata; safe on empty catalogs, no network."""
    events = []
    async def receive(event):
        if event.get('type') == 'catalog':
            events.extend(event.get('providers', []))
    asyncio.run(Bridge(agent_dir, pi).run('catalog', receive))
    return events
