import { useEffect, useRef, useState } from 'react';
import type { PluginAgentPanelProps, PluginScreenProps, PluginWorkspacePanelProps } from '@getpaseo/plugin/client';
import { useRpc, useWorkspace } from '@getpaseo/plugin/client';
import { ScrollView } from '@getpaseo/plugin/client/ui';
import { RefreshControl, View } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { logsRpc, operationRpc, planningRpc, taskRpc, tasksRpc, type Action, type Fleet, type Operation, type Repo, type Task } from '../shared/contracts';
import { canAnswer, closureLabel, display, human, jobSummary, knownDirectory, mainCheckSummary, previewForApply, record, taskMatches, type TaskFilters } from './presentation';
import { operationsKey, readForHost, rememberOperation, useConfirmedAction, useHostState, useReadBackoff, type HostState } from './state';
import { Badge, Button, Caption, Card, Divider, Expand, Heading, Input, Label, Notice, Row, ScrollRow, Stack, Stat, Theme } from './ui';

type ViewName = 'fleet' | 'runner' | 'tasks' | 'blockers' | 'planning';
const views: Array<[ViewName, string]> = [['fleet', 'Fleet'], ['runner', 'Runner'], ['tasks', 'Tasks'], ['blockers', 'Blockers'], ['planning', 'Planning']];
const validView = (view: string | undefined): ViewName => views.find(([name]) => name === view)?.[0] ?? 'fleet';

function tone(state: string): 'success' | 'warning' | 'danger' | 'neutral' {
  const value = state.toLowerCase();
  if (value.includes('run') || value.includes('active') || value === 'ready') return 'success';
  if (value.includes('wait') || value.includes('pause') || value.includes('stall') || value.includes('decision')) return 'warning';
  if (value.includes('fail') || value.includes('error') || value.includes('not running') || value.includes('block')) return 'danger';
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
  const status = fleet.isFetching ? 'Refreshing…' : fleet.data ? `${host.current ? 'Live' : 'Cached'} observation · ${new Date(fleet.data.capturedAt).toISOString()}` : host.enabled ? 'Loading fleet…' : 'No live observation';
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
  const running = repos.reduce((sum, item) => sum + (item.runner?.running ?? 0), 0);
  const decisions = repos.reduce((sum, item) => sum + (item.runner?.decisions ?? 0), 0);
  const readOnly = !fleet.permissions.controls.length && !fleet.permissions.planning && !fleet.permissions.decisions;
  const selectRepo = (id: string) => { selectId(id); if (view === 'fleet') setView('runner'); };
  return <>
    <ScrollRow>{views.map(([name, title]) => <Button key={name} label={title} compact selected={view === name} onPress={() => setView(name)} />)}</ScrollRow>
    <Row>
      <Stat value={repos.length} label="repositories" />
      <Stat value={running} label="running lanes" tone={running ? 'success' : 'neutral'} />
      <Stat value={decisions} label="need decision" tone={decisions ? 'warning' : 'neutral'} />
    </Row>
    <Row>
      <Badge label={readOnly ? 'read-only' : 'actions enabled'} tone={readOnly ? 'warning' : 'success'} />
      <Caption>{readOnly ? 'The daemon operator has not granted runner controls, planning or owner answers.' : 'Actions require an exact confirmation before dispatch.'}</Caption>
    </Row>
    <Caption>Release {fleet.release} · instance {fleet.instance}</Caption>
    {fleet.warnings.map((warning, index) => <Notice key={index} tone="warning"><Label>{warning}</Label></Notice>)}
    <Expand title="Connection details">
      <Label>Executable source release: {fleet.release}</Label>
      <Label>Prepare API: {fleet.prepareApi} · Instance: {fleet.instance}</Label>
      {directory ? <Caption>Workspace directory: {directory} · known repositories only</Caption> : null}
      <Caption>Runners, transport and delivery are observed from the selected host only.</Caption>
    </Expand>
    {view !== 'fleet' && repos.length ? <ScrollRow>{repos.map(item => <Button key={item.id} compact label={`Repository ${item.label}`} selected={repo?.id === item.id} onPress={() => selectId(item.id)} />)}</ScrollRow> : null}
    {view === 'fleet' ? <>
      {repos.map(item => <Card key={item.id} compact>
        <Row>
          <View style={{ flexGrow: 1, gap: 2 }}><Heading level={2}>{item.label}</Heading><Caption truncate>{item.path}</Caption></View>
          <Badge label={item.runner?.state ?? 'unknown'} tone={tone(item.runner?.state ?? '')} />
        </Row>
        {item.runner ? <Row>
          <Caption>{item.runner.running} running · {item.runner.waiting} waiting · {item.runner.stopped} stopped · {item.runner.decisions} decisions</Caption>
        </Row> : <Caption>No runner record observed.</Caption>}
        <Caption>Transport: unknown · Delivery: unknown</Caption>
        {item.error ? <Notice tone="danger"><Label>{item.error}</Label></Notice> : null}
        <Row>
          <Button label={`Open runner ${item.label}`} compact variant="primary" onPress={() => { selectId(item.id); setView('runner'); }} />
          <Button label={`Tasks ${item.label}`} compact onPress={() => { selectId(item.id); setView('tasks'); }} />
          <Button label={`Plan ${item.label}`} compact onPress={() => { selectId(item.id); setView('planning'); }} />
        </Row>
      </Card>)}
    </> : null}
    {!repos.length ? <Notice tone="warning"><Label>No known repository matches this directory.</Label><Caption>No arbitrary path RPC is sent.</Caption></Notice> : null}
    {view !== 'fleet' && repo ? <>
      <Row>
        <View style={{ flexGrow: 1, gap: 2 }}><Heading level={2}>{repo.label}</Heading><Caption truncate>{repo.revision || 'revision unavailable'}</Caption></View>
        {repo.runner ? <Badge label={repo.runner.state} tone={tone(repo.runner.state)} /> : null}
      </Row>
      {repo.error ? <Notice tone="danger"><Label>{repo.error}</Label></Notice> : null}
      {view === 'runner' ? <RunnerView key={repo.id} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} onView={setView} /> : null}
      {view === 'tasks' || view === 'blockers' ? <TasksView key={`${repo.id}:${view}`} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} blockers={view === 'blockers'} /> : null}
      {view === 'planning' ? <PlanningView key={repo.id} repo={repo} fleet={fleet} host={host} hostId={props.host.id} enabled={enabled} request={request} sessionId={sessions[repo.id]} operation={planningOperation} objective={props.params.objective ?? ''} /> : null}
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

