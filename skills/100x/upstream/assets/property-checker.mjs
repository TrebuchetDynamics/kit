// Property checker. Copy into the project, for example .100x/must-not-break/property-checker.mjs.
// It explores every state a small model of the software can reach and checks the properties you wrote.
// This is explicit-state model checking with the project's own functions as the transitions.
// Replace the implementation block and the model block. Keep the engine below the line that says ENGINE.
//
//   node property-checker.mjs [--json]
//   MAX_STATES=500000 MAX_DEPTH=40 node property-checker.mjs
//
// The six kinds of property, and where each one goes in the model.
//   state          init() and the shape of the state. Plain JSON data only, because states are compared as text.
//   transitions    actions[]. Each has pre (when it may run), apply (the project's own function, pure) and params (values to try).
//   preconditions  action.pre. The checker runs the real apply on every state and every parameter. It must accept when
//                  pre says yes and refuse (throw, or return the state unchanged) when pre says no. A step the code accepts
//                  against the spec is followed too, marked with a !, so the invariants judge what the code really does.
//   postconditions action.post(before, after, param). Checked on every transition that the exploration finds.
//   invariants     invariants[]. Checked on every reachable state.
//   liveness       liveness[]. "From any state where from holds, a state where to holds is reached". It is decided under
//                  fairness: strong (the default) means every step that stays possible is eventually taken, so a run
//                  can only stay away from to forever by getting stuck. fairness 'none' also counts a loop that could
//                  be left but is never left. Liveness is decided only when the exploration was exhaustive.
//
// What the checks claim.
//   exhaustive   every reachable state of the model was visited. A pass is a proof for this model and these bounds
//                (the parameter values you listed and the state size you chose).
//   bounded      the exploration stopped at MAX_STATES or MAX_DEPTH. A pass means no violation was found in what was
//                visited. It is not a proof, and every liveness line says "not decided".
// The model is a claim about the software. The proof covers the model, and the checks named guard and post tie the real
// functions to it. Say in the assumptions what the model leaves out.
const num = (value, fallback) => (value === undefined ? fallback : Number(value));
const MAX_STATES = num(process.env.MAX_STATES, 200000);
const MAX_DEPTH = num(process.env.MAX_DEPTH, Infinity);

// ---- The implementation under test. Replace with imports of the project's own functions, which must be pure. ----
function pay(state, amount) {
  if (state.status !== 'open') throw new Error('the order is not open');
  if (!Number.isInteger(amount) || amount < 1) throw new Error('the amount must be a positive whole number');
  if (state.paid + amount > state.total) throw new Error('the payment is more than what is owed');
  const paid = state.paid + amount;
  return { ...state, paid, status: paid === state.total ? 'paid' : 'open' };
}
function ship(state) {
  if (state.status !== 'paid') throw new Error('only a paid order ships');
  return { ...state, status: 'shipped' };
}
function deliver(state) {
  if (state.status !== 'shipped') throw new Error('only a shipped order is delivered');
  return { ...state, status: 'delivered' };
}
function cancel(state) {
  if (state.status !== 'open' && state.status !== 'paid') throw new Error('this order can no longer be cancelled');
  return { ...state, status: 'cancelled' };
}
function refund(state) {
  if (state.status !== 'cancelled') throw new Error('only a cancelled order is refunded');
  if (state.refunded >= state.paid) throw new Error('nothing is left to refund');
  return { ...state, refunded: state.paid };
}

