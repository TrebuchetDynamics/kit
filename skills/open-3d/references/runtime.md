# Open 3D runtime

## Read-only preflight

Reading instructions has no runtime requirements. For a helper, use Python 3.9+
(`python3 --version`) and check only the imports and tools in the matching row.
For a scene preview, check the browser's WebGL context and module loads. The
starter and exploded demo use Three.js 0.169.0 in their import maps; in a project,
use its existing dependencies or approved local modules. No runtime setup,
package download, browser download or provider configuration is implicit.

| Operation | Python imports | Other requirements |
| --- | --- | --- |
| Serve a preview | standard library only | None |
| Site/viewport check | `playwright`, `PIL` | Selected browser(s), project fonts |
| Record MP4 | `playwright` | Selected browser, project fonts, `ffmpeg` with `libx264` and MP4 muxer, `ffprobe` |
| Compare videos | `PIL` | `ffmpeg` with `libx264` and MP4 muxer, `ffprobe`; readable `--font` file if specified, otherwise upstream system/bundled Pillow fallback |
| Scroll film `frames` / `video` / `seams` | `PIL` for `frames`, `numpy` and `PIL` for `seams` | `ffmpeg` with PNG output for `frames`/`seams`, `libx264` and MP4 muxer for `video`; Pillow WebP support for `frames` |
| Alpha key / plate | `cv2`, `numpy`, `PIL` for key; `numpy`, `PIL` for plate | For key, OpenCV input decoding; `ffmpeg` with `libx264`/MP4 for `--stacked` or `libvpx-vp9`/WebM for `--webm`; Pillow WebP support for `--frames` |
| Build cursor rig | `cv2`, `numpy` | `ffmpeg` with PNG output |
| Motion loop check / paste back | `cv2`, `numpy` | OpenCV video/image decoding for the inputs; `ffmpeg` with `libx264` and MP4 muxer only for loop `--fix` |

- **Imports.** In the Python environment that will run the helper, import the
  modules in the row, for example `timeout 10 python3 -B -c 'import playwright, PIL'`
  for site checks. `PIL` comes from Pillow and `cv2` from OpenCV. For WebP output
  check `PIL.features.check('webp')`.
- **Browser.** Launch and close each requested engine without navigating. Use
  the same helper path and engine as the final command:

  ```sh
  timeout 15 python3 -B - "$helper" chromium <<'PY'
  import runpy
  import sys
  from playwright.sync_api import sync_playwright

  with sync_playwright() as p:
      runpy.run_path(sys.argv[1])["launch"](p, sys.argv[2]).close()
  PY
  ```

- **Fonts.** On the authorized preview, await `document.fonts.ready`. For each
  required web face, call `document.fonts.load()` with its CSS font shorthand
  and representative text; require a matching loaded face and inspect the text
  for fallback. Check required local faces in the browser's rendered-font
  inspector; generic system stacks need no named font. For a comparison with
  `--font`, open that file with `PIL.ImageFont.truetype()` before encoding.
- **Encoders.** Run `timeout 10 ffmpeg -hide_banner -encoders`,
  `timeout 10 ffmpeg -hide_banner -muxers` and `timeout 10 ffprobe -version` where
  required. Match the requested output format and codec.

If a probe fails, name the missing capability and ask for an existing working
environment or asset. Leave that operation unverified until it passes.

## Check and record

Set `OPEN_3D` to the absolute path of this installed skill directory. Serve only
an authorized project directory on loopback. The Range-aware
[server](../upstream/skills/frame-capture/scripts/serve.py) allows clips to seek.
Use a new output directory for checks, and run the recorder against the project's
ready signal (the starter exposes `window.__ready`):

```sh
# First terminal
timeout 300 python3 -B "$OPEN_3D/upstream/skills/frame-capture/scripts/serve.py" ./scene --port 8000
# Second terminal
timeout 180 python3 -B "$OPEN_3D/upstream/skills/site-check/scripts/check.py" \
  http://127.0.0.1:8000/ --ready 'window.__ready === true' --out shots
timeout 180 python3 -B "$OPEN_3D/runtime/record.py" \
  'http://127.0.0.1:8000/?record=1' check.mp4 --ready 'window.__ready === true' \
  --size 1280x720 --seconds 2 --fps 8
```

Inspect the contact sheet and report at desktop, tablet and phone widths. Check
reduced motion and the requested scroll or interaction states. Inspect the first,
transition and final encoded frames. In the project's record mode, hide loaders
as soon as ready, without an exit animation, so the initial frame shows the scene.
Allow assets and setup to complete at virtual time zero; drive timed motion from
the virtual clock, not wall-clock timers. Readiness must not depend on advancing
animation time, and `__recordFrame` must finish without waiting for another frame.
If a video cannot seek, correct the server or media before accepting the capture.

## Recorder derivation

Use the [derived recorder](../runtime/record.py) wherever a protocol names
`record.py`. The [original](../upstream/skills/frame-capture/scripts/record.py)
is kept under the [upstream pin](../UPSTREAM.json) for comparison, not execution.
The derived copy keeps the original CLI and carries two adaptations:

1. **Time zero.** Readiness and settle passes pump callbacks with the animation
   clock held at its initial time. Frame `n` uses absolute virtual time `n / fps`;
   frame zero uses the initial rAF, CSS and video time and calls `__recordFrame(0)`.
2. **Fail closed.** Callback, uncaught page and console errors fail the command.
   FFmpeg must finish successfully and ffprobe must decode exactly the requested
   number of frames without errors before the MP4 replaces the destination.
   Failure leaves any prior output in place. Correct the named page error or
   encoder issue before retrying. The success line reports encoded fps from the
   output stream, not render speed.

To refresh, verify the new source license, extract each selected file with
`git show REVISION:PATH`, update the recorded hashes and reapply the two edits
to the derived recorder. Run the real Chromium/FFmpeg regressions from the Kit checkout:

```sh
KIT_TEST_OPEN_3D=1 timeout 90 python3 -m unittest discover -s tests -p test_open_3d_capture.py
```
