// Idle game economy simulator. Copy into the project, for example .100x/must-not-break/economy-simulator.mjs.
// Replace the model block with the game's own rules. If the rules live inside UI code, extract them first
// into pure functions of state and elapsed seconds. The rules must be importable for this to prove anything.
//
//   node economy-simulator.mjs [--json]
//   HOURS=72 GROWTH=1.12 STALL_MINUTES=45 node economy-simulator.mjs
//   PRESTIGE=1 node economy-simulator.mjs        also play a reset loop, and check that the runs never collapse
//
// Import the game's own rules when they can be imported, so the numbers cannot drift from the game:
//   import { createRequire } from 'node:module';
//   const E = createRequire(import.meta.url)('../src/economy.js');   // a UMD or CommonJS file
// then replace the model block and the five small functions under it with calls into E. Nothing here should copy a price.
//
// A greedy player taps and buys the best value upgrade each second. The checks.
//   finite      no NaN, no Infinity, nothing past 1e300
//   first-buy   the first purchase happens within FIRST_BUY_SECONDS
//   early-pace  in the first hour the longest wait between purchases stays under EARLY_GAP_MINUTES
//   gaps        over the whole run the longest wait stays under STALL_MINUTES
//   offline     returning after hours away pays what the same hours of play would have produced
//   runs        (PRESTIGE=1) no run between resets is shorter than RUN_MIN_MINUTES, so the loop never becomes a chore
const num = (value, fallback) => (value === undefined ? fallback : Number(value));
const HOURS = num(process.env.HOURS, 48);
const GROWTH = num(process.env.GROWTH, 1.07);
const TAPS_PER_SECOND = num(process.env.TAPS, 3);
const EARLY_GAP_MINUTES = num(process.env.EARLY_GAP_MINUTES, 5);
const STALL_MINUTES = num(process.env.STALL_MINUTES, 60);
const FIRST_BUY_SECONDS = num(process.env.FIRST_BUY_SECONDS, 30);
const OFFLINE_HOURS = num(process.env.OFFLINE_HOURS, 8);
const MILESTONES = [1e3, 1e6, 1e9, 1e12, 1e15, 1e18];
// Optional reset loop. The player resets when the points on offer are at least WORTH of what they hold.
const PRESTIGE = num(process.env.PRESTIGE, 0) === 1;
const PRESTIGE_STEP = num(process.env.PRESTIGE_STEP, 5e6); // a run must earn this much before it pays one point
const PRESTIGE_BONUS = num(process.env.PRESTIGE_BONUS, 0.1); // each point adds this share to all income
const RUN_MIN_MINUTES = num(process.env.RUN_MIN_MINUTES, 3);
const WORTH = num(process.env.WORTH, 0.5);

// Model. Replace.
const UPGRADES = [
  { name: 'Sprout', baseCost: 10, rate: 0.5 },
  { name: 'Colony', baseCost: 100, rate: 4 },
  { name: 'Terrarium', baseCost: 1100, rate: 32 },
  { name: 'Biome', baseCost: 12000, rate: 200 },
  { name: 'Planet', baseCost: 130000, rate: 1100 },
];
const cost = (index, owned) => UPGRADES[index].baseCost * GROWTH ** owned[index];
const perSecond = (owned) => owned.reduce((sum, count, i) => sum + count * UPGRADES[i].rate, 0);
const bonus = (state) => 1 + PRESTIGE_BONUS * state.points;
const earn = (state, amount) => ({ ...state, coins: state.coins + amount, lifetime: state.lifetime + amount });
const produce = (state, seconds) => earn(state, perSecond(state.owned) * bonus(state) * seconds);
const tap = (state) => earn(state, TAPS_PER_SECOND * bonus(state));
const pointsOnOffer = (state) => Math.floor(Math.sqrt(state.lifetime / PRESTIGE_STEP));

// Player policy and loop.
function bestAffordable(state) {
  let best = -1;
  let bestValue = 0;
  UPGRADES.forEach((upgrade, i) => {
    const price = cost(i, state.owned);
    if (price <= state.coins && upgrade.rate / price > bestValue) {
      best = i;
      bestValue = upgrade.rate / price;
    }
  });
  return best;
}

