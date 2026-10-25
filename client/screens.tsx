import { useEffect, useRef, useState } from 'react';
import type { PluginAgentPanelProps, PluginScreenProps, PluginWorkspacePanelProps } from '@getpaseo/plugin/client';
import { useRpc, useWorkspace } from '@getpaseo/plugin/client';
import { ScrollView } from '@getpaseo/plugin/client/ui';
import { RefreshControl, View } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { logsRpc, operationRpc, planningRpc, taskRpc, tasksRpc, type Action, type Fleet, type Operation, type Repo, type Task } from '../shared/contracts';
import { canAnswer, closureLabel, display, knownDirectory, previewForApply, record, taskMatches, type TaskFilters } from './presentation';
import { operationsKey, readForHost, rememberOperation, useConfirmedAction, useHostState, useReadBackoff, type HostState } from './state';
import { Button, Card, Expand, Heading, Input, Label, Row, Theme } from './ui';

type ViewName = 'fleet' | 'runner' | 'tasks' | 'blockers' | 'planning';
const views: Array<[ViewName, string]> = [['fleet', 'Fleet'], ['runner', 'Runner'], ['tasks', 'Tasks'], ['blockers', 'Blockers'], ['planning', 'Planning']];
const validView = (view: string | undefined): ViewName => views.find(([name]) => name === view)?.[0] ?? 'fleet';

export function AutoworkScreen(props: PluginScreenProps) {
  return <Theme.Provider value={props.theme}>
    <HostScreen key={props.host.id} {...props} />
  </Theme.Provider>;
}
function HostScreen(props: PluginScreenProps) {
  const host = useHostState(props.host.id);
  const { fleet } = host;
  return <ScrollView style={{ flex: 1, backgroundColor: props.theme.colors.surface0 }} contentContainerStyle={{ padding: props.layout.compact ? 16 : 24, gap: 16, maxWidth: 1200, width: '100%', alignSelf: 'center' }} refreshControl={<RefreshControl refreshing={fleet.isFetching} enabled={host.enabled} onRefresh={host.refresh} tintColor={props.theme.colors.accent} />}>
    <Heading>Autowork · {props.host.label}</Heading>
    <Label muted>Host selection is owned by Paseo. This view never routes to another host.</Label>
    {!host.online ? <Label>Host offline or unavailable. Cached observations are not current authority.</Label> : null}
    {!host.foreground ? <Label>App backgrounded: polling paused.</Label> : null}
    <Row>
      <Button label="Refresh" disabled={!host.enabled || fleet.isFetching} onPress={host.refresh} />
      <Label muted>{fleet.isFetching ? 'Refreshing…' : fleet.data ? `${host.current ? 'Live' : 'Cached'} observation · ${new Date(fleet.data.capturedAt).toISOString()}` : host.enabled ? 'Loading fleet…' : 'No live observation'}</Label>
    </Row>
    {fleet.error ? <Label>Fleet unavailable: {fleet.error.message}. Automatic refresh uses bounded backoff.</Label> : null}
    {fleet.data ? <FleetContent key={fleet.data.instance} props={props} host={host} fleet={fleet.data} /> : null}
  </ScrollView>;
}

