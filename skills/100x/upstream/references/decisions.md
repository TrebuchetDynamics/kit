# The decisions log

`.100x/decisions.tsv` is the owner's window into the night. Six tab separated columns, append only, one row per decision. `100x log` writes it.

| Column | Holds |
|---|---|
| ts | added for you |
| phase | `start`, `frame`, `core`, `pivot`, `build`, `depth`, `polish`, `round`, `must-not-break`, `review`, `ship`, `ops`, `resume`, `cut`, `done` |
| decision | what you chose, in one sentence |
| why | the reasoning, in one sentence |
| evidence | how you know. A command, a count, a screenshot path, or the word `guess`. Start with `measured.`, `inferred.` or `guess.` |
| result | what happened. `keep`, `revert`, `open`, `done`, or the number |

`100x log <phase> "<decision>" "<why>" "<evidence>" "<result>"`. `100x log` stores missing evidence as `guess, no evidence yet`, so supply real evidence whenever it exists. `100x log --tail 10` shows the latest rows.

## Write a row when

Someone could reasonably have chosen differently. A reading of the brief, a taste fork, a pivot, a cut. A rejected finding, a deferral, a skipped stage. A failure and what you did about it. Routine edits belong in git, not here.

## Weak and strong

Weak. `build | Added the shop | Needed | | done`

Strong. `depth | Built a theme switch with dark as default, behind features/theme | The owner asks for options at taste forks and dark makes the bloom colors pop | measured. shots pass-2 dark vs light, weak 4 vs 9 | keep`

Strong. `review | Rejected F4, "pause button too small" | The button is 48 px at every phone size | measured. shots pass-3 phone-se, tapTargets 0 weak | keep`

Strong. `ops | Ran the one thing that must not break with a stub for the pricing API | No key in the project and none may be borrowed | inferred. .env.example lists PRICING_KEY, .env is absent | open`

## The last rows

The log ends with a `done` row written after `100x finish` succeeds. A log whose last row is not `done` tells the owner the run did not end cleanly.
