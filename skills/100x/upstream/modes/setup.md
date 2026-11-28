---
name: 100x-setup
description: "Use for /100x-setup, or when the owner wants to choose the models, effort or judge for 100x, or a 100x doctor check says settings are missing. Asks one question, 'which models do which job', sorts the answer into jobs and saves it."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# Setup

One question. The owner answers in their own words, as messy as they like. You sort the models into jobs with common sense and save them.

Done when `100x config validate` is clean and the reply shows the jobs as saved, in plain words.

## Voice

Shortest possible. One idea per line, no paragraphs, no preamble. Use the phrases in `100x ref words`. Never show a config key, a setting value or a model id to the owner. Show a model by the name the owner used or the app's list gives, like "Sonnet" or "Opus". Say "judge", not "reviewer". Say "this chat", never "thread". A job with no model of its own shows the model in this chat by name, like "Overnight: Sonnet, same as this chat". Say "max", "extra high" or "high" for effort. Keys and ids appear only in the commands you run. The whole voice is in `100x ref voice`.

## Steps

1. `100x config print --sources`. Find the model list for this app, as `100x ref apps` says. In Cursor it is `100x helper models`, after `100x helper setup` and `100x helper login` once. Elsewhere use the app's own list or list command, and `command -v claude codex gemini opencode` shows which other agent apps are installed and can act as the judge. With no list at all, work from what you know and ask the owner to correct the names.
2. Scope. Setup is global unless the owner says "local" or "this project". Local writes `<project>/.100x/config.json` and wins over global, key by key. For a local setup in a folder with no `.100x` yet, run `100x init` first. A global setup needs no project folder, so run no `100x init` for it.
3. Ask one question, exactly in this shape. Nothing before it, nothing after it.

   In Claude Code or the Claude desktop app, or when the owner has mentioned Claude, ask this one. You know your own app, so there is no detection. The answer is a plan, or free text.

   ```
   Which plan are you on? Pick one, or write whatever you want.

   Pro    Sonnet builds, Opus judges. Light: about 3 judge looks a run.
   Max    Opus builds, Fable judges. About 5 looks.
   Ultra  Opus builds, Fable judges. The full run, 8 looks.

   Or in your own words, for example:
   Sonnet max builds. Opus max judges. The small fast one does quick jobs.
   ```

   In Codex, or when the owner has mentioned OpenAI or ChatGPT, ask this one. The plans are in the OpenAI section of `100x ref plans`.

   ```
   Which plan are you on? Pick one, or write whatever you want.

   Go or Plus  Sol builds, Astra judges. Light: about 3 judge looks a run.
   Pro 100     Sol builds, Astra judges. About 5 looks.
   Pro 200+    Sol builds, Astra judges. The full run, 8 looks.

   Or in your own words, for example:
   Sol high builds. Astra high judges. Luna does quick jobs.
   ```

   Everywhere else, ask this one.

   ```
   Which models should do which job? Answer any way you like. Example:

   Sonnet max builds. Opus max judges.
   Codex extra high overnight, and backup judge.
   The small fast one does quick jobs.
   ```

4. Read the answer and sort it. It may name 3 vendors and 7 models at different efforts. Common sense, in this order.
   - **Builds.** The model the owner names for building. Not named: the owner's main or strongest model.
   - **Judge.** The model the owner names for judging. Not named: the strongest model from a different vendor than the builder. Never the builder's own model when another vendor exists. Where `helper.only` is set, the judge is the locked selection and nothing else can start.
   - **Backup judge.** The next model from yet another vendor, or the next strongest. "None" when nothing is left.
   - **Quick jobs.** The fastest or cheapest one the owner names, or the smallest. Not named: the builder's model.
   - **Overnight.** The one the owner names for long runs. Not named: the builder's model.
   - **An OpenAI plan.** The owner says Go, Plus, Pro 100, Pro 200 or Pro 500 instead of, or with, the models. Use the OpenAI section of `100x ref plans` the same way as for Claude, with the same rules. Name each model by family and write the newest version the app lists.
   - **A Claude plan.** The owner says Pro, Max or Ultra instead of, or with, the models. The old names count too: "Max 5x" is Max and "Max 20x" is Ultra. Read `100x ref plans` and use its standard for that plan: preset, helpers and the five jobs. Models the owner also names win over the standard, job by job. Never Fable at max, even when the default below says max: use high.
   - An effort the owner names wins. No effort named: max for building and judging when the model offers it, the nearest lower effort when it does not. Say so when you lower one.
   - Skip any model the owner has said they dislike, here or in the profile.
