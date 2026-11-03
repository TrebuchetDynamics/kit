import { useEffect, useRef, useState } from 'react';
import type { PluginAgentPanelProps, PluginScreenProps, PluginWorkspacePanelProps } from '@getpaseo/plugin/client';
import { useRpc, useWorkspace } from '@getpaseo/plugin/client';
import { ScrollView, useToast } from '@getpaseo/plugin/client/ui';
import { RefreshControl, View } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { goalsRpc, logsRpc, modelsRpc, operationRpc, planningRpc, scorecardRpc, statusRpc, storeRpc, taskRpc, tasksRpc, type ActionInput, type Fleet, type Goal, type Operation, type Repo, type Task, type TaskDetail } from '../shared/contracts';
import { canAnswer, closureLabel, display, human, jobSummary, knownDirectory, mainCheckSummary, previewForApply, record, taskMatches, type TaskFilters } from './presentation';
import { operationsKey, readForHost, rememberOperation, useConfirmedAction, useHostState, useReadBackoff, useWatch, type HostState } from './state';
import { Badge, Button, Caption, Card, Choice, Divider, Expand, Heading, Input, Label, Notice, Row, ScrollRow, Stack, Stat, Theme } from './ui';

type ViewName = 'fleet' | 'runner' | 'tasks' | 'blockers' | 'planning' | 'scorecard';
const views: Array<[ViewName, string]> = [['fleet', 'Fleet'], ['runner', 'Runner'], ['tasks', 'Tasks'], ['blockers', 'Blockers'], ['planning', 'Planning'], ['scorecard', 'Scorecard']];
const validView = (view: string | undefined): ViewName => views.find(([name]) => name === view)?.[0] ?? 'fleet';
const lines = (value: string) => value.split('\n').map(item => item.trim()).filter(Boolean);
const words = (value: string) => value.split(/[\s,]+/).map(item => item.trim()).filter(Boolean);

function tone(state: string): 'success' | 'warning' | 'danger' | 'neutral' {
  const value = state.toLowerCase();
  if (value.includes('run') || value.includes('active') || value === 'ready' || value === 'succeeded') return 'success';
  if (value.includes('wait') || value.includes('pause') || value.includes('stall') || value.includes('decision') || value === 'uncertain') return 'warning';
  if (value.includes('fail') || value.includes('error') || value.includes('not running') || value.includes('block') || value === 'dead') return 'danger';
  return 'neutral';
}

export function AutoworkScreen(props: PluginScreenProps) {
  return <Theme.Provider value={props.theme}>
    <HostScreen key={props.host.id} {...props} />
  </Theme.Provider>;
}

function HostScreen(props: PluginScreenProps) {
  const host = useHostState(props.host.id);
  const { fleet } = host;
  const digest = useWatch(host, props.host.id, fleet.data?.instance);
  const status = fleet.isFetching ? 'Refreshing…' : fleet.data ? `${host.current ? 'Live' : 'Cached'} observation · ${new Date(fleet.data.capturedAt).toISOString()}${digest ? ' · change watch active' : ''}` : host.enabled ? 'Loading fleet…' : 'No live observation';
  return <ScrollView style={{ flex: 1, backgroundColor: props.theme.colors.surface0 }} contentContainerStyle={{ padding: props.layout.compact ? 14 : 22, gap: 14, maxWidth: 1100, width: '100%', alignSelf: 'center' }} refreshControl={<RefreshControl refreshing={fleet.isFetching} enabled={host.enabled} onRefresh={host.refresh} tintColor={props.theme.colors.accent} />}>
    <Row>
      <View style={{ flexGrow: 1, gap: 2 }}>
        <Heading>Autowork</Heading>
        <Caption>{props.host.label} · host selection is owned by Paseo</Caption>
      </View>
      <Button label="Refresh" compact variant="primary" disabled={!host.enabled || fleet.isFetching} onPress={host.refresh} />
    </Row>
    <Row>
      <Badge label={host.online ? (host.foreground ? 'online' : 'backgrounded') : 'offline'} tone={host.online ? (host.foreground ? 'success' : 'warning') : 'danger'} />
      <Caption>{status}</Caption>
    </Row>
    {!host.online ? <Notice tone="warning"><Label>Host offline or unavailable. Cached observations are not current authority.</Label></Notice> : null}
    {!host.foreground ? <Notice tone="warning"><Label>App backgrounded: polling paused.</Label></Notice> : null}
    {fleet.error ? <Notice tone="danger"><Label>Fleet unavailable: {fleet.error.message}</Label><Caption>Automatic refresh uses bounded backoff.</Caption></Notice> : null}
    {fleet.data ? <FleetContent key={fleet.data.instance} props={props} host={host} fleet={fleet.data} /> : null}
  </ScrollView>;
}

