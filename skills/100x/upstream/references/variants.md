# Variants

`3 versions` in the brief (any number), or `variants.count` in config. N different prototypes of one brief, so the owner picks by looking.

Done when each variant has finished, or ended in a stated needs-work verdict, and all are registered for the report page.

1. **Choose directions.** Pick N that differ on the biggest taste axis, never only on color. The core mechanic, the visual world, the information layout, or the tone. Write one line per direction under Assumptions in `project.md`. Three variants that differ only by palette are one variant. `references/looks.md` supplies visual worlds, so give each variant a different one.
2. **Folders.** The first lives in the project folder. The others live in sibling folders named `<project>-v2`, `<project>-v3`, each set up with `100x init`, each holding the same brief and its own direction line. Nothing is shared between them, so cutting one never touches another.
3. **Build the core of every direction first.** Run stage 1 for variant 1, then variant 2 and so on, each in its own folder with its own state file and log. A core run is cheap, and it is what the rest of the night is chosen by. Each dev server gets its own port from `100x port`.
4. **Build in order of core score, best first.** Run stages 2 to 8 through `100x finish` for the highest scoring variant, then the next. A night that runs out of time then leaves the strongest direction finished. Ties go to the direction the owner's profile suggests they would pick.
5. **Duds end early.** A variant that is still a dud after its pivots gets no depth, no must-not-break test and no review. Give it `polish.dudPasses`, then finish it with verdict dud, the core evidence, the single change most likely to fix it, the must-not-break check `skipped` with that reason and review `unreviewed` with that reason. Its core screenshots are the hero and the matrix, so the gallery still shows it honestly.
6. **Cost.** Every variant that survives its core stage runs the full pipeline. Add `polish 1` to make them cheap when the owner wants breadth over depth.
7. **Compare.** The report page ranks them together on measured results. Each summary names its direction.

## Parallel children

A solo run never uses them: its variants run one after the other, each folder its own solo run (`100x ref solo`).

With `variants.parallel` set to `true`, a variant may run as a child through your app's subagent tool (in Cursor `100x helper run`) with role `implementation` and isolation `shared`. The target is what `100x config target overnight` prints, and an empty one means the child uses the thread's model, except where `helper.only` is set, where it is the locked selection. The task names the sibling folder, the brief and the direction, and says to use the 100x skill unattended and to start no subagents. This path is opt in and has not been run end to end. Prefer the sequential order unless the owner asked for parallel.
