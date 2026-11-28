# Stage 4. Polish

Three passes on the look, each with measured before and after, then the stage ends. Heavy testing waits until after pass 3.

Done when pass 3 is committed and tagged `100x/polish-3`, every pass has a log row with counts, the last `100x shots` run is at 0 broken, and every pass was judged by another model and answered (a solo run is judged by a written challenge of its own model, see `100x ref solo`). `polish.passes` changes the number (`100x config set polish.passes N --local`). `polish.dudPasses` applies after a needs-work verdict.

## The loop for each pass

1. Shoot the before. `100x shots <url> --label pass-N-before --matrix standard` with `--steps` to reach the screens that matter. Open `contact-sheet.png`. The after shots in step 4 use the label `pass-N` and would overwrite this folder if it had the same name.
2. Decide. Write the pass's list in `.100x/STATE.md`. Fix `Broken things` from the shots first, then shared rules such as one spacing scale and one set of tokens, then hierarchy, then the pass theme below.
3. Implement. Replace, do not only remove. Removing clutter is good when it has no job, and removal alone leaves a page that is plain. Each thing you take out needs something stronger in its place.
4. Shoot again with `100x shots <url> --label pass-N --matrix standard` and the same `--steps`. Open both contact sheets side by side. If the page got plainer, put the character back.
5. Log. `100x log polish "pass N <theme>. <what changed>" "<why>" "shots broken 3 to 0, weak 11 to 4, from `100x shots` before and after" keep`.
6. Commit and tag `100x/polish-N`.
7. Judge. A pass you grade yourself does not count, except in a solo run, where the written loop challenge of `100x ref solo` is the judge. Write `.100x/loops/pass-N/ask.md`: the pass theme, the moment, the Rules, Scope and Do not lines from `.100x/project.md` when it has them, how to run it (command and address), the main flow to walk through, the before and after contact sheets (`.100x/shots/pass-N-before/contact-sheet.png` and `.100x/shots/pass-N/contact-sheet.png`), and what you changed. The judge judges with its eyes, so the ask must let it run the app and see the single screenshots, not only the counts. Then `100x review-call --loop pass-N`. With a judge chosen it prints how to start it, as steps 5 and 6 of the `100x-judge` skill explain. With none chosen it says so: take the `none` bullet of step 5 in the `100x-judge` skill and log the choice. It is a different model, it gets 20 minutes, and it is asked to be brutal. Wait the way `references/apps.md` says, then read `.100x/loops/pass-N/judge.md`.
8. Answer. Fix every blocker and major now. In `.100x/loops/pass-N/answers.md` write one line per finding: fixed in which commit, or why it stays, with evidence. Commit the fixes. `Drifting: yes` means the next pass starts with that fix, before its own theme. A judge that says it cannot see images did not judge a visual pass: start the backup judge instead, and log it. In a solo run there is no backup judge (`100x ref solo`): a chat that cannot see images says so, ends the file `Better: no` and does not claim the pass was looked at.

## Fewer passes

`polish.passes` can be 1 or 2, for example under the lite preset (`100x config preset lite`). Each pass still has its before and after shots and its judge. Only the themes change, so the run keeps the work that shows most.

- **1 pass.** Structure first, then the three details a stranger sees in the first minute: real assets in place of placeholders, every state of the main screen looking designed, and copy that passes `100x text lint`. Leave the moment for the next run's first ask, and say so in `nextAsks`.
- **2 passes.** Pass 1 is structure. Pass 2 is craft and the moment together.

The report and the final message say how many passes ran against the usual three, so a short run never reads as a full one.

## Pass themes

**Pass 1. Structure.** Hierarchy, layout, spacing and type. One spacing scale, at most five type sizes with named roles, one source of truth for color, radius and shadow tokens. Navigation that makes sense on a phone. Every screen has one clear primary action. Works at 1440, 768 and 390 wide.

**Pass 2. Craft.** The details that separate designed from generated.
- Real assets. See the next section.
- One icon family at one stroke weight.
- Color with depth. Tints and shades from the palette, not new hues.
- Motion at 150 to 300 ms with one easing, on state changes that matter.
- Every state looks designed. Hover, active, focus, disabled, loading, empty and error.
- Copy. `100x shots` saves every string the page showed in `.100x/shots/<label>/texts.txt`. Lint that file with `100x text lint <file> --profile ui`, fix what it flags in the source, and shoot again. Lint the source file itself only when it is plain prose.

**Pass 3. Moment.** The signature moment and its surroundings.
- Choreograph the first ten seconds. What appears, in what order, with what motion.
- Transitions between the key states. Feedback on every tap or click that feels physical.
- For games and toys, juice. Particles, screen response, number pops, satisfying completion.
- Sound as files or synthesized in code, off until the user turns it on. Never played while you test.
- Then propagate. Find the best looking screen and bring every other screen up to it. Polishing only the hero is the usual trap. Shoot each main screen and bring it up to the best one.

## Real art

Art assets are the owner's most repeated iteration. Treat placeholders as unfinished.

- If the `boneworks` skill is available, read it and use it for sprite sheets, tiles, textures, palettes, UI kits, effects and sound.
- Otherwise draw. Hand written SVG on a 24 or 32 unit grid, CSS shapes and gradients, canvas drawn procedurally with a seeded generator. Pick the palette first. Keep one style, flat or pixel or line, across every asset.
- Never use emoji for icons or art. Never ship a gray box where a picture belongs.
- Check every asset at 1x and 3x. Blur and stretch are findings.

## When there is no screen

A command line tool, an API or a library has no pixels to shoot. Run the same three passes on the first run instead. Pass 1 is structure, which means command names, flags, defaults and the shape of the output. Pass 2 is craft, which means aligned and colored output that degrades without a terminal, error messages that name the fix, and help text with examples. Pass 3 is the moment, which means a demo command or sample data that shows the point in ten seconds, and a README that opens with it. Read the output as a stranger would and log the before and after. The hero is a picture of the real output: a small script writes the demo command's output into a page (`demo.html`, the command above a block of monospace text), `100x shots demo.html --label final` shoots it, and that picture is the hero. Never type the output by hand. A pass with no shots still leaves its judge's folder `.100x/loops/pass-N`, because `polishPasses` may only claim passes that are on disk.

## Stop conditions

A pass ends when its list is done, `100x shots --label pass-N` has 0 broken, and its judge has answered and been answered. Stop at the configured count even if more could be done, because the review comes next and finds what matters.

A judge that ends `Better: no` is saying the pass made things worse, so fix that before the next pass and say so in `answers.md`. `100x finish` only warns about it, so nothing else stops a pass that is not better.
