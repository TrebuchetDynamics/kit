import { afterEach, describe, expect, it } from 'vitest';
import { readFile, writeFile } from 'node:fs/promises';
import { AutoworkService } from '../server/autowork-client';
import { Operations, type PlanningApi } from '../server/operations';
import { fixture, cleanupFixtures, policy } from './fixture';
import { dispatchFor } from '../server/operations';
import type { Repo } from '../shared/contracts';

afterEach(cleanupFixtures);
async function setup(granted = false, planner?: PlanningApi) {
  const f = await fixture();
  const service = new AutoworkService(policy({ executable: f.exe, planning: granted, decisions: granted, tasks: granted, commit: granted, controls: granted ? ['pause', 'start'] : [], maintenance: granted ? ['model', 'clear-held', 'attention'] : [] }));
  const ops = new Operations(service, planner ? async () => planner : undefined);
  const fleet = await service.fleet();
  return { ...f, service, ops, fleet, repoId: fleet.repos[0]!.id };
}
async function finished(ops: Operations, instance: string, id: string) {
  for (let i = 0; i < 50; i++) {
    const value = await ops.read(instance, id); if (value.status !== 'running') return value;
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  throw new Error('Operation did not settle');
}

describe('confirmed operations', () => {
  it('read-only policy rejects every mutation before issuing a ticket', async () => {
    const s = await setup();
    await expect(s.ops.prepare(s.fleet.instance, { kind: 'control', repoId: s.repoId, action: 'pause' })).rejects.toThrow(/read.only|not allowed/);
    await expect(s.ops.prepare(s.fleet.instance, { kind: 'plan-start', repoId: s.repoId, objective: '' })).rejects.toThrow(/read.only|not allowed/);
    await s.ops.close(); await s.service.close();
  });
  it('single-use confirmations return the existing result without dispatching twice', async () => {
    const s = await setup(true);
    const ticket = await s.ops.prepare(s.fleet.instance, { kind: 'control', repoId: s.repoId, action: 'pause' });
    const first = await s.ops.commit(s.fleet.instance, ticket.ticket);
    const again = await s.ops.commit(s.fleet.instance, ticket.ticket);
    expect(again.id).toBe(first.id);
    expect((await finished(s.ops, s.fleet.instance, first.id)).status).toBe('succeeded');
    const calls = (await readFile(s.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.filter(x => x[0] === 'pause')).toEqual([['pause', s.repo]]);
    await expect(s.ops.commit('other-host-generation', ticket.ticket)).rejects.toThrow(/generation/);
    await s.ops.close(); await s.service.close();
  });
  it('serializes two independently confirmed operations before any asynchronous dispatch', async () => {
    const s = await setup(true);
    const a = await s.ops.prepare(s.fleet.instance, { kind: 'control', repoId: s.repoId, action: 'pause' });
    const b = await s.ops.prepare(s.fleet.instance, { kind: 'control', repoId: s.repoId, action: 'pause' });
    const outcomes = await Promise.allSettled([s.ops.commit(s.fleet.instance, a.ticket), s.ops.commit(s.fleet.instance, b.ticket)]);
    const accepted = outcomes.filter((r): r is PromiseFulfilledResult<Awaited<ReturnType<Operations['commit']>>> => r.status === 'fulfilled');
    expect(accepted).toHaveLength(1);
    await finished(s.ops, s.fleet.instance, accepted[0]!.value.id);
    const calls = (await readFile(s.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.filter(x => x[0] === 'pause')).toHaveLength(1);
    await s.ops.close(); await s.service.close();
  });
  it('changed canonical state invalidates a prepared action', async () => {
    const s = await setup(true);
    const t = await s.ops.prepare(s.fleet.instance, { kind: 'control', repoId: s.repoId, action: 'start' });
    const script = (await readFile(s.exe, 'utf8')).replace('"push":false', '"push":true');
    await writeFile(s.exe, script);
    await expect(s.ops.commit(s.fleet.instance, t.ticket)).rejects.toThrow(/changed|refresh/);
    await s.ops.close(); await s.service.close();
  });
  it('rejects a release swap even when the launcher executable is unchanged', async () => {
    const f = await fixture();
    const versionFile = f.root + '/release'; await writeFile(versionFile, 'release-one');
    const script = (await readFile(f.exe, 'utf8')).replace("release:'fixture-release'", `release:fs.readFileSync(${JSON.stringify(versionFile)},'utf8')`);
    await writeFile(f.exe, script);
    const service = new AutoworkService(policy({ executable: f.exe, controls: ['pause'] }));
    const ops = new Operations(service); const fleet = await service.fleet();
    const ticket = await ops.prepare(fleet.instance, { kind: 'control', repoId: fleet.repos[0]!.id, action: 'pause' });
    await writeFile(versionFile, 'release-two');
    await expect(ops.commit(fleet.instance, ticket.ticket)).rejects.toThrow(/release.*changed|changed.*release/);
    await ops.close(); await service.close();
  });
  it('requires a canonical owner question and current task revision for an answer', async () => {
    const s = await setup(true);
    await expect(s.ops.prepare(s.fleet.instance, { kind: 'decision', repoId: s.repoId,
      task: 'T-TECHNICAL', revision: 'old', text: 'run anything' })).rejects.toThrow(/owner question/);
    await s.ops.close(); await s.service.close();
  });
  it('answers an actionable owner question through revision-bound literal task decide only', async () => {
    const s = await setup(true); const text = '--literal $(touch nope); authorize nothing';
    const ticket = await s.ops.prepare(s.fleet.instance, { kind: 'decision', repoId: s.repoId, task: 'T-1', revision: 'record-v1', text });
    expect(ticket.summary).toContain(text);
    const op = await s.ops.commit(s.fleet.instance, ticket.ticket);
    expect((await finished(s.ops, s.fleet.instance, op.id)).status).toBe('succeeded');
    const calls = (await readFile(s.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.find(x => x[0] === 'tasks' && x[1] === 'decide')).toEqual(['tasks', 'decide', '--expect=record-v1', '--', 'T-1', text, s.repo]);
    expect(calls.some(x => x.includes('live') || x.includes('done'))).toBe(false);
    await s.ops.close(); await s.service.close();
  });
  it('retains planning ownership after an uncertain state read until cancellation actually settles', async () => {
    let starts = 0, cancels = 0, unavailable = true;
    const planner: PlanningApi = {
      start: async () => ({ id: 'owned-' + (++starts), status: 'running' }),
      send: async (_repo, id) => ({ id, status: 'running' }),
      state: async () => { if (unavailable) throw new Error('Planning request concurrency limit reached'); return { status: 'cancelled', text: '' }; },
      view: async () => ({}), apply: async () => ({}), steer: async () => ({}),
      cancel: async () => { cancels++; return { status: 'cancellation-requested' }; }, close: async () => {},
    };
    const s = await setup(true, planner);
    const ticket = await s.ops.prepare(s.fleet.instance, { kind: 'plan-start', repoId: s.repoId, objective: '' });
    const first = await s.ops.commit(s.fleet.instance, ticket.ticket);
    const uncertain = await finished(s.ops, s.fleet.instance, first.id);
    expect(uncertain.status).toBe('uncertain');
    const duplicate = await s.ops.prepare(s.fleet.instance, { kind: 'plan-start', repoId: s.repoId, objective: '' });
    await expect(s.ops.commit(s.fleet.instance, duplicate.ticket)).rejects.toThrow(/active|uncertain|replay/);
    expect(starts).toBe(1);
    const cancel = await s.ops.prepare(s.fleet.instance, { kind: 'plan-cancel', repoId: s.repoId, operationId: first.id });
    const cancelling = await s.ops.commit(s.fleet.instance, cancel.ticket);
    await finished(s.ops, s.fleet.instance, cancelling.id); expect(cancels).toBe(1);
    unavailable = false;
    expect((await s.ops.read(s.fleet.instance, first.id)).status).toBe('cancelled');
    const next = await s.ops.prepare(s.fleet.instance, { kind: 'plan-start', repoId: s.repoId, objective: '' });
    const restarted = await s.ops.commit(s.fleet.instance, next.ticket);
    await finished(s.ops, s.fleet.instance, restarted.id); expect(starts).toBe(2);
    await s.ops.close(); await s.service.close();
  });
  it('planning stays staged, rejects foreign sessions, and applies only the exact reviewed revision', async () => {
    const applied: string[] = []; let starts = 0;
    const planner: PlanningApi = {
      start: async () => { starts++; return { id: 'owned-session', status: 'running' }; },
      send: async () => ({ id: 'owned-session', status: 'running' }),
      state: async () => ({ status: 'ready', text: 'Proposed', result: {} }),
      view: async () => ({ revision: 'preview-v1', valid: true, files: ['docs/plan.md'], diff: '+ proposal' }),
      apply: async (_repo, _sid, rev) => { applied.push(rev); return { commit: 'abc' }; },
      steer: async () => ({}), cancel: async () => ({}), close: async () => {},
    };
    const s = await setup(true, planner);
    await expect(s.ops.planning(s.fleet.instance, s.repoId, 'somebody-elses-session', 'history')).rejects.toThrow(/owned/);
    const start = await s.ops.prepare(s.fleet.instance, { kind: 'plan-start', repoId: s.repoId, objective: '' });
    expect(starts).toBe(0);
    const op = await s.ops.commit(s.fleet.instance, start.ticket); await finished(s.ops, s.fleet.instance, op.id);
    expect(starts).toBe(1); expect(applied).toEqual([]);
    await expect(s.ops.prepare(s.fleet.instance, { kind: 'plan-apply', repoId: s.repoId, sessionId: 'owned-session', revision: 'stale' })).rejects.toThrow(/reviewed revision/);
    const apply = await s.ops.prepare(s.fleet.instance, { kind: 'plan-apply', repoId: s.repoId, sessionId: 'owned-session', revision: 'preview-v1' });
    expect(applied).toEqual([]);
    const applying = await s.ops.commit(s.fleet.instance, apply.ticket); await finished(s.ops, s.fleet.instance, applying.id);
    expect(applied).toEqual(['preview-v1']);
    const calls = (await readFile(s.log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));
    expect(calls.some(x => x[0] === 'start')).toBe(false);
    await s.ops.close(); await s.service.close();
  });
});

const repo: Repo = { id: 'r-1', label: 'example', path: '/srv/example', identity: 'i', revision: 'rev', runner: null, error: null };
const calls = async (log: string) => (await readFile(log, 'utf8')).trim().split('\n').map(x => JSON.parse(x));

describe('server-authored argv', () => {
  it('uses --flag=value for prose, -- before positionals and stdin JSON for records', () => {
    expect(dispatchFor({ kind: 'task-done', repoId: 'r-1', task: 'T-1', revision: 'v1', by: '--owner', reason: '-rf $(touch nope)', evidence: '' }, repo).args)
      .toEqual(['tasks', 'done', '--expect=v1', '--by=--owner', '--reason=-rf $(touch nope)', '--', 'T-1', '/srv/example']);
    expect(dispatchFor({ kind: 'task-supersede', repoId: 'r-1', task: 'T-1', revision: 'v1', by: ['T-2', 'T-3'], reason: 'merged' }, repo).args)
      .toEqual(['tasks', 'supersede', '--expect=v1', '--by=T-2', '--by=T-3', '--reason=merged', '--', 'T-1', '/srv/example']);
    expect(dispatchFor({ kind: 'task-hold', repoId: 'r-1', task: 'T-1', revision: 'v1', by: 'an interactive session', until: '2026-12-31' }, repo).args)
      .toEqual(['tasks', 'hold', '--expect=v1', '--by=an interactive session', '--until=2026-12-31', '--', 'T-1', '/srv/example']);
    expect(dispatchFor({ kind: 'task-field', repoId: 'r-1', task: 'T-1', revision: 'v1', label: 'rank', value: '-5' }, repo).args)
      .toEqual(['tasks', 'field', '--expect=v1', '--', 'T-1', 'rank', '-5', '/srv/example']);
    expect(dispatchFor({ kind: 'task-place', repoId: 'r-1', task: 'T-1', revision: 'v1', section: 'Needs decision', decision: 'wait' }, repo).args)
      .toEqual(['tasks', 'place', '--expect=v1', '--decision=wait', '--', 'T-1', 'Needs decision', '/srv/example']);
    const add = dispatchFor({ kind: 'task-add', repoId: 'r-1', fields: { goal: 'G', title: 'Title', short: 'Short', acceptance: ['a'] } }, repo);
    expect(add.args).toEqual(['tasks', 'add', '--json', '-', '/srv/example']);
    expect(JSON.parse(add.options!.stdin!)).toEqual({ goal: 'G', title: 'Title', short: 'Short', acceptance: ['a'] });
    const goal = dispatchFor({ kind: 'goal', repoId: 'r-1', goal: 'G', revision: 'g1', fields: { priority: 2, focus: true } }, repo);
    expect(goal.args).toEqual(['tasks', 'goal', '--json', '-', '--expect=g1', '--', 'G', '/srv/example']);
    expect(JSON.parse(goal.options!.stdin!)).toEqual({ priority: 2, focus: true });
    expect(dispatchFor({ kind: 'control', repoId: 'r-1', action: 'restart', stopWorkers: true, now: true }, repo).args).toEqual(['restart', '--stop-workers', '--now', '/srv/example']);
    expect(dispatchFor({ kind: 'control', repoId: 'r-1', action: 'update' }, repo).args).toEqual(['update']);
    expect(dispatchFor({ kind: 'model', repoId: 'r-1', model: 'p/m', fallback: 'p/f' }, repo).args).toEqual(['model', '--fallback=p/f', '/srv/example', 'p/m']);
    expect(dispatchFor({ kind: 'clear-held', repoId: 'r-1', tasks: ['T-1'] }, repo).args).toEqual(['clear-held', '/srv/example', 'T-1']);
    expect(dispatchFor({ kind: 'attention', repoId: 'r-1', minutes: 12.5, task: 'T-1', note: '-n' }, repo).args).toEqual(['attention', '--task=T-1', '--note=-n', '12.5', '/srv/example']);
    expect(dispatchFor({ kind: 'commit', repoId: 'r-1', message: 'answer T-1' }, repo).args).toEqual(['tasks', 'commit', '--message=answer T-1', '/srv/example']);
    expect(dispatchFor({ kind: 'store-prepare', repoId: 'r-1', mode: 'stage' }, repo).args).toEqual(['tasks', 'prepare', '--no-commit', '/srv/example']);
    expect(dispatchFor({ kind: 'store-migrate', repoId: 'r-1', commit: false }, repo).args).toEqual(['migrate', '--no-commit', '/srv/example']);
    expect(() => dispatchFor({ kind: 'plan-start', repoId: 'r-1', objective: '', mode: 'plan' }, repo)).toThrow(/planning/);
  });
  it('refuses each grant kind separately and refuses verbs the installed release lacks', async () => {
    const f = await fixture();
    const service = new AutoworkService(policy({ executable: f.exe, decisions: true }));
    const ops = new Operations(service); const fleet = await service.fleet(); const repoId = fleet.repos[0]!.id;
    await expect(ops.prepare(fleet.instance, { kind: 'task-place', repoId, task: 'T-1', revision: 'record-v1', section: 'Now' })).rejects.toThrow(/task edits/);
    await expect(ops.prepare(fleet.instance, { kind: 'commit', repoId, message: 'm' })).rejects.toThrow(/commits/);
    await expect(ops.prepare(fleet.instance, { kind: 'model', repoId, model: 'p/m' })).rejects.toThrow(/maintenance/);
    await expect(ops.prepare(fleet.instance, { kind: 'control', repoId, action: 'remove' })).rejects.toThrow(/runner operation/);
    await ops.close(); await service.close();
    const granted = new AutoworkService(policy({ executable: f.exe, all: true }));
    const all = new Operations(granted); const snap = await granted.fleet();
    await expect(all.prepare(snap.instance, { kind: 'task-place', repoId, task: 'T-1', revision: 'stale', section: 'Now' })).rejects.toThrow(/changed|refresh/);
    const ticket = await all.prepare(snap.instance, { kind: 'task-done', repoId, task: 'T-1', revision: 'record-v1', by: 'owner', reason: 'obsolete' });
    expect(ticket.summary).toContain('does not verify acceptance');
    const op = await all.commit(snap.instance, ticket.ticket);
    expect((await finished(all, snap.instance, op.id)).status).toBe('succeeded');
    const recorded = await calls(f.log);
    expect(recorded.find(x => x[0] === 'tasks' && x[1] === 'done')).toEqual(['tasks', 'done', '--expect=record-v1', '--by=owner', '--reason=obsolete', '--', 'T-1', f.repo]);
    expect(recorded.some(x => x[0] === 'tasks' && x[1] === 'show' && x.includes('--worktree'))).toBe(true);
    const add = await all.prepare(snap.instance, { kind: 'task-add', repoId, fields: { goal: 'G', title: 'New', short: 'New' } });
    await finished(all, snap.instance, (await all.commit(snap.instance, add.ticket)).id);
    const stdin = (await calls(f.log)).find(x => x[0] === 'tasks' && x[1] === 'add')!;
    expect(JSON.parse(stdin[stdin.length - 1].stdin)).toEqual({ goal: 'G', title: 'New', short: 'New' });
    await writeFile(f.exe, (await readFile(f.exe, 'utf8')).replace("'commit',", ''));
    await expect(all.prepare(snap.instance, { kind: 'commit', repoId, message: 'm' })).rejects.toThrow(/executable changed|lacks/);
    await all.close(); await granted.close();
  });
});
