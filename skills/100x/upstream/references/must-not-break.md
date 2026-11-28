# Must not break mode

Stage 5 of every normal build, and any time the owner asks to test the one thing hard.

You cannot test everything in one night. Every app has one thing that, if it breaks, makes the owner stop using it. Test that one thing hard, once, after polish. The quick checks at build time and the screen-size runs inside each polish pass are separate and cheap.

Done when `.100x/must-not-break/` holds a check that passed after you showed it could fail, its output file `.100x/must-not-break/<kind>.txt`, and the `mustNotBreak` record in `run.json`. A check that still fails is also a result. Give it `status` fail and put the exact failure in `summary`. `100x finish` looks for that output file and for numbers in the summary. It refuses a claim with nothing behind it.

## Step 1. Name the one thing

Write one sentence under `## Must not break` in `.100x/project.md`. "If X is wrong, the owner stops using it." Then pick the kind. An app gets one kind, or two at most.

| Kind | Pick when | Check | Done means |
|---|---|---|---|
| `screen-sizes` | apps you touch, games, dashboards, anything with a canvas | `100x shots --matrix all-rotate --resize-test` on every important screen state | 0 broken, every weak line fixed or explained, and you looked at `contact-sheet.png` |
| `numbers` | money, prices, scores, tax, units, contracts | tests on functions that only use their inputs: rules that must always hold, plus cases with a known right answer | all pass, and the check goes red when you put a bug in on purpose |
| `properties` | anything with real logic: workflows, permissions, state machines, parsers, protocols, money flows | the six properties (state, transitions, preconditions, postconditions, invariants, liveness) pulled out of the code and checked exhaustively on a small model that runs the project's own functions, kept in `verify/ledger.tsv` | every property holds, each failed on a seeded defect, each row says its level (`exhaustive`, `bounded` or `sampled`) |
| `game-economy` | idle and incremental games | the economy simulator, plus late game saves through `--init-script` | all checks pass and the table of times between buys rises like a curve |
| `fresh-data` | anything that shows fetched or saved data | the fresh-data check on each source, plus the empty, error and offline screens | fresh data passes, old data fails with a clear message |
| `assets` | art, sound or models are the product | `assets/asset-check.mjs`, then look at every asset where it is used | the script passes and the set looks like one person made it |
| `text` | apps with lots of words, marketing, docs | `100x shots` per state, `100x text lint` on its `texts.txt`, then read the strings as a stranger | lint clean and nothing vague left |
| `main-flow` | nothing above fits | the main flow from start to end with `100x shots --steps`, console clean | the flow finishes at phone and desktop sizes |

More detail for each kind is in [kinds.md](kinds.md). The `properties` kind and the verification ledger are in [properties.md](properties.md), which also says when to start that procedure outside this stage: any time `100x verify cover <file>` finds no rule. How to run the screen shots is in [shots.md](shots.md).

## Step 2. Write the check as code

- Put it in the project's own test folder when it has one. If not, put it in `.100x/must-not-break/`.
- Start from a file in `assets/` and change the example to use the project's real functions. A template passes as shipped, on its own example functions, so a green run before you replaced them proves nothing about the project.
  - `assets/money-checks.test.mjs` for `numbers`.
  - `assets/economy-simulator.mjs` and `assets/seed-localstorage.js` for `game-economy`.
  - `assets/fresh-data-check.mjs` for `fresh-data`.
  - `assets/asset-check.mjs` for `assets`.
  - `assets/property-checker.mjs` for `properties`, recorded with `100x verify add` as [properties.md](properties.md) says.
- When the rules sit inside screen code, pull them out first into functions that only use their inputs. That is the most useful change in this stage. It makes the rules testable at all.
- Run the check and save what it prints to `.100x/must-not-break/<kind>.txt`. One way is to end the command with `| tee .100x/must-not-break/<kind>.txt`. A `screen-sizes` check rests on its `all-rotate` run of the prototype, which `100x shots` writes and signs. It needs no output file, and typed words do not count for it.
- That file holds the passing run and nothing else. Keep the failing run from Step 3 in `.100x/must-not-break/<kind>-red.txt`. `100x finish` refuses a pass when that file still has a line that starts with `FAIL`.

## Step 3. Show the check can fail

A check that has never failed proves nothing. Put in one real defect, in the project's own code. Change how you round, tighten a limit, remove the viewport meta, serve old data. Watch the check fail with a message that names the defect. Then undo it. Do this on a throwaway copy (`mkdir -p /tmp/red && git archive HEAD | tar -x -C /tmp/red`), never in the project. The copy has no `.100x`, because git does not keep it, so copy the check file into it by hand when it lives in `.100x/must-not-break/`. If the check stays green with the defect in, it is not testing the project. Log it.

When the check is a project test, add one test that runs the check with a bad input and checks that the exit code is 1. Then the next change that breaks the check also fails `npm test`.

## Step 4. Fix the cause

Read the failing output. Fix the cause in the app, not in the check. Never loosen a limit, drop a case or widen a range just to pass. Run it again and keep the numbers from before and after.

## Step 5. Write it down

- `100x log must-not-break "<kind>. <result in numbers>" "<why this is the one thing>" "<command and counts>"`
- `100x run push mustNotBreak '{"kind":"screen-sizes","status":"pass","summary":"0 broken of 212 elements across 15 viewports"}'`, once for each check, two at most. The status is `pass`, `fail` or `skipped`. A `skipped` check needs its reason in the summary.
- Give counts with their totals. "0 broken of 212 elements looked at across 15 viewports and 3 states" is a result. "Looks good" is not.

## How deep this goes

`test.budget` in the settings decides. `after-polish` (the default) runs this stage once, after the third polish pass. `quick-only` skips it, so record `status` skipped and say why. `full` adds a `main-flow` check to the kind you picked.

## Rules

- Sound stays off. `100x shots` keeps it off by default. `--sound` is the owner's choice only.
- A check that sometimes passes and sometimes fails is a finding. Fix it, or remove the check and say which you did.
- When you cannot test the one thing on this machine, say what is missing, mark it `skipped`, and name the nearest check you did run.
