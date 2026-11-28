#!/usr/bin/env python3
"""Frame-exact video of any web page: WebGL, canvas, requestAnimationFrame, CSS and <video>.

The page's clock is replaced before any of its scripts run. performance.now, Date.now and
requestAnimationFrame read a virtual time; CSS animations and transitions are pinned to it
through the Web Animations API; every <video> is held paused and seeked to it. Each output
frame samples that clock at frame_number / fps, runs frame callbacks and takes a
screenshot. Frame zero and readiness passes use the initial virtual time.

    python3 record.py URL OUT.mp4 [--seconds 12] [--fps 60] [--size 1920x1080] [--dpr 1]
                      [--scroll "0:0 2:0 9:100%"] [--pointer drift] [--ready "window.__ready"]

    python3 record.py http://localhost:8000/ /tmp/check.mp4 --fps 8      # quick timing check

--scroll takes "seconds:position" keys. A position is pixels (1200), a share of the page's
scroll range (35%) or viewport heights (2.5vh). Between keys the scroll eases (smootherstep,
blended half-linear so long moves do not sprint in the middle); "~" after a key's time makes
that segment linear: "4~:100%".
--pointer moves the real mouse, so :hover and pointer-driven rigs react: "drift" circles
slowly around the centre, "x,y" holds a point (fractions of the viewport), "none" leaves it.
--ready is a JS expression polled before frame 0 while pre-roll frames run the page. Pages that need to know
they are being recorded can read window.__recording (true) and the frame clock from
performance.now(). A page may also define window.__recordFrame(t) to choreograph itself:
it is called with the virtual time in seconds before every frame.
--kill-lenis stops Lenis (and similar smooth-scroll libraries that read window.Lenis) from
loading, so the recorder owns the scroll position.

Needs: Playwright with the selected browser; ffmpeg with libx264 and ffprobe on PATH.
"""
import argparse
import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from fractions import Fraction
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout, sync_playwright
except ImportError as error:
    sys.exit(f"capture: Playwright is required in this Python environment: {error}")

CLOCK = r"""
(() => {
  window.__recording = true;
  if (window.__KILL_LENIS__) Object.defineProperty(window, 'Lenis', { get: () => undefined, set: () => {}, configurable: false });

  // media never runs on the wall clock; it is seeked to virtual time every frame
  const vids = new Set();
  const nativePause = HTMLMediaElement.prototype.pause;
  const nativePlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () {
    if (!vids.has(this)) { this.__t0 = vt; vids.add(this); }
    this.__playing = true;
    nativePause.call(this);
    this.dispatchEvent(new Event('playing'));
    return Promise.resolve();
  };
  HTMLMediaElement.prototype.pause = function () { this.__playing = false; nativePause.call(this); };
  Object.defineProperty(HTMLMediaElement.prototype, 'paused', { get() { return !this.__playing; }, configurable: true });

  const realNow = performance.now.bind(performance);
  let vt = realNow();
  const t0 = vt;
  const dateOffset = Date.now() - vt;
  const queue = new Map();
  let nextId = 1;
  performance.now = () => vt;
  Date.now = () => Math.round(dateOffset + vt);
  window.requestAnimationFrame = cb => { const id = nextId++; queue.set(id, cb); return id; };
  window.cancelAnimationFrame = id => { queue.delete(id); };

  // autoplaying videos never call play(); adopt them as they appear
  const adopt = () => document.querySelectorAll('video').forEach(v => {
    if (!vids.has(v) && (v.autoplay || v.hasAttribute('autoplay'))) { v.__t0 = vt; v.__playing = true; vids.add(v); nativePause.call(v); }
  });

  // A readiness pass pumps rendering without moving the animation clock.
  window.__step = async (elapsedMs, y, recording) => {
    vt = t0 + elapsedMs;
    adopt();
    if (y !== null) window.scrollTo(0, y);
    if (recording && typeof window.__recordFrame === 'function') {
      try { await window.__recordFrame(elapsedMs / 1000); }
      catch (e) { throw new Error(`__recordFrame: ${e?.message ?? e}`); }
    }
    const seeks = [];
    for (const v of vids) {
      if (!v.__playing || !v.duration || v.readyState < 1) continue;
      let t = (vt - v.__t0) / 1000;
      t = v.loop ? t % v.duration : Math.min(t, v.duration);
      t = Math.min(t, v.duration - 0.001);
      if (Math.abs(v.currentTime - t) > 0.002) {
        seeks.push(new Promise(res => { v.addEventListener('seeked', res, { once: true }); setTimeout(res, 1500); }));
        v.currentTime = t;
      }
    }
    await Promise.all(seeks);
    const cbs = [...queue.values()];
    queue.clear();
    for (const cb of cbs) {
      try { cb(vt); }
      catch (e) { throw new Error(`requestAnimationFrame: ${e?.message ?? e}`); }
    }
    for (const a of document.getAnimations()) {
      if (a.__v0 === undefined) { a.__v0 = vt; a.pause(); }
      const t = vt - a.__v0, end = a.effect ? a.effect.getComputedTiming().endTime : 0;
      if (t >= end && end !== Infinity) a.finish(); else a.currentTime = t;
    }
  };
})();
"""

