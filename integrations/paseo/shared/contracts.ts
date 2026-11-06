import { defineRpc } from '@getpaseo/plugin';
import { z } from 'zod';

export const idSchema = z.string().min(1).max(160).regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/);
/** Fixed Autowork service commands: each one is an allowlisted argv, never shell. */
export const controlSchema = z.enum(['start', 'pause', 'resume', 'stop', 'restart', 'remove', 'update']);
/** Runner maintenance that changes private runner state or the service model. */
export const maintenanceSchema = z.enum(['model', 'clear-held', 'attention']);
export const sectionSchema = z.enum(['Now', 'Next', 'Needs decision']);
export const recordSchema = z.record(z.string(), z.unknown());
const text = (max = 16000) => z.string().trim().min(1).max(max);
const optionalText = (max = 16000) => z.string().trim().max(max).optional();
const modelSchema = z.string().trim().min(1).max(200).regex(/^[A-Za-z0-9][A-Za-z0-9._:/-]*$/);
const dateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const questionSchema = z.object({
  id: idSchema, effort: z.string(), unblocks: z.number().int().nonnegative(),
  needs: z.string(), answer: z.string().default(''), kind: z.string().default(''),
});
export const laneSchema = z.object({ task: z.string(), phase: z.string(), detail: z.string().default(''),
  attempt: z.number().default(1), minutes: z.number().nullable().optional(),
  activity: z.string().default(''), activity_age: z.number().nullable().optional() });
// Autowork emits null for an unavailable count, not only an absent one.
const countSchema = z.number().nullish().transform(value => value ?? 0);
const textOrEmpty = z.string().nullish().transform(value => value ?? '');
export const runnerSchema = z.object({
  name: z.string(), repo: z.string(), state: z.string(), service: z.string().default(''),
  mode: z.string().default(''), running: countSchema, waiting: countSchema,
  stopped: countSchema, decisions: countSchema, push: z.boolean().default(false),
  enabled: z.boolean().default(false), blocker: z.string().default(''), stop_reason: z.string().default(''),
  gate: z.string().default(''), toolset: z.string().default(''), model: z.string().default(''),
  fallback: textOrEmpty, state_dir: textOrEmpty, max_workers: z.number().nullish(), minutes: z.number().nullish(),
  observation: recordSchema.nullable().default(null), maintainer: recordSchema.nullable().default(null),
  prepare_state: z.unknown().optional(), restarting: z.unknown().optional(),
  lanes: z.array(laneSchema).default([]), questions: z.array(questionSchema).default([]),
  held: z.array(z.array(z.string())).default([]), roots: z.array(recordSchema).default([]),
  waiting_groups: z.array(recordSchema).default([]), stopped_groups: z.array(recordSchema).default([]),
  main_check: recordSchema.default({}), job: recordSchema.nullable().default(null),
});
export const repoSchema = z.object({ id: idSchema, label: z.string(), path: z.string(), identity: z.string(),
  revision: z.string(), runner: runnerSchema.nullable(), error: z.string().nullable().default(null) });
export const policySchema = z.object({ planning: z.boolean(), decisions: z.boolean(), tasks: z.boolean(), commit: z.boolean(),
  controls: z.array(controlSchema), maintenance: z.array(maintenanceSchema) });
export const fleetSchema = z.object({
  instance: z.string(), capturedAt: z.number(), release: z.string(), executable: z.string(), toolset: z.string().default(''),
  prepareApi: z.number(), permissions: policySchema,
  policy: z.object({ path: z.string().nullable(), source: z.enum(['environment', 'default', 'none']) }),
  capabilities: z.object({ commands: z.array(z.string()), tasks: z.array(z.string()) }),
  repos: z.array(repoSchema), warnings: z.array(z.string()),
});
// Autowork emits null for open tasks; an empty evidence map does not imply closure.
export const closureSchema = recordSchema.nullable().transform(value => value ?? {});
export const taskSchema = z.object({ id: idSchema, title: z.string(), section: z.string().nullable(),
  status: z.string(), goal: z.string().nullable(), rank: z.number().nullable(),
  position: z.number().nullable(), blocked_by: z.string().nullable(), closure: closureSchema,
  // Old releases omit semantic presentation. Neutral is safer than inferring meaning from words.
  presentation: z.object({ tone: z.enum(['success', 'warning', 'danger', 'neutral']),
    closure_tone: z.enum(['success', 'warning', 'danger', 'neutral']) }).optional() });
export const taskDetailSchema = taskSchema.omit({ position: true, blocked_by: true }).extend({
  short: z.string().nullable(), depends_on: z.array(z.string()), verified_depends_on: z.array(z.string()),
  touches: z.array(z.string()), resources: z.array(z.string()), kind: z.string(), ownership: z.string(),
  live: z.string(), scope: z.string().nullable(), acceptance: z.array(z.string()), checks: z.array(z.string()),
  exclusions: z.array(z.string()), contract_hash: z.string(), record_revision: z.string(),
  path: z.string(), rev: z.string(), notes: z.string(), draft: z.boolean(), missing_fields: z.array(z.string()),
});
export const goalSchema = z.object({ id: idSchema, title: z.string(), priority: z.number().nullable(), source: z.string().nullable(),
  status: z.string(), focus: z.boolean(), depends_on: z.array(z.string()), contract_hash: z.string().default(''),
  record_revision: z.string().default(''), path: z.string().default(''), notes: z.string().default(''), rev: z.string().default('') });
