import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { accessSync, constants, lstatSync, realpathSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { TextDecoder } from 'node:util';
import { PLANNING_BRIDGE } from './planning-bridge';

export type PlanningOptions = { source: string; python: string; stateRoot: string; pi?: string };
type Turn = { id: string; status: string; text?: string };
type State = { status: string; text: string; result?: Record<string, unknown> };
type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };
const MAX_LINE = 4 * 1024 * 1024;
const MAX_REQUEST = 256 * 1024;
const MAX_PENDING = 8;
const REQUEST_TIMEOUT = 90_000;
const CLOSE_TIMEOUT = 10_000;

function absolute(path: string, label: string): string {
  if (typeof path !== 'string' || !isAbsolute(path) || path.includes('\0')) throw new Error(`Planning ${label} must be absolute`);
  return resolve(path);
}
function inside(path: string, parent: string): boolean {
  const rel = relative(parent, path);
  return !rel || (rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel));
}
function overlap(a: string, b: string): boolean { return inside(a, b) || inside(b, a); }
function executable(path: string, label: string): string {
  const canonical = realpathSync(absolute(path, label));
  if (!statSync(canonical).isFile()) throw new Error(`Planning ${label} must be an executable file`);
  accessSync(canonical, constants.X_OK);
  return canonical;
}
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
function boundedText(value: string, limit = 65536): void {
  if (typeof value !== 'string' || Buffer.byteLength(value, 'utf8') > limit) throw new Error('Planning text exceeds size limit');
}

/** Owns one stdio bridge generation, never attaches retained or externally created sessions. */
export class PlanningManager {
  private readonly options: PlanningOptions;
  private child?: ChildProcessWithoutNullStreams;
  private readonly owned = new Map<string, string>();
  private readonly pending = new Map<string, Pending>();
  private sequence = 0;
  private output = Buffer.alloc(0);
  private stderrBytes = 0;
  private failure?: Error;
  private closing = false;
  private closePromise?: Promise<void>;
  private exited?: Promise<{ code: number | null; signal: NodeJS.Signals | null }>;

  constructor(options: PlanningOptions) {
    const source = realpathSync(absolute(options.source, 'source'));
    for (const file of ['scripts/autowork_bootstrap.py', 'src/pi_autowork/planning.py', 'src/pi_autowork/planning_hub.py']) {
      const path = realpathSync(join(source, file));
      if (!inside(path, source) || !statSync(path).isFile()) throw new Error('Planning controller escapes selected source');
    }
    const stateRoot = absolute(options.stateRoot, 'state root');
    // Do not follow existing state symlinks, including symlinked ancestors.
    for (let path = stateRoot; ; path = dirname(path)) {
      try {
        if (lstatSync(path).isSymbolicLink()) throw new Error('Planning state root must not contain symlinks');
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
      }
      if (dirname(path) === path) break;
    }
    const upstream = [join(homedir(), '.local/state/pi-autowork/planning'),
      join(process.env.XDG_STATE_HOME || join(homedir(), '.local/state'), 'pi-autowork/planning')];
    if (overlap(stateRoot, source) || upstream.some(path => overlap(stateRoot, resolve(path)))) {
      throw new Error('Planning requires an isolated plugin state root');
    }
    this.options = { source, stateRoot, python: executable(options.python, 'python'),
      ...(options.pi === undefined ? {} : { pi: executable(options.pi, 'pi') }) };
  }

  async start(repo: string, objective: string, options: { mode?: string; task?: string; model?: string } = {}): Promise<Turn> {
    this.available();
    boundedText(objective);
    const mode = options.mode ?? 'plan';
    if (!['plan', 'discuss', 'investigate'].includes(mode)) throw new Error('Planning mode must be plan, discuss or investigate');
    const task = options.task ?? '', model = options.model ?? '';
    boundedText(task, 160); boundedText(model, 200);
    const canonical = this.repository(repo);
    const value = this.turn(await this.request('start', { repo: canonical, objective, mode, task, model }));
    if (this.owned.has(value.id)) return this.invalid();
    this.owned.set(value.id, canonical);
    return value;
  }

