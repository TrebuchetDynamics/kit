const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const plugin = require('../server.cjs');
test('native read RPCs dispatch only fixed CLI operations against configured repositories', async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'autowork-t3-test-'));
  try {
    const executable = path.join(temp, 'autowork.cjs');
    const repository = path.join(temp, 'repo');
    const trace = path.join(temp, 'argv.jsonl');
    await fs.writeFile(executable, `#!${process.execPath}\nconst fs=require('node:fs');const args=process.argv.slice(2);fs.appendFileSync(${JSON.stringify(trace)},JSON.stringify(args)+'\\n');\nif(args[0]==='ls') console.log(JSON.stringify({runners:[]}));\nelse if(args[0]==='tasks') console.log(JSON.stringify([{id:'A',title:'Read task',display:{state:'Ready',why:'Run its checks'}}]));\nelse if(args[0]==='logs') console.log('TOKEN=private');\nelse process.exit(1);\n`, { mode: 0o700 });
    const handlers = new Map(); const cleanup = [];
    plugin.activate({ settings: { get: async () => ({ executable, repositories: [repository] }) },
      rpc: { register: (name, fn, options) => { assert.equal(options.access, 'read'); handlers.set(name, fn); } }, onDeactivate: fn => cleanup.push(fn) });
    assert.deepEqual([...handlers.keys()], ['repositories', 'snapshot']);
    const [repo] = await handlers.get('repositories')();
    const context = { signal: new AbortController().signal, access: 'read' };
    await assert.rejects(handlers.get('snapshot')({ repository: '/arbitrary' }, context), /Select/);
    await assert.rejects(handlers.get('snapshot')({ repository: 'a'.repeat(24) }, context), /no longer/);
    const value = await handlers.get('snapshot')({ repository: repo.id }, context);
    assert.equal(value.repository, repo.id);
    assert.equal(value.tasks[0].state, 'Ready');
    assert.equal(value.logs.trim(), '[redacted]');
    assert.deepEqual((await fs.readFile(trace, 'utf8')).trim().split('\n').map(JSON.parse), [
      ['ls', '--json'], ['tasks', 'list', repository], ['logs', repository, '--lines', '60'],
    ]);
    cleanup.forEach(fn => fn());
    await assert.rejects(handlers.get('snapshot')({ repository: repo.id }, context), /cancelled/);
  } finally { await fs.rm(temp, { recursive: true, force: true }); }
});
