import { describe, expect, it } from 'vitest';
import { createRequire } from 'node:module';
import { URL, fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { writeFile } from 'node:fs/promises';
import process from 'node:process';
import { fixture, cleanupFixtures } from './fixture';

// Pinned official compiler/runtime are test-only dependencies, not bundled with the plugin.
const require = createRequire(import.meta.url);
const plugins = path.join(path.dirname(require.resolve('@getpaseo/server')), 'plugins');
const root = fileURLToPath(new URL('../', import.meta.url));
const official = async (name: string) => import(pathToFileURL(path.join(plugins, name + '.js')).href);

describe('official Paseo 0.13 compatibility', () => {
  it('compiles both native/client and daemon bundles with the real boundary checker', async () => {
    const { readPluginManifest } = await official('manifest');
    const { compilePlugin } = await official('compiler');
    const manifest = await readPluginManifest(root);
    expect(manifest.id).toBe('paseo-autowork');
    const bundles = await compilePlugin({ client: path.join(root, 'index.client.tsx'), server: path.join(root, 'index.server.ts') });
    expect(bundles.clientBundle).toContain('autowork');
    expect(bundles.serverBundle).toContain('autowork.fleet');
    expect(bundles.clientBundle).not.toContain('node:child_process');
  }, 30000);

  it('loads the actual server in an isolated runtime, validates RPC, stops and reloads cleanly', async () => {
    const { PluginRuntime } = await official('runtime');
    const pino = require('pino'); const f = await fixture();
    const config = path.join(f.root, 'policy.json');
    await writeFile(config, JSON.stringify({ executable: f.exe }), { mode: 0o600 });
    const previous = process.env.PASEO_AUTOWORK_CONFIG;
    process.env.PASEO_AUTOWORK_CONFIG = config;
    const sockets = new Set<any>();
    const runtime = new PluginRuntime(pino({ level: 'silent' }), '0.13.0', {
      sessionHost: { async attachPluginSocket(_pluginId: string, socket: any) {
        sockets.add(socket);
        const closed = new Promise<void>(resolve => socket.once('close', () => { sockets.delete(socket); resolve(); }));
        socket.on('message', (data: unknown) => {
          if (typeof data !== 'string' || JSON.parse(data).type !== 'hello') return;
          socket.send(JSON.stringify({ type: 'session', message: { type: 'status', payload: {
            status: 'server_info', serverId: 'isolated-test', hostname: 'isolated-test', version: '0.13.0', features: {},
          } } }));
        });
        return { closed };
      } },
    });
    try {
      await runtime.startPlugin('paseo-autowork', root);
      expect(runtime.catalog()).toHaveLength(1);
      const fleet = await runtime.invoke('paseo-autowork', 'autowork.fleet', {});
      expect(fleet.permissions).toEqual({ planning: false, decisions: false, tasks: false, commit: false, controls: [], maintenance: [] });
      expect(fleet.policy).toEqual({ path: config, source: 'environment' });
      expect(fleet.repos).toHaveLength(1);
      await expect(runtime.invoke('paseo-autowork', 'autowork.prepare', {
        instance: fleet.instance, action: { kind: 'control', repoId: fleet.repos[0].id, action: 'pause' },
      })).rejects.toThrow(/[Rr]ead.only|not allowed/);
      await expect(runtime.invoke('paseo-autowork', 'autowork.fleet', { arbitrary: 'input' })).rejects.toThrow();
      await runtime.stopPluginById('paseo-autowork');
      expect(runtime.catalog()).toHaveLength(0); expect(sockets.size).toBe(0);
      await runtime.startPlugin('paseo-autowork', root);
      const next = await runtime.invoke('paseo-autowork', 'autowork.fleet', {});
      expect(next.instance).not.toBe(fleet.instance);
      await expect(runtime.invoke('paseo-autowork', 'autowork.tasks', { instance: fleet.instance, repoId: fleet.repos[0].id })).rejects.toThrow(/generation/);
    } finally {
      await runtime.stopAll();
      if (previous === undefined) delete process.env.PASEO_AUTOWORK_CONFIG; else process.env.PASEO_AUTOWORK_CONFIG = previous;
      await cleanupFixtures();
    }
    expect(sockets.size).toBe(0);
  }, 30000);
});
