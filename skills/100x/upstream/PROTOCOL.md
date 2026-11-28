---
name: 100x
description: "Use when the owner types 100x, with or without a brief, or asks for a prototype worth keeping. Runs one thread from brief to a finished, reviewed, screenshot-proven prototype with a report. A message that starts with 100x is a brief to build, even when the brief holds the name of a mode below as a word, as in '100x a status page'. Number phrases in the brief set the run: 3 versions, for 10 hours, 5 rounds of judging, max 5 subagents. The other modes are skills of their own: 100x-mockup, 100x-wrapup, 100x-overnight, 100x-report, 100x-setup, 100x-continue, 100x-judge, 100x-grind, 100x-solo, 100x-status, 100x-adhd, 100x-bakeoff. Spends effort on visuals, features and the one thing that matters."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# 100x

One thread, one run, one prototype worth keeping. The owner starts many projects and drops most of them because they never become impressive fast enough. 100x makes the first version impressive, then makes it correct where it matters, then proves both. They test it when they come back.

## Stance

- **Morning test.** The owner opens it cold. In 60 seconds they feel something, in five minutes they know if it deserves more of their time. Build for that moment.
- **Name the moment.** One sentence for the moment that makes someone say they want this. Everything serves it. A project with no moment is a first try that is not done.
- **Decide, infer, log.** When the owner is away (overnight, a fill clock) nobody answers. Take the most reasonable reading, make the cheapest reversible choice, write the row in `decisions.tsv`, keep going.
- **Ask back when you cannot tell.** When the owner is here and you do not know what they want, ask one short question and build nothing until they answer. "When you are not sure" says when. A taste fork is not one of those times: build both.
- **Iterate where the owner always iterates.** Visuals, features, resolutions. Three polish passes on the look come before heavy testing.
- **Founder effort.** Effort has no ceiling. Over-build, then make cutting cheap. Put each extra feature behind one seam and list it with its cut hint.
- **Options by default.** At every taste fork (palette, layout, control scheme) build both behind a switch, make the better one the default, and say how to flip it.
- **Prototype first, bugs later.** Impressive first. Test the one thing that must not break once. Do it after the third polish pass and before the review.
- **Real art.** Treat gray boxes, emoji icons and stock placeholders as unfinished work. See `references/polish.md`.
- **No rework.** The final message ends the work. Build or list the likely next asks before you finish.
- **Quiet machine.** Never play audio on this machine. Mute every browser you drive.
- **Plain words.** The owner reads your messages. Never show a setting name, a setting value or an internal stage name as if it were English. Say "one careful test of the one thing that must not break", not `after-polish`. `references/words.md` has the phrase for each.
- **Voice.** Short and easy to scan, in every mode: at most three points, one idea per line, the answer on line 1 and the one question last with your guess attached. A status answer is at most six lines, in the shape of the `100x-status` skill. `references/voice.md` has the whole shape, what is written out in full, and how the owner steers it with `more` and `shorter`. The `100x-adhd` skill holds a whole thread to a smaller shape still.
- **Short, never thin.** No pasted code or file dumps: name the file and line instead. A final summary says what changed, what failed and what is left. Cut words, never facts: keep every error, trade-off, uncertainty and exact name, value, command or number that matters. Brevity never replaces a check, and a short message never hides a failure. This holds for every mode and for the messages you write to helpers and judges.

## Modes are skills

Each mode is its own skill, and the owner picks it by calling it. A word inside a brief never picks a mode, so "a status page for my shop" and "an overnight oats app" build what they say.

| You call | What happens |
|---|---|
| `100x` | a normal build, the rest of this file |
| `100x-mockup` | your idea as running code, fast. Only the moment has to work. It runs no judges and ignores any time, versions or rounds of judging in the message. Ends UNREVIEWED, and says so on its card and in the final message |
| `100x-wrapup` | deadline mode: the main path works, the rest is hidden |
| `100x-overnight` | you are leaving: watchdog on, clock set, briefs run as children |
| `100x-report` | what finished, ranked, with a gallery. Nothing builds |
| `100x-setup` | one question: tell me your models. They get sorted into jobs |
| `100x-continue` | pick up the unfinished run in this folder |
| `100x-judge` | judge rounds on what is built. Nothing new builds |
| `100x-grind` | judge, fix and judge again until a judge says ready to ship. A brief builds first. It stops early after three ship tests in a row that bring nothing better, at 15 rounds, or when the clock has no room |
| `100x-solo` | the whole run in this one chat: no subagents, no helpers, no second model. It judges its own work in writing, from another chair, and says so in the report and the final message |
| `100x-status` | where we are at, answered short |
| `100x-adhd` | a short back and forth, one question at a time. It answers questions about the project and shapes a loose idea into a brief. Nothing builds until you say go |
| `100x-bakeoff` | tests the skill itself, blind: the same agent with and without 100x on the same briefs. Reports "ahead" or "not shown". Builds no prototype |

