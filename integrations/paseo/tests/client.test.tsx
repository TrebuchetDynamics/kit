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
  toast: { show: vi.fn(), error: vi.fn() },
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
  return { ScrollView: host('ScrollView'), TextInput: host('TextInput'), SidebarRow: host('SidebarRow'), useToast: () => env.toast };
});
vi.mock('@getpaseo/plugin/client', () => ({
  useHosts: () => env.hosts,
  useWorkspace: () => env.directory === null ? null : ({ directory: env.directory }),
  useRpc: (contract: { name: string }) => (input: unknown) => env.invoke(contract.name, input),
}));
import { AutoworkScreen, WorkspacePanel } from '../client/screens';
import { SettingsScreen } from '../client/settings';
import { closureLabel, canAnswer, mainCheckSummary, previewForApply, taskMatches } from '../client/presentation';

const fleet = (instance = 'generation-1') => fleetSchema.parse({ instance, capturedAt: Date.now(), release: 'configured-release', executable: '/bin/autowork', prepareApi: 4,
  permissions: { controls: ['pause'], planning: true, decisions: true, tasks: true, commit: true, maintenance: ['model', 'clear-held', 'attention'] }, policy: { path: '/policy.json', source: 'default' }, capabilities: { commands: ['ls', 'tasks', 'plan', 'logs', 'status', 'scorecard', 'models'], tasks: ['list', 'show', 'decide', 'goals', 'commit', 'validate', 'prepare', 'why'] }, warnings: [], repos: [{ id: 'repo', label: 'Repository', path: '/repo', identity: 'identity', revision: 'rev',
    runner: { name: 'runner', repo: '/repo', state: 'waiting', questions: [{ id: 'T-1', effort: 'small', unblocks: 1, needs: 'Choose the scope' }], held: [['T-2', 'technical hold']] } }] });
const task = taskSchema.parse({ id: 'T-1', title: 'Owner task', section: 'Needs decision', status: 'open', goal: 'goal', rank: 1, position: 1, blocked_by: null, closure: {} });
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
    if (name === 'autowork.store') return { value: input && (input as { view: string }).view === 'pending' ? { files: ['tasks/items/T-1.md'], diff: '+ Owner decision', commit: null, dry_run: true } : { ok: true }, capturedAt: Date.now() };
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
  it('distinguishes manual and verified closure, unknown evidence and technical holds', () => {
    expect(closureLabel({ label: 'closed', provenance: 'manual', verified: false })).toContain('manual');
    expect(closureLabel({ label: 'closed', verified: true })).toContain('verified');
    expect(closureLabel({})).toContain('unknown');
    expect(closureLabel({ label: 'Verified', provenance: 'coordinator_verified', evidence_valid: true })).toContain('· verified');
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
});

