import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import os from 'node:os';
import path from 'node:path';
const [pack] = JSON.parse(execFileSync('npm', ['pack', '--ignore-scripts', '--json'], { encoding: 'utf8' }));
const temporary = mkdtempSync(path.join(os.tmpdir(), 'autowork-t3-package-'));
try {
  execFileSync('tar', ['-xzf', pack.filename, '-C', temporary]);
  const root = path.join(temporary, 'package');
  const manifest = JSON.parse(readFileSync(path.join(root, 't3-plugin.json'), 'utf8'));
  for (const entry of [manifest.server, manifest.web]) {
    if (!existsSync(path.join(root, entry))) throw new Error(`Missing packaged entry: ${entry}`);
  }
  const plugin = createRequire(import.meta.url)(path.join(root, manifest.server));
  if (typeof plugin.activate !== 'function') throw new Error('Packaged server has no activate entry');
  if (pack.files.some(file => /node_modules|\.sdk|tests\//.test(file.path))) throw new Error('Development files packaged');
  console.log(`Packaged manifest entries exist; server loads without SDK/runtime dependencies (${pack.files.length} files, ${pack.size} bytes).`);
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