METRICS = "() => ({ vh: innerHeight, max: Math.max(0, document.documentElement.scrollHeight - innerHeight) })"


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (6 * t - 15) + 10)


def soft(t):
    return 0.5 * min(1.0, max(0.0, t)) + 0.5 * smooth(t)


def parse_scroll(spec, metrics):
    keys = []
    for tok in spec.split():
        m = re.fullmatch(r"([\d.]+)(~?):([\d.]+)(px|%|vh)?", tok)
        if not m:
            sys.exit(f"bad --scroll key {tok!r}; use seconds:position, e.g. 3:50% or 4~:1200")
        t, linear, v, unit = float(m[1]), bool(m[2]), float(m[3]), m[4] or "px"
        y = v * metrics["max"] / 100 if unit == "%" else v * metrics["vh"] if unit == "vh" else v
        keys.append((t, y, linear))
    keys.sort(key=lambda k: k[0])
    return keys


def scroll_at(keys, t):
    if not keys:
        return None
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, y0, _), (t1, y1, linear) in zip(keys, keys[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
            return y0 + (y1 - y0) * (k if linear else soft(k))
    return keys[-1][1]


def pointer_at(mode, t, w, h):
    if mode == "none":
        return None
    if mode == "drift":
        return w * (0.5 + 0.22 * math.sin(t * 0.55)), h * (0.5 + 0.14 * math.sin(t * 0.41 + 1.1))
    x, y = (float(v) for v in mode.split(","))
    return w * x, h * y


def shoot(page, tries=4):
    """Screenshots can stall now and then (WebKit at 1080p, about 1 in 100). The clock is
    paused between steps, so a retry returns the identical frame."""
    for k in range(tries):
        try:
            return page.screenshot(type="png", timeout=30000)
        except PlaywrightTimeout:
            print(f"  screenshot stalled, retry {k + 1}", flush=True)
    sys.exit("screenshot kept stalling")


def cached_chromium():
    """Newest Chromium in the Playwright cache, for when the installed Playwright expects a
    browser build that was never downloaded (a common mismatch after upgrades)."""
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "~/Library/Caches/ms-playwright",
             "~/.cache/ms-playwright", os.path.join(os.environ.get("LOCALAPPDATA", ""), "ms-playwright")]
    pats = ["chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell*",
            "chromium-*/chrome-*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
            "chromium-*/chrome-*/chrome", "chromium-*/chrome-*/chrome.exe"]
    found = []
    for r in filter(None, roots):
        for pat in pats:
            found += glob.glob(os.path.join(os.path.expanduser(r), pat))
    found = [f for f in found if os.path.isfile(f) and os.access(f, os.X_OK)]
    return sorted(found, key=lambda f: int(re.search(r"-(\d+)/", f).group(1)))[-1] if found else None


def launch(p, browser):
    if browser == "webkit":
        return p.webkit.launch()
    args = ["--enable-gpu", "--ignore-gpu-blocklist", "--autoplay-policy=no-user-gesture-required"]
    if sys.platform == "darwin":
        args.append("--use-angle=metal")  # real GPU headless on macOS: 60 fps WebGL, not SwiftShader
    exe = os.environ.get("CHROME_PATH")
    try:
        return p.chromium.launch(args=args, executable_path=exe) if exe else p.chromium.launch(args=args)
    except Exception as e:
        exe = cached_chromium()
        if "Executable doesn't exist" not in str(e) or not exe:
            raise
        print(f"  Playwright's own Chromium is missing; using {exe}", flush=True)
        return p.chromium.launch(args=args, executable_path=exe)


def check_encoder():
    for name in ("ffmpeg", "ffprobe"):
        if not shutil.which(name):
            raise RuntimeError(f"missing {name}; make an existing FFmpeg build available on PATH")
    for option, capability in (("-encoders", "libx264"), ("-muxers", "mp4")):
        probe = subprocess.run(["ffmpeg", "-hide_banner", option], capture_output=True, text=True, timeout=10)
        if probe.returncode or not any(line.split()[1:2] == [capability] for line in probe.stdout.splitlines()):
            raise RuntimeError(f"FFmpeg lacks {capability} or could not list {option[1:]}; "
                               f"use an existing compatible build. {probe.stderr.strip()}".rstrip())


def encode(args, path):
    return subprocess.Popen([
        "ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(args.fps), "-c:v", "png", "-i", "-",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-r", str(args.fps), "-movflags", "+faststart", "-an", path,
    ], stdin=subprocess.PIPE)

def require_complete(path, total):
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
        "-show_entries", "stream=nb_read_frames,avg_frame_rate,width,height,duration",
        "-of", "json", str(path),
    ], capture_output=True, text=True)
    if probe.returncode or probe.stderr:
        raise RuntimeError(f"incomplete encoding: ffprobe: {probe.stderr.strip() or probe.returncode}")
    streams = json.loads(probe.stdout).get("streams", [])
    stream = streams[0] if streams else {}
    decoded = stream.get("nb_read_frames", "0")
    if str(decoded) != str(total):
        raise RuntimeError(f"incomplete encoding: expected {total} frames, decoded {decoded}")
    return stream