let state = { coins: 0, lifetime: 0, points: 0, owned: UPGRADES.map(() => 0) };
let runStart = 0;
const runSeconds = [];
let lastBuy = 0;
let firstBuy = null;
let longestGap = 0;
let longestEarlyGap = 0;
let finite = true;
const reached = new Map();
const seconds = Math.round(HOURS * 3600);
for (let t = 1; t <= seconds; t += 1) {
  state = produce(tap(state), 1);
  for (let guard = 0; guard < 200; guard += 1) {
    const pick = bestAffordable(state);
    if (pick < 0) break;
    state = { ...state, coins: state.coins - cost(pick, state.owned), owned: state.owned.map((n, i) => (i === pick ? n + 1 : n)) };
    firstBuy ??= t;
    longestGap = Math.max(longestGap, t - lastBuy);
    if (t <= 3600) longestEarlyGap = Math.max(longestEarlyGap, t - lastBuy);
    lastBuy = t;
  }
  if (t === Math.min(seconds, 3600)) longestEarlyGap = Math.max(longestEarlyGap, t - lastBuy);
  if (PRESTIGE) {
    const gain = pointsOnOffer(state);
    if (gain >= Math.max(2, Math.ceil(state.points * WORTH))) {
      runSeconds.push(t - runStart);
      state = { coins: 0, lifetime: 0, points: state.points + gain, owned: UPGRADES.map(() => 0) };
      runStart = t;
      lastBuy = t;
    }
  }
  if (!Number.isFinite(state.coins) || state.coins > 1e300) finite = false;
  for (const goal of MILESTONES) if (!reached.has(goal) && state.coins >= goal) reached.set(goal, t);
}
longestGap = Math.max(longestGap, seconds - lastBuy);

const offlineSeconds = OFFLINE_HOURS * 3600;
let stepped = state;
for (let i = 0; i < offlineSeconds; i += 1) stepped = produce(stepped, 1);
const jumped = produce(state, offlineSeconds);
const offlineError = Math.abs(jumped.coins - stepped.coins) / Math.max(1, stepped.coins);

const checks = [
  { name: 'finite', ok: finite, detail: `coins at the end ${state.coins.toExponential(3)}` },
  { name: 'first-buy', ok: firstBuy !== null && firstBuy <= FIRST_BUY_SECONDS, detail: `${firstBuy === null ? 'no purchase ever happened' : `first purchase at ${firstBuy} s`}, limit ${FIRST_BUY_SECONDS} s` },
  { name: 'early-pace', ok: longestEarlyGap <= EARLY_GAP_MINUTES * 60, detail: `first hour, longest wait between purchases ${(longestEarlyGap / 60).toFixed(1)} min, limit ${EARLY_GAP_MINUTES}` },
  { name: 'gaps', ok: longestGap <= STALL_MINUTES * 60, detail: `whole run, longest wait between purchases ${(longestGap / 60).toFixed(1)} min, limit ${STALL_MINUTES}` },
  { name: 'offline', ok: offlineError < 1e-9, detail: `${OFFLINE_HOURS} h away, relative error ${offlineError.toExponential(2)}` },
];
if (PRESTIGE) {
  const shortest = runSeconds.length ? Math.min(...runSeconds) : Infinity;
  checks.push({ name: 'runs', ok: shortest >= RUN_MIN_MINUTES * 60, detail: `${runSeconds.length} resets in ${HOURS} h, shortest run ${runSeconds.length ? (shortest / 60).toFixed(1) : 'none'} min, limit ${RUN_MIN_MINUTES}, points held ${state.points}` });
}
const table = MILESTONES.map((goal) => ({ coins: goal, minutes: reached.has(goal) ? Number((reached.get(goal) / 60).toFixed(1)) : null }));

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ hours: HOURS, growth: GROWTH, checks, milestones: table, owned: state.owned }, null, 2));
} else {
  console.log(`Economy over ${HOURS} h, growth ${GROWTH}.`);
  for (const row of table) console.log(`  ${row.coins.toExponential(0).padStart(6)} coins  ${row.minutes === null ? 'not reached' : `${row.minutes} min`}`);
  for (const check of checks) console.log(`${check.ok ? 'pass' : 'FAIL'}  ${check.name}. ${check.detail}`);
}
process.exitCode = checks.every((check) => check.ok) ? 0 : 1;
