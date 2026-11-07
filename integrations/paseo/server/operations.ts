import { randomUUID } from 'node:crypto';
import { actionSchema, grantFor, type Action, type ActionInput, type Operation, type Repo, type Ticket } from '../shared/contracts';
import { AutoworkService } from './autowork-client';
import { CommandFailure, redact, type RunOptions } from './process';

export type PlanningStart = { mode?: string; task?: string; model?: string };
export interface PlanningApi {
  start(repo: string, objective: string, options?: PlanningStart): Promise<{ id: string; status: string; text?: string }>;
  send(repo: string, sid: string, message: string): Promise<{ id: string; status: string; text?: string }>;
  state(repo: string, sid: string): Promise<{ status: string; text: string; result?: Record<string, unknown> }>;
  view(repo: string, sid: string, view: 'preview' | 'history' | 'roadmap'): Promise<unknown>;
  apply(repo: string, sid: string, revision: string): Promise<unknown>;
  steer(repo: string, sid: string, message: string): Promise<unknown>;
  cancel(repo: string, sid: string): Promise<unknown>;
  close(): Promise<void>;
}
type Prepared = { action: Action; fingerprint: string; expiresAt: number; summary: string; pushAllowed: boolean };
type Dispatch = { args: string[]; options?: RunOptions; verb?: string; command: string; message: string };
function object(value: unknown): Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}; }
const LOCAL_EDIT = 'Leaves a local uncommitted task edit; grants no live or publication permission.';
const COMMITTED = 'Creates a local commit; no push.';

