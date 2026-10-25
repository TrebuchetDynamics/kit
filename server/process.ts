import { spawn, type ChildProcess } from 'node:child_process';
import path from 'node:path';
import process from 'node:process';
import { StringDecoder } from 'node:string_decoder';

export class CommandFailure extends Error {
  constructor(public readonly code: 'NOT_FOUND' | 'TIMEOUT' | 'OUTPUT_LIMIT' | 'EXIT' | 'INVALID_JSON' | 'BUSY' | 'CLOSED',
    message: string, public readonly started = false) { super(message); }
}
export function redact(text: string): string {
  return text.replace(/sk-[A-Za-z0-9_-]{8,}|Bearer\s+[A-Za-z0-9._~+/=-]+|[A-Za-z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Za-z0-9_]*=[^\s]+/gi, '[redacted]');
}
export type RunOptions = { timeoutMs?: number; onStderr?: (text: string) => void;
  onSpawn?: (child: ChildProcess) => void; signal?: AbortSignal };
export type CommandResult = { stdout: string; stderr: string };

/** Finite subprocess pool. Only server-authored argument arrays reach this class. */
export class ProcessRunner {
  private children = new Set<ChildProcess>();
  private active = 0;
  private closed = false;
  private readonly maxBytes: number;
  private readonly timeoutMs: number;
  private readonly concurrency: number;
  constructor(readonly executable: string, options: { maxBytes?: number; timeoutMs?: number; concurrency?: number } = {}) {
    if (!path.isAbsolute(executable)) throw new Error('Executable must be an absolute operator-controlled path');
    this.maxBytes = options.maxBytes ?? 1024 * 1024;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.concurrency = options.concurrency ?? 2;
  }
  run(args: readonly string[], options: RunOptions = {}): Promise<CommandResult> {
    if (this.closed) return Promise.reject(new CommandFailure('CLOSED', 'Plugin adapter is closed'));
    if (this.active >= this.concurrency) return Promise.reject(new CommandFailure('BUSY', 'Autowork request limit reached; refresh later'));
    if (options.signal?.aborted) return Promise.reject(new CommandFailure('CLOSED', 'Operation cancelled before dispatch'));
    this.active++;
    return new Promise((resolve, reject) => {
      // Do not inherit caller-controlled Git routing or ambient runner authority overrides.
      const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
        !key.startsWith('GIT_') && !key.startsWith('PI_AUTOWORK_') && !['NODE_OPTIONS', 'PYTHONPATH', 'PYTHONHOME', 'AUTOWORK_WORKER'].includes(key)));
      let child: ChildProcess;
      try { child = spawn(this.executable, [...args], { shell: false, env, stdio: ['ignore', 'pipe', 'pipe'] }); }
      catch { this.active--; reject(new CommandFailure('NOT_FOUND', 'Cannot execute configured Autowork')); return; }
      this.children.add(child);
      let stdout = '', stderr = '', bytes = 0, failure: CommandFailure | null = null;
      const outputDecoder = new StringDecoder('utf8'), errorDecoder = new StringDecoder('utf8');
      let escalation: ReturnType<typeof setTimeout> | undefined;
      const stop = (error: CommandFailure, signal: NodeJS.Signals = 'SIGTERM') => {
        if (failure) return;
        failure = error;
        // Only this Node-owned child, never a runner, Pi session or process-group target.
        if (child.exitCode === null && child.signalCode === null) child.kill(signal);
        escalation = setTimeout(() => {
          if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL');
        }, signal === 'SIGINT' ? 10_000 : 2_000);
        escalation.unref();
      };
      const cancelled = () => stop(new CommandFailure('CLOSED', 'Owned planning operation cancelled', true), 'SIGINT');
      options.signal?.addEventListener('abort', cancelled, { once: true });
      const timer = setTimeout(() => stop(new CommandFailure('TIMEOUT', 'Autowork command exceeded its deadline; outcome may be uncertain', true), args[0] === 'plan' ? 'SIGINT' : 'SIGTERM'), options.timeoutMs ?? this.timeoutMs);
      const accept = (chunk: Buffer, error: boolean) => {
        bytes += chunk.length;
        if (bytes > this.maxBytes) { stop(new CommandFailure('OUTPUT_LIMIT', 'Autowork output limit exceeded', true)); return; }
        const text = (error ? errorDecoder : outputDecoder).write(chunk);
        if (error) { stderr += text; options.onStderr?.(redact(text)); } else stdout += text;
      };
      child.stdout!.on('data', (chunk: Buffer) => accept(chunk, false));
      child.stderr!.on('data', (chunk: Buffer) => accept(chunk, true));
      child.once('spawn', () => options.onSpawn?.(child));
      child.once('error', () => { failure ??= new CommandFailure('NOT_FOUND', 'Cannot execute configured Autowork'); });
      child.once('close', code => {
        clearTimeout(timer); if (escalation) clearTimeout(escalation);
        options.signal?.removeEventListener('abort', cancelled);
        this.children.delete(child); this.active--;
        stdout += outputDecoder.end(); stderr += errorDecoder.end();
        if (failure) reject(failure);
        else if (code !== 0) reject(new CommandFailure('EXIT', `Autowork exited ${code ?? 'by signal'}: ${redact(stderr).slice(-1200)}`, true));
        else resolve({ stdout, stderr: redact(stderr) });
      });
    });
  }
  async json(args: readonly string[], options: RunOptions = {}): Promise<unknown> {
    const { stdout } = await this.run(args, options);
    try { return JSON.parse(stdout); }
    catch { throw new CommandFailure('INVALID_JSON', 'Autowork returned invalid JSON', true); }
  }
  async close(): Promise<void> {
    this.closed = true;
    await Promise.all([...this.children].map(child => new Promise<void>((resolve, reject) => {
      if (child.exitCode !== null || child.signalCode !== null) { resolve(); return; }
      const live = () => child.exitCode === null && child.signalCode === null;
      const term = setTimeout(() => { if (live()) child.kill('SIGTERM'); }, 1000);
      const kill = setTimeout(() => { if (live()) child.kill('SIGKILL'); }, 2000);
      const deadline = setTimeout(() => reject(new Error('Owned command cleanup is unproven; plugin shutdown incomplete')), 3000);
      child.once('close', () => { clearTimeout(term); clearTimeout(kill); clearTimeout(deadline); resolve(); });
      child.kill('SIGINT');
    })));
  }
}
