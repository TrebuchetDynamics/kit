// Native host-element stub for Node test-renderer only; NOT Android or desktop qualification.
import React from 'react';
import { act, create, type ReactTestRenderer } from 'react-test-renderer';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { PluginScreenProps } from '@getpaseo/plugin/client';
import { fleetSchema, taskDetailSchema, taskSchema } from '../shared/contracts';

const env = vi.hoisted(() => ({
  directory: '/repo' as string | null,
  hosts: [{ serverId: 'a', label: 'A', status: 'online' }],
  invoke: vi.fn(), state: 'active', listener: null as null | ((state: string) => void),
  toast: { show: vi.fn(), error: vi.fn() }, copyText: vi.fn(async () => {}),
}));
vi.mock('react-native', async () => {
  const React = await import('react');
  const host = (name: string) => (props: Record<string, unknown>) => React.createElement(name, props, props.children as React.ReactNode);
  return { View: host('View'), Text: host('Text'), Pressable: host('Pressable'),
    RefreshControl: host('RefreshControl'),
    AppState: { get currentState() { return env.state; }, addEventListener: (_: string, fn: typeof env.listener) => {
      env.listener = fn; return { remove() { env.listener = null; } };
    } } };
});
vi.mock('@getpaseo/plugin/client/ui', async () => {
  const React = await import('react');
  const host = (name: string) => (props: Record<string, unknown>) => React.createElement(name, props, props.children as React.ReactNode);
  const Modal = Object.assign((props: Record<string, unknown>) => props.open ? React.createElement('Modal', props, React.createElement('Text', null, props.title as string), props.children as React.ReactNode) : null, { Content: host('ModalContent') });
  return { ScrollView: host('ScrollView'), TextInput: host('TextInput'), SidebarRow: host('SidebarRow'), Icon: host('Icon'), Modal, copyText: env.copyText, useToast: () => env.toast };
});
vi.mock('@getpaseo/plugin/client', () => ({
  useHosts: () => env.hosts,
  useWorkspace: () => env.directory === null ? null : ({ directory: env.directory }),
  useRpc: (contract: { name: string }) => (input: unknown) => env.invoke(contract.name, input),
}));
import { AutoworkScreen, WorkspacePanel } from '../client/screens';
import { SettingsScreen } from '../client/settings';
import { taskTone, closureTone } from '../client/presentation';
import { Theme } from '../client/ui';
import { canAnswer, headline, mainCheckSummary, markdownSegments, observationRows, previewForApply, relativeTime, revisionParts, selectionFacts, stateTone, taskMatches } from '../client/presentation';

const taskDisplay = { state: 'Waiting · Needs decision', bucket: 'Decision', why: 'in Needs decision',
  question: false, pending: false, blocker: '', closure: null, record_revision: 'working-rev' };
const manualDisplay = { ...taskDisplay, state: 'Manual', bucket: '', why: 'Manual closure detail',
  closure: { label: 'Manual', detail: 'Manual closure detail', verified: false, provenance: 'manual' } };
const fleet = (instance = 'generation-1') => fleetSchema.parse({ instance, capturedAt: Date.now(), release: 'configured-release', executable: '/bin/autowork', prepareApi: 4,
  permissions: { controls: ['pause'], planning: true, decisions: true, tasks: true, commit: true, maintenance: ['model', 'clear-held', 'attention'] }, policy: { path: '/policy.json', source: 'default' }, capabilities: { commands: ['ls', 'tasks', 'plan', 'logs', 'status', 'scorecard', 'models'], tasks: ['list', 'show', 'decide', 'goals', 'commit', 'validate', 'prepare', 'why'] }, warnings: [], repos: [{ id: 'repo', label: 'Repository', path: '/repo', identity: 'identity', revision: 'rev',
    runner: { name: 'runner', repo: '/repo', state: 'waiting', display: { state: 'waiting', needs: 'CLI next action', question_summary: 'CLI question summary', blockers: [], question_ids: ['T-1'], revision: 'rev', tasks: {} }, questions: [{ id: 'T-1', effort: 'small', unblocks: 1, needs: 'Choose the scope' }], held: [['T-2', 'technical hold']] } }] });
const task = taskSchema.parse({ display: taskDisplay, id: 'T-1', title: 'Owner task', section: 'Needs decision', status: 'open', goal: 'goal', rank: 1, position: 1, blocked_by: null, closure: {} });
const detail = taskDetailSchema.parse({ ...task, short: null, depends_on: [], verified_depends_on: [], touches: [], resources: [], kind: 'task', ownership: 'owner', live: 'waiting', scope: null,
  acceptance: ['Must preserve contract'], checks: ['unit'], exclusions: [], contract_hash: 'hash', record_revision: 'working-rev', path: '/repo/T-1', rev: 'rev', notes: 'Evidence notes', draft: false, missing_fields: [] });
const props: PluginScreenProps = { host: { id: 'a', label: 'A' }, params: {}, layout: { compact: true, platform: 'android' },
  theme: { colors: { surface0: '#000', surface1: '#111', surface2: '#222', border: '#333', foreground: '#fff', foregroundMuted: '#aaa', accent: '#06f', accentForeground: '#fff', statusSuccess: '#0f0', statusWarning: '#ff0', statusDanger: '#f00' } } };
let root: ReactTestRenderer;
let query: QueryClient;
const flush = async () => { await act(async () => { await new Promise<void>(resolve => setTimeout(() => resolve(), 20)); }); };
const text = () => root.root.findAll(node => String(node.type) === 'Text').map(node => node.children.filter(child => typeof child === 'string').join('')).join('\n');
const operation = (overrides: Partial<import('../shared/contracts').Operation> = {}): import('../shared/contracts').Operation => ({ id: 'operation-1', repoId: 'repo', kind: 'plan-start', status: 'running', message: 'Owned planning', startedAt: Date.now(), completedAt: null, sessionId: null, progress: 'Working', ...overrides });
const render = (extra: Partial<PluginScreenProps> = {}) => <QueryClientProvider client={query}><AutoworkScreen {...props} {...extra} /></QueryClientProvider>;
const rerender = async (extra: Partial<PluginScreenProps> = {}) => { await act(async () => root.update(render(extra))); await flush(); };
const input = async (label: string, value: string) => { await act(async () => root.root.find(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === label).props.onChangeText(value)); };
const button = (label: string) => root.root.findAll(node => String(node.type) === 'Pressable' && node.props.accessibilityLabel === label)[0];
async function press(label: string) { const node = button(label); expect(node, label).toBeTruthy(); await act(async () => { node!.props.onPress(); }); await flush(); }
async function mount(extra: Partial<PluginScreenProps> = {}) {
  query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  await act(async () => { root = create(<QueryClientProvider client={query}><AutoworkScreen {...props} {...extra} /></QueryClientProvider>); });
  await flush();
}
beforeEach(() => {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
  env.hosts = [{ serverId: 'a', label: 'A', status: 'online' }]; env.state = 'active'; env.directory = '/repo';
  env.invoke.mockReset().mockImplementation(async (name, input) => {
    if (name === 'autowork.fleet') return fleet();
    if (name === 'autowork.tasks') return { revision: 'rev', tasks: [task] };
    if (name === 'autowork.task') return detail;
    if (name === 'autowork.watch') return { digest: 'digest-1', changed: false, capturedAt: Date.now() };
    if (name === 'autowork.goals') return { revision: 'rev', goals: [{ id: 'goal', title: 'Goal', priority: 1, source: 'docs/plan.md', status: 'unmet', focus: false, depends_on: [], record_revision: 'goal-v1' }] };
    if (name === 'autowork.store') return { value: input && (input as { view: string }).view === 'pending' ? { files: ['tasks/items/T-1.md'], diff: '+ Owner decision', pending_revision: 'a'.repeat(64), commit: null, dry_run: true,
      lifecycle: { state: 'pending_commit', message: 'The runner reads committed records; commit the saved answer.' } } : { ok: true }, capturedAt: Date.now() };
    if (name === 'autowork.models') return { models: ['provider/model-a'], capturedAt: Date.now() };
    if (name === 'autowork.scorecard') return { value: { days: 7, runners: { runner: { closed: 2, verified_closed: 1, evaluation: { summary: { closed: { value: 2, unit: 'tasks', status: 'measured' } } } } }, errors: { gone: '/missing is not a directory' }, overall: { summary: {} } }, capturedAt: Date.now() };
    if (name === 'autowork.status') return { text: 'Runner:     not running', capturedAt: Date.now() };
    if (name === 'autowork.prepare') return { ticket: 'ticket', expiresAt: Date.now() + 60000, summary: 'Pause repository', pushAllowed: false };
    if (name === 'autowork.commit') return { id: 'operation-1', repoId: 'repo', kind: 'control', status: 'succeeded', message: 'Dispatched; inspect observation', startedAt: Date.now(), completedAt: Date.now(), sessionId: null, progress: '' };
    throw new Error(`Unexpected RPC ${name} ${JSON.stringify(input)}`);
  });
});
afterEach(async () => { if (root) await act(async () => root.unmount()); query?.clear(); });