// ---- The model. Replace with the properties of the project. ----
const settled = (s) => s.status === 'delivered' || (s.status === 'cancelled' && s.refunded === s.paid);
const model = {
  name: 'order workflow, total 3',
  // Say what the model leaves out. Each line is printed with the result.
  assumptions: [
    'payments are whole units from 1 to 3 and the total is 3',
    'one order at a time, with no concurrent callers',
    'every step that stays possible is eventually taken (strong fairness)',
  ],
  init: () => ({ total: 3, status: 'open', paid: 0, refunded: 0 }),
  // terminal(state) says where the software may stop. Any other state with no possible step is a deadlock.
  terminal: settled,
  actions: [
    {
      name: 'pay',
      params: () => [0, 1, 2, 3, 4], // include values that must be refused
      pre: (s, amount) => s.status === 'open' && amount >= 1 && s.paid + amount <= s.total,
      apply: pay,
      post: (before, after, amount) => after.paid === before.paid + amount || 'paid must grow by exactly the amount',
    },
    {
      name: 'ship',
      pre: (s) => s.status === 'paid',
      apply: ship,
      post: (before, after) => after.paid === before.paid || 'shipping must not change the money',
    },
    {
      name: 'deliver',
      pre: (s) => s.status === 'shipped',
      apply: deliver,
      post: (before, after) => after.status === 'delivered' || 'delivering must end in delivered',
    },
    {
      name: 'cancel',
      pre: (s) => s.status === 'open' || s.status === 'paid',
      apply: cancel,
      post: (before, after) => after.paid === before.paid || 'cancelling must not change what was paid',
    },
    {
      name: 'refund',
      pre: (s) => s.status === 'cancelled' && s.refunded < s.paid,
      apply: refund,
      post: (before, after) => after.refunded === before.paid || 'a refund must return exactly what was paid',
    },
  ],
  invariants: [
    { name: 'money-in-bounds', holds: (s) => (s.refunded >= 0 && s.refunded <= s.paid && s.paid <= s.total) || 'refunded <= paid <= total broke' },
    { name: 'shipped-means-paid', holds: (s) => !['shipped', 'delivered'].includes(s.status) || s.paid === s.total || 'an order left without full payment' },
    { name: 'refund-only-after-cancel', holds: (s) => s.refunded === 0 || s.status === 'cancelled' || 'money was refunded on an order that is not cancelled' },
  ],
  liveness: [
    { name: 'every-started-order-settles', from: (s) => s.paid > 0 || s.status !== 'open', to: settled },
    { name: 'a-cancelled-order-is-refunded', from: (s) => s.status === 'cancelled' && s.paid > 0, to: (s) => s.refunded === s.paid },
  ],
};

// ---- ENGINE. No need to edit below this line. ----
const canon = (value) => JSON.stringify(value, (key, item) => (item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map((name) => [name, item[name]]))
  : item));
const say = (value) => { const text = JSON.stringify(value); return text.length > 150 ? `${text.slice(0, 147)}...` : text; };
const labelOf = (action, param) => (param === undefined ? action.name : `${action.name}(${JSON.stringify(param)})`);
const verdict = (value) => (value === true || value === undefined ? null : typeof value === 'string' ? value : 'it is false');

const keys = [];
const states = [];
const depths = [];
const out = [];
const parent = [];
const open = [];
const seen = new Map();
let truncated = false;
let transitions = 0;

const results = new Map(); // check name -> { ok, detail, trace, count }
const register = (name) => { if (!results.has(name)) results.set(name, { ok: true, more: 0, count: 0 }); return results.get(name); };
// The steps to a failure are built only for the first one, because a long run of failures must not cost a path each.
function fail(name, message, at, extra) {
  const entry = register(name);
  if (!entry.ok) { entry.more += 1; return; }
  entry.ok = false;
  entry.message = message;
  entry.labels = at === null ? [] : [...pathTo(at), ...(extra ? [extra] : [])];
  entry.at = at;
}
const pathTo = (index) => { const labels = []; for (let at = index; parent[at]; at = parent[at][0]) labels.unshift(parent[at][1]); return labels; };

function discover(state, from, label) {
  const key = canon(state);
  const known = seen.get(key);
  if (known !== undefined) return known;
  if (states.length >= MAX_STATES) { truncated = true; return -1; }
  const index = states.length;
  seen.set(key, index);
  keys.push(key);
  states.push(state);
  depths.push(from === null ? 0 : depths[from] + 1);
  out.push([]);
  open.push(false);
  parent.push(from === null ? null : [from, label]);
  return index;
}

const initial = model.init();
for (const state of Array.isArray(initial) ? initial : [initial]) discover(state, null, null);
for (const invariant of model.invariants ?? []) register('inv:' + invariant.name);
for (const action of model.actions) { register('guard:' + action.name); register('post:' + action.name); }
register('pure');
register('deadlock');
register('coverage');
const fired = new Set();
const terminal = model.terminal ?? (() => false);