function FleetContent({ props, host, fleet }: { props: PluginScreenProps; host: HostState; fleet: Fleet }) {
  const [view, setView] = useState<ViewName>(validView(props.params.view));
  const [selectedId, selectId] = useState('');
  const queryClient = useQueryClient();
  const { data: operations } = useQuery<Operation[]>({ queryKey: operationsKey(props.host.id, fleet.instance), queryFn: async () => [], enabled: false, initialData: [], staleTime: Infinity, gcTime: 1800000 });
  const sessions = Object.fromEntries(operations.filter(operation => operation.sessionId).map(operation => [operation.repoId, operation.sessionId!]));
  const directory = props.params.directory;
  const repos = directory ? fleet.repos.filter(repo => knownDirectory(repo.path, directory)) : fleet.repos;
  const repo = repos.find(item => item.id === selectedId) ?? repos[0];
  const latestOperations = [...operations].reverse();
  const planningOperation = latestOperations.find(item => item.repoId === repo?.id && ['plan-start', 'plan-send'].includes(item.kind) && ['running', 'uncertain'].includes(item.status))
    ?? latestOperations.find(item => item.repoId === repo?.id && item.kind.startsWith('plan-'));
  const context = `${view}:${repo?.id ?? ''}:${repo?.revision ?? ''}`;
  const updateOperation = (operation: Operation) => {
    queryClient.setQueryData<Operation[]>(operationsKey(props.host.id, fleet.instance), existing => rememberOperation(existing, operation));
  };
  const mutation = useConfirmedAction(host, props.host.id, fleet.instance, context, updateOperation);
  const enabled = host.current && !mutation.busy && !repo?.error;
  const request = (action: Action) => { void mutation.request(action); };
  useEffect(() => { setView(validView(props.params.view)); }, [props.params.view]);
  return <>
    <Row>{views.map(([name, title]) => <Button key={name} label={title} selected={view === name} onPress={() => setView(name)} />)}</Row>
    <Label muted>Executable source release: {fleet.release} · Prepare API: {fleet.prepareApi} · Instance: {fleet.instance}</Label>
    {fleet.warnings.map((warning, index) => <Label key={index}>{warning}</Label>)}
    {directory ? <Label muted>Workspace directory: {directory} · known repositories only</Label> : null}
    {view === 'fleet' ? <>
      <Heading>{repos.length} repositories · {repos.reduce((sum, item) => sum + (item.runner?.running ?? 0), 0)} running lanes · {repos.reduce((sum, item) => sum + (item.runner?.decisions ?? 0), 0)} tasks needing decision</Heading>
      {repos.map(item => <Card key={item.id}>
        <Heading>{item.label}</Heading>
        <Label>{item.runner?.state ?? 'unknown'}</Label>
        <Label muted>{item.path}</Label>{item.error ? <Label>{item.error}</Label> : null}<Label>Transport: unknown · Delivery: unknown</Label>
        <Button label={`Open runner ${item.label}`} onPress={() => { selectId(item.id); setView('runner'); }} />
      </Card>)}
    </> : null}
    {!repos.length ? <Label>No known repository matches this directory. No arbitrary path RPC is sent.</Label> : null}
    {view !== 'fleet' && repo ? <>
      <Row>{repos.map(item => <Button key={item.id} label={`Repository ${item.label}`} selected={repo.id === item.id} onPress={() => selectId(item.id)} />)}</Row>
      <Heading>{repo.label}</Heading>
      <Label muted>Repository revision: {repo.revision}</Label>
      {repo.error ? <Label>{repo.error}</Label> : null}
      {view === 'runner' ? <RunnerView key={repo.id} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} /> : null}
      {view === 'tasks' || view === 'blockers' ? <TasksView key={`${repo.id}:${view}`} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} blockers={view === 'blockers'} /> : null}
      {view === 'planning' ? <PlanningView key={repo.id} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} sessionId={sessions[repo.id]} operation={planningOperation} objective={props.params.objective ?? ''} /> : null}
    </> : null}
    {mutation.message ? <Label>{mutation.message}</Label> : null}
    {mutation.confirmation ? <Card>
      <Heading>Confirm operation</Heading>
      <Label>{mutation.confirmation.summary}</Label>
      <Label>Effective push allowed: {String(mutation.confirmation.pushAllowed)} (unchanged)</Label>
      <Label muted>Expires: {new Date(mutation.confirmation.expiresAt).toISOString()}</Label>
      <Label>No automatic replay, Start or Apply. Confirmation is intent, not authorization.</Label>
      <Row>
        <Button label="Confirm operation" disabled={!enabled} onPress={() => { void mutation.confirm(); }} />
        <Button label="Dismiss confirmation" onPress={mutation.dismiss} />
      </Row>
    </Card> : null}
    {operations.map(operation => <OperationStatus key={operation.id} operation={operation} fleet={fleet} hostId={props.host.id} enabled={host.enabled && operation.repoId === repo?.id && (!operation.kind.startsWith('plan-') || view === 'planning')} onUpdate={updateOperation} />)}
  </>;
}