describe('canonical presentation', () => {
  it('keeps closure tones canonical and preserves the answer gate', () => {
    expect(closureTone({ presentation: { tone: 'neutral', closure_tone: 'warning' } })).toBe('warning');
    expect(closureTone({ presentation: { tone: 'neutral', closure_tone: 'success' } })).toBe('success');
    expect(closureTone(undefined)).toBe('neutral');
    expect(canAnswer(task, fleet().repos[0]!.runner!, detail)).toBe(true);
    expect(canAnswer({ ...task, id: 'T-2' }, fleet().repos[0]!.runner!, detail)).toBe(false);
    expect(canAnswer({ ...task, status: 'done' }, fleet().repos[0]!.runner!, detail)).toBe(false);
  });
  it('formats main-check and evidence objects instead of dumping raw JSON', () => {
    const summary = mainCheckSummary({ state: 'green', result_class: 'PASS', checked_rev: '7c9960e54149a2e7b5a12cbc', main_head: '7c9960e54149a2e7b5a12cbc', finished: 1793507113.748 });
    expect(summary).toContain('green · PASS');
    expect(summary).not.toContain('{"');
    expect(summary).toContain('checked 7c9960e5');
  });
  it('requires a valid exact preview revision and supports task, goal, runtime and section filters', () => {
    expect(previewForApply({ revision: 'r', valid: true, files: ['a'], diff: 'diff', errors: [] })?.revision).toBe('r');
    expect(previewForApply({ revision: 'r', valid: false, files: ['a'] })).toBeNull();
    expect(previewForApply({ revision: 'r', valid: true, files: [] })).toBeNull();
    expect(taskMatches(task, { task: 'T-1', goal: 'goal', runtime: 'waiting', section: 'Needs decision' }, 'waiting')).toBe(true);
    expect(taskMatches(task, { task: '', goal: 'other', runtime: '', section: '' }, 'waiting')).toBe(false);
  });
  it('reads a selection explanation as facts', () => {
    const rows = selectionFacts({ task: 'T-1', eligible: false, first: false, reasons: [{ code: 'DONE', detail: '' }],
      closure: { provenance: 'manual', actor: 'DOCS-MAINTAINER', timestamp: '2026-10-29T08:37:02.447894+00:00', reason: 'Final reconciliation' } }, Date.parse('2026-10-29T09:37:02Z'));
    expect(rows).toContainEqual(['Eligible now', 'no']);
    expect(rows).toContainEqual(['Reasons', 'done']);
    expect(rows.find(([name]) => name === 'Closed at')?.[1]).toBe('1h ago');
    expect(rows.find(([name]) => name === 'Closure reason')?.[1]).toBe('Final reconciliation');
    expect(relativeTime('2026-10-29T08:37:02.447894+00:00', Date.parse('2026-10-29T08:39:02Z'))).toBe('2m ago');
  });
});

