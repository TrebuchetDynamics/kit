import type { PluginClientContext, PluginSidebarItemProps } from '@getpaseo/plugin/client';
import { SidebarRow } from '@getpaseo/plugin/client/ui';
import { AgentPanel, AutoworkScreen, WorkspacePanel } from './client/screens';

function FleetItem({ currentScreen, openScreen }: PluginSidebarItemProps) {
  return <SidebarRow icon="ListTodo" label="Autowork" active={currentScreen?.screenId === 'autowork'} onPress={() => openScreen({ screenId: 'autowork' })} />;
}

export default function contribute(client: PluginClientContext) {
  const cleanups = [
    client.addScreen({ id: 'autowork', title: 'Autowork', Component: AutoworkScreen }),
    client.addSidebarHeaderItem({ id: 'aw-fleet', title: 'Autowork', Component: FleetItem }),
    client.addWorkspacePanel({ id: 'aw-workspace', title: 'Autowork', icon: 'ListTodo', Component: WorkspacePanel }),
    client.addAgentPanel({ id: 'aw-agent', title: 'Autowork', icon: 'ListTodo', Component: AgentPanel }),
    client.addCommandCenterItem({ id: 'aw-open', title: 'Autowork fleet', icon: 'ListTodo', context: 'global', keywords: ['runner', 'tasks', 'planning', 'blockers'], onSelect: context => context.openScreen({ screenId: 'autowork' }) }),
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
