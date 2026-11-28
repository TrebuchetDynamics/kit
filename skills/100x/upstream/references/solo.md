# Solo

How one model runs the whole 100x pipeline alone, and judges its own work in writing at every step where a normal run asks another model.

Read it before the first challenge of a solo run. `100x solo new <name>` and `100x review-call` print the parts you need at each step, and this file has the reasons and the whole procedure.

## The honest limit

A second model catches what the builder explains away, because it does not share the builder's reasons. A solo run has none, and no procedure removes a model's own blind spots. Solo does not pretend to. It makes the builder harder on itself in ways a file can show: findings are written before fixes, every claim names something that was run, each look starts in another chair, and a clean result is looked at again. `100x finish` refuses what it can check. The report says the judge was the builder, and the owner reads that before the good news. Never write that another model looked.

The guards and the checks stop what a hurried model does and what a careless run leaves behind. They cannot stop a model set on cheating: the flag, the clock, the ledger, the helper log and the challenge files are all files in `.100x/` that it writes itself, and a proof is checked for its shape, not re-run. What holds a solo run honest is the model keeping to the rules below, and the owner reading the challenge files and the report. For work that matters, have a second model judge the finished run afterwards with `100x-judge`, as a separate run the owner starts.

## The question

Every challenge starts with the same words, and you ask them of the work as if someone else had made it:

> Let's analyze this. Is it correct? Is it good? Be brutal. Assume it is not, and find out why.

Then you do the things below, which is the part that makes the question mean something.

## The rules of a challenge

1. **Commit first.** The thing you judge must not move while you judge it.
2. **Change chairs.** The `Seat: <who>` line sits right under the title of a challenge file, and on the first line of a round's `findings.md`. Until the findings are written you are that person: someone who did not build this, owes its maker nothing and does not know why anything is the way it is. The seats are in the table below.
3. **Read what a stranger reads.** The brief file, the ask file, the running product, the screenshots, the ledger. Do not reread `STATE.md`, your decision rows, your commit messages or your earlier answers to decide that something is fine. They are the reasons that blind you. For a screen, write one line per screenshot of what you see in ten seconds, before you read what changed.
4. **Suspect first, then test.** Write the suspicions before you run anything. Each is a sentence that could be false: "a second tap while the total loads charges twice". Then run something for each one. Add what you stumble on.
5. **Proof from this look.** Each suspicion ends with `Proof:` (a command in backticks and what it printed, the path of a screenshot you opened, a file path such as `src/app.js` or `shots/review/phone-320.png`, or a commit) and `Result: holds` or `Result: broken`. A number alone is not proof, and neither are words with a slash in them, so put a number next to the command that printed it. "I remember handling that" and "it looks fine" are not proof. Each suspicion starts with an id, `S1`, `S2` and so on, and a recheck item with `R1`, so a fix can name it. A finding line in `findings.md` or `judge.md` starts with its severity word, `blocker`, `major`, `minor` or `nit`, with or without `F1 [major]` in front, and it ends the suspicion list above it. Check a number by a second route: by hand, or in a throwaway script that shares no code with the project.
6. **Findings before fixes.** Write the whole file first, with severities. Then triage. Then fix. A fix made while judging is a finding nobody saw.
7. **Answer as the opponent.** To reject a finding, first write the best case that it is right, then the command or screenshot that beats it. When you reject more than a third, read the rejections again.
8. **A clean look is suspect.** When nothing broke, write what each probe would have shown if the work were broken. Then look again from another seat with harder inputs. A clean result stands only when the recheck is clean too.
9. **Yes is the hardest word.** Before you write "Ready to ship: yes", try to finish the sentence "I would not ship this because...". When you can finish it with something that reproduces, the answer is no.

| Look | Seat |
|---|---|
| plan | the owner reading `project.md` cold on day two, who wanted something else |
| core | the owner opening the slice cold, with one minute |
| build | a stranger on a fresh clone who owes the builder nothing |
| depth | the owner who asked for none of the extra features and will notice every one |
| properties | an adversary who holds the specification and is paid for every counterexample |
| a code round | a staff engineer who is paged when this breaks and did not write it, then in the second code round a tester paid for every bug, who starts with the inputs nobody expected |
| a UI and UX round | a stranger on a phone with ten seconds to spare, who owes the maker nothing, then in the second one a first time user on the slowest phone, who cannot ask anyone and will not read a manual |
| the ship round | a person deciding whether to put their name on this, who knows the best alternative, or a competitor reading it to find the reason not to pick it |
| a polish pass or a fill round | one of three chairs by its number: a stranger on a phone, a user on the slowest phone, a skeptic who has used the best alternative for years |

