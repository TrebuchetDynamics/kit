# Properties

The way to turn software into claims that a program can check, and to keep those claims true as the code changes. Used when the one thing that must not break has logic in it, and whenever 100x is about to build or change code that no rule covers.

You cannot formally verify a whole program. You can pull verifiable properties out of almost any well-defined part of one. Find that part, state what it promises in six kinds of property, check each with the cheapest tool that can fail, and write the result in the ledger so it stays true on every branch.

## When this starts

Always, unless the owner turned it off. Property checks are on by default for every run, and the planner writes a `Properties` section into the prompt at Stage 0. The owner turns them off by saying `no verification` in the brief, with `100x config set verify.enabled false --local` for one project, or with `--global` for every project. `100x-mockup` skips them. When they are off, the final message says nothing was verified. Do not turn them off yourself.

- **No rule covers the code.** Before you build or change code that carries logic, run `100x verify cover <file>`. It prints the property or the waiver that covers each file, or `NO RULE`. `NO RULE` is not a reason to guess. It starts this procedure. `100x verify gaps` lists every changed code file with no rule.
- **Stage 0.** The one thing that must not break has logic, such as rules, workflows, money, scores, permissions, a state machine, a parser or a protocol. Name kind `properties` in [must-not-break.md](must-not-break.md).
- **A property goes stale.** `100x verify status` says `stale`: the covered code changed after the last sync. Do the upkeep pass below.

Code with nothing to state, such as layout, copy and glue, gets `100x verify waive <path> --why "<reason>"`. A waiver is a recorded decision, so the next run does not ask again.

## The procedure

1. **Find the part that is well defined.** Look for the functions of state: rules that take inputs and give outputs, steps that move an object between states, limits and permissions. If the rules sit inside screen code, pull them into functions that only use their inputs first. That is most of the work, and it is the most useful change.
2. **Write the six properties.** For the part you found, answer each question in one plain sentence per item, using the repo's own names.

| Question | What you write | Where it goes in the checker |
|---|---|---|
| State. What can exist? | The shape of the state and the values each field may take | `init` and the state object |
| Transitions. How can it change? | Each step that changes state, and the values it is tried with | `actions[]` with `params` and `apply` |
| Preconditions. When is a step allowed? | The condition under which each step may run | `action.pre`. The checker runs the real code on every allowed and every refused case |
| Postconditions. What is true after a step? | What the step guarantees about the result, and what it leaves alone | `action.post` |
| Invariants. What always holds? | Facts true in every reachable state | `invariants[]` |
| Liveness. What must eventually happen, under which assumptions? | "From any state where A holds, B is reached", and the fairness it needs | `liveness[]`, `terminal` and `assumptions` |

   Write each as something that can be false. "Money is handled correctly" is not a property. "Refunded never exceeds paid, and paid never exceeds the total" is.
3. **Pick the tool that can answer.** The ladder, cheapest first, stopping at the first that fits.
   - `assets/property-checker.mjs`. A dependency-free explicit-state checker. It runs the project's own pure functions as the transitions, visits every reachable state of a small model, and checks all six kinds of property. A pass is a proof for the model and its bounds. It needs a model small enough to enumerate: a few thousand to a few hundred thousand states.
   - Property tests (`assets/money-checks.test.mjs`). For rules over large input ranges where enumeration is out of reach. The level is `sampled`.
   - A model checker such as TLA+ with TLC, Alloy or Apalache, when events can happen in a bad order across several actors and Java and the tool are installed. Write the model from the code, name the code each step stands for, and put the command in the ledger.
   - A prover or code-level verifier (Dafny, Lean, Kani, Frama-C) for a property that must hold at every size. Use one only when the repo's developers can install and run it.
   When none fits, say so in the ledger as a `sampled` check with real inputs from the code, never a hand model of the function.
