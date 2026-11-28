---
name: 100x-wrapup
description: "Use for /100x-wrapup, or when a deadline is close and a project must just work: 'wrap it up', 'I have until 5pm'. The main path runs from a clean start, everything unfinished is hidden or removed cleanly, and a short note says what is what. No new features."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Wrap up

A deadline and a project that must just work.

Working beats finished. By the deadline one path runs from a clean start, everything unfinished is switched off or removed cleanly, and a short note says what is what. No new features.

Done when a fresh checkout of the branch installs and starts with the written command, the one path ran once with its output kept, `WRAPUP.md` is written, and the work is committed and tagged `100x/wrapup`, with at least 10 percent of the time to spare.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## Steps

1. Model. `100x config target quick`. If it names a model (`{}` means this thread's own model, so there is nothing to compare) and this thread runs another or a lower effort, say so in one plain line and carry on.
2. Deadline. Take it from the message and write it in digits: "by five" is `by 5pm`, "in an hour" is `in 60 minutes`. With none, use 60 minutes, say so and log it with `100x log frame "no deadline given, 60 minutes" "<why>"`. Then `100x init` if the folder has no `.100x`, and `100x clock set "<deadline>"`. Never ask.
3. Branch `100x/wrapup-<yyyymmdd>`, made with `git switch -c`. Stage only files you changed and leave the owner's other uncommitted files untouched.
4. The one path. One sentence in verbs, "A user signs in, adds an item, sees the total". Take it from `.100x/project.md`, the README, the last commits and the routes. Log it with the reason.
5. Inventory by running, not reading. Start the project and try each feature. Mark each as works, half, broken or not started, in `.100x/STATE.md`. Run the project's own tests once and keep the output.
6. Cut plan. Anything not on the path that is half, broken or not started is hidden or removed so nothing leads to a dead end. Prefer hiding behind one flag or one route comment, because it is cheap to bring back. Remove dead buttons, empty pages and half migrations from the visible surface. Write each cut and how to turn it back on.
7. Make the path work. Fix only what blocks it. Stop at the first version that runs end to end. No refactors, no upgrades, no polish unless it hides the path. A fix that would take over a quarter of the time left is replaced by a labelled stub, never an unlabelled fake.
8. Check the clock at every boundary with `100x clock`. At 50 percent used and the path still not working, switch to stubs for the broken part and say so in `WRAPUP.md`.
9. Verify from clean. Commit the work first, staging only your files, because a check of the old commit proves nothing. Then `git worktree add --detach ../wrapup-check`, which checks out that commit and makes no branch. Run the install, the build and the start command there, and run the path once. For a visual project add `100x shots <url> --label wrapup --viewports 390x844@3,1440x900@1` and look. Copy its shots into `.100x/shots/` of the real folder, then `git worktree remove --force ../wrapup-check`. A fix made after this goes back to step 7 and is committed before you verify again.
10. Write `WRAPUP.md`. Works (the path, the run command, the evidence). Cut (each item and how to turn it back on). Known problems (honest, from your runs). Left to do (in order). Time (finished at, minutes spare).
11. Commit `WRAPUP.md` and the shots, tag `100x/wrapup`. Stop every dev server. `100x log done "wrapup" "<what works>" "<the path output>" done`.

## Reply

Eight lines at most. Works or not first. The run command. What was cut. Known problems. No questions.

## Rules

- No new features, no dependency upgrades, no schema or data changes.
- No deploy. A preview only when the project already has one configured and the owner asked for it. Never production.
- No sound. Mute every browser you drive.
- If the path cannot work before the deadline, say that at the halfway mark in `WRAPUP.md` and wrap up what does work.
