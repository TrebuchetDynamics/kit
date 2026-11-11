// Fetch authentic SDK sources, with every byte checked against the reviewed commit.
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
const root = new URL('../', import.meta.url);
const pin = JSON.parse(await readFile(new URL('sdk-source.json', root), 'utf8'));
for (const [name, hash] of Object.entries(pin.files)) {
  const response = await fetch(`https://raw.githubusercontent.com/${pin.repository}/${pin.commit}/packages/plugin-sdk/${name}`);
  if (!response.ok) throw new Error(`SDK fetch failed: ${name} (${response.status})`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (createHash('sha256').update(bytes).digest('hex') !== hash) throw new Error(`SDK hash mismatch: ${name}`);
  const target = new URL(`.sdk/${name}`, root);
  await mkdir(new URL('.', target), { recursive: true });
  if (name === 'package.json') {
    const pkg = JSON.parse(bytes.toString());
    // The source package's catalog build dependencies belong to the upstream monorepo.
    delete pkg.devDependencies; delete pkg.scripts;
    await writeFile(target, JSON.stringify(pkg, null, 2) + '\n');
  } else await writeFile(target, bytes);
}
console.log(`Verified authentic T3 SDK sources at ${pin.commit}`);