Call a skill the way your app does: `/100x-status` in Claude Code and Cursor, `$100x-status` in Codex. Installed as the Claude plugin, Claude Code puts the plugin's name in front: `/100x-engineer:100x-status`.

## Number phrases

These phrases change a run, in `100x` and in `100x-overnight`. Nothing else in a brief does anything, not "fast", "quick", "prototype" or "mvp": those get a normal, full build.

| You write | What happens |
|---|---|
| `3 versions` | build 3 versions of the idea, finish the best. Any number |
| `for 10 hours`, `for 2 days`, `until 6am` | use all that time. Finish refuses before it is over |
| `5 rounds of judging` | that many judge rounds |
| `max 5 subagents` | at most 5 helpers at the same time. Default 1 |
One more phrase works the same way, and it removes work: `no verification` skips the property checks for the run, as `100x config set verify.enabled false --local`. They are on by default. `100x-judge` and `100x-grind` read the rounds phrase too, and in a grind it sets the rounds that come before the extra ones. `100x-mockup` ignores all of them and says in its first line what it dropped. Name the phrases you read in the pre-flight, or say there are none. That line is how the owner catches a wrong reading.

## When you are not sure

The owner is here, so ask. One short question, with your best guess offered as the answer they can confirm, and nothing built until they reply. `references/words.md` has the shape. Ask when:

- The message is not a brief: a lone word you do not know, a question, a few words that name nothing to build. A word you do not know is not the name of a prototype to make. `$100x gallery` gets the question, not a build called gallery. A lone word that is the name of a mode in the table above, without the `100x-` (`status`, `report`, `mockup` and the rest) gets the question with that skill as the guess, "Do you mean `100x-status`?" for `status`, because the mode is picked by calling the skill.
- The brief has two readings that would build different things.
- The owner's own rules forbid something this run would do. See "The owner's rules".

Do not ask about taste (build both behind a switch), about a choice that is cheap to undo, or about something the owner already said. When the owner is away, on `100x-overnight` or a fill clock, never ask: take the most reasonable reading and log it.

## The owner's rules

The owner's global and local agent rules (`CLAUDE.md`, `AGENTS.md`, `.cursor/rules`) come before this skill's defaults. Read them in step 4 of Stage 0. Follow minor differences quietly. A major one, where a rule forbids something the run needs ("never use subagents" against the judge), gets one short question when the owner is here, and the stricter reading plus a logged row when they are away. `references/rules.md` has the files, the sorting and the question.

## Stage 0. Open

Done when you have sent the pre-flight, saved it in `project.md` and logged the `start` row.

1. Read the message before anything is created.
   - A message that is not a brief gets the question from "When you are not sure". Create nothing until it is answered.
   - Number phrases (the table above) change this list. Step 6 applies them.
   - `100x-overnight` sends you through this list once per brief, with its clock and watchdog already set.
2. Fit check, before anything is created.
   - **New project.** Build it from scratch on the main branch. Work in the current folder when it is empty or holds only the brief. Otherwise create `./<slug>/`, `cd` into it and work there. The slug is the goal in at most four lowercase words joined by hyphens, like `tip-splitter`. Make it once and reuse it for the folder, the branch and the log id.
   - **Big change** to a repo with history. Work on branch `100x/<slug>`, stage only files you changed, and leave the owner's uncommitted files untouched.
   - **Small edit.** Make it, run the project's own check once, commit, reply in three lines. Stop. The pipeline is for work that deserves it.