type RepoViewProps = { repo: Repo; fleet: Fleet; host: HostState; hostId: string; enabled: boolean; request: (action: Action) => void };
function RunnerView({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const runner = repo.runner;
  const [showLogs, setShowLogs] = useState(false);
  const logs = useRpc(logsRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'logs'], enabled: host.enabled && showLogs,
    queryFn: () => readForHost(host, () => logs({ instance: fleet.instance, repoId: repo.id })), staleTime: 15000, retry: false, refetchOnWindowFocus: false
  });
  if (!runner) return <Label>Runner unavailable; no status inferred.</Label>;
  return <Card>
    <Heading>{runner.state}</Heading>
    <Label>Service: {display(runner.service)} · Mode: {display(runner.mode)} · Gate: {display(runner.gate)}</Label>
    <Label>Configured model: {display(runner.model)} · Configured toolset: {display(runner.toolset)}</Label>
    <Label>Observed runtime: unknown · Runtime source release: unknown</Label>
    <Expand title="Runner evidence">
      <Label>Current job: {display(runner.job)}</Label>
      <Label>Main check: {display(runner.main_check)}</Label>
      <Label muted>Service liveness and configured source do not prove worker runtime identity.</Label>
    </Expand>
    <Label>Push allowed: {String(runner.push)} · Enabled: {String(runner.enabled)}</Label>
    <Label>Running: {runner.running} · Waiting: {runner.waiting} · Stopped: {runner.stopped} · Needs decision: {runner.decisions}</Label>
    <Label>Transport: unknown · Delivery: unknown</Label>
    <Label>Blocker: {display(runner.blocker)} · Stop reason: {display(runner.stop_reason)}</Label>
    {runner.lanes.map((lane, index) => <View key={index} style={{ gap: 4 }}>
      <Label mono>{lane.task} · {lane.phase} · attempt {lane.attempt}</Label>
      <Label>{lane.detail}</Label>
      <Label muted>{display(lane.activity)} · age {display(lane.activity_age)} · minutes {display(lane.minutes)}</Label>
    </View>)}
    <Row>{fleet.permissions.controls.map(action => <Button key={action} label={`Prepare ${action}`} disabled={!enabled} onPress={() => request({ kind: 'control', repoId: repo.id, action })} />)}</Row>
    {!fleet.permissions.controls.length ? <Label muted>Runner controls are read-only by operator policy.</Label> : null}
    <Button label="Runner logs" selected={showLogs} onPress={() => setShowLogs(!showLogs)} />
    {showLogs ? <>
      <Label muted>{query.isFetching ? 'Refreshing logs…' : `Cached log capture: ${query.data ? new Date(query.data.capturedAt).toISOString() : 'unknown'}`}</Label>
      <Label mono>{query.data?.text ?? query.error?.message ?? 'Loading…'}</Label>
    </> : null}
  </Card>;
}