function grantSummary(fleet: Fleet): string[] {
  const p = fleet.permissions;
  return [...(p.controls.length ? [`controls: ${p.controls.join(', ')}`] : []), ...(p.maintenance.length ? [`maintenance: ${p.maintenance.join(', ')}`] : []),
    ...(p.decisions ? ['owner answers'] : []), ...(p.tasks ? ['task edits'] : []), ...(p.commit ? ['task-store commits'] : []), ...(p.planning ? ['planning'] : [])];
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
  const request = (action: ActionInput) => { void mutation.request(action); };
  useEffect(() => { setView(validView(props.params.view)); }, [props.params.view]);
  const running = repos.reduce((sum, item) => sum + (item.runner?.running ?? 0), 0);
  const decisions = repos.reduce((sum, item) => sum + (item.runner?.decisions ?? 0), 0);
  const grants = grantSummary(fleet);
  const readOnly = !grants.length;
  const common = { fleet, host, hostId: props.host.id, enabled, request };
  return <>
    <ScrollRow>{views.map(([name, title]) => <Button key={name} label={title} compact selected={view === name} onPress={() => setView(name)} />)}</ScrollRow>
    <Row>
      <Stat value={repos.length} label="repositories" />
      <Stat value={running} label="running lanes" tone={running ? 'success' : 'neutral'} />
      <Stat value={decisions} label="need decision" tone={decisions ? 'warning' : 'neutral'} />
    </Row>
    <Row>
      <Badge label={readOnly ? 'read-only' : 'actions enabled'} tone={readOnly ? 'warning' : 'success'} />
      <Caption>{readOnly ? 'The daemon operator has not granted runner controls, planning, task edits or owner answers.' : `Granted: ${grants.join(' · ')}. Actions require an exact confirmation before dispatch.`}</Caption>
    </Row>
    <Caption>Release {fleet.release} · instance {fleet.instance}</Caption>
    {fleet.warnings.map((warning, index) => <Notice key={index} tone="warning"><Label>{warning}</Label></Notice>)}
    <Expand title="Connection details">
      <Label>Executable source release: {fleet.release}</Label>
      <Label>Executable: {fleet.executable}</Label>
      <Label>Prepare API: {fleet.prepareApi} · Instance: {fleet.instance}</Label>
      <Label>Policy: {fleet.policy.path ?? 'none'} ({fleet.policy.source})</Label>
      {directory ? <Caption>Workspace directory: {directory} · known repositories only</Caption> : null}
      <Caption>Runners, transport and delivery are observed from the selected host only. Grants are shown under Settings → Plugins → Autowork.</Caption>
    </Expand>
    {view !== 'fleet' && view !== 'scorecard' && repos.length ? <ScrollRow>{repos.map(item => <Button key={item.id} compact label={`Repository ${item.label}`} selected={repo?.id === item.id} onPress={() => selectId(item.id)} />)}</ScrollRow> : null}
    {view === 'fleet' ? <>
      {repos.map(item => <Card key={item.id} compact>
        <Row>
          <View style={{ flexGrow: 1, gap: 2 }}><Heading level={2}>{item.label}</Heading><Caption truncate>{item.path}</Caption></View>
          <Badge label={item.runner?.state ?? 'unknown'} tone={tone(item.runner?.state ?? '')} />
        </Row>
        {item.runner ? <Row>
          <Caption>{item.runner.running} running · {item.runner.waiting} waiting · {item.runner.stopped} stopped · {item.runner.decisions} decisions</Caption>
        </Row> : <Caption>No runner record observed.</Caption>}
        {item.runner?.blocker ? <Caption>Blocker: {item.runner.blocker}</Caption> : null}
        <Caption>Transport: unknown · Delivery: unknown</Caption>
        {item.error ? <Notice tone="danger"><Label>{item.error}</Label></Notice> : null}
        <Row>
          <Button label={`Open runner ${item.label}`} compact variant="primary" onPress={() => { selectId(item.id); setView('runner'); }} />
          <Button label={`Tasks ${item.label}`} compact onPress={() => { selectId(item.id); setView('tasks'); }} />
          <Button label={`Plan ${item.label}`} compact onPress={() => { selectId(item.id); setView('planning'); }} />
        </Row>
      </Card>)}
    </> : null}
    {view === 'scorecard' ? <ScorecardView fleet={fleet} host={host} hostId={props.host.id} /> : null}
    {!repos.length ? <Notice tone="warning"><Label>No known repository matches this directory.</Label><Caption>No arbitrary path RPC is sent.</Caption></Notice> : null}
    {view !== 'fleet' && view !== 'scorecard' && repo ? <>
      <Row>
        <View style={{ flexGrow: 1, gap: 2 }}><Heading level={2}>{repo.label}</Heading><Caption truncate>{repo.revision || 'revision unavailable'}</Caption></View>
        {repo.runner ? <Badge label={repo.runner.state} tone={tone(repo.runner.state)} /> : null}
      </Row>
      {repo.error ? <Notice tone="danger"><Label>{repo.error}</Label></Notice> : null}
      {view === 'runner' ? <RunnerView key={repo.id} repo={repo} {...common} onView={setView} /> : null}
      {view === 'tasks' || view === 'blockers' ? <TasksView key={`${repo.id}:${view}`} repo={repo} {...common} blockers={view === 'blockers'} /> : null}
      {view === 'planning' ? <PlanningView key={repo.id} repo={repo} {...common} sessionId={sessions[repo.id]} operation={planningOperation} objective={props.params.objective ?? ''} /> : null}
    </> : null}
    {mutation.message ? <Notice tone={mutation.confirmation ? 'neutral' : 'warning'}><Label>{mutation.message}</Label></Notice> : null}
    {mutation.confirmation ? <Card>
      <Heading level={2}>Confirm operation</Heading>
      <Label>{mutation.confirmation.summary}</Label>
      <Label muted>Effective push allowed: {String(mutation.confirmation.pushAllowed)} (unchanged)</Label>
      <Caption>Expires: {new Date(mutation.confirmation.expiresAt).toISOString()}</Caption>
      <Notice tone="warning"><Label>No automatic replay, Start or Apply. Confirmation is intent, not authorization.</Label></Notice>
      <Row>
        <Button label="Confirm operation" variant="primary" disabled={!enabled} onPress={() => { void mutation.confirm(); }} />
        <Button label="Dismiss confirmation" onPress={mutation.dismiss} />
      </Row>
    </Card> : null}
    {operations.map(operation => <OperationStatus key={operation.id} operation={operation} fleet={fleet} hostId={props.host.id} enabled={host.enabled && operation.repoId === repo?.id && (!operation.kind.startsWith('plan-') || view === 'planning')} onUpdate={updateOperation} />)}
  </>;
}

type RepoViewProps = { repo: Repo; fleet: Fleet; host: HostState; hostId: string; enabled: boolean; request: (action: ActionInput) => void; onView?: (view: ViewName) => void };

function useModels(host: HostState, hostId: string, fleet: Fleet, wanted: boolean) {
  const load = useRpc(modelsRpc);
  return useQuery({
    queryKey: ['autowork', hostId, fleet.instance, 'models'], enabled: host.enabled && wanted,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance })), staleTime: 600000, retry: false, refetchOnWindowFocus: false,
  });
}

