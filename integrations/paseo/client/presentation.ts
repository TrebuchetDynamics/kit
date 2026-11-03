import type { Runner, Task, TaskDetail } from '../shared/contracts';

export function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
export function display(value: unknown): string {
  if (value === undefined || value === null || value === '') return 'unknown';
  if (typeof value === 'string') return value.slice(0, 16000);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2).slice(0, 16000);
}
export function closureLabel(closure: Record<string, unknown>): string {
  const provenance = typeof closure.provenance === 'string' ? closure.provenance : 'unknown provenance';
  const verified = closure.provenance === 'coordinator_verified' ? closure.evidence_valid : closure.verified;
  const verification = verified === true ? 'verified' : verified === false ? 'not verified' : 'verification unknown';
  return `${display(closure.label)} · ${provenance} · ${verification}`;
}
export function canAnswer(task: Task, runner: Runner, detail: TaskDetail): boolean {
  return task.status === 'open' && detail.status === 'open' && detail.id === task.id && !!detail.record_revision && runner.questions.some(question => question.id === task.id);
}
export interface PlanPreview { revision: string; files: string[]; diff: string }
export function previewForApply(value: unknown): PlanPreview | null {
  const item = record(value);
  if (!item || item.valid !== true || typeof item.revision !== 'string' || !item.revision.trim() || !Array.isArray(item.files) || !item.files.length || !item.files.every(file => typeof file === 'string' && file.length > 0)) return null;
  return { revision: item.revision, files: item.files, diff: typeof item.diff === 'string' ? item.diff : '' };
}
export interface TaskFilters { task: string; goal: string; runtime: string; section: string }
export function taskMatches(task: Task, filters: TaskFilters, runtime: string): boolean {
  const contains = (value: string, filter: string) => value.toLowerCase().includes(filter.trim().toLowerCase());
  return contains(`${task.id} ${task.title}`, filters.task) && contains(task.goal ?? '', filters.goal) && contains(runtime, filters.runtime) && contains(task.section ?? '', filters.section);
}
export function knownDirectory(path: string, directory: string): boolean {
  const root = path.replace(/\/+$/, '');
  return directory === root || directory.startsWith(`${root}/`);
}

export function shortHash(value: unknown, length = 8): string {
  return typeof value === 'string' && value ? value.slice(0, length) : 'unknown';
}
export function human(value: unknown): string {
  if (value === undefined || value === null || value === '') return 'unknown';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.length ? value.map(human).join(' · ') : 'none';
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).filter(([, item]) => item !== null && item !== undefined && item !== '');
    return entries.length ? entries.slice(0, 8).map(([key, item]) => `${key}: ${human(item)}`).join(' · ') : 'none';
  }
  return String(value);
}
export function mainCheckSummary(value: unknown): string {
  const item = record(value);
  if (!item) return 'no evidence';
  const state = item.result_class ?? item.state;
  const checked = shortHash(item.checked_rev ?? item.rev);
  const main = shortHash(item.main_head ?? item.green);
  const finished = typeof item.finished === 'number' ? new Date(item.finished * 1000).toLocaleString() : 'unknown time';
  return `${human(item.state)}${state ? ` · ${human(state)}` : ''} · checked ${checked} · main ${main} · ${finished}`;
}
export function jobSummary(value: unknown): string {
  if (value === null || value === undefined) return 'unknown';
  const item = record(value);
  if (!item) return human(value);
  const parts = ['task', 'id', 'title', 'status', 'phase', 'state']
    .flatMap(key => item[key] !== undefined ? [`${key}: ${human(item[key])}`] : []);
  return parts.length ? parts.join(' · ') : human(value);
}
