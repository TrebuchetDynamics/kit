---
name: 100x-judge
description: "Use for /100x-judge, or when the owner wants a second model to judge what 100x already built: 'judge it', 'is this ready to ship'. Runs judge rounds, triage and fixes, and builds nothing new. Stage 6 of a normal build runs these same rounds."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Judge

Judge rounds on what is already built. Nothing new builds.

The model that built a prototype shares its own blind spots. A second model that runs the thing and reads it with fresh eyes catches what the builder explained away. It is asked one question, "is this ready to ship, be brutal", in rounds. The judge looks, you fix, a fresh judge looks again and checks your fixes. `review.rounds` sets how many, 5 by default. Round by round the lens moves from the code and how it behaves, to the UI and UX, and the last round is the ship test over everything. A clean round skips the rest of its lens. It is the only second agent a run starts by default. No setting about helpers or counts limits it, and only `review.enabled false` turns it off. Never skip it because you expect a limit. Try to start it. The `100x-grind` skill is this skill with no round count: the rounds go on until a judge says yes.

In a solo run (`run.json` says mode solo) no second model starts, so skip steps 5 and 6, the check of the model that ran, and the section "When the call fails": nothing can fail to start and nothing falls back. `100x review-call` says so, and the rounds are written challenges by this model: follow `100x ref solo` for them, the log rows of steps 4 and 10 included, worded there as a self-review. `review.model` is this chat's own model, never one a check names.

Done when `100x triage` says all rounds are done, every accepted finding is fixed and re-checked, and the run is marked reviewed, or it is UNREVIEWED with the reason.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

The same judge also sits in every loop, not only here. Each polish pass and each fill round asks a fresh judge the brutal question through `100x review-call --loop <name>`, with the ask at `.100x/loops/<name>/ask.md` and the answers at `answers.md`. The polish and fill references say when. Start and wait for a loop judge exactly as in steps 5 and 6 below, with the loop's 20 minute deadline. A loop judge adapts to its loop: it judges what a user sees with its eyes on the single screenshots and never from code, runs flows end to end, and tests numbers with its own inputs. Its first line says how it judged.

## Steps, once per round

Start after polish and the one thing that must not break check. The owner can set the number in words, "three rounds of judging", so run `100x config set review.rounds 3 --local`. Before each round run `100x clock`. `100x review-call` sizes `deadlineMinutes` to the clock, at most `review.timeoutMinutes`, so a run with an hour left still gets a short review and not none. A judge needs 15 minutes. The last fifth of a plain deadline belongs to wrap up and a fill clock keeps 5 minutes for triage and finish, so the judge never runs into them. When `review-call` says there is no room, stop the rounds, run the `100x run set review` command it prints, and finish, which then only warns.

1. `100x review-call`. If it says review is off, run the `100x run set review` command it prints, which records `unreviewed` with that reason, log it, and stop. It also prints `via`, which decides step 5, and the round and its lens. When it says the judge is the model that builds (`selfReview` in `--json`), that look is a self-review. Say so in the step 4 row and the review note, and offer the owner `100x-setup` to change it. With no judge chosen it says so and prints no `via`, and step 5's `none` bullet applies. "All rounds are done" means go to step 9 and finish.
2. Commit or save all work. The reviewer shares this checkout, so uncommitted files are visible to it. Stop your own dev server so its port is free.
3. `100x brief`. It opens the next round, archives the last one and carries the earlier findings with your answers to the judge. Skim the top of `.100x/review/brief.md`. The asks, the moment, the one thing that must not break and the run command must be right, because the reviewer gets nothing else from you. Fix `project.md` and rebuild the brief if not.
4. `100x log review "starting the second-model review" "<why now>"` with the model name from step 1. With no judge chosen, write this row after step 5 has picked one.
5. Start the reviewer by `via` from `100x review-call --json`. It returns at once while the reviewer works. The reviewer sees only the task and the brief, so keep your opinions out of both. Log the time you started and the task id or pid.
   - `command`. Run `100x review-run`. The configured shell command starts in the background, so it works in any agent app and with any vendor's command line tool.
   - `harness`. Pass the `delegateTask` object to your app's subagent tool. In Cursor never use the Task tool, because it ran Composer for every helper whatever model was asked for. Cursor helpers start through the SDK, at the 300k window and never in MAX mode (`100x helper run` refuses a selection that could be): `100x helper run --model <target.model> --effort <the effort> --context <the context window> --task "<task>"` with `block_until_ms` 0, and wait for its finished notice. Better, set `review.command` once to the SDK line in `100x ref apps` so `via` says `command` and `100x review-run` starts, checks and stops it. Elsewhere start a subagent on `target.model` with `task` as its instruction.
   - `none`. No reviewer is chosen. Where `helper.only` is set this never happens: with no judge model set, `100x review-call` makes the judge the locked selection and prints it. Otherwise pick the strongest model from a different vendor than yours that this app or a command line on this machine can start, check that it starts, log the choice and why, and go on. In Cursor the only way to start one is `100x helper run` with the SDK, at a 300k window and never in MAX mode, and never the Task tool. If nothing can start, take the last bullet under "When the call fails".
   - Then check the model that ran. For an SDK helper the `ran` line of `100x helper run` is the record, and exit code 3 means another model ran. For a Task helper `100x review-verify --requested <model>` reads the app's own record of the helper it started and prints ok, mismatch or unknown. A model name in a note is only what someone wrote. `mismatch` means the app ran another model: stop that helper, the round does not count as a review by the model you chose, and the next judge starts another way (`100x review-run`, or an app that honors the model). `unknown` means the app keeps no record. Write "model not verified by the app" in the review note, and `100x review-verify --setup` prints the one hook that makes Cursor keep it.
