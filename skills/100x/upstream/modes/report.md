---
name: 100x-report
description: "Use for /100x-report, or when the owner comes back and asks what 100x finished: 'what got built', 'show me the report', 'morning report'. Ranks the finished runs, says what each is and why the judge held any back, lists the runs still being built, and opens the gallery page. Nothing builds."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Report

What finished, ranked, what is still being built, and a gallery. Nothing builds.

The owner comes back to several prototypes and decides in minutes which deserve more time. Your job is a ranking they can trust, a plain line on what each run is, the reasons the judge held a run back, where each unfinished run stands, and a page they can click.

Done when the reply has the ranking, what each run is, the reasons for every run the judge held back, every run still in progress, and the page path or URL, and every claim in the reply matches a registry entry.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## Steps

1. Run `100x morning`. It prints the ranking, best verdict first, and writes `~/.100x/morning/index.html`. The command is yours: the owner calls this skill, and you never tell them to run it.
   - The window is `morning.windowHours` (18 by default). "since 2d" after the call is `--since 2d`, and "all" is `--all`.
   - An empty ranking is a result. Say so, then run `100x registry list --all` to look for older runs before concluding nothing finished.
   - A run the page left out because its record is damaged is named in the command's warnings, with the command that drops it. Repeat that warning.
   - Words after the call that are not `all` or a window are a request you do not know. Ask what they want to see, as "When you are not sure" in the `100x` skill says.
2. For clicking, run `100x morning --serve --detach --open`. The page serves from 127.0.0.1 with a random token in the URL. Run starts a prototype's dev server, waits for its port and opens it. Stop ends it. `100x morning --stop` ends the server and every prototype it started.
3. Reply from the ranking, in its words and its order. Draw no table, no second page and no summary of your own over it.
   - One line with the counts. For example "4 finished. 2 ready to ship, 1 fine, 1 needing work."
   - For each run, the ranking's lines: rank, title, what it is, then the moment. A run marked `look` keeps its `look` line and its `why` lines.
   - For the top run, the try-first steps and the run command.
   - Every run no judge looked at, named, with its reason. Every run that needs work, with the single change most likely to fix it. Every failing must-not-break check.
   - After the ranking, the `In progress.` block lists each run that began and has not finished: title, working or idle, its stage, the asks closed, the judge's rounds, and the line that picks it up. Repeat it as written. A run marked idle may have stopped. Say so, and offer `100x-continue` from its folder, or its `100x registry remove` line to drop it from the report. "N older runs never finished" is a count of runs outside the window, and `--all` lists them. A report with no finished run and a run in progress is not empty, so do not say nothing happened.
   - Close with the page path or URL, and the one line that continues the top run: say its folder, and that the owner calls `100x-continue` from there.

## Reading the entries

`look` stands where the verdict would. The builder called the run ready to ship or fine, and something would stop a stranger: a judge who said not ready to ship, no judge, a failed check or a broken screen size. The `look` line says what the builder said and which thing it is. Repeat both, and never turn `look` into a verdict of your own.

Not ready to ship is the usual word after one night, so it is not a failure. The `why` lines say what is behind it. They are the judge's own blockers and majors from its last round, what still stands first. Each ends with what became of it: left for later, fixed but not checked again, or the builder disagreed. Repeat them as written. A `why` line that says the judge left no big finding on record means the judge named nothing big, or its files are gone. Say that, and never make up reasons.

The verdict and its reason come from the run's own core and polish evidence, so repeat them as written. If the reason is thin, say that and recommend the owner look at the hero screenshot and the contact sheet before trusting it.

`REPORT.html` in each project's `.100x` folder is the full trail as a page, including the last decisions and the features with their cut hints. `REPORT.md` has the same in plain text. Open one when the owner asks why. Both start with a `Look first.` line, in red on the page, when something would stop a stranger: a failed check, a broken screen size, no judge, or a judge who said not ready to ship. A judge's no is followed by `Why not ready to ship.` and the same reasons. Repeat both in your reply.

## Housekeeping

- `100x registry remove <id>` drops a run from the gallery. The project folder stays untouched.
- The cards are runs that passed `100x finish`, which refuses to close a run with open asks, a missing review reason or an untriaged finding. A run joins the `In progress` block at its first logged decision and leaves it when it finishes.
- `100x status` inside a project shows one unfinished run in more detail.
