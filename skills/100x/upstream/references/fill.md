# Use all the time

The owner said how long to work, for example "work for 10 hours". `100x clock` says use all the time. There is always more to polish and test, so the clock decides when you are done, not your feeling of being done.

`100x finish` refuses until the work time is over. Only `100x clock stop "<reason>"` ends it earlier, and the report shows the reason.

Done when the work time is over, every round is logged, the best version is tagged and the last stretch below ran.

## Before the rounds

Run the normal stages to a first working version, stage 7 included. Commit it and tag it `100x/best`. Then start rounds.

## A round

One lens, 45 to 90 minutes.

1. Take the first lens in the list below that this lap has not used. Run `100x clock`.
2. Measure before. A screenshot, a test run or a number.
3. Change one kind of thing.
4. Measure after. Better, so commit and `git tag -f 100x/best`. The same or worse, so go back to `100x/best` and log "tried, no gain".
5. Judge. Every round gets a fresh judge, brutal, before the next round starts (in a solo run, the written loop challenge of `100x ref solo`). N is the number of `round` rows so far, plus one. Write `.100x/loops/round-N/ask.md` (the lens, the moment, the Rules, Scope and Do not lines from `.100x/project.md` when it has them, how to run it and the main flow when it has a screen, the before and after numbers or screenshots, what changed), run `100x review-call --loop round-N`, wait the way `references/apps.md` says, read `judge.md`. Fix blockers and majors now, answer every finding in `answers.md`. `Drifting: yes` sends you back to `100x/best` first.
6. `100x log round "<lens>" "<what changed, or why nothing>" "<before and after>"`. Update `STATE.md` `Next:` with the next lens.

A lens that finds nothing is logged with what was checked, then the next lens starts. Finding nothing is never a reason to stop.

## Lenses

1. Fresh eyes. `100x shots` on every size and state. Look as a stranger with ten seconds. Fix what looks off.
2. Break it. Empty, huge, rapid taps, reload halfway, offline, keyboard only, large text.
3. Must not break. Add five new cases to the must-not-break check (`references/must-not-break.md`) and run them all.
4. Skeptic. One more judge round on the changed product. `100x config set review.rounds <one more> --local`, then the steps of the `100x-judge` skill. The last round is the ship test, so it asks again whether it is ready to ship.
5. The moment. Make the one signature moment 10 percent better, or build a rival in a branch and keep the better one.
6. Weight and speed. Load time, size, jank. A soak of 20 minutes of use, watching memory.
7. Everyone. Contrast, focus order, reduced motion, names for screen readers, touch size.
8. Words. Every visible sentence plain and short. `100x shots` leaves the strings in `texts.txt`, so lint that file with `100x text lint <file> --profile ui`.
9. Cut. Remove what does not earn its place.
10. First five minutes. Do the owner's try-first steps from a clean checkout.

After lens 10 start lap two with a harder bar. More sizes, a longer soak, odder data.

### With no screen

A command line tool, a library or an agent skill has the same ten lenses in other words. Each one still ends in a measurement.

1. Fresh eyes. In an empty folder, follow the README quickstart and read every output as a stranger.
2. Break it. Empty input, huge input, a missing file, a bad flag, an interrupted run, no network, a read-only folder.
3. Must not break. Same as above.
4. Skeptic. Same as above.
5. The moment. The demo command or the README opening, until it lands in ten seconds.
6. Weight and speed. Start time, memory on a big input, install size, dependency count.
7. Everyone. Output that reads without color or a wide terminal, errors that name the fix.
8. Words. Help text, errors and the README.
9. Cut. Flags and commands nobody needs.
10. First five minutes. Install from a clean checkout and run the quickstart.

## The last stretch

When `100x clock` says the work time is over, stop the rounds. Run the judge if the code changed since its last pass. Run the final matrix and the must-not-break check on `100x/best`, run the project from a clean checkout, then `100x finish`.

## Never

- Never add what the brief did not ask for. A round improves what exists. A new idea goes in `nextAsks`.
- Never sleep or idle to pass the time. The report counts rounds against hours.
- Never keep a change you cannot show helped.
