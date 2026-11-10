import { randomUUID, createHash } from 'node:crypto';
import { lstat, readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';
import { fleetSchema, goalSchema, runnerSchema, taskSchema, taskDetailSchema, type Fleet, type Repo, type StoreView, type TaskDetail } from '../shared/contracts';
import { type Config, effectivePolicy, resolveExecutable } from './config';
import { assertIdentity, repositoryIdentity, type Identity } from './discovery';
import { ProcessRunner, redact } from './process';

const capabilitiesSchema = z.object({ tool: z.literal('autowork'), release: z.string().min(1), prepare_api: z.literal(4),
  commands: z.array(z.string()), tasks: z.array(z.string()), toolset: z.string().optional() });
type Capabilities = z.infer<typeof capabilitiesSchema>;
function parseCapabilities(value: unknown): Capabilities {
  const result = capabilitiesSchema.safeParse(value);
  if (!result.success) {
    const api = value !== null && typeof value === 'object' && 'prepare_api' in value
      && typeof value.prepare_api === 'number' ? String(value.prepare_api) : 'missing or invalid';
    throw new Error(`Incompatible Autowork: requires prepare API 4 and fleet/task/planning contracts; received API ${api}`);
  }
  return result.data;
}
const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms));
const READ_SLOT = { waitForSlotMs: 5000 };
const WATCH_WINDOW = 20_000;
const WATCH_STEP = 2_000;