for (let i = 0; i < states.length; i += 1) {
  const state = states[i];
  for (const invariant of model.invariants ?? []) {
    const entry = register('inv:' + invariant.name);
    entry.count += 1;
    const bad = verdict(invariant.holds(state));
    if (bad) fail('inv:' + invariant.name, bad, i);
  }
  if (depths[i] >= MAX_DEPTH) { open[i] = true; truncated = true; continue; }
  let enabledCount = 0;
  for (const action of model.actions) {
    const guard = register('guard:' + action.name);
    for (const param of action.params ? action.params(state) : [undefined]) {
      const label = labelOf(action, param);
      if (action.pre(state, param)) {
        enabledCount += 1;
        let next;
        try {
          next = action.apply(state, param);
        } catch (error) {
          fail('guard:' + action.name, 'the model allows ' + label + ' but the implementation refused it: ' + error.message, i, label);
          continue;
        }
        guard.count += 1;
        if (canon(state) !== keys[i]) {
          fail('pure', label + ' changed the state it was given. Return a new state and leave the old one alone', i, label);
          states[i] = JSON.parse(keys[i]);
        }
        fired.add(action.name);
        const post = register('post:' + action.name);
        post.count += 1;
        const bad = action.post ? verdict(action.post(state, next, param)) : null;
        if (bad) fail('post:' + action.name, bad, i, label);
        const target = discover(next, i, label);
        transitions += 1;
        if (target === -1) open[i] = true;
        else out[i].push([label, target]);
      } else if (action.refuses !== false) {
        let applied = null;
        try {
          applied = action.apply(state, param);
        } catch {
          guard.count += 1;
          continue;
        }
        if (canon(applied) === keys[i]) guard.count += 1;
        else {
          fail('guard:' + action.name, 'the model forbids ' + label + ' but the implementation accepted it and changed the state to ' + say(applied), i, label);
          // What the code really does is reachable too, so the invariants judge it. A step the code accepts and the spec forbids is marked with a !.
          const target = discover(applied, i, '!' + label);
          transitions += 1;
          if (target === -1) open[i] = true;
          else out[i].push(['!' + label, target]);
        }
      }
    }
  }
  if (enabledCount === 0 && !terminal(state)) fail('deadlock', 'no step is possible and the model does not call this a stopping point', i);
}

const exhaustive = !truncated;
const never = model.actions.filter((action) => !fired.has(action.name) && action.optional !== true).map((action) => action.name);
if (never.length && exhaustive) fail('coverage', 'these steps were never possible in any reachable state: ' + never.join(', ') + '. Check the model, or mark one optional', null);

// Liveness. Strong fairness: a run that avoids to forever must end in a closed set of states that all avoid to.
function components(allowed) {
  const index = new Array(states.length).fill(-1);
  const low = new Array(states.length).fill(0);
  const onStack = new Array(states.length).fill(false);
  const comp = new Array(states.length).fill(-1);
  const stack = [];
  const comps = [];
  let counter = 0;
  for (let root = 0; root < states.length; root += 1) {
    if (!allowed(root) || index[root] !== -1) continue;
    index[root] = low[root] = counter; counter += 1;
    stack.push(root);
    onStack[root] = true;
    const work = [[root, 0]];
    while (work.length) {
      const frame = work[work.length - 1];
      const v = frame[0];
      if (frame[1] < out[v].length) {
        const w = out[v][frame[1]][1];
        frame[1] += 1;
        if (!allowed(w)) continue;
        if (index[w] === -1) {
          index[w] = low[w] = counter; counter += 1;
          stack.push(w);
          onStack[w] = true;
          work.push([w, 0]);
        } else if (onStack[w]) low[v] = Math.min(low[v], index[w]);
      } else {
        work.pop();
        if (work.length) { const u = work[work.length - 1][0]; low[u] = Math.min(low[u], low[v]); }
        if (low[v] === index[v]) {
          const members = [];
          let w;
          do { w = stack.pop(); onStack[w] = false; comp[w] = comps.length; members.push(w); } while (w !== v);
          comps.push(members);
        }
      }
    }
  }
  return { comp, comps };
}

const reverse = states.map(() => []);
states.forEach((_, i) => { for (const [, j] of out[i]) if (j >= 0) reverse[j].push(i); });
let fullGraph = null;

