import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { lstat, realpath } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import process from 'node:process';

const exec = promisify(execFile);
export type Identity = { root: string; common: string; identity: string; id: string; revision: string };
const probes = new Map<string, Promise<Identity>>();
export function repositoryIdentity(directory: string): Promise<Identity> {
  const existing = probes.get(directory); if (existing) return existing;
  if (probes.size >= 4) return Promise.reject(new Error('Repository identity request limit reached; refresh later'));
  const pending = inspectIdentity(directory).finally(() => probes.delete(directory));
  probes.set(directory, pending); return pending;
}
async function inspectIdentity(directory: string): Promise<Identity> {
  if (!path.isAbsolute(directory) || directory.includes('\0')) throw new Error('Repository path must be absolute');
  const root = await realpath(directory);
  if (root !== path.resolve(directory) || (await lstat(directory)).isSymbolicLink()) throw new Error('Repository symlink/alias is not an exact known target');
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith('GIT_')));
  const { stdout } = await exec('git', ['-C', root, 'rev-parse', '--path-format=absolute', '--show-toplevel', '--git-common-dir', 'HEAD'],
    { env, timeout: 5000, maxBuffer: 8192 });
  const [top, commonText, revision] = stdout.trim().split('\n');
  if (top !== root || !commonText || !revision || !/^[a-f0-9]{40,64}$/.test(revision)) throw new Error('Repository identity is unavailable or is not its root');
  const common = await realpath(commonText); const [a, b] = await Promise.all([lstat(root), lstat(common)]);
  const identity = createHash('sha256').update(JSON.stringify([root, common, a.dev, a.ino, b.dev, b.ino])).digest('hex');
  return { root, common, identity, id: 'r-' + identity.slice(0, 24), revision };
}
export async function assertIdentity(before: Identity): Promise<Identity> {
  try {
    const now = await repositoryIdentity(before.root);
    if (now.identity !== before.identity) throw new Error('changed');
    return now;
  } catch { throw new Error('Repository identity changed or disappeared; refresh before continuing'); }
}
