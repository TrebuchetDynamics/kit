# Visual worlds

A menu of thirteen specific looks. The owner's most repeated correction is that a prototype looks generic and vibe coded. A named world gives every project a point of view before the first screen exists, and it keeps overnight variants from collapsing into one design with three palettes.

## How to use it

1. Pick a world in the core stage by what the product is and the feeling it should leave, not by taste in the moment. Write its name and the tokens under Moment in `project.md`.
2. Variants take different worlds. Give variant 2 the world farthest in mood from variant 1, such as dark against light or serious against playful.
3. Derive tints and shades from the palette. A new hue is allowed only for status colors.
4. One accent color per screen. Use it for the primary action and the signature moment.
5. Break one rule of the world on purpose, so the result looks like this product and not like the menu.
6. Fonts. The system stacks below load without a network. For a bolder voice, bundle an open font from `@fontsource/<name>` and keep the system stack as the fallback.

Each palette meets these contrast limits, and `test/looks.test.mjs` enforces them. Ink on the background is at least 10 to 1. Mute text is at least 4.5 to 1 on the background and the panel. The accent is at least 3 to 1 on both, which is enough for fills, icons and large text. For small accent text, darken the accent until its contrast ratio on the background is 4.5 to 1.

## 1. Instrument panel

- **Feel.** precise, calm, a little dangerous.
- **Palette.** bg `#0B1220`, panel `#142238`, ink `#E8EEF8`, mute `#8FA3BF`, accent `#D4A72C`, signal `#4ADE80`.
- **Type.** Display in `ui-monospace, "SF Mono", Menlo, Consolas, monospace`, uppercase, tracked 0.08em. Body in `system-ui`.
- **Shape.** Inset bezels, 1px hairlines, tick marks, rivets, 6px radius.
- **Motion.** Dials sweep with a slight overshoot in 250 ms. Values count up.
- **Signature.** The main number winds up like a gauge on load.
- **Best for.** Dashboards, tools, idle and management games.
- **Beware.** Neon glow and glassy cards.

## 2. Field notebook

- **Feel.** personal, unhurried, handmade.
- **Palette.** bg `#F4EDE0`, panel `#FBF7EE`, ink `#1F2A44`, mute `#5F6370`, accent `#B3261E`, mark `#F2C94C`.
- **Type.** `"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif` for display and body. Numbers in `ui-monospace`.
- **Shape.** Ruled lines, taped corners, a tilt of at most 1.5 degrees, only a paper lift shadow.
- **Motion.** Ink draws in over 300 ms. Done items get a pen strike.
- **Signature.** Checking an item strikes it through with a pen stroke.
- **Best for.** Trackers, planners, writing and learning tools.
- **Beware.** Fake paper textures that fight legibility.

## 3. Hardware synth

- **Feel.** tactile, nerdy, satisfying to touch.
- **Palette.** bg `#222428`, panel `#2E3137`, ink `#ECEAE4`, mute `#A0A2A9`, accent `#FF6A1A`, led `#B6F23A`.
- **Type.** Display in `"Avenir Next Condensed", "Arial Narrow", system-ui`, small and uppercase. Labels in `ui-monospace`.
- **Shape.** Knobs with notches, sliders, button grids, LEDs with a soft bloom, stenciled labels, 4px radius.
- **Motion.** Knobs ease with inertia. An LED flickers once on press.
- **Signature.** Every control changes the main number live.
- **Best for.** Music and audio tools, control surfaces, idle games with many dials.
- **Beware.** Skeuomorphic gradients on every surface.

## 4. Newsprint

- **Feel.** confident, editorial, loud type.
- **Palette.** bg `#F2EEE6`, panel `#FFFFFF`, ink `#141414`, mute `#5C5A55`, accent `#C81E17`.
- **Type.** Display in `"Didot", "Bodoni 72", "Playfair Display", Georgia, serif` at very large sizes. Body in `Georgia, serif`. Captions in `system-ui` small caps.
- **Shape.** Column grids, thick and thin rules, halftone images, zero radius.
- **Motion.** The headline slides in line by line in 200 ms, with no bounce.
- **Signature.** A front page hero that reads like a headline about the user's own data.
- **Best for.** Content, news, dashboards with a story, landing pages.
- **Beware.** Serif body text at small sizes.

## 5. Greenhouse

- **Feel.** growing, warm, patient.
- **Palette.** bg `#F3EFE3`, panel `#E4EAD5`, ink `#14301F`, mute `#4F6755`, accent `#B8481C`, leaf `#3E7B4F`, sun `#E8B23A`.
- **Type.** Display in `ui-serif, Georgia, serif`, weight 600. Body in `system-ui`.
- **Shape.** Organic blobs, leaf radii such as 24px 4px, stems as connectors, line drawn plants.
- **Motion.** Things grow from 0.9 scale and settle softly in 400 ms.
- **Signature.** Progress is a plant that grows.
- **Best for.** Habits, wellness, gardening and idle games, sustainability.
- **Beware.** Stock leaf icons and green gradients.

## 6. Industrial terminal

- **Feel.** raw, fast, no ornament.
- **Palette.** bg `#0A0A0A`, panel `#141414`, ink `#EDEDED`, mute `#8A8A8A`, accent `#FF4D00`, ok `#39D98A`.
- **Type.** `ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace` everywhere, in two sizes only.
- **Shape.** Visible 1px borders in `#2A2A2A`, a strict 8px grid, zero radius, ASCII rules.
- **Motion.** Instant, with a one frame cursor blink. Key moments type out at 12 ms per character.
- **Signature.** Output prints as if the machine is thinking.
- **Best for.** Developer tools, data tools, hacker games.
- **Beware.** Green on black is the cliché. Keep the single orange accent.

