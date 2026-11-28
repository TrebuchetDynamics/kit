# Verify a local Canvas sketch

Use Python 3 with the Playwright package and a compatible, already installed
Chromium. Pass its executable with `--chromium` if it is not named `chromium`
on `PATH`. The [verifier](scripts/verify_canvas.py) loads the package and launches
the browser before rendering. It does not install tools or write in the project.

1. In a trusted local HTML sketch, use one Canvas 2D element with backing
   dimensions from `?width=` and `?height=`. Render the `?hash=` input on load and
   expose `window.render(hash)` to reset and redraw in place. Set
   `window.rendered = true` only after each render finishes, including any asset
   or font loads. See the [seeded example](examples/seeded.html).
2. Keep assets under the sketch directory. The verifier serves them through a
   Playwright route at a local HTTP origin and refuses other HTTP requests.
   For text, load the actual bundled font files (use `@font-face` or `FontFace`
   and wait for the faces before drawing); missing or failed font loads fail
   the check. Font-free pieces need no font files. Pixel readback needs no PNG
   or video encoder. Do not pass untrusted HTML to the verifier.
3. From the skill directory, run:

   ```sh
   python3 -B scripts/verify_canvas.py examples/seeded.html
   ```

   Replace the example path with your local `.html` file. A missing browser,
   missing local asset, script error, or failed comparison gives a nonzero
   exit. Supply the missing local input or correct the sketch, then rerun.

The verifier prints the Chromium version and SHA-256 hashes of raw RGBA
pixels. It checks both fixed seeds in three fresh contexts each and runs
A→B→A in one page; the in-page renders must match the fresh results. To reject
trivial differences, at least 1% of pixels must differ by at least 16 in an
RGBA channel. A pass covers this 256×256, scale-1 Chromium run only. It does not
qualify other sizes, browsers, machines, animation, traits, or SVG.