/** Every argv is server-authored: fixed words, `--flag=value` for prose and `--` before positionals. */
export function dispatchFor(action: Action, repo: Repo): Dispatch {
  const r = repo.path;
  const expect = (revision: string) => `--expect=${revision}`;
  const slow = (ms: number): RunOptions => ({ timeoutMs: ms });
  switch (action.kind) {
    case 'control': {
      if (action.action === 'update') return { command: 'update', args: ['update'], options: slow(600_000), message: 'Installed suite update exited successfully. Reload this plugin to qualify the new release.' };
      const flags = action.action === 'restart' ? [...(action.stopWorkers ? ['--stop-workers'] : []), ...(action.now ? ['--now'] : [])] : [];
      return { command: action.action, args: [action.action, ...flags, r], options: slow(action.action === 'restart' && action.stopWorkers ? 2_100_000 : 180_000),
        message: 'Autowork command exited successfully. Refresh to inspect observed service state.' };
    }
    case 'model': return { command: 'model', args: ['model', ...(action.fallback ? [`--fallback=${action.fallback}`] : []), r, action.model], options: slow(180_000),
      message: 'Service model recorded and the runner restarted through Autowork. Refresh to inspect the observed model.' };
    case 'clear-held': return { command: 'clear-held', args: ['clear-held', r, ...action.tasks], options: slow(120_000),
      message: 'Held commits returned to integration as technical recovery; no owner decision was recorded.' };
    case 'attention': return { command: 'attention', args: ['attention', ...(action.task ? [`--task=${action.task}`] : []), ...(action.note ? [`--note=${action.note}`] : []), String(action.minutes), r],
      message: 'Owner attention recorded in private runner state; nothing committed.' };
    case 'decision': return { command: 'tasks', verb: 'decide', args: ['tasks', 'decide', expect(action.revision), ...(action.section ? [`--section=${action.section}`] : []), '--', action.task, action.text, r],
      message: `Owner direction recorded locally. ${LOCAL_EDIT}` };
    case 'task-add': return { command: 'tasks', verb: 'add', args: ['tasks', 'add', '--json', '-', r], options: { stdin: JSON.stringify(action.fields) },
      message: `Task record added. ${LOCAL_EDIT}` };
    case 'task-field': return { command: 'tasks', verb: 'field', args: ['tasks', 'field', expect(action.revision), '--', action.task, action.label, action.value, r],
      message: `Field written. ${LOCAL_EDIT}` };
    case 'task-place': return { command: 'tasks', verb: 'place', args: ['tasks', 'place', expect(action.revision), ...(action.decision ? [`--decision=${action.decision}`] : []), '--', action.task, action.section, r],
      message: `Task moved to ${action.section}. ${LOCAL_EDIT}` };
    case 'task-move': return { command: 'tasks', verb: 'move', args: ['tasks', 'move', expect(action.revision), '--', action.task, action.direction, r],
      message: `Rank changed. ${LOCAL_EDIT}` };
    case 'task-hold': return { command: 'tasks', verb: 'hold', args: ['tasks', 'hold', expect(action.revision), `--by=${action.by}`, ...(action.until ? [`--until=${action.until}`] : []), '--', action.task, r],
      message: `Hold recorded. ${LOCAL_EDIT}` };
    case 'task-release': return { command: 'tasks', verb: 'release', args: ['tasks', 'release', expect(action.revision), '--', action.task, r],
      message: `Hold released. ${LOCAL_EDIT}` };
    case 'task-done': return { command: 'tasks', verb: 'done', args: ['tasks', 'done', expect(action.revision), `--by=${action.by}`, `--reason=${action.reason}`, ...(action.evidence ? [`--evidence=${action.evidence}`] : []), '--', action.task, r],
      message: `Manual closure recorded; acceptance is not verified by this close. ${LOCAL_EDIT}` };
    case 'task-supersede': return { command: 'tasks', verb: 'supersede', args: ['tasks', 'supersede', expect(action.revision), ...action.by.map(id => `--by=${id}`), `--reason=${action.reason}`, '--', action.task, r],
      message: `Task superseded. ${LOCAL_EDIT}` };
    case 'task-delete': return { command: 'tasks', verb: 'delete', args: ['tasks', 'delete', expect(action.revision), '--', action.task, r],
      message: `Task record deleted; worktrees, commits, evidence and goals stay. ${LOCAL_EDIT}` };
    case 'goal': return { command: 'tasks', verb: 'goal', args: ['tasks', 'goal', '--json', '-', ...(action.revision ? [expect(action.revision)] : []), '--', action.goal, r], options: { stdin: JSON.stringify(action.fields) },
      message: `Goal written. ${LOCAL_EDIT}` };
    case 'store-prepare': return { command: 'tasks', verb: 'prepare', args: ['tasks', 'prepare', ...(action.mode === 'stage' ? ['--no-commit'] : []), r], options: { timeoutMs: 300_000, acceptExit: [3] },
      message: action.mode === 'stage' ? 'Store conversion staged in the working tree; HEAD unmoved.' : `Store prepared. ${COMMITTED}` };
    case 'store-migrate': return { command: 'migrate', args: ['migrate', ...(action.commit ? [] : ['--no-commit']), r], options: slow(300_000),
      message: action.commit ? `Repository converted to the tasks/ store. ${COMMITTED}` : 'Store conversion staged; HEAD unmoved.' };
    case 'commit': return { command: 'tasks', verb: 'commit', args: ['tasks', 'commit', `--expect-pending=${action.pendingRevision}`, `--message=${action.message}`, r],
      message: `Task edits committed. ${COMMITTED}` };
    default: throw new Error('Planning actions use the owned planning controller, not argv');
  }
}
export function summarize(action: Action, repo: Repo): { description: string; captured: string } {
  const push = `Existing publication policy: ${repo.runner?.push ? 'push allowed' : 'push not granted'}.`;
  const label = repo.label;
  switch (action.kind) {
    case 'control': return {
      description: action.action === 'update' ? `Update the installed Autowork suite on this daemon host (every runner). ${push}`
        : `${action.action}${action.stopWorkers ? ' --stop-workers' : ''}${action.now ? ' --now' : ''} ${label} on this daemon host. ${action.action === 'start' ? 'May install/start a user service and make model calls. ' : action.action === 'remove' ? 'Stops and removes the service; state and worktrees stay. ' : ''}${push}`,
      captured: '' };
    case 'model': return { description: `Set the service model for ${label} and restart its runner. ${push}`, captured: `Model: ${action.model}${action.fallback ? `\nFallback: ${action.fallback}` : ''}` };
    case 'clear-held': return { description: `Return ${action.tasks.length ? action.tasks.join(', ') : 'every held commit'} in ${label} to integration as technical recovery. No owner decision is asked.`, captured: '' };
    case 'attention': return { description: `Record ${action.minutes} owner minute(s) for ${action.task ? action.task + ' in ' : ''}${label} in private runner state.`, captured: action.note ? `Note:\n${action.note}` : '' };
    case 'decision': return { description: `Record owner direction for ${action.task} in ${label}${action.section ? '; move to ' + action.section : ''}. ${LOCAL_EDIT}`, captured: `Owner answer for ${action.task}:\n${action.text}` };
    case 'task-add': return { description: `Add task "${action.fields.title}" under goal ${action.fields.goal} in ${label}. ${LOCAL_EDIT}`, captured: `Record:\n${JSON.stringify(action.fields, null, 2)}` };
    case 'task-field': return { description: `Set ${action.label} on ${action.task} in ${label}. ${LOCAL_EDIT}`, captured: `Value:\n${action.value}` };
    case 'task-place': return { description: `Move ${action.task} to ${action.section} in ${label}. ${LOCAL_EDIT}`, captured: action.decision ? `Owner decision:\n${action.decision}` : '' };
    case 'task-move': return { description: `Move ${action.task} ${action.direction} within its section in ${label}. ${LOCAL_EDIT}`, captured: '' };
    case 'task-hold': return { description: `Hold ${action.task} in ${label} by "${action.by}"${action.until ? ' until ' + action.until : ''}. ${LOCAL_EDIT}`, captured: '' };
    case 'task-release': return { description: `Release the hold on ${action.task} in ${label}. ${LOCAL_EDIT}`, captured: '' };
    case 'task-done': return { description: `Manually close ${action.task} in ${label} by "${action.by}". This does not verify acceptance. ${LOCAL_EDIT}`, captured: `Reason:\n${action.reason}${action.evidence ? `\nEvidence reference:\n${action.evidence}` : ''}` };
    case 'task-supersede': return { description: `Supersede ${action.task} in ${label} by ${action.by.join(', ')}. ${LOCAL_EDIT}`, captured: `Reason:\n${action.reason}` };
    case 'task-delete': return { description: `Delete the record ${action.task} from ${label}. Worktrees, commits, evidence and goals stay. ${LOCAL_EDIT}`, captured: '' };
    case 'goal': return { description: `Write goal ${action.goal} in ${label}. ${LOCAL_EDIT}`, captured: `Fields:\n${JSON.stringify(action.fields, null, 2)}` };
    case 'store-prepare': return { description: `Prepare the tasks/ store of ${label} (${action.mode === 'stage' ? 'stage only, HEAD unmoved' : 'may create one local commit'}). ${push}`, captured: '' };
    case 'store-migrate': return { description: `Convert ${label} to the tasks/ store${action.commit ? ' with one local commit' : ' without committing'}. ${push}`, captured: '' };
    case 'commit': return { description: `Commit the working tree's tasks/ edits in ${label} and nothing else. ${COMMITTED} ${push}`, captured: `Pending snapshot: ${action.pendingRevision}\nCommit message:\n${action.message}` };
    case 'plan-start': return { description: `Start a plugin-owned planning session for ${label} in ${action.mode} mode${action.task ? ' scoped to ' + action.task : ''}${action.model ? ' with model ' + action.model : ''}. Planning may make model calls; no automatic Apply or runner Start.`, captured: `Objective:\n${action.objective || '(empty: discover useful work)'}` };
    case 'plan-send': return { description: `Send a follow-up to the plugin-owned planning session for ${label}. Planning may make model calls; no automatic Apply.`, captured: `Follow-up for session ${action.sessionId}:\n${action.message}` };
    case 'plan-steer': return { description: `Steer the running planning turn for ${label}.`, captured: `Steering for operation ${action.operationId}:\n${action.message}` };
    case 'plan-cancel': return { description: `Cancel the running planning turn for ${label}.`, captured: `Cancel operation ${action.operationId}` };
    case 'plan-apply': return { description: `Apply reviewed revision ${action.revision} in ${label}. Creates a local commit; existing runners may pick up accepted tasks. No service start or push grant.`, captured: '' };
  }
}

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
    if (!this.service.policy.planning || !this.planningFactory) throw new Error('Planning is not allowed by this host operator');
    this.planner ??= this.planningFactory(); return this.planner;
  }
  private owns(repo: string, sid: string): void {
    if (this.sessions.get(sid) !== repo) throw new Error('Planning session is not owned by this plugin generation and repository');
  }
  private allowed(action: Action): void {
    const policy = this.service.policy;
    const grant = grantFor(action);
    const ok = grant === 'controls' ? action.kind === 'control' && policy.controls.includes(action.action)
      : grant === 'maintenance' ? (action.kind === 'model' || action.kind === 'clear-held' || action.kind === 'attention') && policy.maintenance.includes(action.kind)
        : policy[grant] === true;
    if (!ok) {
      const what = grant === 'controls' ? 'this runner operation' : grant === 'maintenance' ? 'runner maintenance' : grant === 'decisions' ? 'owner answers'
        : grant === 'tasks' ? 'task edits' : grant === 'commit' ? 'task-store commits' : 'planning';
      throw new Error(`Read-only: ${what} ${grant === 'controls' ? 'is' : 'are'} not allowed by the host operator`);
    }
  }
  private async binding(action: Action): Promise<{ fingerprint: string; repo: Repo }> {
    this.allowed(action);
    const fleet = await this.service.fleet(true);
    const repo = fleet.repos.find(r => r.id === action.repoId);
    if (!repo || repo.error) throw new Error('Repository is not a known available target; refresh');
    await this.service.repo(this.service.instance, repo.id);
    let revision = '';
    if ('task' in action && 'revision' in action) {
      if (action.kind === 'decision' && !repo.runner?.questions.some(q => q.id === action.task)) throw new Error('This task has no actionable canonical owner question');
      // Task edits bind to the working-tree record so several edits can precede one commit.
      const task = await this.service.task(this.service.instance, repo.id, action.task, this.service.policy.tasks);
      if (task.record_revision !== action.revision) throw new Error('Task record changed; refresh before editing it');
      if (action.kind === 'decision' && task.status !== 'open') throw new Error('Task record changed; refresh before answering');
      revision = task.record_revision;
    } else if (action.kind === 'commit') {
      const pending = object((await this.service.store(this.service.instance, repo.id, 'pending')).value);
      if (typeof pending.pending_revision !== 'string' || !/^[a-f0-9]{64}$/.test(pending.pending_revision)) {
        throw new Error('Installed Autowork lacks pending snapshot protection; update the executable before committing');
      }
      if (pending.pending_revision !== action.pendingRevision) throw new Error('pending task edits changed; review the diff again');
      if (!Array.isArray(pending.files) || !pending.files.length) throw new Error('There are no pending task edits to commit');
      revision = pending.pending_revision;
    } else if (action.kind === 'goal' && action.revision) {
      const { goals } = await this.service.goals(this.service.instance, repo.id, true);
      const goal = goals.find(item => item.id === action.goal);
      if (!goal || goal.record_revision !== action.revision) throw new Error('Goal record changed; refresh before editing it');
      revision = action.revision;
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
    } else if (!action.kind.startsWith('plan-')) {
      const dispatch = dispatchFor(action, repo);
      await this.service.require(dispatch.command, dispatch.verb);
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
  async prepare(instance: string, input: ActionInput): Promise<Ticket> {
    this.service.checkInstance(instance); if (this.closed) throw new Error('Plugin is closing');
    const action = actionSchema.parse(input); this.prune();
    const { fingerprint, repo } = await this.binding(action);
    const ticket = randomUUID(); const expiresAt = Date.now() + 60_000;
    const { description, captured } = summarize(action, repo);
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
    if (serial) this.busy.set(action.repoId, op.id);
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
      if (!action.kind.startsWith('plan-')) {
        const dispatch = dispatchFor(action, repo);
        const commands = await this.service.require(dispatch.command, dispatch.verb);
        const result = await commands.run(dispatch.args, dispatch.options);
        this.finish(op, 'succeeded', dispatch.message, { output: redact(result.stdout).slice(-16000) });
        return;
      }
      const planner = await this.planningApi();
      if (action.kind === 'plan-start' || action.kind === 'plan-send') {
        const result = action.kind === 'plan-start'
          ? await planner.start(repo.path, action.objective, { mode: action.mode, task: action.task, model: action.model })
          : await planner.send(repo.path, action.sessionId, action.message);
        this.sessions.set(result.id, repo.id); op.sessionId = result.id; op.progress = result.text ?? '';
        op.message = 'Plugin-owned planning turn active; proposal remains unaccepted';
        if (result.status !== 'running') await this.read(this.service.instance, op.id);
      } else if (action.kind === 'plan-apply') {
        this.finish(op, 'succeeded', 'Reviewed proposal applied through Autowork; no push or service start.', await planner.apply(repo.path, action.sessionId, action.revision));
      } else if (action.kind === 'plan-cancel' || action.kind === 'plan-steer') {
        const owned = this.operations.get(action.operationId)!;
        const result = action.kind === 'plan-cancel' ? await planner.cancel(repo.path, owned.sessionId!) : await planner.steer(repo.path, owned.sessionId!, action.message);
        this.finish(op, 'succeeded', action.kind === 'plan-cancel' ? 'Cancellation requested; inspect the original turn for settlement.' : 'Steering accepted by the owned planning controller; not a completed turn.', result);
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