type RepoViewProps = { repo: Repo; fleet: Fleet; host: HostState; hostId: string; enabled: boolean; request: (action: Action) => void; onView?: (view: ViewName) => void };

function RunnerView({ repo, fleet, host, hostId, enabled, request, onView }: RepoViewProps) {
  const runner = repo.runner;
  const [showLogs, setShowLogs] = useState(false);
  const logs = useRpc(logsRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'logs'], enabled: host.enabled && showLogs,
    queryFn: () => readForHost(host, () => logs({ instance: fleet.instance, repoId: repo.id })), staleTime: 15000, retry: false, refetchOnWindowFocus: false
  });
  if (!runner) return <Notice tone="warning"><Label>Runner unavailable; no status inferred.</Label></Notice>;
  const controls = fleet.permissions.controls;
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
      </Row>
      <Divider />
      <Row>{controls.length ? controls.map(action => <Button key={action} label={`Prepare ${action}`} compact variant="primary" disabled={!enabled} onPress={() => request({ kind: 'control', repoId: repo.id, action })} />) : <Caption>Runner controls are read-only by operator policy.</Caption>}</Row>
      {!controls.length ? <Caption>Set a daemon-side `PASEO_AUTOWORK_CONFIG` controls grant to enable start, pause, resume, stop or restart.</Caption> : null}
    </Card>
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
      <Label>Push allowed: {String(runner.push)} · Enabled: {String(runner.enabled)}</Label>
      <Label>Transport: unknown · Delivery: unknown</Label>
      <Divider />
      <Label>Main check: {mainCheckSummary(runner.main_check)}</Label>
      <Label>Current job: {jobSummary(runner.job)}</Label>
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
    {showLogs ? <Card>
      <Row><Heading level={2}>Runner logs</Heading><Caption>{query.isFetching ? 'Refreshing…' : query.data ? new Date(query.data.capturedAt).toISOString() : 'Loading…'}</Caption></Row>
      {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
      <Label mono>{query.data?.text ?? 'Loading…'}</Label>
    </Card> : null}
  </Stack>;
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
    <Card>
      <Row><Heading level={2}>{blockers ? 'Blocked tasks' : 'Task queue'}</Heading><Caption>{query.isFetching ? 'Refreshing…' : `${host.enabled && !query.isStale && !query.isError ? 'Live' : 'Cached'} · revision ${query.data?.revision ?? 'unknown'}`}</Caption></Row>
      <Row>{(['task', 'goal', 'runtime', 'section'] as const).map(key => <View key={key} style={{ flexGrow: 1, minWidth: 132 }}>
        <Input label={`Filter ${key}`} value={filters[key]} onChange={value => changeFilter(key, value)} />
      </View>)}</Row>
      {hasFilters ? <Button label="Clear task filters" compact onPress={() => { setFilters({ task: '', goal: '', runtime: '', section: '' }); setPage(0); }} /> : null}
      {query.data ? <Caption>Showing {visibleTasks.length ? pageStart + 1 : 0}–{pageStart + pageTasks.length} of {visibleTasks.length} matching tasks · {query.data.tasks.length} total</Caption> : null}
      {query.error ? <Notice tone="danger"><Label>{query.error.message}</Label></Notice> : null}
      {pageTasks.map((task, index) => <View key={task.id} style={{ gap: 6 }}>
        {index === 0 || pageTasks[index - 1]?.goal !== task.goal ? <Heading level={2}>Goal · {task.goal ?? 'unassigned'}</Heading> : null}
        <Card compact>
          <Row><Label mono>{task.id}</Label><Badge label={task.status} tone={tone(task.status)} /><Caption>{task.section ?? 'unknown section'}</Caption></Row>
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
    {selected ? <TaskView key={selected} task={query.data?.tasks.find(task => task.id === selected)} taskId={selected} repo={repo} fleet={fleet} host={host} hostId={hostId} enabled={enabled && !query.isStale && !query.isError} request={request} onClose={() => select('')} /> : null}
  </Stack>;
}

function TaskView({ task, taskId, repo, fleet, host, hostId, enabled, request, onClose }: RepoViewProps & { task?: Task; taskId: string; onClose?: () => void }) {
  const load = useRpc(taskRpc);
  const query = useQuery({
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'task', taskId], enabled: host.enabled,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance, repoId: repo.id, task: taskId, working: false })), staleTime: 10000, retry: false, refetchOnWindowFocus: false
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
      {task && repo.runner && canAnswer(task, repo.runner, detail) ? <>
        <Divider />
        <Heading level={2}>Owner question</Heading>
        <Label>{question?.needs}</Label>
        <Input label="Owner answer" value={answer} onChange={setAnswer} multiline />
        <Button label="Prepare owner answer" variant="primary" disabled={!enabled || query.isStale || !answer.trim() || !fleet.permissions.decisions} onPress={() => request({ kind: 'decision', repoId: repo.id, task: taskId, revision: detail.record_revision, text: answer })} />
      </> : <Notice><Label>No answer action: this is not a current canonical owner question for an open task.</Label></Notice>}
    </> : <Caption>Loading task…</Caption>}
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
  useEffect(() => { setRequested(false); }, [operation?.id, sessionId]);
  const preview = view === 'preview' && requested && !query.isError && !query.isFetching ? previewForApply(query.data?.value) : null;
  const busy = operation?.status === 'running' || operation?.status === 'uncertain';
  const planEnabled = enabled && fleet.permissions.planning && !busy;
  const value = record(query.data?.value);
  return <Card>
    <Row><Heading level={2}>Staged planning</Heading><Badge label={fleet.permissions.planning ? 'planning enabled' : 'read-only'} tone={fleet.permissions.planning ? 'success' : 'warning'} /></Row>
    <Caption>Planning never starts a runner. Only sessions created by this backend instance are accepted.</Caption>
    <Input label={sessionId ? 'Planning message' : 'Objective (empty discovers work)'} value={text} onChange={setText} multiline />
    {!sessionId ? <Button label="Prepare planning start" variant="primary" disabled={!planEnabled} onPress={() => request({ kind: 'plan-start', repoId: repo.id, objective: text })} /> : <>
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