  async send(repo: string, sessionId: string, message: string): Promise<Turn> {
    const canonical = this.session(repo, sessionId);
    boundedText(message);
    const value = this.turn(await this.request('send', { repo: canonical, sessionId, message }));
    if (value.id !== sessionId) return this.invalid();
    return value;
  }

  async state(repo: string, sessionId: string): Promise<State> {
    const canonical = this.session(repo, sessionId);
    const value = await this.request('state', { repo: canonical, sessionId });
    if (!record(value) || typeof value.status !== 'string' || typeof value.text !== 'string'
      || (value.result !== undefined && !record(value.result))) return this.invalid();
    return value as State;
  }

  async view(repo: string, sessionId: string, view: 'preview' | 'history' | 'roadmap'): Promise<unknown> {
    const canonical = this.session(repo, sessionId);
    if (!['preview', 'history', 'roadmap'].includes(view)) throw new Error('Unknown planning view');
    return this.request(view, { repo: canonical, sessionId });
  }

  async apply(repo: string, sessionId: string, revision: string): Promise<unknown> {
    const canonical = this.session(repo, sessionId);
    boundedText(revision, 4096);
    return this.request('apply', { repo: canonical, sessionId, revision });
  }

  async steer(repo: string, sessionId: string, message: string): Promise<unknown> {
    const canonical = this.session(repo, sessionId);
    boundedText(message);
    return this.request('steer', { repo: canonical, sessionId, message });
  }