export class AutoworkService {
  readonly instance = randomUUID();
  readonly config: Config;
  private runner: ProcessRunner | null = null;
  private executableIdentity = '';
  private initialized: Promise<void> | null = null;
  private capabilities: Capabilities | null = null;
  private executable = '';
  private cache: Fleet | null = null;
  private collection: Promise<Fleet> | null = null;
  private known = new Map<string, Identity>();
  private closed = false;
  constructor(config: Config) { this.config = config; }
  get policy() { return effectivePolicy(this.config); }
  private async stamp(file: string): Promise<string> {
    const s = await lstat(file); if (!s.isFile() || s.isSymbolicLink()) throw new Error('Executable identity changed');
    return `${s.dev}:${s.ino}:${s.size}:${s.mtimeMs}`;
  }
  async commands(): Promise<ProcessRunner> {
    if (this.closed) throw new Error('Autowork plugin is closed');
    this.initialized ??= (async () => {
      this.executable = await resolveExecutable(this.config.executable);
      this.executableIdentity = await this.stamp(this.executable);
      if (this.closed) throw new Error('Autowork plugin closed during initialization');
      this.runner = new ProcessRunner(this.executable, { maxBytes: 4 * 1024 * 1024, concurrency: 3 });
      const cap = parseCapabilities(await this.runner.json(['capabilities'], READ_SLOT));
      if (!['ls', 'tasks', 'plan', 'logs'].every(c => cap.commands.includes(c)) || !['list', 'show', 'decide'].every(c => cap.tasks.includes(c))) {
        throw new Error('Installed Autowork lacks the required fleet/task/planning command contract');
      }
      this.capabilities = cap;
    })();
    try { await this.initialized; }
    catch (error) { this.initialized = null; this.cache = null; await this.runner?.close(); this.runner = null; throw error; }
    if (this.executableIdentity !== await this.stamp(this.executable)) throw new Error('Autowork executable changed; reload the plugin to qualify its new release');
    return this.runner!;
  }
  /** Refuse before dispatch when the installed release lacks a command or `tasks` verb. */
  async require(command: string, verb?: string): Promise<ProcessRunner> {
    const commands = await this.commands();
    const cap = this.capabilities!;
    if (!cap.commands.includes(command) || (verb && !cap.tasks.includes(verb))) {
      throw new Error(`Installed Autowork release lacks \`autowork ${command}${verb ? ' ' + verb : ''}\`; update the executable named by the policy`);
    }
    return commands;
  }
  async verifyRelease(): Promise<void> {
    const commands = await this.commands();
    const current = parseCapabilities(await commands.json(['capabilities'], READ_SLOT));
    if (current.release !== this.capabilities!.release || current.toolset !== this.capabilities!.toolset) {
      this.cache = null;
      throw new Error('Autowork source release changed; reload and requalify before another operation');
    }
  }
  async source(): Promise<string> {
    await this.verifyRelease();
    const source = this.capabilities?.toolset;
    if (!source || !path.isAbsolute(source)) throw new Error('Installed Autowork does not expose an absolute controller source');
    return source;
  }
  checkInstance(instance: string): void {
    if (instance !== this.instance) throw new Error('Plugin host generation changed; refresh and confirm again (no replay)');
  }
  invalidate(): void { this.cache = null; }
  async fleet(force = false): Promise<Fleet> {
    if (this.closed) throw new Error('Autowork plugin is closed');
    if (!force && this.cache && Date.now() - this.cache.capturedAt < 5000) return this.cache;
    if (this.collection) return this.collection;
    this.collection = this.collect();
    try { return await this.collection; }
    finally { this.collection = null; }
  }
  private async collect(): Promise<Fleet> {
    try {
      const commands = await this.commands();
      await this.verifyRelease();
      const { runners } = z.object({ runners: z.array(runnerSchema).max(128) }).parse(await commands.json(['ls', '--json'], READ_SLOT));
      const candidates = new Map<string, z.infer<typeof runnerSchema> | null>();
      for (const r of runners) if (r.repo) candidates.set(r.repo, r);
      for (const directory of this.config.repositories) if (!candidates.has(directory)) candidates.set(directory, null);
      if (candidates.size > 128) throw new Error('Too many known Autowork repositories for a bounded snapshot');
      const known = new Map<string, Identity>(); const repos: Repo[] = []; const warnings: string[] = [];
      for (const [directory, runner] of candidates) {
        try {
          const identity = await repositoryIdentity(directory); known.set(identity.id, identity);
          repos.push({ id: identity.id, label: runner?.name ?? path.basename(identity.root), path: identity.root,
            identity: identity.identity, revision: identity.revision, runner, error: null });
        } catch {
          const id = 'missing-' + createHash('sha256').update(directory).digest('hex').slice(0, 16);
          repos.push({ id, label: runner?.name ?? path.basename(directory), path: directory, identity: '', revision: '',
            runner, error: 'Repository unavailable or identity mismatch; actions disabled' });
          warnings.push(`Repository ${runner?.name ?? path.basename(directory)} is unavailable`);
        }
      }
      if (this.closed) throw new Error('Autowork plugin closed during collection');
      this.known = known;
      const cap = this.capabilities!;
      this.cache = fleetSchema.parse({ instance: this.instance, capturedAt: Date.now(), release: cap.release, toolset: cap.toolset ?? '',
        executable: this.executable, prepareApi: cap.prepare_api, permissions: this.policy,
        policy: { path: this.config.path, source: this.config.source },
        capabilities: { commands: [...cap.commands].sort(), tasks: [...cap.tasks].sort() }, repos, warnings });
      return this.cache;
    } catch (error) { this.cache = null; this.known.clear(); throw error; }
  }
  async repo(instance: string, id: string): Promise<Identity> {
    this.checkInstance(instance);
    if (!this.known.has(id)) await this.fleet();
    const before = this.known.get(id); if (!before) throw new Error('Repository is not a known Autowork target on this host');
    return assertIdentity(before);
  }
  /** Working-tree reads are transactional edits in progress; only a task-edit grant exposes them. */
  private workingAllowed(working: boolean): void {
    if (working && !this.policy.tasks) throw new Error('Transactional working-tree reads are not exposed; inspect committed records instead');
  }
  async tasks(instance: string, repoId: string, working = false) {
    this.workingAllowed(working);
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    const tasks = z.array(taskSchema).max(10000).parse(await commands.json(['tasks', 'list', repo.root, ...(working ? ['--worktree'] : ['--rev', repo.revision])], READ_SLOT));
    return { revision: working ? `${repo.revision}+working` : repo.revision, tasks };
  }
  async task(instance: string, repoId: string, task: string, working = false): Promise<TaskDetail> {
    this.workingAllowed(working);
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    return taskDetailSchema.parse(await commands.json(['tasks', 'show', task, repo.root, ...(working ? ['--worktree'] : ['--rev', repo.revision])], READ_SLOT));
  }
  async goals(instance: string, repoId: string, working = false) {
    this.workingAllowed(working);
    const repo = await this.repo(instance, repoId); const commands = await this.require('tasks', 'goals');
    const goals = z.array(goalSchema).max(1000).parse(await commands.json(['tasks', 'goals', repo.root, ...(working ? ['--worktree'] : ['--rev', repo.revision])], READ_SLOT));
    return { revision: working ? `${repo.revision}+working` : repo.revision, goals };
  }
  async logs(instance: string, repoId: string, lines = 150) {
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    const { stdout } = await commands.run(['logs', repo.root, '--lines', String(lines)], READ_SLOT);
    return { text: redact(stdout).slice(-256000), capturedAt: Date.now() };
  }
  async status(instance: string, repoId: string) {
    const repo = await this.repo(instance, repoId); const commands = await this.require('status');
    const { stdout } = await commands.run(['status', repo.root], { ...READ_SLOT, timeoutMs: 60_000, acceptExit: [1] });
    return { text: redact(stdout).slice(-64000), capturedAt: Date.now() };
  }
  async scorecard(instance: string, days = 7) {
    this.checkInstance(instance); const commands = await this.require('scorecard');
    const value = await commands.json(['scorecard', '--json', '--days', String(days)], { ...READ_SLOT, timeoutMs: 180_000 });
    return { value, capturedAt: Date.now() };
  }
  async models(instance: string) {
    this.checkInstance(instance); const commands = await this.require('models');
    const { stdout } = await commands.run(['models'], { ...READ_SLOT, timeoutMs: 60_000 });
    const models = redact(stdout).split('\n').map(line => line.trim()).filter(line => /^[A-Za-z0-9][A-Za-z0-9._:/-]*$/.test(line)).slice(0, 500);
    return { models, capturedAt: Date.now() };
  }
  async store(instance: string, repoId: string, view: StoreView, task?: string) {
    const repo = await this.repo(instance, repoId);
    let value: unknown;
    if (view === 'validate') value = await (await this.require('tasks', 'validate')).json(['tasks', 'validate', '--worktree', repo.root], { ...READ_SLOT, acceptExit: [1] });
    else if (view === 'prepare') value = await (await this.require('tasks', 'prepare')).json(['tasks', 'prepare', '--check', repo.root], { ...READ_SLOT, acceptExit: [1, 3], timeoutMs: 120_000 });
    else if (view === 'pending') value = await (await this.require('tasks', 'commit')).json(['tasks', 'commit', '--dry-run', repo.root], READ_SLOT);
    else {
      if (!task) throw new Error('A task ID is required for the selection explanation');
      value = await (await this.require('tasks', 'why')).json(['tasks', 'why', task, repo.root, '--rev', repo.revision], READ_SLOT);
    }
    return { value, capturedAt: Date.now() };
  }
  /** A cheap fingerprint of what the views show: task records, Git heads and runner state files. */
  private async digest(): Promise<string> {
    const fleet = this.cache ?? await this.fleet();
    const hash = createHash('sha256');
    const mark = async (file: string) => {
      try { const s = await stat(file); hash.update(`${file}:${s.mtimeMs}:${s.size};`); }
      catch { hash.update(`${file}:-;`); }
    };
    for (const repo of fleet.repos) {
      if (!repo.path || repo.error) continue;
      for (const dir of ['tasks/items', 'tasks/goals']) {
        try {
          const names = (await readdir(path.join(repo.path, dir))).sort().slice(0, 5000);
          for (const name of names) await mark(path.join(repo.path, dir, name));
        } catch { hash.update(`${dir}:-;`); }
      }
      const identity = this.known.get(repo.id);
      if (identity) for (const name of ['HEAD', 'ORIG_HEAD', 'logs/HEAD']) await mark(path.join(identity.common, name));
      const state = repo.runner?.state_dir;
      if (state && path.isAbsolute(state)) for (const name of ['status.json', 'restart-status.json', 'runner.json', 'session.json', 'stop.json']) await mark(path.join(state, name));
    }
    return hash.digest('hex').slice(0, 32);
  }
  /** Long poll: answer when the digest differs from the caller's, or after the window. */
  async watch(instance: string, digest = '') {
    this.checkInstance(instance);
    const deadline = Date.now() + WATCH_WINDOW;
    let current = await this.digest();
    while (digest && current === digest && Date.now() < deadline && !this.closed) {
      await sleep(Math.min(WATCH_STEP, Math.max(0, deadline - Date.now())));
      if (this.closed) break;
      current = await this.digest();
    }
    const changed = current !== digest;
    if (changed && digest) this.invalidate();
    return { digest: current, changed, capturedAt: Date.now() };
  }
  async close(): Promise<void> {
    this.closed = true; this.cache = null; this.known.clear(); await this.runner?.close();
  }
}
