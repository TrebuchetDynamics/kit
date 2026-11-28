# Two finished prompts

Each block is a whole `.100x/project.md` as stage 0 leaves it, minus the sections that are not part of the prompt. Both pass `100x prompt check`, and a test keeps them passing. The first is a short brief for a game. The second is a tool that runs on real files, so it has the proof asks that the first one keeps small.

Copy the shape, not the words. Every line here changes something the builder does.

## A game from one line

```markdown
# lighthouse

## Brief
an idle game where you run a lighthouse. cozy, phone first.

## Goal
Make a cozy idle game for a phone where you keep one lighthouse lit, guide ships in, and earn while the page is closed. "Idle" means the total keeps growing while you are away, and the number you come back to can be checked by hand: 3 hours away pays 3 hours, and 30 hours pays 8. "Cozy" counts a ship that waits in the harbor and a lamp that glows softly. It does not count a countdown or a game-over screen. It is not a clicker in a lighthouse skin: the player makes one real choice in the first minute and a new one every few minutes after.

## Read first
- `~/.100x/profile.md`, the repeat corrections. Placeholders get rejected, so the lighthouse, three ships and the sea get real art. Sound is never played while testing.
- `references/looks.md` in the skill. Deep sea for the night scene, Travel poster for the day one. Use the palette and type as written.
- `100x registry list --all`, for earlier idle prototypes. Take their Judge focus lines and reuse no code.

## Rules
- Pay for attention, not for waiting. Away earnings stop at 8 hours, so coming back is a gift and never a chore. The limit is the tooltip: a rule that needs one is cut.
- One screen, not tabs. A whole session fits in a thumb's reach on a 390 by 844 phone. The limit is the settings page, which may open over the game.
- Real numbers, not decoration. Every number on screen is computed from the saved state, and the same state always gives the same number. The limit is the ship art, which is drawn and holds no number.
- Soft failure, not game over. A missed ship waits in the harbor. The limit is the night sea, when no ships come at all.

## Riskiest unknown
The core loop is not fun in the first minute. The first try answers three questions. Is there a choice in the first 20 seconds? Does lighting the lamp feel like something? Does a ship arriving make the player want the next one? If not, change the mechanic before drawing anything more.

## Asks
- [ ] 1. A lighthouse the player lights, and ships that come in and pay, on a phone screen.
- [ ] 2. It keeps earning while the page is closed, up to 8 hours, and shows what came in while you were away.
- [ ] 3. A cozy look with real art in the Deep sea world, and a sound that stays off until the player turns it on.
- [ ] 4. Proof, planted case. A test sets the clock back 3 hours, reopens, and checks the total equals the rate times 3 hours, worked out by hand inside the test.
- [ ] 5. Proof, limit. A test sets the clock back 30 hours and checks the total stops at 8 hours, and that the screen says so.
- [ ] 6. Proof, first minute. Screenshots at 0, 20 and 60 seconds from a cold start with no help, showing the first choice.
- [ ] 7. One command runs it. The README has a screenshot and the one line the game is about.
- [ ] 8. (stretch) A second upgrade path for the lamp.

## Scope
In: one lighthouse, three kinds of ship, saving in the browser, a phone layout from 360 to 430 px wide that also works in a desktop window. Out: accounts, cloud saves, ads, purchases, other languages. The settings screen says plainly that progress lives in this browser only.

## Test material
none: no outside files are needed, because the tests run on a fixed clock

## Do not
- Do not use the real clock in a test, because it would pass only at the right time of day.
- Do not add a timer that ends the game, or a count of lost ships.
- Do not play sound while testing. Mute every browser you drive.

## Assumptions
- Phone first means a web page that works well on a phone, not a store app, because the brief names no store.
- The earning rate is one constant in one file, because the brief gives no numbers and the owner will want to tune it.

## Must not break
Kind game-economy, then screen-sizes. Away earnings equal the same time of play, capped at 8 hours, and never go negative or drop after a reload.

## Properties
- State: coins, owned counts per upgrade, last seen time and prestige points, all finite numbers.
- Transitions: tap, buy one upgrade, tick for a number of seconds, go away and return, prestige reset.
- Preconditions: a buy needs coins at or above the price. Prestige needs at least one earned point.
- Postconditions: a buy lowers coins by exactly the price. Returning pays what the same seconds of play would have paid.
- Invariants: coins never go negative or past 1e300, and owned counts never drop except by prestige.
- Liveness: from any save the player can buy again within the stall limit, under a player who taps three times a second.

## Moment
The lamp lights, the beam sweeps across the water, and a small ship turns toward it.

## Judge focus
- Does the total after 3 hours away match a hand count?
- What does a player do in the first 20 seconds with no help?
- Is any art a placeholder or a stock gradient?
- Does anything move that does not need to, or any sound start without a tap?
- Does it work with a thumb on the smallest phone, with nothing clipped?
```

## A tool that runs on real files

