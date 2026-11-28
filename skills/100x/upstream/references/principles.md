# Working principles

The stance in the main skill rests on these. Each says what it means in a 100x run and where it bites. They come from pstack (MIT), condensed and reworded for prototypes. `NOTICE.md` has the credit.

1. **Experience first.** Choose what the user feels over what is easy to build. A few polished things beat many rough ones. Core, depth, polish.
2. **Make cutting cheap.** Over-building is fine while every extra comes out with a one line change. Build, depth.
3. **Never block on a human who is away.** Take the most reasonable reading, log it, continue. A human who is here gets one short question when you cannot tell what they want: a message that is not a brief, or a brief with two readings. Open, overnight.
4. **Prove it works.** Run the real artifact and read the actual value. Compiling is not proof. The must-not-break stage, finish.
5. **Fix root causes.** Trace a symptom to the first place the system went wrong and fix it there. A guard is a fix only for a state that is legitimate. The must-not-break stage, review fixes.
6. **Explain the number.** Before reporting a measurement, find what limits it and rule out that it measured something else. Zero broken over zero elements says nothing. Shots, simulations.
7. **Sequence verifiable units.** Small steps that each end in a state you can check, each committed and tagged. Build, polish.
8. **Subtract before you add.** Remove dead code and stale screens before building on them. In polish, replace instead of flattening, and let the pass's judge say whether it did.
9. **Model the domain.** Core types first. Money is integer minor units. Make states explicit so illegal states cannot be written. Build, numbers.
10. **Exhaust the design space.** At a real fork with no precedent, build two or three versions and look. Options by default is the cheap form. Core, depth, variants.
11. **Guard the context window.** Long runs fill the window. Put bulk in files, read slices, keep the state file true. Overnight.
12. **Encode lessons in structure.** When a correction repeats, make a tool refuse it instead of writing it again. `100x finish` and `100x validate` are examples.
13. **Test behavior, not implementation.** Assert what a user can observe, so internals can change. Must not break.
14. **Guard the boundaries.** Validate at the edges, such as input, network and storage, and trust internal types. Build.
15. **Make operations idempotent.** A command run again after a crash converges to the same state. `100x init`, `100x finish` and the watchdog work this way, and build steps should too.
