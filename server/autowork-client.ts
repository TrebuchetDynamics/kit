import { randomUUID, createHash } from 'node:crypto';
import { lstat } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';
import { fleetSchema, runnerSchema, taskSchema, taskDetailSchema, type Fleet, type Repo, type TaskDetail } from '../shared/contracts';
import { type Config, resolveExecutable } from './config';
import { assertIdentity, repositoryIdentity, type Identity } from './discovery';
import { ProcessRunner, redact } from './process';

const capabilitiesSchema = z.object({ tool: z.literal('autowork'), release: z.string().min(1), prepare_api: z.literal(4),
  commands: z.array(z.string()), tasks: z.array(z.string()), toolset: z.string().optional() });
function parseCapabilities(value: unknown): z.infer<typeof capabilitiesSchema> {
  const result = capabilitiesSchema.safeParse(value);
  if (!result.success) {
    const api = value !== null && typeof value === 'object' && 'prepare_api' in value
      && typeof value.prepare_api === 'number' ? String(value.prepare_api) : 'missing or invalid';
    throw new Error(`Incompatible Autowork: requires prepare API 4 and fleet/task/planning contracts; received API ${api}`);
  }
  return result.data;
}
export class AutoworkService {
  readonly instance = randomUUID();
  readonly config: Config;
  private runner: ProcessRunner | null = null;
  private executableIdentity = '';
  private initialized: Promise<void> | null = null;
  private capabilities: z.infer<typeof capabilitiesSchema> | null = null;
  private executable = '';
  private cache: Fleet | null = null;
  private collection: Promise<Fleet> | null = null;
  private known = new Map<string, Identity>();
  private closed = false;
  constructor(config: Config) { this.config = config; }
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
      this.runner = new ProcessRunner(this.executable);
      const cap = parseCapabilities(await this.runner.json(['capabilities']));
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
  async verifyRelease(): Promise<void> {
    const commands = await this.commands();
    const current = parseCapabilities(await commands.json(['capabilities']));
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
      const { runners } = z.object({ runners: z.array(runnerSchema).max(128) }).parse(await commands.json(['ls', '--json']));
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
      this.cache = fleetSchema.parse({ instance: this.instance, capturedAt: Date.now(), release: this.capabilities!.release,
        executable: this.executable, prepareApi: this.capabilities!.prepare_api,
        permissions: { planning: this.config.planning, decisions: this.config.decisions, controls: this.config.controls }, repos, warnings });
      return this.cache;
    } catch (error) { this.cache = null; this.known.clear(); throw error; }
  }
  async repo(instance: string, id: string): Promise<Identity> {
    this.checkInstance(instance);
    if (!this.known.has(id)) await this.fleet();
    const before = this.known.get(id); if (!before) throw new Error('Repository is not a known Autowork target on this host');
    return assertIdentity(before);
  }
  async tasks(instance: string, repoId: string) {
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    const tasks = z.array(taskSchema).max(10000).parse(await commands.json(['tasks', 'list', repo.root, '--rev', repo.revision]));
    return { revision: repo.revision, tasks };
  }
  async task(instance: string, repoId: string, task: string, working = false): Promise<TaskDetail> {
    if (working) throw new Error('Transactional working-tree reads are not exposed; inspect committed records instead');
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    return taskDetailSchema.parse(await commands.json(['tasks', 'show', task, repo.root, '--rev', repo.revision]));
  }
  async logs(instance: string, repoId: string) {
    const repo = await this.repo(instance, repoId); const commands = await this.commands();
    const { stdout } = await commands.run(['logs', repo.root, '--lines', '150']);
    return { text: redact(stdout).slice(-64000), capturedAt: Date.now() };
  }
  async close(): Promise<void> {
    this.closed = true; this.cache = null; this.known.clear(); await this.runner?.close();
  }
}