5. Show the sorting, at most five lines, plain words only. "ok" saves it. A correction by job ("judge: <other>") changes that one line. If the owner picks the builder's own model as judge and another vendor exists, ask once for another.

   ```
   Builds: <model>, <effort>
   Judge: <model>, <effort>
   Backup judge: <model>, <effort>
   Quick jobs: <model>, <effort>
   Overnight: <model>, <effort>
   ```
6. Write each job with `100x config role <builder|review|fallback|quick|overnight> --provider <instance> --model <id> --option <id=value> --global` (or `--local`). Repeat `--option` for each option. A model only starts under the provider that offers it, so write the pair, and use the option ids exactly as the app's list gives them: one model says `effort`, another says `reasoning_effort`. For every job but the judge, "None" or "same as this chat" is `100x config role <role> --clear`. The judge cannot be cleared, because a second model has to be another one. For "no judge" run `100x config set review.enabled false --global`, and say in one line that runs will then finish with no judge looking. Property checks are on by default. For "no property checks" run `100x config set verify.enabled false --global`, and say in one line that runs will then verify nothing. When the judge's vendor is only reachable through another app's command line, also write the judge as a command, using the template for that app in `100x ref apps`: `100x config set review.command '<template>' --global`.
7. A small plan, or a plan standard. A plan standard from step 4 also runs the preset and the helper settings its table in `100x ref plans` names, with the same scope as the jobs, and says in one line that deploys are not part of it. When the owner says they are on a small or $20 plan, are short on usage, or want a cheaper run, offer lite in one line: "Lite does 1 polish round and 2 judge rounds, about 3 judge looks a run and not 8. Say lite to turn it on." On "lite", run `100x config preset lite --global` (or `--local`), and say in one line that the models and the judge stay as they are. "Usual" runs `100x config preset standard` with the same scope. "Medium" runs `100x config preset medium`: 2 polish rounds and 3 judge rounds, about 5 judge looks a run.
8. Only when the owner says "more", list the other settings in plain words, one short line each. Rounds of polish, rounds of judging, features built ahead, how much testing, subagents at once, preview and live deploys, overnight nudges, parallel versions. No keys. Write the answers with `100x config set <key> <value> --global` (or `--local`), translating with the words table.
9. No planner question. One thread plans. If the owner asks for a planner, say in one line there is none and offer to add it.
10. `100x config validate`. Reply with the same five lines as saved, then one line: "Saved for every project.", or "Saved for this project only." after a local setup. Nothing else.

## Where the answers are used

`100x review-call` says how the judge starts and `100x review-run` starts a command judge. The backup runs when the first cannot start. A command judge runs unattended under an allow rule that names the commands it may run, so set one only when the owner asks for it, and say so in one line when you do. Quick jobs (`100x-mockup` and `100x-wrapup`) run in the thread and only compare it with the quick model, in one line. Overnight children start with the app's subagent tool (in Cursor `100x helper run`), and you pass `target` from `100x config target overnight`. An empty target means the child follows the thread, except where `helper.only` is set: then the target is the locked selection. The builder line is never sent anywhere. Stage 0 compares it with the thread and tells the owner in one line when they differ.

## Examples

- `100x config role review --provider <provider> --model <id> --option <id=value> --global` writes a whole job. The provider and the option ids are the ones the app's list shows, for example `--provider cursor --option reasoning_effort=max --option contextWindow=300k`. On Cursor always write the 300k window and never 1m, because every 1m window is MAX mode and a helper never starts in MAX mode. `100x doctor` fails a 1m window and warns on a Cursor role with none.
- `100x config role fallback --model <id> --option <id=value> --global`
- `100x config set review.command 'claude -p ...' --global` for a judge that runs as a command, from `100x ref apps`.
- `100x config role quick --model <id> --local`
- `100x config role quick --clear --local` returns quick jobs to the thread's own model.
- `100x config set subagents.atOnce 5 --local`
- `100x config unset polish.passes --local` returns that key to the global value.
