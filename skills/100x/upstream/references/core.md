# Stage 1. Core

Find out whether this is worth building before building all of it, and find the look.

Done when a `core` row holds a verdict (ship, fine or needs work) and the evidence that produced it.

Skip when `core.enabled` is false, or the brief is a big change with a clear spec. Log the skip and the reason.

## 1. Name the riskiest assumption

Take it from `## Riskiest unknown` in `project.md` when the prompt names one, and build the slice that answers its questions. Otherwise name it now. One sentence. The thing that, if false, makes the project not worth finishing. A core loop that is not fun, data that does not exist, a layout that cannot work on a phone, a number that cannot be right. When the brief holds several, take the one that is cheapest to test and most expensive to be wrong about.

Then, when `project.md` has `Read first` lines marked `(not read)`, open the ones the slice needs and rewrite each to say what you took.

## 2. Choose the look before you build

The core stage is where the visual thesis is born. Write it under Moment in `project.md`.

- Three adjectives for the feel. Not "clean, modern, minimal".
- Five named color tokens with real values, and one accent.
- Two type choices, display and body, that load without a network. System fonts or font files in the repo.
- One concrete visual world the product lives in. A ship's instrument panel, a field notebook, an arcade cabinet. It tells you shape, texture and motion.

Start from a world in `references/looks.md`. It has thirteen with palettes, type stacks, shapes, motion and a signature moment, and every palette passes contrast. Invent a new world only at the same level of detail. When the project has no screen, such as a command line tool or an API, the look is the first run. Decide the help text voice, the output format and the first command that delights.

The median AI app is the thing to beat. Purple to blue gradients, a sans serif on white, piles of rounded cards, emoji for icons, a centered hero with two buttons.

## 3. Build the smallest slice that tests the assumption

Real stack, real looking visuals, real data shape or a believable fixture. No tests, no accounts, no settings. A slice that needs more than about 90 minutes of agent time is too big, so cut it.

## 4. Score it

Run `100x shots <url> --label core --matrix standard`, open `contact-sheet.png` and look. Three tests, scored 0 to 2.

| Test | 0 | 1 | 2 |
|---|---|---|---|
| First minute | nothing happens unprompted | something works | something delightful happens within 60 seconds |
| Screenshot | you would not send it | fine | you would send it to a friend |
| Second day | no reason to come back | a vague one | a concrete one, such as progress, a streak, new data or an unfinished goal |

Total 5 or 6 is ready to ship. 3 or 4 is fine. 0 to 2 needs work. Score honestly. The owner trusts the verdict.

## 5. Act on the verdict

- **ship.** Write the moment in one sentence and go to Build.
- **fine.** Find the weakest of the three tests and spend one pivot on it, then score again.
- **needs work.** Pivot. A pivot changes the idea, the mechanic or the visual world, never the polish. At most two pivots. Each is a `pivot` row naming what changed and why it should score higher.
- **Still needs work after two pivots.** Use `polish.dudPasses` for this run. Build only what shows the idea honestly. Finish with the needs-work verdict, the reason, and the single change most likely to fix it. A truthful needs-work verdict saves the owner an hour.

The stored word for needs work is `dud`. Write `dud` in the log row and in `100x run set verdict`; the report and the gallery show it to the owner as "Needs work".

Log it. `100x log core "<verdict> <score> of 6 on <assumption>" "<why this slice>" "<tests, screenshots>" "<ship|fine|dud>"`.