function checkLiveness(property) {
  const name = 'live:' + property.name;
  const entry = register(name);
  if (!exhaustive) { entry.ok = false; entry.message = 'not decided. The exploration stopped at a bound, so a state that looks stuck may only be unexplored. Raise MAX_STATES and MAX_DEPTH, or shrink the model'; entry.labels = []; entry.at = null; return; }
  const goal = states.map((state) => Boolean(property.to(state)));
  const starts = states.map((state, i) => !goal[i] && Boolean(property.from(state)));
  const count = states.filter((state) => property.from(state)).length;
  entry.count = count;
  if (count === 0) { entry.ok = false; entry.message = 'vacuous. No reachable state satisfies from, so nothing was checked'; entry.labels = []; entry.at = null; return; }
  const seeds = new Set();
  if ((property.fairness ?? 'strong') === 'strong') {
    fullGraph ??= components(() => true);
    fullGraph.comps.forEach((members, id) => {
      const closed = members.every((v) => out[v].every(([, w]) => fullGraph.comp[w] === id));
      if (closed && members.every((v) => !goal[v])) for (const v of members) seeds.add(v);
    });
  } else {
    const { comps } = components((v) => !goal[v]);
    comps.forEach((members) => {
      const loops = members.length > 1 || out[members[0]].some(([, w]) => w === members[0]);
      if (loops) for (const v of members) seeds.add(v);
    });
    states.forEach((_, v) => { if (!goal[v] && out[v].length === 0) seeds.add(v); });
  }
  // Every state that can reach a seed without passing through to.
  const doomed = new Set(seeds);
  const queue = [...seeds];
  while (queue.length) {
    const v = queue.shift();
    for (const u of reverse[v]) if (!goal[u] && !doomed.has(u)) { doomed.add(u); queue.push(u); }
  }
  const bad = starts.findIndex((isStart, i) => isStart && doomed.has(i));
  if (bad === -1) return;
  // The way from the bad state into the trap, staying away from to.
  const via = new Map([[bad, null]]);
  const walk = [bad];
  let trapped = seeds.has(bad) ? bad : -1;
  for (let at = 0; at < walk.length && trapped === -1; at += 1) {
    for (const [label, w] of out[walk[at]]) {
      if (goal[w] || via.has(w)) continue;
      via.set(w, [walk[at], label]);
      walk.push(w);
      if (seeds.has(w)) { trapped = w; break; }
    }
  }
  const tail = [];
  for (let at = trapped; via.get(at); at = via.get(at)[0]) tail.unshift(via.get(at)[1]);
  entry.ok = false;
  entry.message = 'from ' + say(states[bad]) + ' the run can stay away from to forever. It gets stuck at ' + say(states[trapped]);
  entry.labels = [...pathTo(bad), ...tail];
  entry.at = trapped;
}
for (const property of model.liveness ?? []) checkLiveness(property);

const level = exhaustive ? 'exhaustive' : 'bounded';
const deepest = depths.reduce((most, depth) => Math.max(most, depth), 0);
const describe = (name, entry) => {
  if (!entry.ok) {
    const trace = entry.labels?.length ? ' Steps: ' + entry.labels.join(', ') + '.' : '';
    const more = entry.more ? ' (and ' + entry.more + ' more)' : '';
    return entry.message + more + '.' + trace;
  }
  if (name.startsWith('inv:')) return entry.count + ' states checked, ' + level;
  if (name.startsWith('guard:')) return entry.count + ' enabled and refused cases agree with the implementation, ' + level;
  if (name.startsWith('post:')) return entry.count + ' transitions checked, ' + level;
  if (name === 'pure') return 'no apply changed its input';
  if (name === 'deadlock') return 'every state has a step or is a stopping point, ' + level;
  if (name === 'coverage') return exhaustive ? 'every step was possible somewhere, ' + fired.size + ' of ' + model.actions.length : fired.size + ' of ' + model.actions.length + ' steps reached so far. Not decided on a bounded search';
  if (name.startsWith('live:')) return 'holds from ' + entry.count + ' states under ' + ((model.liveness.find((p) => 'live:' + p.name === name).fairness ?? 'strong')) + ' fairness, exhaustive';
  return 'ok';
};
const checks = [...results].map(([name, entry]) => ({ name, ok: entry.ok, level: name.startsWith('live:') || exhaustive ? level : 'bounded', detail: describe(name, entry) }));

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ model: model.name, exhaustive, states: states.length, transitions, depth: deepest, assumptions: model.assumptions ?? [], checks }, null, 2));
} else {
  console.log('Model ' + model.name + '. ' + states.length + ' states, ' + transitions + ' transitions, deepest path ' + deepest + '.');
  console.log(exhaustive
    ? 'Exhaustive. Every reachable state was visited, so a pass is a proof for this model and these bounds.'
    : 'BOUNDED. The exploration stopped at ' + MAX_STATES + ' states or depth ' + MAX_DEPTH + '. A pass means nothing was found in what was visited, not a proof.');
  for (const line of model.assumptions ?? []) console.log('  assumes ' + line);
  for (const check of checks) console.log((check.ok ? 'pass' : 'FAIL') + '  ' + check.name + '. ' + check.detail);
}
process.exitCode = checks.every((check) => check.ok) ? 0 : 1;