Two looks in a row never use the same seat. A lens has two seats and the position of the round within its lens picks one (the first code round the first seat, the second code round the second), a loop takes its chair by its number, and a recheck always takes a seat other than the first. The brief and `100x review-call --loop` name the seat.

## Where each challenge happens

| Where | A normal run | A solo run |
|---|---|---|
| Stage 0, after `100x prompt check` | nobody judges the prompt | the `plan` challenge |
| Stage 1, Core | the builder scores the slice | the `core` challenge |
| Stage 2, Build | the builder's quick check | the `build` challenge |
| Stage 3, Depth | the builder's cut hints | the `depth` challenge |
| Stage 4, each polish pass | a loop judge | a loop challenge |
| Stage 5 | the red run, and the ledger | the red run as usual, then the `properties` challenge |
| Stage 6 | judge rounds: code, UI and UX, ship | the same rounds, each one a round challenge |
| A fill clock, each round | a loop judge | a loop challenge |
| A fill clock, the Skeptic lens and the last stretch | one more judge round, and the judge before the finish | a round challenge, with the seat and the brief of its lens |
| Stage 8 | `100x finish` | `100x finish`, which checks all of this |

## Challenge files

For plan, core, build, depth and properties. `100x solo new <name>` writes `.100x/solo/<name>.md` with the seat, what to read, the questions to start from and the form of a suspicion. It refuses to overwrite. `100x solo check` says which files the run owes and what each one lacks, and `100x finish` makes the same check. Core is owed when a core row was logged and it is not a skip (`core.enabled` false, or a big change with a clear spec, logged as `skipped`), depth when `run.json` lists features, and properties when the ledger has rows.

```text
# Challenge: build
Seat: a stranger on a fresh clone who owes the builder nothing

## Suspicions
- S1 The install line in the README fails on a clean checkout. Proof: `git clone . /tmp/x && cd /tmp/x && npm ci` exited 0 in 41 s. Result: holds
- S2 Two quick taps on Add make two rows. Proof: `node scripts/double-tap.mjs` printed 2 rows. Result: broken
(three more, at least five in all)

## Fixes
- S2 fixed in a1b2c3d, and `node scripts/double-tap.mjs` now prints 1 row.

Verdict: fixed
```

A file passes when it has at least five suspicions, each with an id, proof that names a command, a file or a commit, and a result, and a verdict that is closed. Every broken suspicion, in the suspicions or in the recheck, needs a list item under `## Fixes` that starts with its id and names a commit, a path or a command, so the fix is tied to the break and says what was run again. Recheck items are numbered `R1`, `R2` and are held to the same rules. When nothing broke the verdict is `holds`, and only after `## Recheck`: its own `Seat:` line, different from the first, and at least three more suspicions in the same form. A recheck that finds a break counts, and the verdict is then `fixed`.

## The property attack

At stage 5 once the ledger has rows, and again in every code round and in the ship round. A property that only the builder tried to break is a claim, so you try as the adversary.

1. For each row, read the code it covers, not the model. Write an input or a sequence of steps that breaks the sentence, and run it against the real function. A hit is a finding, and the row is amended with `100x verify amend` or the code is fixed.
2. Write five things that must always be true about this logic that no row states: conservation, order, doing it twice, bounds, who may do it. Each one becomes a row with `100x verify add`, or a waiver with `100x verify waive` and the reason.
3. For each row, read what its model leaves out and how large it is. Widen one bound or add the missing case, and run it again. A pass that holds only at the smallest size has the level `bounded`, and the row says what is not covered.
4. A property touched by a fix this round gets its red run again, so the check is shown to fail for the seeded defect and not for a typo.
5. `100x verify status` must say every row holds before the round closes.

## A loop challenge

For a polish pass or a fill round. Write `.100x/loops/<name>/ask.md` as the references say, then `100x review-call --loop <name>`. It starts nothing and prints the ten steps, which are always the same: commit, sit in the chair it names, open the pictures before you read what changed, name how to judge, at least five suspicions, run the flow with your own inputs, findings, `Drifting` and `Better`, the clean-look recheck, and only then `answers.md`.