```markdown
# dead-exports

## Brief
a cli that finds dead exports in a typescript repo. fast, no config, and it must never tell me to delete something that is used.

## Goal
Build a command line tool that lists the exports in a TypeScript repo that nothing uses, with the file and line of each. "Dead" means no import, re-export or dynamic import anywhere in the repo reaches it. An exported function that no file imports is dead, and so is a type that no file names. An export that only a test imports is not dead, and neither is one that a barrel file re-exports and something imports. It is not a style linter, and it deletes nothing: it reports, and the owner decides.

## Read first
- The TypeScript wiki page "Using the Compiler API" (not read, the core stage opens it). Look for how to build a program and find references, and the part on module resolution, because `paths` aliases are where tools go wrong.
- The `knip` README (not read, the core stage opens it). Look for what it reports and where it needs config, so this tool has a reason to exist. Credit the idea in the README and copy no text.
- `~/.100x/profile.md`, the repeat corrections. A command line tool's look is its first run, so the help text and the first output get the care a screen would.

## Rules
- Silence over noise. Report only what is certain, and list the rest under "maybe" with the reason. A wrong "dead" costs more than a missed one. The limit is a count: when "maybe" is longer than "dead", the tool is not working.
- The compiler's answer, not a regex's. Resolve imports the way the repo's own `tsconfig.json` does. The limit is dynamic strings such as `import(name)`, which no tool resolves, so those files go under "maybe".
- No config on the first run, not no config ever. It reads `tsconfig.json`, and a file can add entry points after that.
- Plain output, not a dashboard. One line per finding, `path:line name`, sorted, and exit code 1 when anything is dead. The limit is `--json`, a stretch ask that adds a second format and changes nothing in the first.

## Riskiest unknown
It calls a used export dead. The first try answers three questions. Does it follow `paths` aliases and barrel files (`export * from`)? Does it count a file used only by a test as used? How many "maybe" lines does a real repo get? If aliases fail, the approach changes to the compiler's own find-references.

## Asks
- [ ] 1. `deadx` lists dead exports as `path:line name`, and exits 1 when it finds any.
- [ ] 2. It runs with no config in a folder that has a `tsconfig.json`, and finishes a 2,000 file repo in under 10 seconds.
- [ ] 3. Proof, planted case. On a copy of a real repo, add 3 unused exports (a function, a type, a re-export). Show all 3 are found and nothing else is.
- [ ] 4. Proof, control. On a small repo built for the test, where every export is used through aliases, barrel files and one test, it prints nothing and exits 0.
- [ ] 5. Proof, real input. Run it on the 3 repos in Test material. For the first 20 findings in each, open the file and mark each right or wrong, then give a second model 10 of them to mark blind. Pass: at most 2 wrong of 60, and the two markings agree on at least 9 of the 10.
- [ ] 6. Proof, honest limit. The help text and the README say what it cannot see: dynamic imports, plugins loaded by string, importers outside the repo. It prints "maybe" for those files.
- [ ] 7. A README with install, the one command, and real output.
- [ ] 8. (stretch) `--json` output.

## Scope
In: `.ts`, `.tsx`, `.js` and `.mjs` files in one repo, `paths` aliases, barrel files, type-only exports, test files counting as users. It skips `node_modules`, anything `.gitignore` names and generated `.d.ts` files, and it needs Node 20 and no dependency but `typescript`. Out: monorepos with several tsconfigs, deleting or fixing anything, editor plugins, CI plugins. `--help` says so.

## Test material
Three of the owner's TypeScript repos, found with `ls ~/Documents/GitHub/*/tsconfig.json`: `shop` (412 files), `blog` (96) and `tools` (230). Read only: copy a repo to `/tmp` before planting anything, and write nothing into the original. Raw findings stay in `/tmp`. Nothing from them goes into the README or a test, so anything that ships calls them repo A, B and C.

## Do not
- Do not delete or rewrite any file the tool reports on.
- Do not run the audited repo's own scripts, install anything in it or touch its git state. The tool reads files and does nothing else.
- Do not print a finding that a regex found and the compiler did not confirm.
- Do not count an export as used because its name is in a comment or a string.
- Do not ship a test that reads the owner's repos.

## Assumptions
- A file named by `main` or `exports` in `package.json` has importers outside the repo, so its exports go under "maybe" and never under "dead".
- The tool is for repos with a `tsconfig.json`, because the brief says TypeScript and "no config".

## Must not break
Never call a used export dead. If it does, the owner deletes working code and stops trusting the tool. Kind main-flow, with the planted case and the control as the check, and the real input run for the count of wrong findings.

## Properties
- State: the set of exports found, the references found and the report lines.
- Transitions: scan a file, resolve one import, classify one export.
- Preconditions: classify runs only after every file of the scan was read.
- Postconditions: every reported export has no reference in the scanned files.
- Invariants: an export with any reference is never reported dead, and the same input gives the same report.
- Liveness: a scan ends within the size cap on any folder, under a disk that answers every read.

## Moment
The first run on a repo the owner knows well: the list is short and every line is right.

## Judge focus
- Can you make it call a used export dead? Try aliases, barrels, type-only imports and a file used only by a test.
- How many "maybe" lines does a real repo get, and are they useful or noise?
- What does the first run print on a repo with a `tsconfig.json` and on one without?
- Is the help text honest about what it cannot see?
- How long does it take on the largest repo you can find?
```
