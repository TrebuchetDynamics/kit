---
name: 100x
description: "Build a prototype with checks and review in one session."
license: MIT
disable-model-invocation: true
---

# 100x

Apply the [shared Ponytail method](../shared/PONYTAIL.md) and
[communication rules](../shared/COMMUNICATION.md). Read the owner's
`AGENTS.md` and `CLAUDE.md` rules first. Run only on explicit invocation;
Kit's limits below override the pinned upstream text.

## Run

1. **Reject unattended work.** If the request asks to fill a clock (`for 10 hours`,
   `until 6am`), use a watchdog, or continue after the session, or selects an
   excluded mode (`overnight`, `continue`, `bakeoff`, including the old `100x-`
   spellings), reply with one line and stop: “Kit does not run unattended 100x
   work; use Orbi (`/plan-for-me`) for queued delivery.” A short cutoff for a
   mockup or wrapup is a limit, not time to fill.
2. **Preflight without writes.** Run `command -v 100x`, then, only if found,
   `100x --version`. Expect `0.1.1` (the first field; checkout builds also print a
   commit). If absent, say “100x CLI not found on PATH; Kit requires 0.1.1.” If the
   version differs or the check fails, report the version or error. In either case,
   point to [Install a pinned release](https://github.com/DeadInternetStudios/100x-engineer-skill/blob/8b43a726e3114882061f4b0b5dc1887bb96cefa3/docs/install.md#install-a-pinned-release)
   for the owner to repair, and stop before Stage 0 creates anything. Skip all
   upstream installer and PATH fallback instructions. If browsers or a helper
   are missing later, report the prerequisite; do not provision it automatically.
3. **Select by the first argument only.** With no mode selector, the whole brief
   is the default build (`/100x a status page` builds it). With an exact first
   word below, pass the remaining text to that mode. Read only the selected mode
   file, if any, then the [upstream protocol](upstream/PROTOCOL.md). Follow that
   mode's steps, not a second default build. Resolve `references/`, `assets/`, and
   `100x ref` pointers to the corresponding vendored material in `upstream/`.

   | Start of argument | Mode |
   | --- | --- |
   | `mockup` | [Mockup](upstream/modes/mockup.md) |
   | `wrapup` | [Wrapup](upstream/modes/wrapup.md) |
   | `judge` | [Judge](upstream/modes/judge.md) |
   | `grind` | [Grind](upstream/modes/grind.md) |
   | `solo` | [Solo](upstream/modes/solo.md) |
   | `status` | [Status](upstream/modes/status.md) |
   | `report` | [Report](upstream/modes/report.md) |
   | `setup` | [Setup](upstream/modes/setup.md) |
   | `adhd` | [ADHD](upstream/modes/adhd.md) |

4. **Apply Kit limits through finish.** Read a stage's references only when entering
   it. Treat upstream mode names as internal references, not host commands; load
   the linked judge procedure when the pipeline reaches review. Do not follow
   excluded handoffs, arm a watchdog or schedule night/morning work. If a grind
   needs the excluded continue mode, report the unfinished stage and stop.
   Report uses the static gallery only, without starting a server or pruning the
   registry. Setup proposes model choices without saving them. Leave user config,
   permissions and credentials alone; use only project-local run settings and
   ordinary CLI evidence outputs. Never push.
5. **Close from evidence.** For a full build, save the prompt, build the riskiest
   slice first, build and polish, show the must-not-break check fail before it
   passes, and seek a second model using tools already available. Start each
   reviewer in a fresh context with the brief, review scope and evidence target;
   keep it read-only except for its scoped findings. Keep all work in this session
   and follow the [Definition of Done](../shared/DEFINITION-OF-DONE.md) within scope.
   When the mode calls for `100x finish`, use its output as the receipt; if it
   refuses, report the missing evidence rather than inventing a report.

## Common Rationalizations

| Excuse | Rule |
| --- | --- |
| “The upstream guide can install the missing tool.” | Stop at preflight and give the owner the pinned instructions. |
| “A self-review counts as a second model.” | Name who actually reviewed, or report the failed attempt. |

## Red Flags

- Project files changed before preflight passed.
- A timer, watchdog or helper would outlive this session.
- A finish claim has no saved evidence or successful CLI receipt.

## Boundaries

- Use `/plan-with-me` for interactive planning or `/plan-for-me` to plan and queue
  GitHub delivery through Orbi. Use `/grill-me` to challenge a plan.
- Use `/unslop` for Kit's audit. The upstream `unslop-text` companion runs only
  through `100x text` within this workflow.
- Use `/ponytail-review` to review an existing change and `/lgtm` to continue an
  already approved action, not to start a new prototype.

**Done when:** the selected mode returns its evidence-backed result (the successful
`100x finish` receipt for a build), or the specific blocker and next action are stated.
