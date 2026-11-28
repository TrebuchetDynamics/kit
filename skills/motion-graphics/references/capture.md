# Seek, capture and export

Use a trusted, self-contained local HTML file. Run `python3 --version` and use an
existing Python 3 environment with the Playwright Python package and its matching
Chromium, including Chromium's system libraries. The [capture helper](../scripts/capture.py)
checks the import and launches the browser before writing frames. There is no encoder
or additional Python package needed for PNG capture. Do not install or fetch anything.

```sh
timeout 60 python3 -B /absolute/path/to/capture.py ./motion.html \
  --size 640x360 --duration 2 --at 0.37 1.28 --loop --out ./motion-frames
```

Replace the helper path, size, duration and sample times with those for the actual
artifact. Use a new output directory. Omit `--loop` for a hold or non-looping film.
Inline assets and embed the project's required fonts. For every required face, pass
`--font '600 32px "Project Sans"' 'Sample title'` (repeatable). Use the actual
weight/style, a single family with an embedded `@font-face` source, and sample
text from the artifact. The helper loads faces that match the shorthand and text
(including Unicode ranges) and fails if none load. This does not prove glyph
coverage; inspect the rendered text for fallback.

The helper opens `?render` offline and seeks directly to each time, then seeks back
through those same times. It compares the PNGs for repeatability, checks both loop
endpoints when requested, and rejects a static result. It reports errors without a
passing receipt. Provide missing prerequisites separately and retry; if no sample
moves, fix `seek` or sample a moving interval. A failed run is not verified, even
if it left some sequence PNGs. Inspect the reported samples for unintended motion,
clipping and illegible content. Tests at sampled times do not prove every frame.

## Encode only on request

First run `timeout 10 ffmpeg -hide_banner -encoders` and check for `libx264` for
MP4 or `gif` for GIF. Check the matching output muxer with
`timeout 10 ffmpeg -hide_banner -muxers`. If
FFmpeg or the requested codec or muxer is missing, report the missing item and ask
for an existing suitable build. PNG capture can still pass; export stays unmet.

Add `--fps 30` to the capture command, with a larger timeout for long sequences.
This seeks to `frame_number / 30` starting at zero and stopping before the exact
endpoint. Use the same rate for encoding. Use even dimensions for `yuv420p` MP4.
For example, for a loop with both formats requested:

```sh
timeout 60 ffmpeg -n -framerate 30 -i ./motion-frames/frame-%06d.png -c:v libx264 -pix_fmt yuv420p ./motion.mp4
timeout 60 ffmpeg -n -framerate 30 -i ./motion-frames/frame-%06d.png -c:v gif -loop 0 ./motion.gif
```

`-loop 0` repeats the GIF indefinitely; use `-loop -1` for a one-shot GIF.
Check the finished media before reporting it; successful PNG checks do not prove
an encode succeeded or that the encoded result has the intended appearance.
