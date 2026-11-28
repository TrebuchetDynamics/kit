# Recipes for `100x shots`

`100x shots <url|file|folder>` opens the target in Chromium with no window, at many screen sizes and pixel ratios. It takes a screenshot of each state and runs simple checks. `100x help shots` lists every flag. Output goes to `.100x/shots/<label>/`. It holds one PNG per state, `matrix.json`, `matrix.md`, `contact-sheet.png` for you and `contact-sheet.html` for the owner.

## Labels

Use the stage as the label so the report and the judge find the right folder. `core`, `build`, `pass-1`, `pass-2`, `pass-3`, `must-not-break`, `final`. `100x finish` reads the best label in that order and reports its counts.

## Matrices

| Matrix | Viewports | Use |
|---|---|---|
| `standard` | phone, small phone, phone landscape, tablet, desktop, desktop HD | polish passes and quick checks |
| `phone` | 320x568 up to 430x932, both landscape sizes | touch first apps |
| `tablet`, `desktop` | the named group | focused checks |
| `all` | 15 viewports from 280x653 to a 3440x1440 ultrawide | the review and `final` |
| `all-rotate` | `all` plus a rotate test with no reload | the one thing that must not break for `screen-sizes` |

Pass your own list with `--viewports 390x844@3,844x390@3`. Touch emulation switches on when the short side is 820 px or less.

## Reaching states

A page that only looks right on its first screen is not tested. Use `--steps` with a JSON array or a file.

```
100x shots http://localhost:5173 --label must-not-break --matrix all-rotate --resize-test \
  --steps '[{"waitFor":"#game"},{"shot":"idle"},{"click":"text=Upgrade"},{"wait":400},{"shot":"shop"},{"press":"Escape"},{"shot":"after-close"}]'
```

Actions are `goto click tap dblclick hover fill press type wait waitFor scroll eval viewport shot`. A step that fails is a broken finding named `stepFailed`, so a missing button shows up as a defect and not as a quiet skip. A step waits 10 s for its target before it fails, in every viewport, so try new steps on one viewport first with `--viewports 390x844@3`.

Two states with one name get a number, `initial` and `initial-2`, so no shot is overwritten. Before each check and screenshot the run waits for every finite CSS animation and transition to end, up to 2.5 s, so a sheet is not measured while it is still half transparent. Endless loops are ignored. A short `wait` after the click that opens a sheet still helps on a slow page. With a modal open (`aria-modal="true"` or `<dialog open>`) the overlap check compares only the controls inside it, even while it fades in. A real run on software rendering at a high load average saw the first frame arrive 450 ms late and reported controls behind a sheet that was on its way in.

Never give a clickable control an endless `transform` animation. A click waits for the target to hold still and times out at 10 s. Pulse it with `box-shadow` or `opacity` instead.

A viewport that cannot be captured at all is one broken finding named `viewportFailed`. The other viewports still report, and `matrix.md` lists that state with no screenshot.

## Late game and awkward data

`--init-script` runs before the page loads. Seed `localStorage` with a save in late game magnitudes, an empty account, a very long name, or a huge list. `assets/seed-localstorage.js` in the must-not-break skill is the starting point. Run once per extreme, with its own label.

Make the seed hit every number the page can show at its longest. Coins at 1e45, every row owned in the hundreds, the largest stack of the permanent currency, most achievements done. Then open every sheet and dialog in that state with `--steps` and look at the narrowest viewport (280 px) first. A real run found the prestige sheet printing 993478736561583400000 in plain digits and the score chip letting its number run out of the box, both only in this state.

## Reading the result

- Broken is a real defect. Overflow, clipped text, text that sticks out of its chip or button (`spill`), a stretched or blurry canvas, a broken image, a console error, a failed step, a blank page. Fix all of them.
- Weak is a guideline miss. Tap target under 44 px, text under 12 px on a phone, overlap, no viewport meta. Fix each or write one line saying why it stays.
- Info is context, such as safe area use.
- Counts come with totals. `matrix.md` states how many elements were looked at. A zero over very few elements means the check had little to look at.
- Open `contact-sheet.png`, one image holding every shot with its counts, then open single screenshots for the smallest phone, the landscape phone and the widest desktop. Mechanical checks do not see a layout that is technically intact and plainly wrong.
- A folder or a file is opened from disk, and a browser blocks the scripts, fonts and data a page loads from disk, so a page built from modules shows up blank and `shots` says so, with the fix. Shoot the dev server address, or serve the folder, when the page loads anything.
- Alternate looks (a dark theme, a high contrast mode) are not in the matrix. Switch each one on with a step and look at it once.

## Speed

A run at 6 screen sizes with a few states takes under a minute. Use `--matrix standard` in polish passes and `--matrix all` or `all-rotate` once, at the must-not-break stage. Start the dev server once and keep it running through the stage, then stop it at the end of the run.