describe('native host-scoped surfaces', () => {
  it('keeps repository context through the overview round trip without dispatching changes', async () => {
    const value = fleet(); const base = value.repos[0]!;
    value.repos.push({ ...base, id: 'second', label: 'Second', path: '/repo/second' });
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.fleet' ? Promise.resolve(value) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    await press('Switch repository'); await press('Repository Second');
    expect(text()).toContain('/repo/second');
    expect(text()).toContain('Second · Tasks');
    expect(button('Tasks')!.props.accessibilityState.selected).toBe(true);
    await press('Back to Fleet');
    expect(button('Back to Fleet')).toBeUndefined();
    expect(button('Fleet')!.props.accessibilityState.selected).toBe(true);
    await press('Tasks');
    expect(text()).toContain('Second · Tasks');
    expect(text()).toContain('/repo/second');
    expect(env.invoke.mock.calls.some(([name]) => ['autowork.prepare', 'autowork.commit'].includes(name))).toBe(false);
  });
  it('explains workspace mismatch and refreshes only the known fleet', async () => {
    await mount({ params: { directory: '/unknown-workspace' } });
    expect(text()).toContain('No known repository matches this workspace.');
    expect(text()).toContain('/unknown-workspace');
    expect(text()).toContain('Open a workspace inside a known repository');
    const reads = env.invoke.mock.calls.filter(([name]) => name === 'autowork.fleet').length;
    await press('Refresh repositories');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.fleet')).toHaveLength(reads + 1);
    expect(env.invoke.mock.calls.some(([name]) => ['autowork.tasks', 'autowork.prepare', 'autowork.commit'].includes(name))).toBe(false);
  });
  it('provides a recovery action for an empty task queue', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('No tasks observed.');
    const reads = env.invoke.mock.calls.filter(([name]) => name === 'autowork.tasks').length;
    await press('Refresh task queue');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.tasks')).toHaveLength(reads + 1);
  });
  it('shows a loading explanation until the first fleet observation arrives', async () => {
    const initial = env.invoke.getMockImplementation()!;
    let resolveFleet!: (value: ReturnType<typeof fleet>) => void;
    const pending = new Promise<ReturnType<typeof fleet>>(resolve => { resolveFleet = resolve; });
    env.invoke.mockImplementation((name, data) => name === 'autowork.fleet' ? pending : initial(name, data));
    await mount();
    expect(text()).toContain('Reading repositories…');
    expect(button('Tasks')).toBeUndefined();
    await act(async () => resolveFleet(fleet())); await flush();
    expect(text()).not.toContain('Reading repositories…');
    expect(button('Tasks')).toBeTruthy();
  });

  it('renders canonical status, unknown transport and manual closure without inferring health', async () => {
    await mount();
    expect(text()).toContain('waiting'); expect(text()).not.toContain('Transport');
    await press('Connection details'); expect(text()).toContain('Transport');
    await press('Tasks');
    expect(text()).toContain('Owner task'); expect(text()).not.toContain('Closure: unknown');
    await press('Open task T-1'); await press('Contract and evidence');
    expect(text()).toContain('Must preserve contract');
    expect(button('Send answer')).toBeTruthy();
  });
  // The owner answers on this view; the runner reads committed records, so the commit step
  // has to be visible here too instead of only in Tasks.
  it('uses semantic presentation even when the words suggest another tone', () => {
    const projected = { ...task, status: 'running', presentation: { tone: 'danger' as const, closure_tone: 'warning' as const } };
    expect(taskTone(projected)).toBe('danger');
    expect(taskTone({ presentation: undefined })).toBe('neutral');
    expect(taskTone(projected, true)).toBe('warning');
    expect(closureTone(projected)).toBe('warning');
    expect(closureTone({ presentation: undefined })).toBe('neutral');
  });
  it('shows the commit step where the answer is recorded', async () => {
    await mount({ params: { view: 'blockers' } }); await flush();
    expect(text()).toContain('Pending task edits');
    expect(text()).toContain('The runner reads committed records');
    expect(button('Commit task edits')).toBeTruthy();
  });
  it('prepares, requires explicit confirmation, consumes once and never auto-replays', async () => {
    await mount(); await press('Runner'); await press('Pause');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
    expect(text()).toContain('Pause repository');
    await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    expect(button('Confirm operation')).toBeUndefined();
  });
  it('shows every view and repository from a compact picker', async () => {
    const value = fleet(); const base = value.repos[0]!;
    const labels = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta', 'Iota', 'Kappa', 'Lambda', 'Mu'];
    value.repos = labels.map((label, index) => ({ ...base, id: `repo-${index}`, label, path: `/repo/repo-${index}`, runner: { ...base.runner!, repo: `/repo/repo-${index}` } }));
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.fleet' ? Promise.resolve(value) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    for (const title of ['Fleet', 'Runner', 'Tasks', 'Blockers', 'Planning', 'Scorecard']) expect(button(title), title).toBeTruthy();
    expect(root.root.findAll(node => String(node.type) === 'ScrollView' && node.props.horizontal === true)).toHaveLength(0);
    await press('Switch repository');
    expect(text()).toContain('Choose repository');
    await input('Search repositories', 'beta');
    expect(button('Repository Beta')).toBeTruthy();
    expect(button('Repository Alpha')).toBeUndefined();
    const rows = root.root.findAll(node => String(node.type) === 'Pressable' && /^Repository /.test(node.props.accessibilityLabel));
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.props.style.minHeight).toBeGreaterThanOrEqual(48);
      expect(row.props.style.minWidth).toBeGreaterThanOrEqual(48);
    }
    await press('Repository Beta');
    expect(button('Search repositories')).toBeUndefined();
    expect(text()).toContain('Beta');
    expect(env.invoke.mock.calls.some(([name, data]) => name === 'autowork.tasks' && (data as { repoId: string }).repoId === 'repo-1')).toBe(true);
  });
  it('names the exact effect and one safety limit before confirmation', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => {
      if (name === 'autowork.prepare') {
        const action = (data as { action: { kind: string } }).action;
        return Promise.resolve({ ticket: 'ticket', expiresAt: Date.now() + 60000, summary: action.kind === 'decision' ? 'Answer T-1' : 'Pause repository', pushAllowed: false });
      }
      return initial(name, data);
    });
    await mount({ params: { view: 'runner' } });
    await press('Pause');
    expect(text()).toContain('Pause repository');
    expect(text()).toContain('Runs pause once on Repository.');
    expect(text()).toContain('Single use; a lost response stays uncertain and is never retried.');
    expect(text()).toContain('Push not allowed (unchanged).');
    expect(text()).not.toContain('Confirming dispatches once');
    await press('Dismiss confirmation');
    await press('Tasks'); await press('Open task T-1');
    await input('Owner answer', 'Approved scope'); await press('Send answer');
    expect(text()).toContain('Answer T-1');
    expect(text()).toContain('Records your answer on T-1. It does not start work.');
  });
  it('keeps one Open action and Answer on a fleet row', async () => {
    const value = fleet(); value.repos[0]!.runner!.decisions = 1;
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.fleet' ? Promise.resolve(value) : initial(name, data));
    await mount();
    expect(button('Open Repository')).toBeTruthy();
    expect(button('Answer Repository')).toBeTruthy();
    expect(button('More Repository')).toBeUndefined();
    await press('Tasks');
    expect(text()).toContain('Owner task');
  });
  // A native modal body renders in the host's portal host, which rebuilds only Paseo's own
  // runtime contexts. The sheet must re-provide this plugin's theme, or every label inside it
  // throws and takes the whole app down (Android report: "Autowork theme missing").
  it('re-provides the plugin theme inside a host modal body', async () => {
    await mount({ params: { view: 'runner' } }); await press('Pause');
    const body = root.root.findAll(node => String(node.type) === 'ModalContent')[0];
    expect(body, 'no modal body rendered').toBeTruthy();
    const reProvided = React.Children.toArray(body.props.children as React.ReactNode)
      .some(child => React.isValidElement(child) && child.type === Theme.Provider);
    expect(reProvided).toBe(true);
    const colors = root.root.findAll(node => String(node.type) === 'Text' && node.props.style?.color).map(node => node.props.style.color);
    expect(colors).toContain(props.theme.colors.foreground);
  });
  // After an Autowork update the daemon-side generation refuses every read until the owner
  // reloads the plugin, so a bare "Retry now" and an automatic-retry promise are both wrong.
  it('names the reload step instead of promising an automatic recovery', async () => {
    env.invoke.mockImplementation(async () => { throw new Error('Autowork executable changed; reload the plugin to qualify its new release'); });
    await mount(); await flush();
    expect(text()).toContain('Autowork updated on this host');
    expect(text()).toContain('Paseo Settings → Plugins');
    expect(text()).toContain('a retry cannot succeed before that reload');
    expect(text()).not.toContain('bounded backoff');
    expect(text()).not.toContain('..');
    expect(button('Retry after reload')).toBeTruthy();
    expect(button('Retry now')).toBeUndefined();
  });
  it('does not query an offline/missing host or use another online host as fallback', async () => {
    env.hosts = [{ serverId: 'b', label: 'B', status: 'online' }];
    await mount(); expect(env.invoke).not.toHaveBeenCalled(); expect(text()).toContain('offline');
  });
  it('keys fleet by host and discards pending confirmations on host switch', async () => {
    await mount(); await press('Runner'); await press('Pause');
    env.hosts.push({ serverId: 'b', label: 'B', status: 'online' });
    await act(async () => root.update(<QueryClientProvider client={query}><AutoworkScreen {...props} host={{ id: 'b', label: 'B' }} /></QueryClientProvider>));
    await flush();
    expect(query.getQueryData(['autowork', 'a', 'fleet'])).toBeTruthy();
    expect(query.getQueryData(['autowork', 'b', 'fleet'])).toBeTruthy();
    expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('retains backend-owned operation handles across host switches without dispatch replay', async () => {
    env.invoke.mockImplementation(async name => {
      if (name === 'autowork.fleet') return fleet();
      if (name === 'autowork.prepare') return { ticket: 't', expiresAt: Date.now() + 60000, summary: 'Start planning', pushAllowed: false };
      if (name === 'autowork.commit') return operation();
      if (name === 'autowork.operation') return operation({ sessionId: 'owned-session', status: 'succeeded' });
      throw new Error(name);
    });
    await mount({ params: { view: 'planning' } });
    await press('Start planning'); await press('Confirm operation');
    await flush();
    env.hosts.push({ serverId: 'b', label: 'B', status: 'online' });
    await rerender({ host: { id: 'b', label: 'B' }, params: { view: 'planning' } });
    expect(text()).not.toContain('owned-session');
    await rerender({ params: { view: 'planning' } });
    expect(text()).toContain('owned-session');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('does not enable mutations using an old cached fleet capture', async () => {
    const value = fleet(); value.capturedAt = Date.now() - 120000;
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Cached');
    expect(button('Pause')!.props.disabled).toBe(true);
    expect(text()).toContain('Actions disabled');
    expect(text()).toContain('cached; refresh for live authority');
  });
  it('does not query a workspace without a known directory', async () => {
    env.directory = '';
    query = new QueryClient();
    await act(async () => { root = create(<QueryClientProvider client={query}><WorkspacePanel {...props} params={{}} workspaceId="w" revision={0} context="workspace" tab={{ state: null, setState() {}, setModified() {} }} /></QueryClientProvider>); });
    await flush();
    expect(env.invoke).not.toHaveBeenCalled();
    expect(text()).toContain('directory unavailable');
  });
  it('refreshes working revisions after reconnect instead of authorizing cached answers', async () => {
    await mount({ params: { view: 'tasks' } }); await press('Open task T-1');
    await input('Owner answer', 'Approved scope');
    expect(button('Send answer')!.props.disabled).toBe(false);
    await act(async () => { env.hosts[0]!.status = 'offline'; root.update(render({ params: { view: 'tasks' } })); });
    await flush();
    const before = env.invoke.mock.calls.filter(([name]) => name === 'autowork.task').length;
    await act(async () => { env.hosts[0]!.status = 'online'; root.update(render({ params: { view: 'tasks' } })); });
    await flush();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.task').length).toBeGreaterThan(before);
  });
  it('rejects late preparation after offline/reconnect and does not replay commit', async () => {
    const initial = env.invoke.getMockImplementation()!;
    let release!: (value: unknown) => void;
    env.invoke.mockImplementation((name, data) => name === 'autowork.prepare' ? new Promise(resolve => { release = resolve; }) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Pause');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'runner' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'runner' } });
    await act(async () => release({ ticket: 'late', expiresAt: Date.now() + 60000, summary: 'Late', pushAllowed: false }));
    expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('invalidates tickets and owned sessions on backend instance change', async () => {
    await mount({ params: { view: 'runner' } }); await press('Pause');
    env.invoke.mockImplementation(async name => { if (name === 'autowork.fleet') return fleet('generation-2'); throw new Error(name); });
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'fleet'], exact: true }); });
    await flush();
    expect((query.getQueryData(['autowork', 'a', 'fleet']) as { instance: string }).instance).toBe('generation-2'); expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('retains uncertainty after commit transport failure and does not retry on reconnect', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit' ? Promise.reject(new Error('Connection lost')) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Pause'); await press('Confirm operation');
    expect(text()).toContain('Delivery unknown; not retried');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'runner' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'runner' } });
    expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('renders the selection explanation as sentences and keeps the raw payload collapsed', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.store' && (data as { view: string }).view === 'why'
      ? Promise.resolve({ value: { task: 'T-1', eligible: false, first: false, reasons: [{ code: 'DONE', detail: '' }], closure: { provenance: 'manual', actor: 'DOCS-MAINTAINER', timestamp: Date.now() - 3600000, reason: 'Final reconciliation' } }, capturedAt: Date.now() })
      : initial(name, data));
    await mount({ params: { view: 'tasks' } }); await press('Open task T-1'); await press('Selection explanation');
    expect(text()).toContain('Eligible now'); expect(text()).toContain('Reasons'); expect(text()).toContain('Final reconciliation');
    expect(text()).not.toContain('"eligible"'); expect(button('Raw selection data')).toBeTruthy();
    expect(button('Close details')).toBeUndefined();
  });
  it('sends only the current owner record revision through confirmation', async () => {
    await mount({ params: { view: 'tasks' } }); await press('Open task T-1');
    await input('Owner answer', 'Literal answer; no command execution'); await press('Send answer');
    const prepared = env.invoke.mock.calls.find(([name]) => name === 'autowork.prepare')!;
    expect(prepared[1]).toEqual({ instance: 'generation-1', action: { kind: 'decision', repoId: 'repo', task: 'T-1', revision: 'working-rev', text: 'Literal answer; no command execution' } });
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('renders technical holds without exposing an answer action for held tasks', async () => {
    const initial = env.invoke.getMockImplementation()!;
    const display = { ...taskDisplay, state: 'Blocker', blocker: 'technical' };
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [{ ...task, id: 'T-2', title: 'Technical task', blocked_by: 'technical', display }] }) : name === 'autowork.task' ? Promise.resolve({ ...detail, id: 'T-2', display }) : initial(name, data));
    await mount({ params: { view: 'blockers' } }); await press('Technical holds and blocker evidence');
    expect(text()).toContain('technical hold');
    await press('Open task T-2');
    expect(button('Send answer')).toBeUndefined();
    expect(text()).toContain('Blocked by technical');
    expect(text()).toContain('No owner question is recorded for this task');
    expect(text()).not.toContain('not a current canonical owner question');
  });
  it('stages empty-objective planning, learns session from operation, previews then confirms exact Apply', async () => {
    let prepared: import('../shared/contracts').Action | undefined;
    env.invoke.mockImplementation(async (name, data) => {
      if (name === 'autowork.fleet') return fleet();
      if (name === 'autowork.prepare') { prepared = data.action; return { ticket: 't', expiresAt: Date.now() + 60000, summary: prepared!.kind, pushAllowed: false }; }
      if (name === 'autowork.commit') return operation({ id: prepared!.kind === 'plan-start' ? 'plan-op' : 'apply-op', kind: prepared!.kind, status: 'succeeded', sessionId: 'owned-plan', completedAt: Date.now() });
      if (name === 'autowork.planning') return { value: { revision: 'preview-exact', valid: true, files: ['Tasks/T-1.md'], diff: '+ acceptance', errors: [] } };
      throw new Error(name);
    });
    await mount({ params: { view: 'planning' } });
    expect(env.invoke.mock.calls.filter(([name]) => name !== 'autowork.fleet' && name !== 'autowork.watch')).toHaveLength(0);
    await press('Start planning');
    expect(prepared).toEqual({ kind: 'plan-start', repoId: 'repo', objective: '', mode: 'plan' });
    await press('Confirm operation'); await flush();
    expect(text()).toContain('Owned session: owned-plan');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.planning')).toHaveLength(0);
    expect(button('Apply preview')).toBeUndefined();
    await press('Read planning preview'); await press('Planning result');
    expect(text()).toContain('+ acceptance');
    await press('Apply preview');
    expect(prepared).toEqual({ kind: 'plan-apply', repoId: 'repo', sessionId: 'owned-plan', revision: 'preview-exact' });
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(2);
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.prepare').some(([, data]) => data.action.kind === 'control')).toBe(false);
  });
  it('discards a preview response from before disconnect instead of exposing Apply', async () => {
    let release!: (value: unknown) => void;
    env.invoke.mockImplementation(async name => {
      if (name === 'autowork.fleet') return fleet();
      if (name === 'autowork.prepare') return { ticket: 't', expiresAt: Date.now() + 60000, summary: 'Start', pushAllowed: false };
      if (name === 'autowork.commit') return operation({ status: 'succeeded', sessionId: 'owned-plan' });
      if (name === 'autowork.planning') return new Promise(resolve => { release = resolve; });
      throw new Error(name);
    });
    await mount({ params: { view: 'planning' } }); await press('Start planning'); await press('Confirm operation'); await flush();
    await press('Read planning preview');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'planning' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'planning' } });
    await act(async () => release({ value: { revision: 'old-preview', valid: true, files: ['Task.md'], diff: 'old', errors: [] } }));
    await flush();
    expect(button('Apply preview')).toBeUndefined();
  });
  it('stores a late commit response only on the original host and instance', async () => {
    let release!: (value: unknown) => void;
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit' ? new Promise(resolve => { release = resolve; }) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Pause'); await press('Confirm operation');
    env.hosts.push({ serverId: 'b', label: 'B', status: 'online' });
    await rerender({ host: { id: 'b', label: 'B' }, params: { view: 'planning' } });
    await act(async () => release(operation({ kind: 'control', status: 'succeeded', sessionId: null })));
    await flush();
    expect(text()).not.toContain('operation-1');
    expect(query.getQueryData(['autowork', 'a', 'generation-1', 'accepted-operations'])).toEqual([expect.objectContaining({ id: 'operation-1' })]);
    expect(query.getQueryData(['autowork', 'b', 'generation-1', 'accepted-operations'])).toEqual([]);
  });
  it('consumes confirmation synchronously against double taps', async () => {
    await mount({ params: { view: 'runner' } }); await press('Pause');
    const confirm = button('Confirm operation')!.props.onPress;
    await act(async () => { confirm(); confirm(); }); await flush();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('does not commit an expired ticket', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.prepare' ? Promise.resolve({ ticket: 'expired', expiresAt: Date.now() - 1, summary: 'Expired', pushAllowed: false }) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Pause'); await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('polls owned planning only on its active view and confirms steering/cancel mutations', async () => {
    let prepared: import('../shared/contracts').Action | undefined;
    env.invoke.mockImplementation(async (name, data) => {
      if (name === 'autowork.fleet') return fleet();
      if (name === 'autowork.prepare') { prepared = data.action; return { ticket: 't', expiresAt: Date.now() + 60000, summary: prepared!.kind, pushAllowed: false }; }
      if (name === 'autowork.commit') return prepared?.kind === 'plan-steer' ? operation({ id: 'steer-op', kind: 'plan-steer', status: 'succeeded', sessionId: 'owned-plan' }) : operation({ sessionId: 'owned-plan' });
      if (name === 'autowork.operation') return prepared?.kind === 'plan-steer' ? new Promise(() => {}) : operation({ sessionId: 'owned-plan', progress: 'Controller evidence' });
      throw new Error(name);
    });
    await mount({ params: { view: 'planning' } }); await press('Start planning'); await press('Confirm operation'); await flush();
    const key = ['autowork', 'a', 'generation-1', 'operation'];
    const count = () => env.invoke.mock.calls.filter(([name]) => name === 'autowork.operation').length;
    await press('Runner'); const before = count();
    await act(async () => { await query.invalidateQueries({ queryKey: key }); }); await flush();
    expect(count()).toBe(before);
    await press('Planning'); await flush(); expect(count()).toBeGreaterThan(before);
    await input('Planning message', 'Clarify acceptance'); await press('Steer planning');
    expect(prepared).toEqual({ kind: 'plan-steer', repoId: 'repo', operationId: 'operation-1', message: 'Clarify acceptance' });
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    await press('Confirm operation'); await flush();
    expect(button('Send planning message')!.props.disabled).toBe(true);
    await press('Cancel planning');
    expect(prepared).toEqual({ kind: 'plan-cancel', repoId: 'repo', operationId: 'operation-1' });
    await act(async () => { env.state = 'background'; env.listener?.('background'); });
    const paused = count(); await act(async () => { await query.invalidateQueries({ queryKey: key }); }); await flush();
    expect(count()).toBe(paused);
  });
  it('backs observation errors off exponentially and resets after a successful read', async () => {
    await mount();
    const q = query.getQueryCache().find({ queryKey: ['autowork', 'a', 'fleet'], exact: true })!;
    const delay = () => (q.options as unknown as { refetchInterval: (query: unknown) => number }).refetchInterval(q);
    expect(delay()).toBe(20000);
    env.invoke.mockRejectedValue(new Error('offline transport'));
    for (const expected of [40000, 80000, 120000]) {
      await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'fleet'], exact: true }); }); await flush();
      expect(delay()).toBe(expected);
    }
    env.invoke.mockImplementation(async () => fleet());
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'fleet'], exact: true }); }); await flush();
    expect(delay()).toBe(20000);
  });
  it('separates configured runner model/toolset from unavailable observed runtime evidence', async () => {
    const value = fleet(); value.repos[0]!.runner!.model = 'configured-model'; value.repos[0]!.runner!.toolset = '/configured/source';
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Configured model\nconfigured-model');
    expect(text()).toContain('Configured toolset\n/configured/source');
    expect(text()).toContain('Observed runtime: unknown');
    expect(text()).not.toContain('Observed runtime: configured-model');
  });
  it('updates a navigated planning objective as draft text only, without starting', async () => {
    await mount({ params: { view: 'planning', objective: 'First' } });
    await rerender({ params: { view: 'planning', objective: 'Changed objective' } });
    const field = root.root.find(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Objective');
    expect(field.props.value).toBe('Changed objective');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.prepare' || name === 'autowork.commit')).toHaveLength(0);
  });
  // The repository owns its own failure: a detached notice above the picker named no path
  // and repeated what the row and the runner banner already said.
  it('carries a broken repository on its row instead of a detached notice', async () => {
    const value = fleet();
    value.repos[0]!.error = 'Repository unavailable or identity mismatch; actions disabled';
    value.repos[0]!.identity = ''; value.repos[0]!.path = '/missing';
    value.warnings = ['Repository Repository is unavailable'];
    env.invoke.mockResolvedValue(value);
    await mount();
    expect(text()).not.toContain('Repository Repository is unavailable');
    expect(text()).toContain('/missing');
    await press('Connection details');
    expect(text()).toContain('Daemon warnings: Repository Repository is unavailable');
    await press('Open Repository');
    expect(text()).toContain('/missing');
    expect(text()).toContain("restore the path or remove it from the daemon policy's repositories list");
  });
  it('disables actions on repository identity errors', async () => {
    const value = fleet(); value.repos[0]!.error = 'Repository unavailable'; value.repos[0]!.identity = '';
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(button('Pause')!.props.disabled).toBe(true);
  });
  it('renders manual versus verified closure explicitly on task rows', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [
      { ...task, status: 'done', closure: { label: 'closed', provenance: 'manual', verified: false }, display: manualDisplay },
      { ...task, id: 'T-2', status: 'done', closure: { label: 'closed', provenance: 'evidence', verified: true }, display: { ...manualDisplay, state: 'Verified', why: 'Verified closure detail', closure: { label: 'Verified', detail: 'Verified closure detail', provenance: 'coordinator_verified', verified: true } } },
    ] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } }); await press('Show completed');
    expect(text()).toContain('Manual closure detail');
    expect(text()).toContain('Verified closure detail');
  });
  it('filters completed and canonically held tasks without requiring a live worker lane', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [
      task, { ...task, id: 'T-DONE', title: 'Finished task', status: 'done', display: { ...task.display, state: 'done' } },
      { ...task, id: 'T-HELD', title: 'Held task', blocked_by: 'HELD', display: { ...task.display, state: 'Blocker', blocker: 'held', why: 'held' } },
    ] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } }); await press('Filters');
    await input('Filter runtime', 'done'); expect(text()).toContain('Finished task'); expect(text()).not.toContain('Owner task');
    await input('Filter runtime', 'held'); expect(text()).toContain('Held task'); expect(text()).not.toContain('Finished task');
  });
  it('keeps uncertain planning cancellable and explicitly reconcilable without starting another turn', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit'
      ? Promise.resolve(operation({ sessionId: 'owned-session', status: 'uncertain' }))
      : name === 'autowork.operation' ? Promise.resolve(operation({ sessionId: 'owned-session', status: 'running' })) : initial(name, data));
    await mount({ params: { view: 'planning' } });
    await press('Start planning'); await press('Confirm operation');
    expect(button('Cancel planning')).toBeTruthy();
    expect(button('Send planning message')!.props.disabled).toBe(true);
    await press('Reconcile operation');
    // Reconciliation may resume ordinary status polling; neither observation may replay a commit.
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.operation').length).toBeGreaterThanOrEqual(1);
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('groups task rows by canonical goal', async () => {
    await mount({ params: { view: 'tasks' } });
    const headings = root.root.findAll(node => String(node.type) === 'Text' && node.props.accessibilityRole === 'header');
    expect(headings.some(node => node.children.join('') === 'Goal · goal')).toBe(true);
  });
  it('distinguishes unmatched filters from an empty queue and lets the user reset filters', async () => {
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('Showing 1–1 of 1 matching tasks · 1 total');
    await press('Filters'); await input('Filter task', 'not-present');
    expect(text()).toContain('No tasks match these filters.');
    expect(text()).not.toContain('No tasks observed.');
    expect(text()).not.toContain('Owner task');
    await press('Clear task filters');
    expect(text()).toContain('Owner task');
    for (const key of ['task', 'goal', 'runtime', 'section']) {
      expect(root.root.find(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === `Filter ${key}`).props.value).toBe('');
    }
  });
  it('bounds rendered task rows and applies filters before pagination', async () => {
    const initial = env.invoke.getMockImplementation()!;
    const tasks = Array.from({ length: 61 }, (_, index) => ({ ...task, id: `T-${index + 1}`, title: `Queue item ${index + 1}` }));
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    const rows = () => root.root.findAll(node => String(node.type) === 'Pressable' && /^Open task /.test(node.props.accessibilityLabel));
    expect(rows()).toHaveLength(25);
    expect(button('Previous task page')!.props.disabled).toBe(true);
    await press('Next task page');
    expect(text()).toContain('Showing 26–50 of 61 matching tasks · 61 total');
    expect(button('Open task T-1')).toBeUndefined();
    expect(button('Open task T-26')).toBeTruthy();
    await press('Next task page');
    expect(rows()).toHaveLength(11);
    expect(button('Next task page')!.props.disabled).toBe(true);
    await press('Filters'); await input('Filter task', 'Queue item 61');
    expect(text()).toContain('Showing 1–1 of 1 matching tasks · 61 total');
    expect(button('Open task T-61')).toBeTruthy();
    await press('Clear task filters');
    expect(button('Open task T-1')).toBeTruthy();
    expect(rows()).toHaveLength(25);
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.tasks')).toHaveLength(1);
  });
  it('clamps task pagination when a refreshed queue shrinks', async () => {
    const initial = env.invoke.getMockImplementation()!;
    let tasks = Array.from({ length: 26 }, (_, index) => ({ ...task, id: `T-${index + 1}` }));
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    await press('Next task page');
    tasks = [tasks[0]!];
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'generation-1', 'repo', 'tasks'], exact: true }); });
    await flush();
    expect(text()).toContain('Showing 1–1 of 1 matching tasks · 1 total');
    expect(button('Open task T-1')).toBeTruthy();
    expect(button('Next task page')).toBeUndefined();
  });
  it('repeats goal headings at page boundaries and supports backward navigation', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks:
      Array.from({ length: 26 }, (_, index) => ({ ...task, id: `T-${index + 1}` })) }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    await press('Next task page');
    expect(text()).toContain('Goal · goal');
    expect(button('Open task T-26')).toBeTruthy();
    await press('Previous task page');
    expect(button('Open task T-1')).toBeTruthy();
    expect(button('Open task T-26')).toBeUndefined();
  });
  it('distinguishes an empty queue from a nonempty queue without blocked tasks', async () => {
    const initial = env.invoke.getMockImplementation()!;
    let tasks: typeof task[] = [];
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('No tasks observed.');
    tasks = [{ ...task, id: 'T-OTHER' }];
    await press('Blockers');
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'generation-1', 'repo', 'tasks'], exact: true }); });
    await flush();
    expect(text()).toContain('No blocked tasks observed.');
    expect(button('Open task T-OTHER')).toBeUndefined();
    expect(text()).toContain('of 0 matching tasks · 1 total');
  });
  it('does not describe failed task reads as an empty queue', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.reject(new Error('Task read unavailable')) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('Task read unavailable');
    expect(text()).not.toContain('No tasks observed.');
    expect(text()).not.toContain('No tasks match these filters.');
  });
  it('shows read-only policy and navigation actions when the host grants nothing', async () => {
    const value = fleet(); value.permissions = { controls: [], planning: false, decisions: false, tasks: false, commit: false, maintenance: [] };
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Read-only');
    expect(text()).toContain('Runner controls are read-only by operator policy');
    expect(button('Tasks')).toBeTruthy();
    expect(button('Pause')).toBeUndefined();
  });
  it('renders the main-check summary rather than a raw object in the runner view', async () => {
    const value = fleet(); value.repos[0]!.runner!.main_check = { state: 'green', result_class: 'PASS', checked_rev: '7c9960e54149a2e7b5a12cbc565167f0', main_head: '7c9960e54149a2e7b5a12cbc565167f0', finished: 1793507113.748 };
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Main check: green · PASS');
    expect(text()).not.toContain('{"state"');
  });
  it('uses minimum 48px accessible native action targets and theme tokens', async () => {
    await mount({ params: { view: 'runner' } });
    for (const node of root.root.findAll(node => String(node.type) === 'Pressable')) {
      expect(node.props.style.minHeight).toBeGreaterThanOrEqual(48);
      expect(node.props.style.minWidth).toBeGreaterThanOrEqual(48);
      expect(node.props.accessibilityRole).toBe('button'); expect(node.props.accessibilityLabel).toBeTruthy();
      expect([props.theme.colors.surface2, props.theme.colors.accent]).toContain(node.props.style.backgroundColor);
    }
  });
  it('pauses queries in AppState background and revokes pending confirmation', async () => {
    await mount(); await press('Runner'); await press('Pause');
    await act(async () => { env.state = 'background'; env.listener?.('background'); });
    expect(button('Confirm operation')).toBeUndefined(); expect(text()).toContain('paused');
    const calls = env.invoke.mock.calls.length;
    await query.invalidateQueries(); await flush(); expect(env.invoke).toHaveBeenCalledTimes(calls);
  });
});

