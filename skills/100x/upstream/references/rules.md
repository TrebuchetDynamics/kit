# The owner's rules

The owner's agent rules come before this skill's defaults. Read them in step 4 of Stage 0, before the prompt is written. Done when every major difference has an answer under Rules in `project.md`, or, away, a logged row.



- Global: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.agents/AGENTS.md`, `~/.cursor/rules`, and the equivalent for your app.
- Local: `CLAUDE.md`, `AGENTS.md` and `.cursor/rules` in the project folder and the repo root. A local rule wins over a global one on the same point.

Your app may have loaded some of them already. Read the ones it did not, and do not re-read the ones in view.

Compare them with what this run would do by default: helpers and children (the judge, polish-pass judges, `100x-overnight` children), commits and branches, installs, network calls, deploys, run length, browser use, where files may be written, and which tools to use. Then sort each difference:

- **Minor.** Style, naming, commit message format, output length, a tool preference. Follow the rule, say nothing, and note it under Rules in `project.md`.
- **Major.** A rule that forbids something this run needs. Example: "never use subagents" against a judge that runs as a helper, or "never commit" against stage commits. Do not pick a side quietly.

A rule the owner gave in this message beats the files for this run only. It still counts as major when it contradicts them.

**Owner here.** Ask one short question before step 5, and build nothing until they answer. Name the rule, the file it came from, what the run would do, and your best guess as the answer to confirm. Example: "Your global AGENTS.md says never use subagents, and the judge runs as one. Run the judge as a separate shell command, run the whole thing solo with `100x-solo` (no helper at all, this model judges itself), or turn the review off and finish UNREVIEWED?" One question per major difference, one at a time. Write the answer under Rules in `project.md` and as a `decisions.tsv` row. Ask once per project: a later run reads the answer from `project.md`.

**Owner away** (`100x-overnight`, a fill clock). Never ask. Take the stricter reading, because a broken rule cannot be undone in the morning. Log a row with evidence `guess`, and put the conflict and what you did in the first lines of the report. Where the stricter reading would stop the run (the judge), find the nearest way that keeps the rule, such as a shell command in place of the app's subagent tool. A rule that forbids every other model leaves the solo way: `100x run set mode solo` and `100x ref solo`, and the report says so. When none exists, run `100x config set review.enabled false --local`, log the rule as the reason, finish UNREVIEWED and put the reason in `review.note`. `100x finish` refuses UNREVIEWED while a judge is still switched on and no attempt to start it is logged, and it asks for a judge on every polish pass.

Never edit the owner's rule files, and never weaken a rule to make the run easier.
