#!/usr/bin/env python3
"""Measure how fast Dig actually is, on the real app, before changing anything.

Numbers, not impressions. Cold start, how long a redraw takes on each screen,
how long a click takes to show its result, and what a save costs. Run it twice
with a change in between and the difference is the answer.

    python scripts/bench.py --data /tmp/bench            a normal amount of work
    python scripts/bench.py --data /tmp/bench --big      a lot of it
    python scripts/bench.py --data /tmp/bench --json out.json

Every timing is taken inside the page with performance.now(), around the work
itself, and repeated, because one measurement of anything on a desktop is
noise.
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

ROUNDS = 9

# A document the size of a year of real use: enough projects that every list
# has to work for its living, and one project heavy enough to be the worst
# case on its own.
BULK = """
(function(n, per){
  var t = S.types[0], g = S.groups[0];
  for (var i = 0; i < n; i++) {
    var p = {id:uid(), name:'Project number ' + i, group:g.id, type:t.id,
      stage:i % t.stages.length, enteredAt:new Date(NOW - (i % 90) * DAY),
      when:['now','next','later','someday'][i % 4],
      next:'The next thing to do on number ' + i,
      items:[], decisions:[], files:[], links:[], notes:'',
      pub:true, wait:null, lastAct:new Date(NOW - (i % 60) * DAY),
      releases:[], people:[], hist:[], logs:[], quiet:false, origin:null,
      parked:false, waitHist:[]};
    for (var j = 0; j < per; j++) {
      p.items.push({id:uid(), text:'Something to tick, number ' + j,
                    done:j % 3 === 0, tag:j % 7 === 0 ? 'bug' : ''});
      p.logs.push({id:uid(), text:'What happened on day ' + j + '. A line of it.',
                   at:new Date(NOW - j * DAY), stage:t.stages[0], highlight:j % 9 === 0});
    }
    for (var k = 0; k < 4; k++) {
      p.decisions.push({id:uid(), no:i * 4 + k + 1,
        text:'Decided something on ' + i + ', number ' + k + ', and why.',
        at:new Date(NOW - k * DAY), supersedes:null, superseded:false});
      p.releases.push({v:'1.' + k, at:new Date(NOW - k * 7 * DAY), note:'What was in it'});
      p.people.push({n:'Person ' + k, r:'reviewer'});
    }
    S.projects.push(p);
  }
  for (var q = 0; q < n; q++) {
    S.ideas.push({id:uid(), text:'An idea, number ' + q,
                  desc:'A line about it, so the card has something in it.',
                  at:new Date(NOW - q * DAY), opened:null, group:''});
    S.library.push({id:uid(), kind:q % 2 ? 'note' : 'link',
                    title:'Something kept, number ' + q,
                    meta:'example.com/' + q, group:''});
    S.inbox.push({id:uid(), text:'Unfiled, number ' + q, type:'todo',
                  at:new Date(NOW - q * DAY), guess:null});
  }
  render();
  return {projects:S.projects.length, ideas:S.ideas.length};
})
"""

SCREENS = [
    ("home", "S.view='home'"),
    ("projects", "S.view='projects';S.sort='activity';S.filterGroup='all'"),
    ("roadmap", "S.view='roadmap'"),
    ("project work", "S.projectId=BIGGEST;S.view='project';S.ptab='work'"),
    ("project record", "S.projectId=BIGGEST;S.view='project';S.ptab='rec'"),
    ("ideas", "S.view='ideas'"),
    ("library", "S.view='library'"),
    ("review", "S.view='week'"),
    ("settings", "S.view='settings'"),
]

# What a person actually does, and how long it takes to show.
ACTIONS = [
    ("tick a checklist item",
     "S.projectId=BIGGEST;S.view='project';S.ptab='work';render()",
     "toggleItem(BIGGEST, Pr(BIGGEST).items[0].id)"),
    ("type in the next step",
     "S.projectId=BIGGEST;S.view='project';S.ptab='work';render()",
     "Pr(BIGGEST).next='Another thing entirely';render()"),
    ("move between screens",
     "S.view='home';render()",
     "go('projects')"),
    ("open a project",
     "S.view='projects';render()",
     "openP(BIGGEST)"),
    ("switch a project tab",
     "S.projectId=BIGGEST;S.view='project';S.ptab='work';render()",
     "S.ptab='rec';render()"),
    ("filter to one group",
     "S.view='projects';render()",
     "S.filterGroup=S.groups[0].id;render()"),
    ("open the add box",
     "S.view='home';render()",
     "openCap()"),
]


def timed(ui, setup: str, work: str, rounds: int = ROUNDS) -> dict:
    """How long `work` takes, measured in the page, after `setup` each time."""
    runs = []
    for _ in range(rounds):
        ui.run(f"{setup};1", settle=90)
        value = ui.js(
            "(function(){var a=performance.now();"
            f"{work};"
            "var b=performance.now();return Math.round((b-a)*1000)/1000})()"
        )
        if isinstance(value, (int, float)):
            runs.append(float(value))
    runs.sort()
    return {
        "median": round(statistics.median(runs), 2) if runs else None,
        "worst": round(runs[-1], 2) if runs else None,
        "runs": len(runs),
    }


def painted(ui, setup: str, work: str, rounds: int = ROUNDS) -> dict:
    """How long until the next frame is actually on screen.

    A redraw that returns quickly and then leaves the compositor to do the work
    is still a stutter to the person watching, so this waits for the frame.
    """
    from tests.uiharness import pump

    runs = []
    for _ in range(rounds):
        ui.run(f"{setup};1", settle=90)
        ui.raw(
            "window.__painted=null;(function(){var a=performance.now();"
            f"{work};"
            "requestAnimationFrame(function(){requestAnimationFrame(function(){"
            "window.__painted=Math.round((performance.now()-a)*1000)/1000})})})();1"
        )
        for _ in range(80):
            pump(15)
            value = ui.js("window.__painted")
            if value is not None:
                runs.append(float(value))
                break
    runs.sort()
    if not runs:
        return {"median": None, "worst": None, "runs": 0}
    return {
        "median": round(statistics.median(runs), 2),
        "worst": round(runs[-1], 2),
        "runs": len(runs),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--big", action="store_true", help="a year of work, not a week")
    ap.add_argument("--json", default="")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    work = Path(args.data).resolve()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    os.environ["XDG_DATA_HOME"] = str(work)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --no-sandbox --in-process-gpu --disable-dev-shm-usage",
    )
    os.environ.setdefault("DIG_REDUCE_MOTION", "0")

    from tests.uiharness import UI, app

    app()

    started = time.monotonic()
    ui = UI().start()
    cold = round((time.monotonic() - started) * 1000, 1)

    ui.run("S.org='Bench';S.setupWork.apps=true;obGo(4);S.obExamples=true;obFinish();",
           settle=700)

    size = {"projects": len(ui.js("S.projects")), "ideas": len(ui.js("S.ideas"))}
    if args.big:
        size = ui.js(f"({BULK.strip()})(40, 25)")
        ui.run("1;", settle=600)

    # The worst case on the screen: whichever project carries the most.
    ui.raw("window.BIGGEST=S.projects.slice().sort(function(a,b){"
           "return (b.items.length+b.logs.length)-(a.items.length+a.logs.length)"
           "})[0].id;1")
    heaviest = ui.js("(function(){var p=Pr(BIGGEST);return {items:p.items.length,"
                     "logs:p.logs.length,decisions:p.decisions.length}})()")

    report = {
        "heaviest project": heaviest,
        "label": args.label or ("a year of work" if args.big else "a week of work"),
        "size": size,
        "cold start ms": cold,
        "screens": {},
        "actions": {},
    }

    print(f"\n{report['label']}: {size}, heaviest project {heaviest}")
    print(f"cold start, launch to ready: {cold} ms\n")

    print("a full redraw, in milliseconds")
    print(f"  {'screen':22s} {'median':>8s} {'worst':>8s}")
    for name, setup in SCREENS:
        got = timed(ui, setup, "render()")
        report["screens"][name] = got
        print(f"  {name:22s} {got['median']:>8} {got['worst']:>8}")

    print("\nfrom the click to the frame on screen, in milliseconds")
    print(f"  {'what a person does':26s} {'median':>8s} {'worst':>8s}")
    for name, setup, action in ACTIONS:
        got = painted(ui, setup, action)
        report["actions"][name] = got
        print(f"  {name:26s} {got['median']:>8} {got['worst']:>8}")

    save = timed(ui, "S.view='home';render()", "flushSave()", rounds=5)
    report["handing the document over ms"] = save
    print(f"\nhanding the whole document to the disk: "
          f"{save['median']} ms median, {save['worst']} worst")

    serialize = timed(ui, "1", "JSON.stringify(persist())", rounds=5)
    report["serialising the document ms"] = serialize
    print(f"turning the document into text:        "
          f"{serialize['median']} ms median, {serialize['worst']} worst")

    ui.close()
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1))
        print(f"\nwritten to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
