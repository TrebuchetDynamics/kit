import type { PluginSurfaceProps } from '@getpaseo/plugin/client';
import { View } from 'react-native';
import { useHostState } from './state';
import { Badge, Caption, Expand, Heading, KeyValue, Label, Notice, Row, Stack, Theme } from './ui';

/** Read-only: grants come only from the daemon-side policy file; nothing here can change them. */
export function SettingsScreen(props: PluginSurfaceProps) {
  return <Theme.Provider value={props.theme}><SettingsContent key={props.host.id} hostId={props.host.id} label={props.host.label} compact={props.layout.compact} /></Theme.Provider>;
}
function SettingsContent({ hostId, label, compact }: { hostId: string; label: string; compact: boolean }) {
  const host = useHostState(hostId);
  const fleet = host.fleet.data;
  const grants = fleet ? [
    ['planning', fleet.permissions.planning], ['owner answers', fleet.permissions.decisions], ['task edits', fleet.permissions.tasks],
    ['task-store commits', fleet.permissions.commit], ['runner controls', fleet.permissions.controls.length > 0], ['runner maintenance', fleet.permissions.maintenance.length > 0],
  ] as const : [];
  return <View style={{ gap: 12, padding: compact ? 4 : 8 }}>
    <Heading>Autowork grants on {label}</Heading>
    <Caption>The daemon operator's policy file is the only source of grants. This screen shows the effective grants; no client control changes them.</Caption>
    {!host.online ? <Notice tone="warning"><Label>Host offline: no live policy observation.</Label></Notice> : null}
    {host.fleet.error ? <Notice tone="danger"><Label>{host.fleet.error.message}</Label></Notice> : null}
    {fleet ? <Stack gap={10}>
      <Row>{grants.map(([name, granted]) => <Badge key={name} label={`${name}: ${granted ? 'granted' : 'denied'}`} tone={granted ? 'success' : 'neutral'} />)}</Row>
      <KeyValue name="Controls" value={fleet.permissions.controls.length ? fleet.permissions.controls.join(', ') : 'none'} />
      <KeyValue name="Maintenance" value={fleet.permissions.maintenance.length ? fleet.permissions.maintenance.join(', ') : 'none'} />
      <KeyValue name="Policy file" value={fleet.policy.path ?? 'none'} mono />
      <KeyValue name="Policy source" value={fleet.policy.source === 'environment' ? 'PASEO_AUTOWORK_CONFIG in the daemon environment' : fleet.policy.source === 'default' ? 'default path, loaded' : 'no policy file: read-only'} />
      <KeyValue name="Executable" value={fleet.executable} mono />
      <KeyValue name="Toolset" value={fleet.toolset || 'unknown'} mono />
      <KeyValue name="Release" value={fleet.release} mono />
      <KeyValue name="Prepare API" value={String(fleet.prepareApi)} />
      <Expand title="Installed commands and task verbs">
        <Label>Commands: {fleet.capabilities.commands.join(', ') || 'unknown'}</Label>
        <Label>Task verbs: {fleet.capabilities.tasks.join(', ') || 'unknown'}</Label>
        <Caption>An action whose command or verb is missing here is refused before dispatch.</Caption>
      </Expand>
      <Notice>
        <Label>To grant: write a JSON policy at the policy file path above (or at the path named by PASEO_AUTOWORK_CONFIG), owned by the daemon user with mode 0600, then reload this plugin.</Label>
        <Label mono>{'{ "all": true, "executable": "/absolute/path/to/autowork" }'}</Label>
        <Caption>Selective keys: planning, decisions, tasks, commit, controls [start, pause, resume, stop, restart, remove, update], maintenance [model, clear-held, attention], repositories [paths].</Caption>
      </Notice>
    </Stack> : <Caption>{host.enabled ? 'Loading policy…' : 'No live observation.'}</Caption>}
  </View>;
}
