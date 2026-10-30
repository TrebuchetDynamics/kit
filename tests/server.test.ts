import { afterEach, describe, expect, it } from 'vitest';
import { mkdtemp, writeFile, chmod, rm, symlink, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { ProcessRunner } from '../server/process';
import { AutoworkService } from '../server/autowork-client';
import { loadConfig } from '../server/config';
import { repositoryIdentity } from '../server/discovery';

import { fixture, cleanupFixtures } from './fixture';
afterEach(cleanupFixtures);

describe('bounded command adapter', () => {
  it('uses literal argv without shell expansion and bounds invalid output/time', async () => {
    const f = await fixture(); const p = new ProcessRunner(f.exe, { maxBytes: 4096, timeoutMs: 1000 });
    await p.run(['literal', '$(touch SHOULD_NOT_EXIST); rm -rf /']);
    const calls = (await readFile(f.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls[0][1]).toBe('$(touch SHOULD_NOT_EXIST); rm -rf /');
    expect(await p.json(['unicode'])).toBe('é');
    await expect(p.json(['invalid'])).rejects.toMatchObject({ code: 'INVALID_JSON' });
    await expect(p.run(['large'])).rejects.toMatchObject({ code: 'OUTPUT_LIMIT' });
    await expect(p.run(['hang'], { timeoutMs: 60 })).rejects.toMatchObject({ code: 'TIMEOUT' });
    await expect(p.json(['fail'])).rejects.toMatchObject({ code: 'EXIT' });
    await p.close();
  });
  it('redacts secrets split across stderr chunks and flushes a final unterminated line', async () => {
    const f = await fixture();
    await writeFile(f.exe, `#!/usr/bin/env node
process.stderr.write('safe progress\\nSECRET_TO');
setTimeout(() => {
  process.stderr.write('KEN=private-value\\nBearer ');
  setTimeout(() => process.stderr.write('private-bearer'), 30);
}, 30);
`);
    const p = new ProcessRunner(f.exe);
    const streamed: string[] = [];
    try {
      const result = await p.run([], { onStderr: text => streamed.push(text) });
      expect(streamed.join('')).toBe('safe progress\n[redacted]\n[redacted]');
      expect(result.stderr).toBe(streamed.join(''));
    } finally { await p.close(); }
  });
  it.each(['\n', '\r\n', '\n\n\t'])('redacts a Bearer credential across a %j line boundary', async separator => {
    const f = await fixture();
    await writeFile(f.exe, `#!/usr/bin/env node
process.stderr.write(${JSON.stringify('safe progress\nBearer' + separator)});
setTimeout(() => {
  process.stderr.write('private-');
  setTimeout(() => process.stderr.write('bearer\\n'), 30);
}, 30);
`);
    const p = new ProcessRunner(f.exe);
    const streamed: string[] = [];
    try {
      const result = await p.run([], { onStderr: text => streamed.push(text) });
      expect(streamed.join('')).toBe('safe progress\n[redacted]\n');
      expect(result.stderr).toBe(streamed.join(''));
    } finally { await p.close(); }
  });
  it('withholds an incomplete stderr credential when a command fails or exceeds its output budget', async () => {
    const f = await fixture();
    for (const ending of ["process.exitCode = 2;", "process.stdout.write('x'.repeat(2048));"]) {
      await writeFile(f.exe, `#!/usr/bin/env node
process.stderr.write('safe progress\\nSECRET_TO');
setTimeout(() => { ${ending} }, 30);
`);
      const p = new ProcessRunner(f.exe, { maxBytes: 1024 });
      const streamed: string[] = [];
      try {
        await expect(p.run([], { onStderr: text => streamed.push(text) })).rejects.toMatchObject({
          code: ending.includes('exitCode') ? 'EXIT' : 'OUTPUT_LIMIT',
        });
        expect(streamed.join('')).toBe('safe progress\n');
      } finally { await p.close(); }
    }
  });
  it('teardown has a finite deadline even when an owned command ignores graceful signals', async () => {
    const f = await fixture(); const p = new ProcessRunner(f.exe);
    let ready!: () => void; const observed = new Promise<void>(resolve => { ready = resolve; });
    const running = p.run(['ignore'], { onStderr: () => ready() });
    const stopped = running.catch(() => undefined);
    await observed;
    const start = Date.now(); await p.close();
    expect(Date.now() - start).toBeLessThan(4000);
    await stopped;
  }, 5000);
  it('does not accept relative executables or unlimited parallel processes', async () => {
    expect(() => new ProcessRunner('autowork')).toThrow(/absolute/);
    const f = await fixture(); const p = new ProcessRunner(f.exe, { concurrency: 1 });
    const first = p.run(['hang'], { timeoutMs: 100 });
    await expect(p.run(['hang'])).rejects.toMatchObject({ code: 'BUSY' });
    await expect(first).rejects.toMatchObject({ code: 'TIMEOUT' }); await p.close();
    await expect(p.run(['ls'])).rejects.toMatchObject({ code: 'CLOSED' });
  });
});

describe('authoritative discovery', () => {
  it('shares concurrent Git identity probes instead of accumulating subprocesses', async () => {
    const f = await fixture();
    const first = repositoryIdentity(f.repo), second = repositoryIdentity(f.repo);
    expect(first).toBe(second);
    await first;
  });
  it('shares one fleet collector and preserves canonical stalled/paused observations', async () => {
    const f = await fixture(); const service = new AutoworkService({ executable: f.exe, repositories: [], planning: false, decisions: false, controls: [] });
    const [a, b] = await Promise.all([service.fleet(), service.fleet()]);
    expect(a).toEqual(b); expect(a.repos[0]?.runner?.state).toBe('stalled');
    expect(a.repos[0]?.runner?.running).toBe(0); expect(a.repos[0]?.runner?.lanes[0]?.phase).toBe('paused');
    expect(a.permissions.planning).toBe(false);
    const calls = (await readFile(f.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.filter(x => x[0] === 'ls')).toHaveLength(1);
    await expect(service.tasks('wrong-generation', a.repos[0]!.id)).rejects.toThrow(/generation/);
    await expect(service.tasks(a.instance, 'unexpected-repo')).rejects.toThrow(/known/);
    await service.close();
  });
  it('does not expose transactional working-tree reads through a read-only detail RPC', async () => {
    const f = await fixture(); const service = new AutoworkService({ executable: f.exe, repositories: [], planning: false, decisions: false, controls: [] });
    const snapshot = await service.fleet();
    await expect(service.task(snapshot.instance, snapshot.repos[0]!.id, 'T-1', true)).rejects.toThrow(/working.tree|committed/i);
    const calls = (await readFile(f.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.some(x => x.includes('--worktree'))).toBe(false);
    await service.close();
  });
  it('rejects a repository replaced by an alias after discovery', async () => {
    const f = await fixture(); const service = new AutoworkService({ executable: f.exe, repositories: [], planning: false, decisions: false, controls: [] });
    const snap = await service.fleet(); const entry = snap.repos[0]!;
    await rm(f.repo, { recursive: true }); await symlink(f.root, f.repo);
    await expect(service.tasks(snap.instance, entry.id)).rejects.toThrow(/identity|changed|symlink/);
    await service.close();
  });
  it('reports an incompatible Autowork API instead of an empty fleet', async () => {
    const f = await fixture(); await writeFile(f.exe, (await readFile(f.exe, 'utf8')).replace('prepare_api:4', 'prepare_api:3'));
    const service = new AutoworkService({ executable: f.exe, repositories: [], planning: false, decisions: false, controls: [] });
    await expect(service.fleet()).rejects.toThrow(/prepare API 4.*3/);
    await service.close();
  });
  it('does not let client-editable settings grant mutation authority', async () => {
    const config = await loadConfig({ PATH: '' });
    expect(config.planning).toBe(false); expect(config.decisions).toBe(false); expect(config.controls).toEqual([]);
  });
});