function RunnerView({ repo, fleet, host, hostId, enabled, request, onView }: RepoViewProps) {
  const runner = repo.runner;
  const [showLogs, setShowLogs] = useState(false);
  const [follow, setFollow] = useState(false);
  const [logLines, setLogLines] = useState<'150' | '500' | '2000'>('150');
  const [showStatus, setShowStatus] = useState(false);
  const [stopWorkers, setStopWorkers] = useState(false);
  const [now, setNow] = useState(false);
  const [model, setModel] = useState('');
  const [fallback, setFallback] = useState('');
  const [wantModels, setWantModels] = useState(false);
  const [minutes, setMinutes] = useState('');
  const [attentionTask, setAttentionTask] = useState('');
  const [note, setNote] = useState('');
  const [heldTasks, setHeldTasks] = useState('');
  const logs = useRpc(logsRpc);
  const status = useRpc(statusRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'logs', logLines], enabled: host.enabled && showLogs,
    queryFn: () => readForHost(host, () => logs({ instance: fleet.instance, repoId: repo.id, lines: Number(logLines) })), staleTime: 4000, retry: false, refetchOnWindowFocus: false,
    refetchInterval: () => host.enabled && showLogs && follow ? 5000 : false,
  });
  const statusQuery = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'status'], enabled: host.enabled && showStatus,
    queryFn: () => readForHost(host, () => status({ instance: fleet.instance, repoId: repo.id })), staleTime: 10000, retry: false, refetchOnWindowFocus: false,
  });
  const models = useModels(host, hostId, fleet, wantModels);
  if (!runner) return <Notice tone="warning"><Label>Runner unavailable; no status inferred.</Label></Notice>;
  const controls = fleet.permissions.controls;
  const maintenance = fleet.permissions.maintenance;
  const minutesValue = Number(minutes);
  return <Stack gap={12}>
    <Card>
      <Row>
        <View style={{ flexGrow: 1, gap: 3 }}><Heading level={2}>Runner actions</Heading><Caption>Reads are live; mutations need an exact confirmation.</Caption></View>
        <Badge label={runner.state} tone={tone(runner.state)} />
      </Row>
      <Row>
        <Button label="Tasks" compact onPress={() => onView?.('tasks')} />
        <Button label="Blockers" compact onPress={() => onView?.('blockers')} />
        <Button label="Planning" compact onPress={() => onView?.('planning')} />
        <Button label="Runner logs" compact selected={showLogs} onPress={() => setShowLogs(!showLogs)} />
        <Button label="Runner status" compact selected={showStatus} onPress={() => setShowStatus(!showStatus)} />
      </Row>
      <Divider />
      <Row>{controls.length ? controls.map(action => <Button key={action} label={`Prepare ${action}`} compact variant={action === 'remove' || action === 'update' ? 'danger' : 'primary'} disabled={!enabled}
        onPress={() => request(action === 'restart' ? { kind: 'control', repoId: repo.id, action, stopWorkers, now: stopWorkers && now } : { kind: 'control', repoId: repo.id, action })} />)
        : <Caption>Runner controls are read-only by operator policy.</Caption>}</Row>
      {controls.includes('restart') ? <Row>
        <Button label="Restart waits for merges, then pauses workers" compact selected={stopWorkers} onPress={() => setStopWorkers(!stopWorkers)} />
        <Button label="Restart interrupts merges now" compact selected={now} disabled={!stopWorkers} onPress={() => setNow(!now)} />
      </Row> : null}
      {!controls.length ? <Caption>Grant controls in the daemon-side policy file to enable start, pause, resume, stop, restart, remove or update.</Caption> : null}
      {controls.includes('update') ? <Caption>Update replaces the installed Autowork suite for every runner on this host; reload the plugin afterwards.</Caption> : null}
    </Card>
    {maintenance.length ? <Card>
      <Heading level={2}>Runner maintenance</Heading>
      {maintenance.includes('model') ? <Expand title="Service model">
        <Label>Current: {display(runner.model)} · fallback: {display(runner.fallback)}</Label>
        <Row><Button label="Load model list" compact selected={wantModels} onPress={() => setWantModels(true)} />{models.isFetching ? <Caption>Loading models…</Caption> : null}</Row>
        {models.error ? <Notice tone="danger"><Label>{models.error.message}</Label></Notice> : null}
        {models.data?.models.length ? <ScrollRow>{models.data.models.map(name => <Button key={name} label={name} compact selected={model === name} onPress={() => setModel(name)} />)}</ScrollRow> : null}
        <Input label="Model" value={model} onChange={setModel} />
        <Input label="Fallback model" value={fallback} onChange={setFallback} />
        <Button label="Prepare model change" variant="primary" disabled={!enabled || !model.trim()} onPress={() => request({ kind: 'model', repoId: repo.id, model: model.trim(), ...(fallback.trim() ? { fallback: fallback.trim() } : {}) })} />
        <Caption>Setting a model restarts the service through Autowork.</Caption>
      </Expand> : null}
      {maintenance.includes('attention') ? <Expand title="Owner attention">
        <Input label="Minutes" value={minutes} onChange={setMinutes} />
        <Input label="Attention task" value={attentionTask} onChange={setAttentionTask} />
        <Input label="Attention note" value={note} onChange={setNote} multiline />
        <Button label="Prepare attention record" variant="primary" disabled={!enabled || !(minutesValue > 0)} onPress={() => request({ kind: 'attention', repoId: repo.id, minutes: minutesValue, ...(attentionTask.trim() ? { task: attentionTask.trim() } : {}), ...(note.trim() ? { note: note.trim() } : {}) })} />
        <Caption>Recorded in private runner state, never committed.</Caption>
      </Expand> : null}
      {maintenance.includes('clear-held') ? <Expand title="Clear held commits">
        <Label>Held: {human(runner.held)}</Label>
        <Input label="Held task IDs (empty clears all)" value={heldTasks} onChange={setHeldTasks} />
        <Button label="Prepare clear-held" variant="primary" disabled={!enabled} onPress={() => request({ kind: 'clear-held', repoId: repo.id, tasks: words(heldTasks) })} />
        <Caption>Technical recovery: held commits return to integration; no owner decision is recorded.</Caption>
      </Expand> : null}
    </Card> : null}
    <Card>
      <Row>
        <Stat value={runner.running} label="running" tone={runner.running ? 'success' : 'neutral'} />
        <Stat value={runner.waiting} label="waiting" tone={runner.waiting ? 'warning' : 'neutral'} />
        <Stat value={runner.stopped} label="stopped" tone={runner.stopped ? 'danger' : 'neutral'} />
        <Stat value={runner.decisions} label="decisions" tone={runner.decisions ? 'warning' : 'neutral'} />
      </Row>
      <Label>Configured model: {display(runner.model)} · Configured toolset: {display(runner.toolset)}</Label>
      <Label>Observed runtime: unknown · Runtime source release: unknown</Label>
      <Label>Service: {display(runner.service)} · Mode: {display(runner.mode)} · Gate: {display(runner.gate)}</Label>
      <Label>Push allowed: {String(runner.push)} · Enabled: {String(runner.enabled)} · Max workers: {display(runner.max_workers)}</Label>
      <Label>Transport: unknown · Delivery: unknown</Label>
      <Divider />
      <Label>Main check: {mainCheckSummary(runner.main_check)}</Label>
      <Label>Current job: {jobSummary(runner.job)}</Label>
      {runner.observation ? <Label>Observation: {human(runner.observation)}</Label> : null}
      {runner.blocker ? <Notice tone="danger"><Label>Blocker: {runner.blocker}</Label></Notice> : null}
      {runner.stop_reason ? <Notice tone="warning"><Label>Stop reason: {runner.stop_reason}</Label></Notice> : null}
    </Card>
    <Card>
      <Expand title="Runner evidence">
        <Label>Held: {human(runner.held)}</Label>
        <Label>Roots: {human(runner.roots)}</Label>
        <Label>Waiting groups: {human(runner.waiting_groups)}</Label>
        <Label>Stopped groups: {human(runner.stopped_groups)}</Label>
        <Label>Main check evidence: {mainCheckSummary(runner.main_check)}</Label>
        <Label>Maintainer: {human(runner.maintainer)} · Prepare state: {human(runner.prepare_state)}</Label>
        <Caption>Service liveness and configured source do not prove worker runtime identity.</Caption>
      </Expand>
    </Card>
    {runner.lanes.length ? <Card>
      <Heading level={2}>Active lanes</Heading>
      {runner.lanes.map((lane, index) => <View key={index} style={{ gap: 3, paddingVertical: 6 }}>
        <Row><Badge label={lane.phase} tone="accent" /><Label mono>{lane.task}</Label></Row>
        <Label>{lane.detail}</Label>
        <Caption>{human(lane.activity)} · age {display(lane.activity_age)} · minutes {display(lane.minutes)} · attempt {lane.attempt}</Caption>
        {index < runner.lanes.length - 1 ? <Divider /> : null}
      </View>)}
    </Card> : null}
    {showStatus ? <Card>
      <Row><Heading level={2}>Runner status</Heading><Caption>{statusQuery.isFetching ? 'Reading…' : statusQuery.data ? new Date(statusQuery.data.capturedAt).toISOString() : 'Loading…'}</Caption></Row>
      {statusQuery.error ? <Notice tone="danger"><Label>{statusQuery.error.message}</Label></Notice> : null}
      <Label mono>{statusQuery.data?.text ?? 'Loading…'}</Label>
    </Card> : null}
    {showLogs ? <Card>
      <Row><Heading level={2}>Runner logs</Heading><Caption>{query.isFetching ? 'Refreshing…' : query.data ? new Date(query.data.capturedAt).toISOString() : 'Loading…'}</Caption></Row>
      <Row>
        <Choice label="Lines" value={logLines} options={['150', '500', '2000'] as const} onChange={setLogLines} />
        <Button label="Follow logs" compact selected={follow} onPress={() => setFollow(!follow)} />
      </Row>
      {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
      <Label mono>{query.data?.text ?? 'Loading…'}</Label>
    </Card> : null}
  </Stack>;
}