function TasksView({ repo, fleet, host, hostId, enabled, request, blockers }: RepoViewProps & { blockers: boolean }) {
  const tasks = useRpc(tasksRpc);
  const backoff = useReadBackoff();
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'tasks'], enabled: host.enabled,
    queryFn: () => backoff.run(() => readForHost(host, () => tasks({ instance: fleet.instance, repoId: repo.id }))), staleTime: 15000, retry: false, refetchOnWindowFocus: false,
    refetchInterval: () => host.enabled ? backoff.delay(20000, 120000) : false
  });
  const [filters, setFilters] = useState<TaskFilters>({ task: '', goal: '', runtime: '', section: '' });
  const [selected, select] = useState('');
  const runner = repo.runner;
  const questions = runner?.questions ?? [];
  const visibleTasks = (query.data?.tasks ?? []).filter(task =>
    (!blockers || !!task.blocked_by || questions.some(question => question.id === task.id)) &&
    taskMatches(task, filters, [task.status, task.blocked_by ?? '', runner?.lanes.find(lane => lane.task === task.id)?.phase ?? ''].join(' ')))
    .sort((a, b) => (a.goal ?? '').localeCompare(b.goal ?? ''));
  return <>
    {blockers ? <Card>
      <Heading>Canonical owner questions</Heading>{questions.length ? questions.map(question => <View key={question.id} style={{ gap: 8 }}>
        <Label mono>{question.id} · {question.effort} · unblocks {question.unblocks}</Label>
        <Label>{question.needs}</Label>
        <Label muted>Existing answer: {display(question.answer)}</Label>
        <Button label={`Inspect owner question ${question.id}`} onPress={() => select(question.id)} />
      </View>) : <Label>No canonical owner question observed.</Label>}
      <Expand title="Technical holds and blocker evidence">
        <Label>Technical holds are not new owner questions.</Label>
        <Label>{display(runner?.held)}</Label>
        <Label>Roots: {display(runner?.roots)}</Label>
        <Label>Waiting groups: {display(runner?.waiting_groups)}</Label>
        <Label>Stopped groups: {display(runner?.stopped_groups)}</Label>
        <Label>Main check: {display(runner?.main_check)}</Label>
      </Expand>
    </Card> : null}
    <Card>
      <Heading>{blockers ? 'Blocked tasks' : 'Tasks'}</Heading>
      <Row>{(['task', 'goal', 'runtime', 'section'] as const).map(key => <View key={key} style={{ flexGrow: 1, minWidth: 140 }}>
        <Input label={`Filter ${key}`} value={filters[key]} onChange={value => setFilters(existing => ({ ...existing, [key]: value }))} />
      </View>)}</Row>
      <Label muted>{query.isFetching ? 'Refreshing tasks…' : `${host.enabled && !query.isStale && !query.isError ? 'Live' : 'Cached'} tasks · revision ${query.data?.revision ?? 'unknown'}`}</Label>
      {query.error ? <Label>{query.error.message}</Label> : null}
      {visibleTasks.map((task, index) => <View key={task.id} style={{ gap: 8 }}>
        {index === 0 || visibleTasks[index - 1]?.goal !== task.goal ? <Heading>Goal · {task.goal ?? 'unassigned'}</Heading> : null}
        <Card>
        <Label mono>{task.id} · {task.status} · {task.section ?? 'unknown section'}</Label>
        <Label>{task.title}</Label>
        <Label muted>Goal: {display(task.goal)} · Blocked by: {display(task.blocked_by)}</Label>
        <Label>Closure: {closureLabel(task.closure)}</Label>
        <Button label={`Open task ${task.id}`} onPress={() => select(selected === task.id ? '' : task.id)} />
      </Card></View>)}
      {!query.isFetching && !query.data?.tasks.length ? <Label>No tasks observed.</Label> : null}
    </Card>
    {selected ? <TaskView key={selected} task={query.data?.tasks.find(task => task.id === selected)} taskId={selected} repo={repo} fleet={fleet} host={host} hostId={hostId} enabled={enabled && !query.isStale && !query.isError} request={request} /> : null}
  </>;
}

