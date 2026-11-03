import { access, lstat, readFile, realpath } from 'node:fs/promises';
import { constants } from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { z } from 'zod';
import { controlSchema } from '../shared/contracts';

export const configSchema = z.strictObject({
  executable: z.string().optional(), repositories: z.array(z.string()).max(32).default([]),
  planning: z.boolean().default(false), decisions: z.boolean().default(false),
  controls: z.array(controlSchema).default([]),
});
export type Config = z.infer<typeof configSchema>;
export async function loadConfig(env: NodeJS.ProcessEnv = process.env): Promise<Config> {
  const file = env.PASEO_AUTOWORK_CONFIG;
  if (!file) return configSchema.parse({});
  if (!path.isAbsolute(file)) throw new Error('PASEO_AUTOWORK_CONFIG must be absolute');
  const stat = await lstat(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536 || (stat.mode & 0o022) !== 0
      || (process.getuid && stat.uid !== process.getuid())) throw new Error('Autowork policy must be a private, owner-controlled regular file');
  return configSchema.parse(JSON.parse(await readFile(file, 'utf8')));
}
export async function resolveExecutable(configured?: string, env: NodeJS.ProcessEnv = process.env): Promise<string> {
  return resolveProgram('autowork', configured, env);
}
export async function resolveProgram(program: 'autowork' | 'python3', configured?: string, env: NodeJS.ProcessEnv = process.env): Promise<string> {
  const candidates = configured ? [configured] : (env.PATH ?? '').split(path.delimiter).filter(Boolean).map(p => path.join(p, program));
  if (configured && !path.isAbsolute(configured)) throw new Error('Autowork executable must be absolute');
  for (const candidate of candidates) {
    if (!path.isAbsolute(candidate)) continue;
    try {
      const resolved = await realpath(candidate); const stat = await lstat(resolved);
      if (!stat.isFile()) continue;
      await access(resolved, constants.X_OK); return resolved;
    } catch { if (configured) break; }
  }
  throw new Error(`${program} executable unavailable on this daemon host; configure an absolute executable`);
}
