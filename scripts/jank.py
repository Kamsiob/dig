#!/usr/bin/env python3
"""Count dropped frames while using Dig on a real screen.

Milliseconds measured offscreen tell you almost nothing: with no compositor and
no GPU the numbers are frame scheduling, not work. What a person calls lag is
frames that did not arrive in time, so this counts those, on the display that is
actually there.

    python scripts/jank.py --data /tmp/jank            a week of work
    python scripts/jank.py --data /tmp/jank --big      a year of it

It opens a real window. Let it get on with it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

WATCH = """
(function(){
  window.__frames = [];
  window.__watching = true;
  var last = performance.now();
  function tick(now) {
    if (!window.__watching) return;
    window.__frames.push(now - last);
    last = now;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(function(now){ last = now; requestAnimationFrame(tick); });
  return 1;
})()
"""

# A minute of ordinary use, in the order a person would do it.
FLOW = [
    ("open Home", "go('home')"),
    ("open Projects", "go('projects')"),
    ("open the Roadmap", "go('roadmap')"),
    ("open Ideas", "go('ideas')"),
    ("open the Library", "go('library')"),
    ("open Your review", "go('week')"),
    ("open Projects again", "go('projects')"),
    ("open a heavy project", "openP(BIGGEST)"),
    ("its Roadmap tab", "S.ptab='rm';render()"),
    ("its Record tab", "S.ptab='rec';render()"),
    ("back to its Work tab", "S.ptab='work';render()"),
    ("tick something", "toggleItem(BIGGEST, Pr(BIGGEST).items[0].id)"),
    ("tick another", "toggleItem(BIGGEST, Pr(BIGGEST).items[1].id)"),
    ("tick a third", "toggleItem(BIGGEST, Pr(BIGGEST).items[2].id)"),
    ("write a next step", "Pr(BIGGEST).next='Something else now';render()"),
    ("open the add box", "openCap()"),
    ("close it", "closeOv()"),
    ("filter to a group", "S.filterGroup=S.groups[0].id;go('projects')"),
    ("back to everything", "setGroup('all')"),
    ("open Settings", "go('settings')"),
    ("back to Home", "go('home')"),
]

# Scrolling is where a long list is felt, and it is the one thing a redraw
# cannot be blamed for, so it is measured on its own.
SCROLLS = [
    ("scroll the project list", "go('projects')", ".main"),
    ("scroll a heavy record", "openP(BIGGEST);S.ptab='rec';render()", ".main"),
    ("scroll the ideas", "go('ideas')", ".main"),
    ("scroll settings", "go('settings')", ".main"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--big", action="store_true")
    ap.add_argument("--json", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--size", default="", help="WIDTHxHEIGHT, default the whole screen")
    args = ap.parse_args()

    work = Path(args.data).resolve()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.environ["XDG_DATA_HOME"] = str(work)
    os.environ.setdefault("DIG_REDUCE_MOTION", "0")
    os.environ.pop("QT_QPA_PLATFORM", None)

    from tests.uiharness import UI, app, pump

    qt = app()
    screen = qt.primaryScreen()
    hz = round(screen.refreshRate()) or 60
    budget = 1000.0 / hz
    if args.size:
        width, height = (int(n) for n in args.size.lower().split("x"))
    else:
        # The window a person actually works in, which on a wide screen is the
        # whole of it. Paint cost goes with area, so testing small tests nothing.
        area = screen.geometry()
        width, height = area.width(), area.height()

    started = time.monotonic()
    ui = UI(size=(width, height)).start()
    cold = round((time.monotonic() - started) * 1000, 1)

    ui.run("S.org='Bench';S.setupWork.apps=true;obGo(4);S.obExamples=true;obFinish();",
           settle=900)

    bench = (REPO / "scripts" / "bench.py").read_text()
    bulk = bench[bench.index('BULK = """') + len('BULK = """'):bench.index('"""\n\nSCREENS')]
    if args.big:
        ui.js(f"({bulk.strip()})(40, 25)")
        pump(700)
    ui.raw("window.BIGGEST=S.projects.slice().sort(function(a,b){"
           "return (b.items.length+b.logs.length)-(a.items.length+a.logs.length)"
           "})[0].id;1")

    # Let the window settle before anything is counted.
    pump(1200)
    ui.raw(WATCH)
    pump(400)

    steps = []
    for name, action in FLOW:
        ui.raw("window.__mark=window.__frames.length;1")
        ui.raw(f"{action};1")
        pump(450)
        frames = ui.js("window.__frames.slice(window.__mark)") or []
        frames = [float(f) for f in frames if isinstance(f, (int, float))]
        # One frame late is a stutter at 120 Hz just as much as at 60.
        late = [f for f in frames if f > budget * 1.5]
        bad = [f for f in frames if f > budget * 3]
        steps.append({
            "what": name,
            "frames": len(frames),
            "late": len(late),
            "dropped": len(bad),
            "worst frame ms": round(max(frames), 1) if frames else 0,
        })

    for name, setup, target in SCROLLS:
        ui.raw(f"{setup};1")
        pump(500)
        ui.raw("window.__mark=window.__frames.length;1")
        # Roll it down and back, a wheel notch at a time, the way a hand does.
        ui.raw(
            f"(function(){{var e=document.querySelector({target!r})||document.scrollingElement;"
            "var n=0;var step=function(){"
            "e.scrollTop += (n<18? 120 : -120); n++;"
            "if(n<36) requestAnimationFrame(step)};requestAnimationFrame(step)}})();1"
        )
        pump(900)
        frames = ui.js("window.__frames.slice(window.__mark)") or []
        frames = [float(f) for f in frames if isinstance(f, (int, float))]
        steps.append({
            "what": name,
            "frames": len(frames),
            "late": len([f for f in frames if f > budget * 1.5]),
            "dropped": len([f for f in frames if f > budget * 3]),
            "worst frame ms": round(max(frames), 1) if frames else 0,
        })

    ui.raw("window.__watching=false;1")
    pump(200)

    total = sum(s["frames"] for s in steps)
    late = sum(s["late"] for s in steps)
    dropped = sum(s["dropped"] for s in steps)
    worst = max((s["worst frame ms"] for s in steps), default=0)

    report = {
        "window": f"{width}x{height}",
        "hz": hz,
        "label": args.label or ("a year of work" if args.big else "a week of work"),
        "cold start ms": cold,
        "frames": total,
        "late frames": late,
        "dropped frames": dropped,
        "worst frame ms": worst,
        "steps": steps,
    }

    print(f"\n{report['label']}, on the real display")
    print(f"window {width}x{height} at {hz} Hz, so a frame is due every "
          f"{budget:.1f} ms")
    print(f"cold start, launch to ready: {cold} ms")
    print(f"\n{total} frames while working through it")
    print(f"  {late} arrived late, over {budget * 1.5:.0f} ms "
          f"({late * 100 // max(total, 1)}%)")
    print(f"  {dropped} were badly late, over {budget * 3:.0f} ms "
          f"({dropped * 100 // max(total, 1)}%)")
    print(f"  worst single frame: {worst} ms")
    print("\nwhere it happens")
    print(f"  {'what':26s} {'frames':>7s} {'late':>6s} {'dropped':>8s} {'worst':>7s}")
    for s in sorted(steps, key=lambda x: -x["worst frame ms"]):
        if s["worst frame ms"] < budget * 1.5:
            continue
        print(f"  {s['what']:26s} {s['frames']:>7} {s['late']:>6} "
              f"{s['dropped']:>8} {s['worst frame ms']:>7}")

    ui.close()
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1))
        print(f"\nwritten to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
