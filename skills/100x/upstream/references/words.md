# Plain words

The owner reads what you write. A setting name, a setting value or an internal stage name is not English, so never put one in a message to them. Say the phrase from this table. Keys and values stay in commands and files, and this table is how you translate in both directions: say the phrase out, and map the owner's own words back to the value.

## Jobs

| Internal | Say |
|---|---|
| builder | the model that builds, the one you are chatting with in this chat |
| thread | this chat. Never say "thread" to the owner. A job with no model of its own says "the model in this chat, <name>", for example "Overnight: the model in this chat, Sonnet" |
| review, reviewer | the judge, the model that checks the finished work |
| fallback reviewer | the backup judge, who steps in when the judge cannot start |
| quick | quick jobs, a fast demo of an idea or a deadline wrap up |
| overnight | working through the night, one child per idea |
| UNREVIEWED | no judge looked at it |
| fill clock | working for the whole time you asked for, not stopping early |
| judge round | the judge looks, you fix, a fresh judge looks again. The first look is the code, then the UI and UX, the last asks if it is ready to ship |
| grind | the judge looks, you fix, and a fresh judge looks again, for as long as it takes until one says it is ready to ship |
| adhd | a short back and forth, a few lines and one question at a time |
| solo | the whole run done by the model in this chat alone, with no helpers and no second model. It checks its own work in writing at every step, and says nobody else looked |
| challenge | the model in this chat attacks its own work from another chair, writes down what could be wrong, tests each one, and fixes what broke |
| loop judge | in every round of work a different model looks, is brutal, and says if the work is drifting into a bad idea. The builder has to answer it before going on |
| round | one pass of testing or polish with one question, such as "what breaks with an empty list?" |

## Effort

| Value | Say |
|---|---|
| minimal | minimal |
| low | low |
| medium | medium |
| high | high |
| xhigh | extra high |
| max | max |

Say "max effort" or "high effort". Never say `reasoning_effort` or `effort=max`.

## Settings

| Key and value | Say |
|---|---|
| `test.budget` `quick-only` | only check that it starts |
| `test.budget` `after-polish` | one careful test of the one thing that must not break, after the polish |
| `test.budget` `full` | test everything |
| `polish.passes` N | N rounds of polish on the look and feel |
| preset lite | the small-plan setup: 1 round of polish, 2 rounds of judging, 2 features built ahead. About 3 judge looks a run and not 8 |
| preset medium | the middle setup: 2 rounds of polish, 3 rounds of judging, 3 features built ahead. About 5 judge looks a run and not 8 |
| plan Pro, Max, Ultra | the standard setup for that Claude plan, from `references/plans.md` |
| preset standard | the usual setup: 3 rounds of polish, 5 rounds of judging, 5 features built ahead |
| `polish.dudPasses` N | N extra rounds when the first try felt flat |
| `depth.predictedFollowups` with `depth.max` N | builds the N features you will probably ask for next, each easy to remove |
| `variants.parallel` false | versions of one idea are built one after another |
| `variants.parallel` true | several versions of one idea built at once by separate helpers |
| `subagents.atOnce` N | at most N helpers at the same time. Judges run one at a time, so this never blocks a judge |
| `deploy.preview` `auto` | puts a preview online by itself when the project already has hosting |
| `deploy.preview` `ask` | asks before putting a preview online |
| `deploy.preview` `off` | never puts a preview online |
| `deploy.prod` `on-say-so` | goes live only when you say so in words |
| `deploy.prod` `never` | never goes live |
| `watchdog.mode` `schedule` | a timer that nudges a stalled overnight build every N minutes |
| `watchdog.mode` `off` | no nudges |
| `review.enabled` false | no judge, every project says so |
| `verify.enabled` false | no property checks, every project says nothing was verified |
| `review.grind` true | judging goes on after the usual rounds until a judge says it is ready to ship |
| `review.timeoutMinutes` N | the judge gets N minutes |

## Stages

| Internal | Say |
|---|---|
| Open | getting started |
| Core | a quick first try of the riskiest part |
| Build | building the first full version |
| Depth | building the extras you will probably ask for next |
| Polish | rounds of polish on the look and feel |
| Must not break | testing the one thing that must not break |
| Review | the judge's rounds |
| Ship | putting a preview online |
| Finish | writing the report |

## Internal terms

| Internal | Say |
|---|---|
| must not break | the one thing that must not break |
| core | a quick first try of the riskiest part |
| polish pass | a round of polish |
| matrix | the screen size check |
| triage | going through the judge's findings one by one |
| depth | the extra features you will probably ask for next |
| registry, gallery | the report page |
| decisions.tsv | the decisions file |
| moment | the moment that makes someone want it |

## What the owner says

The owner calls skills and runs no commands. Never tell them to run `100x <command>`: those are yours. Tell them the skill to call, the way their app calls it (`/100x-report` in Claude Code and Cursor, `$100x-report` in Codex, `/100x-engineer:100x-report` when Claude Code has it from the plugin).

| To | Tell them to call |
|---|---|
| see what finished, ranked | `100x-report`. For older runs, "all" after it |
| pick a run back up | `100x-continue` |
| see where a run stands | `100x-status` |
| talk it through in short turns, one question at a time | `100x-adhd` |
| find out whether 100x makes better prototypes than the same agent without it | `100x-bakeoff` |
| have the judge look again | `100x-judge` |
| keep judging and fixing until a judge says it is ready to ship | `100x-grind` |
| choose which models do which job | `100x-setup` |
| see an idea fast, with no judge | `100x-mockup` |
| make a project work by a deadline | `100x-wrapup` |
| leave and have it work while away | `100x-overnight` |

## Asking back

When the owner is here and you cannot tell what they want, ask once and wait. Three lines at most:

- What you read, in their words. "I do not know the word `gallery`."
- Your best guess, as something they can act on at once. "Do you want the report of what finished? Call `100x-report`."
- The other reading, and what picks it. "Or describe the prototype, and I build it."

Ask one question, never a list of settings. Never ask at night or on a fill clock: the owner is away, so take the most reasonable reading and log it.