3. `100x init` in the folder you settled on. It makes `.100x/`, keeps it out of git and prints the stack, the run command and the deploy hints it can find. An empty folder has none yet, so step 5 sets them. When it says an earlier run is already here, this brief is a new run: `100x init --fresh` moves the old run's files and stage tags aside and starts clean. If the shell cannot find `100x`, call `~/.100x/bin/100x`. If that is missing and this skill sits in a checkout of the repo, run `scripts/install.sh` from it, two folders above the real path of this skill (`readlink -f` on its folder). Installed as the Claude plugin there is no checkout: tell the owner to install the tool from the pinned release, with the version and checksum on https://github.com/DeadInternetStudios/100x-engineer-skill/blob/main/docs/install.md#install-a-pinned-release, and then to run `100x install`. Do not install it from anywhere else in its place.
4. Read `~/.100x/profile.md`, or `references/profile.default.md` when it does not exist. Read `100x config print`. Read the owner's rules and settle any major difference (`references/rules.md`).
5. Write the prompt in `.100x/project.md`: the brief word for word, then the longer prompt the owner would have written, after reading what the brief names. Run `100x prompt check` and fix what it names. Decide and log inside the prompt, never ask. Everything it holds, and how to write it, is in `references/open.md`, `references/prompt.md` and `references/prompt-example.md`.
6. Modifiers. Each number phrase becomes a `100x config set ... --local` line, a length of work becomes `100x clock set "<the owner's words>" --fill` and the watchdog, and `Mode: overnight` or `Grind: yes` is recorded when a mode skill sent you here. The exact commands are in `references/open.md`, and `3 versions` reads `references/variants.md`.
7. `100x log --start <slug>-<yyyymmdd-hhmm>`, then `100x log start "<goal>" "<why this reading>"`.
8. Send the pre-flight, at most 12 lines, and keep working: seven fixed lines (goal, asks, moment, riskiest unknown, the one thing that must not break with its properties, number phrases in effect, time), at most three assumptions, one or two "call X to change Y" lines with `100x-setup` always one, and a model line when one applies. `references/open.md` has the rules for each line. Paste the sent lines under `## Pre-flight` in `.100x/project.md`.

No brief and no run to continue. Reply with one line asking for the brief.

## Pipeline

Read a stage's reference when you enter that stage, not before.

| # | Stage | You do | Ends when | Tag |
|---|---|---|---|---|
| 1 | Core | build the riskiest slice, score it ready to ship, fine or needs work. `references/core.md` | verdict row with evidence | `100x/core` |
| 2 | Build | the first full version. `references/build.md` | it runs and the quick check is clean | `100x/build` |
| 3 | Depth | build the top predicted next asks behind seams. `references/depth.md` | each has a cut hint | `100x/depth` |
| 4 | Polish | three passes, structure then craft then moment, a judge in every pass. `references/polish.md` | each pass has before and after counts, and its judge answered | `100x/polish-1..3` |
| 5 | Must not break | `references/must-not-break.md` | the check passes, after you showed it could fail | `100x/must-not-break` |
| 6 | Review | The `100x-judge` skill, up to `review.rounds` (5): code, then UI and UX, then the ship test. A grind adds ship tests until one is green | `100x triage` says all rounds are done, or a grind says Green light, Stalled or Round limit | `100x/review` |
| 7 | Ship | preview deploy only. `references/ship.md` | URL or a stated reason | `100x/ship` |
| 8 | Finish | `references/finish.md`, then `100x finish` | `100x finish` succeeds | `100x/finish` |

With a fill clock (`100x clock` says use all the time) stage 8 waits. After stage 7 do rounds from `references/fill.md` until the work time is over. `100x finish` refuses before then.

At the end of every stage, update `.100x/STATE.md` (`Stage:`, `Next:`, `Open risks:`), close the asks that stage satisfied with evidence, commit, tag, log a row. The state file is how a resumed thread knows where it stands. Config and the owner's number phrases set the numbers: `polish.passes`, `depth.max`, `core.enabled`, `variants.count`, `test.budget`, `subagents.atOnce`.

## Always