function useGoals(host: HostState, hostId: string, fleet: Fleet, repo: Repo, wanted: boolean) {
  const load = useRpc(goalsRpc);
  return useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'goals'], enabled: host.enabled && wanted,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id })), staleTime: 15000, retry: false, refetchOnWindowFocus: false,
  });
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
  const [page, setPage] = useState(0);
  const pageSize = 25;
  const runner = repo.runner;
  const questions = runner?.questions ?? [];
  const editing = fleet.permissions.tasks;
  const visibleTasks = (query.data?.tasks ?? []).filter(task =>
    (!blockers || !!task.blocked_by || questions.some(question => question.id === task.id)) &&
    taskMatches(task, filters, [task.status, task.blocked_by ?? '', runner?.lanes.find(lane => lane.task === task.id)?.phase ?? ''].join(' ')))
    .sort((a, b) => (a.goal ?? '').localeCompare(b.goal ?? ''));
  const lastPage = Math.max(0, Math.ceil(visibleTasks.length / pageSize) - 1);
  const currentPage = Math.min(page, lastPage);
  const pageStart = currentPage * pageSize;
  const pageTasks = visibleTasks.slice(pageStart, pageStart + pageSize);
  useEffect(() => { setPage(currentPage); }, [currentPage]);
  const changeFilter = (key: keyof TaskFilters, value: string) => { setFilters(existing => ({ ...existing, [key]: value })); setPage(0); };
  const hasFilters = Object.values(filters).some(value => value.trim());
  const common = { repo, fleet, host, hostId, enabled, request };
  return <Stack gap={12}>
    {blockers ? <Card>
      <Heading level={2}>Canonical owner questions</Heading>
      {questions.length ? questions.map(question => <View key={question.id} style={{ gap: 6, paddingVertical: 6 }}>
        <Row><Badge label={question.effort} tone="warning" /><Label mono>{question.id}</Label><Caption>unblocks {question.unblocks}</Caption></Row>
        <Label>{question.needs}</Label>
        <Caption>Existing answer: {display(question.answer)}</Caption>
        <Button label={`Inspect owner question ${question.id}`} compact onPress={() => select(question.id)} />
        <Divider />
      </View>) : <Caption>No canonical owner question observed.</Caption>}
      <Expand title="Technical holds and blocker evidence">
        <Label>Technical holds are not new owner questions.</Label>
        <Label>Held: {human(runner?.held)}</Label>
        <Label>Roots: {human(runner?.roots)}</Label>
        <Label>Waiting groups: {human(runner?.waiting_groups)}</Label>
        <Label>Stopped groups: {human(runner?.stopped_groups)}</Label>
        <Label>Main check: {mainCheckSummary(runner?.main_check)}</Label>
      </Expand>
    </Card> : null}
    {!blockers && (editing || fleet.permissions.commit) ? <PendingCard {...common} /> : null}
    <Card>
      <Row><Heading level={2}>{blockers ? 'Blocked tasks' : 'Task queue'}</Heading><Caption>{query.isFetching ? 'Refreshing…' : `${host.enabled && !query.isStale && !query.isError ? 'Live' : 'Cached'} · revision ${query.data?.revision ?? 'unknown'}`}</Caption></Row>
      {editing ? <Caption>Working-tree records: uncommitted edits are included until you commit them.</Caption> : null}
      <Row>{(['task', 'goal', 'runtime', 'section'] as const).map(key => <View key={key} style={{ flexGrow: 1, minWidth: 132 }}>
        <Input label={`Filter ${key}`} value={filters[key]} onChange={value => changeFilter(key, value)} />
      </View>)}</Row>
      {hasFilters ? <Button label="Clear task filters" compact onPress={() => { setFilters({ task: '', goal: '', runtime: '', section: '' }); setPage(0); }} /> : null}
      {query.data ? <Caption>Showing {visibleTasks.length ? pageStart + 1 : 0}–{pageStart + pageTasks.length} of {visibleTasks.length} matching tasks · {query.data.tasks.length} total</Caption> : null}
      {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
      {pageTasks.map((task, index) => <View key={task.id} style={{ gap: 6 }}>
        {index === 0 || pageTasks[index - 1]?.goal !== task.goal ? <Heading level={2}>Goal · {task.goal ?? 'unassigned'}</Heading> : null}
        <Card compact>
          <Row><Label mono>{task.id}</Label><Badge label={task.status} tone={tone(task.status)} /><Caption>{task.section ?? 'unknown section'}</Caption>{task.position ? <Caption>position {task.position}</Caption> : null}</Row>
          <Label>{task.title}</Label>
          <Caption>Goal: {display(task.goal)} · Blocked by: {display(task.blocked_by)}</Caption>
          <Label>Closure: {closureLabel(task.closure)}</Label>
          <Row>
            <Button label={`Open task ${task.id}`} compact onPress={() => select(selected === task.id ? '' : task.id)} />
            {questions.some(question => question.id === task.id) ? <Button label={`Answer task ${task.id}`} compact variant="primary" onPress={() => select(task.id)} /> : null}
          </Row>
        </Card>
      </View>)}
      {lastPage > 0 ? <Row>
        <Button label="Previous task page" compact disabled={currentPage === 0} onPress={() => setPage(currentPage - 1)} />
        <Caption>Page {currentPage + 1} of {lastPage + 1}</Caption>
        <Button label="Next task page" compact disabled={currentPage === lastPage} onPress={() => setPage(currentPage + 1)} />
      </Row> : null}
      {!query.isFetching && !query.isError && query.data && !visibleTasks.length ? <Notice><Label>{!query.data.tasks.length ? 'No tasks observed.' : hasFilters ? 'No tasks match these filters.' : 'No blocked tasks observed.'}</Label></Notice> : null}
    </Card>
    {selected ? <TaskView key={selected} task={query.data?.tasks.find(task => task.id === selected)} taskId={selected} {...common} enabled={enabled && !query.isStale && !query.isError} onClose={() => select('')} /> : null}
    {!blockers && editing ? <AddTaskCard {...common} /> : null}
    {!blockers && editing ? <GoalsCard {...common} /> : null}
    {!blockers ? <StoreCard {...common} /> : null}
  </Stack>;
}

