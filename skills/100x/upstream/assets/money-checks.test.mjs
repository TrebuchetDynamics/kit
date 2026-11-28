// Property tests for money math. Copy into the project, for example test/must-not-break/money.test.mjs.
// Replace the example functions with imports of the project's own, keep the harness and the invariants,
// then add golden cases from an authority. Run with `node --test test/must-not-break/money.test.mjs`.
// Money is integer cents. If the project stores floats, the first finding is that it should not.
import assert from 'node:assert/strict'
import test from 'node:test'

// Example targets so the template runs as it is. Replace these.
function splitCents(totalCents, parts) {
  const base = Math.floor(totalCents / parts);
  const extra = totalCents - base * parts;
  return Array.from({ length: parts }, (_, i) => base + (i < extra ? 1 : 0));
}

function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

// Harness. A seeded generator, so a failure repeats, and the failing input printed with the error.
function rng(seed) {
  let state = seed >>> 0;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
}
const int = (r, low, high) => low + Math.floor(r() * (high - low + 1));

function forAll(label, generate, check, { runs = 2000, seed = 20260101 } = {}) {
  test(label, () => {
    const r = rng(seed);
    for (let i = 0; i < runs; i += 1) {
      const input = generate(r);
      try {
        check(input);
      } catch (error) {
        throw new Error(`${error.message}\nfailing input (run ${i}, seed ${seed}): ${JSON.stringify(input)}`, { cause: error });
      }
    }
  });
}

const shares = (r) => ({ total: int(r, 0, 100_000_000_000), parts: int(r, 1, 60) });
const sum = (list) => list.reduce((a, b) => a + b, 0);

forAll('a split keeps every cent', shares, ({ total, parts }) => {
  const out = splitCents(total, parts);
  assert.equal(out.length, parts);
  assert.equal(sum(out), total);
});

forAll('a split is fair to within one cent and never negative', shares, ({ total, parts }) => {
  const out = splitCents(total, parts);
  assert.ok(Math.max(...out) - Math.min(...out) <= 1);
  assert.ok(Math.min(...out) >= 0);
});

forAll('rounding twice equals rounding once', (r) => ({ x: r() * 1000 }), ({ x }) => {
  assert.equal(roundHalfEven(roundHalfEven(x)), roundHalfEven(x));
});

forAll('rounding never reorders values', (r) => ({ a: r() * 1000, b: r() * 1000 }), ({ a, b }) => {
  const [low, high] = a <= b ? [a, b] : [b, a];
  assert.ok(roundHalfEven(low) <= roundHalfEven(high));
});

// Golden cases. Every case names its source: the spec, the statute, the vendor document, or a hand
// calculation written out in the commit message. A golden case without a source is a guess.
const GOLDEN = [
  { name: 'half rounds to even, down', input: 2.5, expected: 2, source: 'IEEE 754 round half to even' },
  { name: 'half rounds to even, up', input: 3.5, expected: 4, source: 'IEEE 754 round half to even' },
  { name: 'just under half rounds down', input: 2.4999, expected: 2, source: 'IEEE 754 round half to even' },
];

test('golden cases agree with their sources', () => {
  for (const item of GOLDEN) {
    assert.ok(item.source, `${item.name} has no source`);
    assert.equal(roundHalfEven(item.input), item.expected, item.name);
  }
});

test('boundaries hold', () => {
  assert.deepEqual(splitCents(0, 3), [0, 0, 0]);
  assert.deepEqual(splitCents(1, 3), [1, 0, 0]);
  assert.equal(sum(splitCents(Number.MAX_SAFE_INTEGER, 7)), Number.MAX_SAFE_INTEGER);
});
