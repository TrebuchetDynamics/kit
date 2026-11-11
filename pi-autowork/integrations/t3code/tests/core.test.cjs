const { test } = require('node:test');
const assert = require('node:assert/strict');
const c = require('../core.cjs');
const signal = () => new AbortController().signal;
test('configuration admits only operator paths and gives opaque repository identities', () => {
  assert.throws(() => c.config({ executable: 'autowork', repositories: [] }), /absolute/);
  assert.throws(() => c.config({ executable: '/bin/autowork', repositories: ['--help'] }), /absolute/);
  const cfg = c.config({ executable: '/bin/autowork', repositories: ['/repo/project', '/repo/project'] });
  assert.equal(cfg.repositories.length, 1);
  assert.match(cfg.repositories[0].id, /^[a-f0-9]{24}$/);
  assert.equal(cfg.repositories[0].label, 'project');
});
test('canonical engine presentation is preserved without status classification', () => {
  assert.deepEqual(c.runnerDisplay({ runners: [{ repo: '/repo', state: 'looks done', display: { state: 'Awaiting evidence', needs: 'Review local checks', blockers: [['review', 'Evidence missing']] } }] }, '/repo'), {
    state: 'Awaiting evidence', needs: 'Review local checks', blockers: ['review: Evidence missing'],
  });
  assert.equal(c.tasks([{ id: 'A', title: 'Task', status: 'done' }])[0].state, 'Presentation unavailable');
  assert.throws(() => c.tasks([{ id: 'A', title: 'Task', display: { state: 0 } }]), /Unsupported/);
  assert.throws(() => c.runnerDisplay({ runners: 'invalid' }, '/repo'), /Unsupported/);
  assert.throws(() => c.json('secret invalid token'), error => !error.message.includes('secret'));
});
test('output sanitization removes control sequences, redacts common credentials and bounds text', () => {
  assert.equal(c.text('\x1b[31mhello\x00 TOKEN=private Bearer abcdef sk-abcdefghijk'), 'hello [redacted] [redacted] [redacted]');
  assert.equal(c.text('abcdef', 3), 'abc');
});
test('process uses literal argv, strips ambient authority and handles missing executable', async () => {
  const value = '$(touch /tmp/SHOULD_NOT_EXIST); --help';
  const out = await c.run(process.execPath, ['-e', 'process.stdout.write(process.argv[1])', '--', value], signal());
  assert.equal(out, value);
  const previous = process.env.PI_AUTOWORK_PUSH;
  process.env.PI_AUTOWORK_PUSH = '1';
  try { assert.equal(await c.run(process.execPath, ['-e', 'process.stdout.write(String(process.env.PI_AUTOWORK_PUSH))'], signal()), 'undefined'); }
  finally { if (previous === undefined) delete process.env.PI_AUTOWORK_PUSH; else process.env.PI_AUTOWORK_PUSH = previous; }
  await assert.rejects(c.run('/nonexistent/autowork', [], signal()), /Cannot execute/);
});
test('process bounds stdout, stderr, time and cancellation', async () => {
  await assert.rejects(c.run(process.execPath, ['-e', 'process.stdout.write("x".repeat(1000))'], signal(), { maxBytes: 50 }), /limit/);
  await assert.rejects(c.run(process.execPath, ['-e', 'process.stderr.write("x".repeat(1000))'], signal(), { maxBytes: 50 }), /limit/);
  await assert.rejects(c.run(process.execPath, ['-e', 'setTimeout(()=>{},10000)'], signal(), { timeout: 80 }), /timed out/);
  const controller = new AbortController();
  const result = c.run(process.execPath, ['-e', 'setTimeout(()=>{},10000)'], controller.signal);
  controller.abort();
  await assert.rejects(result, /cancelled/);
});
test('timeout and abort kill descendants holding inherited output pipes without delaying settlement', { skip: process.platform !== 'linux' }, async () => {
  const fs = require('node:fs/promises');
  const os = require('node:os');
  const path = require('node:path');
  const temporary = await fs.mkdtemp(path.join(os.tmpdir(), 't3-descendants-'));
  const descendants = [];
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  const running = async pid => {
    try { return !/^\d+ \(.*\) Z /.test(await fs.readFile(`/proc/${pid}/stat`, 'utf8')); }
    catch (error) { if (error.code === 'ENOENT') return false; throw error; }
  };
  try {
    for (const mode of ['timeout', 'abort']) {
      const ready = path.join(temporary, mode);
      const descendant = `require('node:fs').writeFileSync(${JSON.stringify(ready)},String(process.pid));setTimeout(()=>{},2500)`;
      // The immediate child exits; its grandchild still owns stdout AND stderr.
      const parent = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(descendant)}],{stdio:['ignore',1,2]});process.exit(0)`;
      const controller = new AbortController();
      const start = performance.now();
      const result = c.run(process.execPath, ['-e', parent], controller.signal, { timeout: mode === 'timeout' ? 700 : 5000 });
      const rejection = assert.rejects(result, mode === 'timeout' ? /timed out/ : /cancelled/);
      let pid;
      for (let i = 0; i < 100; i++) {
        try { pid = Number(await fs.readFile(ready, 'utf8')); break; }
        catch (error) { if (error.code !== 'ENOENT') throw error; await delay(10); }
      }
      assert.ok(pid, 'descendant must start before cancellation');
      descendants.push(pid);
      if (mode === 'abort') controller.abort();
      await rejection;
      assert.ok(performance.now() - start < 1400, 'inherited pipes must not delay settlement until descendant exit');
      for (let i = 0; i < 50 && await running(pid); i++) await delay(10);
      assert.equal(await running(pid), false, 'descendant must be killed, not merely disconnected');
    }
  } finally {
    for (const pid of descendants) { try { process.kill(pid, 'SIGKILL'); } catch {} }
    await fs.rm(temporary, { recursive: true, force: true });
  }
});