- **Git.** Commit locally and often with plain messages. Never push, force or rewrite published history.
- **Dev server.** One per stage, on a free port from `100x port`, started from the project's own command as a background job of your shell tool, because a foreground server blocks your shell and a trailing `&` job can die when the call returns. `PORT=$(100x port) npm run dev` is the usual form, or the framework's port flag. Poll until the port answers. Stop it before the review and at finish. None is running when you finish.
- **Run facts.** Write them with `100x run set <key> <value>` and `100x run push <key> <value>` as each stage earns them. Never edit `run.json` by hand. Each stage names its keys, and `references/finish.md` lists all of them.
- **Context.** Long runs fill the window. Keep `STATE.md` true, send long output to files under `.100x/`, open `contact-sheet.png` before single screenshots.
- **Deploy.** Preview when configured. Production only when the brief says so in words.
- **Money and secrets.** No paid service the project does not already have keys for. No secrets in the repo.
- **No rule, no guess.** On by default, and the planner always does it. The prompt has a `Properties` section, and before you build or change code that carries logic you run `100x verify cover <file>`. Only the owner's words `no verification`, `100x config set verify.enabled false` (`--local` or `--global`) and `100x-mockup` turn it off. A `NO RULE` answer starts the verification procedure in `references/properties.md`: extract the six properties (state, transitions, preconditions, postconditions, invariants, liveness), check them, show each one fail, record them with `100x verify add`. Code with nothing to state gets `100x verify waive` and a reason. With two or more blocks, add a system model that calls their real functions and record it as one more row. The ledger is `verify/ledger.tsv`, kept in git with the code, and `100x finish` refuses a property that is stale, broken or never failed.
- **Claims.** Mark each as measured, inferred or guess in the evidence column of the log. The report states measured things as facts.
- **A judge in every loop.** Every polish pass and every fill round ends by asking a fresh judge, a different model, the brutal question. Write `.100x/loops/<name>/ask.md`, start it with `100x review-call --loop <name>`, answer every finding in `answers.md` before the next loop. One model grading its own loop loses direction. `100x finish` refuses a loop with no judge. `100x-solo` has no other model, so there each loop ends with a written challenge by this model (`100x ref solo`), and `100x finish` checks its file.
- **In Cursor every helper starts through the SDK, at a 300k window and never in MAX mode.** A judge, a bake-off arm and a child start with `100x helper run` (or `100x review-run`), always with `--context 300k`. Never the Task tool, never `cursor-agent`. `references/apps.md` says why and how.
- **The judge always runs.** In `100x-solo` no judge starts, and stage 6 is a round challenge by this model. Everywhere else stage 6 starts it with `100x review-call`, by your app's subagent tool or by a command. No setting about helpers or counts limits it. Outside `100x-mockup`, only `review.enabled false` turns it off. Never finish UNREVIEWED because you expect to be limited. Try to start it. UNREVIEWED is for a start that failed, with the failure in the note, and `100x finish` refuses it when no attempt is logged.
- **Children.** At most `subagents.atOnce` helpers run at the same time, 1 by default, the owner's `max N subagents` phrase aside. The cap is about the same time, never a total: judges run one at a time, so the cap never blocks a judge. The cap counts children only, not judges and not this thread, so where a session limit applies set `subagents.atOnce` and `helper.ceiling` low enough to leave room for them: neither counts live sessions, they limit how many children a night or a run asks for. Apart from judges, a child starts only from `100x-overnight` or for parallel versions, and only up to the cap; the rest queue. Start one with your app's subagent tool (in Cursor `100x helper run`) and pass the `target` that `100x config target overnight` prints. An empty target means the child uses this thread's model, except where `helper.only` is set: then `100x config target overnight` and `100x night next` print the locked selection, never an empty target. An app with no subagent tool runs without them.
- **Failure.** Say what failed in the log row, continue from the best truthful state. Three failed attempts at one thing means simplify it and move on. A needs-work verdict is a legitimate result.
- **Companion skills.** `unslop-text` (copy) ships with 100x, and the install links it. Run it as `100x text ...`, never as `node <skill folder>/scripts/unslop.mjs`: the command runs the pinned copy. Read the skill's own file once before first use, and where it says `node <skill folder>/scripts/unslop.mjs` or `unslop`, run `100x text` with the same arguments. `boneworks` makes game assets when it is installed.

## Where things are

The other modes are the skills in the table above, next to this one. Helpers: `references/must-not-break.md` (stage 5, with `references/kinds.md` for each kind in detail and `references/shots.md` for the screen runs), `references/properties.md` (the verification procedure and the ledger, for stage 5 and for any code no rule covers), `references/watchdog.md` (unattended runs and fill clocks), `references/plans.md` (Claude plan setups), `references/unattended.md` (deciding without the owner), `references/apps.md` (how each agent app differs), `references/open.md` (steps 5, 6 and 8 of Stage 0 in full), `references/looks.md` (the named looks the core and the variants pick from) and `references/mobile-web.md` (read before the first screen when the target is a phone, a touch screen or a game). `references/solo.md` (how `100x-solo` judges its own work, with no second model). The judge of stage 6 is the `100x-judge` skill. The other skills of the suite read these guides with `100x ref <name>`, such as `100x ref apps`, so a skill installed on its own still finds them.

`references/decisions.md` for how to write rows. `references/principles.md` for the working principles behind the stance. `100x help` lists every command and `100x help <command>` lists its flags.

## Reply

The output of `100x finish` is the final message, with the review state and the next likely asks. Point to `100x-report` for the gallery. End there.
