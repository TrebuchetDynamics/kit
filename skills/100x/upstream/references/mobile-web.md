# Phone-first web

Read this before the first screen when the target is a phone, a touch screen or a game. `100x shots` finds these defects after the fact. This list prevents them, because retrofitting scaling costs more than starting right.

## Layout

1. Viewport meta on every page. `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`. Never `user-scalable=no`.
2. Full screen heights use `100dvh` with a `100vh` fallback. Plain `100vh` hides content behind the browser bars on phones.
3. Fixed bars pad with `env(safe-area-inset-top)`, `-right`, `-bottom` and `-left`, so notches and home indicators never cover controls.
4. Size layout in `rem`, `%`, `fr` and `clamp()`. Use `px` for hairlines and borders only. Fluid type, for example `font-size: clamp(1rem, 0.9rem + 1vw, 1.25rem)`.
5. Design portrait and landscape. If one is unsupported, show a designed rotate screen, never a broken layout.

## Touch

6. Tap targets are at least 44 by 44 CSS pixels with 8px between them. The visible shape may be smaller if padding extends the hit area.
7. Body text at 16px or more on phones. Inputs at 16px or more, or iOS zooms on focus. Nothing under 12px.
8. Use pointer events, not mouse and touch pairs. Set `touch-action: manipulation` on buttons and `touch-action: none` on game canvases.
9. Nothing important lives behind hover. Give every hover state a press equivalent.
10. Games and full screen tools set `overscroll-behavior: contain` so a swipe never scrolls the page behind.

## Canvas and pixels

11. Size the backing store, not only the CSS box. `canvas.width = Math.round(cssWidth * dpr)` with `dpr = Math.min(devicePixelRatio, 3)`, then `ctx.scale(dpr, dpr)`.
12. React to size changes with `ResizeObserver` on the canvas parent. Re-layout without a reload on rotation and on window resize.
13. Pixel art uses `image-rendering: pixelated` at integer scales only.

## Behavior

14. One `requestAnimationFrame` loop. Animate `transform` and `opacity`. Cap particles and cap work per frame, because the target phone is not your laptop.
15. Save on `visibilitychange` and `pagehide`, not only on a timer. Keep a version key in saved data and migrate on load. Catch quota errors.
16. Honor `prefers-reduced-motion` by shortening or removing large motion.
17. Installable when the brief wants it. A manifest, `theme-color`, 192 and 512 icons and an `apple-touch-icon`.

## Sizes to check

`100x shots --matrix phone` runs 320x568, 360x640, 390x844, 430x932 and the landscape sizes 844x390 and 640x360. `--matrix all` adds a 280 wide folded phone, two tablet sizes and six desktop sizes up to 3440x1440. `all-rotate` is `all` plus a rotation test that checks the layout again after the viewport rotates without a reload. `100x-must-not-break` runs `all-rotate` for the `screen-sizes` kind.