describe('native host-scoped surfaces', () => {
  it('renders canonical status, unknown transport and manual closure without inferring health', async () => {
    await mount();
    expect(text()).toContain('waiting'); expect(text()).toContain('Transport: unknown');
    await press('Tasks');
    expect(text()).toContain('Owner task'); expect(text()).toContain('Closure: unknown');
    await press('Open task T-1'); await press('Contract and evidence');
    expect(text()).toContain('Must preserve contract');
    expect(button('Prepare owner answer')).toBeTruthy();
  });
  it('prepares, requires explicit confirmation, consumes once and never auto-replays', async () => {
    await mount(); await press('Runner'); await press('Prepare pause');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
    expect(text()).toContain('Pause repository');
    await press('Confirm operation');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    expect(button('Confirm operation')).toBeUndefined();
  });
  it('does not query an offline/missing host or use another online host as fallback', async () => {
    env.hosts = [{ serverId: 'b', label: 'B', status: 'online' }];
    await mount(); expect(env.invoke).not.toHaveBeenCalled(); expect(text()).toContain('offline');
  });
  it('keys fleet by host and discards pending confirmations on host switch', async () => {
    await mount(); await press('Runner'); await press('Prepare pause');
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
    await press('Prepare planning start'); await press('Confirm operation');
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
    expect(button('Prepare pause')!.props.disabled).toBe(true);
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
    expect(button('Prepare owner answer')!.props.disabled).toBe(false);
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
    await mount({ params: { view: 'runner' } }); await press('Prepare pause');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'runner' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'runner' } });
    await act(async () => release({ ticket: 'late', expiresAt: Date.now() + 60000, summary: 'Late', pushAllowed: false }));
    expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('invalidates tickets and owned sessions on backend instance change', async () => {
    await mount({ params: { view: 'runner' } }); await press('Prepare pause');
    env.invoke.mockImplementation(async name => { if (name === 'autowork.fleet') return fleet('generation-2'); throw new Error(name); });
    await act(async () => { await query.invalidateQueries({ queryKey: ['autowork', 'a', 'fleet'], exact: true }); });
    await flush();
    expect(text()).toContain('generation-2'); expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('retains uncertainty after commit transport failure and does not retry on reconnect', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit' ? Promise.reject(new Error('Connection lost')) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Prepare pause'); await press('Confirm operation');
    expect(text()).toContain('Delivery unknown; not retried');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'runner' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'runner' } });
    expect(button('Confirm operation')).toBeUndefined();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('sends only the current owner record revision through confirmation', async () => {
    await mount({ params: { view: 'tasks' } }); await press('Open task T-1');
    await input('Owner answer', 'Literal answer; no command execution'); await press('Prepare owner answer');
    const prepared = env.invoke.mock.calls.find(([name]) => name === 'autowork.prepare')!;
    expect(prepared[1]).toEqual({ instance: 'generation-1', action: { kind: 'decision', repoId: 'repo', task: 'T-1', revision: 'working-rev', text: 'Literal answer; no command execution' } });
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(0);
  });
  it('renders technical holds without exposing an answer action for held tasks', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [{ ...task, id: 'T-2', title: 'Technical task', blocked_by: 'technical' }] }) : name === 'autowork.task' ? Promise.resolve({ ...detail, id: 'T-2' }) : initial(name, data));
    await mount({ params: { view: 'blockers' } }); await press('Technical holds and blocker evidence');
    expect(text()).toContain('technical hold');
    await press('Open task T-2');
    expect(button('Prepare owner answer')).toBeUndefined();
    expect(text()).toContain('not a current canonical owner question');
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
    await press('Prepare planning start');
    expect(prepared).toEqual({ kind: 'plan-start', repoId: 'repo', objective: '', mode: 'plan' });
    await press('Confirm operation'); await flush();
    expect(text()).toContain('Owned session: owned-plan');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.planning')).toHaveLength(0);
    expect(button('Prepare Apply exact preview')).toBeUndefined();
    await press('Read planning preview'); await press('Planning result');
    expect(text()).toContain('+ acceptance');
    await press('Prepare Apply exact preview');
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
    await mount({ params: { view: 'planning' } }); await press('Prepare planning start'); await press('Confirm operation'); await flush();
    await press('Read planning preview');
    env.hosts[0]!.status = 'offline'; await rerender({ params: { view: 'planning' } });
    env.hosts[0]!.status = 'online'; await rerender({ params: { view: 'planning' } });
    await act(async () => release({ value: { revision: 'old-preview', valid: true, files: ['Task.md'], diff: 'old', errors: [] } }));
    await flush();
    expect(button('Prepare Apply exact preview')).toBeUndefined();
  });
  it('stores a late commit response only on the original host and instance', async () => {
    let release!: (value: unknown) => void;
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit' ? new Promise(resolve => { release = resolve; }) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Prepare pause'); await press('Confirm operation');
    env.hosts.push({ serverId: 'b', label: 'B', status: 'online' });
    await rerender({ host: { id: 'b', label: 'B' }, params: { view: 'planning' } });
    await act(async () => release(operation({ kind: 'control', status: 'succeeded', sessionId: null })));
    await flush();
    expect(text()).not.toContain('operation-1');
    expect(query.getQueryData(['autowork', 'a', 'generation-1', 'accepted-operations'])).toEqual([expect.objectContaining({ id: 'operation-1' })]);
    expect(query.getQueryData(['autowork', 'b', 'generation-1', 'accepted-operations'])).toEqual([]);
  });
  it('consumes confirmation synchronously against double taps', async () => {
    await mount({ params: { view: 'runner' } }); await press('Prepare pause');
    const confirm = button('Confirm operation')!.props.onPress;
    await act(async () => { confirm(); confirm(); }); await flush();
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
  });
  it('does not commit an expired ticket', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.prepare' ? Promise.resolve({ ticket: 'expired', expiresAt: Date.now() - 1, summary: 'Expired', pushAllowed: false }) : initial(name, data));
    await mount({ params: { view: 'runner' } }); await press('Prepare pause'); await press('Confirm operation');
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
    await mount({ params: { view: 'planning' } }); await press('Prepare planning start'); await press('Confirm operation'); await flush();
    const key = ['autowork', 'a', 'generation-1', 'operation'];
    const count = () => env.invoke.mock.calls.filter(([name]) => name === 'autowork.operation').length;
    await press('Runner'); const before = count();
    await act(async () => { await query.invalidateQueries({ queryKey: key }); }); await flush();
    expect(count()).toBe(before);
    await press('Planning'); await flush(); expect(count()).toBeGreaterThan(before);
    await input('Planning message', 'Clarify acceptance'); await press('Prepare planning steer');
    expect(prepared).toEqual({ kind: 'plan-steer', repoId: 'repo', operationId: 'operation-1', message: 'Clarify acceptance' });
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.commit')).toHaveLength(1);
    await press('Confirm operation'); await flush();
    expect(button('Prepare planning message')!.props.disabled).toBe(true);
    await press('Prepare planning cancel');
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
    expect(text()).toContain('Configured model: configured-model');
    expect(text()).toContain('Configured toolset: /configured/source');
    expect(text()).toContain('Observed runtime: unknown');
    expect(text()).not.toContain('Observed runtime: configured-model');
  });
  it('updates a navigated planning objective as draft text only, without starting', async () => {
    await mount({ params: { view: 'planning', objective: 'First' } });
    await rerender({ params: { view: 'planning', objective: 'Changed objective' } });
    const field = root.root.find(node => String(node.type) === 'TextInput' && node.props.accessibilityLabel === 'Objective (empty discovers work)');
    expect(field.props.value).toBe('Changed objective');
    expect(env.invoke.mock.calls.filter(([name]) => name === 'autowork.prepare' || name === 'autowork.commit')).toHaveLength(0);
  });
  it('disables actions on repository identity errors', async () => {
    const value = fleet(); value.repos[0]!.error = 'Repository unavailable'; value.repos[0]!.identity = '';
    env.invoke.mockResolvedValue(value);
    await mount({ params: { view: 'runner' } });
    expect(button('Prepare pause')!.props.disabled).toBe(true);
  });
  it('renders manual versus verified closure explicitly on task rows', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [
      { ...task, status: 'done', closure: { label: 'closed', provenance: 'manual', verified: false } },
      { ...task, id: 'T-2', status: 'done', closure: { label: 'closed', provenance: 'evidence', verified: true } },
    ] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('Closure: closed · manual · not verified');
    expect(text()).toContain('Closure: closed · evidence · verified');
  });
  it('filters completed and canonically held tasks without requiring a live worker lane', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.tasks' ? Promise.resolve({ revision: 'rev', tasks: [
      task, { ...task, id: 'T-DONE', title: 'Finished task', status: 'done' },
      { ...task, id: 'T-HELD', title: 'Held task', blocked_by: 'HELD' },
    ] }) : initial(name, data));
    await mount({ params: { view: 'tasks' } });
    await input('Filter runtime', 'done'); expect(text()).toContain('Finished task'); expect(text()).not.toContain('Owner task');
    await input('Filter runtime', 'held'); expect(text()).toContain('Held task'); expect(text()).not.toContain('Finished task');
  });
  it('keeps uncertain planning cancellable and explicitly reconcilable without starting another turn', async () => {
    const initial = env.invoke.getMockImplementation()!;
    env.invoke.mockImplementation((name, data) => name === 'autowork.commit'
      ? Promise.resolve(operation({ sessionId: 'owned-session', status: 'uncertain' }))
      : name === 'autowork.operation' ? Promise.resolve(operation({ sessionId: 'owned-session', status: 'running' })) : initial(name, data));
    await mount({ params: { view: 'planning' } });
    await press('Prepare planning start'); await press('Confirm operation');
    expect(button('Prepare planning cancel')).toBeTruthy();
    expect(button('Prepare planning message')!.props.disabled).toBe(true);
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
    await input('Filter task', 'not-present');
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
    await input('Filter task', 'Queue item 61');
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
    expect(text()).toContain('read-only');
    expect(text()).toContain('Runner controls are read-only by operator policy');
    expect(button('Tasks')).toBeTruthy();
    expect(button('Prepare pause')).toBeUndefined();
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
    await mount(); await press('Runner'); await press('Prepare pause');
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
    for (const action of ['start', 'pause', 'resume', 'stop', 'restart', 'remove', 'update']) expect(button(`Prepare ${action}`), action).toBeTruthy();
    await press('Restart waits for merges, then pauses workers'); await press('Restart interrupts merges now'); await press('Prepare restart');
    expect(captured.action).toEqual({ kind: 'control', repoId: 'repo', action: 'restart', stopWorkers: true, now: true });
    await press('Service model'); await press('Load model list'); await press('provider/model-a'); await press('Prepare model change');
    expect(captured.action).toEqual({ kind: 'model', repoId: 'repo', model: 'provider/model-a' });
    await press('Owner attention'); await input('Minutes', '15'); await input('Attention note', '-n'); await press('Prepare attention record');
    expect(captured.action).toEqual({ kind: 'attention', repoId: 'repo', minutes: 15, note: '-n' });
    await press('Clear held commits'); await input('Held task IDs (empty clears all)', 'T-2 T-3'); await press('Prepare clear-held');
    expect(captured.action).toEqual({ kind: 'clear-held', repoId: 'repo', tasks: ['T-2', 'T-3'] });
    await press('Runner status'); expect(text()).toContain('Runner:     not running');
  });
  it('edits tasks against the working-tree revision, adds records and commits only task paths after showing the diff', async () => {
    const captured = capture(grantAll());
    await mount({ params: { view: 'tasks' } });
    expect(text()).toContain('Working-tree records'); expect(text()).toContain('1 file(s) uncommitted');
    await press('Pending diff'); expect(text()).toContain('+ Owner decision');
    await input('Commit message', 'answer T-1'); await press('Prepare task commit');
    expect(captured.action).toEqual({ kind: 'commit', repoId: 'repo', message: 'answer T-1' });
    await press('Open task T-1');
    expect(env.invoke.mock.calls.some(([name, value]) => name === 'autowork.task' && (value as { working: boolean }).working === true)).toBe(true);
    await press('Edit task'); await input('Closed by', 'owner'); await input('Closure reason', 'obsolete'); await press('Prepare task done');
    expect(captured.action).toEqual({ kind: 'task-done', repoId: 'repo', task: 'T-1', revision: 'working-rev', by: 'owner', reason: 'obsolete' });
    await press('Prepare move up');
    expect(captured.action).toEqual({ kind: 'task-move', repoId: 'repo', task: 'T-1', revision: 'working-rev', direction: 'up' });
    await press('New task'); await press('goal'); await input('Title', 'New work'); await input('Short (at most 80 characters)', 'New'); await input('Acceptance (one per line)', 'a\nb'); await press('Prepare task add');
    expect(captured.action).toEqual({ kind: 'task-add', repoId: 'repo', fields: { goal: 'goal', title: 'New work', short: 'New', section: 'Next', kind: 'implementation', ownership: 'worker', acceptance: ['a', 'b'] } });
    await press('Show goals'); await press('Edit goal goal'); await input('Goal priority', '3'); await press('focus'); await press('Prepare goal write');
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
    await press('Investigate'); await input('Task scope (optional)', 'T-1'); await input('Planning model (optional)', 'provider/model-a'); await press('Prepare planning start');
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
    await press('Prepare pause'); await press('Confirm operation');
    expect(env.toast.show).toHaveBeenCalledWith('control: succeeded', expect.objectContaining({ variant: 'success' }));
  }, 10000);
});
