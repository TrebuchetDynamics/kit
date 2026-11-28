---
name: 100x-mockup
description: "Use for /100x-mockup, or when the owner wants to see an idea as running code fast: 'mock it up', 'just show me'. Only the moment has to work. It runs no judges, takes about 15 minutes and ends UNREVIEWED, and says so on its card and in the final message."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Mockup

The owner wants to see the idea, not read about it. A mockup is the idea as running code: something to look at and click, fast.

Only one thing has to really work: the moment. Everything else can be fake, static or hard-coded, and never has to work. Code quality does not count in this mode. Licenses still apply: use your own art, art you may reuse, or a placeholder marked as one, and name anything borrowed in `MOCKUP.md` so it gets replaced before building properly. No judge looks at it, not in loops and not at the end. The owner does, in the morning gallery. The run ends marked UNREVIEWED and says so.

Done when it runs from one command, you have looked at its screenshots, `MOCKUP.md` says whether the idea holds, it is committed, and `100x finish` has accepted the run, so it shows on the report page. Aim for 15 minutes, never past 30.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## Steps

1. Model. `100x config target quick`. When it prints a model and your app shows this thread on another model or a lower effort, say so in one plain line and carry on. Never switch or wait.
2. Folder. In an empty folder, build there. Inside an existing project, use `mockups/<slug>/`. Otherwise `./<slug>/`. `100x init` (with `--fresh` when it says an earlier run is here), then `100x clock set +15m` and `100x run set mode mockup`, so a status check, a continue and a retried night child know from the first minute that this run is a mockup. A night child keeps this clock too, not the night's deadline.
3. The question. One sentence, "Does <thing> feel <way>?". It decides what to build and what to fake. `100x log --start <slug>-<yyyymmdd-hhmm>`, then `100x log start "<question>" "<why this reading>"`. Write `.100x/project.md` short: the brief word for word, the goal in one line, the `## Asks` ledger with one `- [ ]` line per ask, and the moment. The prompt sections of stage 0 and `100x prompt check` do not apply to a mockup. Never ask the owner anything. Infer. The 100x skill's 12 line pre-flight does not apply here. Send one line instead, "Mockup: does <thing> feel <way>? Back in about 15 minutes. Call 100x for a full build.", and start building. When the brief also asked for time, versions, rounds of judging or helpers, add "Dropped: <what they asked for>." to that line, because a mockup has none of them.
4. Smallest stack. One `index.html` with inline CSS and JavaScript, no install and no build, unless the question needs a server or the project's own framework. A single file needs no server: the run command is `open index.html` and `100x shots index.html` reads the file. With a server, use the dev-server rule in the 100x skill (a background job of your shell tool, never a trailing `&`).
5. Fake the rest. Hard-coded data, stub APIs, no login, no saving. Real art for the one moment that matters, never gray boxes. Pick one named look from `100x ref looks` in ten seconds and use its palette and type. A taste fork gets a switch only when both sides take under a minute.
6. Look once. `100x shots <file or url> --label mockup --viewports 390x844@3,1440x900@1`, then open the screenshots. Then one more run with `--steps` that does the key moment (click, wait, shot) and look at that too. Fix what is blank, clipped or broken once. No second pass, no loop judge.
7. Mark it. `100x run set review '{"status":"unreviewed","note":"mockup mode, no judges by design"}'`. Nobody later mistakes this for a reviewed build, and `100x finish` does not look for a judge.
8. Write `MOCKUP.md`. The idea, the question, the verdict (`holds`, `unclear` or `does not hold`) with one line of why, the run command, three things to check, what is fake, what to replace before building properly (borrowed art and fonts, with where they came from), and a paragraph that can be pasted after the 100x skill name to build it properly.
9. Close. Stop any server and commit. Close the asks with evidence, fill `run.json` as `100x ref finish` says, and run `100x finish`. A mockup has no polish passes (`polishPasses` 0), needs no must-not-break check, and has no judge. `100x finish` turns back a mockup that has polish passes, no `MOCKUP.md`, or no short clock set in its first minutes. Add one quick check only when a wrong answer would make the idea a lie, such as money, scores or dates. The verdict is `ship` when the moment lands, `fine` when it works and the moment does not land, `dud` (shown as "Needs work") when the idea does not hold. Then `100x log done "<verdict>" "<why>" "<screenshot path>" done`.

## Reply

Six lines at most. The verdict first, then the run command, then the screenshot path, then `MOCKUP.md`. No questions.

## Rules

- No judges, no deploy, no tests beyond "it loads and the key moment works".
- Code quality does not count. Spaghetti is fine. Nothing in a mockup gets reused.
- A licence question never stops a mockup, and the licence still applies. Use your own art, anything you may reuse, or a placeholder marked as one. Anything else that makes it look right goes in `MOCKUP.md` under "Replace before building properly", with where it came from. Never keep another product's logo or art in a mockup the owner might share.
- Only the moment has to work. Dead buttons and fake screens are fine when they do not block it.
- No sound. Mute every browser you drive.
- No subagents, no versions, no `for N hours`, no rounds of judging.
- A mockup that cannot answer its question in 30 minutes is a finding. Say what blocked it in `MOCKUP.md` and stop.
