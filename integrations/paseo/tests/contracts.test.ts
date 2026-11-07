import { describe, expect, it } from 'vitest';
import { actionSchema, fleetSchema, prepareSchema, runnerSchema, taskDetailSchema, taskSchema } from '../shared/contracts';

describe('wire contracts', () => {
  it('does not accept arbitrary commands, paths or authority fields', () => {
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'rm -rf /' }).success).toBe(false);
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'pause', executable: '/tmp/evil' }).success).toBe(false);
    expect(prepareSchema.safeParse({ instance: 'host-a', action: { kind: 'control', repoId: 'repo', action: 'pause' } }).success).toBe(true);
  });
  it('treats a null Autowork count as zero', () => {
    const runner = runnerSchema.parse({ name: 'example', repo: '/repo', state: 'not running',
      running: null, waiting: null, stopped: null, decisions: null });
    expect([runner.running, runner.waiting, runner.stopped, runner.decisions]).toEqual([0, 0, 0, 0]);
    expect(runner.display).toEqual({ state: '', needs: '', question_summary: '', blockers: [], questions: [], tasks: {} });
    expect(runnerSchema.parse({ name: 'example', repo: '/repo', state: 'running', running: 2 }).running).toBe(2);
  });
  it('preserves absence of closure evidence and defaults the display for canonical open tasks', () => {
    const task = taskSchema.parse({ id: 'T-1', title: 'Open', section: 'Now', status: 'open', goal: 'G', rank: 1000,
      position: 1, blocked_by: null, closure: null });
    expect(task.closure).toEqual({});
    expect(task.display).toEqual({ state: '', bucket: '', why: '', question: false, pending: false, blocker: '', closure: null });
  });
  it('requires explicit host generation and source/evidence identity', () => {
    expect(fleetSchema.safeParse({ repos: [] }).success).toBe(false);
    expect(taskDetailSchema.safeParse({ id: 'T-1', title: 'No provenance' }).success).toBe(false);
  });
});