function PendingCard({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const load = useRpc(storeRpc);
  const [message, setMessage] = useState('');
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'store', 'pending'], enabled: host.enabled && fleet.capabilities.tasks.includes('commit'),
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, view: 'pending' })), staleTime: 10000, retry: false, refetchOnWindowFocus: false,
  });
  const pending = record(query.data?.value);
  const files = Array.isArray(pending?.files) ? pending!.files.filter((item): item is string => typeof item === 'string') : [];
  if (!fleet.capabilities.tasks.includes('commit')) return <Notice tone="warning"><Label>The installed Autowork release lacks `tasks commit`; task edits stay uncommitted until the executable is updated.</Label></Notice>;
  return <Card>
    <Row><Heading level={2}>Pending task edits</Heading><Caption>{query.isFetching ? 'Reading…' : files.length ? `${files.length} file(s) uncommitted` : 'nothing to commit'}</Caption></Row>
    {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
    {files.length ? <>
      <Label mono>{files.join('\n')}</Label>
      <Expand title="Pending diff"><Label mono>{display(pending?.diff)}</Label></Expand>
      {fleet.permissions.commit ? <>
        <Input label="Commit message" value={message} onChange={setMessage} />
        <Button label="Prepare task commit" variant="primary" disabled={!enabled || !message.trim()} onPress={() => request({ kind: 'commit', repoId: repo.id, message: message.trim() })} />
        <Caption>Commits only tasks/ paths; other dirty files stay. No push.</Caption>
      </> : <Caption>Task-store commits are not granted by operator policy.</Caption>}
    </> : null}
  </Card>;
}

const sections = ['Now', 'Next', 'Needs decision'] as const;
const kinds = ['implementation', 'plan', 'inspection'] as const;
const ownerships = ['worker', 'coordinator', 'owner'] as const;

function AddTaskCard({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const [open, setOpen] = useState(false);
  const goals = useGoals(host, hostId, fleet, repo, open && fleet.capabilities.tasks.includes('goals'));
  const [goal, setGoal] = useState('');
  const [title, setTitle] = useState('');
  const [short, setShort] = useState('');
  const [section, setSection] = useState<typeof sections[number]>('Next');
  const [kind, setKind] = useState<typeof kinds[number]>('implementation');
  const [ownership, setOwnership] = useState<typeof ownerships[number]>('worker');
  const [scope, setScope] = useState('');
  const [acceptance, setAcceptance] = useState('');
  const [checks, setChecks] = useState('');
  const [touches, setTouches] = useState('');
  const [dependsOn, setDependsOn] = useState('');
  const ready = goal.trim() && title.trim() && short.trim();
  return <Card>
    <Row><Heading level={2}>Add task</Heading><Button label={open ? 'Hide task form' : 'New task'} compact selected={open} onPress={() => setOpen(!open)} /></Row>
    {open ? <>
      {goals.data?.goals.length ? <ScrollRow>{goals.data.goals.map(item => <Button key={item.id} label={item.id} compact selected={goal === item.id} onPress={() => setGoal(item.id)} />)}</ScrollRow> : null}
      <Input label="Goal ID" value={goal} onChange={setGoal} />
      <Input label="Title" value={title} onChange={setTitle} />
      <Input label="Short (at most 80 characters)" value={short} onChange={setShort} />
      <Choice label="Section" value={section} options={sections} onChange={setSection} />
      <Choice label="Kind" value={kind} options={kinds} onChange={setKind} />
      <Choice label="Ownership" value={ownership} options={ownerships} onChange={setOwnership} />
      <Input label="Scope" value={scope} onChange={setScope} multiline />
      <Input label="Acceptance (one per line)" value={acceptance} onChange={setAcceptance} multiline />
      <Input label="Checks (one per line)" value={checks} onChange={setChecks} multiline />
      <Input label="Touches (one per line)" value={touches} onChange={setTouches} multiline />
      <Input label="Depends on (IDs)" value={dependsOn} onChange={setDependsOn} />
      <Button label="Prepare task add" variant="primary" disabled={!enabled || !ready} onPress={() => request({ kind: 'task-add', repoId: repo.id, fields: {
        goal: goal.trim(), title: title.trim(), short: short.trim(), section, kind, ownership,
        ...(scope.trim() ? { scope: scope.trim() } : {}), ...(lines(acceptance).length ? { acceptance: lines(acceptance) } : {}), ...(lines(checks).length ? { checks: lines(checks) } : {}),
        ...(lines(touches).length ? { touches: lines(touches) } : {}), ...(words(dependsOn).length ? { depends_on: words(dependsOn) } : {}),
      } })} />
      <Caption>The record is written to the working tree; commit it from Pending task edits.</Caption>
    </> : null}
  </Card>;
}

const goalStatuses = ['unmet', 'partial', 'unverified', 'met'] as const;
function GoalsCard({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const [open, setOpen] = useState(false);
  const goals = useGoals(host, hostId, fleet, repo, open && fleet.capabilities.tasks.includes('goals'));
  const [selected, select] = useState<Goal | null>(null);
  const [newId, setNewId] = useState('');
  const [title, setTitle] = useState('');
  const [source, setSource] = useState('');
  const [priority, setPriority] = useState('');
  const [status, setStatus] = useState<typeof goalStatuses[number] | ''>('');
  const [focus, setFocus] = useState<boolean | null>(null);
  const [dependsOn, setDependsOn] = useState('');
  const [evidence, setEvidence] = useState('');
  const choose = (goal: Goal | null) => { select(goal); setTitle(goal?.title ?? ''); setSource(goal?.source ?? ''); setPriority(goal?.priority != null ? String(goal.priority) : ''); setStatus(''); setFocus(null); setDependsOn(goal?.depends_on.join(' ') ?? ''); setEvidence(''); };
  const target = selected?.id ?? newId.trim();
  const fields = {
    ...(title.trim() && title.trim() !== selected?.title ? { title: title.trim() } : {}), ...(source.trim() && source.trim() !== selected?.source ? { source: source.trim() } : {}),
    ...(priority.trim() && Number(priority) !== selected?.priority ? { priority: Number(priority) } : {}), ...(status ? { status } : {}), ...(focus !== null ? { focus } : {}),
    ...(dependsOn.trim() !== (selected?.depends_on.join(' ') ?? '') ? { depends_on: words(dependsOn) } : {}), ...(evidence.trim() ? { evidence: evidence.trim() } : {}),
  };
  const changed = Object.keys(fields).length > 0;
  return <Card>
    <Row><Heading level={2}>Goals</Heading><Button label={open ? 'Hide goals' : 'Show goals'} compact selected={open} onPress={() => setOpen(!open)} /></Row>
    {open ? <>
      {!fleet.capabilities.tasks.includes('goals') ? <Notice tone="warning"><Label>The installed Autowork release lacks `tasks goals`.</Label></Notice> : null}
      {goals.error ? <Notice tone="danger"><Label>{goals.error.message}</Label></Notice> : null}
      {goals.data?.goals.map(goal => <View key={goal.id} style={{ gap: 4, paddingVertical: 4 }}>
        <Row><Label mono>{goal.id}</Label><Badge label={goal.status} tone={goal.status === 'met' ? 'success' : 'neutral'} />{goal.focus ? <Badge label="focus" tone="accent" /> : null}<Caption>priority {display(goal.priority)}</Caption></Row>
        <Label>{goal.title}</Label>
        <Row><Button label={`Edit goal ${goal.id}`} compact selected={selected?.id === goal.id} onPress={() => choose(selected?.id === goal.id ? null : goal)} /></Row>
      </View>)}
      {!selected ? <Input label="New goal ID" value={newId} onChange={setNewId} /> : <Caption>Editing {selected.id} at record revision {selected.record_revision}</Caption>}
      <Input label="Goal title" value={title} onChange={setTitle} />
      <Input label="Goal source (path#anchor)" value={source} onChange={setSource} />
      <Input label="Goal priority" value={priority} onChange={setPriority} />
      <Choice label="Goal status (unchanged when none selected)" value={status || 'unchanged'} options={['unchanged', ...goalStatuses]} onChange={value => setStatus(value === 'unchanged' ? '' : value as typeof goalStatuses[number])} />
      <Choice label="Focus" value={focus === null ? 'unchanged' : focus ? 'focus' : 'no focus'} options={['unchanged', 'focus', 'no focus']} onChange={value => setFocus(value === 'unchanged' ? null : value === 'focus')} />
      <Input label="Goal depends on (IDs)" value={dependsOn} onChange={setDependsOn} />
      <Input label="Goal evidence (for met)" value={evidence} onChange={setEvidence} />
      <Button label="Prepare goal write" variant="primary" disabled={!enabled || !target || !changed} onPress={() => request({ kind: 'goal', repoId: repo.id, goal: target, ...(selected ? { revision: selected.record_revision } : {}), fields })} />
    </> : null}
  </Card>;
}

function StoreCard({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const load = useRpc(storeRpc);
  const [view, setView] = useState<'validate' | 'prepare' | null>(null);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'store', view ?? ''], enabled: host.enabled && !!view,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, view: view! })), staleTime: 10000, retry: false, refetchOnWindowFocus: false,
  });
  const result = record(query.data?.value);
  const unconverted = result?.state === 'unconverted' || result?.state === 'missing' || result?.outcome === 'NO_STORE';
  return <Card>
    <Expand title="Store checks">
      <Row>
        <Button label="Validate working tree" compact selected={view === 'validate'} onPress={() => setView('validate')} />
        <Button label="Prepare check" compact selected={view === 'prepare'} onPress={() => setView('prepare')} />
      </Row>
      {query.isFetching ? <Caption>Reading…</Caption> : null}
      {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
      {result ? <Label mono>{display(result)}</Label> : null}
      {fleet.permissions.tasks && view === 'prepare' && result ? <Row>
        <Button label="Prepare store prepare" compact variant="primary" disabled={!enabled} onPress={() => request({ kind: 'store-prepare', repoId: repo.id, mode: 'commit' })} />
        <Button label="Prepare store staging" compact disabled={!enabled} onPress={() => request({ kind: 'store-prepare', repoId: repo.id, mode: 'stage' })} />
        {unconverted ? <Button label="Prepare store migrate" compact disabled={!enabled} onPress={() => request({ kind: 'store-migrate', repoId: repo.id, commit: true })} /> : null}
      </Row> : null}
      <Caption>Prepare may create one local commit; staging leaves HEAD unmoved. Neither pushes.</Caption>
    </Expand>
  </Card>;
}

