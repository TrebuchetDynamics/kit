import { useEffect, useRef, useState } from 'react';
import type { PluginClientContext, PluginSidebarItemProps } from '@getpaseo/plugin/client';
import { useRpc } from '@getpaseo/plugin/client';
import { SidebarRow } from '@getpaseo/plugin/client/ui';
import { fleetRpc } from './shared/contracts';
import { AgentPanel, AutoworkScreen, WorkspacePanel } from './client/screens';
import { SettingsScreen } from './client/settings';

/** The sidebar row carries the pending-decision total for the selected host, refreshed each minute. */
function FleetItem({ host, currentScreen, openScreen }: PluginSidebarItemProps) {
  const read = useRpc(fleetRpc);
  const call = useRef(read); call.current = read;
  const [decisions, setDecisions] = useState<number | null>(null);
  useEffect(() => {
    let active = true;
    const tick = async () => {
      try { const fleet = await call.current({}); if (active) setDecisions(fleet.repos.reduce((sum, repo) => sum + (repo.runner?.decisions ?? 0), 0)); }
      catch { if (active) setDecisions(null); }
    };
    void tick();
    const timer = setInterval(() => { void tick(); }, 60000);
    return () => { active = false; clearInterval(timer); };
  }, [host.id]);
  return <SidebarRow icon="ListTodo" label={decisions ? `Autowork · ${decisions} to decide` : 'Autowork'} active={currentScreen?.screenId === 'autowork'} onPress={() => openScreen({ screenId: 'autowork' })} />;
}

export default function contribute(client: PluginClientContext) {
  const cleanups = [
    client.addScreen({ id: 'autowork', title: 'Autowork', Component: AutoworkScreen }),
    client.addSettingsScreen({ id: 'aw-grants', title: 'Autowork grants', icon: 'ShieldCheck', Component: SettingsScreen }),
    client.addSidebarHeaderItem({ id: 'aw-fleet', title: 'Autowork', Component: FleetItem }),
    client.addWorkspacePanel({ id: 'aw-workspace', title: 'Autowork', icon: 'ListTodo', Component: WorkspacePanel }),
    client.addAgentPanel({ id: 'aw-agent', title: 'Autowork', icon: 'ListTodo', Component: AgentPanel }),
    client.addCommandCenterItem({ id: 'aw-open', title: 'Autowork fleet', icon: 'ListTodo', context: 'global', keywords: ['runner', 'tasks', 'planning', 'blockers'], onSelect: context => context.openScreen({ screenId: 'autowork' }) }),
    client.addCommandCenterItem({ id: 'aw-grants', title: 'Autowork grants', icon: 'ShieldCheck', context: 'global', keywords: ['policy', 'settings'], onSelect: context => context.openSettings('aw-grants') }),
    client.addCommandCenterItem({ id: 'aw-scorecard', title: 'Autowork scorecard', icon: 'ListTodo', context: 'global', keywords: ['metrics', 'evaluation'], onSelect: context => context.openScreen({ screenId: 'autowork', params: { view: 'scorecard' } }) }),
    ...([
      ['aw-open-health', 'Runner health', 'runner'], ['aw-open-tasks', 'Task queue', 'tasks'],
      ['aw-open-blockers', 'Review blockers', 'blockers'], ['aw-open-plan', 'Plan this repository', 'planning'],
    ] as const).map(([id, title, view]) => client.addCommandCenterItem({ id, title: `Autowork: ${title}`, icon: 'ListTodo', context: 'workspace',
      onSelect: context => context.openScreen({ screenId: 'autowork', params: { view, directory: context.workspace.directory } }) })),
    ...([
      ['aw-status', 'fleet'], ['aw-tasks', 'tasks'], ['aw-plan', 'planning'], ['aw-blockers', 'blockers'],
    ] as const).map(([name, view]) => client.addSlashCommand({ name, description: `Open Autowork ${view}`, argumentHint: view === 'planning' ? '[objective]' : '', context: 'workspace', onSubmit: context => context.openScreen({ screenId: 'autowork', params: { view, directory: context.workspace.directory, ...(view === 'planning' ? { objective: context.args } : {}) } }) })),
  ];
  let disposed = false;
  return async () => {
    if (disposed) return;
    disposed = true;
    // Run every cleanup even if an individual host cleanup fails.
    const results = await Promise.allSettled(cleanups.reverse().map(cleanup => Promise.resolve().then(cleanup)));
    const failed = results.find(result => result.status === 'rejected');
    if (failed?.status === 'rejected') throw failed.reason;
  };
}