6. Wait the way `100x ref apps` says: where the app wakes your thread when the subagent ends, do other work and end the turn, and elsewhere run `sleep 240`, check `.100x/review/findings.md` and repeat. Never use a call that waits for the result, because it gives up after about a minute while the reviewer keeps going. The review is done when that file ends with a `## Verdict` section, or when `100x review-run --status` says exited, or when your app reports the subagent complete. Read the result once, and do not poll a running task. A real review takes 10 to 60 minutes. Past `deadlineMinutes` from `review-call --json`, see "When the call fails".
7. Read `.100x/review/findings.md`. It must contain findings or a "No findings" line. Triage every finding in `.100x/review/triage.md`, one line each. A reason points at something checkable, which is a commit, a file path, a command in backticks or a number, and `100x triage` refuses `ok` and `blah`.
   - `F1 accept. fixed in a1b2c3d, the row wraps at 320px`
   - `F2 reject. the button is hidden on tablets by design, shown in shots/pass-3/tablet.png`
   - `F3 defer. needs a backend, listed under next asks`
8. Fix accepted findings, blockers first. Re-run `100x shots` or the one thing that must not break check for what you touched. Commit.
9. `100x triage` must pass. It closes the round and says what comes next, another `100x brief` or all rounds done. Back to step 1 for the next round. After the first round, `100x run set review '{"status":"reviewed","model":"<model>"}'`, so a run that stops early still shows that a judge looked. The model is the one `100x review-verify` said ran, or the one you asked for with `"note":"model not verified by the app"` added when it said unknown. `100x finish` fills in the counts and the rounds from the files and refuses while a planned round is missing.
10. `100x log review "<n> findings, <a> accepted, <r> rejected, <d> deferred" "<what changed>" "<evidence>" done`.

## Judging findings

- Accept when the reviewer's evidence holds on your own run. Fix the cause.
- Reject only with your own evidence, such as a command output or a screenshot path. "I disagree" is not evidence.
- Defer only what costs more than the owner would pay tonight, with the cost named. A blocker cannot be deferred.
- If you reject more than half, read them again. Two models share priors, and the common mistake is defending your own work.
- A weak moment, a generic look and an ask that was narrowed are findings to act on, as much as bugs.
- A finding whose heading has no severity word counts as a blocker, so it cannot be deferred.

## When the call fails

- The model or provider cannot start. Retry once with `fallbackTarget` from `review-call --json` if it exists. With `via` command, run `100x review-run --fallback`. A status of `died` or a nonzero exit code with an empty findings file counts as cannot start. When `review-call` says the backup is the model that builds, its look is a self-review. Put that in the review note, and the report and the final message name it too.
- `100x review-verify` says mismatch on the fallback too, or on every try. The app cannot start the model you chose. Treat it as "No second model is reachable" below, name the model that ran in the note, and do not count its look as a review by another model.
- No second model is reachable. Review the prototype yourself with the rubric in the brief, record it with `100x run set review '{"status":"unreviewed","note":"no second model was reachable, self-review only"}'`, and say so in the final message. Reviewed means a different model reviewed it.
- The deadline passes and the child still runs. Stop it with your app's cancel tool and say why, or for a command reviewer `100x review-run --stop`. If `findings.md` has content, triage it as a partial review and say "partial" in the note. If it is empty, the run is UNREVIEWED.
- `findings.md` is missing but the child's summary lists findings. Treat the review as failed. Do not copy the summary into the file, since the file is the evidence.

## Settings

Model, effort, context window, timeout and fallback live in config, not in this skill. `100x config print` shows them and `100x-setup` changes them. Nothing vendor specific is built in. `100x doctor` says whether a reviewer is chosen. A command reviewer reads its model and effort from environment variables, see `100x ref apps`.
