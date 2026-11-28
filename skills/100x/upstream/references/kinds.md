# The kinds in detail

Pick the kind in [must-not-break.md](must-not-break.md). Each section says what usually breaks, what to run and what counts as green.

## screen-sizes

What breaks, most common first.

- No `<meta name="viewport" content="width=device-width, initial-scale=1">`. The page lays out at 980 px and shrinks. `100x shots` reports it as `zoomedOut`.
- Fixed pixel widths and heights on containers. Prefer `min()`, `clamp()`, container units and `aspect-ratio`.
- `100vh` on phones. The browser bar makes it taller than the screen. Use `100dvh` or `100svh`.
- Notches and home bars. Use `viewport-fit=cover` and `env(safe-area-inset-*)` on fixed bars and edge controls.
- Canvas not tied to device pixel ratio. Set the backing store to the CSS size times the ratio, redraw on resize and on orientation change, and scale pointer coordinates the same way.
- Fixed aspect ratio games. Letterbox with one scale factor for the whole scene, so art, hit areas and text scale together.
- Text under 12 px on phones. Buttons and tap targets under 44 px.
- Fixed headers and footers that eat a landscape phone (844x390 leaves very little height).
- Big numbers. A value like 1.234e45 or a long currency string overflows its button. Format with a compact notation and test the longest value.
- Rotation without reload. Layout state computed once at load breaks here, and `--resize-test` catches it.

Run `100x shots <url> --label must-not-break --matrix all-rotate --resize-test` with `--steps` for each important state. Done means 0 broken, a decision on every weak line, and a look at `contact-sheet.png`. Show the check can fail: remove the viewport meta or fix a width in pixels, and watch the finding appear.

## numbers

Money, pricing, scores, tax, units and anything a contract could describe.

1. Store money as integer minor units, or a decimal type. Floats in the data model are the first finding.
2. Pull the math into functions that only use their inputs. No screen code, no clock, no network.
3. Write rules that must always hold. A split keeps every cent. Rounding twice gives the same answer as rounding once. Larger inputs never give smaller totals. Fees never exceed the amount. Changing currency and back stays within one unit.
4. Add cases with a known right answer, from a source you trust. The law, the vendor document, the spec, or a hand calculation written in the commit message. Every case names its source.
5. Test the ends. Zero, one unit, the largest safe integer, negative values, NaN and Infinity, and leap days for date math.
6. When two sources can compute the same number, compare them. For example the same schedule in plain integers and in BigInt.

Start from `assets/money-checks.test.mjs`. Done means every rule holds for 2000 random cases and every known answer matches. Show the check can fail: change one rounding call and watch it print a failing input.

## game-economy

Idle and incremental games live or die on how fast things come.

- Pull the rules into functions of the game state and the seconds gone by, so a script can run them. The simulator must use that same code, not a copy of the prices. Then the numbers cannot drift apart.
- Run `assets/economy-simulator.mjs` with the real numbers. If the game has a prestige or reset loop, run it with `PRESTIGE=1` or play the loop with the game's own rules. A real run found a loop where each reset gave a quarter more income and runs fell to 1.2 minutes by the tenth reset. The `runs` check goes red when any run is shorter than three minutes, because a reset that comes every minute is a chore and not a decision. It plays greedily for `HOURS`. It checks that no number ever becomes NaN or Infinity. The first purchase must come fast. The first hour must never wait more than five minutes for a buy. No stretch of the run may stall past `STALL_MINUTES`. Offline progress must equal the same time of play.
- Read the milestone table. It should look like a curve with a rising gap, not a cliff and not a flat line.
- Seed a late game save with `assets/seed-localstorage.js` and run `100x shots` across the phone matrix. Check formatting and layout at 1e15, 1e60 and 1e300. Open every sheet in that state, because counts and multipliers inside sheets are usually formatted by hand and break first.
- Check prestige or reset flows from a late game save, and save loading with a missing or broken field.

