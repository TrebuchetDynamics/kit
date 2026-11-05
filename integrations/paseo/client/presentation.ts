import type { Repo, Runner, Task, TaskDetail } from '../shared/contracts';

export type Tone = 'success' | 'warning' | 'danger' | 'neutral';

export function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
export function display(value: unknown): string {
  if (value === undefined || value === null || value === '') return 'unknown';
  if (typeof value === 'string') return value.slice(0, 16000);
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value, null, 2).slice(0, 16000);
}
export const known = (value: unknown): boolean => value !== undefined && value !== null && value !== '' && value !== 'unknown';

/** Colour follows meaning, never a substring: "not running" is neutral, only live states are green. */
export function stateTone(state: string): Tone {
  const value = state.trim().toLowerCase();
  if (!value || value === 'unknown') return 'neutral';
  if (/\bnot running\b|\bstopped\b|\bidle\b|\bdisabled\b|\bremoved\b|\bcancelled\b|\bdone\b|\bsuperseded\b|\bclosed\b/.test(value)) return 'neutral';
  if (/\bfail|\berror|\bdead\b|\bred\b|\bblock|\bcrash|\bmissing\b/.test(value)) return 'danger';
  if (/\bpaus|\bwait|\bstall|\bdecision|\buncertain\b|\bhold|\bheld\b|\bpending\b|\brestarting\b|\bdraft\b/.test(value)) return 'warning';
  if (/\brunning\b|\bactive\b|\bready\b|\bsucceeded\b|\bgreen\b|\bpass\b|\bverified\b|\bopen\b|\bmet\b/.test(value)) return 'success';
  return 'neutral';
}
/** The icon that carries the same meaning as the colour, for colour-blind and screen-reader users. */
export function toneIcon(tone: Tone): string {
  return tone === 'success' ? 'CircleCheck' : tone === 'warning' ? 'CircleAlert' : tone === 'danger' ? 'CircleX' : 'Circle';
}
export function shortHash(value: unknown, length = 8): string {
  return typeof value === 'string' && value ? value.slice(0, length) : 'unknown';
}
/** Revision text as Autowork reports it: a hash, optionally suffixed with "+working". */
export function revisionParts(revision: string): { hash: string; short: string; suffix: string } {
  const [hash = '', ...rest] = revision.split('+');
  return { hash, short: shortHash(hash), suffix: rest.length ? `+${rest.join('+')}` : '' };
}
/** Seconds, milliseconds or an ISO timestamp become "5m ago"; the unit is inferred from magnitude. */
export function relativeTime(value: unknown, now = Date.now()): string {
  const parsed = typeof value === 'string' ? Date.parse(value) : value;
  if (typeof parsed !== 'number' || !Number.isFinite(parsed) || parsed <= 0) return 'unknown time';
  const millis = parsed < 1e11 ? parsed * 1000 : parsed;
  const seconds = Math.round((now - millis) / 1000);
  if (seconds < 0) return 'just now';
  if (seconds < 45) return seconds < 5 ? 'just now' : `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
export function closureLabel(closure: Record<string, unknown>): string {
  const provenance = typeof closure.provenance === 'string' ? closure.provenance.replace(/_/g, ' ') : 'unknown provenance';
  const verified = closure.provenance === 'coordinator_verified' ? closure.evidence_valid : closure.verified;
  const verification = verified === true ? 'verified' : verified === false ? 'not verified' : 'verification unknown';
  // The badge already shows the closure label; this line adds only provenance and proof.
  return `${provenance} · ${verification}`;
}
/** One badge for a closed task: how it was closed and whether evidence backs it. */
export function closureBadge(closure: Record<string, unknown>): { label: string; tone: Tone } | null {
  if (!Object.keys(closure).length) return null;
  const verified = closure.provenance === 'coordinator_verified' ? closure.evidence_valid : closure.verified;
  if (verified === true) return { label: 'verified', tone: 'success' };
  if (closure.provenance === 'manual') return { label: 'manual close', tone: 'warning' };
  if (verified === false) return { label: 'not verified', tone: 'warning' };
  return { label: display(closure.label), tone: 'neutral' };
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
export const emptyFilters: TaskFilters = { task: '', goal: '', runtime: '', section: '' };
export function taskMatches(task: Task, filters: TaskFilters, runtime: string): boolean {
  const contains = (value: string, filter: string) => value.toLowerCase().includes(filter.trim().toLowerCase());
  return contains(`${task.id} ${task.title}`, filters.task) && contains(task.goal ?? '', filters.goal) && contains(runtime, filters.runtime) && contains(task.section ?? '', filters.section);
}
/** Work someone can still act on; closed records are shown only on request. */
export function isActionable(task: Pick<Task, 'status'>): boolean {
  return !/^(done|superseded|closed|cancelled)$/i.test(task.status);
}
/** One state for the queue row and the detail sheet: an owner question wins, then a blocker, then the record status. */
export function taskState(task: Pick<Task, 'status' | 'blocked_by'>, question: boolean): string {
  if (question) return 'needs decision';
  if (isActionable(task) && task.blocked_by) return 'blocked';
  return task.status;
}
export function knownDirectory(path: string, directory: string): boolean {
  const root = path.replace(/\/+$/, '');
  return directory === root || directory.startsWith(`${root}/`);
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
export function mainCheckSummary(value: unknown, now = Date.now()): string {
  const item = record(value);
  if (!item) return 'no evidence';
  const state = item.result_class ?? item.state;
  const checked = shortHash(item.checked_rev ?? item.rev);
  const main = shortHash(item.main_head ?? item.green);
  return `${human(item.state)}${state ? ` · ${human(state)}` : ''} · checked ${checked} · main ${main} · ${relativeTime(item.finished, now)}`;
}
/** A selection explanation as sentences with the technical payload kept one tap away. */
export function selectionFacts(value: unknown, now = Date.now()): Array<[string, string]> {
  const item = record(value);
  if (!item) return [];
  const rows: Array<[string, string]> = [];
  if (item.eligible !== undefined) rows.push(['Eligible now', item.eligible === true ? 'yes' : 'no']);
  if (item.first !== undefined) rows.push(['Next in queue', item.first === true ? 'yes' : 'no']);
  const reasons = (Array.isArray(item.reasons) ? item.reasons : []).map(record).filter((reason): reason is Record<string, unknown> => !!reason)
    .map(reason => [known(reason.code) ? human(reason.code).replace(/_/g, ' ').toLowerCase() : '', known(reason.detail) ? human(reason.detail) : ''].filter(Boolean).join(': '))
    .filter(Boolean);
  if (reasons.length) rows.push(['Reasons', reasons.join(' · ')]);
  const closure = record(item.closure);
  const labels: Array<[string, string]> = [['provenance', 'Closed by provenance'], ['actor', 'Closed by'], ['timestamp', 'Closed at'], ['reason', 'Closure reason'], ['evidence', 'Closure evidence']];
  for (const [key, label] of labels) {
    if (!closure || !known(closure[key])) continue;
    rows.push([label, key === 'timestamp' ? relativeTime(closure[key], now) : human(closure[key])]);
  }
  return rows;
}
export function mainCheckTone(value: unknown): Tone {
  const item = record(value);
  if (!item) return 'neutral';
  return stateTone(`${human(item.state)} ${human(item.result_class)}`);
}
export function jobSummary(value: unknown): string {
  if (value === null || value === undefined) return 'unknown';
  const item = record(value);
  if (!item) return human(value);
  const parts = ['task', 'id', 'title', 'status', 'phase', 'state']
    .flatMap(key => item[key] !== undefined ? [`${key}: ${human(item[key])}`] : []);
  return parts.length ? parts.join(' · ') : human(value);
}
/** Observation fields as sentences: epoch timestamps become relative, booleans become yes/no, snake_case becomes words. */
export function observationRows(value: unknown, now = Date.now()): Array<[string, string]> {
  const item = record(value);
  if (!item) return [];
  return Object.entries(item).filter(([, field]) => known(field)).slice(0, 12).map(([key, field]) => {
    const label = key.replace(/_/g, ' ').replace(/^./, first => first.toUpperCase());
    if (/_at$|timestamp|time$/.test(key) && typeof field === 'number') return [label, relativeTime(field, now)];
    if (typeof field === 'boolean') return [label, field ? 'yes' : 'no'];
    return [label, human(field)];
  });
}
/** Health, runtime and policy facts for the runner, without unknown or zero noise. */
export function runnerFacts(runner: Runner): { runtime: Array<[string, string]>; policy: Array<[string, string]> } {
  const runtime: Array<[string, string]> = [];
  if (known(runner.model)) runtime.push(['Configured model', runner.model]);
  if (known(runner.fallback)) runtime.push(['Fallback model', runner.fallback]);
  if (known(runner.toolset)) runtime.push(['Configured toolset', runner.toolset]);
  if (runner.max_workers != null) runtime.push(['Max workers', String(runner.max_workers)]);
  if (known(runner.mode)) runtime.push(['Mode', runner.mode]);
  const policy: Array<[string, string]> = [['Push', runner.push ? 'allowed' : 'not allowed'], ['Enabled', runner.enabled ? 'yes' : 'no']];
  if (known(runner.gate)) policy.push(['Gate', runner.gate]);
  return { runtime, policy };
}
/** A single "why it stopped" line: blocker and stop reason often repeat each other. */
export function whyStopped(runner: Runner): string[] {
  const reasons = [runner.blocker, runner.stop_reason].map(item => item.trim()).filter(Boolean);
  return reasons.filter((item, index) => reasons.indexOf(item) === index);
}
/** Most urgent first: needs a decision or is broken, then live, then paused, then not running. */
export function urgency(repo: Repo): number {
  const runner = repo.runner;
  if (repo.error) return 0;
  if (!runner) return 4;
  if (runner.decisions > 0) return 0;
  if (stateTone(runner.state) === 'danger') return 1;
  if (runner.running > 0 || stateTone(runner.state) === 'success') return 2;
  if (stateTone(runner.state) === 'warning') return 3;
  return 4;
}
export function sortByUrgency(repos: Repo[]): Repo[] {
  return [...repos].sort((a, b) => urgency(a) - urgency(b) || (b.runner?.decisions ?? 0) - (a.runner?.decisions ?? 0) || a.label.localeCompare(b.label));
}
/** A blocker shared by several runners is a host problem; it is said once, not once per row. */
export function sharedBlocker(repos: Repo[]): string | null {
  const counts = new Map<string, number>();
  for (const repo of repos) { const blocker = repo.runner?.blocker.trim(); if (blocker) counts.set(blocker, (counts.get(blocker) ?? 0) + 1); }
  const [top] = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  return top && top[1] >= 2 ? top[0] : null;
}
/** A blocker code is not a task ID: NEEDS_DECISION reads as “needs decision”. */
export function blockedReason(value: string): string {
  return /^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$/.test(value) ? value.replace(/_/g, ' ').toLowerCase() : value;
}
/** Counts worth a word; zeros are silence. */
export function countSummary(runner: Runner | null): string {
  if (!runner) return 'no runner record';
  const parts = [[runner.running, 'running'], [runner.waiting, 'waiting'], [runner.stopped, 'stopped'], [runner.decisions, runner.decisions === 1 ? 'decision' : 'decisions']] as const;
  const said = parts.filter(([count]) => count > 0).map(([count, word]) => `${count} ${word}`);
  return said.length ? said.join(' · ') : 'idle';
}
/** The owner question, not the goal history that precedes it, as the headline above the fold. */
export function headline(text: string, max = 160): string {
  const plain = stripMarkdown(text).replace(/\s+/g, ' ').trim();
  const asked = plain.match(/\bQuestion:\s*(.+?)(?:\?|$)/i)?.[1]?.trim();
  const sentence = asked ? `${asked}?` : plain.match(/^.{1,}?[.!?](?=\s|$)/)?.[0] ?? plain;
  return sentence.length > max ? `${sentence.slice(0, max - 1).trimEnd()}…` : sentence;
}
/** A stale daemon-side plugin generation refuses every read until the owner reloads it. */
export function reloadRequired(error: unknown): boolean {
  const raw = error instanceof Error ? error.message : String(error);
  return /source release changed|executable changed/i.test(raw);
}
/** Host failures as one sentence; raw RPC metadata belongs in Diagnostics. */
export function friendlyError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  const clean = raw.replace(/\s*requestType=.*$/s, '').replace(/\s*code=.*$/s, '').replace(/^Request failed:\s*/i, '').trim();
  if (/request limit reached/i.test(clean)) return 'Autowork is busy; refresh later.';
  if (reloadRequired(clean)) return 'Autowork updated on this host; this plugin needs a reload.';
  if (/plugin stopped/i.test(clean)) return 'The plugin restarted; refresh.';
  return clean || 'The request failed; retry when the host is available.';
}
export type Segment = { text: string; bold?: boolean; code?: boolean; link?: string };
/** Inline Markdown as segments: bold, code and links render as their text, never as source. */
export function markdownSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  const pattern = /\*\*(.+?)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > last) segments.push({ text: text.slice(last, index) });
    if (match[1] !== undefined) segments.push({ text: match[1], bold: true });
    else if (match[2] !== undefined) segments.push({ text: match[2], code: true });
    else if (match[3] !== undefined) segments.push({ text: match[3], link: match[4] });
    last = index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last) });
  return segments;
}
export function stripMarkdown(text: string): string {
  return markdownSegments(text).map(segment => segment.text).join('').replace(/^#+\s*/gm, '').replace(/^\s*[-*]\s+/gm, '');
}
