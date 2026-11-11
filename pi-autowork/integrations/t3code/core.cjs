// @ts-check
const { spawn } = require('node:child_process');
const path = require('node:path');
const { createHash } = require('node:crypto');
/** @param {unknown} value */
function object(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Unsupported Autowork response');
  return /** @type {Record<string, unknown>} */ (value);
}
/** @param {unknown} value @param {number} [max] */
function text(value, max = 1000) {
  if (typeof value !== 'string') throw new Error('Unsupported Autowork text field');
  return value.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '')
    .replace(/sk-[\w-]{8,}|Bearer\s+[\w.~+/=-]+|[\w]*(?:KEY|TOKEN|SECRET|PASSWORD)[\w]*\s*=\s*[^\s]+/gi, '[redacted]').slice(0, max);
}
/** @param {unknown} settings */
function config(settings) {
  const s = object(settings);
  if (typeof s.executable !== 'string' || !path.isAbsolute(s.executable) || /[\x00-\x1f]/.test(s.executable)) throw new Error('Configure an absolute trusted Autowork executable in plugin settings');
  if (!Array.isArray(s.repositories) || s.repositories.length > 32) throw new Error('Configure at most 32 repositories');
  const repositories = [...new Set(s.repositories.map((v) => {
    if (typeof v !== 'string' || !path.isAbsolute(v) || /[\x00-\x1f]/.test(v)) throw new Error('Repository settings require absolute paths');
    return path.normalize(v);
  }))];
  return { executable: s.executable, repositories: repositories.map(root => ({ root, id: createHash('sha256').update(root).digest('hex').slice(0, 24), label: text(path.basename(root)) })) };
}
/** Only fixed server-authored argv are passed here; output and elapsed time are bounded.
 * @param {string} executable @param {string[]} args @param {AbortSignal} signal
 * @param {{timeout?: number, maxBytes?: number}} [limits]
 */
function run(executable, args, signal, limits = {}) {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new Error('Read cancelled'));
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_') && !key.startsWith('PI_AUTOWORK_') && !['NODE_OPTIONS', 'PYTHONPATH', 'PYTHONHOME', 'AUTOWORK_WORKER'].includes(key)));
    // Linux Autowork reads may spawn descendants which inherit the output pipes.
    // Give this invocation its own process group so cancellation reaches that tree.
    const grouped = process.platform !== 'win32';
    const child = spawn(executable, args, { shell: false, detached: grouped, stdio: ['ignore', 'pipe', 'pipe'], env });
    let bytes = 0; let output = ''; let settled = false;
    /** @param {Error | null} error */
    const finish = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal.removeEventListener('abort', abort);
      if (error) reject(error); else resolve(output);
    };
    /** @param {string} message */
    const stop = (message) => {
      if (settled) return;
      if (grouped && child.pid !== undefined) {
        try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); }
      } else child.kill('SIGKILL');
      // A descendant could detach itself. Never wait on inherited pipe handles
      // to settle the request or release the snapshot concurrency slot.
      child.stdout.destroy();
      child.stderr.destroy();
      finish(new Error(message));
    };
    const abort = () => stop('Read cancelled');
    const timer = setTimeout(() => stop('Autowork read timed out'), limits.timeout ?? 8000);
    signal.addEventListener('abort', abort, { once: true });
    child.stdout.setEncoding('utf8');
    child.stdout.on('data', chunk => { bytes += Buffer.byteLength(chunk); if (bytes > (limits.maxBytes ?? 192000)) stop('Autowork output limit exceeded'); else output += chunk; });
    child.stderr.on('data', chunk => { bytes += chunk.length; if (bytes > (limits.maxBytes ?? 192000)) stop('Autowork output limit exceeded'); });
    child.stdout.on('error', () => stop('Autowork output unavailable'));
    child.stderr.on('error', () => stop('Autowork output unavailable'));
    child.on('error', () => stop('Cannot execute configured Autowork'));
    child.on('close', code => finish(code === 0 ? null : new Error('Autowork read failed; check installed CLI compatibility')));
    if (signal.aborted) abort();
  });
}
/** @param {unknown} raw @param {string} root */
function runnerDisplay(raw, root) {
  const runners = object(raw).runners;
  if (!Array.isArray(runners) || runners.length > 128) throw new Error('Unsupported Autowork fleet response');
  const runner = runners.map(object).find(r => r.repo === root);
  if (!runner) return { state: 'No registered runner', needs: 'Review committed tasks. Start runners through the existing Autowork CLI when authorized.', blockers: [] };
  if (!runner.display) return { state: 'Presentation unavailable', needs: 'Update Autowork to a release exposing canonical display fields.', blockers: [] };
  const d = object(runner.display);
  if (!Array.isArray(d.blockers) || d.blockers.length > 128) throw new Error('Unsupported blocker response');
  return { state: text(d.state), needs: text(d.needs), blockers: d.blockers.map(b => {
    if (!Array.isArray(b) || b.length !== 2) throw new Error('Unsupported blocker response');
    return `${text(b[0], 100)}: ${text(b[1], 500)}`;
  }) };
}
/** @param {unknown} raw @returns {import('./rpc.ts').Task[]} */
function tasks(raw) {
  if (!Array.isArray(raw) || raw.length > 10000) throw new Error('Unsupported task list');
  return raw.slice(0, 100).map(item => {
    const t = object(item); const d = t.display ? object(t.display) : null;
    return { id: text(t.id, 160), title: text(t.title, 300), state: d ? text(d.state, 160) : 'Presentation unavailable', why: d ? text(d.why, 500) : 'Update Autowork for canonical task presentation.' };
  });
}
/** @param {string} value */
function json(value) {
  try { return JSON.parse(value); } catch { throw new Error('Autowork returned invalid JSON; check CLI compatibility'); }
}
module.exports = { json, object, text, config, run, runnerDisplay, tasks };