export const taskKindSchema = z.enum(['implementation', 'plan', 'inspection']);
export const ownershipSchema = z.enum(['worker', 'coordinator', 'owner']);
export const taskFieldsSchema = z.strictObject({
  goal: idSchema, title: text(300), short: text(80), section: sectionSchema.optional(), scope: optionalText(),
  kind: taskKindSchema.optional(), ownership: ownershipSchema.optional(), id: idSchema.optional(), sources: optionalText(500),
  acceptance: z.array(text(2000)).max(32).optional(), checks: z.array(text(2000)).max(32).optional(),
  touches: z.array(text(500)).max(64).optional(), depends_on: z.array(idSchema).max(64).optional(),
  verified_depends_on: z.array(idSchema).max(64).optional(), resources: z.array(text(200)).max(32).optional(),
  exclusions: z.array(text(2000)).max(32).optional(),
});
export const goalFieldsSchema = z.strictObject({
  title: text(300).optional(), source: text(300).optional(), priority: z.number().int().positive().max(1000000).optional(),
  status: z.enum(['unmet', 'partial', 'unverified', 'met']).optional(), focus: z.boolean().optional(),
  depends_on: z.array(idSchema).max(64).optional(), evidence: text(2000).optional(),
});
const taskTarget = { repoId: idSchema, task: idSchema, revision: z.string().min(1).max(128) };
export const actionSchema = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('control'), repoId: idSchema, action: controlSchema,
    stopWorkers: z.boolean().optional(), now: z.boolean().optional() }),
  z.strictObject({ kind: z.literal('model'), repoId: idSchema, model: modelSchema, fallback: modelSchema.optional() }),
  z.strictObject({ kind: z.literal('clear-held'), repoId: idSchema, tasks: z.array(idSchema).max(64).default([]) }),
  z.strictObject({ kind: z.literal('attention'), repoId: idSchema, minutes: z.number().positive().max(1440),
    task: idSchema.optional(), note: optionalText(2000) }),
  z.strictObject({ kind: z.literal('decision'), ...taskTarget, text: text(), section: sectionSchema.optional() }),
  z.strictObject({ kind: z.literal('task-add'), repoId: idSchema, fields: taskFieldsSchema }),
  z.strictObject({ kind: z.literal('task-field'), ...taskTarget, label: z.string().trim().min(1).max(64).regex(/^[A-Za-z][A-Za-z0-9 _-]*$/), value: z.string().max(16000) }),
  z.strictObject({ kind: z.literal('task-place'), ...taskTarget, section: sectionSchema, decision: optionalText(2000) }),
  z.strictObject({ kind: z.literal('task-move'), ...taskTarget, direction: z.enum(['up', 'down']) }),
  z.strictObject({ kind: z.literal('task-hold'), ...taskTarget, by: text(200), until: dateSchema.optional() }),
  z.strictObject({ kind: z.literal('task-release'), ...taskTarget }),
  z.strictObject({ kind: z.literal('task-done'), ...taskTarget, by: text(200), reason: text(2000), evidence: optionalText(2000) }),
  z.strictObject({ kind: z.literal('task-supersede'), ...taskTarget, by: z.array(idSchema).min(1).max(16), reason: text(2000) }),
  z.strictObject({ kind: z.literal('task-delete'), ...taskTarget }),
  z.strictObject({ kind: z.literal('goal'), repoId: idSchema, goal: idSchema, revision: z.string().min(1).max(128).optional(), fields: goalFieldsSchema }),
  z.strictObject({ kind: z.literal('store-prepare'), repoId: idSchema, mode: z.enum(['stage', 'commit']) }),
  z.strictObject({ kind: z.literal('store-migrate'), repoId: idSchema, commit: z.boolean().default(true) }),
  z.strictObject({ kind: z.literal('commit'), repoId: idSchema, message: text(500), pendingRevision: z.string().regex(/^[a-f0-9]{64}$/) }),
  z.strictObject({ kind: z.literal('plan-start'), repoId: idSchema, objective: z.string().max(16000).default(''),
    mode: z.enum(['plan', 'discuss', 'investigate']).default('plan'), task: idSchema.optional(), model: modelSchema.optional() }),
  z.strictObject({ kind: z.literal('plan-send'), repoId: idSchema, sessionId: idSchema, message: text() }),
  z.strictObject({ kind: z.literal('plan-cancel'), repoId: idSchema, operationId: idSchema }),
  z.strictObject({ kind: z.literal('plan-steer'), repoId: idSchema, operationId: idSchema, message: text() }),
  z.strictObject({ kind: z.literal('plan-apply'), repoId: idSchema, sessionId: idSchema, revision: z.string().min(1).max(128) }),
]);
export const prepareSchema = z.strictObject({ instance: z.string(), action: actionSchema });
export const ticketSchema = z.object({ ticket: z.string(), expiresAt: z.number(), summary: z.string(), pushAllowed: z.boolean() });
export const operationSchema = z.object({ id: z.string(), repoId: z.string(), kind: z.string(),
  status: z.enum(['running', 'succeeded', 'failed', 'uncertain', 'cancelled']),
  message: z.string(), startedAt: z.number(), completedAt: z.number().nullable(),
  sessionId: z.string().nullable(), progress: z.string(), result: z.unknown().optional(),
});
export const storeViewSchema = z.enum(['validate', 'prepare', 'pending', 'why']);
const target = { instance: z.string(), repoId: idSchema };
export const fleetRpc = defineRpc({ name: 'autowork.fleet', input: z.strictObject({}), output: fleetSchema });
export const tasksRpc = defineRpc({ name: 'autowork.tasks', input: z.strictObject(target),
  output: z.object({ revision: z.string(), tasks: z.array(taskSchema) }) });
