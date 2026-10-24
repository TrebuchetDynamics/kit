import { describe, expect, it, vi } from 'vitest';
import type { PluginClientContext, PluginClientSlashCommandContribution, PluginCommandCenterItemContribution } from '@getpaseo/plugin/client';
vi.mock('react-native', () => ({ Pressable: () => null, Text: () => null, View: () => null }));
vi.mock('../client/screens', () => ({ AutoworkScreen: () => null, WorkspacePanel: () => null, AgentPanel: () => null }));
vi.mock('@getpaseo/plugin/client/ui', () => ({ SidebarRow: () => null }));
import contribute from '../index.client';

describe('native contributions', () => {
  it('uses valid non-overriding IDs, navigates only, and cleans up every registration once', async () => {
    const records: Array<{ kind: string; value: Record<string, unknown>; cleanup: ReturnType<typeof vi.fn> }> = [];
    const client = Object.fromEntries(['addScreen', 'addSidebarHeaderItem', 'addWorkspacePanel', 'addAgentPanel', 'addCommandCenterItem', 'addSlashCommand'].map(kind => [kind, (value: Record<string, unknown>) => {
      const cleanup = vi.fn(); records.push({ kind, value, cleanup }); return cleanup;
    }])) as unknown as PluginClientContext;
    const dispose = contribute(client);
    expect(records.filter(r => r.kind === 'addScreen').map(r => r.value.id)).toEqual(['autowork']);
    expect(records.filter(r => r.kind === 'addWorkspacePanel')).toHaveLength(1);
    expect(records.filter(r => r.kind === 'addAgentPanel')).toHaveLength(1);
    for (const record of records) {
      const id = record.value.id ?? record.value.name;
      expect(id).toMatch(/^[a-z][a-z0-9-]*$/);
      expect(record.value).not.toHaveProperty('override');
    }
    const slash = records.filter(r => r.kind === 'addSlashCommand');
    expect(slash.map(r => r.value.name)).toEqual(['aw-status', 'aw-tasks', 'aw-plan', 'aw-blockers']);
    const context = { openScreen: vi.fn(), rpc: vi.fn(), args: 'objective; not a command', workspace: { directory: '/repo' } };
    for (const record of slash) await (record.value as unknown as Extract<PluginClientSlashCommandContribution, { context: 'workspace' }>).onSubmit(context as never);
    const command = records.find(r => r.kind === 'addCommandCenterItem')!;
    await (command.value as unknown as Extract<PluginCommandCenterItemContribution, { context: 'global' }>).onSelect(context as never);
    expect(context.openScreen).toHaveBeenCalledTimes(5); expect(context.rpc).not.toHaveBeenCalled();
    expect(context.openScreen.mock.calls[2]?.[0]).toEqual({ screenId: 'autowork', params: { view: 'planning', directory: '/repo', objective: context.args } });
    await dispose(); await dispose();
    for (const record of records) expect(record.cleanup).toHaveBeenCalledTimes(1);
  });
});
