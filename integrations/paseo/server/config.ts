import { access, lstat, readFile, realpath } from 'node:fs/promises';
import { constants } from 'node:fs';
import { homedir } from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { z } from 'zod';
import { ALL_CONTROLS, ALL_MAINTENANCE, controlSchema, maintenanceSchema, type Policy } from '../shared/contracts';

export const configSchema = z.strictObject({
  executable: z.string().optional(), repositories: z.array(z.string()).max(32).default([]),
  /** Every grant below at once; omit it to grant selectively. */
  all: z.boolean().default(false),
  planning: z.boolean().default(false), decisions: z.boolean().default(false),
  tasks: z.boolean().default(false), commit: z.boolean().default(false),
  controls: z.array(controlSchema).default([]), maintenance: z.array(maintenanceSchema).default([]),
});
export type PolicySource = 'environment' | 'default' | 'none';
export type Config = z.infer<typeof configSchema> & { path: string | null; source: PolicySource };

function configHome(env: NodeJS.ProcessEnv): string {
  return env.XDG_CONFIG_HOME && path.isAbsolute(env.XDG_CONFIG_HOME) ? env.XDG_CONFIG_HOME : path.join(env.HOME || homedir(), '.config');
}
/** `$XDG_CONFIG_HOME/autowork/policy.json`, else `~/.config/autowork/policy.json`. */
export function defaultPolicyPath(env: NodeJS.ProcessEnv = process.env): string {
  return path.join(configHome(env), 'autowork', 'policy.json');
}
/** The pre-rename path, read only while the current one is absent, so existing grants survive. */
export function legacyPolicyPath(env: NodeJS.ProcessEnv = process.env): string {
  return path.join(configHome(env), 'paseo-autowork', 'policy.json');
}
async function readPolicy(file: string): Promise<z.infer<typeof configSchema>> {
  const stat = await lstat(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 65536 || (stat.mode & 0o022) !== 0
      || (process.getuid && stat.uid !== process.getuid())) throw new Error('Autowork policy must be a private, owner-controlled regular file');
  return configSchema.parse(JSON.parse(await readFile(file, 'utf8')));
}
export async function loadConfig(env: NodeJS.ProcessEnv = process.env): Promise<Config> {
  const file = env.PASEO_AUTOWORK_CONFIG;
  if (file) {
    if (!path.isAbsolute(file)) throw new Error('PASEO_AUTOWORK_CONFIG must be absolute');
    return { ...await readPolicy(file), path: file, source: 'environment' };
  }
  const fallback = defaultPolicyPath(env);
  try { await lstat(fallback); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    // The plugin was named paseo-autowork before the rename; an operator's grants live there.
    const legacy = legacyPolicyPath(env);
    try { await lstat(legacy); }
    catch (legacyError) {
      if ((legacyError as NodeJS.ErrnoException).code === 'ENOENT') return { ...configSchema.parse({}), path: fallback, source: 'none' };
      throw legacyError;
    }
    return { ...await readPolicy(legacy), path: legacy, source: 'default' };
  }
  return { ...await readPolicy(fallback), path: fallback, source: 'default' };
}
/** The grants the UI sees and the server enforces; `all` expands to every grant. */
export function effectivePolicy(config: Config): Policy {
  if (config.all) return { planning: true, decisions: true, tasks: true, commit: true, controls: [...ALL_CONTROLS], maintenance: [...ALL_MAINTENANCE] };
  return { planning: config.planning, decisions: config.decisions, tasks: config.tasks, commit: config.commit,
    controls: [...new Set(config.controls)], maintenance: [...new Set(config.maintenance)] };
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
