# Stage 2. Build

Done when the app starts from the project's own command, you have closed each ask Build satisfies with evidence, the quick check is clean, and you have tagged `100x/build`.

## Stack

Use the stack the brief names. Otherwise pick the simplest one that can ship a preview link. A static site with a bundler for interfaces and games, responsive and installable as a web app. Add a server only for secrets, data or accounts the brief needs. Phone apps are responsive web unless the brief says native. Few dependencies, all well known.

## Order

1. The pure core. Rules, math and data model as functions of state, with no UI, clock or network. The one thing that must not break in a numbers or game economy project lives here.
2. The moment screen, with the look of the core stage carried over.
3. The remaining screens and flows. Each one closes an ask.
4. Persistence, settings, first run, empty states and error states.

Close each ask in the ledger as it lands. `- [x] the ask (evidence: path or screenshot)`.

## Seams, so cutting is cheap

Every feature outside the core of the moment is a folder or a flag with one import line. Features do not import each other. Keep one registry of features so removing one is deleting a folder and a line. Depth builds on this, and the report lists each cut hint.

## While building

- Real copy and real art from the start. See `references/polish.md` for assets.
- Responsive from the first screen. Viewport meta, fluid units, targets of 44 px or more. Retrofitting costs more than starting right. For phone, touch and game targets, read `references/mobile-web.md` before the first screen.
- A clean console.
- Commit at each working step. Small commits with plain messages.

## Quick check

Start the dev server, run `100x shots <url> --label build --matrix phone`, and run the project's own test command once if it has one. Fix every broken finding before tagging. Full test suites wait for the must-not-break stage.
