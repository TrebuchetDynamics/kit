import { useEffect, useRef, useState, type RefObject } from 'react';
import type { PluginAgentPanelProps, PluginScreenProps, PluginWorkspacePanelProps } from '@getpaseo/plugin/client';
import { useRpc, useWorkspace } from '@getpaseo/plugin/client';
import { ScrollView, useToast } from '@getpaseo/plugin/client/ui';
import { Pressable, RefreshControl, View } from 'react-native';
import type { ScrollView as NativeScrollView } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { goalsRpc, logsRpc, modelsRpc, operationRpc, planningRpc, scorecardRpc, statusRpc, storeRpc, taskRpc, tasksRpc, type ActionInput, type Fleet, type Goal, type Operation, type Repo, type Runner, type Task, type TaskDetail } from '../shared/contracts';
import { canAnswer, countSummary, display, emptyFilters, friendlyError, headline, human, isActionable, jobSummary, knownDirectory, mainCheckSummary, mainCheckTone, observationRows, previewForApply, record, relativeTime, reloadRequired, revisionParts, runnerFacts, selectionFacts, sharedBlocker, sortByUrgency, stateTone, taskMatches, whyStopped, type TaskFilters } from './presentation';
import { operationsKey, readForHost, rememberOperation, useConfirmedAction, useHostState, useReadBackoff, useWatch, type HostState } from './state';
import { Badge, Banner, Button, Caption, Card, Choice, Divider, Expand, Facts, HashChip, Heading, Input, Label, Markdown, Notice, Row, ScrollRow, Sheet, Stack, Stat, StatusPill, Theme, useColors } from './ui';

