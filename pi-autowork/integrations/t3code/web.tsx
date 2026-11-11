import { useEffect, useId, useState } from 'react';
import { defineWebPlugin, type WebPluginApi } from '@t3tools/plugin-sdk/web';
import type { AutoworkRpc, Repository, Snapshot } from './rpc';

const css = `
.aw-t3 { color:var(--foreground); background:var(--background); padding:20px; font:14px/1.5 system-ui,sans-serif; min-width:0; }
.aw-t3 * { box-sizing:border-box; }
.aw-t3 h2 { font-size:23px; letter-spacing:-.03em; margin:6px 0; }
.aw-t3 h3 { font-size:12px; text-transform:uppercase; letter-spacing:.08em; margin:22px 0 8px; }
.aw-t3 p { margin:6px 0; overflow-wrap:anywhere; }
.aw-t3 .aw-muted { color:var(--muted-foreground); font-size:12px; }
.aw-t3 .aw-top { display:flex; justify-content:space-between; align-items:center; gap:12px; }
.aw-t3 button, .aw-t3 select { font:inherit; color:var(--foreground); background:var(--background); border:1px solid var(--border); border-radius:var(--radius); padding:8px 10px; min-height:38px; }
.aw-t3 button { cursor:pointer; }
.aw-t3 button:hover { background:var(--accent); }
.aw-t3 button:disabled { opacity:.55; cursor:wait; }
.aw-t3 :is(button,select):focus-visible { outline:2px solid var(--ring); outline-offset:3px; }
.aw-t3 select { width:100%; margin-top:6px; }
.aw-t3 .aw-summary { background:var(--muted); border-left:3px solid var(--primary); padding:12px; margin:16px 0; border-radius:var(--radius); }
.aw-t3 ul { list-style:none; padding:0; margin:0; }
.aw-t3 li { padding:10px 0; border-bottom:1px solid var(--border); overflow-wrap:anywhere; }
.aw-t3 .aw-task { width:100%; text-align:left; display:block; border:0; padding:4px; }
.aw-t3 .aw-task[aria-pressed=true] { background:var(--accent); }
.aw-t3 .aw-task strong { display:block; font-size:13px; }
.aw-t3 .aw-task span { display:block; color:var(--muted-foreground); font-size:12px; }
.aw-t3 pre { white-space:pre-wrap; overflow-wrap:anywhere; font:11px/1.6 ui-monospace,monospace; max-height:340px; overflow:auto; border:1px solid var(--border); padding:12px; }
.aw-t3 summary { cursor:pointer; padding:10px 0; }
.aw-t3 [role=alert] { border:1px solid var(--destructive); padding:12px; margin:16px 0; border-radius:var(--radius); }
`;

export function Panel({ api, subscribeRefresh }: {
  api: Pick<WebPluginApi<AutoworkRpc>, 'rpc'>;
  subscribeRefresh: (refresh: () => void) => () => void;
}) {
  const selectId = useId();
  const [selected, select] = useState('');
  const [revision, refresh] = useState(0);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [taskId, selectTask] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => subscribeRefresh(() => refresh(n => n + 1)), [subscribeRefresh]);
  useEffect(() => {
    let current = true;
    setLoading(true); setError(''); setSnapshot(null); selectTask('');
    void (async () => {
      try {
        const repos = await api.rpc.invoke('repositories');
        if (!current) return;
        setRepositories(repos);
        const target = repos.find(r => r.id === selected) ?? repos[0];
        if (!target) return;
        const result = await api.rpc.invoke('snapshot', { repository: target.id });
        if (current) setSnapshot(result);
      } catch {
        // RPC errors may include private host paths. Keep the UI actionable and generic.
        if (current) setError('Unable to read Autowork. Check the plugin’s executable and repository settings, then retry. The installed CLI must expose canonical display fields.');
      } finally { if (current) setLoading(false); }
    })();
    return () => { current = false; };
  }, [api, selected, revision]);
  const task = snapshot?.tasks.find(t => t.id === taskId);
  return <section className="aw-t3" aria-label="Autowork overview" aria-busy={loading}>
    <div className="aw-top"><div><p className="aw-muted">REPOSITORY WORK · READ ONLY</p><h2>Autowork</h2></div>
      <button disabled={loading} onClick={() => refresh(n => n + 1)}>Refresh</button></div>
    <p className="aw-muted">Inspect work here. Use the existing Autowork CLI for authorized changes.</p>
    <div style={{ marginTop: 20 }}><label htmlFor={selectId}>Repository</label>
      <select id={selectId} value={snapshot?.repository ?? (repositories.some(r => r.id === selected) ? selected : repositories[0]?.id ?? '')}
        onChange={e => select(e.currentTarget.value)} disabled={!repositories.length}>
        {!repositories.length && <option value="">No configured repositories</option>}
        {repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.label}</option>)}
      </select></div>
    {loading && <p role="status">Reading repository work…</p>}
    {error && <div role="alert"><p>{error}</p><button onClick={() => refresh(n => n + 1)}>Retry</button></div>}
    {!loading && !error && !repositories.length && <div className="aw-summary"><strong>Add a repository</strong>
      <p>Open Settings → Plugins → Autowork and configure a trusted executable and repository paths.</p></div>}
    {snapshot && <>
      <div className="aw-summary"><strong>{snapshot.state}</strong><p>{snapshot.needs || 'No next action reported by Autowork.'}</p></div>
      <p className="aw-muted">Snapshot {snapshot.capturedAt} · Refresh to check current state.</p>
      <h3>Blockers · {snapshot.blockers.length}</h3>
      {snapshot.blockers.length ? <ul>{snapshot.blockers.map((b, i) => <li key={i}>{b}</li>)}</ul> : <p className="aw-muted">No blockers reported.</p>}
      <h3>Tasks · first {snapshot.tasks.length}</h3>
      {snapshot.tasks.length ? <ul>{snapshot.tasks.map(t => <li key={t.id}>
        <button className="aw-task" aria-pressed={t.id === taskId} onClick={() => selectTask(t.id)}>
          <strong>{t.title}</strong><span>{t.id} · {t.state}</span></button></li>)}</ul> : <p className="aw-muted">No committed tasks reported.</p>}
      {task && <div className="aw-summary"><strong>{task.id} · Selected task</strong><p>{task.why || 'No additional task guidance reported.'}</p></div>}
      <h3>Recent activity</h3><details><summary>Read latest logs · up to 60 lines</summary>
        {snapshot.logs ? <pre tabIndex={0} aria-label="Recent Autowork logs">{snapshot.logs}</pre> : <p>No recent logs reported.</p>}</details>
    </>}
  </section>;
}

export default defineWebPlugin<AutoworkRpc>({
  activate(api) {
    api.injectStyles(css);
    const listeners = new Set<() => void>();
    const subscribeRefresh = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
    api.onDeactivate(() => listeners.clear());
    api.rightPanel.register({ name: 'overview', title: 'Autowork', component: () => <Panel api={api} subscribeRefresh={subscribeRefresh} /> });
    api.commands.register({ id: 'refresh', title: 'Autowork: refresh overview', keywords: ['tasks', 'blockers', 'repository'], run: () => {
      listeners.forEach(fn => fn());
      if (!listeners.size) api.toast({ title: 'Open Autowork in the right panel', description: 'Choose Autowork from the thread’s panel add menu.' });
    } });
  },
});
