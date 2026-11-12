import { afterEach, describe, expect, it, vi } from 'vitest';
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { PlanningManager } from '../server/planning';
import { PLANNING_BRIDGE } from '../server/planning-bridge';

const python = execFileSync('which', ['python3'], { encoding: 'utf8' }).trim();
const roots: string[] = [];
const managers: PlanningManager[] = [];
afterEach(async () => {
  vi.useRealTimers();
  await Promise.all(managers.splice(0).map(m => m.close().catch(() => {})));
  for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

// A controlled, offline dependency implementing the inspected controller interfaces.
// Deleting the adapter's ownership checks, hub.start, or revision forwarding breaks these tests.
const planner = `
from pathlib import Path
import json, time, uuid
class Planner:
    def __init__(self, repo, state_root=None, pi='pi', model=None):
        self.repo = Path(repo).resolve()
        self.root = Path(state_root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.messages = {}
    def record(self, op, **data):
        with (self.root / 'calls').open('a') as f:
            f.write(json.dumps(dict(op=op, **data)) + '\\n')
    def create(self, objective=''):
        sid = uuid.uuid4().hex
        self.record('create', id=sid, objective=objective)
        return dict(id=sid, status='ready')
    def send(self, sid, message='', on_event=None, cancel=None):
        self.record('send', id=sid, message=message)
        on_event(dict(text='你好 🌎'))
        while message == 'wait' and not cancel.wait(.01):
            pass
        if cancel.is_set():
            self.record('cancelled', id=sid)
            return dict(id=sid, status='cancelled', text='')
        if message == 'fail':
            raise RuntimeError('PASSWORD=never-disclose-this')
        return dict(id=sid, status='ready', text='你好 🌎', preview=self.preview(sid))
    def steer(self, sid, message):
        self.record('steer', message=message)
        return dict(id=sid)
    def preview(self, sid):
        self.record('preview')
        return dict(revision='review:🌎/unchanged', valid=True, diff='+ proposal only')
    def history(self, sid):
        self.record('history')
        return [dict(role='assistant', content='你好 🌎')]
    def roadmap(self, sid):
        self.record('roadmap')
        return dict(revision='roadmap', tasks=[])
    def apply(self, sid, revision):
        self.record('apply', revision=revision)
        return dict(commit='explicit-only', revision=revision)
`;
const hub = `
from concurrent.futures import ThreadPoolExecutor
import threading
class PlanningHub:
    def __init__(self, max_text=200000):
        self.turns = {}
        self.planners = {}
        self.pool = ThreadPoolExecutor(max_workers=4)
        self.max_text = max_text
    def controller(self, repo, factory):
        if repo not in self.planners:
            self.planners[repo] = factory(repo)
        return self.planners[repo]
    def start(self, repo, planner, sid, message):
        key = (repo, sid)
        if key in self.turns and self.turns[key]['status'] == 'running':
            raise ValueError('running')
        if sum(t['status'] == 'running' for t in self.turns.values()) >= 4:
            raise ValueError('limit')
        turn = dict(status='running', text='', result={}, cancel=threading.Event())
        self.turns[key] = turn
        def event(e):
            turn['text'] = (turn['text'] + e['text'])[-self.max_text:]
        def run():
            try:
                result = planner.send(sid, message, on_event=event, cancel=turn['cancel'])
                turn.update(status=result['status'], text=result['text'][-self.max_text:], result=result)
            except Exception as e:
                turn.update(status='failed', text=str(e))
        self.pool.submit(run)
        return turn
    def snapshot(self, repo, sid):
        t = self.turns.get((repo, sid))
        return dict(status=t['status'], text=t['text'], result=dict(t['result'])) if t else None
    def cancel(self, repo, sid):
        if (repo, sid) in self.turns:
            self.turns[(repo, sid)]['cancel'].set()
    def close(self):
        for t in self.turns.values():
            t['cancel'].set()
        self.pool.shutdown(wait=True, cancel_futures=True)
`;
function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'paseo-plan-'));
  roots.push(root);
  const source = join(root, 'source');
  const repo = join(root, 'repo');
  const other = join(root, 'other');
  const stateRoot = join(root, 'private', 'planning');
  mkdirSync(join(source, 'pi-autowork', 'pi_autowork'), { recursive: true });
  mkdirSync(join(source, 'scripts'));
  mkdirSync(repo); mkdirSync(other);
  writeFileSync(join(source, 'pi-autowork', 'pi_autowork', '__init__.py'), '');
  writeFileSync(join(source, 'pi-autowork', 'pi_autowork', 'planning.py'), planner);
  writeFileSync(join(source, 'pi-autowork', 'pi_autowork', 'planning_hub.py'), hub);
  writeFileSync(join(source, 'scripts/autowork_bootstrap.py'), `import sys, importlib\ndef load(root, module):\n    sys.path.insert(0, str(root / 'pi-autowork'))\n    return importlib.import_module(module)\n`);
  const options = { source, python, stateRoot };
  const manager = new PlanningManager(options);
  managers.push(manager);
  const calls = () => {
    try { return readFileSync(join(stateRoot, 'calls'), 'utf8').trim().split('\n').filter(Boolean).map(l => JSON.parse(l)); }
    catch { return []; }
  };
  return { root, source, repo, other, stateRoot, options, manager, calls };
}
async function settled(m: PlanningManager, repo: string, id: string) {
  for (let i = 0; i < 200; i++) {
    const state = await m.state(repo, id);
    if (state.status !== 'running') return state;
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  throw new Error('test turn did not settle');
}
function transportFixture(body: string) {
  const f = fixture();
  const executable = join(f.root, 'fake-python');
  writeFileSync(executable, `#!${python}\nimport sys, json, time\n${body}\n`);
  chmodSync(executable, 0o700);
  const manager = new PlanningManager({ ...f.options, python: executable });
  managers.push(manager);
  return { ...f, manager };
}

describe('owned planning adapter', () => {
  it('constructing and reconnect reads never create a session or start work', async () => {
    const f = fixture();
    expect(f.calls()).toEqual([]);
    await expect(f.manager.state(f.repo, 'a'.repeat(32))).rejects.toThrow(/unknown|owned/i);
    expect(f.calls()).toEqual([]);
  });
  it('starts a bounded live hub turn quickly and preserves Unicode progress', async () => {
    const f = fixture();
    const started = await f.manager.start(f.repo, 'wait');
    expect(started.status).toBe('running');
    const state = await f.manager.state(f.repo, started.id);
    expect(state.status).toBe('running');
    expect(state.text).toBe('你好 🌎');
    await f.manager.steer(f.repo, started.id, '/literal steer');
    await expect(f.manager.send(f.repo, started.id, 'concurrent')).rejects.toThrow();
    await expect(f.manager.view(f.repo, started.id, 'preview')).rejects.toThrow();
    await f.manager.cancel(f.repo, started.id);
    expect((await settled(f.manager, f.repo, started.id)).status).toBe('cancelled');
    expect(f.calls().filter(c => c.op === 'steer')).toEqual([{ op: 'steer', message: '/literal steer' }]);
    expect(f.calls().some(c => c.op === 'apply')).toBe(false);
  });
  it('reads are passive and only explicit apply forwards the exact staged revision', async () => {
    const f = fixture();
    const { id } = await f.manager.start(f.repo, 'literal objective');
    const state = await settled(f.manager, f.repo, id);
    expect(state.text).toBe('你好 🌎');
    const preview = await f.manager.view(f.repo, id, 'preview') as { revision: string };
    expect(preview.revision).toBe('review:🌎/unchanged');
    await f.manager.view(f.repo, id, 'history');
    await f.manager.view(f.repo, id, 'roadmap');
    await f.manager.state(f.repo, id);
    expect(f.calls().filter(c => c.op === 'send')).toHaveLength(1);
    expect(f.calls().some(c => c.op === 'apply')).toBe(false);
    await f.manager.send(f.repo, id, '/literal followup');
    await settled(f.manager, f.repo, id);
    expect(f.calls().filter(c => c.op === 'send').map(c => c.message)).toEqual(['literal objective', '/literal followup']);
    expect(await f.manager.apply(f.repo, id, preview.revision)).toEqual({ commit: 'explicit-only', revision: preview.revision });
    expect((await f.manager.state(f.repo, id)).status).toBe('applied');
    await expect(f.manager.send(f.repo, id, 'after apply')).rejects.toThrow();
  });
  it('rejects unknown, cross-repo and previous-generation sessions for every operation', async () => {
    const f = fixture();
    const { id } = await f.manager.start(f.repo, 'objective');
    await settled(f.manager, f.repo, id);
    for (const [repo, sid] of [[f.other, id], [f.repo, 'b'.repeat(32)]]) {
      await expect(f.manager.send(repo, sid, 'x')).rejects.toThrow();
      await expect(f.manager.state(repo, sid)).rejects.toThrow();
      await expect(f.manager.view(repo, sid, 'history')).rejects.toThrow();
      await expect(f.manager.apply(repo, sid, 'revision')).rejects.toThrow();
      await expect(f.manager.steer(repo, sid, 'x')).rejects.toThrow();
      await expect(f.manager.cancel(repo, sid)).rejects.toThrow();
    }
    await f.manager.close();
    const fresh = new PlanningManager(f.options); managers.push(fresh);
    await expect(fresh.state(f.repo, id)).rejects.toThrow();
    expect(f.calls().filter(c => c.op === 'create')).toHaveLength(1);
  });
  it('caps running turns before creating more retained sessions', async () => {
    const f = fixture();
    for (let i = 0; i < 4; i++) await f.manager.start(f.repo, 'wait');
    await expect(f.manager.start(f.repo, 'fifth')).rejects.toThrow(/limit|four|running/i);
    expect(f.calls().filter(c => c.op === 'create')).toHaveLength(4);
    await f.manager.close();
    expect(f.calls().filter(c => c.op === 'cancelled')).toHaveLength(4);
  });
  it('close cancels owned turns, retains records, and permanently closes the adapter', async () => {
    const f = fixture();
    await f.manager.start(f.repo, 'wait');
    await f.manager.close();
    expect(f.calls().some(c => c.op === 'cancelled')).toBe(true);
    await expect(f.manager.start(f.repo, 'again')).rejects.toThrow(/clos/i);
    await f.manager.close();
  });
  it('does not expose unsanitized controller failures', async () => {
    const f = fixture();
    const { id } = await f.manager.start(f.repo, 'fail');
    const state = await settled(f.manager, f.repo, id);
    expect(state.status).toBe('failed');
    expect(JSON.stringify(state)).not.toContain('never-disclose');
  });
  it('validates runtime paths and rejects state inside source or repo', async () => {
    const f = fixture();
    expect(() => new PlanningManager({ ...f.options, source: 'relative' })).toThrow();
    expect(() => new PlanningManager({ ...f.options, python: 'python3' })).toThrow();
    expect(() => new PlanningManager({ ...f.options, stateRoot: join(f.source, 'state') })).toThrow();
    const nested = new PlanningManager({ ...f.options, stateRoot: join(f.repo, 'state') }); managers.push(nested);
    await expect(nested.start(f.repo, 'x')).rejects.toThrow(/state|overlap/i);
    await expect(f.manager.start(f.repo, 'x'.repeat(300_000))).rejects.toThrow(/large|limit/i);
    expect(f.calls()).toEqual([]);
  });
  it.each([
    ['malformed', "sys.stdin.readline(); print('not-json', flush=True)"],
    ['oversized', "sys.stdin.readline(); sys.stdout.write('x' * (5 * 1024 * 1024)); sys.stdout.flush()"],
    ['unknown response', "sys.stdin.readline(); print(json.dumps(dict(id='foreign', result={})), flush=True)"],
    ['invalid UTF-8', "sys.stdin.readline(); sys.stdout.buffer.write(b'\\xff\\n'); sys.stdout.buffer.flush()"],
    ['stderr flood', "sys.stdin.readline(); sys.stderr.write('PASSWORD=secret\\n' * 20000); sys.stderr.flush()"],
  ])('fails closed on %s bridge output without disclosing diagnostics', async (_name, body) => {
    const f = transportFixture(body);
    await expect(f.manager.start(f.repo, 'x')).rejects.toThrow(/planning|bridge|protocol|output/i);
    await expect(f.manager.start(f.repo, 'again')).rejects.toThrow();
  });
  it('does not acknowledge a result followed by protocol corruption in the same output batch', async () => {
    const f = transportFixture("r=json.loads(sys.stdin.readline()); sys.stdout.write(json.dumps(dict(id=r['id'],result=dict(id='a'*32,status='running')))+'\\nnot-json\\n'); sys.stdout.flush(); sys.stdin.read()");
    await expect(f.manager.start(f.repo, 'x')).rejects.toThrow(/planning|bridge/i);
  });
  it('reassembles split multibyte JSON records', async () => {
    const f = transportFixture("r=json.loads(sys.stdin.readline()); data=(json.dumps(dict(id=r['id'], result=dict(id='a'*32,status='running',text='你好 🌎')),ensure_ascii=False)+'\\n').encode();\nfor b in data:\n sys.stdout.buffer.write(bytes([b])); sys.stdout.buffer.flush(); time.sleep(.001)\nsys.stdin.read()");
    expect(await f.manager.start(f.repo, 'x')).toEqual({ id: 'a'.repeat(32), status: 'running', text: '你好 🌎' });
  });
  it('does not write bytecode or other import artifacts into the selected source', async () => {
    const f = fixture();
    const { id } = await f.manager.start(f.repo, 'x');
    await settled(f.manager, f.repo, id);
    expect(existsSync(join(f.source, '__pycache__'))).toBe(false);
    expect(existsSync(join(f.source, 'pi-autowork/pi_autowork/__pycache__'))).toBe(false);
  });
  it('the Python boundary independently rejects unowned sessions, arbitrary methods and authority fields', () => {
    const f = fixture();
    const requests = [
      { method: 'state', repo: f.repo, sessionId: 'a'.repeat(32) },
      { method: 'stage', repo: f.repo, sessionId: 'a'.repeat(32) },
      { method: 'start', repo: f.repo, objective: 'x', source: '/untrusted' },
    ].map((r, i) => JSON.stringify({ id: String(i + 1), ...r })).join('\n') + '\n';
    const output = execFileSync(python, ['-I', '-B', '-c', PLANNING_BRIDGE, f.source, f.stateRoot], { input: requests, encoding: 'utf8' });
    const records = output.trim().split('\n').map(l => JSON.parse(l));
    expect(records).toHaveLength(3);
    expect(records.every(r => typeof r.error === 'string' && !('result' in r))).toBe(true);
    expect(f.calls()).toEqual([]);
  });
  it('limits concurrent outstanding requests without starting a second bridge', async () => {
    const f = transportFixture('sys.stdin.read()');
    const requests = Array.from({ length: 8 }, () => f.manager.start(f.repo, 'x').catch(e => e));
    await expect(f.manager.start(f.repo, 'ninth')).rejects.toThrow(/concurrency/i);
    await f.manager.close();
    expect((await Promise.all(requests)).every(r => r instanceof Error)).toBe(true);
  });
  it('times out stalled requests and invalidates that bridge generation', async () => {
    const f = transportFixture('sys.stdin.read()');
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const pending = f.manager.start(f.repo, 'x');
    const rejected = expect(pending).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(90_001);
    await rejected;
    vi.useRealTimers();
    await expect(f.manager.start(f.repo, 'retry')).rejects.toThrow(/timed out/i);
    await expect(f.manager.close()).rejects.toThrow(/shutdown/i);
  });
  it('bounds shutdown and rejects uncertainty when a bridge ignores EOF', async () => {
    const f = transportFixture("r=json.loads(sys.stdin.readline()); print(json.dumps(dict(id=r['id'], result=dict(id='a'*32,status='running'))),flush=True); time.sleep(60)");
    await f.manager.start(f.repo, 'x');
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] });
    const closed = f.manager.close();
    const rejected = expect(closed).rejects.toThrow(/shutdown|incomplete/i);
    await vi.advanceTimersByTimeAsync(12_001);
    await rejected;
    vi.useRealTimers();
  });
  it('does not claim successful cleanup when the owned bridge exits nonzero', async () => {
    const f = transportFixture("r=json.loads(sys.stdin.readline()); print(json.dumps(dict(id=r['id'], result=dict(id='a'*32,status='running'))),flush=True); sys.stdin.read(); sys.exit(9)");
    await f.manager.start(f.repo, 'x');
    await expect(f.manager.close()).rejects.toThrow(/shutdown|clos|exit/i);
  });
});
