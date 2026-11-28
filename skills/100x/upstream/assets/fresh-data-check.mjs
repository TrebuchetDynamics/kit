// Data fresh-data check for apps that show live or cached data. Copy into the project, for example .100x/must-not-break/.
//   node fresh-data-check.mjs <url> [--field updated_at] [--max-age-hours 24] [--array items] [--timeout 10000]
// Checks. the request succeeds in time, the body is JSON, the timestamp field is recent, a named array is not empty.
// Exit code 1 when any check fails. Run it once against a stale or broken source to see it go red.
const args = process.argv.slice(2);
const url = args.find((arg) => !arg.startsWith('--') && !args[args.indexOf(arg) - 1]?.startsWith('--'));
const option = (name, fallback) => {
  const at = args.indexOf(`--${name}`);
  return at >= 0 ? args[at + 1] : fallback;
};
if (!url) {
  console.error('Usage. node fresh-data-check.mjs <url> [--field updated_at] [--max-age-hours 24] [--array items] [--timeout 10000]');
  process.exit(2);
}
const field = option('field', 'updated_at');
const maxAgeHours = Number(option('max-age-hours', 24));
const arrayPath = option('array', null);
const timeout = Number(option('timeout', 10000));
const pick = (object, dotted) => dotted.split('.').reduce((node, key) => (node && typeof node === 'object' ? node[key] : undefined), object);

const checks = [];
const record = (name, ok, detail) => checks.push({ name, ok, detail });
let body = null;
const started = Date.now();
try {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeout) });
  record('request', response.ok, `HTTP ${response.status} in ${Date.now() - started} ms`);
  const text = await response.text();
  try {
    body = JSON.parse(text);
    record('json', true, `${text.length} bytes`);
  } catch {
    record('json', false, `not JSON, starts with ${JSON.stringify(text.slice(0, 40))}`);
  }
} catch (error) {
  record('request', false, `${error.name}. ${error.message}`);
}
if (body !== null) {
  const stamp = pick(body, field);
  const age = stamp ? (Date.now() - new Date(stamp).getTime()) / 3600000 : NaN;
  record('fresh', Number.isFinite(age) && age <= maxAgeHours, Number.isFinite(age) ? `${field} is ${age.toFixed(1)} h old, limit ${maxAgeHours}` : `no readable ${field}`);
  if (arrayPath) {
    const list = pick(body, arrayPath);
    record('not-empty', Array.isArray(list) && list.length > 0, Array.isArray(list) ? `${list.length} items in ${arrayPath}` : `${arrayPath} is not an array`);
  }
}
for (const check of checks) console.log(`${check.ok ? 'pass' : 'FAIL'}  ${check.name}. ${check.detail}`);
process.exitCode = checks.every((check) => check.ok) ? 0 : 1;
