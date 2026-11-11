// @ts-check
const core = require('./core.cjs');
/** @type {import('@t3tools/plugin-sdk/server').PluginDefinition<import('./rpc.ts').AutoworkRpc>} */
module.exports = {
  activate(api) {
    const lifecycle = new AbortController();
    api.onDeactivate(() => lifecycle.abort());
    let active = 0;
    api.rpc.register('repositories', async () => core.config(await api.settings.get()).repositories.map(({ id, label }) => ({ id, label })), { access: 'read' });
    api.rpc.register('snapshot', async (input, context) => {
      const request = core.object(input);
      if (Object.keys(request).length !== 1 || typeof request.repository !== 'string' || !/^[a-f0-9]{24}$/.test(request.repository)) throw new Error('Select a configured repository');
      const cfg = core.config(await api.settings.get());
      const repo = cfg.repositories.find(r => r.id === request.repository);
      if (!repo) throw new Error('Repository is no longer configured; refresh the panel');
      if (active >= 2) throw new Error('Autowork is busy; refresh shortly');
      active++;
      const signal = AbortSignal.any([context.signal, lifecycle.signal]);
      try {
        // Sequential reads keep process concurrency at two and total time below host RPC deadline.
        const fleet = core.json(await core.run(cfg.executable, ['ls', '--json'], signal));
        const list = core.json(await core.run(cfg.executable, ['tasks', 'list', repo.root], signal));
        const logs = await core.run(cfg.executable, ['logs', repo.root, '--lines', '60'], signal);
        const result = { repository: repo.id, capturedAt: new Date().toISOString(), ...core.runnerDisplay(fleet, repo.root), tasks: core.tasks(list), logs: core.text(logs, 24000) };
        if (Buffer.byteLength(JSON.stringify(result)) > 240000) throw new Error('Snapshot exceeds transport limit; narrow repository output');
        return result;
      } finally { active--; }
    }, { access: 'read' });
  },
};
