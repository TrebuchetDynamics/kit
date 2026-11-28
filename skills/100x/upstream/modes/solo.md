---
name: 100x-solo
description: "Use for /100x-solo, or when the owner wants a whole 100x run done by this one model in this one chat, with no subagents, no helpers and no second model: 'solo', 'do it all yourself', 'never delegate'. Same pipeline as 100x. It judges its own work in writing at every step, as a stranger would, and says in the report and the final message that nobody else looked."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Solo

One model, one chat, no helpers. The full 100x run, where each second look that a normal run gets from another model is this model attacking its own work, in writing, with proof from running it, again and again.

This is weaker than a second model, and the run says so. A builder cannot see all of its own blind spots. Solo makes it hard on itself in ways a file can show, and `100x finish` refuses what it can check. `100x ref solo` has the rules and the whole procedure. Read it before the first challenge.

Done when `100x finish` has accepted the run, every challenge file passes `100x solo check`, every round and loop file holds its suspicions, and the final message says that no other model looked.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## What changes from `100x`

- **No one else starts.** No subagent, helper, child or judge, for any reason. Where any guide says to start a judge, a backup judge, a fallback or a child, a challenge takes that step instead. Not the Task tool, `100x helper`, `100x review-run`, `100x night`, `claude -p`, `codex exec`, `cursor-agent` or a browser subagent. Tools are fine. Handing work to another model is not. The first three refuse in a solo run, `100x run unset mode` refuses too (the flag is one way), and `100x finish` refuses a run that started one.
- **The same pipeline.** Stages 0 to 8 of the `100x` skill with its stage guides: the prompt, the one thing that must not break, the screens, the report, and the invariants. "No rule, no guess" stays fully on: a `NO RULE` answer from `100x verify cover` still starts the verification procedure, each property is shown to fail before it is trusted, and the ledger is attacked in the `properties` challenge and in every code round.
- **Challenges in place of judges.** Where the pipeline asks a judge, you challenge your own work, in another chair, in a file. `100x ref solo` says where and how.
- **This model judges.** The model in this chat builds and judges, whatever `builder`, `review` and `fallback` say in the settings. Never ask to switch, and never wait for another model.
- **The owner's number phrases** work: `5 rounds of judging`, `for 10 hours`, `3 versions` (one after the other, never at once, each sibling folder its own solo run with `100x run set mode solo` right after its `100x init`, and a dud ending as the variants guide says) and `no verification`. `max N subagents` is dropped, and the first line says so.

## The question

Every challenge starts with it. Ask it of the work as if someone else had made it, and ask it of the running product and the files, never of your memory of making it.

> Let's analyze this. Is it correct? Is it good? Be brutal. Assume it is not, and find out why.

## Steps

1. Stage 0 steps 1 to 4 of the `100x` skill. Solo starts a new run: an unfinished run in this folder that began another way keeps its way, so say that in one line and point to `100x-continue`. After `100x init` run `100x run set mode solo` at once, so a status check, a continue and the CLI know from the first minute. Settle the owner's rules (`100x ref rules`) with this reading: a rule against subagents is what this mode keeps.
2. Step 5, the prompt, and `100x prompt check`. Then the `plan` challenge: `100x solo new plan`, fill it in, and fix `project.md` where it found holes before anything is built.
3. Step 6 and 7. Write `Mode: solo` under Modifiers in `project.md`, and drop `max N subagents`. Step 8, the pre-flight: the line about the model is this one, "Solo: no helpers. I judge my own work and the report says so." Leave out the builder model comparison and the doctor `judge` warning: a solo run is a self-review by design. `100x-setup` stays a "call X" line. The 12 line limit still holds.
4. Stages 1 to 3 as the guides say. At the end of core, build and depth, before the stage's commit and tag: `100x solo new core`, `build` or `depth`, fill it in, fix what broke, `100x solo check`. Core only when a core ran and was not skipped, depth only when features were built.
5. Stage 4. Each pass ends with a loop challenge: write `ask.md`, run `100x review-call --loop pass-N`, which starts nothing and prints the steps, write `judge.md` and then `answers.md`.
6. Stage 5. The red run as the guide says, then `100x solo new properties` when the ledger has rows, and the property attack in `100x ref solo`.
7. Stage 6. The rounds of the `100x-judge` skill, with these changes: `100x brief` and `100x review-call` as usual, and no judge starts. Each round is a round challenge: take the seat the brief names, write the suspicions first, then `findings.md`, then triage, fix and `100x triage`. After the first round `100x run set review '{"status":"reviewed","model":"<this model, as your app names it>"}'`.
8. With a fill clock, arm the watchdog as `100x ref watchdog` says: it is a message into this thread, not another model. Each round of `100x ref fill` ends with a loop challenge, the Skeptic lens and the last stretch are round challenges, and wherever the guide says run the judge you run one. Stage 7 and stage 8 as the guides say, and `100x solo check` before `100x finish`.

A challenge you write after the fact to satisfy the check is worth nothing. Write the suspicions before you run anything, and the findings before you fix anything.

## Reply

The output of `100x finish` is the final message. Add one line of your own: "Solo run: no other model looked at this. The judging was this model checking itself." Point to `100x-report`. End there.

## Rules

- No other model, ever, for any reason. When something needs a second opinion, say so in the final message and leave it to the owner.
- The challenge files are the evidence. A look that left no file did not happen.
- Never write that another model looked, name a judge you did not run, or let a note suggest it.
- Findings before fixes. Triage before changes. Never edit `findings.md` after triage to drop a finding you dislike.
- A short clock shortens the run through the owner's number phrases or through wrap up, never by skipping a look.
- `100x-grind` does not apply: it needs a fresh judge to say yes, and this model cannot be one.
- A solo run fills the window faster than a normal one. Keep `STATE.md` true after every stage and every challenge, and read the files back from disk.