def capture(args, path, w, h, total):
    errors = []
    with sync_playwright() as p:
        try:
            browser = launch(p, args.browser)
        except PlaywrightError as error:
            raise RuntimeError(f"cannot launch {args.browser}; provide a working browser and its system libraries: {error}") from error
        page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=args.dpr)
        page.on("pageerror", lambda e: errors.append(f"page error: {e}"))
        page.on("console", lambda m: m.type == "error" and errors.append(f"console error: {m.text}"))

        def check_page():
            if errors:
                raise RuntimeError("\n  ".join(dict.fromkeys(errors)))

        def step(ms=0, y=None, recording=False):
            page.evaluate("([ms, y, recording]) => window.__step(ms, y, recording)", [ms, y, recording])
            check_page()

        if args.kill_lenis:
            page.add_init_script("window.__KILL_LENIS__ = true;")
        page.add_init_script(CLOCK)
        page.goto(args.url, wait_until="load")
        check_page()
        # rAF is virtual, so nothing renders until we step. Pump pre-roll frames (in real time,
        # so network loads land) until the page says it is ready, then let it settle.
        t_wait = time.monotonic()
        while not page.evaluate(f"() => !!({args.ready})"):
            if time.monotonic() - t_wait > 120:
                sys.exit(f"page never satisfied --ready {args.ready!r}")
            step()
            time.sleep(0.03)
        page.evaluate("document.fonts.ready")
        for _ in range(max(1, round(args.settle * 20))):
            step()
            time.sleep(0.05)
        keys = parse_scroll(args.scroll, page.evaluate(METRICS)) if args.scroll else []
        stuck = page.evaluate("""() => [...document.querySelectorAll('video')].filter(v =>
            v.duration > 0.1 && !(v.seekable.length && v.seekable.end(v.seekable.length - 1) > 0.1)).map(v => v.currentSrc)""")
        if stuck:
            print("  warning: these videos cannot seek, so they will hold one frame. The server ignores HTTP\n"
                  "  Range requests (python3 -m http.server does); serve the page with scripts/serve.py:\n    "
                  + "\n    ".join(stuck), flush=True)

        with encode(args, path) as ff:
            try:
                started = time.monotonic()
                for n in range(total):
                    t = n / args.fps
                    pt = pointer_at(args.pointer, t, w, h)
                    if pt:
                        page.mouse.move(*pt)
                    step(1000 * t, scroll_at(keys, t), recording=True)
                    png = shoot(page)
                    check_page()
                    ff.stdin.write(png)
                    if n % max(1, round(args.fps * 2)) == 0:
                        print(f"  {t:6.2f}s  frame {n}/{total}  ({time.monotonic() - started:.0f}s real)", flush=True)
                ff.stdin.close()
                status = ff.wait()
                if status != 0:
                    raise RuntimeError(f"ffmpeg failed (exit {status})")
                # Dispatch browser events that arrived while waiting for FFmpeg.
                page.evaluate("() => null")
                check_page()
            except BaseException:
                ff.kill()
                raise
        browser.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--fps", type=float, default=60)
    ap.add_argument("--size", default="1920x1080", help="viewport in CSS px, WxH")
    ap.add_argument("--dpr", type=float, default=1, help="device pixel ratio; output is size x dpr")
    ap.add_argument("--browser", choices=["chromium", "webkit"], default="chromium")
    ap.add_argument("--scroll", default="", help='keys "seconds:position", e.g. "0:0 2:0 9:100%%"')
    ap.add_argument("--pointer", default="none", help="none | drift | x,y (fractions)")
    ap.add_argument("--ready", default="document.readyState === 'complete'", help="JS expression to wait for")
    ap.add_argument("--settle", type=float, default=0.5, help="seconds to settle at virtual time zero after ready")
    ap.add_argument("--kill-lenis", action="store_true")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--preset", default="slow")
    args = ap.parse_args()

    try:
        w, h = (int(v) for v in args.size.lower().split("x"))
        total = round(args.seconds * args.fps)
        if min(w, h, args.fps, args.dpr) <= 0 or total < 1:
            raise ValueError
    except (ValueError, OverflowError):
        ap.error("--size, --fps and --dpr must be positive; capture must request at least one frame")
    out = Path(args.out)
    try:
        check_encoder()
        with tempfile.TemporaryDirectory(prefix=".open-3d-", dir=out.parent) as temp:
            candidate = Path(temp) / "capture.mp4"
            capture(args, candidate, w, h, total)
            stream = require_complete(candidate, total)
            rate = float(Fraction(stream["avg_frame_rate"]))
            duration = float(stream["duration"])
            candidate.replace(out)
    except BrokenPipeError:
        sys.exit("capture: ffmpeg closed the input before encoding completed; see encoder errors above")
    except (KeyError, ValueError, ZeroDivisionError, OSError, RuntimeError,
            PlaywrightError, subprocess.TimeoutExpired) as error:
        sys.exit(f"capture: {error}")
    print(f"wrote {out}: {total} frames, {duration:.2f}s at {rate:g} encoded fps, "
          f"{stream['width']}x{stream['height']}")


if __name__ == "__main__":
    main()
