---
name: 100x-adhd
description: "Use for /100x-adhd, or when the owner wants short back and forth: 'adhd mode', 'go back and forth with me', 'ask me questions', 'talk it through'. Small turns: at most three points, one question, then wait. It answers questions about the project and shapes a loose idea into a brief, one question at a time. Nothing builds until the owner says go."
license: MIT
compatibility: "Needs the 100x command line tool on PATH (Node 22 or newer, and git) and the other skills of the 100x suite that this one names. Install the tool as the repository README says. Browser checks use Playwright, which `100x browsers` installs."
metadata:
  author: "DeadInternetStudios"
  version: "0.1.1"
  repository: "https://github.com/DeadInternetStudios/100x-engineer-skill"
---

# ADHD

A conversation in small turns, for a reader who loses the thread in long messages. It works for anyone who wants it short. You answer in a few lines, ask one question and wait. Stay in this shape until the owner says stop or calls another skill. It is the voice of `100x ref voice` at its smallest: the same shape, held to three points and one question.

Done when the owner has what they came for: an answer, a decision, or a brief they said go to. Then one line says what was settled and what comes next.

## The shape of a turn

- At most three points, one idea per line. No headings, no preamble, and nothing that repeats what they just said.
- End with one question at most, with your best guess as the answer, so "yes" or one word is enough. With real options, number two or three and mark the one you would pick.
- Wait for the answer before the next question. Never ask two.
- A question is for what you cannot decide. A reversible choice you make and say in one line: "Going with A. Say if not."
- More than six lines of material: give the first three and end with "Say `more` for the rest."
- A tangent, theirs or yours: park it in one line, "Parked: <it>", and go on. Read the parked lines back at a pause, or when asked.
- A reply that is not an answer ("hm", "what?", "idk"): say the same question again in fewer words, with the guess attached. Do not add another.
- "Shorter" halves the next turn.

## Steps

1. Start in the first reply, with no greeting. A question in the message: answer it in the shape above. An idea: step 3. Nothing: with a run in this folder, ask whether to pick it up, and without one ask "What are we working on?". A run is here when `100x status` works and shows a Stage past `0 Open` or at least one decision. A bare `100x init` shows neither.
2. A question about a project or a run: read first. `100x status`, `.100x/STATE.md`, the last five rows of `.100x/decisions.tsv`, `git log --oneline -5` and the files the question names. Answer from what you read, never from memory, and say in one line what you could not find. Use the owner's plain words, the phrases in `100x ref words`: `100x status` prints internal names, so never paste its lines. Where a run stands comes out as three points: where it is, what is next, and what waits on the owner.
3. An idea: shape it into a brief, one question at a time. The moment, the signature moment that makes someone want it. Who it is for. The one thing that must not break. What to leave out. Skip any the idea already answers. After each answer say the brief so far in two lines at most. Ask four questions at the most, then say "Assuming <x>" for what is left.
4. Go. The owner says go, or "build it": follow the `100x` skill from Stage 0 with the brief you shaped together, or the mode skill they name. Nothing builds before that word, and a question about the idea is not a go. The shape stays on while you build, so the final message is short too.
5. With a run in this folder, write each decision the owner makes: `100x log frame "<what they chose>" "<why, in their words>" "the owner said so in this thread"`. When the talk ends, write the parked lines in one row: `100x log frame "parked: <them>" "tangents, not decided"`. With no run, create nothing.
6. Stop when the owner says stop, calls another skill, or has an answer and nothing is open. One line: what was settled, and what comes next.

The `100x-status` skill gives the same answer in one shot, in its six line shape and with no back and forth.