function TaskView({ task, taskId, repo, fleet, host, hostId, enabled, request }: RepoViewProps & { task?: Task; taskId: string }) {
  const load = useRpc(taskRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'task', taskId], enabled: host.enabled,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, task: taskId, working: false })), staleTime: 10000, retry: false, refetchOnWindowFocus: false
  });
  const [answer, setAnswer] = useState('');
  const detail = query.data;
  const question = repo.runner?.questions.find(item => item.id === taskId);
  return <Card>
    <Heading>{taskId} · {detail?.title ?? 'Task detail'}</Heading>
    {query.error ? <Label>{query.error.message}</Label> : null}
    {detail ? <>
      <Label>{detail.status} · {display(detail.section)} · live permission: {display(detail.live)}</Label>
      <Label>Closure: {closureLabel(detail.closure)}</Label>
      <Expand title="Contract and evidence">
        <Label>Acceptance: {display(detail.acceptance)}</Label>
        <Label>Checks: {display(detail.checks)}</Label>
        <Label>Exclusions: {display(detail.exclusions)}</Label>
        <Label>Scope: {display(detail.scope)}</Label>
        <Label>Depends on: {display(detail.depends_on)} · Verified dependencies: {display(detail.verified_depends_on)}</Label>
        <Label>Touches: {display(detail.touches)} · Resources: {display(detail.resources)}</Label>
        <Label>Ownership: {detail.ownership} · Kind: {detail.kind}</Label>
        <Label>Missing fields: {display(detail.missing_fields)} · Draft: {String(detail.draft)}</Label>
        <Label mono>Contract hash: {detail.contract_hash} · Record revision: {detail.record_revision}</Label>
        <Label>{detail.notes}</Label>{['label', 'provenance', 'verified', 'evidence_valid', 'evidence', 'actor', 'timestamp', 'reason', 'waiver', 'qualification'].map(key => <Label key={key}>{key}: {display(detail.closure[key])}</Label>)}</Expand>
      {task && repo.runner && canAnswer(task, repo.runner, detail) ? <>
        <Heading>Owner question</Heading>
        <Label>{question?.needs}</Label>
        <Input label="Owner answer" value={answer} onChange={setAnswer} multiline />
        <Button label="Prepare owner answer" disabled={!enabled || query.isStale || !answer.trim() || !fleet.permissions.decisions} onPress={() => request({ kind: 'decision', repoId: repo.id, task: taskId, revision: detail.record_revision, text: answer })} />
      </> : <Label muted>No answer action: this is not a current canonical owner question for an open task.</Label>}
    </> : <Label>Loading task…</Label>}
  </Card>;
}

function PlanningView({ repo, fleet, host, hostId, enabled, request, sessionId, operation, objective }: RepoViewProps & { sessionId?: string; operation?: Operation; objective: string }) {
  const [text, setText] = useState(objective);
  useEffect(() => { if (!sessionId) setText(objective); }, [objective, sessionId]);
  const [view, setView] = useState<'preview' | 'history' | 'roadmap'>('preview');
  const [requested, setRequested] = useState(false);
  const load = useRpc(planningRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'planning', sessionId ?? '', view], enabled: host.enabled && !!sessionId && requested,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, sessionId: sessionId!, view })), staleTime: 0, retry: false, refetchOnWindowFocus: false, refetchOnMount: false, refetchOnReconnect: false
  });
  // Any accepted planning turn invalidates the previous preview, even before its new session ID arrives.
  useEffect(() => { setRequested(false); }, [operation?.id, sessionId]);
  const preview = view === 'preview' && requested && !query.isError && !query.isFetching ? previewForApply(query.data?.value) : null;
  const busy = operation?.status === 'running' || operation?.status === 'uncertain';
  const planEnabled = enabled && fleet.permissions.planning && !busy;
  const value = record(query.data?.value);
  return <Card>
    <Heading>Staged planning</Heading>
    <Label>Planning never starts a runner. Sessions are accepted only from this backend instance's operations.</Label>
    <Input label={sessionId ? 'Planning message' : 'Objective (empty discovers work)'} value={text} onChange={setText} multiline />
    {!sessionId ? <Button label="Prepare planning start" disabled={!planEnabled} onPress={() => request({ kind: 'plan-start', repoId: repo.id, objective: text })} /> : <>
      <Label mono>Owned session: {sessionId}</Label>
      <Button label="Prepare planning message" disabled={!planEnabled || !text.trim()} onPress={() => request({ kind: 'plan-send', repoId: repo.id, sessionId, message: text })} />
      <Row>{(['preview', 'history', 'roadmap'] as const).map(next => <Button key={next} label={`Read planning ${next}`} disabled={!host.enabled || busy} selected={view === next && requested} onPress={() => { setView(next); setRequested(true); if (next === view && requested) void query.refetch(); }} />)}</Row>
      {requested ? <>
        <Label muted>{query.isFetching ? 'Reading planning…' : 'Cached planning observation; Apply revalidates exact revision.'}</Label>{query.error ? <Label>{query.error.message}</Label> : null}<Expand title="Planning result">
          <Label mono>{view === 'preview' ? `Revision: ${display(value?.revision)}\nValid: ${display(value?.valid)}\nFiles: ${display(value?.files)}\nErrors: ${display(value?.errors)}\n${display(value?.diff)}` : display(query.data?.value)}</Label>
        </Expand>
      </> : null}
      {preview ? <>
        <Label mono>Preview revision: {preview.revision}</Label>
        <Button label="Prepare Apply exact preview" disabled={!planEnabled} onPress={() => request({ kind: 'plan-apply', repoId: repo.id, sessionId, revision: preview.revision })} />
      </> : <Label muted>Read a valid nonempty preview before Apply.</Label>}
    </>}
    {busy && operation?.sessionId && ['plan-start', 'plan-send'].includes(operation.kind) ? <>
      <Button label="Prepare planning cancel" disabled={!enabled || !fleet.permissions.planning} onPress={() => request({ kind: 'plan-cancel', repoId: repo.id, operationId: operation.id })} />
      <Button label="Prepare planning steer" disabled={!enabled || !fleet.permissions.planning || !text.trim()} onPress={() => request({ kind: 'plan-steer', repoId: repo.id, operationId: operation.id, message: text })} />
      <Label muted>Steering uses the existing controller interface; unsupported runtime capabilities are refused by the backend.</Label>
    </> : null}
    {!fleet.permissions.planning ? <Label muted>Planning is disabled by operator policy.</Label> : null}
  </Card>;
}