function TaskView({ task, taskId, repo, fleet, host, hostId, enabled, request, onClose }: RepoViewProps & { task?: Task; taskId: string; onClose?: () => void }) {
  const load = useRpc(taskRpc);
  const why = useRpc(storeRpc);
  const editing = fleet.permissions.tasks;
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'task', taskId, editing], enabled: host.enabled,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, task: taskId, working: editing })), staleTime: 10000, retry: false, refetchOnWindowFocus: false
  });
  const [explain, setExplain] = useState(false);
  const explanation = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'store', 'why', taskId], enabled: host.enabled && explain,
    queryFn: () => readForHost(host, () => why({ instance: fleet.instance, repoId: repo.id, view: 'why', task: taskId })), staleTime: 10000, retry: false, refetchOnWindowFocus: false
  });
  const [answer, setAnswer] = useState('');
  const detail = query.data;
  const question = repo.runner?.questions.find(item => item.id === taskId);
  return <Card>
    <Row><View style={{ flexGrow: 1, gap: 2 }}><Heading level={2}>{taskId}</Heading><Caption>{detail?.title ?? task?.title ?? 'Task detail'}</Caption></View>{onClose ? <Button label="Close task" compact onPress={onClose} /> : null}</Row>
    {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
    {detail ? <>
      <Row><Badge label={detail.status} tone={tone(detail.status)} /><Caption>{display(detail.section)} · live permission: {display(detail.live)}</Caption></Row>
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
      <Row><Button label="Explain selection" compact selected={explain} onPress={() => setExplain(!explain)} /></Row>
      {explain ? (explanation.error ? <Notice tone="danger"><Label>{explanation.error.message}</Label></Notice> : <Label mono>{explanation.data ? display(explanation.data.value) : 'Reading…'}</Label>) : null}
      {task && repo.runner && canAnswer(task, repo.runner, detail) ? <>
        <Divider />
        <Heading level={2}>Owner question</Heading>
        <Label>{question?.needs}</Label>
        <Input label="Owner answer" value={answer} onChange={setAnswer} multiline />
        <Button label="Prepare owner answer" variant="primary" disabled={!enabled || query.isStale || !answer.trim() || !fleet.permissions.decisions} onPress={() => request({ kind: 'decision', repoId: repo.id, task: taskId, revision: detail.record_revision, text: answer })} />
      </> : <Notice><Label>No answer action: this is not a current canonical owner question for an open task.</Label></Notice>}
      {editing ? <TaskActions detail={detail} repo={repo} enabled={enabled && !query.isStale} request={request} /> : null}
    </> : <Caption>Loading task…</Caption>}
  </Card>;
}