  async cancel(repo: string, sessionId: string): Promise<unknown> {
    return this.request('cancel', { repo: this.session(repo, sessionId), sessionId });
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closing = true;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error('Planning manager is closing; operation may be incomplete'));
    }
    this.pending.clear();
    this.owned.clear();
    this.output = Buffer.alloc(0);
    this.closePromise = this.shutdown();
    return this.closePromise;
  }

  private available(): void {
    if (this.failure) throw this.failure;
    if (this.closing) throw new Error('Planning manager is closed');
  }

  private repository(repo: string): string {
    const canonical = realpathSync(absolute(repo, 'repository'));
    if (!statSync(canonical).isDirectory() || overlap(canonical, this.options.stateRoot)) {
      throw new Error('Planning state and repository must not overlap');
    }
    return canonical;
  }

  private session(repo: string, id: string): string {
    this.available();
    if (typeof id !== 'string' || !this.owned.has(id)) throw new Error('Unknown owned planning session');
    const canonical = this.repository(repo);
    if (this.owned.get(id) !== canonical) throw new Error('Planning session repository mismatch');
    return canonical;
  }

  private turn(value: unknown): Turn {
    if (!record(value) || typeof value.id !== 'string' || !/^[a-f0-9]{32}$/.test(value.id)
      || typeof value.status !== 'string' || (value.text !== undefined && typeof value.text !== 'string')) return this.invalid();
    return value as Turn;
  }

  private invalid(): never {
    this.fail(new Error('Invalid planning bridge protocol'));
    throw this.failure;
  }

  private launch(): void {
    if (this.child) return;
    const { source, python, stateRoot, pi } = this.options;
    // -I ignores PYTHONPATH/user site and the working directory. The selected release's
    // bootstrap is the sole import authority; no shell and no frontend-supplied argv.
    const child = this.child = spawn(python, ['-I', '-B', '-u', '-c', PLANNING_BRIDGE, source, stateRoot, ...(pi ? [pi] : [])], {
      cwd: source, stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env },
    });
    this.exited = new Promise(resolveExit => {
      child.once('close', (code, signal) => {
        if (!this.closing) this.fail(new Error('Planning bridge exited unexpectedly; sessions cannot be adopted'));
        resolveExit({ code, signal });
      });
    });
    child.once('error', () => this.fail(new Error('Planning bridge could not start')));
    child.stdin.on('error', () => { if (!this.closing) this.fail(new Error('Planning bridge input failed')); });
    child.stdout.on('error', () => this.fail(new Error('Planning bridge output failed')));
    child.stderr.on('error', () => this.fail(new Error('Planning bridge diagnostics failed')));
    child.stdout.on('data', (chunk: Buffer) => this.receive(chunk));
    // Never forward raw stderr: it can include provider credentials, source, or paths.
    child.stderr.on('data', (chunk: Buffer) => {
      this.stderrBytes += chunk.length;
      if (this.stderrBytes > 65536) this.fail(new Error('Planning bridge diagnostic output exceeded limit'));
    });
  }

  private request(method: string, fields: Record<string, string>): Promise<unknown> {
    this.available();
    if (this.pending.size >= MAX_PENDING) return Promise.reject(new Error('Planning request concurrency limit reached'));
    const id = String(++this.sequence);
    const line = Buffer.from(JSON.stringify({ id, method, ...fields }) + '\n');
    if (line.length > MAX_REQUEST) return Promise.reject(new Error('Planning request exceeds size limit'));
    this.launch();
    return new Promise<unknown>((resolveReply, reject) => {
      const timer = setTimeout(() => this.fail(new Error('Planning bridge request timed out; operation may be incomplete')), REQUEST_TIMEOUT);
      this.pending.set(id, { resolve: resolveReply, reject, timer });
      this.child!.stdin.write(line, error => {
        if (error) this.fail(new Error('Planning bridge input failed; operation may be incomplete'));
      });
    }).then(value => {
      // A later record in the same batch may have invalidated the generation.
      this.available();
      return value;
    });
  }

  private receive(chunk: Buffer): void {
    if (this.closing || this.failure) return;
    // At most one bounded partial line is retained; every complete line must settle
    // exactly one of <=8 pending requests. Unsolicited/flooded records fail closed.
    let offset = 0;
    while (offset < chunk.length) {
      const newline = chunk.indexOf(10, offset);
      const end = newline < 0 ? chunk.length : newline + 1;
      const piece = chunk.subarray(offset, end);
      if (this.output.length + piece.length > MAX_LINE) { this.fail(new Error('Planning bridge output exceeded limit')); return; }
      this.output = Buffer.concat([this.output, piece]);
      offset = end;
      if (newline < 0) return;
      let value: unknown;
      try { value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(this.output)); }
      catch { this.fail(new Error('Invalid planning bridge output')); return; }
      this.output = Buffer.alloc(0);
      if (!record(value) || typeof value.id !== 'string' || !this.pending.has(value.id)
        || (Object.keys(value).sort().join(',') !== 'id,result' && Object.keys(value).sort().join(',') !== 'error,id')
        || ('error' in value && typeof value.error !== 'string')) { this.fail(new Error('Invalid planning bridge protocol')); return; }
      const pending = this.pending.get(value.id)!;
      this.pending.delete(value.id);
      clearTimeout(pending.timer);
      // The bridge returns only fixed safe refusals, but do not trust an executable's
      // arbitrary error strings with frontend diagnostics.
      if ('error' in value) pending.reject(new Error('Planning operation refused or failed; session may be running, at its limit, or unavailable'));
      else pending.resolve(value.result);
    }
  }

  private fail(error: Error): void {
    if (this.failure) return;
    this.failure = error;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    this.output = Buffer.alloc(0);
    // Close only our child. Never signal a runner, PID read from disk, or process group.
    void this.close().catch(() => {});
  }

  private async shutdown(): Promise<void> {
    if (!this.child || !this.exited) return;
    this.child.stdin.end(); // EOF invokes hub.close(), cancelling all owned turns.
    const wait = async (ms: number) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        return await Promise.race([this.exited!, new Promise<undefined>(resolveWait => { timer = setTimeout(() => resolveWait(undefined), ms); })]);
      } finally { clearTimeout(timer); }
    };
    let result = await wait(CLOSE_TIMEOUT);
    let forced = false;
    if (!result) {
      forced = true;
      this.child.kill('SIGTERM');
      result = await wait(1000);
    }
    if (!result) {
      this.child.kill('SIGKILL');
      result = await wait(1000);
    }
    if (forced || !result || result.code !== 0 || result.signal || this.failure) {
      throw new Error('Planning bridge shutdown was not clean; owned work may be incomplete; inspect retained records');
    }
  }
}
