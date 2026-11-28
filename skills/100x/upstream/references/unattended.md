# Unattended rules

The owner is asleep or away. Nobody answers what you ask until morning, so the run has to finish without them.

Done when the run reaches `100x finish` without a question to the owner, or ends in a stated block that no choice could remove.

## Set up

1. Set the clock to the wake time with `100x clock set <time>`, and arm the watchdog. See the watchdog (`references/watchdog.md`). Log it. A child of a night skips the watchdog, because the thread that started it holds one for the whole night, and a second one would revive a thread that is meant to be retried. When the owner gave a length of work, add `--fill`, and `100x finish` refuses until the work time is over. Use the time with `references/fill.md`.
2. The pre-flight is a statement. Send it and keep working.
3. Keep `.100x/STATE.md` true at every boundary, so a resumed thread knows exactly where to continue.
4. Commit at least every 30 minutes of work, so a crash loses little.

## Decide without asking

- **Ambiguity.** Take the most reasonable reading and the cheapest reversible choice. Log it with evidence `guess` so the owner can see it.
- **The owner's rules.** A global or local rule that forbids something the run needs (for example "never use subagents" against the judge): take the stricter reading, find the nearest way that keeps the rule, log it with evidence `guess`, and say it in the first lines of the report. See `references/rules.md`.
- **Missing credentials or keys.** Build against a realistic fixture or a local stub and say so on the first line of the report. Use only keys that belong to this project, never keys you find elsewhere on the machine.
- **Missing assets.** Draw them or generate them. See `references/polish.md`.
- **A failing install or build.** Try the nearest alternative, another library or an older version, up to three times. Then simplify the feature and list it under `nextAsks`.
- **A stage that drags.** After about 90 minutes of wall time in one stage, ship what exists in it and move on. Run `100x clock` to know the time. Log the cut.
- **The deadline nears.** With 20 percent of the time left and the run not at finish, stop the remaining stages and run the `100x-wrapup` skill, then finish. Finish takes fewer polish passes than the setting from then on, and the report says "1 of 3". With a fill clock the same rule starts at 80 percent used, and only when the run has no working version yet.

## Safe while nobody watches

- No destructive commands outside the project folder. Never delete files you did not create.
- No system settings, no global installs. Use the project's own packages.
- Network calls go to package registries, the project's own APIs and the preview platform. No emails, posts or purchases.
- Audio stays muted. Dev servers use free ports, and you stop them at the end.

## When something blocks you

Sometimes a real requirement needs the owner, for example a paid API with no key. Build everything around it and mark the ask `- [~] ... (dropped: needs <thing>)`. Make that the first line of the final message, then finish. A stopped run helps nobody.

## Morning

End with `100x finish`. The owner's next step is the `100x-report` skill.
