// Pi 1.5.0 public ModelRuntime/AuthInteraction contract. No sessions or model calls.
import { createInterface } from 'node:readline';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const emit = value => process.stdout.write(JSON.stringify(value) + '\n');
const controller = new AbortController();
let waiting;
let promptSequence = 0;
const input = createInterface({ input: process.stdin });
input.on('line', line => {
  try {
    const message = JSON.parse(line);
    if (message.type === 'cancel') controller.abort();
    else if (message.type === 'answer' && waiting && message.id === waiting.id) waiting.resolve(message.value);
  } catch { controller.abort(); }
});
input.on('close', () => controller.abort());
process.on('SIGTERM', () => controller.abort());

try {
  const root = process.env.AUTOWORK_PI_SDK;
  const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
  if (pkg.name !== '@earendil-works/pi-coding-agent' || pkg.version !== '1.5.0') throw Error();
  const { ModelRuntime, readStoredCredential } = await import(pathToFileURL(join(root, 'dist/index.js')).href);
  const directory = process.env.PI_CODING_AGENT_DIR;
  // No catalog network refresh, credential resolution, token refresh or commands on open.
  const listing = process.argv[2] === 'catalog';
  const readOnly = {
    read: async id => readStoredCredential(id, join(directory, 'auth.json')),
    list: async () => [],
    modify: async () => { throw new Error('Read only'); },
    delete: async () => { throw new Error('Read only'); },
  };
  const runtime = await ModelRuntime.create({
    ...(listing ? { credentials: readOnly } : {}),
    authPath: join(directory, 'auth.json'), modelsPath: join(directory, 'models.json'),
    refreshOnCreate: false, allowModelNetwork: false,
  });
  const providers = runtime.getProviders();
  if (listing) {
    const stored = new Map(providers.map(p => [p.id, readStoredCredential(p.id, join(directory, 'auth.json'))?.type])
      .filter(([, type]) => ['api_key', 'oauth'].includes(type)));
    emit({ type: 'catalog', providers: providers.map(p => ({
      id: p.id, name: p.name || p.id, state: stored.has(p.id) ? 'stored ' + stored.get(p.id) : 'not stored',
      methods: [p.auth.oauth?.login && 'oauth', p.auth.apiKey?.login && 'api_key'].filter(Boolean),
    })) });
  } else {
    const provider = providers.find(p => p.id === process.argv[3]);
    const method = process.argv[4];
    if (!provider || !['oauth', 'api_key'].includes(method) ||
        !(method === 'oauth' ? provider.auth.oauth?.login : provider.auth.apiKey?.login)) throw Error();
    const interaction = {
      signal: controller.signal,
      notify: event => {
        // Status text comes from the provider, never forward arbitrary exceptions/credentials.
        if (event.type === 'auth_url') emit({ type: 'url', url: event.url });
        else if (event.type === 'device_code') emit({ type: 'device', url: event.verificationUri, code: event.userCode });
        else emit({ type: 'progress' });
      },
      prompt: prompt => new Promise((resolve, reject) => {
        const id = ++promptSequence;
        const signal = prompt.signal ? AbortSignal.any([controller.signal, prompt.signal]) : controller.signal;
        const abort = () => {
          if (waiting?.resolve === answer) {
            waiting = undefined;
            emit({ type: 'clear_prompt', id });
          }
          reject(new Error('Cancelled'));
        };
        const answer = value => {
          signal.removeEventListener('abort', abort);
          waiting = undefined;
          if (typeof value !== 'string' || !value.trim()) { reject(new Error('Empty answer')); return; }
          // Pi interprets ! values as executable configuration; secret entry must be literal.
          if (prompt.type === 'secret' && value.startsWith('!')) { reject(new Error('Command key')); return; }
          resolve(value);
        };
        waiting = { id, resolve: answer };
        signal.addEventListener('abort', abort, { once: true });
        if (signal.aborted) { abort(); return; }
        emit({ type: 'prompt', id, kind: prompt.type, message: prompt.message,
               options: prompt.type === 'select' ? prompt.options.map(o => ({ id: o.id, label: o.label })) : [] });
      }),
    };
    await runtime.login(provider.id, method, interaction, { signal: controller.signal });
    emit({ type: 'success' });
  }
} catch {
  emit({ type: 'error', message: controller.signal.aborted ? 'Authentication cancelled.' :
    'Pi authentication unavailable or failed. Check the SDK, provider and credentials, then retry.' });
  process.exitCode = 1;
} finally { input.close(); }