describe('management surface', () => {
  const grantAll = () => { const value = fleet(); value.permissions = { controls: ['start', 'pause', 'resume', 'stop', 'restart', 'remove', 'update'], planning: true, decisions: true, tasks: true, commit: true, maintenance: ['model', 'clear-held', 'attention'] }; return value; };
  const capture = (value = fleet()) => {
    const captured: { action?: unknown } = {}; const base = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation(async (name, input) => {
      if (name === 'autowork.fleet') return value;
      if (name === 'autowork.prepare') { captured.action = (input as { action: unknown }).action; return { ticket: 't', expiresAt: Date.now() + 60000, summary: 'Prepared', pushAllowed: false }; }
      return base(name, input);
    });
    return captured;
  };
  it('offers every granted control and maintenance action and sends restart flags, model and attention exactly', async () => {
    const captured = capture(grantAll());
    await mount({ params: { view: 'runner' } });
    for (const title of ['Start', 'Pause', 'Resume', 'Stop', 'Restart', 'Remove service', 'Update all runners']) expect(button(title), title).toBeTruthy();
    await press('Interrupt merges now');
    expect(button('Interrupt merges now')!.props.style.backgroundColor).toBe(props.theme.colors.statusDanger);
    expect(text()).toContain('Interrupting merges now can leave an integration incomplete.');
    await press('Restart');
    expect(captured.action).toEqual({ kind: 'control', repoId: 'repo', action: 'restart', stopWorkers: true, now: true });
    await press('Service model'); await press('Choose model'); await press('provider/model-a'); await press('Change model');
    expect(captured.action).toEqual({ kind: 'model', repoId: 'repo', model: 'provider/model-a' });
    await press('Owner attention'); await input('Minutes', '15'); await input('Attention note', '-n'); await press('Record attention');
    expect(captured.action).toEqual({ kind: 'attention', repoId: 'repo', minutes: 15, note: '-n' });
    await press('Held commits'); await input('Held task IDs (empty clears all)', 'T-2 T-3'); await press('Clear held commits');
    expect(captured.action).toEqual({ kind: 'clear-held', repoId: 'repo', tasks: ['T-2', 'T-3'] });
    await press('Diagnostics'); expect(text()).toContain('Runner:     not running');
  });
  it('keeps an unchanged protected snapshot committable after a long diff review', async () => {
    capture(grantAll());
    await mount({ params: { view: 'tasks' } });
    const key = ['autowork', 'a', 'generation-1', 'repo', 'store', 'pending'];
    const preview = query.getQueryData(key);
    expect(preview).toBeTruthy();
    await act(async () => { query.setQueryData(key, preview, { updatedAt: Date.now() - 11000 }); });
    await input('Commit message', 'carefully reviewed');
    expect(button('Commit task edits')!.props.disabled).toBe(false);
  });
  it('refuses unprotected commits when an older backend omits the pending snapshot', async () => {
    capture(grantAll()); const base = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation(async (name, input) => {
      if (name === 'autowork.store' && (input as { view: string }).view === 'pending') {
        return { value: { files: ['tasks/items/T-1.md'], diff: '+ older backend', commit: null, dry_run: true }, capturedAt: Date.now() };
      }
      return base(name, input);
    });
    await mount({ params: { view: 'tasks' } });
    await input('Commit message', 'answer T-1');
    expect(button('Commit task edits')!.props.disabled).toBe(true);
    expect(text()).toContain('Update Autowork for exact pending-snapshot protection');
    expect(env.invoke.mock.calls.some(([name]) => name === 'autowork.prepare')).toBe(false);
  });
  it('authors an ungrouped task from four primary inputs and leaves dispatch bounds explicit', async () => {
    const captured = capture(grantAll());
    await mount({ params: { view: 'tasks' } });
    await press('New task');
    expect(text()).toContain('Without bounded Touches it stays a draft');
    expect(root.root.findAll(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Goal ID')).toHaveLength(0);
    await input('Title', 'Independent fix'); await input('Scope', 'Bounded change');
    await input('Acceptance (one per line)', 'Works'); await input('Checks (one per line)', 'true');
    await press('Add task');
    expect(captured.action).toEqual({ kind: 'task-add', repoId: 'repo', fields: {
      title: 'Independent fix', scope: 'Bounded change', acceptance: ['Works'], checks: ['true'],
      section: 'Next', kind: 'implementation', ownership: 'worker',
    } });
  });
  it('edits tasks against the working-tree revision, adds records and commits only task paths after showing the diff', async () => {
    const captured = capture(grantAll());
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('working-tree records'); expect(text()).toContain('1 file uncommitted');
    await press('Pending diff'); expect(text()).toContain('+ Owner decision');
    await input('Commit message', 'answer T-1'); await press('Commit task edits');
    expect(captured.action).toEqual({ kind: 'commit', repoId: 'repo', message: 'answer T-1', pendingRevision: 'a'.repeat(64) });
    await press('Open task T-1');
    expect(env.invoke.mock.calls.some(([name, value]) => name === 'autowork.task' && (value as { working: boolean }).working === true)).toBe(true);
    const field = (label: string) => root.root.findAll(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === label).length;
    await press('Edit task');
    expect(field('Closed by')).toBe(0); expect(field('Hold by')).toBe(0);
    await press('Close task'); await input('Closed by', 'owner'); await input('Closure reason', 'obsolete'); await press('Mark done');
    expect(captured.action).toEqual({ kind: 'task-done', repoId: 'repo', task: 'T-1', revision: 'working-rev', by: 'owner', reason: 'obsolete' });
    await press('Placement'); expect(field('Closed by')).toBe(0); await press('Move up');
    expect(captured.action).toEqual({ kind: 'task-move', repoId: 'repo', task: 'T-1', revision: 'working-rev', direction: 'up' });
    await press('New task'); await press('Task options'); await press('goal'); await input('Title', 'New work'); await input('Short (at most 80 characters)', 'New'); await input('Scope', 'Bounded fix'); await input('Acceptance (one per line)', 'a\nb'); await input('Checks (one per line)', 'true'); await press('Add task');
    expect(captured.action).toEqual({ kind: 'task-add', repoId: 'repo', fields: { goal: 'goal', title: 'New work', short: 'New', section: 'Next', kind: 'implementation', ownership: 'worker', scope: 'Bounded fix', acceptance: ['a', 'b'], checks: ['true'] } });
    await press('Show goals'); await press('Edit goal goal'); await input('Goal priority', '3'); await press('focus'); await press('Save goal');
    expect(captured.action).toEqual({ kind: 'goal', repoId: 'repo', goal: 'goal', revision: 'goal-v1', fields: { priority: 3, focus: true } });
  });
  it('hides task editing without the grant and never asks for working-tree records', async () => {
    const value = fleet(); value.permissions = { controls: [], planning: false, decisions: false, tasks: false, commit: false, maintenance: [] };
    capture(value);
    await mount({ params: { view: 'tasks' } });
    expect(text()).not.toContain('Pending task edits'); expect(button('New task')).toBeUndefined();
    await press('Open task T-1'); expect(button('Edit task')).toBeUndefined();
    expect(env.invoke.mock.calls.some(([name, input]) => name === 'autowork.task' && (input as { working: boolean }).working === true)).toBe(false);
  });
  it('starts planning with a mode, task scope and model when chosen', async () => {
    const captured = capture(grantAll());
    await mount({ params: { view: 'planning', objective: 'Improve docs' } });
    await press('Investigate'); await press('Planning options'); await input('Task scope (optional)', 'T-1'); await input('Planning model (optional)', 'provider/model-a'); await press('Start planning');
    expect(captured.action).toEqual({ kind: 'plan-start', repoId: 'repo', objective: 'Improve docs', mode: 'investigate', task: 'T-1', model: 'provider/model-a' });
  });
  it('renders the scorecard with missing-repository errors and the read-only settings grants', async () => {
    await mount({ params: { view: 'scorecard' } });
    expect(text()).toContain('gone: no metrics'); expect(text()).toContain('closed: 2 tasks [measured]');
    await act(async () => root.unmount());
    await act(async () => { root = create(<QueryClientProvider client={query}><SettingsScreen {...props} /></QueryClientProvider>); }); await flush();
    expect(text()).toContain('task edits: granted'); expect(text()).toContain('/policy.json'); expect(text()).toContain('default path, loaded');
    expect(root.root.findAll(node => String(node.type) === 'Pressable')).toHaveLength(1);
  });
  it('announces a settled operation with a toast and refreshes reads when the watch reports a change', async () => {
    let watches = 0;
    const base = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation(async (name, input) => {
      if (name === 'autowork.watch') { watches++; return { digest: `digest-${watches}`, changed: true, capturedAt: Date.now() }; }
      return base(name, input);
    });
    await mount({ params: { view: 'runner' } });
    const before = env.invoke.mock.calls.filter(([name]) => name === 'autowork.fleet').length;
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 1400)); }); await flush();
    expect(watches).toBeGreaterThanOrEqual(2);
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.fleet').length).toBeGreaterThan(before);
    await press('Pause'); await press('Confirm operation');
    expect(env.toast.show).toHaveBeenCalledWith('control: succeeded', expect.objectContaining({ variant: 'success' }));
  }, 10000);

  it('colours by meaning, not by substring: not running is neutral, only live states are green', () => {
    expect(stateTone('NOT RUNNING')).toBe('neutral'); expect(stateTone('stopped')).toBe('neutral'); expect(stateTone('done')).toBe('neutral');
    expect(stateTone('running')).toBe('success'); expect(stateTone('paused')).toBe('warning'); expect(stateTone('waiting')).toBe('warning');
    expect(stateTone('service failed')).toBe('danger'); expect(stateTone('dead')).toBe('danger');
  });
  it('humanises hashes, times, observations and owner Markdown', () => {
    expect(revisionParts('7c9960e54149a2e7b5a12cbc565167f0ea87a4d0+working')).toEqual({ hash: '7c9960e54149a2e7b5a12cbc565167f0ea87a4d0', short: '7c9960e5', suffix: '+working' });
    expect(relativeTime(Date.now() - 5 * 3600 * 1000)).toBe('5h ago');
    expect(relativeTime(1793671362.96, 1793671362960 + 90000)).toBe('2m ago');
    expect(markdownSegments('Keep **WEB-ALL** per [final reconciliation](docs/r.md).')).toEqual([{ text: 'Keep ' }, { text: 'WEB-ALL', bold: true }, { text: ' per ' }, { text: 'final reconciliation', link: 'docs/r.md' }, { text: '.' }]);
    expect(headline('Which scope applies? The rest is **detail** that goes on.')).toBe('Which scope applies?');
    expect(headline('Goal WEB-ALL remains unmet at Plan round 2 of 2. **Question:** Should WEB-ALL continue? No successor is saved.')).toBe('Should WEB-ALL continue?');
    expect(observationRows({ runner_alive: false, health_written_at: Date.now() / 1000 - 60, task_state: 'unknown' })).toEqual([['Runner alive', 'no'], ['Health written at', '1m ago']]);
  });
  it('leads the fleet with one banner, says a host-wide blocker once and sorts the urgent repository first', async () => {
    const value = fleet(); const base = value.repos[0]!;
    value.repos = [
      { ...base, id: 'quiet', label: 'Quiet', runner: { ...base.runner!, state: 'not running', display: { ...base.runner!.display!, state: 'not running' }, decisions: 0, questions: [], blocker: 'Pi RPC incompatible' } },
      { ...base, id: 'urgent', label: 'Urgent', runner: { ...base.runner!, state: 'waiting', decisions: 2, blocker: 'Pi RPC incompatible' } },
    ];
    capture(value);
    await mount();
    expect(text()).toContain('2 decisions waiting');
    expect(text().split('Pi RPC incompatible')).toHaveLength(2);
    const opens = root.root.findAll(node => String(node.type) === 'Pressable' && /^Open (Quiet|Urgent)$/.test(node.props.accessibilityLabel)).map(node => node.props.accessibilityLabel);
    expect(opens).toEqual(['Open Urgent', 'Open Quiet']);
    const pill = (state: string) => root.root.find(node => String(node.type) === 'View' && node.props.accessibilityLabel === `status ${state}`).props.style.borderColor;
    expect(pill('not running')).toBe(props.theme.colors.foregroundMuted);
    expect(pill('waiting')).toBe(props.theme.colors.statusWarning);
    expect(text()).not.toContain('Transport');
    await press('Answer in Urgent');
    expect(text()).toContain('Decision needed · 1');
  });
  it('asks for the repository name before a destructive control and keeps danger out of the primary row', async () => {
    capture(grantAll());
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Danger zone');
    await press('Remove service');
    expect(button('Confirm operation')!.props.disabled).toBe(true);
    await input('Type the repository name to confirm', 'Repository');
    expect(button('Confirm operation')!.props.disabled).toBe(false);
    await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    await press('Pause');
    expect(button('Confirm operation')!.props.disabled).toBe(false);
    expect(root.root.findAll(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Type the repository name to confirm')).toHaveLength(0);
  });
  it('requires the all-runners phrase before the host-wide update', async () => {
    capture(grantAll());
    await mount({ params: { view: 'runner' } });
    await press('Update all runners');
    expect(button('Confirm operation')!.props.disabled).toBe(true);
    await input('Type all runners to update every runner', 'all runners');
    expect(button('Confirm operation')!.props.disabled).toBe(false);
    await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('puts the question and the answer above the fold and renders Markdown as words', async () => {
    const value = fleet(); value.repos[0]!.runner!.questions = [{ id: 'T-1', effort: 'small', unblocks: 3, needs: 'Keep **WEB-ALL** as one goal? See [final reconciliation](docs/r.md).\n\nLong evidence paragraph.', answer: '', kind: '' }];
    capture(value);
    await mount({ params: { view: 'blockers' } });
    expect(text()).toContain('Decision needed · 1'); expect(text()).toContain('Keep WEB-ALL as one goal?'); expect(text()).toContain('unblocks 3 tasks');
    expect(text()).not.toContain('**'); expect(text()).not.toContain('Existing answer');
    await press('Answer T-1');
    expect(button('Send answer')).toBeTruthy(); expect(text()).not.toContain('](docs/'); expect(text()).toContain('final reconciliation');
  });
  it('renders the CLI task map in the row and matching detail, without remapping raw status', async () => {
    const initial = env.invoke.getMockImplementation()!;
    const blocked = { ...task, id: 'T-BLOCK', title: 'Blocked open task', blocked_by: 'NEEDS_DECISION' };
    const supplied = { ...taskDisplay, state: 'Blocker · supplied by CLI', blocker: 'needs decision', why: 'CLI explanation' };
    const value = fleet();
    value.repos[0]!.runner!.display!.tasks[blocked.id] = supplied;
    let currentDetail = { ...detail, id: blocked.id };
    env.invoke.mockImplementation((name, data) => name === 'autowork.fleet' ? Promise.resolve(value) : name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [blocked] }) : name === 'autowork.task' ? Promise.resolve(currentDetail) : initial(name, data));
    await mount({ params: { view: 'blockers' } });
    expect(text()).toContain('Blocked open task');
    expect(text()).toContain('Blocked by needs decision');
    expect(root.root.find(node => String(node.type) === 'View' && node.props.accessibilityLabel === 'status Blocker · supplied by CLI')).toBeTruthy();
    expect(text()).not.toContain('NEEDS_DECISION');
    await press('Open task T-BLOCK');
    expect(root.root.findAll(node => String(node.type) === 'View' && node.props.accessibilityLabel === 'status Blocker · supplied by CLI')).toHaveLength(2);
    expect(text()).toContain('CLI explanation');
    expect(button('Send answer')).toBeUndefined();
    expect(text()).toContain('No owner question is recorded for this task');
    currentDetail = { ...currentDetail, record_revision: 'edited', display: { ...taskDisplay, state: 'Waiting · Edited record' } };
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'generation-1', 'repo', 'task'] }); }); await flush();
    expect(root.root.findAll(node => String(node.type) === 'View' && node.props.accessibilityLabel === 'status Waiting · Edited record')).toHaveLength(1);
  });
  it('keeps completed blocked work out of the blocked queue until completed is requested', async () => {
    const initial = env.invoke.getMockImplementation()!;
    const done = { ...task, id: 'T-DONE', title: 'Finished blocked task', status: 'done', blocked_by: 'DONE', closure: { label: 'closed', provenance: 'manual', verified: false }, display: manualDisplay };
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [task, done] }) : initial(name, data));
    await mount({ params: { view: 'blockers' } });
    expect(text()).not.toContain('Finished blocked task');
    expect(text()).not.toContain('blocked by DONE');
    await press('Show completed');
    expect(text()).toContain('Finished blocked task');
    expect(text()).toContain('Manual closure detail');
    expect(text()).not.toContain('blocked by DONE');
  });
  it('shows task titles and separates resolution guidance from saved answers', async () => {
    const value = fleet(); value.repos[0]!.runner!.questions[0]!.answer = 'Move the task to **Next** or defer it.';
    capture(value);
    await mount({ params: { view: 'blockers' } });
    expect(text()).toContain('Owner task');
    expect(text()).not.toContain('Existing answer');
    expect(text()).not.toContain('Move the task');
    await press('Answer T-1');
    expect(text()).not.toContain('existing answer');
    expect(text()).toContain('How to resolve');
    await press('How to resolve');
    expect(text()).toContain('Move the task to '); expect(text()).toContain('Next');
    expect(text()).not.toContain('**');
    expect(text()).toContain('does not grant live permission');
  });
  it('keeps a revision-bound answer usable while the owner types beyond the cache freshness window', async () => {
    await mount({ params: { view: 'blockers' } });
    await press('Answer T-1');
    const now = Date.now();
    const clock = vi.spyOn(Date, 'now').mockReturnValue(now + 16000);
    try {
      await act(async () => {
        query.setQueryData(['autowork', 'a', 'generation-1', 'repo', 'task', 'T-1', true], detail, { updatedAt: now });
        query.setQueryData(['autowork', 'a', 'generation-1', 'repo', 'tasks'], { revision: 'rev', tasks: [task] }, { updatedAt: now });
        query.setQueryData(['autowork', 'a', 'fleet'], { ...fleet(), capturedAt: now }, { updatedAt: now });
      });
      await flush(); await input('Owner answer', 'Keep it deferred');
      expect(button('Send answer')!.props.disabled).toBe(false);
      await press('Send answer');
      expect(env.invoke).toHaveBeenCalledWith('autowork.prepare', expect.objectContaining({ action: expect.objectContaining({ kind: 'decision', revision: 'working-rev', text: 'Keep it deferred' }) }));
    } finally { clock.mockRestore(); }
  });
  it('retries failed detail reads in place without losing the answer or dispatching it', async () => {
    const initial = env.invoke.getMockImplementation()!;
    let fail = false;
    env.invoke.mockImplementation((name, data) => name === 'autowork.task' && fail
      ? Promise.reject(new Error('Autowork request limit reached; refresh later')) : initial(name, data));
    await mount({ params: { view: 'blockers' } });
    await press('Answer T-1'); await input('Owner answer', 'Keep it deferred');
    fail = true;
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'generation-1', 'repo', 'task'] }); });
    await flush();
    expect(button('Send answer')!.props.disabled).toBe(true);
    expect(button('Retry task details')).toBeTruthy();
    expect(text()).toContain('Your draft is kept');
    fail = false; await press('Retry task details');
    expect(root.root.find(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Owner answer').props.value).toBe('Keep it deferred');
    expect(button('Send answer')!.props.disabled).toBe(false);
    expect(env.invoke.mock.calls.some(([name]) => name === 'autowork.prepare' || name === 'autowork.commit')).toBe(false);
  });
  it('turns a raw request-limit failure into a retryable cached-data message', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks'
      ? Promise.reject(new Error('Request failed: Autowork request limit reached; refresh later requestType=plugin.rpc.invoke.request code=handler_error'))
      : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('Autowork is busy. Retry the read.');
    expect(text()).not.toContain('requestType=');
    expect(text()).not.toContain('handler_error');
    expect(button('Retry')).toBeTruthy();
  });
  it('puts controls before explanatory status and explains each maintenance action', async () => {
    capture(grantAll());
    const value = fleet(); value.repos[0]!.runner!.blocker = 'Pi 1.5.0 is not qualified'; value.repos[0]!.runner!.stop_reason = 'Pi 1.5.0 is not qualified';
    capture(value);
    await mount({ params: { view: 'runner' } });
    expect(text().indexOf('Controls')).toBeLessThan(text().indexOf('Why it stopped'));
    expect(text()).toContain('Change the model and fallback; restarts the service.');
    expect(text()).toContain('Record attention minutes or a note in private runner state.');
    expect(text()).toContain('Clear technical holds and return commits to integration.');
  });
  it('hides completed work by default, counts the queue and keeps filters behind one button', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'abcdef0123456789+working', tasks: [task, { ...task, id: 'T-DONE', title: 'Finished task', status: 'done', closure: { label: 'closed', provenance: 'manual', verified: false }, display: manualDisplay }] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).not.toContain('Finished task');
    expect(text()).toContain('1 open task · 1 need decision · 0 blocked · 1 done');
    expect(text()).toContain('abcdef01 · working tree'); expect(text()).not.toContain('abcdef0123456789');
    expect(root.root.findAll(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Filter task')).toHaveLength(0);
    await press('Show completed'); expect(text()).toContain('Finished task'); expect(text()).toContain('Manual closure detail');
  });
  it('groups runner health into facts with relative times and says why it stopped once', async () => {
    const value = fleet(); const runner = value.repos[0]!.runner!;
    runner.state = 'not running'; runner.blocker = 'Pi 1.5.0 is not qualified'; runner.stop_reason = 'Pi 1.5.0 is not qualified';
    runner.observation = { runner_alive: false, health_written_at: Date.now() / 1000 - 5 * 3600, task_state: 'unknown' };
    capture(value);
    await mount({ params: { view: 'runner' } });
    expect(text()).toContain('Why it stopped');
    expect(text()).toContain('CLI next action');
    expect(text()).toContain('CLI question summary');
    expect(text().split('Pi 1.5.0 is not qualified')).toHaveLength(2);
    expect(text()).toContain('Runner alive\nno'); expect(text()).toContain('Health written at\n5h ago');
    expect(text()).not.toContain('health_written_at'); expect(text()).not.toContain('task_state');
    expect(root.root.find(node => String(node.type) === 'ScrollView' && node.props.contentContainerStyle).props.contentContainerStyle.paddingBottom).toBeGreaterThanOrEqual(96);
  });
});