4. **Tie the model to the code.** In the checker, `apply` is the project's own function and `pre` and `post` are the spec. The `guard` lines fail when the code accepts what the spec forbids or refuses what the spec allows. This is what stops a model from describing code that does not exist. In another tool, name the file and function each step stands for.
5. **Make it fail.** For each property, seed one defect in a throwaway copy of the covered code (`mkdir -p /tmp/red && git archive HEAD | tar -x -C /tmp/red`): remove a guard, reorder a step, drop a limit. Run the check there and save the output to `verify/red/<id>.txt`. It must hold a `FAIL` line that names the defect. If the check stays green, it checks nothing: fix the check, not the defect.
6. **Record it.** `100x verify add <id> --kind <kind> --property "<sentence>" --covers <paths> --command "<cmd>" --level <level>`, then `100x verify run <id>`. One row per property. Copy the checker into the project (for example `verify/check.mjs`) so the command is cheap and the ledger lives with the code. Add `| tee .100x/must-not-break/properties.txt` to the run when this is the must-not-break check.
7. **Read findings as findings.** When the current code breaks a property, say it as the shortest list of steps in the code's own words and the harm in one sentence. Do not weaken the property, the model or the bound to get green, and do not change product code to hide it. A fix is a separate change.

## Blocks and the system

A big program is not verified in one piece. Cut it into small blocks, each with a contract: what it needs and what it guarantees. Each block gets its own properties, its own ledger row and its own failing run. With two or more blocks, also do these:

1. **Check the seams.** Where block A hands a value to block B, A's guarantee has to meet B's precondition. In the system model that is B's `pre`, and the `guard` lines fail when the real code disagrees.
2. **Write a system model.** One checker model whose steps call the real functions of several blocks, in the order the product uses them. Add the properties that only exist across blocks, such as "money in equals money out". The checker visits every state of the whole.
3. **Give the system its own row.** One more ledger row, kind by what it states, `covers` every block the model calls, so a change to any block makes it stale.
4. **State the assumptions.** What the system model leaves out, such as concurrent callers, the clock or the network, goes in its `assumptions`. Checked blocks plus checked seams are not proof of behavior the model never contained.

## What a pass means

- `exhaustive`. Every reachable state of the model was visited. The property holds for this model, these parameter values and this size. The model is a claim about the software, so a pass covers the model, plus the real functions the guard and post checks ran.
- `bounded`. The search stopped at a limit. No violation was found in what was visited. Liveness is never decided on a bounded search, and the checker says so.
- `sampled`. Random or chosen cases. A pass finds nothing in those cases and proves nothing about the rest.
- **Assumptions.** Say what the model leaves out: concurrency you did not model, the clock, the network, the values you did not try. Every liveness line holds only under the fairness you named: strong means every step that stays possible is eventually taken.
- Never write "verified" for a `sampled` or `bounded` check. Write the level.

## Keeping it true

The ledger (`verify/ledger.tsv`, tracked by git) and the log (`verify/history.tsv`, append only) travel with the branch. Each row holds a hash of the code it covers, so drift is found by the machine and not by anyone's memory.

- `100x verify status` says `holds`, `stale`, `broken`, `unproven` or `unchecked` for every row and exits 1 unless all hold. Run it in CI. `100x finish` refuses a run with a property that is not holding.
- **Stale** (covered code changed). Read every change to the covered files. For each change decide one of four things: no effect on what the model describes, the model no longer describes the code, the promise changed on purpose, or the promise may be broken. Update the model and checker from the code, never from the result. Run the check. Seed one new defect and watch the check catch it. Then `100x verify sync <id> --note "<what you read>"`, which moves the hash forward and is logged.
- **Broken** (the last run failed). Replay the counterexample against the real code, step by step. A step the code cannot take means the model is wrong: fix the model and say what was wrong. Every step possible means a bug: report it with the steps, the harm and the commit that introduced it.
- **The promise changed on purpose.** `100x verify amend <id> --evidence "<commit, test or doc>" --property "<new sentence>"`. The old wording and the evidence go to the log, and the row is unchecked until it runs again. A property is never edited in place to get green.
- **No longer applies.** `100x verify retire <id> --why "<reason>"`.
- A green run does not move the hash. Only `sync` does, and it needs a green run and a written note.
- `100x verify run` runs the `command` of each row, as `npm test` runs a script of package.json. It prints the command first. Read the ledger of a project you did not write before you run it. `status`, `cover` and `gaps` run nothing, and neither does `100x finish`.

## Report it

Say what was verified in plain words, the level of each property, the assumptions, what the check found, the one command that reruns it, and what it does not cover. Put the counts in the must-not-break summary, for example "18 checks pass, exhaustive over 13 states, 5 steps, 3 invariants, 2 liveness lines". Never write more certainty than the level.
