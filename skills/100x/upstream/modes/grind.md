---
name: 100x-grind
description: "Use for /100x-grind, or when the owner wants work judged and fixed until a judge says yes: 'grind it', 'keep going until it is ready to ship', 'do not stop until the judge is happy'. Keeps judge rounds going past the usual count until a fresh judge says ready to ship with no blocker or major finding. A brief builds first. It stops early only when three ship tests in a row bring nothing better, at 15 rounds, or when the clock has no room. Only for a 100x project with judge rounds, never for carrying on an ordinary code task until its tests pass."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Grind

Judge, fix, judge again, for as long as it takes. The usual review stops after `review.rounds` rounds, whatever the last judge said. A grind stops when a fresh judge says the product is ready to ship.

The green light is a ship test (the last lens, over everything) where the judge writes "Ready to ship: yes" and lists no blocker and no major finding. A judge that gave no answer has not said yes. `100x triage` decides this from the files, so nobody argues it.

Done when `100x triage` said Green light and `100x finish` accepted the run. Or the grind stopped on a stall, the round limit or the clock, the final message says which in plain words, and the run is finished that way.

Messages to the owner follow `100x ref voice`: the answer first, one idea per line, one question last, every fact kept.

## Steps

1. Read the message and `100x status`. A solo run (`run.json` says mode solo) cannot grind, because the green light has to come from a fresh judge and this model cannot be one. Say so in one line and stop.
   - A brief: this is a normal build with the grind on. Follow the `100x` skill from Stage 0. Its step 6 turns the grind on once the folder exists.
   - No brief and a run in this folder: grind it. A run still before stage 6 goes through the `100x-continue` skill first. A run that already finished is ground anyway and finished again at the end, which replaces its report and its row.
   - No brief and no run: one line asking for the brief. Create nothing.
2. For a run that exists, turn it on now. `100x config set review.grind true --local`, write `Grind: yes` under Modifiers in `.100x/project.md`, and log it with `100x log frame "grind until a judge says yes" "<why>"`. Number phrases work as in the router: `5 rounds of judging` sets the usual rounds that come before the extra ones.
3. Send the pre-flight. For a build it is the router's step 8, and its time line says there is no end time: it ends on a green light, after three ship tests in a row that bring nothing better, or at 15 rounds. For a run that exists it is at most four lines: where the run stands, how many rounds are held and what the last judge said (`100x status`), that same stop line, and one "call X to change Y" line.
4. Run the rounds. Follow the `100x-judge` skill for each one, which is `100x brief`, the judge, the answers in `triage.md`, the fixes, then `100x triage`, and never shorten a round. With the grind on, `100x triage` keeps planning another ship test after the usual rounds until one is green. Read its last line:
   - `Next, 100x brief for round N`: start the next round. After the usual rounds it begins with "Not green yet."
   - `Green light`: step 6.
   - `Stalled` or `Round limit`: step 7.
   - A run that already holds rounds gets the same words from `100x brief` when its grind is over.
5. Fix between rounds.
   - Fix every accepted finding at its cause, blockers first, and run the thing again to see it hold.
   - A finding that comes back means your fix missed the cause. Reproduce the judge's evidence before you edit, and try a different fix, never the same one again.
   - A finding you reject with evidence still counts in the numbers until the next judge drops it. Put the evidence in `triage.md` and let the judge read it.
   - Never edit `findings.md`, never ask a judge for a yes, never write your own opinion of readiness into the brief. The yes has to come from a fresh judge looking at the real product.
   - Build what a finding asks for and nothing else. A grind is not a licence to add features.
   - Keep `.100x/STATE.md` true after every round (the stage, the round, `Next:`) and send long output to files. A grind outlives a context window, and the `100x-continue` skill picks it up from that file.
6. Green. The run is marked reviewed. Do the stages that are left in the `100x` skill, ship and then `100x finish`. A run that finished before gets its facts made true again first: the fixes changed the product, so run the final screens again (`100x shots`), look at them, and update `run.json` where a number or a screenshot changed, as `100x ref finish` says. Then `100x finish` replaces its report and its row. Last, `100x config set review.grind false --local`.
7. Stalled, limit or no room on the clock. Stop and do not ask another judge. A stall is three ship tests in a row that found nothing better than the best one so far, which counts blockers and majors first and findings second. `100x review-call` says when the clock has no room, and then you run the `100x run set review` command it prints, as in the `100x-judge` skill. Finish with `100x finish`, which shows the judge's no on the report like any other run, then turn the grind off as in step 6. In the final message say what the judges keep saying, in at most three lines, what you tried, and the one decision that is the owner's.
8. No judge. A grind with no judge is a build with no judge. Follow "When the call fails" in the `100x-judge` skill, finish UNREVIEWED with the reason, and say that no judge green lit it.

## Reply

The output of `100x finish` is the final message. Put one line above it: "Green light after N rounds." or "Stopped after N rounds, <why>. <the one decision>." Point to `100x-report` for the gallery. No questions.
