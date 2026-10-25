import { defineRpc } from '@getpaseo/plugin';
import { z } from 'zod';

export const idSchema = z.string().min(1).max(160).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/);
export const controlSchema = z.enum(['start', 'pause', 'resume', 'stop', 'restart']);
export const sectionSchema = z.enum(['Now', 'Next', 'Needs decision']);
export const recordSchema = z.record(z.string(), z.unknown());
export const questionSchema = z.object({
  id: idSchema, effort: z.string(), unblocks: z.number().int().nonnegative(),
  needs: z.string(), answer: z.string().default(''), kind: z.string().default(''),
});
export const laneSchema = z.object({ task: z.string(), phase: z.string(), detail: z.string().default(''),
  attempt: z.number().default(1), minutes: z.number().nullable().optional(),
  activity: z.string().default(''), activity_age: z.number().nullable().optional() });
export const runnerSchema = z.object({
  name: z.string(), repo: z.string(), state: z.string(), service: z.string().default(''),
  mode: z.string().default(''), running: z.number().default(0), waiting: z.number().default(0),
  stopped: z.number().default(0), decisions: z.number().default(0), push: z.boolean().default(false),
  enabled: z.boolean().default(false), blocker: z.string().default(''), stop_reason: z.string().default(''),
  gate: z.string().default(''), toolset: z.string().default(''), model: z.string().default(''),
  lanes: z.array(laneSchema).default([]), questions: z.array(questionSchema).default([]),
  held: z.array(z.array(z.string())).default([]), roots: z.array(recordSchema).default([]),
  waiting_groups: z.array(recordSchema).default([]), stopped_groups: z.array(recordSchema).default([]),
  main_check: recordSchema.default({}), job: recordSchema.nullable().default(null),
});
export const repoSchema = z.object({ id: idSchema, label: z.string(), path: z.string(), identity: z.string(),
  revision: z.string(), runner: runnerSchema.nullable(), error: z.string().nullable().default(null) });
export const policySchema = z.object({ planning: z.boolean(), decisions: z.boolean(), controls: z.array(controlSchema) });
export const fleetSchema = z.object({
  instance: z.string(), capturedAt: z.number(), release: z.string(), executable: z.string(),
  prepareApi: z.number(), permissions: policySchema, repos: z.array(repoSchema), warnings: z.array(z.string()),
});
// Autowork emits null for open tasks; an empty evidence map does not imply closure.
export const closureSchema = recordSchema.nullable().transform(value => value ?? {});
export const taskSchema = z.object({ id: idSchema, title: z.string(), section: z.string().nullable(),
  status: z.string(), goal: z.string().nullable(), rank: z.number().nullable(),
  position: z.number().nullable(), blocked_by: z.string().nullable(), closure: closureSchema });
export const taskDetailSchema = taskSchema.omit({ position: true, blocked_by: true }).extend({
  short: z.string().nullable(), depends_on: z.array(z.string()), verified_depends_on: z.array(z.string()),
  touches: z.array(z.string()), resources: z.array(z.string()), kind: z.string(), ownership: z.string(),
  live: z.string(), scope: z.string().nullable(), acceptance: z.array(z.string()), checks: z.array(z.string()),
  exclusions: z.array(z.string()), contract_hash: z.string(), record_revision: z.string(),
  path: z.string(), rev: z.string(), notes: z.string(), draft: z.boolean(), missing_fields: z.array(z.string()),
});
export const actionSchema = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('control'), repoId: idSchema, action: controlSchema }),
  z.strictObject({ kind: z.literal('decision'), repoId: idSchema, task: idSchema,
    revision: z.string().min(1).max(128), text: z.string().trim().min(1).max(16000), section: sectionSchema.optional() }),
  z.strictObject({ kind: z.literal('plan-start'), repoId: idSchema, objective: z.string().max(16000).default('') }),
  z.strictObject({ kind: z.literal('plan-send'), repoId: idSchema, sessionId: idSchema, message: z.string().trim().min(1).max(16000) }),
  z.strictObject({ kind: z.literal('plan-cancel'), repoId: idSchema, operationId: idSchema }),
  z.strictObject({ kind: z.literal('plan-steer'), repoId: idSchema, operationId: idSchema, message: z.string().trim().min(1).max(16000) }),
  z.strictObject({ kind: z.literal('plan-apply'), repoId: idSchema, sessionId: idSchema, revision: z.string().min(1).max(128) }),
]);
export const prepareSchema = z.strictObject({ instance: z.string(), action: actionSchema });
export const ticketSchema = z.object({ ticket: z.string(), expiresAt: z.number(), summary: z.string(), pushAllowed: z.boolean() });
export const operationSchema = z.object({ id: z.string(), repoId: z.string(), kind: z.string(),
  status: z.enum(['running', 'succeeded', 'failed', 'uncertain', 'cancelled']),
  message: z.string(), startedAt: z.number(), completedAt: z.number().nullable(),
  sessionId: z.string().nullable(), progress: z.string(), result: z.unknown().optional(),
});
export const fleetRpc = defineRpc({ name: 'autowork.fleet', input: z.strictObject({}), output: fleetSchema });
export const tasksRpc = defineRpc({ name: 'autowork.tasks', input: z.strictObject({ instance: z.string(), repoId: idSchema }),
  output: z.object({ revision: z.string(), tasks: z.array(taskSchema) }) });
export const taskRpc = defineRpc({ name: 'autowork.task', input: z.strictObject({ instance: z.string(), repoId: idSchema, task: idSchema, working: z.boolean().default(false) }), output: taskDetailSchema });
export const logsRpc = defineRpc({ name: 'autowork.logs', input: z.strictObject({ instance: z.string(), repoId: idSchema }), output: z.object({ text: z.string(), capturedAt: z.number() }) });
export const prepareRpc = defineRpc({ name: 'autowork.prepare', input: prepareSchema, output: ticketSchema });
export const commitRpc = defineRpc({ name: 'autowork.commit', input: z.strictObject({ instance: z.string(), ticket: z.string() }), output: operationSchema });
export const operationRpc = defineRpc({ name: 'autowork.operation', input: z.strictObject({ instance: z.string(), id: idSchema }), output: operationSchema });
export const planningRpc = defineRpc({ name: 'autowork.planning', input: z.strictObject({ instance: z.string(), repoId: idSchema,
  sessionId: idSchema, view: z.enum(['preview', 'history', 'roadmap']) }), output: z.object({ value: z.unknown() }) });

export type Fleet = z.infer<typeof fleetSchema>;
export type Repo = z.infer<typeof repoSchema>;
export type Runner = z.infer<typeof runnerSchema>;
export type Task = z.infer<typeof taskSchema>;
export type TaskDetail = z.infer<typeof taskDetailSchema>;
export type Action = z.infer<typeof actionSchema>;
export type Operation = z.infer<typeof operationSchema>;
export type Ticket = z.infer<typeof ticketSchema>;
export type Policy = z.infer<typeof policySchema>;
export type Control = z.infer<typeof controlSchema>;