type ViewName = 'fleet' | 'runner' | 'tasks' | 'blockers' | 'planning' | 'scorecard';
const views: Array<[ViewName, string]> = [['fleet', 'Fleet'], ['runner', 'Runner'], ['tasks', 'Tasks'], ['blockers', 'Blockers'], ['planning', 'Planning'], ['scorecard', 'Scorecard']];
const validView = (view: string | undefined): ViewName => views.find(([name]) => name === view)?.[0] ?? 'fleet';
const lines = (value: string) => value.split('\n').map(item => item.trim()).filter(Boolean);
const words = (value: string) => value.split(/[\s,]+/).map(item => item.trim()).filter(Boolean);
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? '' : 's'}`;

export function AutoworkScreen(props: PluginScreenProps) {
  return <Theme.Provider value={props.theme}>
    <HostScreen key={props.host.id} {...props} />
  </Theme.Provider>;
}

function HostScreen(props: PluginScreenProps) {
  const host = useHostState(props.host.id);
  const scrollRef = useRef<NativeScrollView>(null);
  const { fleet } = host;
  const digest = useWatch(host, props.host.id, fleet.data?.instance);
  const checked = fleet.isFetching ? 'Refreshing…' : fleet.data ? `${host.current ? (digest ? 'Live via watch' : 'Live') : 'Cached'} · checked ${relativeTime(fleet.data.capturedAt)}${!host.current && digest ? ' · watch active' : ''}` : host.enabled ? 'Loading fleet…' : 'No live observation';
  // Bottom clearance keeps the last action above the navigation bar and the host's floating control.
  return <ScrollView ref={scrollRef} style={{ flex: 1, backgroundColor: props.theme.colors.surface0 }} contentContainerStyle={{ padding: props.layout.compact ? 14 : 22, paddingBottom: props.layout.compact ? 128 : 48, gap: 12, maxWidth: 1100, width: '100%', alignSelf: 'center' }} refreshControl={<RefreshControl refreshing={fleet.isFetching} enabled={host.enabled} onRefresh={host.refresh} tintColor={props.theme.colors.accent} />}>
    <Row between>
      <View style={{ flexShrink: 1, gap: 2, paddingRight: 56 }}>
        <Heading>{props.host.label}</Heading>
        <Caption>Autowork · {checked}</Caption>
      </View>
      <Button label={fleet.isFetching ? 'Refreshing…' : 'Refresh'} compact disabled={!host.enabled || fleet.isFetching} onPress={host.refresh} />
    </Row>
    {!host.online ? <Banner tone="danger" title="Host offline" body="Cached observations are not current authority. Nothing can be dispatched until the host is back." /> : null}
    {host.online && !host.foreground ? <Banner tone="warning" title="App backgrounded: polling paused" body="Reads resume when the app returns to the foreground." /> : null}
    {fleet.error ? <FleetUnavailable error={fleet.error} enabled={host.enabled} onRetry={host.refresh} /> : null}
    {fleet.data ? <FleetContent key={fleet.data.instance} props={props} host={host} fleet={fleet.data} scrollRef={scrollRef} /> : null}
  </ScrollView>;
}

/** A stale plugin generation cannot answer a retry; say where the reload happens instead. */
function FleetUnavailable({ error, enabled, onRetry }: { error: unknown; enabled: boolean; onRetry: () => void }) {
  const reload = reloadRequired(error);
  return <Banner tone="danger" title="Fleet unavailable"
    body={reload
      ? `${friendlyError(error)} In Paseo Settings → Plugins, reload Autowork, then refresh; a retry cannot succeed before that reload.`
      : `${friendlyError(error)} Automatic refresh retries with bounded backoff.`}
    action={{ label: reload ? 'Retry after reload' : 'Retry now', onPress: onRetry, disabled: !enabled }} />;
}

function grantSummary(fleet: Fleet): string[] {
  const p = fleet.permissions;
  return [...(p.controls.length ? [`controls: ${p.controls.join(', ')}`] : []), ...(p.maintenance.length ? [`maintenance: ${p.maintenance.join(', ')}`] : []),
    ...(p.decisions ? ['owner answers'] : []), ...(p.tasks ? ['task edits'] : []), ...(p.commit ? ['task-store commits'] : []), ...(p.planning ? ['planning'] : [])];
}
/** Operations that change something the owner cannot undo from this plugin need the repository name typed back. */
function dangerOf(action: ActionInput): string {
  if (action.kind === 'control' && action.action === 'remove') return 'removes this runner service from the host';
  if (action.kind === 'control' && action.action === 'update') return 'replaces the installed Autowork suite for every runner on this host';
  if (action.kind === 'task-delete') return 'deletes the task record';
  return '';
}
/** The consequence an owner needs before a ticket is consumed; the frozen summary carries the exact payload. */
function confirmationEffect(action: ActionInput, repoLabel: string): string {
  const label = repoLabel || 'this repository';
  switch (action.kind) {
    case 'control':
      if (action.action === 'restart') return `Restarts ${label} ${action.now ? 'now, interrupting merges' : action.stopWorkers ? 'after waiting for merges, then pausing workers' : 'after waiting for merges'}.`;
      if (action.action === 'remove') return `Removes the ${label} runner service. Task records and worktrees stay.`;
      if (action.action === 'update') return 'Replaces the installed Autowork suite for every runner on this host. Reload the plugin afterwards.';
      return `Runs ${action.action} once on ${label}.`;
    case 'model': return `Restarts ${label} with ${action.model}${action.fallback ? ` and fallback ${action.fallback}` : ''}.`;
    case 'attention': return `Records ${action.minutes} attention minutes${action.task ? ` for ${action.task}` : ''} in private runner state.`;
    case 'clear-held': return action.tasks?.length ? `Returns ${action.tasks.join(', ')} to integration.` : 'Returns every held commit to integration.';
    case 'decision': return `Records your answer on ${action.task}. It does not start work.`;
    case 'commit': return 'Commits the pending tasks/ edits. It does not push.';
    case 'task-add': return `Adds a task record under ${action.fields.goal}. Commit it separately.`;
    case 'goal': return `Writes goal ${action.goal}. Commit it separately.`;
    case 'task-delete': return `Deletes the ${action.task} record. It does not delete worktrees or commits.`;
    case 'task-field': case 'task-place': case 'task-move': case 'task-hold': case 'task-release': case 'task-done': case 'task-supersede':
      return `Writes the ${action.task} task record. Commit it separately.`;
    case 'store-prepare': return action.mode === 'stage' ? 'Stages the tasks/ store without moving HEAD.' : 'Prepares the tasks/ store and may create one local commit.';
    case 'store-migrate': return 'Converts the tasks/ store and creates one local commit.';
    case 'plan-start': return 'Starts an owned planning session. It does not start a runner.';
    case 'plan-send': return 'Sends a message to the owned planning session.';
    case 'plan-cancel': return 'Cancels the owned planning turn.';
    case 'plan-steer': return 'Steers the owned planning turn.';
    case 'plan-apply': return 'Applies the reviewed preview. It does not push or start a runner.';
  }
}

function FleetContent({ props, host, fleet, scrollRef }: { props: PluginScreenProps; host: HostState; fleet: Fleet; scrollRef: RefObject<NativeScrollView | null> }) {
  const [view, setView] = useState<ViewName>(validView(props.params.view));
  const [selectedId, selectId] = useState('');
  const [picker, setPicker] = useState(false);
  const [repoSearch, setRepoSearch] = useState('');
  const [pending, setPending] = useState<{ danger: string; label: string; phrase: string; prompt: string; action: ActionInput } | null>(null);
  const [typed, setTyped] = useState('');
  const queryClient = useQueryClient();
  const { data: operations } = useQuery<Operation[]>({ queryKey: operationsKey(props.host.id, fleet.instance), queryFn: async () => [], enabled: false, initialData: [], staleTime: Infinity, gcTime: 1800000 });
  const sessions = Object.fromEntries(operations.filter(operation => operation.sessionId).map(operation => [operation.repoId, operation.sessionId!]));
  const directory = props.params.directory;
  const repos = sortByUrgency(directory ? fleet.repos.filter(repo => knownDirectory(repo.path, directory)) : fleet.repos);
  const repo = repos.find(item => item.id === selectedId) ?? repos[0];
  const repoMatches = repos.filter(item => `${item.label} ${item.path}`.toLowerCase().includes(repoSearch.trim().toLowerCase()));
  const latestOperations = [...operations].reverse();
  const planningOperation = latestOperations.find(item => item.repoId === repo?.id && ['plan-start', 'plan-send'].includes(item.kind) && ['running', 'uncertain'].includes(item.status))
    ?? latestOperations.find(item => item.repoId === repo?.id && item.kind.startsWith('plan-'));
  const context = `${view}:${repo?.id ?? ''}:${repo?.revision ?? ''}`;
  const updateOperation = (operation: Operation) => {
    queryClient.setQueryData<Operation[]>(operationsKey(props.host.id, fleet.instance), existing => rememberOperation(existing, operation));
  };
  const mutation = useConfirmedAction(host, props.host.id, fleet.instance, context, updateOperation);
  const enabled = host.current && !mutation.busy && !repo?.error;
  const request = (action: ActionInput, label = '') => {
    const updateAll = action.kind === 'control' && action.action === 'update';
    const repoLabel = label || repos.find(item => item.id === action.repoId)?.label || '';
    setPending({ danger: dangerOf(action), label: repoLabel, phrase: updateAll ? 'all runners' : repoLabel,
      prompt: updateAll ? 'Type all runners to update every runner' : 'Type the repository name to confirm', action }); setTyped('');
    void mutation.request(action);
  };
  useEffect(() => { setView(validView(props.params.view)); }, [props.params.view]);
  useEffect(() => { scrollRef.current?.scrollTo({ y: 0, animated: false }); }, [view, selectedId, scrollRef]);
  const running = repos.reduce((sum, item) => sum + (item.runner?.running ?? 0), 0);
  const decisions = repos.reduce((sum, item) => sum + (item.runner?.decisions ?? 0), 0);
  const grants = grantSummary(fleet);
  const readOnly = !grants.length;
  const common = { fleet, host, hostId: props.host.id, enabled, request };
  const open = (target: Repo, next: ViewName) => { selectId(target.id); setView(next); };
  const hostBlocker = sharedBlocker(repos);
  const confirmation = mutation.confirmation;
  const effect = pending ? confirmationEffect(pending.action, pending.label) : '';
  const dangerous = !!pending?.danger;
  const typedOk = !dangerous || (typed.trim() === pending?.phrase && !!pending.phrase);
  return <>
    <Row>{views.map(([name, title]) => <Button key={name} label={title} compact selected={view === name} onPress={() => setView(name)} />)}</Row>
    {view === 'fleet' ? <FleetBanner repos={repos} decisions={decisions} running={running} onOpen={open} /> : null}
    {view === 'fleet' && hostBlocker ? <Notice tone="danger"><Label bold>Host-wide blocker</Label><Label>{hostBlocker}</Label><Caption>Affects every runner on this host; repository rows do not repeat it.</Caption></Notice> : null}
    {readOnly ? <Notice tone="warning"><Label bold>Read-only</Label><Caption>The daemon operator has not granted runner controls, planning, task edits or owner answers. Grants live in the daemon-side policy file.</Caption></Notice> : null}
    {view !== 'fleet' && view !== 'scorecard' && repos.length ? <Sheet title="Choose repository" open={picker} onClose={() => setPicker(false)}>
      {repos.length > 6 ? <Input label="Search repositories" value={repoSearch} onChange={setRepoSearch} placeholder="name or path" /> : null}
      {repoMatches.map(item => <RepositoryOption key={item.id} repo={item} selected={repo?.id === item.id} onPress={() => { selectId(item.id); setPicker(false); }} />)}
      {!repoMatches.length ? <Caption>No repository matches the search.</Caption> : null}
    </Sheet> : null}
    {view === 'fleet' ? <>
      <Row>
        <Stat value={repos.length} label="repositories" />
        {repos.some(item => item.error) ? <Stat value={repos.filter(item => item.error).length} label="unavailable" tone="danger" /> : null}
        <Stat value={running} label="running lanes" tone={running ? 'success' : 'neutral'} />
        <Stat value={decisions} label="need decision" tone={decisions ? 'warning' : 'neutral'} />
      </Row>
      {repos.map(item => <FleetRow key={item.id} repo={item} hostBlocker={hostBlocker} onOpen={open} />)}
      <Expand title="Connection details">
        <Facts rows={[['Release', fleet.release], ['Instance', fleet.instance], ['Executable', fleet.executable], ['Prepare API', String(fleet.prepareApi)], ['Policy', `${fleet.policy.path ?? 'none'} (${fleet.policy.source})`], ['Granted', readOnly ? 'nothing' : grants.join(' · ')], ['Transport', 'unknown'], ['Delivery', 'unknown']]} />
        {fleet.warnings.length ? <Caption>Daemon warnings: {fleet.warnings.join(' · ')}</Caption> : null}
        {directory ? <Caption>Workspace directory: {directory} · known repositories only</Caption> : null}
        <Caption>Runners, transport and delivery are observed from the selected host only. Every action is prepared, shown for confirmation, then dispatched once.</Caption>
      </Expand>
    </> : null}
    {view === 'scorecard' ? <ScorecardView fleet={fleet} host={host} hostId={props.host.id} /> : null}
    {!repos.length ? <Notice tone="warning"><Label>No known repository matches this directory.</Label><Caption>No arbitrary path RPC is sent.</Caption></Notice> : null}
    {view !== 'fleet' && view !== 'scorecard' && repo ? <>
      <Row between>
        <View style={{ flexShrink: 1, gap: 2 }}><Heading level={2}>{repo.label}</Heading>{repo.revision ? <HashChip value={revisionParts(repo.revision).hash} name="revision" suffix={revisionParts(repo.revision).suffix} /> : <Caption>revision unavailable</Caption>}</View>
        <View style={{ alignItems: 'flex-end', gap: 6 }}>
          {repo.runner ? <StatusPill state={repo.runner.display?.state ?? 'unknown'} /> : null}
          <Button label="Switch repository" compact onPress={() => { setRepoSearch(''); setPicker(true); }} />
        </View>
      </Row>
      {repo.error ? <Notice tone="danger"><Label bold>Repository unavailable</Label><Label mono>{repo.path}</Label><Caption>{repo.error}. Actions are disabled until this identity is readable: restore the path or remove it from the daemon policy's repositories list.</Caption></Notice> : null}
      {view === 'runner' ? <RunnerView key={repo.id} repo={repo} {...common} onView={setView} /> : null}
      {view === 'tasks' || view === 'blockers' ? <TasksView key={`${repo.id}:${view}`} repo={repo} {...common} blockers={view === 'blockers'} /> : null}
      {view === 'planning' ? <PlanningView key={repo.id} repo={repo} {...common} sessionId={sessions[repo.id]} operation={planningOperation} objective={props.params.objective ?? ''} /> : null}
    </> : null}
    {mutation.message && !confirmation ? <Notice tone={mutation.busy ? 'neutral' : 'warning'}><Label>{mutation.message}</Label></Notice> : null}
    <Sheet title="Confirm operation" open={!!confirmation} onClose={mutation.dismiss}>
      {confirmation ? <>
        <Label bold>{confirmation.summary}</Label>
        <Label>{effect}</Label>
        <Caption>Single use; a lost response stays uncertain and is never retried.</Caption>
        <Caption>Expires {relativeTime(confirmation.expiresAt).replace(' ago', '').replace('just now', 'now')} from now · Push {confirmation.pushAllowed ? 'allowed' : 'not allowed'} (unchanged).</Caption>
        {dangerous ? <Notice tone="danger">
          <Label bold>This {pending!.danger}.</Label>
          <Input label={pending!.prompt} value={typed} onChange={setTyped} placeholder={pending!.phrase} />
        </Notice> : null}
        <Row>
          <Button label="Confirm operation" variant={dangerous ? 'danger' : 'primary'} disabled={!enabled || !typedOk} onPress={() => { void mutation.confirm(); }} />
          <Button label="Dismiss confirmation" onPress={mutation.dismiss} />
        </Row>
      </> : null}
    </Sheet>
    {operations.map(operation => <OperationStatus key={operation.id} operation={operation} fleet={fleet} hostId={props.host.id} enabled={host.enabled && operation.repoId === repo?.id && (!operation.kind.startsWith('plan-') || view === 'planning')} onUpdate={updateOperation} />)}
  </>;
}

/** One banner for the whole fleet: the most urgent repository and the one thing to do about it. */
function FleetBanner({ repos, decisions, running, onOpen }: { repos: Repo[]; decisions: number; running: number; onOpen: (repo: Repo, view: ViewName) => void }) {
  const first = repos[0];
  if (!first) return null;
  const needing = repos.filter(item => (item.runner?.decisions ?? 0) > 0);
  if (needing.length) return <Banner tone="warning" title={`${plural(decisions, 'decision')} waiting`} body={`${needing.map(item => item.label).join(', ')} cannot continue until an owner answers.`} action={{ label: `Answer in ${needing[0]!.label}`, onPress: () => onOpen(needing[0]!, 'blockers') }} />;
  const broken = repos.find(item => item.error || (item.runner && stateTone(item.runner.state) === 'danger'));
  if (broken) return <Banner tone="danger" title={`${broken.label} needs attention`} body={broken.error ?? whyStopped(broken.runner!)[0] ?? broken.runner!.state} action={{ label: 'See why', onPress: () => onOpen(broken, 'runner') }} />;
  if (running) return <Banner tone="success" title={`${plural(running, 'lane')} running`} body="No decision is waiting and no runner reports a failure." secondary={{ label: 'Open tasks', onPress: () => onOpen(first, 'tasks') }} />;
  return <Banner tone="neutral" title="No runner is active" body="Every runner is paused, stopped or not running. Start one from its runner view." action={{ label: `Open ${first.label}`, onPress: () => onOpen(first, 'runner') }} />;
}

/** Two lines per repository, then Open and Answer; the host-wide blocker is said once above. */
function FleetRow({ repo, hostBlocker, onOpen }: { repo: Repo; hostBlocker: string | null; onOpen: (repo: Repo, view: ViewName) => void }) {
  const runner = repo.runner;
  const ownBlocker = runner?.blocker.trim() && runner.blocker.trim() !== hostBlocker ? runner.blocker.trim() : '';
  return <Card compact tone={repo.error ? 'danger' : undefined}>
    <Row between>
      <View style={{ flexShrink: 1, gap: 1 }}><Label bold>{repo.label}</Label><Caption truncate>{countSummary(runner)}</Caption></View>
      <StatusPill state={runner?.display?.state ?? 'unknown'} />
    </Row>
    {ownBlocker ? <Caption>Blocked: {ownBlocker}</Caption> : null}
    {repo.error ? <><Caption>{repo.error}</Caption><Caption truncate>{repo.path} · restore or remove it in the daemon policy</Caption></> : null}
    <Row>
      <Button label="Open" compact variant="primary" accessibilityLabel={`Open ${repo.label}`} onPress={() => onOpen(repo, 'runner')} />
      {(runner?.decisions ?? 0) > 0 ? <Button label="Answer" compact accessibilityLabel={`Answer ${repo.label}`} onPress={() => onOpen(repo, 'blockers')} /> : null}
    </Row>
  </Card>;
}

function RepositoryOption({ repo, selected, onPress }: { repo: Repo; selected: boolean; onPress: () => void }) {
  const colors = useColors();
  return <Pressable accessibilityRole="button" accessibilityLabel={`Repository ${repo.label}`} accessibilityState={{ selected }} onPress={onPress}
    style={{ minHeight: 48, minWidth: 48, flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10, borderRadius: 9, borderWidth: 1, borderColor: selected ? colors.accent : colors.border, backgroundColor: colors.surface2 }}>
    <View style={{ flex: 1, gap: 2 }}><Label bold>{repo.label}</Label><Caption truncate>{countSummary(repo.runner)}</Caption></View>
    <StatusPill state={repo.runner?.display?.state ?? 'unknown'} />
  </Pressable>;
}

type RepoViewProps = { repo: Repo; fleet: Fleet; host: HostState; hostId: string; enabled: boolean; request: (action: ActionInput) => void; onView?: (view: ViewName) => void };

function useModels(host: HostState, hostId: string, fleet: Fleet, wanted: boolean) {
  const load = useRpc(modelsRpc);
  return useQuery({
    queryKey: ['autowork', hostId, fleet.instance, 'models'], enabled: host.enabled && wanted,
    queryFn: () => readForHost(host, () => load({ instance: fleet.instance })), staleTime: 600000, retry: false, refetchOnWindowFocus: false,
  });
}
/** A searchable list instead of a free-text field; the typed value stays available for models the list lacks. */
function ModelPicker({ host, hostId, fleet, value, onChange, label }: { host: HostState; hostId: string; fleet: Fleet; value: string; onChange: (model: string) => void; label: string }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const models = useModels(host, hostId, fleet, open);
  const matches = (models.data?.models ?? []).filter(name => name.toLowerCase().includes(search.trim().toLowerCase())).slice(0, 40);
  return <Stack>
    <Row><Button label={value ? `Model: ${value}` : 'Choose model'} compact selected={open} accessibilityLabel="Choose model" onPress={() => setOpen(!open)} />{value ? <Button label="Clear model" compact variant="ghost" onPress={() => onChange('')} /> : null}</Row>
    {open ? <>
      <Input label="Search models" value={search} onChange={setSearch} placeholder="provider/name" />
      {models.isFetching ? <Caption>Loading models…</Caption> : null}
      {models.error ? <Notice tone="danger"><Label>{friendlyError(models.error)}</Label></Notice> : null}
      {models.data && !matches.length ? <Caption>{models.data.models.length ? 'No model matches the search.' : 'The CLI reported no models.'}</Caption> : null}
      {matches.length ? <ScrollRow>{matches.map(name => <Button key={name} label={name} compact selected={value === name} onPress={() => { onChange(value === name ? '' : name); setOpen(false); }} />)}</ScrollRow> : null}
    </> : null}
    <Input label={label} value={value} onChange={onChange} placeholder="provider/name" />
  </Stack>;
}

const restartModes = [['graceful', 'Wait for merges, keep workers'], ['stop-workers', 'Wait for merges, then pause workers'], ['now', 'Interrupt merges now']] as const;
type RestartMode = typeof restartModes[number][0];
const controlTitles: Record<string, string> = { start: 'Start', pause: 'Pause', resume: 'Resume', stop: 'Stop', restart: 'Restart', remove: 'Remove service', update: 'Update all runners' };

function RunnerView({ repo, fleet, host, hostId, enabled, request }: RepoViewProps) {
  const runner = repo.runner;
  const [showLogs, setShowLogs] = useState(false);
  const [follow, setFollow] = useState(false);
  const [logLines, setLogLines] = useState<'150' | '500' | '2000'>('150');
  const [showDiagnostics, setShowDiagnostics] = useState(false);
  const [restartMode, setRestartMode] = useState<RestartMode>('graceful');
  const [model, setModel] = useState('');
  const [fallback, setFallback] = useState('');
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
    queryKey: ['autowork', hostId, fleet.instance, repo.id, 'status'], enabled: host.enabled && showDiagnostics,
    queryFn: () => readForHost(host, () => status({ instance: fleet.instance, repoId: repo.id })), staleTime: 10000, retry: false, refetchOnWindowFocus: false,
  });
  if (!runner) return <Notice tone="warning"><Label>Runner unavailable; no status inferred.</Label></Notice>;
  const controls = fleet.permissions.controls;
  const maintenance = fleet.permissions.maintenance;
  const minutesValue = Number(minutes);
  const safe = controls.filter(action => action !== 'remove' && action !== 'update');
  const danger = controls.filter(action => action === 'remove' || action === 'update');
  const reasons = whyStopped(runner);
  const facts = runnerFacts(runner);
  const observation = observationRows(runner.observation);
  const control = (action: typeof controls[number]) => request(action === 'restart'
    ? { kind: 'control', repoId: repo.id, action, stopWorkers: restartMode !== 'graceful', now: restartMode === 'now' }
    : { kind: 'control', repoId: repo.id, action });
  return <Stack gap={12}>
    <Card>
      <Heading level={2}>Controls</Heading>
      {safe.length ? <>
        {!enabled ? <Notice tone="warning"><Label bold>Actions disabled</Label><Caption>{repo.error ? 'Repository identity is unavailable.' : !host.online ? 'Host is offline.' : !host.current ? 'This observation is cached; refresh for live authority.' : 'Another action is being prepared.'}</Caption></Notice> : null}
        <Row>{safe.map(action => <Button key={action} label={controlTitles[action] ?? action} variant="primary" disabled={!enabled} onPress={() => control(action)} />)}</Row>
        {controls.includes('restart') ? <Choice label="Restart mode" value={restartMode} options={restartModes} onChange={setRestartMode} disabled={!enabled} danger={['now']} /> : null}
        {restartMode === 'now' ? <Notice tone="danger"><Label bold>Interrupting merges now can leave an integration incomplete.</Label></Notice> : null}
        <Caption>Each control is prepared, shown for confirmation with its exact effect, then dispatched once.</Caption>
      </> : <Caption>Runner controls are read-only by operator policy. Grant controls in the daemon-side policy file to enable start, pause, resume, stop or restart.</Caption>}
    </Card>
    <Card>
      <Row>
        <Stat value={runner.running} label="running" tone={runner.running ? 'success' : 'neutral'} />
        <Stat value={runner.waiting} label="waiting" tone={runner.waiting ? 'warning' : 'neutral'} />
        <Stat value={runner.stopped} label="stopped" tone={runner.stopped ? 'danger' : 'neutral'} />
        <Stat value={runner.decisions} label="decisions" tone={runner.decisions ? 'warning' : 'neutral'} />
      </Row>
      {reasons.length ? <Notice tone={stateTone(runner.state) === 'danger' ? 'danger' : 'warning'}>
        <Label bold>Why it stopped</Label>
        {reasons.map(reason => <Label key={reason}>{reason}</Label>)}
        <Row style={{ maxWidth: 260 }}>
          <Button label="Logs" compact selected={showLogs} accessibilityLabel="Runner logs" onPress={() => setShowLogs(!showLogs)} />
          <Button label="Diagnostics" compact selected={showDiagnostics} onPress={() => setShowDiagnostics(!showDiagnostics)} />
        </Row>
      </Notice> : null}
    </Card>
    {danger.length ? <Card tone="danger">
      <Heading level={2}>Danger zone</Heading>
      {danger.includes('remove') ? <Label>Remove deletes this runner service from the host. Task records and worktrees stay on disk.</Label> : null}
      {danger.includes('update') ? <Label>Update replaces the installed Autowork suite for every runner on this host; reload the plugin afterwards.</Label> : null}
      <Caption>Remove asks for the repository name; Update all runners asks for “all runners” before dispatch.</Caption>
      <Row>{danger.map(action => <Button key={action} label={controlTitles[action] ?? action} variant="danger" disabled={!enabled} onPress={() => control(action)} />)}</Row>
    </Card> : null}
    <Card>
      <Heading level={2}>Health</Heading>
      <Row><StatusPill state={human(record(runner.main_check)?.result_class ?? record(runner.main_check)?.state ?? 'no evidence')} tone={mainCheckTone(runner.main_check)} /><Label>Main check: {mainCheckSummary(runner.main_check)}</Label></Row>
      {runner.display?.needs ? <Label>{runner.display.needs}</Label> : null}
      {runner.display?.question_summary ? <Caption>{runner.display.question_summary}</Caption> : null}
      {runner.display?.blockers.map(([label, items]) => <Label key={label}>{label}: {items}</Label>)}
      {runner.job ? <Label>Current job: {jobSummary(runner.job)}</Label> : null}
      <Facts rows={observation} />
      <Row style={{ maxWidth: 260 }}>
        <Button label="Logs" compact selected={showLogs} accessibilityLabel="Runner logs" onPress={() => setShowLogs(!showLogs)} />
        <Button label="Diagnostics" compact selected={showDiagnostics} onPress={() => setShowDiagnostics(!showDiagnostics)} />
      </Row>
      {showDiagnostics ? <Stack>
        <Caption>{statusQuery.isFetching ? 'Reading…' : statusQuery.data ? `Runner status · ${relativeTime(statusQuery.data.capturedAt)}` : 'Loading…'}</Caption>
        {statusQuery.error ? <Notice tone="danger"><Label>{friendlyError(statusQuery.error)}</Label></Notice> : null}
        {statusQuery.data ? <Label mono>{statusQuery.data.text}</Label> : null}
        <Facts rows={[['Transport', 'unknown'], ['Delivery', 'unknown'], ['Held', human(runner.held)], ['Roots', human(runner.roots)], ['Waiting groups', human(runner.waiting_groups)], ['Stopped groups', human(runner.stopped_groups)], ['Maintainer', human(runner.maintainer)], ['Prepare state', human(runner.prepare_state)]]} />
        <Caption>Service liveness and configured source do not prove worker runtime identity.</Caption>
      </Stack> : null}
      {showLogs ? <Stack>
        <Row>
          <Choice label="Lines" value={logLines} options={['150', '500', '2000'] as const} onChange={setLogLines} />
          <Button label="Follow logs" compact selected={follow} onPress={() => setFollow(!follow)} />
          <Caption>{query.isFetching ? 'Refreshing…' : query.data ? relativeTime(query.data.capturedAt) : 'Loading…'}</Caption>
        </Row>
        {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
        <Label mono>{query.data?.text ?? 'Loading…'}</Label>
      </Stack> : null}
    </Card>
    <Card>
      <Heading level={2}>Runtime and policy</Heading>
      <Facts rows={facts.runtime} />
      <Caption>Observed runtime: unknown · service liveness does not prove which runtime the workers use.</Caption>
      <Facts rows={facts.policy} />
    </Card>
    {maintenance.length ? <Card>
      <Heading level={2}>Maintenance</Heading>
      {maintenance.includes('model') ? <Expand title="Service model" hint="Change the model and fallback; restarts the service.">
        <Label>Current: {display(runner.model)} · fallback: {display(runner.fallback)}</Label>
        <ModelPicker host={host} hostId={hostId} fleet={fleet} value={model} onChange={setModel} label="Model" />
        <Input label="Fallback model" value={fallback} onChange={setFallback} placeholder="optional" />
        <Button label="Change model" variant="primary" disabled={!enabled || !model.trim()} onPress={() => request({ kind: 'model', repoId: repo.id, model: model.trim(), ...(fallback.trim() ? { fallback: fallback.trim() } : {}) })} />
        <Caption>Setting a model restarts the service through Autowork.</Caption>
      </Expand> : null}
      {maintenance.includes('attention') ? <Expand title="Owner attention" hint="Record attention minutes or a note in private runner state.">
        <Input label="Minutes" value={minutes} onChange={setMinutes} placeholder="15" />
        <Input label="Attention task" value={attentionTask} onChange={setAttentionTask} placeholder="optional task ID" />
        <Input label="Attention note" value={note} onChange={setNote} multiline placeholder="optional" />
        <Button label="Record attention" variant="primary" disabled={!enabled || !(minutesValue > 0)} onPress={() => request({ kind: 'attention', repoId: repo.id, minutes: minutesValue, ...(attentionTask.trim() ? { task: attentionTask.trim() } : {}), ...(note.trim() ? { note: note.trim() } : {}) })} />
        <Caption>Recorded in private runner state, never committed.</Caption>
      </Expand> : null}
      {maintenance.includes('clear-held') ? <Expand title="Held commits" hint="Clear technical holds and return commits to integration.">
        <Label>Held: {human(runner.held)}</Label>
        <Input label="Held task IDs (empty clears all)" value={heldTasks} onChange={setHeldTasks} placeholder="T-12 T-13" />
        <Button label="Clear held commits" variant="primary" disabled={!enabled} onPress={() => request({ kind: 'clear-held', repoId: repo.id, tasks: words(heldTasks) })} />
        <Caption>Technical recovery: held commits return to integration; no owner decision is recorded.</Caption>
      </Expand> : null}
    </Card> : null}
    {runner.lanes.length ? <Card>
      <Heading level={2}>Active lanes</Heading>
      {runner.lanes.map((lane, index) => <View key={index} style={{ gap: 3, paddingVertical: 6 }}>
        <Row><Badge label={lane.phase} tone="accent" /><Label mono>{lane.task}</Label></Row>
        {lane.detail ? <Label>{lane.detail}</Label> : null}
        <Caption>{[lane.activity || null, lane.activity_age != null ? `age ${lane.activity_age}` : null, lane.minutes != null ? `${lane.minutes} min` : null, `attempt ${lane.attempt}`].filter(Boolean).join(' · ')}</Caption>
        {index < runner.lanes.length - 1 ? <Divider /> : null}
      </View>)}
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
  const [filters, setFilters] = useState<TaskFilters>(emptyFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [showCompleted, setShowCompleted] = useState(false);
  const [selected, select] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 25;
  const runner = repo.runner;
  const questions = runner?.questions ?? [];
  const editing = fleet.permissions.tasks;
  const all = (query.data?.tasks ?? []).map(task => ({ ...task, display:
    runner?.display?.revision === query.data?.revision ? runner?.display?.tasks[task.id] ?? task.display : task.display }));
  const hasFilters = Object.values(filters).some(value => value.trim());
  const counts = { open: all.filter(task => isActionable(task)).length, decisions: all.filter(task => questions.some(question => question.id === task.id)).length, blocked: all.filter(task => !!task.blocked_by && isActionable(task)).length, done: all.filter(task => !isActionable(task)).length };
  // A filter is an explicit request and searches everything; otherwise closed work stays out of the way.
  const visibleTasks = all.filter(task =>
    (!blockers || !!task.blocked_by || questions.some(question => question.id === task.id)) &&
    (hasFilters || showCompleted || isActionable(task)) &&
    taskMatches(task, filters, [task.status, task.blocked_by ?? '', runner?.lanes.find(lane => lane.task === task.id)?.phase ?? ''].join(' ')))
    .sort((a, b) => (a.goal ?? '').localeCompare(b.goal ?? ''));
  const lastPage = Math.max(0, Math.ceil(visibleTasks.length / pageSize) - 1);
  const currentPage = Math.min(page, lastPage);
  const pageStart = currentPage * pageSize;
  const pageTasks = visibleTasks.slice(pageStart, pageStart + pageSize);
  useEffect(() => { setPage(currentPage); }, [currentPage]);
  const changeFilter = (key: keyof TaskFilters, value: string) => { setFilters(existing => ({ ...existing, [key]: value })); setPage(0); };
  const activeFilters = (Object.entries(filters) as Array<[keyof TaskFilters, string]>).filter(([, value]) => value.trim());
  const common = { repo, fleet, host, hostId, enabled, request };
  const revision = query.data ? revisionParts(query.data.revision) : null;
  return <Stack gap={12}>
    {blockers ? <DecisionsCard runner={runner} onAnswer={select} /> : null}
    {/* An answer is an uncommitted record edit and the runner reads committed records, so the
        commit step belongs where the answer is recorded, not only in Tasks. */}
    {editing || fleet.permissions.commit ? <PendingCard {...common} /> : null}
    <Card>
      <Row between><Heading level={2}>{blockers ? 'Blocked tasks' : 'Task queue'}</Heading><Caption>{query.isFetching ? 'Refreshing…' : `${host.enabled && !query.isStale && !query.isError ? 'Live' : 'Cached'}${revision ? ` · ${revision.short}${revision.suffix ? ' · working tree' : ''}` : ''}`}</Caption></Row>
      {query.data ? <Caption>{plural(counts.open, 'open task')} · {counts.decisions} need decision · {counts.blocked} blocked{blockers ? '' : ` · ${counts.done} done`}{editing ? ' · working-tree records, uncommitted edits included' : ''}</Caption> : null}
      <Row>
        <Button label="Filters" compact selected={showFilters} onPress={() => setShowFilters(!showFilters)} />
        <Button label={showCompleted ? 'Hide completed' : 'Show completed'} compact selected={showCompleted} onPress={() => setShowCompleted(!showCompleted)} />
        {hasFilters ? <Button label="Clear task filters" compact onPress={() => { setFilters(emptyFilters); setPage(0); }} /> : null}
      </Row>
      {!showFilters && activeFilters.length ? <Row>{activeFilters.map(([key, value]) => <Badge key={key} label={`${key}: ${value.trim()}`} tone="accent" />)}</Row> : null}
      {showFilters ? <Row>{(['task', 'goal', 'runtime', 'section'] as const).map(key => <View key={key} style={{ flexGrow: 1, minWidth: 132 }}>
        <Input label={`Filter ${key}`} value={filters[key]} onChange={value => changeFilter(key, value)} placeholder={key === 'task' ? 'ID or title' : key === 'runtime' ? 'open, done, held…' : key} />
      </View>)}</Row> : null}
      {query.data ? <Caption>Showing {visibleTasks.length ? pageStart + 1 : 0}–{pageStart + pageTasks.length} of {visibleTasks.length} matching tasks · {all.length} total</Caption> : null}
      {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label>{query.data ? <Caption>Showing cached task data; retry when Autowork is free.</Caption> : null}<Button label="Retry" compact onPress={() => { void query.refetch(); }} /></Notice> : null}
      {pageTasks.map((task, index) => <View key={task.id} style={{ gap: 6 }}>
        {index === 0 || pageTasks[index - 1]?.goal !== task.goal ? <Heading level={3}>Goal · {task.goal ?? 'unassigned'}</Heading> : null}
        <TaskRow task={task} question={questions.some(question => question.id === task.id)} selected={selected === task.id} onOpen={() => select(selected === task.id ? '' : task.id)} onAnswer={() => select(task.id)} />
      </View>)}
      {lastPage > 0 ? <Row>
        <Button label="Previous task page" compact disabled={currentPage === 0} onPress={() => setPage(currentPage - 1)} />
        <Caption>Page {currentPage + 1} of {lastPage + 1}</Caption>
        <Button label="Next task page" compact disabled={currentPage === lastPage} onPress={() => setPage(currentPage + 1)} />
      </Row> : null}
      {!query.isFetching && !query.isError && query.data && !visibleTasks.length ? <Notice><Label>{!all.length ? 'No tasks observed.' : hasFilters ? 'No tasks match these filters.' : blockers ? 'No blocked tasks observed.' : counts.done ? 'No open tasks; completed work is hidden.' : 'No tasks observed.'}</Label></Notice> : null}
    </Card>
    <Sheet title="Task detail" open={!!selected} onClose={() => select('')}>
      {selected ? <TaskView key={selected} task={all.find(task => task.id === selected)} taskId={selected} {...common} enabled={enabled && !query.isStale && !query.isError} /> : null}
    </Sheet>
    {!blockers && editing ? <AddTaskCard {...common} /> : null}
    {!blockers && editing ? <GoalsCard {...common} /> : null}
    {!blockers ? <StoreCard {...common} /> : null}
  </Stack>;
}

function TaskRow({ task, question, selected, onOpen, onAnswer }: { task: Task; question: boolean; selected: boolean; onOpen: () => void; onAnswer: () => void }) {
  const colors = useColors();
  const closure = task.display?.closure;
  const blocked = !!task.display?.blocker;
  const meta = [task.position ? `Position ${task.position}` : null, blocked ? `Blocked by ${task.display!.blocker}` : !question && task.section ? `Section: ${task.section}` : null].filter(Boolean).join(' · ');
  // A row inside the queue, not a card inside a card.
  return <View style={{ gap: 6, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.border }}>
    <Row><Label mono>{task.id}</Label><StatusPill state={task.display?.state ?? 'unknown'} />{closure ? <Badge label={closure.label} tone={stateTone(closure.label)} /> : null}</Row>
    <Label>{task.title}</Label>
    {meta ? <Caption>{meta}</Caption> : null}
    {task.display?.why ? <Caption>{task.display.why}</Caption> : null}
    {closure && closure.detail !== task.display?.why ? <Caption>{closure.detail}</Caption> : null}
    <Row>
      {question ? <Button label="Answer" compact variant="primary" accessibilityLabel={`Answer task ${task.id}`} onPress={onAnswer} /> : null}
      <Button label={selected ? 'Hide details' : 'Details'} compact accessibilityLabel={`Open task ${task.id}`} selected={selected} onPress={onOpen} />
    </Row>
  </View>;
}

/** Decisions lead with the question and the answer action; evidence waits behind a tap. */
function DecisionsCard({ runner, onAnswer }: { runner: Runner | null; onAnswer: (task: string) => void }) {
  const questions = runner?.questions ?? [];
  return <Card tone={questions.length ? 'warning' : undefined}>
    <Row between><Heading level={2}>{questions.length ? `Decision needed · ${questions.length}` : 'No decision waiting'}</Heading></Row>
    {runner?.display?.question_summary ? <Caption>{runner.display.question_summary}</Caption> : null}
    {questions.length ? questions.map(question => <View key={question.id} style={{ gap: 6, paddingVertical: 6 }}>
      <Label bold>{headline(question.needs)}</Label>
      <Row><Label mono>{question.id}</Label><Badge label={`${question.effort} effort`} tone="neutral" /><Caption>unblocks {plural(question.unblocks, 'task')}</Caption></Row>
      {question.answer ? <Caption>Existing answer: {question.answer}</Caption> : null}
      <Row><Button label="Answer" variant="primary" compact accessibilityLabel={`Answer ${question.id}`} onPress={() => onAnswer(question.id)} /></Row>
      <Divider />
    </View>) : <Caption>No canonical owner question observed.</Caption>}
    <Expand title="Technical holds and blocker evidence">
      <Label>Held commits and stopped groups are technical state, not owner questions.</Label>
      <Facts rows={[['Held', human(runner?.held)], ['Roots', human(runner?.roots)], ['Waiting groups', human(runner?.waiting_groups)], ['Stopped groups', human(runner?.stopped_groups)], ['Main check', mainCheckSummary(runner?.main_check)]]} />
    </Expand>
  </Card>;
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
  if (!files.length && !query.error) return null;
  return <Card tone="warning">
    <Row between><Heading level={2}>Pending task edits</Heading><Caption>{query.isFetching ? 'Reading…' : `${plural(files.length, 'file')} uncommitted`}</Caption></Row>
    {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
    {files.length ? <>
      <Label mono>{files.join('\n')}</Label>
      <Expand title="Pending diff"><Label mono>{display(pending?.diff)}</Label></Expand>
      {fleet.permissions.commit ? <>
        <Input label="Commit message" value={message} onChange={setMessage} placeholder="tasks: answer T-12" />
        <Button label="Commit task edits" variant="primary" disabled={!enabled || !message.trim()} onPress={() => request({ kind: 'commit', repoId: repo.id, message: message.trim() })} />
        <Caption>Commits only tasks/ paths; other dirty files stay. No push. The runner reads committed records, so a saved answer takes effect after this commit.</Caption>
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
    <Row between><Heading level={2}>Add task</Heading><Button label={open ? 'Hide task form' : 'New task'} compact selected={open} onPress={() => setOpen(!open)} /></Row>
    {open ? <>
      {goals.data?.goals.length ? <ScrollRow>{goals.data.goals.map(item => <Button key={item.id} label={item.id} compact selected={goal === item.id} onPress={() => setGoal(item.id)} />)}</ScrollRow> : null}
      <Input label="Goal ID" value={goal} onChange={setGoal} placeholder="pick above or type" />
      <Input label="Title" value={title} onChange={setTitle} placeholder="What must be true when this is done" />
      <Input label="Short (at most 80 characters)" value={short} onChange={setShort} />
      <Choice label="Section" value={section} options={sections} onChange={setSection} />
      <Choice label="Kind" value={kind} options={kinds} onChange={setKind} />
      <Choice label="Ownership" value={ownership} options={ownerships} onChange={setOwnership} />
      <Input label="Scope" value={scope} onChange={setScope} multiline placeholder="optional" />
      <Input label="Acceptance (one per line)" value={acceptance} onChange={setAcceptance} multiline />
      <Input label="Checks (one per line)" value={checks} onChange={setChecks} multiline />
      <Input label="Touches (one per line)" value={touches} onChange={setTouches} multiline />
      <Input label="Depends on (IDs)" value={dependsOn} onChange={setDependsOn} placeholder="T-12 T-13" />
      <Button label="Add task" variant="primary" disabled={!enabled || !ready} onPress={() => request({ kind: 'task-add', repoId: repo.id, fields: {
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
    <Row between><Heading level={2}>Goals</Heading><Button label={open ? 'Hide goals' : 'Show goals'} compact selected={open} onPress={() => setOpen(!open)} /></Row>
    {open ? <>
      {!fleet.capabilities.tasks.includes('goals') ? <Notice tone="warning"><Label>The installed Autowork release lacks `tasks goals`.</Label></Notice> : null}
      {goals.error ? <Notice tone="danger"><Label>{friendlyError(goals.error)}</Label></Notice> : null}
      {goals.data?.goals.map(goal => <View key={goal.id} style={{ gap: 4, paddingVertical: 4 }}>
        <Row><Label mono>{goal.id}</Label><StatusPill state={goal.status} />{goal.focus ? <Badge label="focus" tone="accent" /> : null}{goal.priority != null ? <Caption>priority {goal.priority}</Caption> : null}</Row>
        <Label>{goal.title}</Label>
        <Row><Button label={selected?.id === goal.id ? 'Stop editing' : 'Edit'} compact accessibilityLabel={`Edit goal ${goal.id}`} selected={selected?.id === goal.id} onPress={() => choose(selected?.id === goal.id ? null : goal)} /></Row>
      </View>)}
      {!selected ? <Input label="New goal ID" value={newId} onChange={setNewId} placeholder="UPPER-CASE-ID" /> : <Caption>Editing {selected.id} at record revision {selected.record_revision}</Caption>}
      <Input label="Goal title" value={title} onChange={setTitle} />
      <Input label="Goal source (path#anchor)" value={source} onChange={setSource} placeholder="docs/plan.md#section" />
      <Input label="Goal priority" value={priority} onChange={setPriority} placeholder="10" />
      <Choice label="Goal status (unchanged when none selected)" value={status || 'unchanged'} options={['unchanged', ...goalStatuses]} onChange={value => setStatus(value === 'unchanged' ? '' : value as typeof goalStatuses[number])} />
      <Choice label="Focus" value={focus === null ? 'unchanged' : focus ? 'focus' : 'no focus'} options={['unchanged', 'focus', 'no focus']} onChange={value => setFocus(value === 'unchanged' ? null : value === 'focus')} />
      <Input label="Goal depends on (IDs)" value={dependsOn} onChange={setDependsOn} />
      <Input label="Goal evidence (for met)" value={evidence} onChange={setEvidence} />
      <Button label="Save goal" variant="primary" disabled={!enabled || !target || !changed} onPress={() => request({ kind: 'goal', repoId: repo.id, goal: target, ...(selected ? { revision: selected.record_revision } : {}), fields })} />
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
      {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
      {result ? <Label mono>{display(result)}</Label> : null}
      {fleet.permissions.tasks && view === 'prepare' && result ? <Row>
        <Button label="Prepare store (commit)" compact variant="primary" disabled={!enabled} onPress={() => request({ kind: 'store-prepare', repoId: repo.id, mode: 'commit' })} />
        <Button label="Prepare store (stage only)" compact disabled={!enabled} onPress={() => request({ kind: 'store-prepare', repoId: repo.id, mode: 'stage' })} />
        {unconverted ? <Button label="Migrate store" compact disabled={!enabled} onPress={() => request({ kind: 'store-migrate', repoId: repo.id, commit: true })} /> : null}
      </Row> : null}
      <Caption>Prepare may create one local commit; staging leaves HEAD unmoved. Neither pushes.</Caption>
    </Expand>
  </Card>;
}

function TaskView({ task, taskId, repo, fleet, host, hostId, enabled, request }: RepoViewProps & { task?: Task; taskId: string }) {
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
  const answerable = !!(task && repo.runner && detail && canAnswer(task, repo.runner, detail));
  const presentation = (detail && task?.display?.record_revision === detail.record_revision
    ? task.display : detail?.display) ?? task?.display;
  const blocked = !!presentation?.blocker;
  const state = presentation?.state ?? 'unknown';
  const meta = detail ? [detail.section ? `Section: ${detail.section}` : null, detail.goal ? `Goal: ${detail.goal}` : null].filter(Boolean).join(' · ') : '';
  const closure = presentation?.closure;
  const list = (items: string[]) => items.length ? items.map(item => `• ${item}`).join('\n') : null;
  const contract: Array<[string, string]> = detail ? ([
    ['Scope', detail.scope], ['Acceptance', list(detail.acceptance)], ['Checks', list(detail.checks)], ['Exclusions', list(detail.exclusions)],
    ['Depends on', detail.depends_on.join(', ') || null], ['Verified dependencies', detail.verified_depends_on.join(', ') || null],
    ['Touches', detail.touches.join(', ') || null], ['Resources', detail.resources.join(', ') || null],
    ['Ownership', detail.ownership], ['Kind', detail.kind], ['Live permission', detail.live],
    ['Missing fields', detail.missing_fields.join(', ') || null], ['Draft', detail.draft ? 'yes' : null],
  ] as Array<[string, string | null]>).filter((row): row is [string, string] => !!row[1]) : [];
  const closureRows: Array<[string, string]> = detail ? ['label', 'provenance', 'verified', 'evidence_valid', 'evidence', 'actor', 'timestamp', 'reason', 'waiver', 'qualification']
    .filter(key => detail.closure[key] !== undefined && detail.closure[key] !== null && detail.closure[key] !== '')
    .map(key => [key.replace(/_/g, ' '), key === 'timestamp' ? relativeTime(detail.closure[key]) : human(detail.closure[key])]) : [];
  return <Card tone={answerable ? 'warning' : undefined}>
    <View style={{ gap: 2 }}><Heading level={2}>{taskId}</Heading><Caption>{detail?.title ?? task?.title ?? 'Task detail'}</Caption></View>
    {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
    {detail ? <>
      <Row><StatusPill state={state} />{closure ? <Badge label={closure.label} tone={stateTone(closure.label)} /> : null}{meta ? <Caption>{meta}</Caption> : null}</Row>
      {presentation?.why ? <Caption>{presentation.why}</Caption> : null}
      {closure && closure.detail !== presentation?.why ? <Caption>{closure.detail}</Caption> : null}
      {answerable ? <>
        <Heading level={3}>Decision needed</Heading>
        <Markdown text={question?.needs ?? ''} />
        {question ? <Caption>{question.effort} effort · unblocks {plural(question.unblocks, 'task')}{question.answer ? ` · existing answer: ${question.answer}` : ''}</Caption> : null}
        <Input label="Owner answer" value={answer} onChange={setAnswer} multiline placeholder="Your decision, in your words. It is recorded on the task, never executed." />
        <Button label="Send answer" variant="primary" disabled={!enabled || query.isStale || !answer.trim() || !fleet.permissions.decisions} onPress={() => request({ kind: 'decision', repoId: repo.id, task: taskId, revision: detail.record_revision, text: answer })} />
        {!fleet.permissions.decisions ? <Caption>Owner answers are not granted by operator policy.</Caption> : null}
      </> : blocked ? <Notice tone="warning">
        <Label bold>Blocked by {presentation!.blocker}</Label>
        <Caption>No owner question is recorded for this task, so there is nothing to answer here. Refresh for a current blocker; a technical hold clears without an owner answer.</Caption>
      </Notice> : null}
      <Expand title="Contract and evidence">
        <Facts rows={contract} />
        {detail.notes ? <Expand title="Task notes"><Markdown text={detail.notes} /></Expand> : null}
        <Row><Caption>Contract</Caption><HashChip value={detail.contract_hash} name="contract hash" /><Caption>Record</Caption><HashChip value={detail.record_revision} name="record revision" /></Row>
        {closureRows.length ? <><Caption>Closure</Caption><Facts rows={closureRows} /></> : null}
      </Expand>
      <Expand title="Selection explanation" onToggle={setExplain}>
        {explanation.error ? <Notice tone="danger"><Label>{friendlyError(explanation.error)}</Label></Notice> : explanation.data ? <>
          <Facts rows={selectionFacts(explanation.data.value)} />
          <Expand title="Raw selection data"><Label mono>{display(explanation.data.value)}</Label></Expand>
        </> : <Caption>Reading…</Caption>}
      </Expand>
      {editing ? <TaskActions detail={detail} repo={repo} enabled={enabled && !query.isStale} request={request} /> : null}
    </> : <Caption>Loading task…</Caption>}
  </Card>;
}

type TaskEditMode = 'placement' | 'hold' | 'close' | 'supersede' | 'fields';
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
  const [mode, setMode] = useState<TaskEditMode | ''>('');
  const choose = (next: TaskEditMode) => setMode(mode === next ? '' : next);
  const open = detail.status === 'open';
  return <Expand title="Edit task">
    <Caption>Changes apply to the working-tree record at revision {detail.record_revision.slice(0, 8)}. Commit them from Pending task edits.</Caption>
    <Row>
      <Button label="Placement" compact selected={mode === 'placement'} onPress={() => choose('placement')} />
      <Button label="Hold" compact selected={mode === 'hold'} onPress={() => choose('hold')} />
      <Button label="Close task" compact selected={mode === 'close'} onPress={() => choose('close')} />
      <Button label="Supersede" compact selected={mode === 'supersede'} onPress={() => choose('supersede')} />
      <Button label="Fields" compact selected={mode === 'fields'} onPress={() => choose('fields')} />
    </Row>
    {!mode ? <Caption>Choose one change; only its form is shown.</Caption> : null}
    {mode === 'placement' ? <>
      <Choice label="Section" value={section} options={sections} onChange={setSection} />
      <Input label="Placement decision (optional)" value={placement} onChange={setPlacement} />
      <Button label="Place task" compact variant="primary" disabled={!enabled || !open} onPress={() => request({ kind: 'task-place', ...base, section, ...(placement.trim() ? { decision: placement.trim() } : {}) })} />
      <Row>
        <Button label="Move up" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-move', ...base, direction: 'up' })} />
        <Button label="Move down" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-move', ...base, direction: 'down' })} />
      </Row>
    </> : null}
    {mode === 'hold' ? <>
      <Input label="Hold by" value={holdBy} onChange={setHoldBy} placeholder="who or what holds it" />
      <Input label="Hold until (YYYY-MM-DD)" value={holdUntil} onChange={setHoldUntil} placeholder="optional" />
      <Row>
        <Button label="Hold task" compact variant="primary" disabled={!enabled || !open || !holdBy.trim()} onPress={() => request({ kind: 'task-hold', ...base, by: holdBy.trim(), ...(holdUntil.trim() ? { until: holdUntil.trim() } : {}) })} />
        <Button label="Release task" compact disabled={!enabled || !open} onPress={() => request({ kind: 'task-release', ...base })} />
      </Row>
    </> : null}
    {mode === 'close' ? <>
      <Input label="Closed by" value={doneBy} onChange={setDoneBy} placeholder="owner" />
      <Input label="Closure reason" value={reason} onChange={setReason} multiline />
      <Input label="Closure evidence reference (optional)" value={evidence} onChange={setEvidence} />
      <Button label="Mark done" compact variant="primary" disabled={!enabled || !open || !doneBy.trim() || !reason.trim()} onPress={() => request({ kind: 'task-done', ...base, by: doneBy.trim(), reason: reason.trim(), ...(evidence.trim() ? { evidence: evidence.trim() } : {}) })} />
      <Caption>A manual close records provenance; it does not verify acceptance.</Caption>
    </> : null}
    {mode === 'supersede' ? <>
      <Input label="Successor IDs" value={successors} onChange={setSuccessors} placeholder="T-12 T-13" />
      <Input label="Supersede reason" value={supersedeReason} onChange={setSupersedeReason} />
      <Button label="Supersede task" compact disabled={!enabled || !words(successors).length || !supersedeReason.trim()} onPress={() => request({ kind: 'task-supersede', ...base, by: words(successors), reason: supersedeReason.trim() })} />
    </> : null}
    {mode === 'fields' ? <>
      <Input label="Field label" value={label} onChange={setLabel} />
      <Input label="Field value (JSON array for lists)" value={value} onChange={setValue} multiline />
      <Button label="Set field" compact disabled={!enabled || !label.trim()} onPress={() => request({ kind: 'task-field', ...base, label: label.trim(), value })} />
      <Divider />
      <Button label="Delete task" compact variant="danger" disabled={!enabled} onPress={() => request({ kind: 'task-delete', ...base })} />
      <Caption>Delete removes the record only and asks for the repository name first; worktrees, commits, evidence and goals stay.</Caption>
    </> : null}
  </Expand>;
}

const modes = [['plan', 'Plan'], ['discuss', 'Discuss'], ['investigate', 'Investigate']] as const;
const modeHelp: Record<typeof modes[number][0], string> = {
  plan: 'Plan stages file proposals you can preview and apply; nothing is written until Apply.',
  discuss: 'Discuss talks the objective through without staging files.',
  investigate: 'Investigate reads the repository and reports findings without staging files.',
};
function PlanningView({ repo, fleet, host, hostId, enabled, request, sessionId, operation, objective }: RepoViewProps & { sessionId?: string; operation?: Operation; objective: string }) {
  const [text, setText] = useState(objective);
  useEffect(() => { if (!sessionId) setText(objective); }, [objective, sessionId]);
  const [view, setView] = useState<'preview' | 'history' | 'roadmap'>('preview');
  const [requested, setRequested] = useState(false);
  const [mode, setMode] = useState<'plan' | 'discuss' | 'investigate'>('plan');
  const [task, setTask] = useState('');
  const [model, setModel] = useState('');
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
  const dirty = !!(text.trim() || task.trim() || model.trim());
  return <Card>
    <Row between><Heading level={2}>Planning</Heading><Badge label={fleet.permissions.planning ? 'planning granted' : 'read-only'} tone={fleet.permissions.planning ? 'accent' : 'warning'} /></Row>
    {!fleet.permissions.planning ? <Notice tone="warning"><Label>Planning is disabled by operator policy.</Label><Caption>No client toggle grants planning authority; grants live in the daemon-side policy file.</Caption></Notice> : null}
    <Input label={sessionId ? 'Planning message' : 'Objective'} value={text} onChange={setText} multiline placeholder={sessionId ? 'Reply to the planner' : 'e.g. Reduce flaky CI runs. Leave empty to discover work.'} />
    {!sessionId ? <>
      <Choice label="Mode" value={mode} options={modes} onChange={setMode} />
      <Caption>{modeHelp[mode]}</Caption>
      <Expand title="Planning options" hint="Optional task scope and model selection.">
        <Input label="Task scope (optional)" value={task} onChange={setTask} placeholder="T-12 narrows planning to one task" />
        <ModelPicker host={host} hostId={hostId} fleet={fleet} value={model} onChange={setModel} label="Planning model (optional)" />
      </Expand>
      <Row>
        <Button label="Start planning" variant="primary" disabled={!planEnabled} onPress={() => request({ kind: 'plan-start', repoId: repo.id, objective: text, mode, ...(task.trim() ? { task: task.trim() } : {}), ...(model.trim() ? { model: model.trim() } : {}) })} />
        {dirty ? <Button label="Clear" compact variant="ghost" onPress={() => { setText(''); setTask(''); setModel(''); }} /> : null}
      </Row>
      <Caption>Planning never starts a runner. Start prepares a confirmation first; only sessions created by this backend instance are accepted.</Caption>
    </> : <>
      <Label mono>Owned session: {sessionId}</Label>
      <Row>
        <Button label="Send planning message" compact variant="primary" disabled={!planEnabled || !text.trim()} onPress={() => request({ kind: 'plan-send', repoId: repo.id, sessionId, message: text })} />
        {(['preview', 'history', 'roadmap'] as const).map(next => <Button key={next} label={`Read planning ${next}`} compact disabled={!host.enabled || busy} selected={view === next && requested} onPress={() => { setView(next); setRequested(true); if (next === view && requested) void query.refetch(); }} />)}
      </Row>
      {requested ? <>
        <Caption>{query.isFetching ? 'Reading planning…' : 'Cached planning observation; Apply revalidates the exact revision.'}</Caption>{query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
        <Expand title="Planning result">
          <Label mono>{view === 'preview' ? `Revision: ${display(value?.revision)}\nValid: ${display(value?.valid)}\nFiles: ${display(value?.files)}\nErrors: ${display(value?.errors)}\n${display(value?.diff)}` : display(query.data?.value)}</Label>
        </Expand>
      </> : null}
      {preview ? <>
        <Row><Caption>Preview revision</Caption><HashChip value={preview.revision} name="preview revision" /><Caption>{plural(preview.files.length, 'file')}</Caption></Row>
        <Button label="Apply preview" variant="primary" disabled={!planEnabled} onPress={() => request({ kind: 'plan-apply', repoId: repo.id, sessionId, revision: preview.revision })} />
      </> : <Caption>Read a valid nonempty preview before Apply.</Caption>}
    </>}
    {busy && operation?.sessionId && ['plan-start', 'plan-send'].includes(operation.kind) ? <Row>
      <Button label="Cancel planning" compact disabled={!enabled || !fleet.permissions.planning} onPress={() => request({ kind: 'plan-cancel', repoId: repo.id, operationId: operation.id })} />
      <Button label="Steer planning" compact disabled={!enabled || !fleet.permissions.planning || !text.trim()} onPress={() => request({ kind: 'plan-steer', repoId: repo.id, operationId: operation.id, message: text })} />
    </Row> : null}
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
    <Row between><Heading level={2}>Scorecard</Heading><Caption>{query.isFetching ? 'Measuring…' : query.data ? `measured ${relativeTime(query.data.capturedAt)}` : 'No model call; read-only accounting.'}</Caption></Row>
    <Choice label="Days" value={days} options={['1', '7', '14', '30'] as const} onChange={setDays} />
    {!fleet.capabilities.commands.includes('scorecard') ? <Notice tone="warning"><Label>The installed Autowork release lacks `scorecard`.</Label></Notice> : null}
    {query.error ? <Notice tone="danger"><Label>{friendlyError(query.error)}</Label></Notice> : null}
    {Object.entries(errors).map(([name, error]) => <Notice key={name} tone="warning"><Label>{name}: no metrics; {human(error)}</Label></Notice>)}
    {Object.entries(runners).map(([name, row]) => <View key={name} style={{ gap: 3, paddingVertical: 6 }}>
      <Row between><Heading level={2}>{name}</Heading><Caption>closed {human(record(row)?.closed)} · verified {human(record(row)?.verified_closed)}</Caption></Row>
      {metricLines(record(row)?.evaluation).map(line => <Caption key={line}>{line}</Caption>)}
      <Divider />
    </View>)}
    {card ? <><Heading level={2}>Overall</Heading>{metricLines(card.overall).map(line => <Caption key={line}>{line}</Caption>)}</> : null}
  </Card>;
}

/** Settled operations announced on this client; survives remounts so a toast shows once per outcome. */
const announced = new Set<string>();
const kindTitles: Record<string, string> = { control: 'Runner control', model: 'Model change', 'clear-held': 'Clear held', attention: 'Attention record', decision: 'Owner answer', commit: 'Task commit', 'plan-start': 'Planning start', 'plan-send': 'Planning message', 'plan-cancel': 'Planning cancel', 'plan-steer': 'Planning steer', 'plan-apply': 'Planning apply' };
const kindTitle = (kind: string) => kindTitles[kind] ?? (kind.startsWith('task-') ? `Task ${kind.slice(5)}` : kind.startsWith('store-') ? `Store ${kind.slice(6)}` : kind === 'goal' ? 'Goal write' : kind);
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
  return <Card compact tone={operation.status === 'failed' ? 'danger' : operation.status === 'uncertain' ? 'warning' : undefined}>
    <Row between><Row><StatusPill state={operation.status} /><Label bold>{kindTitle(operation.kind)}</Label></Row><Caption>{relativeTime(operation.completedAt ?? operation.startedAt)}</Caption></Row>
    <Label>{operation.message}</Label>
    {operation.status === 'uncertain' ? <Button label="Reconcile operation" compact disabled={!enabled} onPress={() => { void query.refetch(); }} /> : null}
    {operation.progress ? <Caption>{operation.progress}</Caption> : null}
    {operation.result !== undefined ? <Expand title="Operation result evidence"><Label mono>{display(operation.result)}</Label></Expand> : null}
    {query.error ? <Notice tone="danger"><Label>Status unavailable; delivery unknown. No replay: {friendlyError(query.error)}</Label></Notice> : null}
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
