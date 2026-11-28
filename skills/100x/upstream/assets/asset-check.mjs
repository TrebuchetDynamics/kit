// Asset check for products whose art, sound or models are the product. Copy into the project, for example .100x/must-not-break/.
//   node asset-check.mjs <folder> [--max-kb 1024] [--max-total-mb 25] [--min-px 16]
// Checks. there are assets, every file opens (real header, not empty), every file is under budget, the whole folder is under budget,
// no two files are the same bytes, and frames of one set ("run_01.png", "run_02.png") share a size.
// It cannot judge taste. Open the files or a contact sheet and look. Exit code 1 when any check fails.
import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(`--${name}`);
  return at >= 0 ? Number(args[at + 1]) : fallback;
};
const folder = args.find((arg, i) => !arg.startsWith('--') && !args[i - 1]?.startsWith('--'));
if (!folder) {
  console.error('Usage. node asset-check.mjs <folder> [--max-kb 1024] [--max-total-mb 25] [--min-px 16]');
  process.exit(2);
}
const maxKb = option('max-kb', 1024);
const maxTotalMb = option('max-total-mb', 25);
const minPx = option('min-px', 16);

const KINDS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.glb', '.wav', '.mp3', '.ogg']);

function imageSize(bytes, ext) {
  if (ext === '.png' && bytes.length > 24 && bytes.toString('latin1', 1, 4) === 'PNG') return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
  if (ext === '.gif' && bytes.toString('latin1', 0, 3) === 'GIF') return [bytes.readUInt16LE(6), bytes.readUInt16LE(8)];
  if ((ext === '.jpg' || ext === '.jpeg') && bytes[0] === 0xff && bytes[1] === 0xd8) {
    for (let at = 2; at + 9 < bytes.length; ) {
      if (bytes[at] !== 0xff) return null;
      const marker = bytes[at + 1];
      if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) return [bytes.readUInt16BE(at + 7), bytes.readUInt16BE(at + 5)];
      at += 2 + bytes.readUInt16BE(at + 2);
    }
    return null;
  }
  if (ext === '.webp' && bytes.toString('latin1', 0, 4) === 'RIFF' && bytes.toString('latin1', 8, 12) === 'WEBP') {
    const form = bytes.toString('latin1', 12, 16);
    if (form === 'VP8X') return [1 + bytes.readUIntLE(24, 3), 1 + bytes.readUIntLE(27, 3)];
    if (form === 'VP8 ') return [bytes.readUInt16LE(26) & 0x3fff, bytes.readUInt16LE(28) & 0x3fff];
    if (form === 'VP8L') return [1 + (bytes.readUInt16LE(21) & 0x3fff), 1 + ((bytes.readUInt32LE(21) >> 14) & 0x3fff)];
  }
  return null;
}

const OPENS = {
  '.svg': (bytes) => /<(?=svg)/.test(bytes.toString('utf8', 0, 2000)), // a "<" then svg, written as a lookahead so a file scanner does not take this script for an SVG
  '.glb': (bytes) => bytes.toString('latin1', 0, 4) === 'glTF',
  '.wav': (bytes) => bytes.toString('latin1', 0, 4) === 'RIFF' && bytes.toString('latin1', 8, 12) === 'WAVE',
  '.mp3': (bytes) => bytes.toString('latin1', 0, 3) === 'ID3' || (bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0),
  '.ogg': (bytes) => bytes.toString('latin1', 0, 4) === 'OggS',
};

const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
  if (entry.name.startsWith('.') || entry.name === 'node_modules') return [];
  const full = path.join(dir, entry.name);
  return entry.isDirectory() ? walk(full) : [full];
});

const files = fs.existsSync(folder) ? walk(folder).filter((file) => KINDS.has(path.extname(file).toLowerCase())) : [];
const rel = (file) => path.relative(folder, file);
const checks = [];
const record = (name, bad, detail) => checks.push({ name, ok: bad.length === 0, detail: bad.length ? `${bad.length} of ${files.length}. ${bad.slice(0, 5).join('; ')}` : detail });

const info = files.map((file) => {
  const bytes = fs.readFileSync(file);
  const ext = path.extname(file).toLowerCase();
  const size = imageSize(bytes, ext);
  const opens = bytes.length > 0 && (size ? true : ext in OPENS ? OPENS[ext](bytes) : false);
  return { file, name: rel(file), ext, bytes: bytes.length, size, opens, hash: crypto.createHash('sha1').update(bytes).digest('hex') };
});

checks.push({ name: 'found', ok: files.length > 0, detail: files.length ? `${files.length} asset files in ${folder}` : `no asset files in ${folder}` });
record('opens', info.filter((i) => !i.opens).map((i) => `${i.name} ${i.bytes === 0 ? 'is empty' : 'has no valid header'}`), `all ${files.length} files open`);
record('too-small', info.filter((i) => i.size && Math.min(...i.size) < minPx).map((i) => `${i.name} is ${i.size.join('x')}`), `every image is at least ${minPx} px on its short side`);
record('file-budget', info.filter((i) => i.bytes > maxKb * 1024).map((i) => `${i.name} is ${(i.bytes / 1024).toFixed(0)} KB`), `every file is under ${maxKb} KB`);
const total = info.reduce((sum, i) => sum + i.bytes, 0);
checks.push({ name: 'total-budget', ok: total <= maxTotalMb * 1048576, detail: `${(total / 1048576).toFixed(1)} MB, limit ${maxTotalMb} MB` });

const seen = new Map();
const twins = [];
for (const i of info.filter((x) => x.bytes > 0)) {
  if (seen.has(i.hash)) twins.push(`${i.name} is the same file as ${seen.get(i.hash)}`);
  else seen.set(i.hash, i.name);
}
record('duplicates', twins, 'no two files are the same bytes');

const sets = new Map();
for (const i of info.filter((x) => x.size)) {
  const stem = path.basename(i.name, i.ext);
  const match = /^(.*?)[-_ ]?\d+$/.exec(stem);
  if (!match) continue;
  const dir = path.dirname(i.name);
  const group = `${dir === '.' ? '' : `${dir}/`}${match[1]}_*${i.ext}`;
  sets.set(group, [...(sets.get(group) ?? []), i]);
}
const mixed = [...sets].filter(([, frames]) => frames.length > 1 && new Set(frames.map((f) => f.size.join('x'))).size > 1)
  .map(([group, frames]) => `${group} has sizes ${[...new Set(frames.map((f) => f.size.join('x')))].join(', ')}`);
record('sets', mixed, `${[...sets.values()].filter((frames) => frames.length > 1).length} numbered sets, each frame the same size`);

for (const check of checks) console.log(`${check.ok ? 'pass' : 'FAIL'}  ${check.name}. ${check.detail}`);
process.exitCode = checks.every((check) => check.ok) ? 0 : 1;