function TaskActions({ detail, repo, enabled, request }: { detail: TaskDetail; repo: Repo; enabled: boolean; request: (action: ActionInput) => void }) {
  const base = { repoId: repo.id, task: detail.id, revision: detail.record_revision };
  const [section, setSection] = useState<typeof sections[number]>(sections.find(item => item === detail.section) ?? 'Now');
  const [placement, setPlacement] = useState('');
  const [holdBy, setHoldBy] = useState('');
  const [holdUntil, setHoldUntil] = useState('');
  const [doneBy, setDoneBy] = useState('');
  const [reason, setReason] = useState('');
  const [evidence, setEvidence] = useState('');
  const [successors, setSuccessors] = useState('');
  const [supersedeReason, setSupersedeReason] = useState('');
  const [label, setLabel] = useState('');
  const [value, setValue] = useState('');
  const open = detail.status === 'open';
  return <Expand title="Edit task">
    <Caption>Every edit binds to record revision {detail.record_revision} and writes the working tree; commit from Pending task edits.</Caption>
    <Choice label="Section" value={section} options={sections} onChange={setSection} />
    <Input label="Placement decision (optional)" value={placement} onChange={setPlacement} />
    <Row>
      <Button label="Prepare task place" compact variant="primary" disabled={!enabled || !open} onPress={() => request({ kind: 'task-place', ...base, section, ...(placement.trim() ? { decision: placement.trim() } : {}) })} />
      <Button label="Prepare move up" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-move', ...base, direction: 'up' })} />
      <Button label="Prepare move down" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-move', ...base, direction: 'down' })} />
    </Row>
    <Divider />
    <Input label="Hold by" value={holdBy} onChange={setHoldBy} />
    <Input label="Hold until (YYYY-MM-DD)" value={holdUntil} onChange={setHoldUntil} />
    <Row>
      <Button label="Prepare task hold" compact variant="primary" disabled={!enabled || !open || !holdBy.trim()} onPress={() => request({ kind: 'task-hold', ...base, by: holdBy.trim(), ...(holdUntil.trim() ? { until: holdUntil.trim() } : {}) })} />
      <Button label="Prepare task release" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-release', ...base })} />
    </Row>
    <Divider />
    <Input label="Closed by" value={doneBy} onChange={setDoneBy} />
    <Input label="Closure reason" value={reason} onChange={setReason} multiline />
    <Input label="Closure evidence reference (optional)" value={evidence} onChange={setEvidence} />
    <Button label="Prepare task done" compact variant="primary" disabled={!enabled || !open || !doneBy.trim() || !reason.trim()} onPress={() => request({ kind: 'task-done', ...base, by: doneBy.trim(), reason: reason.trim(), ...(evidence.trim() ? { evidence: evidence.trim() } : {}) })} />
    <Caption>A manual close records provenance; it does not verify acceptance.</Caption>
    <Divider />
    <Input label="Successor IDs" value={successors} onChange={setSuccessors} />
    <Input label="Supersede reason" value={supersedeReason} onChange={setSupersedeReason} />
    <Button label="Prepare task supersede" compact disabled={!enabled || !words(successors).length || !supersedeReason.trim()} onPress={() => request({ kind: 'task-supersede', ...base, by: words(successors), reason: supersedeReason.trim() })} />
    <Divider />
    <Input label="Field label" value={label} onChange={setLabel} />
    <Input label="Field value (JSON array for lists)" value={value} onChange={setValue} multiline />
    <Button label="Prepare task field" compact disabled={!enabled || !label.trim()} onPress={() => request({ kind: 'task-field', ...base, label: label.trim(), value })} />
    <Divider />
    <Button label="Prepare task delete" compact variant="danger" disabled={!enabled} onPress={() => request({ kind: 'task-delete', ...base })} />
    <Caption>Delete removes the record only; worktrees, commits, evidence and goals stay.</Caption>
  </Expand>;
}

const modes = [['plan', 'Plan'], ['discuss', 'Discuss'], ['investigate', 'Investigate']] as const;
function PlanningView({ repo, fleet, host, hostId, enabled, request, sessionId, operation, objective }: RepoViewProps & { sessionId?: string; operation?: Operation; objective: string }) {
  const [text, setText] = useState(objective);
  useEffect(() => { if (!sessionId) setText(objective); }, [objective, sessionId]);
  const [view, setView] = useState<'preview' | 'history' | 'roadmap'>('preview');
  const [requested, setRequested] = useState(false);
  const [mode, setMode] = useState<'plan' | 'discuss' | 'investigate'>('plan');
  const [task, setTask] = useState('');
  const [model, setModel] = useState('');
  const [wantModels, setWantModels] = useState(false);
  const models = useModels(host, hostId, fleet, wantModels);
  const load = useRpc(planningRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'planning', sessionId ?? '', view], enabled: host.enabled && !!sessionId && requested,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, sessionId: sessionId!, view })), staleTime: 0, retry: false, refetchOnWindowFocus: false, refetchOnMount: false, refetchOnReconnect: false
  });
  useEffect(() => { setRequested(false); }, [operation?.id, sessionId]);
  const preview = view === 'preview' && requested && !query.isError && !query.isFetching ? previewForApply(query.data?.value) : null;
  const busy = operation?.status === 'running' || operation?.status === 'uncertain';
  const planEnabled = enabled && fleet.permissions.planning && !busy;
  const value = record(query.data?.value);
  return <Card>
    <Row><Heading level={2}>Staged planning</Heading><Badge label={fleet.permissions.planning ? 'planning enabled' : 'read-only'} tone={fleet.permissions.planning ? 'success' : 'warning'} /></Row>
    <Caption>Planning never starts a runner. Only sessions created by this backend instance are accepted.</Caption>
    <Input label={sessionId ? 'Planning message' : 'Objective (empty discovers work)'} value={text} onChange={setText} multiline />
    {!sessionId ? <>
      <Choice label="Mode" value={mode} options={modes} onChange={setMode} />
      <Input label="Task scope (optional)" value={task} onChange={setTask} />
      <Row><Button label="Load model list" compact selected={wantModels} onPress={() => setWantModels(true)} />{models.isFetching ? <Caption>Loading models…</Caption> : null}</Row>
      {models.data?.models.length ? <ScrollRow>{models.data.models.map(name => <Button key={name} label={name} compact selected={model === name} onPress={() => setModel(model === name ? '' : name)} />)}</ScrollRow> : null}
      <Input label="Planning model (optional)" value={model} onChange={setModel} />
      <Button label="Prepare planning start" variant="primary" disabled={!planEnabled} onPress={() => request({ kind: 'plan-start', repoId: repo.id, objective: text, mode, ...(task.trim() ? { task: task.trim() } : {}), ...(model.trim() ? { model: model.trim() } : {}) })} />
      <Caption>Discuss and investigate modes talk about the plan; only plan mode stages file proposals.</Caption>
    </> : <>
      <Label mono>Owned session: {sessionId}</Label>
      <Row>
        <Button label="Prepare planning message" compact variant="primary" disabled={!planEnabled || !text.trim()} onPress={() => request({ kind: 'plan-send', repoId: repo.id, sessionId, message: text })} />
        {(['preview', 'history', 'roadmap'] as const).map(next => <Button key={next} label={`Read planning ${next}`} compact disabled={!host.enabled || busy} selected={view === next && requested} onPress={() => { setView(next); setRequested(true); if (next === view && requested) void query.refetch(); }} />)}
      </Row>
      {requested ? <>
        <Caption>{query.isFetching ? 'Reading planning…' : 'Cached planning observation; Apply revalidates the exact revision.'}</Caption>{query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
        <Expand title="Planning result">
          <Label mono>{view === 'preview' ? `Revision: ${display(value?.revision)}\nValid: ${display(value?.valid)}\nFiles: ${display(value?.files)}\nErrors: ${display(value?.errors)}\n${display(value?.diff)}` : display(query.data?.value)}</Label>
        </Expand>
      </> : null}
      {preview ? <>
        <Label>Preview revision: <Label mono>{preview.revision}</Label></Label>
        <Button label="Prepare Apply exact preview" variant="primary" disabled={!planEnabled} onPress={() => request({ kind: 'plan-apply', repoId: repo.id, sessionId, revision: preview.revision })} />
      </> : <Caption>Read a valid nonempty preview before Apply.</Caption>}
    </>}
    {busy && operation?.sessionId && ['plan-start', 'plan-send'].includes(operation.kind) ? <Row>
      <Button label="Prepare planning cancel" compact disabled={!enabled || !fleet.permissions.planning} onPress={() => request({ kind: 'plan-cancel', repoId: repo.id, operationId: operation.id })} />
      <Button label="Prepare planning steer" compact disabled={!enabled || !fleet.permissions.planning || !text.trim()} onPress={() => request({ kind: 'plan-steer', repoId: repo.id, operationId: operation.id, message: text })} />
    </Row> : null}
    {!fleet.permissions.planning ? <Notice tone="warning"><Label>Planning is disabled by operator policy.</Label><Caption>No client toggle grants planning authority.</Caption></Notice> : null}
  </Card>;
}

