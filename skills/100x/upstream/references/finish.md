# Stage 8. Finish

Done when `100x finish` succeeds. It refuses to close a run it cannot prove. That refusal is the point, so read what it names and fix the cause, never the check.

What it checks, so you can have it ready.

- A real hero. The file sits inside the project, is an 8 bit PNG (what `100x shots` writes) at least 200 by 200 pixels, and is not one flat color. A JPEG, WebP, GIF or other kind of PNG is refused, because only this kind can be checked for a blank page. A blank hero usually means the page was not up when you shot it. A project with no screen shoots its real output, see "When there is no screen" in `polish.md`.
- A resolution matrix from this run. It is the latest `100x shots` run, it started after the run did, `100x shots` signed it, and it looked at the prototype: a file inside the project, a page on this machine, or the address `run.json` names. It looked at what `url` opens: screens of a file do not back a run whose `url` is a served address, and the other way round. A matrix file typed or edited by hand does not count, and neither does a run of someone else's site. A project with no screen records `100x run set matrixSkipped "<reason>"` instead.
- A `ship` verdict needs a final matrix with 0 broken and no failing must-not-break check. Otherwise the verdict is `fine`.
- Each must-not-break check, one or two of them, has its output file `.100x/must-not-break/<kind>.txt`, a summary with numbers, and no contradiction between its status and that output. A `screen-sizes` check rests on its all-rotate screen run, which `100x shots` signs. It needs no output file, and typed words do not count for it.
- `polishPasses` is no more than the passes on disk: `shots/pass-N` or `loops/pass-N` folders. The passes on disk reach `polish.passes` (a run that needs work takes `polish.dudPasses`, a mockup takes none), unless 80 percent of the clock was used and wrap up took over, and when the owner asked for fewer, `100x config set polish.passes <n> --local` says so. The report shows "1 of 3" for either.
- Every ask is `- [x] text (evidence: where to look)` or `- [~] text (dropped: reason)`. Where to look names a commit, a file, a command in backticks or a number, as a triage reason does.
- For a reviewed run, the log has a `review` row for the judge (stage 6 writes it), and every finding has a triage line with a reason that points at something checkable.
- A mockup (`mode` mockup) has `MOCKUP.md` in the project folder, no polish passes, and the short clock it set in its first minutes (`100x clock set +15m`). A run that was polished is a normal run.
- Facts the owner can read in ten seconds. `title` is 70 characters at most, `pitch` and `moment` 240, `verdictWhy` 320, one `tryFirst` step 200, one must-not-break summary 400. The refusal names the fact and the length. Keep the numbers for the report.

## 1. Final proof

- `100x shots <url> --label final --matrix all` with `--steps` for the key states. Zero broken. Fix the weak lines, or write the reason they stay in the Asks ledger or the log.
- Close every ask in `project.md` with its evidence or its reason.

## 2. Record the run facts

Set each fact with `100x run`, never by editing the file.

```
100x run set title "Springtails Idle"
100x run set pitch "An idle game where you farm springtails in a terrarium that grows as you play."
100x run set verdict ship
100x run set verdictWhy "The core stage held attention for a full minute and the screenshot is worth sending."
100x run set moment "The first tap makes the whole terrarium bloom."
100x run set url http://localhost:5173
100x run set runCmd "npm run dev"
100x run set hero .100x/shots/final/phone-390x844-3x__idle.png
100x run push tryFirst "Tap the big button twenty times"
100x run push tryFirst "Open the shop and buy the first upgrade"
100x run push mustNotBreak '{"kind":"screen-sizes","status":"pass","summary":"0 broken of 212 elements across 15 viewports and 3 states"}'
100x run set review '{"status":"reviewed","model":"<model id>"}'
100x run set polishPasses 3
100x run push features '{"name":"Prestige","cutHint":"delete src/features/prestige and its line in features.js"}'
100x run push nextAsks "Daily rewards"
```

- Stages 3, 5 and 6 already set `features`, `mustNotBreak` and `review`. Check them with `100x run show`.
- `verdict` is the core stage's word after polish. Change it only with a reason in `verdictWhy`.
- Write each fact for a person reading on a phone. `verdictWhy` is one or two plain sentences: what you saw and why it earns the word. Scores, file names and frame counts live in the report. Too long: "Scored 5 of 6 (first minute 2, screenshot 2, second day 1): a frame 216 ms after the tap shows ...". Right: "A stranger gets the point on the first tap and the first screen is worth sending. The second day is thin."
- `runCmd` is the project's own start command, the one the owner types in the project folder (`npm start`). It never has `100x` in it and no port of yours: the report page sets the port from `url` itself, and `100x finish` refuses a `runCmd` that runs `100x`, or one that names a package script or a file the project folder does not have (`npm run serve` with no such script). `url` is the address it opens at by default. Leave `url` out for a command line tool, and the morning page offers the command to copy instead of a Run button.
- `hero` is the screenshot that sells the moment. A phone portrait of the signature moment is usually right. Pick it from the final shots and look at it.
- `tryFirst` is two to four steps that reach the moment fast, written for someone who has never seen it.
- An unreviewed run uses `100x run set review '{"status":"unreviewed","note":"<reason>"}'`. Reviewed counts come from the triage files, so leave them out.
- A mockup also sets `100x run set mode mockup`. Then `100x finish` accepts UNREVIEWED without a judge attempt and needs no must-not-break check. A solo run sets `100x run set mode solo` and no other mode. `100x finish` then checks the challenge files in `.100x/solo` (`100x solo check` runs the same check), the suspicions in every round and loop file, that no helper or judge command started, and marks the review as a self-review. `review.model` is the model of this chat. No other run sets `mode`.
- `ship` is optional. `100x run set ship '{"preview":"https://...","note":""}'`.

## 3. Close

1. Stop every dev server you started.
2. `100x finish --check`. Fix what it names. It also reads the pitch, the moment, the reason for the verdict, the steps and the next asks with the writing tool and names stock phrases in them. Say those plainly with the `100x run set` command it prints. The check says ready either way, because a phrase is a warning and not a refusal.
3. Commit, then tag `100x/finish`, so the tag marks the commit that passed the check. A change after that is committed and the tag moved with `git tag -f 100x/finish`.
4. `100x finish`. It copies the hero, writes the report as a page (`.100x/REPORT.html`) and as text (`.100x/REPORT.md`), adds the run to the registry behind the report page, writes `.100x/finished.json`, and prints the summary.
5. Disarm the watchdog if you armed one. See `references/watchdog.md`.
6. `100x log done "<verdict> and <n> decisions" "run closed" "<finish output line>" done`. The last row of the log is a `done` row.
7. Send the finish output as the final message. Add the UNREVIEWED reason if there is one. If it has a `Look first.` line, keep it where it is, right after the verdict: a failed check, a broken screen size, no judge, or a judge who said not ready to ship. Stop. Do not ask what to do next.

`100x report` rebuilds both reports from the run facts if you edit them later.
