import type { PluginServerContext } from '@getpaseo/plugin/server';
import { fleetRpc, tasksRpc, taskRpc, goalsRpc, logsRpc, statusRpc, scorecardRpc, modelsRpc, storeRpc, watchRpc, prepareRpc, commitRpc, operationRpc, planningRpc } from './shared/contracts';
import { AutoworkService } from './server/autowork-client';
import { loadConfig, resolveProgram } from './server/config';
import { Operations } from './server/operations';
import { PlanningManager } from './server/planning';
import path from 'node:path';
import process from 'node:process';
import { homedir } from 'node:os';

export default function contribute(server: PluginServerContext) {
  let closed = false;
  let resources: Promise<{ service: AutoworkService; operations: Operations }> | null = null;
  const get = () => {
    if (closed) return Promise.reject(new Error('Autowork plugin is disabled'));
    resources ??= (async () => {
      const config = await loadConfig();
      const service = new AutoworkService(config);
      const operations = new Operations(service, async () => new PlanningManager({
        source: await service.source(), python: await resolveProgram('python3'),
        stateRoot: path.join(process.env.XDG_STATE_HOME ?? path.join(homedir(), '.local/state'),
          'paseo-autowork', 'planning', service.instance),
      }));
      return { service, operations };
    })();
    return resources;
  };
  server.handle(fleetRpc, async () => (await get()).service.fleet());
  server.handle(tasksRpc, async input => (await get()).service.tasks(input.instance, input.repoId, (await get()).service.policy.tasks));
  server.handle(taskRpc, async input => (await get()).service.task(input.instance, input.repoId, input.task, input.working));
  server.handle(goalsRpc, async input => (await get()).service.goals(input.instance, input.repoId, (await get()).service.policy.tasks));
  server.handle(logsRpc, async input => (await get()).service.logs(input.instance, input.repoId, input.lines));
  server.handle(statusRpc, async input => (await get()).service.status(input.instance, input.repoId));
  server.handle(scorecardRpc, async input => (await get()).service.scorecard(input.instance, input.days));
  server.handle(modelsRpc, async input => (await get()).service.models(input.instance));
  server.handle(storeRpc, async input => (await get()).service.store(input.instance, input.repoId, input.view, input.task));
  server.handle(watchRpc, async input => (await get()).service.watch(input.instance, input.digest));
  server.handle(prepareRpc, async input => (await get()).operations.prepare(input.instance, input.action));
  server.handle(commitRpc, async input => (await get()).operations.commit(input.instance, input.ticket));
  server.handle(operationRpc, async input => (await get()).operations.read(input.instance, input.id));
  server.handle(planningRpc, async input => (await get()).operations.planning(input.instance, input.repoId, input.sessionId, input.view));
  return async () => {
    closed = true;
    if (!resources) return;
    const owned = await resources;
    try { await owned.operations.close(); }
    finally { await owned.service.close(); }
  };
}