`judge.md` keeps the loop judge's shape: a first line `Judged by: looking`, `running`, `numbers` or `words`, a second line `Seat: <the chair>`, a `## Suspicions` list, a `## Findings` list with one line for each finding and one of its own for each broken suspicion, a `Rechecked:` line when there are no findings, and the last two lines `Drifting: yes|no` and `Better: yes|no`. `Drifting: yes` or `Better: no` means the next loop starts with the fix. Judge the way that is hardest on the work, not the way that is easiest for you. A visual loop is judged from the single screenshots, never from the source. When this chat cannot see images, the first finding says so as a blocker, the file ends `Better: no`, and no look at the screen is claimed: finish warns about it and the report must say that the screens were not looked at. A broken suspicion in a loop is also a finding, a line that starts with its severity, and `100x finish` counts them.

## A round challenge

Stage 6, up to `review.rounds`: the code and how it behaves, then the UI and UX, then the ship test. The owner's `5 rounds of judging` sets the number.

1. Commit. Stop your own dev server so its port is free.
2. `100x brief` opens the round and writes the brief for the builder in another chair. `100x review-call` says which round and lens it is, and that nothing starts. `100x log review "solo round <n>, seat <who>" "self-review by design, no other model" "this chat"`.
3. Read the brief file and nothing else. Take the seat it names. Write `.100x/review/findings.md`: `Seat:` first, then `## Suspicions` with at least eight, written before you run anything, then the findings in the brief's format, then `What is good` and `Verdict` with the line `Ready to ship: yes` or `Ready to ship: no`. Every broken suspicion is also a finding with a severity, one for each, named by its id. Two rounds in a row never carry the same `Seat:` line. In a code round and in the ship round, when the ledger has rows, the property attack above runs in full, all five steps, and what it finds is written as suspicions. The brief leaves out your commits and decision notes on purpose.
4. A look that finds nothing is suspect. Write what you tried and what each probe would have shown if the work were broken, look again from another seat, and add a line starting with `Rechecked:`.
5. Only now write `.100x/review/triage.md`, one line for each finding, with a reason that points at something checkable. Fix what you accepted, blockers first, run it again, commit.
6. `100x triage` closes the round and says what is next. The next brief carries your earlier findings and your answers. Check each accepted finding by running the product, never by reading your commit message.
7. After the first round: `100x run set review '{"status":"reviewed","model":"<the model of this chat, as your app names it>"}'`. The model is this chat's own, never one from the settings.

`100x-grind` does not apply to a solo run. It needs a fresh judge to say yes, and this model cannot be one.

## What the owner reads

`100x finish` records the run as solo and as judged by the builder. The registry and the morning page list it as `(solo)`. The report says `Review (<model>, the same model that built it. A solo run, so no other model looked)`. The card's trust line says "A solo run: the model that built it judged it and no other model looked", in the amber of a missing second look and never in the green of a cleared run. The final message says it in a line of your own.

## Never

- Start another model for any reason. Not the Task tool, not `100x helper`, not `100x review-run`, not `100x night`, not `claude -p`, `codex exec` or `cursor-agent`, not a browser subagent. The first three refuse in a solo run, and `100x finish` refuses a helper row or a judge command. The rest no file can stop, so it is yours to keep. Where any other guide says to start a judge, a backup judge, a fallback, a helper, a child or a subagent, this file replaces that step with a challenge.
- Take the solo flag off, or set a clock at the end of the run to make UNREVIEWED look allowed. The flag is one way, and finish refuses a clock that was not set when the run began.
- Change `findings.md` after triage to remove a finding you do not like.
- Write "Ready to ship: yes" without having tried to finish "I would not ship this because...".
- Skip a look to save time. A short clock shortens the run through the owner's number phrases or through wrap up, and `100x finish` refuses a run with a missing round.
- Name a judge you did not run, or let a note suggest that someone else looked.

## The window

A solo run fills the window faster than a normal one, because no helper holds a share of the work. Keep `STATE.md` true after every stage and every challenge, send long output to files under `.100x/`, and read challenge files back from disk instead of from memory. After a restart `100x solo check` and `100x status` say where the run stands.