## 7. Clay toy

- **Feel.** friendly, squishy, safe.
- **Palette.** bg `#FFF4EA`, panel `#FFFFFF`, ink `#3D2C4D`, mute `#6F5F7B`, accent `#D9482A`, mint `#8FD6B5`, butter `#FFD66B`.
- **Type.** Display in `ui-rounded, "SF Pro Rounded", Nunito, system-ui`, weight 800. Body in the same family at 500.
- **Shape.** Radii from 20px to 28px, soft inner highlights, shadows tinted with the panel hue, chunky 56px buttons.
- **Motion.** Squash and stretch on press with a 180 ms spring. Confetti rarely.
- **Signature.** The primary button squishes and the whole screen answers.
- **Best for.** Family and kids, casual games, onboarding heavy apps.
- **Beware.** Pastel on pastel with weak contrast.

## 8. Travel poster

- **Feel.** optimistic, graphic, retro modern.
- **Palette.** bg `#F6E8CF`, panel `#FFF6E3`, ink `#14213D`, mute `#4D5A75`, accent `#C23B4E`, teal `#1B6F78`, sun `#F28F3B`.
- **Type.** Display in `"Futura", "Century Gothic", "Avenir Next", system-ui`, uppercase, heavy, tight tracking. Body in `system-ui`.
- **Shape.** Flat color blocks, sun discs, layered hills with no outlines, optional paper grain at 4 percent.
- **Motion.** Layers parallax at three speeds in 500 ms ease in out.
- **Signature.** The hero is a flat illustrated scene, not a photo.
- **Best for.** Landing pages, travel, weather, casual games with a world.
- **Beware.** Gradients inside the shapes.

## 9. Blueprint

- **Feel.** engineered, exact, studious.
- **Palette.** bg `#0E3A5E`, panel `#134A75`, ink `#EAF4FB`, mute `#A8CBE6`, accent `#FFD166`, line `#6FB1E0`.
- **Type.** Display in `ui-monospace, Menlo, monospace`, uppercase. Body in `system-ui`. Dimension labels at 11px, tracked.
- **Shape.** A 24px grid background, 1px light lines, dimension arrows, corner marks, a title block in the footer.
- **Motion.** Lines draw themselves with `stroke-dashoffset` in 500 ms.
- **Signature.** The main screen draws itself like a plotted drawing.
- **Best for.** Tools for builders, planners, calculators, engineering and architecture sims.
- **Beware.** A grid so loud it hurts reading.

## 10. Deep sea

- **Feel.** quiet, vast, curious.
- **Palette.** bg `#04141C`, panel `#082630`, ink `#DDF4F0`, mute `#7FA9AB`, accent `#3DF5C8`, glow `#5B8DEF`.
- **Type.** Display in `"Avenir Next", system-ui`, weight 300, wide tracking. Body in `system-ui`.
- **Shape.** Depth layers with blur and fog, soft circular nodes, light rays.
- **Motion.** Slow drift over 20 to 40 seconds. Ripples on touch. Nothing snaps.
- **Signature.** Touching anything sends a ripple through the whole scene.
- **Best for.** Ambient apps, exploration and discovery games, music visualizers.
- **Beware.** Glow on everything. One glowing thing per screen.

## 11. Sticker book

- **Feel.** playful, loud, personal.
- **Palette.** bg `#FFF3D6`, panel `#FFFFFF`, ink `#1B1B2F`, mute `#5A5A72`, accent `#E8344A`, teal `#00A6A6`, sun `#FFC857`.
- **Type.** Display in `"Trebuchet MS", "Avenir Next", system-ui`, weight 900. Body in `system-ui`.
- **Shape.** 3px ink outlines, hard offset shadows such as `4px 4px 0 ink`, die cut stickers tilted up to 3 degrees, 12px radii.
- **Motion.** Stickers slap in with overshoot in 220 ms.
- **Signature.** Rewards arrive as stickers the user can place.
- **Best for.** Consumer apps, social and party games, onboarding.
- **Beware.** Outlines on text and on everything else.

## 12. Library and brass

- **Feel.** serious, warm, trusted.
- **Palette.** bg `#1F1611`, panel `#2B1F17`, ink `#F0E4CF`, mute `#B7A78C`, accent `#C9A24D`, oxblood `#7A2E2E`, forest `#2F4A3A`.
- **Type.** Display in `"Iowan Old Style", "Palatino Linotype", Georgia, serif`, weight 600. Numbers in tabular `ui-monospace`.
- **Shape.** Leather panel tones, thin brass rules, corner details, engraved dividers, 2px radius.
- **Motion.** 300 ms fades. Ledger rows slide in one by one, with no bounce.
- **Signature.** Totals settle like a ledger being written.
- **Best for.** Finance, accounting, legal, premium tools.
- **Beware.** Gold gradients. Keep the brass flat.

## 13. Swiss grid

- **Feel.** calm authority, huge type.
- **Palette.** bg `#FAFAF7`, panel `#FFFFFF`, ink `#111111`, mute `#5B5B58`, accent `#E3000F`.
- **Type.** `"Helvetica Neue", Helvetica, Arial, system-ui`. Display at weight 700 and huge sizes with tight leading. Body at 400.
- **Shape.** A strict 12 column grid, shared baselines, one accent, no shadows, zero radius.
- **Motion.** Elements slide along grid axes only, in 200 ms.
- **Signature.** One giant number or word owns the screen.
- **Best for.** Finance, promo pages, portfolios, anything with one big claim.
- **Beware.** Centered layouts that break the grid.
