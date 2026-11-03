import { randomUUID } from 'node:crypto';
import { actionSchema, type Action, type Operation, type Repo, type Ticket } from '../shared/contracts';
import { AutoworkService } from './autowork-client';
import { CommandFailure, redact } from './process';

export interface PlanningApi {
  start(repo: string, objective: string): Promise<{ id: string; status: string; text?: string }>;
  send(repo: string, sid: string, message: string): Promise<{ id: string; status: string; text?: string }>;
  state(repo: string, sid: string): Promise<{ status: string; text: string; result?: Record<string, unknown> }>;
  view(repo: string, sid: string, view: 'preview' | 'history' | 'roadmap'): Promise<unknown>;
  apply(repo: string, sid: string, revision: string): Promise<unknown>;
  steer(repo: string, sid: string, message: string): Promise<unknown>;
  cancel(repo: string, sid: string): Promise<unknown>;
  close(): Promise<void>;
}
type Prepared = { action: Action; fingerprint: string; expiresAt: number; summary: string; pushAllowed: boolean };
function object(value: unknown): Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}; }

/** Confirmation and lifetime bookkeeping only; Autowork still validates every actual mutation. */
export class Operations {
  private tickets = new Map<string, Prepared>();
  private operations = new Map<string, Operation>();
  private consumed = new Map<string, string>();
  private busy = new Map<string, string>();
  private sessions = new Map<string, string>();
  private planner: Promise<PlanningApi> | null = null;
  private closed = false;
  constructor(readonly service: AutoworkService, private planningFactory?: () => Promise<PlanningApi>) {}
  private async planningApi(): Promise<PlanningApi> {
    if (!this.service.config.planning || !this.planningFactory) throw new Error('Planning is not allowed by this host operator');
    this.planner ??= this.planningFactory(); return this.planner;
  }
  private owns(repo: string, sid: string): void {
    if (this.sessions.get(sid) !== repo) throw new Error('Planning session is not owned by this plugin generation and repository');
  }
  private allowed(action: Action): void {
    const p = this.service.config;
    if (action.kind === 'control') {
      if (!p.controls.includes(action.action)) throw new Error('Read-only: this runner operation is not allowed by the host operator');
    } else if (action.kind === 'decision') {
      if (!p.decisions) throw new Error('Read-only: owner answers are not allowed by the host operator');
    } else if (!p.planning) throw new Error('Read-only: planning is not allowed by the host operator');
  }
  private async binding(action: Action): Promise<{ fingerprint: string; repo: Repo }> {
    this.allowed(action);
    const fleet = await this.service.fleet(true);
    const repo = fleet.repos.find(r => r.id === action.repoId);
    if (!repo || repo.error) throw new Error('Repository is not a known available target; refresh');
    await this.service.repo(this.service.instance, repo.id);
    let revision = '';
    if (action.kind === 'decision') {
      if (!repo.runner?.questions.some(q => q.id === action.task)) throw new Error('This task has no actionable canonical owner question');
      const task = await this.service.task(this.service.instance, repo.id, action.task);
      if (task.status !== 'open' || task.record_revision !== action.revision) throw new Error('Task record changed; refresh before answering');
      revision = task.record_revision;
    } else if (action.kind === 'plan-send' || action.kind === 'plan-apply') {
      this.owns(repo.id, action.sessionId);
      if (action.kind === 'plan-apply') {
        const preview = object(await (await this.planningApi()).view(repo.path, action.sessionId, 'preview'));
        if (preview.valid !== true || preview.revision !== action.revision || !Array.isArray(preview.files) || !preview.files.length) {
          throw new Error('Apply needs the exact valid reviewed revision; review the proposal again');
        }
        revision = action.revision;
      }
    } else if (action.kind === 'plan-cancel' || action.kind === 'plan-steer') {
      const owned = this.operations.get(action.operationId);
      if (!owned || owned.repoId !== repo.id || !owned.sessionId || !['running', 'uncertain'].includes(owned.status) || this.busy.get(repo.id) !== owned.id) throw new Error('No active planning turn owned by this plugin');
      this.owns(repo.id, owned.sessionId);
    }
    const fingerprint = JSON.stringify({ identity: repo.identity, revision: repo.revision, record: revision,
      release: fleet.release, service: repo.runner?.service ?? null, state: repo.runner?.state ?? null,
      push: repo.runner?.push ?? false, enabled: repo.runner?.enabled ?? false });
    return { fingerprint, repo };
  }
  private prune(): void {
    const now = Date.now(); for (const [key, ticket] of this.tickets) if (ticket.expiresAt < now) this.tickets.delete(key);
    if (this.operations.size >= 256) {
      for (const [id, op] of this.operations) {
        if (op.status !== 'running' && this.busy.get(op.repoId) !== id) { this.operations.delete(id); this.consumed.delete(id); }
        if (this.operations.size < 192) break;
      }
    }
    if (this.tickets.size >= 256 || this.operations.size >= 256) throw new Error('Operation reservation limit reached; wait for existing operations');
  }
  async prepare(instance: string, input: Action): Promise<Ticket> {
    this.service.checkInstance(instance); if (this.closed) throw new Error('Plugin is closing');
    const action = actionSchema.parse(input); this.prune();
    const { fingerprint, repo } = await this.binding(action);
    const ticket = randomUUID(); const expiresAt = Date.now() + 60_000;
    const description = action.kind === 'control'
      ? `${action.action} ${repo.label} on this daemon host. ${action.action === 'start' ? 'May install/start a user service and make model calls. ' : ''}Existing publication policy: ${repo.runner?.push ? 'push allowed' : 'push not granted'}.`
      : action.kind === 'decision'
        ? `Record owner direction for ${action.task} in ${repo.label}${action.section ? '; move to ' + action.section : ''}. Leaves a local uncommitted task edit; grants no live or publication permission.`
        : action.kind === 'plan-apply'
          ? `Apply reviewed revision ${action.revision} in ${repo.label}. Creates a local commit; existing runners may pick up accepted tasks. No service start or push grant.`
          : `${action.kind.replace('plan-', '')} the plugin-owned planning session for ${repo.label}. Planning may make model calls; no automatic Apply or runner Start.`;
    const captured = action.kind === 'decision' ? `Owner answer for ${action.task}:\n${action.text}`
      : action.kind === 'plan-start' ? `Objective:\n${action.objective || '(empty: discover useful work)'}`
      : action.kind === 'plan-send' ? `Follow-up for session ${action.sessionId}:\n${action.message}`
      : action.kind === 'plan-steer' ? `Steering for operation ${action.operationId}:\n${action.message}`
      : action.kind === 'plan-cancel' ? `Cancel operation ${action.operationId}` : '';
    const summary = description + (captured ? '\n\nFrozen prepared payload (later draft edits do not change this ticket):\n' + captured : '');
    this.tickets.set(ticket, { action, fingerprint, expiresAt, summary, pushAllowed: repo.runner?.push ?? false });
    return { ticket, expiresAt, summary, pushAllowed: repo.runner?.push ?? false };
  }
  async commit(instance: string, ticket: string): Promise<Operation> {
    this.service.checkInstance(instance); if (this.closed) throw new Error('Plugin is closing');
    const previous = this.consumed.get(ticket); if (previous) return this.read(instance, previous);
    const prepared = this.tickets.get(ticket);
    if (!prepared || prepared.expiresAt < Date.now()) throw new Error('Confirmation expired or belongs to another generation; refresh and confirm again');
    // Reserve before awaiting: two clients cannot dispatch the same ticket concurrently.
    this.tickets.delete(ticket);
    const { action } = prepared;
    const activeId = this.busy.get(action.repoId);
    if (activeId && this.operations.has(activeId)) await this.read(instance, activeId);
    const serial = !['plan-cancel', 'plan-steer'].includes(action.kind);
    if (this.busy.has(action.repoId) && serial) throw new Error('An owned operation is still active for this repository; do not replay');
    // Acquire before binding's first await, not after: different valid tickets still share one writer.
    if (serial) this.busy.set(action.repoId, ticket);
    let current: Awaited<ReturnType<Operations['binding']>>;
    try {
      current = await this.binding(action);
      if (current.fingerprint !== prepared.fingerprint) throw new Error('Repository, service or publication state changed; refresh and confirm again');
    } catch (error) {
      if (this.busy.get(action.repoId) === ticket) this.busy.delete(action.repoId);
      throw error;
    }
    const op: Operation = { id: ticket, repoId: action.repoId, kind: action.kind, status: 'running',
      message: 'Operation reserved; awaiting authoritative result', startedAt: Date.now(), completedAt: null, sessionId: null, progress: '' };
    this.operations.set(op.id, op); this.consumed.set(ticket, op.id);
    if (!['plan-cancel', 'plan-steer'].includes(action.kind)) this.busy.set(action.repoId, op.id);
    void this.execute(op, action, current.repo);
    return { ...op };
  }
  private finish(op: Operation, status: Operation['status'], message: string, result?: unknown): void {
    op.status = status; op.message = redact(message).slice(-16000); op.completedAt = Date.now(); op.result = result;
    // A failed observation is not proof that accepted work stopped. Keep its reservation.
    if (status !== 'uncertain' && this.busy.get(op.repoId) === op.id) this.busy.delete(op.repoId);
    this.service.invalidate();
  }
  private async execute(op: Operation, action: Action, repo: Repo): Promise<void> {
    try {
      if (action.kind === 'control') {
        const commands = await this.service.commands();
        const result = await commands.run([action.action, repo.path]);
        this.finish(op, 'succeeded', 'Autowork command exited successfully. Refresh to inspect observed service state.', { output: redact(result.stdout).slice(-16000) });
      } else if (action.kind === 'decision') {
        const args = ['tasks', 'decide', '--expect', action.revision, ...(action.section ? ['--section', action.section] : []), '--', action.task, action.text, repo.path];
        const result = await (await this.service.commands()).run(args);
        this.finish(op, 'succeeded', 'Owner direction recorded locally; not committed, not live authorization.', { output: redact(result.stdout).slice(-16000) });
      } else {
        const planner = await this.planningApi();
        if (action.kind === 'plan-start' || action.kind === 'plan-send') {
          const result = action.kind === 'plan-start' ? await planner.start(repo.path, action.objective) : await planner.send(repo.path, action.sessionId, action.message);
          this.sessions.set(result.id, repo.id); op.sessionId = result.id; op.progress = result.text ?? '';
          op.message = 'Plugin-owned planning turn active; proposal remains unaccepted';
          if (result.status !== 'running') await this.read(this.service.instance, op.id);
        } else if (action.kind === 'plan-apply') {
          this.finish(op, 'succeeded', 'Reviewed proposal applied through Autowork; no push or service start.', await planner.apply(repo.path, action.sessionId, action.revision));
        } else {
          const owned = this.operations.get(action.operationId)!;
          const result = action.kind === 'plan-cancel' ? await planner.cancel(repo.path, owned.sessionId!) : await planner.steer(repo.path, owned.sessionId!, action.message);
          this.finish(op, 'succeeded', action.kind === 'plan-cancel' ? 'Cancellation requested; inspect the original turn for settlement.' : 'Steering accepted by the owned planning controller; not a completed turn.', result);
        }
      }
    } catch (error) {
      // Once dispatch could have occurred, an error is not permission to submit again.
      this.finish(op, error instanceof CommandFailure && !error.started ? 'failed' : 'uncertain', error instanceof Error ? error.message : 'Autowork operation failed; outcome uncertain');
    }
  }
  async read(instance: string, id: string): Promise<Operation> {
    this.service.checkInstance(instance);
    const op = this.operations.get(id); if (!op) throw new Error('Unknown operation on this plugin host generation; no automatic replay');
    if (['running', 'uncertain'].includes(op.status) && op.sessionId && this.busy.get(op.repoId) === op.id) {
      const repo = await this.service.repo(instance, op.repoId);
      try {
        const state = await (await this.planningApi()).state(repo.root, op.sessionId);
        op.progress = redact(state.text).slice(-200000);
        if (state.status === 'running') {
          op.status = 'running'; op.completedAt = null;
          op.message = 'Owned planning turn remains active; reservation retained';
        }
        if (state.status !== 'running') this.finish(op, state.status === 'ready' ? 'succeeded' : state.status === 'cancelled' ? 'cancelled' : 'failed',
          state.status === 'ready' ? 'Planning turn settled; review before Apply.' : `Planning ${state.status}`, state.result);
      } catch (error) { this.finish(op, 'uncertain', error instanceof Error ? error.message : 'Planning state unavailable; no replay'); }
    }
    return { ...op };
  }
  async planning(instance: string, repoId: string, sessionId: string, view: 'preview' | 'history' | 'roadmap') {
    this.service.checkInstance(instance); this.owns(repoId, sessionId);
    const repo = await this.service.repo(instance, repoId);
    return { value: await (await this.planningApi()).view(repo.root, sessionId, view) };
  }
  async close(): Promise<void> {
    this.closed = true; this.tickets.clear();
    if (this.planner) await (await this.planner).close();
    for (const op of this.operations.values()) if (op.status === 'running') this.finish(op, 'uncertain', 'Plugin closing; retained upstream state requires explicit reconciliation, not replay');
  }
}
