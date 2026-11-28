# The prompt

The brief is a few lines, and a build from a few lines drifts. So before you build anything, write the longer prompt the owner would have written with an hour to spare, and build from that. It lives in `.100x/project.md`, one section for each part. Take about 15 minutes, plus the time it takes to open what the brief names.

This starts after the question from "When you are not sure" has been answered. A brief with two readings that build different things gets that one question first. Inside the prompt you never ask: decide, write the choice under `## Assumptions`, and say the top ones in the pre-flight.

Done when `100x prompt check` is clean, and someone holding only `project.md` could build the right thing. The check counts what is there. It cannot tell a good prompt from a thin one, so reread yours as a stranger would.

`prompt-example.md` has two finished ones, a short game and a tool that runs on real files. Read it once, then write yours in the same plain way.

## 1. Read before you write

One line per source under `## Read first`: the exact file or page, and what you took from it. A source you opened and took nothing from gets no line. A line claims only what you opened. Open sources in the order below and stop when the time is up. List what is left as `(not read)` with what the core should look for in it, never what it holds, because you have not seen that.

- What the brief names. Every path, repo, address, file and product in it.
- What is already here. The README, any `AGENTS.md` or `CONTEXT.md`, `git log -5`, the tests.
- What the owner built that is alike. `100x registry list --all` lists their finished runs. Read the `project.md` and report of one or two. Change nothing there, and take no secret.
- `~/.100x/profile.md`. A repeat correction in it becomes a rule or a Do not line when it applies here.
- The primary source for every API, format or rule the build rests on: the official docs or the spec, never a blog post about them. List it now and open it in the core stage.
- Tools that already do part of the job. Credit an idea you take, and copy no text.

Write `none: <reason>` when there is nothing to read, such as an empty folder and an idea that names nothing. The reason is a few words. `none: n/a` fails the check.

## 2. Write the sections

- **Brief.** The owner's words, word for word. Lines in it that start with `## ` go in a fenced block, so they are not read as sections. Whatever steers the build is said again in Rules, Scope or Do not, because the export and the loop judges do not carry the Brief.
- **Goal.** One sentence that starts with a verb, then what it is and what it is not. For each word that could mean two things, give two instances that count and two that do not.
- **Rules.** Three to six rules that settle a trade-off, written "X, not Y", each with where it stops. A rule nobody could break is not a rule. A rule or limit the brief gives stays as strict as the brief states it: tighten it, never loosen it. If the build needs an exception, keep the rule and write the exception under Assumptions with the reason.
- **Riskiest unknown.** One sentence, then the two or three questions the first try answers, and what changes when an answer is no. Stage 1 builds exactly this slice.
- **Asks.** The owner's own asks first, each rewritten as a spec, while their words stay in Brief. When the brief numbers its asks, keep its numbers and number yours after the last, because the brief refers to them. A feature you think they would want is a `(stretch)` ask or an assumption, never a plain ask. Each ask names what you can run or open to close it, with the count, format or limit that decides pass or fail: a command and its exit code, a file and line, a time, a sample size. An ask with no visible end is not an ask. Then proof asks (section 3), then packaging: a README and one command to run it, then stretch asks.
- **Scope.** What is in and out, the platforms and sizes, the file formats, whether ignored and generated files count, size and time caps that keep odd input from hanging it, the runtime and dependency rule, where each part lives so the folder can be copied whole, and what it says plainly it cannot do.
- **Test material.** The exact inputs: paths, sizes, counts. Say which you may only read, which you copy before you change them, what is made anonymous in anything that ships, and where raw output stays. Write into no other project.
- **Do not.** The hazards of this problem, and what the work may not run, install or write: the audited project's own commands, git state, anything outside this folder. The standing rules are in the skill already, so leave them out.
- **Assumptions.** One line per thing you decided instead of asking.
- **Properties.** The verifiable properties of the part that has logic, one line each, in the repo's own names: state (what can exist), transitions (how it changes), preconditions (when a step is allowed), postconditions (what is true after), invariants (what always holds) and liveness (what must eventually happen, and the assumption it needs). `references/properties.md` says how to find them and what checks them. Write `none: <reason>` for a project with nothing to state, such as a page of copy, and then waive its code with `100x verify waive`. The section is not asked for when the owner turned property checks off with `verify.enabled false`.
- **Must not break, Moment, Judge focus.** As stage 0 says. The judge focus is two to six questions a judge can answer by running the thing, such as "does the total match a hand count?"

The check wants every section written and not left as the template's hint, at least three rule lines, three asks that count (a dropped one does not), two judge focus lines and a question mark in the riskiest unknown. Lines in a code fence are a quotation and subheadings are titles, so neither counts toward those numbers. Stack and run, Modifiers and Pre-flight are not part of the prompt, so it does not ask for them. Stage 0 records them beside it. Properties needs three lines, one per property it states. Only Read first, Test material, Do not, Properties and Assumptions may say `none: <reason>`, and are then left out of the exported text. The other sections cannot, because every build has them.

## 3. Proof asks

What the builder says about its own work is not evidence. For each claim the stages cannot see, add an ask whose result someone else can check.

| Shape | The ask reads |
|---|---|
| Planted case | put a known flaw in a copy, and show the tool finds that one |
| Control | feed it clean input, and show it says nothing |
| Real input | run it on the owner's real material, and report what it found |
| Honest limit | say what it cannot do, in its own output or README |
| A/B | compare two versions or two tools blind, with a trap in each |

Stack the shapes a claim needs. A claim of measurement usually needs a planted case, a clean control and real input together. Where they fit, state the sample size, who or what judges, the number that counts as a pass, and one benign case that must produce nothing. Run the deciding case on clean input first, where it must pass, then with the flaw planted, where it must fail. A check that fails on clean input proves nothing, and one that never fails proves nothing either. Judge an A/B blind, by a different model, with the key kept apart. Name the worst failure, such as a false pass, and test that one directly. Money, scores, units and clocks get a planted case with the answer worked out by hand. It is the same idea as "show the check can fail" in `references/must-not-break.md`.

## 4. Check it, then build

1. Run `100x prompt check` and fix what it names.
2. Read the Goal and the Asks as a stranger would. Does each ask end in something you can look at? Do the numbers and names agree from one section to the next?
3. Go on. The prompt now steers the rest. Stage 1 tests the riskiest unknown. The review judge's brief and each loop judge's ask carry the Rules, Scope and Do not (`references/polish.md` and `references/fill.md` say where). `100x finish` refuses while a section is unwritten or an ask is open.

A mockup skips this, and so does a run that began before the prompt step: it has no `.100x/prompt-step` file.

## Using it in another chat

`100x prompt` prints the prompt as one text, and refuses while the check has anything to say. Paste it after the skill name in another chat to run it there. `--where <dir>` names that chat's folder, and `--with-brief` adds the owner's words. It lists on stderr, with the line, any word in the text that would turn on a mode there, such as "overnight" or "3 versions".

## Keep it short

As long as the build needs and no longer. A line stays when it changes what is built or checked. A section with nothing to say gets `none: <reason>` where that is allowed, never filler.
