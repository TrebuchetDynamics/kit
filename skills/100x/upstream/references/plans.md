# Plan standards for Claude

The plans are Pro, Max (formerly called 5x) and Ultra (formerly called 20x). An owner who still says "Max 5x" or "Max 20x" means Max and Ultra.

An owner on a Claude plan can pick a standard instead of describing every job. This is for `100x-setup`. Nothing here detects the plan: the owner says which one, and a plan the owner does not name gets no standard. These are suggestions to confirm, not limits 100x enforces. Which models a plan includes and how much it allows are the owner's to check, so when a model on the list is not in the app's own list, take the nearest one below it and say so in a line.

Never use Fable at max effort, on any plan, as builder, judge or anything else. Fable's top setting is high. The owner has said so, and it holds over the "max when the model offers it" default of setup.

| | Pro | Max | Ultra |
|---|---|---|---|
| Usage preset | `lite` | `medium` | `standard` |
| Polish passes, judge rounds, features ahead | 1, 2, 2 | 2, 3, 3 | 3, 5, 5 |
| Judge looks in a run | 3 | 5 | 8 |
| Builds | Sonnet, high | Opus, high | Opus, max |
| Judge | Opus, medium | Fable, high | Fable, high |
| Backup judge | none | Sonnet, high | Sonnet, high |
| Quick jobs | Haiku | Haiku | Sonnet |
| Overnight | the builder's model | the builder's model | Opus, high |
| Helpers at once (`subagents.atOnce`) | 1 | 2 | 3 |
| Parallel versions (`variants.parallel`) | false | false | true |

Use the newest version of each family the app lists. Model ids as of now: Fable `claude-fable-5-2`, Opus `claude-opus-5-5`, Sonnet `claude-sonnet-5-5`, Haiku `claude-haiku-5-5`. The app's own list wins when it differs.

## What to run

1. The preset: `100x config preset <lite|medium|standard> --global` (or `--local`).
2. The helpers: `100x config set subagents.atOnce <n> --global` and `100x config set variants.parallel <true|false> --global`. Pro and Max are the built-in defaults for parallel versions, so write them anyway: a plan chosen later must undo an earlier one.
3. The jobs: `100x config role <review|fallback|quick|overnight> --model <id> --option effort=<level> --global`, with the option id the app's list shows. For the builder, `100x config role builder` records it and Stage 0 compares it with the thread. For "none", `--clear`, and the judge is never cleared. A command judge follows step 6 of `100x-setup`.

Deploys are not part of a plan standard. Putting something online is the owner's call, so `deploy.preview` and `deploy.prod` stay as they are.

## Notes the owner should hear, in one line each

- Pro. A judge on Opus uses a lot of the allowance. When a window runs out mid-run, call `100x-continue` after the reset.
- Every row. The judge is another model than the builder, from the same vendor. A judge from another vendor is stronger and needs `review.command`, which has not been proven (see the README).
- Every row. Nobody has measured the tokens of any of these. They are starting points.

## OpenAI plans

For an owner on ChatGPT with Codex. Run it the same way as the Claude standards above: the preset, the helper settings, then the five jobs, from "What to run". The owner says the plan, and nothing detects it. A plan the owner does not name gets no standard.

Models are named by family: Astra, Sol and Luna. Use the newest version of each that the app lists, which is GPT-6.2 for Astra and Sol at the moment (`gpt-6.2-astra`, `gpt-6.2-sol`, out November 17, 2026). Never write an older version into a role while a newer one is listed. Luna has no 6.2 yet, so it takes its latest. Go may not list the newest models: use the newest it shows and say so in a line.

This came from third-party pages and a few OpenAI help pages. They disagree in places, and nobody has run these standards. The plan names and prices change, and OpenAI has said the ChatGPT and Codex limits will be shared from December.

| | Go or Plus | Pro 100 | Pro 200 or 500 |
|---|---|---|---|
| Usage preset | `lite` | `medium` | `standard` |
| Polish passes, judge rounds, features ahead | 1, 2, 2 | 2, 3, 3 | 3, 5, 5 |
| Judge looks in a run | 3 | 5 | 8 |
| Builds | Sol, medium | Sol, high | Sol, high |
| Judge, a different model | Astra, medium | Astra, high | Astra, high |
| Backup judge | none | none | none |
| Quick jobs | Luna | Luna | Luna |
| Overnight | the builder's model | the builder's model | Sol, medium |
| Helpers at once (`subagents.atOnce`) | 1 | 2 | 3 |
| Parallel versions (`variants.parallel`) | false | false | true |

- Astra is the stronger model for harder work, and it has the smaller allowance, so it judges and does not build. A run only needs a few judge looks. Sol is cheaper for routine coding, so it builds. Luna does the quick jobs because its allowance is the largest.
- There is no backup judge. The only other models are Sol, which is the builder, and Luna, which is too weak to judge. A backup from the builder's own family is a self-review. Add one from another vendor, such as Claude, when the owner has it.
- No standard asks for a model's top effort. The owner can say so in words when they want more.
- One source says the system card measured GPT-6.2 Astra hiding a known coding obstacle about twice as often as GPT-6 Astra (22.28% against 11.09% of trials), and that Codex instructions cut it a lot. The judge's ask already tells it to report everything it saw, so the standard stays. Tell the owner if a judge's report looks too clean.
- Ultrafast is Pro 200 with Sol and Pro 500 with either model. The standard leaves it out, because it is for speed and not for quality.
- Deploys stay as they are, as for Claude.
