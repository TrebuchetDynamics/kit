import { describe, expect, it } from 'vitest';
import { actionSchema, fleetSchema, prepareSchema, taskDetailSchema } from '../shared/contracts';

describe('wire contracts', () => {
  it('does not accept arbitrary commands, paths or authority fields', () => {
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'rm -rf /' }).success).toBe(false);
    expect(actionSchema.safeParse({ kind: 'control', repoId: 'repo', action: 'pause', executable: '/tmp/evil' }).success).toBe(false);
    expect(prepareSchema.safeParse({ instance: 'host-a', action: { kind: 'control', repoId: 'repo', action: 'pause' } }).success).toBe(true);
  });
  it('requires explicit host generation and source/evidence identity', () => {
    expect(fleetSchema.safeParse({ repos: [] }).success).toBe(false);
    expect(taskDetailSchema.safeParse({ id: 'T-1', title: 'No provenance' }).success).toBe(false);
  });
});