Done means all simulator checks pass and the late game screenshots have no broken findings. Show the check can fail with `TAPS=0` (dead start) or a growth rate of 2 (stall).

## properties

Anything with logic that can be stated: a workflow, a permission rule, a state machine, a parser, a protocol, a money flow.

1. Find the well defined part and pull it into functions that only use their inputs.
2. Write the six properties in plain sentences with the repo's names: state, transitions, preconditions, postconditions, invariants and liveness under named assumptions. [properties.md](properties.md) has the table and the procedure.
3. Start from `assets/property-checker.mjs`. Replace the implementation block with imports of the project's own functions and the model block with the properties. The checker visits every reachable state and prints `pass` or `FAIL` for each invariant, each step's guard and postcondition, deadlock, coverage and each liveness line, with the shortest steps to a failure.
4. Record each property with `100x verify add`, with a failing run on a seeded defect in `verify/red/<id>.txt`, then `100x verify run`.

Done means every property holds at the level the ledger names, `100x verify status` shows no stale, broken or unproven row, and the output says whether the search was exhaustive. Show the check can fail: remove a guard, change a limit, or make one step loop, and watch a named property go red. `FAIL guard:pay` means the code and the spec disagree about when a step is allowed. `FAIL live:...` gives the steps into the state the run never leaves.

## fresh-data

Apps that show fetched or cached data.

- Run `node assets/fresh-data-check.mjs <url> --field updated_at --max-age-hours 24 --array items` for each source the app depends on.
- Try the states around it. Empty data, a failing request, a slow request, offline, and a saved copy that is hours old. Each needs a clear screen the user can see, not a spinner that never ends.
- Check that the page shows when its data was last updated, and that the time zone is right.
- Check the limits the source names, and what the app does when it hits one.

Done means fresh data passes, old data fails with a message that names the field and its age, and every state around it is on screen in `100x shots`. Show the check can fail by pointing it at a test file with old data.

## text

Content heavy apps, landing pages, docs.

- `100x shots <app> --label words` saves every string the page showed in `.100x/shots/words/texts.txt`, including text a script wrote. `100x text lint <that file> --profile ui` checks it. Use `docs`, `article`, `message`, `marketing` or `narrative` for those forms, and lint the source file itself only when it is plain prose.
- Reach every state with `--steps` first, so the empty, error and win screens are in the file.
- Read every shown string once as a stranger. Vague labels, padded sentences, generic empty states and error messages that blame the user are findings.
- Check numbers and names in copy against the data they describe.

Done means lint passes at the level the project chose and a stranger read finds nothing vague.

## assets

Products where art, sound or models are what the owner sees and hears. A pack, a game with its own art, a portfolio, a sprite sheet, a texture set.

1. Run `node assets/asset-check.mjs <assets folder>`. It catches the mechanical failures. Empty or corrupt files, files over budget, two names for the same bytes, a frame that is a different size than its set, an image too small to use.
2. Look at every asset at the size it is used, not in a file browser. `100x shots` the screen that uses them, and open `contact-sheet.png`. For art that is not on a screen, render a grid of it and open that.
3. Judge the set, not each piece. One style, one palette, one light direction, one level of detail, one loudness for sounds. The odd one out is the finding.
4. Read the edges. Halos around cut outs, seams in tiles, clipped transparent borders, blurry upscales, sprites sitting off their pivot, a loop that clicks.
5. Check the license of anything that was not made here, and write it down.

Done means the script passes, every asset was seen in use and the set looks like one person made it. Show the check can fail: cut one file to zero bytes, or resize one frame of a numbered set. Taste stays a person's call, so the judge is told to look at the assets with its own eyes.

## main-flow

When nothing above fits, test the main flow.

- Write the flow as `100x shots --steps` with a `shot` after each stage, at `--matrix standard`.
- Add the unhappy path once. An invalid input, a refresh in the middle, the back button.
- Done means the flow finishes at phone and desktop sizes with no console error and no failed step.