export const taskRpc = defineRpc({ name: 'autowork.task', input: z.strictObject({ ...target, task: idSchema, working: z.boolean().default(false) }), output: taskDetailSchema });
export const goalsRpc = defineRpc({ name: 'autowork.goals', input: z.strictObject(target),
  output: z.object({ revision: z.string(), goals: z.array(goalSchema) }) });
export const logsRpc = defineRpc({ name: 'autowork.logs', input: z.strictObject({ ...target, lines: z.number().int().min(20).max(2000).default(150) }),
  output: z.object({ text: z.string(), capturedAt: z.number() }) });
export const statusRpc = defineRpc({ name: 'autowork.status', input: z.strictObject(target), output: z.object({ text: z.string(), capturedAt: z.number() }) });
export const scorecardRpc = defineRpc({ name: 'autowork.scorecard', input: z.strictObject({ instance: z.string(), days: z.number().int().min(1).max(30).default(7) }),
  output: z.object({ value: z.unknown(), capturedAt: z.number() }) });
export const modelsRpc = defineRpc({ name: 'autowork.models', input: z.strictObject({ instance: z.string() }),
  output: z.object({ models: z.array(z.string()), capturedAt: z.number() }) });
export const storeRpc = defineRpc({ name: 'autowork.store', input: z.strictObject({ ...target, view: storeViewSchema, task: idSchema.optional() }),
  output: z.object({ value: z.unknown(), capturedAt: z.number() }) });
export const watchRpc = defineRpc({ name: 'autowork.watch', input: z.strictObject({ instance: z.string(), digest: z.string().max(128).default('') }),
  output: z.object({ digest: z.string(), changed: z.boolean(), capturedAt: z.number() }) });
export const prepareRpc = defineRpc({ name: 'autowork.prepare', input: prepareSchema, output: ticketSchema });
export const commitRpc = defineRpc({ name: 'autowork.commit', input: z.strictObject({ instance: z.string(), ticket: z.string() }), output: operationSchema });
export const operationRpc = defineRpc({ name: 'autowork.operation', input: z.strictObject({ instance: z.string(), id: idSchema }), output: operationSchema });
export const planningRpc = defineRpc({ name: 'autowork.planning', input: z.strictObject({ ...target,
  sessionId: idSchema, view: z.enum(['preview', 'history', 'roadmap']) }), output: z.object({ value: z.unknown() }) });

export type Fleet = z.infer<typeof fleetSchema>;
export type Repo = z.infer<typeof repoSchema>;
export type Runner = z.infer<typeof runnerSchema>;
export type Task = z.infer<typeof taskSchema>;
export type TaskDetail = z.infer<typeof taskDetailSchema>;
export type Goal = z.infer<typeof goalSchema>;
export type Action = z.infer<typeof actionSchema>;
/** What a caller sends: defaults such as the planning mode may be omitted. */
export type ActionInput = z.input<typeof actionSchema>;
export type Operation = z.infer<typeof operationSchema>;
export type Ticket = z.infer<typeof ticketSchema>;
export type Policy = z.infer<typeof policySchema>;
export type Control = z.infer<typeof controlSchema>;
export type Maintenance = z.infer<typeof maintenanceSchema>;
export type StoreView = z.infer<typeof storeViewSchema>;
export const ALL_CONTROLS = controlSchema.options;
export const ALL_MAINTENANCE = maintenanceSchema.options;
/** The grant each action kind needs; the host operator's policy is the only source of grants. */
export function grantFor(action: Action): keyof Policy {
  switch (action.kind) {
    case 'control': return 'controls';
    case 'model': case 'clear-held': case 'attention': return 'maintenance';
    case 'decision': return 'decisions';
    case 'commit': return 'commit';
    case 'plan-start': case 'plan-send': case 'plan-cancel': case 'plan-steer': case 'plan-apply': return 'planning';
    default: return 'tasks';
  }
}