function OperationStatus({ operation, fleet, hostId, enabled, onUpdate }: { operation: Operation; fleet: Fleet; hostId: string; enabled: boolean; onUpdate: (operation: Operation) => void }) {
  const load = useRpc(operationRpc);
  const backoff = useReadBackoff();
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, 'operation', operation.id], enabled: enabled && operation.status === 'running',
    queryFn: () => backoff.run(() => load({ instance: fleet.instance, id: operation.id })), retry: false, staleTime: 0, refetchOnWindowFocus: false,
    refetchInterval: q => enabled && operation.status === 'running' && q.state.data?.status !== 'failed' && q.state.data?.status !== 'uncertain' && q.state.data?.status !== 'succeeded' && q.state.data?.status !== 'cancelled' ? backoff.delay(1500, 30000) : false
  });
  const update = useRef(onUpdate); update.current = onUpdate;
  useEffect(() => { if (query.data && query.data !== operation) update.current(query.data); }, [query.data, operation]);
  return <Card>
    <Heading>Operation · {operation.status}</Heading>
    <Label mono>{operation.id} · {operation.kind} · {operation.repoId}</Label>
    <Label>{operation.message}</Label>
    {operation.status === 'uncertain' ? <Button label="Reconcile operation" disabled={!enabled} onPress={() => { void query.refetch(); }} /> : null}
    <Label mono>{operation.progress}</Label>{operation.result !== undefined ? <Expand title="Operation result evidence">
      <Label mono>{display(operation.result)}</Label>
    </Expand> : null}{query.error ? <Label>Status unavailable; delivery unknown. No replay: {query.error.message}</Label> : null}{operation.status === 'uncertain' ? <Label>Outcome uncertain. Inspect canonical state before attempting another action.</Label> : null}</Card>;
}

export function WorkspacePanel(props: PluginWorkspacePanelProps) {
  const workspace = useWorkspace(props.workspaceId, workspace => ({ directory: workspace.directory }));
  if (!workspace?.directory.trim()) return <Theme.Provider value={props.theme}>
    <Label>Workspace directory unavailable; no fleet query issued.</Label>
  </Theme.Provider>;
  return <AutoworkScreen {...props} params={{ directory: workspace.directory }} />;
}
export function AgentPanel(props: PluginAgentPanelProps) {
  const workspace = useWorkspace(props.workspaceId, workspace => ({ directory: workspace.directory }));
  if (!workspace?.directory.trim()) return <Theme.Provider value={props.theme}>
    <Label>Workspace directory unavailable; no fleet query issued.</Label>
  </Theme.Provider>;
  return <AutoworkScreen {...props} params={{ directory: workspace.directory, view: 'tasks' }} />;
}