function metricLines(card: unknown): string[] {
  const summary = record(record(card)?.summary);
  if (!summary) return [];
  return Object.entries(summary).map(([key, metric]) => {
    const item = record(metric);
    return `${key}: ${item?.value === null || item?.value === undefined ? 'missing' : `${human(item.value)} ${human(item.unit)}`} [${human(item?.status)}]`;
  });
}
function ScorecardView({ fleet, host, hostId }: { fleet: Fleet; host: HostState; hostId: string }) {
  const load = useRpc(scorecardRpc);
  const [days, setDays] = useState<'1' | '7' | '14' | '30'>('7');
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, 'scorecard', days], enabled: host.enabled && fleet.capabilities.commands.includes('scorecard'),
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, days: Number(days) })), staleTime: 60000, retry: false, refetchOnWindowFocus: false,
  });
  const card = record(query.data?.value);
  const runners = record(card?.runners) ?? {};
  const errors = record(card?.errors) ?? {};
  return <Card>
    <Row><Heading level={2}>Scorecard</Heading><Caption>{query.isFetching ? 'Measuring…' : query.data ? new Date(query.data.capturedAt).toISOString() : 'No model call; read-only accounting.'}</Caption></Row>
    <Choice label="Days" value={days} options={['1', '7', '14', '30'] as const} onChange={setDays} />
    {!fleet.capabilities.commands.includes('scorecard') ? <Notice tone="warning"><Label>The installed Autowork release lacks `scorecard`.</Label></Notice> : null}
    {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
    {Object.entries(errors).map(([name, error]) => <Notice key={name} tone="warning"><Label>{name}: no metrics; {human(error)}</Label></Notice>)}
    {Object.entries(runners).map(([name, row]) => <View key={name} style={{ gap: 3, paddingVertical: 6 }}>
      <Row><Heading level={2}>{name}</Heading><Caption>closed {human(record(row)?.closed)} · verified {human(record(row)?.verified_closed)}</Caption></Row>
      {metricLines(record(row)?.evaluation).map(line => <Caption key={line}>{line}</Caption>)}
      <Divider />
    </View>)}
    {card ? <><Heading level={2}>Overall</Heading>{metricLines(card.overall).map(line => <Caption key={line}>{line}</Caption>)}</> : null}
  </Card>;
}

/** Settled operations announced on this client; survives remounts so a toast shows once per outcome. */
const announced = new Set<string>();
function OperationStatus({ operation, fleet, hostId, enabled, onUpdate }: { operation: Operation; fleet: Fleet; hostId: string; enabled: boolean; onUpdate: (operation: Operation) => void }) {
  const load = useRpc(operationRpc);
  const toast = useToast();
  const backoff = useReadBackoff();
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, 'operation', operation.id], enabled: enabled && operation.status === 'running',
    queryFn: () => backoff.run(() => load({ instance: fleet.instance, id: operation.id })), retry: false, staleTime: 0, refetchOnWindowFocus: false,
    refetchInterval: q => enabled && operation.status === 'running' && q.state.data?.status !== 'failed' && q.state.data?.status !== 'uncertain' && q.state.data?.status !== 'succeeded' && q.state.data?.status !== 'cancelled' ? backoff.delay(1500, 30000) : false
  });
  const update = useRef(onUpdate); update.current = onUpdate;
  useEffect(() => { if (query.data && query.data !== operation) update.current(query.data); }, [query.data, operation]);
  useEffect(() => {
    const key = `${operation.id}:${operation.status}`;
    if (operation.status === 'running' || announced.has(key)) return;
    if (announced.size > 512) announced.clear();
    announced.add(key);
    toast.show(`${operation.kind}: ${operation.status}`, { variant: operation.status === 'succeeded' ? 'success' : operation.status === 'uncertain' ? 'warning' : 'error', durationMs: 4000 });
  }, [operation.id, operation.status, operation.kind, toast]);
  return <Card compact>
    <Row><Badge label={operation.status} tone={tone(operation.status)} /><Label mono>{operation.kind}</Label><Caption>{operation.id}</Caption></Row>
    <Label>{operation.message}</Label>
    {operation.status === 'uncertain' ? <Button label="Reconcile operation" compact disabled={!enabled} onPress={() => { void query.refetch(); }} /> : null}
    {operation.progress ? <Caption>{operation.progress}</Caption> : null}
    {operation.result !== undefined ? <Expand title="Operation result evidence"><Label mono>{display(operation.result)}</Label></Expand> : null}
    {query.error ? <Notice tone="danger"><Label>Status unavailable; delivery unknown. No replay: {query.error.message}</Label></Notice> : null}
    {operation.status === 'uncertain' ? <Caption>Outcome uncertain. Inspect canonical state before attempting another action.</Caption> : null}
  </Card>;
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
