---
name: 100x-status
description: "Use for /100x-status, or when the owner asks where a 100x project is at: 'where are we at', 'explain where this run is'. Answers in at most six lines: stage, done, next, risks, and the one thing waiting on the owner. Nothing builds. Not for git status, build status or the status of any tool but a 100x run."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Status

The owner asks where we are at with this project. Answer short, always in this shape. Nothing builds, nothing is asked back unless one line at the end names the one decision waiting on the owner.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## Steps

1. Run `100x status`. Read `.100x/STATE.md` and the last five lines of `.100x/decisions.tsv`. `git log --oneline -5`. Its Stage, Next and Risks lines are cut short, and a State line means STATE.md is behind the log, so trust the log and the commits over the file.
2. Answer in at most six lines, one idea per line:
   - **Stage.** Which stage the run is at, in plain words. `100x ref words` has a phrase for each stage. In the judge rounds, add the round and what the last judge said from the `Rounds` line, and say so when a grind is on and how it stands.
   - **Done.** What is finished and proven, with the number or screenshot that proves it.
   - **Next.** The one next step.
   - **Risks.** Open risks from `STATE.md`, or "none".
   - **Waiting.** The one thing waiting on the owner, or "nothing".
3. No brief and no run in this folder: say so in one line and ask what they want built.
