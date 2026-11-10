import { describe, expect, it } from 'vitest';
import { actionSchema, fleetSchema, prepareSchema, runnerSchema, taskDetailSchema, taskSchema } from '../shared/contracts';

describe('wire contracts', () => {
  it('does not accept arbitrary commands, paths or authority fields', () => {
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'rm -rf /' }).success).toBe(false);
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'pause', executable: '/tmp/evil' }).success).toBe(false);
    expect(prepareSchema.safeParse({ instance: 'host-a', action: { kind: 'control', repoId: 'repo', action: 'pause' } }).success).toBe(true);
  });
  it('accepts simple task authoring without fabricating a goal or authority', () => {
    const input = { kind: 'task-add', repoId: 'repo', fields: { title: 'Small fix', scope: 'Bounded', acceptance: ['Works'], checks: ['true'] } };
    expect(actionSchema.parse(input)).toEqual(input);
    expect(actionSchema.safeParse({ ...input, fields: { ...input.fields, goal: '' } }).success).toBe(false);
    expect(actionSchema.safeParse({ ...input, fields: { ...input.fields, live: 'authorized' } }).success).toBe(false);
  });
  it('treats a null Autowork count as zero', () => {
    const runner = runnerSchema.parse({ name: 'example', repo: '/repo', state: 'not running',
      running: null, waiting: null, stopped: null, decisions: null });
    expect([runner.running, runner.waiting, runner.stopped, runner.decisions]).toEqual([0, 0, 0, 0]);
    expect(runner.display).toBeNull();
    expect(runnerSchema.parse({ name: 'example', repo: '/repo', state: 'running', running: 2 }).running).toBe(2);
  });
  it('preserves absent closure and display evidence for canonical open tasks', () => {
    const task = taskSchema.parse({ id: 'T-1', title: 'Open', section: 'Now', status: 'open', goal: 'G', rank: 1000,
      position: 1, blocked_by: null, closure: null });
    expect(task.closure).toEqual({});
    expect(task.display).toBeNull();
  });
  it('requires explicit host generation and source/evidence identity', () => {
    expect(fleetSchema.safeParse({ repos: [] }).success).toBe(false);
    expect(taskDetailSchema.safeParse({ id: 'T-1', title: 'No provenance' }).success).toBe(false);
  });
});
