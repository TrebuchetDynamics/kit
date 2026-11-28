# Stage 3. Depth

Done when you have built the top predicted next asks behind seams, each with a cut hint in `run.json`, and tagged `100x/depth`.

The owner always asks for more after seeing the first version. Ask for it first. This stage turns the likely second round of requests into work already done, so the morning review starts at a fuller product. Skip when `depth.predictedFollowups` is false. `depth.max` caps how many features this stage builds.

## 1. Predict

Read the profile. List what this owner asks next for this kind of project. Rank each by how likely the ask is and how much more it costs to add later than now. The usual candidates.

- Options and variants. Themes, control schemes, layout densities, difficulty.
- Mobile resolutions and orientation, if the app is touch first.
- Art upgrades. A second pass on assets, animation, sound files.
- Number display. Compact formatting, units, large values.
- Save and load, export, share, reset.
- First run. A one screen introduction, a sample dataset, a tour the user can skip.
- Removal and simplification. A way to turn each extra off.
- Empty, loading and error states that read as designed.
- Keyboard and accessibility basics.

Write the ranked list under Assumptions in `project.md` with one line of reason each.

## 2. Build the top N

For each one.

1. Put it behind one seam. A folder or a flag, one import line, no coupling to other features.
2. Make it good enough to show. A rough feature the owner cuts is a waste, and so is a hidden one.
3. Cut test. Turn it off, start the app and run the quick screen shots. The app must still work. This proves the cut hint.
4. Record it with `100x run push features '{"name":"Prestige","cutHint":"delete src/features/prestige and its line in features.js"}'`.
5. Log a `depth` row with the prediction and why.

## 3. Options at taste forks

When a design choice could go two ways, build both behind a switch in a settings panel or a URL parameter. Make the better one the default. Put the switch and the reason in the log row and the report.

## 4. List the rest

Predicted asks that did not make the cut go in with `100x run push nextAsks "<ask>"`, in rank order, one line each. The final message names them.
