import { afterEach, describe, expect, it } from 'vitest';
import { readFile, writeFile } from 'node:fs/promises';
import { AutoworkService } from '../server/autowork-client';
import { Operations, type PlanningApi } from '../server/operations';
import { fixture, cleanupFixtures } from './fixture';

afterEach(cleanupFixtures);
async function setup(granted = false, planner?: PlanningApi) {
  const f = await fixture();
  const service = new AutoworkService({ executable: f.exe, repositories: [], planning: granted, decisions: granted, controls: granted ? ['pause', 'start'] : [] });
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
    const service = new AutoworkService({ executable: f.exe, repositories: [], planning: false, decisions: false, controls: ['pause'] });
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
    expect(calls.find(x => x[0] === 'tasks' && x[1] === 'decide')).toEqual(['tasks', 'decide', '--expect', 'record-v1', '--', 'T-1', text, s.repo]);
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
