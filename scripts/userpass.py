#!/usr/bin/env python3
"""Use Dig the way a person would, for a week's worth of work, and write down
everything that goes wrong.

BUILD_PLAN Phase 8 asks for a scripted pass over the real app on a fresh
profile, and the addendum adds a list of its own. This is that pass. It drives
the app a person launches, not a stand in for it: the same window, the same
bridge, the same database.

    python scripts/userpass.py --data /tmp/pass

Nothing here stops at the first failure. Every step records what it found and
the run ends with the whole list, because a pass that halts on the first defect
hides the nine behind it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


class Pass:
    """One run through the app, with a list of what it found."""

    def __init__(self, ui) -> None:
        self.ui = ui
        self.found: list[str] = []
        self.step = ""
        self.checks = 0

    def at(self, step: str) -> None:
        self.step = step
        print(f"\n--- {step}", flush=True)

    def check(self, ok, what: str) -> bool:
        self.checks += 1
        if not ok:
            self.found.append(f"{self.step}: {what}")
            print(f"    DEFECT  {what}", flush=True)
        return bool(ok)

    def same(self, got, want, what: str) -> bool:
        return self.check(got == want, f"{what} (got {got!r}, wanted {want!r})")

    # Shorthands so the steps below read like the thing being done.
    def js(self, expression): return self.ui.js(expression)
    def run(self, code, settle=280): self.ui.run(code, settle=settle)
    def text(self, sel=".main"): return self.ui.text(sel)
    def html(self, sel=".main"): return self.ui.html(sel)
    def count(self, sel): return self.ui.count(sel)
    def click(self, sel, settle=300): self.ui.click(sel, settle=settle)
    def toasts(self): return self.ui.toasts()


def console_is_clean(p: Pass) -> None:
    noise = [m for m in p.ui.console if "Uncaught" in m or "TypeError" in m
             or "not defined" in m or "null" in m.lower()]
    p.check(not noise, f"the console complained: {noise[:3]}")
    p.ui.console.clear()


# ------------------------------------------------------------------ the steps


def step_1_fresh_start(p: Pass) -> None:
    """A fresh machine opens on the welcome, and setup builds what it says."""
    p.at("1. Fresh start and setup")
    p.same(p.js("S.view"), "setup", "a fresh machine does not open on setup")
    p.same(p.js("S.obStep"), 1, "the welcome does not start at step one")
    p.check("no outbound internet requests of any kind" in p.ui.html("body"),
            "the welcome does not say the sentence about the network")

    p.run("S.org='Riverbank';S.you='Sam';obGo(3);"
          "S.setupWork.apps=true;S.setupWork.clients=true;S.setupWork.personal=true;"
          "obGo(4);S.obExamples=false;obGo(5);obFinish();", settle=700)

    p.same(p.js("S.view"), "home", "setup did not finish into Home")
    p.same([g["id"] for g in p.js("S.groups")], ["apps", "clients", "personal"],
           "the three work kinds did not make their three groups")
    p.same([t["id"] for t in p.js("S.types")], ["app", "eng", "task"],
           "the three work kinds did not make their three types")
    p.check(p.js("S.projects") == [], "an empty start still created projects")
    p.check("Nothing lined up" in p.html(), "the empty Home has no empty state")
    p.check(p.text(".hd h1").startswith("Good"), "no greeting on Home")
    p.check("Sam" in p.text(".hd h1"), "the greeting does not use the name")

    for view, empty in (("projects", "No projects"), ("ideas", "No ideas"),
                        ("library", "Nothing here yet"), ("roadmap", "Nothing here")):
        p.run(f"go({view!r});")
        p.check(empty.lower() in p.html().lower(), f"{view} has no empty state")
    p.run("go('home');")
    console_is_clean(p)


def step_2_capture_everything(p: Pass) -> None:
    """Twelve things through Ctrl K, of every type, with and without a project,
    and each one lands where the sentence under the box said it would."""
    p.at("2. Capture twelve things")
    p.run("openNew('apps');document.getElementById('np-n').value='Ledger';createP(null);")
    p.run("openNew('clients');document.getElementById('np-n').value='Harbour site';createP(null);")
    project = p.js("S.projects.find(function(x){return x.name==='Ledger'}).id")

    # kind, words, project, where it should end up
    wanted = [
        ("idea", "A quieter way to file receipts", "", "ideas"),
        ("todo", "Renew the domain", "", "inbox"),
        ("bug", "The export drops the last row", project, "items"),
        ("note", "The client prefers Tuesdays", project, "library"),
        ("link", "example.com/spec", "", "library"),
        ("decision", "We are keeping the old structure", project, "decisions"),
        ("idea", "Walking routes near the office", "", "ideas"),
        ("todo", "Book the venue", project, "items"),
        ("note", "Three pages fewer than we started with", "", "library"),
        ("bug", "The date reads back a day early", "", "inbox"),
        ("link", "github.com/example/thing", project, "library"),
        ("auto", "Fix the footer on the small screen", "", "inbox"),
    ]
    for kind, words, into, _ in wanted:
        p.run(
            f"openCap({kind!r});S.capProject={into!r};"
            f"document.getElementById('cap-in').value={words!r};doCapture();",
            settle=220,
        )

    counted = {}
    for _, _, _, home in wanted:
        counted[home] = counted.get(home, 0) + 1
    p.same(len(p.js("S.ideas")), counted["ideas"], "the ideas did not all reach Ideas")
    p.same(len(p.js("S.inbox")), counted["inbox"], "the inbox did not get what it should")
    p.same(len(p.js("S.library")), counted["library"],
           "the notes and links did not all reach the Library")
    p.same(p.js("S.projects.reduce(function(n,x){return n+x.items.length},0)"),
           counted["items"], "the to-dos and bugs did not reach the checklist")
    p.same(p.js("S.projects.reduce(function(n,x){return n+x.decisions.length},0)"),
           counted["decisions"], "the decision did not reach the record")

    p.check(any(i["text"] == "A quieter way to file receipts" for i in p.js("S.ideas")),
            "an idea reached Ideas with the wrong words")
    p.check(p.js("S.library.some(function(x){return x.kind==='link'"
                 "&&x.meta==='example.com/spec'})"),
            "a link did not keep its address")
    p.check(p.js(f"Pr({project!r}).items.some(function(x){{return x.tag==='bug'}})"),
            "a bug did not arrive tagged as one")
    p.check(p.js("S.library.filter(function(x){return x.group}).length") >= 1,
            "a note captured on a project did not land in that project's group")
    guessed = p.js("(S.inbox.find(function(x){return /footer/.test(x.text)})||{}).type")
    p.same(guessed, "todo", "letting Dig guess put it in the wrong drawer")
    console_is_clean(p)


def step_3_sort_the_inbox(p: Pass) -> None:
    p.at("3. Sort the inbox both ways, throw one away")
    inbox = p.js("S.inbox")
    p.check(len(inbox) >= 2, "not enough in the inbox to sort")
    first = inbox[0]["id"]
    p.run(f"openSort({first!r});", settle=350)
    p.check(p.count("#ov-dlg.open") == 1, "the sort dialog did not open")
    p.run(f"var s=document.querySelector('#dlg-body select');"
          f"if(s){{s.value=S.projects[0].id}};doSort({first!r});", settle=350)
    p.check(not any(i["id"] == first for i in p.js("S.inbox")),
            "the sorted item is still in the inbox")

    rest = p.js("S.inbox")
    if rest:
        gone = rest[0]["id"]
        p.run(f"delInbox({gone!r});", settle=300)
        p.check(not any(i["id"] == gone for i in p.js("S.inbox")),
                "throwing one away left it there")
    console_is_clean(p)


def step_4_projects_and_stages(p: Pass) -> None:
    p.at("4. Three projects, next steps, two stages, an unmet warning, an undo")
    p.run("openNew('personal');document.getElementById('np-n').value='Kitchen';"
          "document.getElementById('np-x').value='Measure the alcove';createP(null);")
    p.same(len(p.js("S.projects")), 3, "there are not three projects")

    pid = p.js("S.projects.find(function(x){return x.name==='Ledger'}).id")
    p.run(f"Pr({pid!r}).next='Write the spec';render();scheduleSave();")
    p.same(p.js(f"Pr({pid!r}).next"), "Write the spec", "the next step did not save")

    p.run(f"addItem({pid!r},'Write the spec');", settle=250)
    p.run(f"openAdvance({pid!r});", settle=350)
    body = p.ui.html("#dlg-body")
    p.check("not ticked" in body.lower() or "unmet" in body.lower()
            or "still" in body.lower(), "moving on with an unticked item said nothing")
    stage_before = p.js(f"Pr({pid!r}).stage")
    p.run(f"doAdvance({pid!r});", settle=400)
    p.check(p.js(f"Pr({pid!r}).stage") == stage_before + 1, "the project did not move on")

    activity_before = len(p.js("S.activity"))
    p.run(f"openAdvance({pid!r});doAdvance({pid!r});", settle=400)
    p.run("undoAdvance();", settle=400)
    p.same(p.js(f"Pr({pid!r}).stage"), stage_before + 1, "undo did not put the stage back")
    p.same(len(p.js("S.activity")), activity_before + 1,
           "undo removed the wrong number of activity lines")
    console_is_clean(p)


def step_5_waiting(p: Pass) -> None:
    p.at("5. Two waiting, one resolved, and everywhere it shows")
    a, b = p.js("S.projects[0].id"), p.js("S.projects[1].id")
    for pid, what in ((a, "the signed agreement"), (b, "the font license")):
        p.run(f"openWait({pid!r});document.getElementById('w-what').value={what!r};"
              f"setWait({pid!r});", settle=350)
    p.same(p.js("S.projects.filter(function(x){return x.wait}).length"), 2,
           "two projects are not waiting")

    p.run("go('home');")
    p.check("the signed agreement" in p.html(), "Home does not show what it waits on")
    p.run("go('roadmap');")
    p.check("waiting" in p.html().lower(), "the roadmap does not mark a waiting project")
    p.run("go('week');")
    p.check("the signed agreement" in p.html(), "Your review does not list the wait")

    p.run(f"resolveWait({a!r});", settle=350)
    p.check(not p.js(f"Pr({a!r}).wait"), "resolving left it waiting")
    p.run(f"openP({a!r});S.ptab='rec';render();")
    p.check("the signed agreement" in p.html(),
            "the resolved wait is not in past waits")
    console_is_clean(p)


def step_6_decisions(p: Pass) -> None:
    p.at("6. Four decisions, one replacing another, numbered across projects")
    a, b = p.js("S.projects[0].id"), p.js("S.projects[1].id")
    p.run(f"recordDecision({a!r},'Keep the existing structure.','');", settle=250)
    p.run(f"recordDecision({a!r},'Ship without the importer.','');", settle=250)
    p.run(f"recordDecision({b!r},'One typeface, two weights.','');", settle=250)
    numbers = p.js("S.projects.map(function(x){return x.decisions.map(function(d)"
                   "{return d.no})}).reduce(function(a,b){return a.concat(b)},[])")
    p.same(sorted(numbers), list(range(1, len(numbers) + 1)),
           "decision numbers are not one run across every project")

    first = p.js(f"Pr({a!r}).decisions[0].no")
    p.run(f"recordDecision({a!r},'Actually, rebuild the structure.',{first!r});", settle=300)
    p.check(p.js(f"Pr({a!r}).decisions.find(function(d){{return d.no==={first}}}).superseded"),
            "the replaced decision is not marked as replaced")
    p.run(f"openP({a!r});S.ptab='rec';render();")
    p.check("replaced" in p.html().lower() or "supersed" in p.html().lower(),
            "the record does not say a decision was replaced")
    console_is_clean(p)


def step_7_releases(p: Pass) -> None:
    p.at("7. Two releases, on the project roadmap and in the review")
    pid = p.js("S.projects[0].id")
    for version, note in (("1.0", "First cut"), ("1.1", "Faster export")):
        p.run(f"addRelease({pid!r});document.getElementById('rv').value={version!r};"
              f"document.getElementById('rn').value={note!r};doRelease({pid!r});", settle=350)
    p.same(len(p.js(f"Pr({pid!r}).releases")), 2, "both releases did not save")
    p.run(f"openP({pid!r});S.ptab='rm';render();")
    p.check("1.1" in p.html(), "the project roadmap does not show the release")
    p.run("go('week');S.period='month';render();")
    p.check("1.1" in p.html(), "the review does not show the release")
    console_is_clean(p)


def step_8_people_links_files(p: Pass, sample: Path) -> None:
    p.at("8. People, links, and files including a name collision")
    pid = p.js("S.projects[0].id")
    p.run(f"addPerson({pid!r});document.getElementById('pn').value='Robin';"
          f"document.getElementById('pr').value='reviewer';"
          f"document.querySelector('#dlg-body .foot .btn.p').click();", settle=350)
    p.check(any(x["n"] == "Robin" for x in p.js(f"Pr({pid!r}).people")),
            "the person did not save")
    p.run(f"addLink({pid!r});document.getElementById('lk').value='example.com/spec';"
          f"document.querySelector('#dlg-body .foot .btn.p').click();", settle=350)
    p.check("example.com/spec" in p.js(f"Pr({pid!r}).links"), "the link did not save")

    p.ui.queue_open(str(sample))
    p.run(f"addFiles({pid!r},'');", settle=900)
    p.same(len(p.js("S.files")), 1, "the first file did not arrive")

    other = sample.parent / "second" / sample.name
    other.parent.mkdir(exist_ok=True)
    other.write_bytes(b"a different set of bytes entirely, same name\n")
    p.ui.queue_open(str(other))
    p.run(f"addFiles({pid!r},'');", settle=1200)
    if p.count("#ov-dlg.open") == 1 and "already" in p.ui.html("#dlg-body").lower():
        p.run("resolveClash('keep');", settle=800)
    p.same(len(p.js("S.files")), 2,
           "the same name with different bytes did not become two files")
    names = [f["name"] for f in p.js("S.files")]
    p.check(len(set(names)) == 2 or names[0] != names[1],
            "the collision did not get its own name")

    p.run(f"openFile(S.files[0].id);", settle=900)
    p.check(p.count(".viewer") == 1, "the viewer did not open")
    p.run("closeViewer();", settle=300)
    console_is_clean(p)


def step_9_roadmap(p: Pass) -> None:
    p.at("9. Horizons at all three levels, park and unpark")
    pid = p.js("S.projects[0].id")
    for horizon in ("now", "next", "later", "someday"):
        p.run(f"setWhen({pid!r},{horizon!r});", settle=250)
        p.same(p.js(f"Pr({pid!r}).hz"), horizon, f"the {horizon} horizon did not stick")
    p.run("go('roadmap');")
    p.check("Someday" in p.html(), "the roadmap has no Someday column")

    p.run(f"togglePark({pid!r});", settle=300)
    p.check(p.js(f"Pr({pid!r}).parked"), "parking did nothing")
    p.run("go('projects');S.sort='parked';render();")
    p.check(p.js(f"Pr({pid!r}).name") in p.html(), "the parked list does not show it")
    p.run(f"togglePark({pid!r});", settle=300)
    p.check(not p.js(f"Pr({pid!r}).parked"), "unparking did nothing")
    console_is_clean(p)


def step_10_ideas(p: Pass) -> None:
    p.at("10. Start an idea, and show another five times")
    p.run("go('ideas');")
    ideas = p.js("S.ideas")
    p.check(len(ideas) >= 2, "not enough ideas to work with")
    first = ideas[0]
    p.run(f"startIdea({first['id']!r});", settle=350)
    p.run("document.getElementById('np-n').value='From an idea';"
          f"createP({first['id']!r});", settle=500)
    p.check(not any(i["id"] == first["id"] for i in p.js("S.ideas")),
            "starting an idea left it in Ideas")
    started = p.js("S.projects.find(function(x){return x.name==='From an idea'})")
    p.check(started and started.get("from"), "the new project does not say where it came from")
    p.run(f"openP({started['id']!r});")
    p.check("idea" in p.html().lower(), "the project page does not mention its origin")

    p.run("go('home');")
    seen = set()
    for _ in range(5):
        p.run("pickResurf();render();", settle=200)
        seen.add(p.js("S.resurfId"))
    p.check(len(seen) >= 1, "show another never picked anything")
    console_is_clean(p)


def step_11_settings_shape(p: Pass) -> None:
    p.at("11. Types, stages, and checklists in Settings reach the projects")
    p.run("go('settings');")
    p.run("addType();", settle=350)
    types_now = len(p.js("S.types"))
    p.check(types_now >= 4, "adding a type did nothing")

    tid = p.js("S.types[0].id")
    p.run(f"renameStage({tid!r},0,'Sketch');", settle=300)
    p.same(p.js(f"T({tid!r}).stages[0]"), "Sketch", "renaming a stage did not stick")
    p.run(f"addStage({tid!r});", settle=300)
    p.run(f"addExp({tid!r},0,'Write down what it is for');", settle=300)
    p.check("Write down what it is for" in json.dumps(p.js(f"T({tid!r}).expected")),
            "the checklist suggestion did not save")

    pid = p.js(f"S.projects.find(function(x){{return x.type==={tid!r}}}).id")
    if pid:
        p.run(f"openP({pid!r});")
        p.check("Sketch" in p.html(), "the renamed stage did not reach the project")
    console_is_clean(p)


def step_12_export_import_recovery(p: Pass, work: Path) -> None:
    p.at("12. Export, wipe, import, and recover from a corrupt database")
    out = work / "export.json"
    p.ui.queue_save(str(out))
    p.run("exportData();", settle=900)
    p.check(out.exists(), "the export did not write a file")
    before = p.ui.on_disk()

    p.ui.queue_open(str(out))
    p.run("importData();", settle=900)
    p.run("doImport();", settle=1200)
    after = p.ui.on_disk()
    p.same(len(after.get("projects", [])), len(before.get("projects", [])),
           "importing what was exported changed the number of projects")

    p.ui.close()
    db = Path(os.environ["XDG_DATA_HOME"]) / "dig" / "dig.db"
    db.write_bytes(b"this is not a database")
    p.ui.start()
    p.check(p.js("!!S"), "a corrupt database left the app with no state")
    p.check(p.js("S.projects.length") >= 1, "recovery did not bring the projects back")
    console_is_clean(p)


def step_13_themes(p: Pass) -> None:
    p.at("13. Light, dark, follow system, and a restart")
    for mode in ("light", "dark", "system"):
        p.run(f"setTheme({mode!r});", settle=350)
        p.same(p.js("S.theme"), mode, f"{mode} did not take")
        shown = p.js("document.documentElement.getAttribute('data-theme')")
        p.check(shown in ("light", "dark"), f"{mode} left the page with no theme")
    p.run("setTheme('dark');", settle=300)
    p.ui.restart()
    p.same(p.js("S.theme"), "dark", "the theme was not remembered")
    p.same(p.js("document.documentElement.getAttribute('data-theme')"), "dark",
           "the remembered theme did not reach the page")
    console_is_clean(p)


def step_14_pdfs(p: Pass, work: Path) -> None:
    p.at("14. Every PDF, and the private exclusion note")
    pid = p.js("S.projects[0].id")
    jobs = [
        ("one project", f"openShare({pid!r});doShare({pid!r});", work / "project.pdf"),
        ("every project", "openShare(null);doShare(null);", work / "projects.pdf"),
        ("the roadmap", "openShare('rm');doShare('rm');", work / "roadmap.pdf"),
        ("the review", "go('week');savePdfWeek();", work / "review.pdf"),
    ]
    for what, code, target in jobs:
        p.ui.queue_save(str(target))
        p.run(code, settle=2600)
        ok = target.exists() and target.stat().st_size > 1000
        p.check(ok, f"the PDF for {what} did not save")
        if ok:
            head = target.read_bytes()[:5]
            p.check(head == b"%PDF-", f"the PDF for {what} is not a PDF")
    console_is_clean(p)


def step_15_geometry(p: Pass) -> None:
    p.at("15. Smallest and largest, and geometry remembered")
    p.ui.window.resize(1100, 720)
    p.ui.run("1;", settle=400)
    p.ui.window.resize(1500, 900)
    p.ui.run("1;", settle=600)
    p.ui.restart()
    size = p.ui.window.size()
    p.check(abs(size.width() - 1500) < 60 and abs(size.height() - 900) < 60,
            f"the window came back at {size.width()}x{size.height()}, not 1500x900")
    console_is_clean(p)


def step_16_reduced_motion(p: Pass) -> None:
    p.at("16. Reduced motion")
    p.run("setMotion(true);", settle=350)
    p.same(p.js("document.documentElement.getAttribute('data-motion')"), "reduce",
           "asking for less motion did not mark the page")
    moving = p.js(
        "Array.prototype.filter.call(document.querySelectorAll('#app *'),"
        "function(e){var c=getComputedStyle(e);"
        "return (parseFloat(c.transitionDuration)||0)>0"
        "||(parseFloat(c.animationDuration)||0)>0}).length"
    )
    p.check(moving == 0, f"{moving} things still animate with motion reduced")
    p.run("setMotion(false);", settle=300)
    console_is_clean(p)


# ------------------------------------------------- what the addendum added


def step_17_onboarding_again(p: Pass) -> None:
    p.at("17. Run setup again, with examples, and take them out")
    p.run("S.obStep=1;go('setup');", settle=350)
    p.same(p.js("S.view"), "setup", "setup would not replay")
    p.run("obGo(4);S.obExamples=true;obGo(5);obFinish();", settle=900)
    p.check(p.js("S.projects.filter(function(x){return x.example}).length") >= 1,
            "the examples were not added")
    p.check(p.js("S.projects.filter(function(x){return !x.example}).length") >= 1,
            "replaying setup removed real work")
    p.run("removeExamples();", settle=900)
    p.same(p.js("S.projects.filter(function(x){return x.example}).length"), 0,
           "the examples did not all come out")
    console_is_clean(p)


def step_18_files_every_way(p: Pass, work: Path) -> None:
    p.at("18. Every kind of file, by every route, viewed, copied, versioned, moved")
    made = {}
    made["notes.txt"] = b"A plain note.\nSecond line.\n"
    made["table.csv"] = b"name,count\nalpha,2\nbeta,5\n"
    made["page.md"] = b"# Heading\n\nSome **words**.\n"
    made["data.json"] = b'{"a": 1, "b": [2, 3]}\n'
    made["tiny.png"] = bytes.fromhex(
        "89504e470d0a1a0a0000000d494844520000000100000001080600000"
        "01f15c4890000000a49444154789c6360000002000100ffff0300000600"
        "05570cd7a90000000049454e44ae426082"
    )
    for name, body in made.items():
        (work / name).write_bytes(body)

    pid = p.js("S.projects[0].id")
    before = len(p.js("S.files"))
    p.ui.queue_open(*[str(work / n) for n in made])
    p.run(f"addFiles({pid!r},'');", settle=2000)
    p.same(len(p.js("S.files")), before + len(made), "not every file arrived")

    for name in made:
        fid = p.js(f"(S.files.find(function(f){{return f.name==={name!r}}})||{{}}).id")
        if not p.check(fid, f"{name} is not in the file list"):
            continue
        p.run(f"openFile({fid!r});", settle=900)
        p.check(p.count(".viewer") == 1, f"the viewer did not open for {name}")
        shown = p.ui.html(".viewer")
        if name.endswith(".txt"):
            p.check("A plain note" in shown, "the text file showed nothing")
        if name.endswith(".csv"):
            p.check("alpha" in shown, "the csv did not show as a table")
        if name.endswith(".md"):
            p.check("Heading" in shown, "the markdown showed nothing")
        p.run("closeViewer();", settle=250)

    fid = p.js("S.files[S.files.length-1].id")
    copy_to = work / "saved-copy.png"
    p.ui.queue_save(str(copy_to))
    p.run(f"saveFileCopy({fid!r});", settle=1200)
    if p.check(copy_to.exists(), "save a copy wrote nothing"):
        original = p.js(f"(S.files.find(function(f){{return f.id==={fid!r}}})||{{}}).name")
        source = work / original if (work / original).exists() else None
        if source:
            p.check(copy_to.read_bytes() == source.read_bytes(),
                    "the saved copy is not the same bytes")

    zip_to = work / "everything.zip"
    p.ui.queue_save(str(zip_to))
    p.run(f"saveAllFiles({pid!r},'');", settle=2500)
    if p.check(zip_to.exists(), "save all wrote no zip"):
        with zipfile.ZipFile(zip_to) as z:
            inside = z.namelist()
        p.check(any("manifest" in n.lower() for n in inside),
                "the zip has no manifest")

    text_id = p.js("(S.files.find(function(f){return f.name==='notes.txt'})||{}).id")
    if text_id:
        newer = work / "v2" / "notes.txt"
        newer.parent.mkdir(exist_ok=True)
        newer.write_bytes(b"A plain note, rewritten.\n")
        p.ui.queue_open(str(newer))
        count_before = len(p.js("S.files"))
        p.run(f"addFiles({pid!r},'');", settle=1500)
        if p.count("#ov-dlg.open") == 1:
            p.run("resolveClash('version');", settle=1000)
        p.same(len(p.js("S.files")), count_before,
               "replacing a file as a new version made a second file")
        p.check(p.js(f"(S.files.find(function(f){{return f.id==={text_id!r}}})||{{}}).version")
                != 1, "the new version did not raise the version number")

        p.run(f"moveFile({text_id!r});", settle=400)
        p.run(f"var s=document.querySelector('#dlg-body select');if(s)s.value='';"
              f"doMoveFile({text_id!r});", settle=700)
        p.run(f"deleteFile({text_id!r});", settle=700)
        p.check(not any(f["id"] == text_id for f in p.js("S.files")),
                "deleting a file left it in the list")
        p.run("var t=S.toasts[S.toasts.length-1];if(t&&t.undo)t.undo();", settle=700)
    console_is_clean(p)


def step_19_groups_and_log(p: Pass, work: Path) -> None:
    p.at("19. Group pages, a group one pager, and the log")
    gid = p.js("S.groups[0].id")
    p.run(f"openG({gid!r});", settle=500)
    p.same(p.js("S.view"), "group", "a group did not open its own page")
    p.check(p.count(".gh h1") == 1, "the group page has no heading")
    p.run("var d=document.querySelector('.gdesc');d.innerText='Everything we look after.';"
          "d.dispatchEvent(new Event('input',{bubbles:true}));", settle=600)
    p.same(p.js(f"G({gid!r}).description"), "Everything we look after.",
           "the group description did not save as it was typed")
    p.ui.restart()
    p.same(p.js(f"G({gid!r}).description"), "Everything we look after.",
           "the group description did not survive a restart")
    p.run(f"openG({gid!r});", settle=400)

    out = work / "group.pdf"
    p.ui.queue_save(str(out))
    p.run(f"openShare('g:'+{gid!r});doShare('g:'+{gid!r});", settle=2800)
    p.check(out.exists() and out.stat().st_size > 1000,
            "the group one pager did not save")

    pid = p.js("S.projects[0].id")
    p.run(f"addLog('project',{pid!r},'Walked the whole thing with fresh eyes.');", settle=400)
    p.check(len(p.js(f"Pr({pid!r}).logs")) >= 1, "the log entry did not save")
    p.run(f"openP({pid!r});S.ptab='rec';render();")
    p.check("fresh eyes" in p.html(), "the log entry is not on the record")
    p.run(f"toggleHighlight({pid!r},Pr({pid!r}).logs[0].id);", settle=350)
    p.run("go('week');S.period='month';render();")
    p.check("fresh eyes" in p.html(), "a highlighted log entry is not in the review")
    console_is_clean(p)


def step_20_duplicate_and_templates(p: Pass) -> None:
    p.at("20. Duplicate a project, and start one from a template")
    pid = p.js("S.projects[0].id")
    count = len(p.js("S.projects"))
    p.run(f"duplicateProject({pid!r});", settle=600)
    p.same(len(p.js("S.projects")), count + 1, "duplicating made no second project")
    copy = p.js("S.projects[S.projects.length-1]")
    p.check(copy["name"] != p.js(f"Pr({pid!r}).name"),
            "the duplicate has exactly the same name")
    p.check(not copy["decisions"], "the duplicate carried the decisions over")

    p.run(f"saveAsTemplate({pid!r});", settle=400)
    p.run(f"var i=document.querySelector('#dlg-body input');if(i)i.value='House style';"
          f"doSaveTemplate({pid!r});", settle=600)
    p.check(len(p.js("S.templates")) >= 1, "the template did not save")

    tid = p.js("S.templates[0].id")
    p.run("openNew('');document.getElementById('np-n').value='From a template';"
          f"var s=document.getElementById('np-tpl');if(s)s.value={tid!r};"
          f"applyTemplate(null,{tid!r});createP(null);", settle=700)
    made = p.js("S.projects.find(function(x){return x.name==='From a template'})")
    if p.check(made, "the project from a template was not created"):
        p.check(made["type"] == p.js(f"Pr({pid!r}).type"),
                "the template did not carry its type")
    console_is_clean(p)


def step_21_recently_deleted(p: Pass) -> None:
    p.at("21. Recently deleted, and putting something back")
    pid = p.js("S.projects[S.projects.length-1].id")
    name = p.js(f"Pr({pid!r}).name")
    p.run(f"doDeleteProject({pid!r});", settle=800)
    p.check(not p.js(f"!!Pr({pid!r})"), "the deleted project is still there")

    p.run("go('settings');loadDeleted();", settle=900)
    p.check(name in p.html(), "the deleted project is not in Recently deleted")
    p.run(f"restoreDeleted('projects',{pid!r});", settle=900)
    p.check(p.js(f"!!Pr({pid!r})"), "putting it back did not bring it back")
    p.same(p.js(f"Pr({pid!r}).name"), name, "it came back with a different name")
    console_is_clean(p)


def step_22_command_line(p: Pass) -> None:
    p.at("22. dig add from a terminal")
    before = len(p.js("S.inbox"))
    p.ui.window.handle_command(json.dumps({"add": "Something from the terminal"}))
    p.ui.run("1;", settle=800)
    p.same(len(p.js("S.inbox")), before + 1, "dig add did not reach the inbox")
    p.check(any(i["text"] == "Something from the terminal" for i in p.js("S.inbox")),
            "dig add saved the wrong words")
    console_is_clean(p)


def step_23_quiet(p: Pass) -> None:
    p.at("23. A project goes quiet, and can be found")
    pid = p.js("S.projects[0].id")
    p.run(f"Pr({pid!r}).lastAct=new Date(Date.now()-40*864e5).toISOString();"
          "render();scheduleSave();", settle=400)
    p.check(p.js(f"goneQuiet(Pr({pid!r}))"), "a month of silence did not count as quiet")
    p.run("go('projects');S.sort='quiet';render();")
    p.check(p.js(f"Pr({pid!r}).name") in p.html(),
            "the quiet filter does not find the quiet project")
    p.run("go('home');")
    p.check("quiet" in p.html().lower(), "Home says nothing about what has gone quiet")
    p.run("S.sort='activity';render();")
    console_is_clean(p)


def step_24_people_screen(p: Pass) -> None:
    p.at("24. The People screen")
    p.run("go('people');", settle=500)
    p.same(p.js("S.view"), "people", "the People screen did not open")
    p.check("Robin" in p.html(), "a person who is on a project is not listed")
    p.check(p.js("S.projects[0].name") in p.html() or "project" in p.html().lower(),
            "the People screen does not say where a person turns up")
    console_is_clean(p)


def step_25_backup_and_restore(p: Pass, work: Path) -> None:
    p.at("25. Back up everything, wipe, restore, and check it is identical")
    folder = work / "backups"
    folder.mkdir(exist_ok=True)
    p.ui.queue_save(str(folder / "dig-backup.zip"))
    p.run("backupEverything();", settle=3000)
    made = sorted(folder.glob("*.zip"))
    if not p.check(made, "the backup wrote nothing"):
        return
    archive = made[0]
    before = p.ui.on_disk()
    files_before = sorted(f["sha256"] for f in (before.get("files") or []))

    p.ui.close()
    root = Path(os.environ["XDG_DATA_HOME"]) / "dig"
    shutil.rmtree(root, ignore_errors=True)
    p.ui.start()
    p.check(not p.js("S.projects.length"), "wiping the folder left work behind")

    p.ui.queue_open(str(archive))
    p.run("restoreBackup();", settle=1200)
    p.run("doRestore();", settle=3000)
    p.ui.restart()
    after = p.ui.on_disk()
    p.same(len(after.get("projects", [])), len(before.get("projects", [])),
           "the restore brought back a different number of projects")
    files_after = sorted(f["sha256"] for f in (after.get("files") or []))
    p.same(files_after, files_before, "the restored files are not the same bytes")
    console_is_clean(p)


def step_26_csv(p: Pass, work: Path) -> None:
    p.at("26. Import a CSV")
    csv = work / "ideas.csv"
    csv.write_text("text,description\nA folding desk,For the small room\n"
                   "Bread on Sundays,Only if the oven is free\n")
    before = len(p.js("S.ideas"))
    p.ui.queue_open(str(csv))
    p.run("importCsv('ideas');", settle=1200)
    p.run("doCsvImport();", settle=1200)
    p.same(len(p.js("S.ideas")), before + 2, "the CSV did not bring in two ideas")
    p.check(any(i["text"] == "A folding desk" for i in p.js("S.ideas")),
            "the CSV import lost the words")
    console_is_clean(p)


def step_27_sync(p: Pass, work: Path) -> None:
    p.at("27. Pair a device, sync both ways, force a disagreement, revoke")
    from dig.sync.server import tailscale_addresses

    if not tailscale_addresses():
        p.check(True, "")
        print("    skipped: there is no Tailscale address on this machine",
              flush=True)
        return

    p.run("go('settings');syncOn();", settle=2000)
    p.run("loadSync();", settle=1200)
    running = p.js("SYNC.running")
    if not p.check(running, "the sync server would not start"):
        return
    address = p.js("SYNC.tailscale[0]")
    port = p.js("SYNC.port")
    p.run("syncPair();", settle=1500)
    code = p.js("SYNC.code||(document.querySelector('#dlg-body .code')||{}).textContent||''")
    if not p.check(code, "pairing produced no code"):
        return

    import subprocess
    client = REPO / "tools" / "sync-client" / "dig_sync_client.py"
    done = subprocess.run(
        [sys.executable, str(client), "--address", str(address),
         "--port", str(port), "--code", code.strip()],
        capture_output=True, text=True, timeout=300,
    )
    p.check(done.returncode == 0,
            f"the conformance client failed: {done.stdout[-400:]}{done.stderr[-200:]}")

    p.run("loadSync();", settle=1000)
    p.check(p.js("SYNC.devices.length") >= 1, "the paired device is not listed")
    p.run("syncRevoke(SYNC.devices[0].id);", settle=1200)
    p.run("loadSync();", settle=800)
    p.check(p.js("SYNC.devices.filter(function(d){return !d.revoked}).length") == 0,
            "revoking left the device paired")
    p.run("syncOff();", settle=1200)
    console_is_clean(p)


def step_28_text_size_and_names(p: Pass) -> None:
    p.at("28. Text size, and a name on everything a screen reader would read")
    room = p.js("window.innerWidth")
    p.run("setTextSize('xl');", settle=500)
    p.check(p.js("window.innerWidth") < room, "larger text did not scale the interface")
    p.run("setTextSize('m');", settle=500)
    p.same(p.js("window.innerWidth"), room, "going back to the default did not restore it")

    for view in ("home", "projects", "roadmap", "ideas", "library", "week",
                 "settings", "people", "notplanned"):
        p.run(f"go({view!r});", settle=320)
        unreachable = p.js(
            "Array.prototype.filter.call(document.querySelectorAll('#app [onclick]'),"
            "function(e){return ['BUTTON','INPUT','SELECT','TEXTAREA'].indexOf(e.tagName)<0"
            "&&!e.classList.contains('overlay')&&!e.hasAttribute('tabindex')}).length"
        )
        p.check(unreachable == 0, f"{view} has clickable things a keyboard cannot reach")
        unnamed = p.js(
            "Array.prototype.filter.call(document.querySelectorAll('#app [onclick]'),"
            "function(e){var t=(e.textContent||'').trim();"
            "return t.length<2&&!e.getAttribute('aria-label')"
            "&&!e.classList.contains('overlay')}).length"
        )
        p.check(unnamed == 0, f"{view} has an icon only control with no name")
    p.run("go('home');")
    console_is_clean(p)


def step_29_not_planned(p: Pass) -> None:
    p.at("29. Not planned")
    p.run("go('notplanned');", settle=450)
    p.same(p.js("S.view"), "notplanned", "the Not planned screen did not open")
    body = p.html()
    for expected in ("Boards", "Due dates", "Assignees", "Time tracking"):
        p.check(expected.lower() in body.lower(),
                f"Not planned does not mention {expected.lower()}")
    console_is_clean(p)


def step_30_the_sentence(p: Pass) -> None:
    p.at("30. The one sentence about the network, said the same way everywhere")
    sentence = "no outbound internet requests of any kind"
    p.run("S.obStep=1;go('setup');", settle=400)
    p.check(sentence in p.ui.html("body"), "the welcome does not say it")
    p.run("obFinish();go('settings');", settle=700)
    p.check(sentence in p.ui.html("body"), "Settings does not say it")
    p.run("openAbout();", settle=600)
    p.check(sentence in p.ui.html("body"), "About does not say it")
    p.run("closeOv();", settle=300)
    readme = (REPO / "README.md").read_text() if (REPO / "README.md").exists() else ""
    p.check(sentence in readme, "the README does not say it")
    console_is_clean(p)


# ------------------------------------------------------------------- the run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="a folder to be the fresh profile")
    ap.add_argument("--from-step", type=int, default=0)
    args = ap.parse_args()

    work = Path(args.data).resolve()
    shutil.rmtree(work, ignore_errors=True)
    (work / "home").mkdir(parents=True)
    (work / "files").mkdir()

    os.environ["XDG_DATA_HOME"] = str(work / "home")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --no-sandbox --in-process-gpu --disable-dev-shm-usage",
    )
    os.environ.setdefault("DIG_REDUCE_MOTION", "0")

    from tests.uiharness import UI, app

    app()
    sample = work / "files" / "brief.txt"
    sample.write_bytes(b"The brief, in one page.\n")

    ui = UI().start()
    p = Pass(ui)

    steps = [
        (1, lambda: step_1_fresh_start(p)),
        (2, lambda: step_2_capture_everything(p)),
        (3, lambda: step_3_sort_the_inbox(p)),
        (4, lambda: step_4_projects_and_stages(p)),
        (5, lambda: step_5_waiting(p)),
        (6, lambda: step_6_decisions(p)),
        (7, lambda: step_7_releases(p)),
        (8, lambda: step_8_people_links_files(p, sample)),
        (9, lambda: step_9_roadmap(p)),
        (10, lambda: step_10_ideas(p)),
        (11, lambda: step_11_settings_shape(p)),
        (12, lambda: step_12_export_import_recovery(p, work)),
        (13, lambda: step_13_themes(p)),
        (14, lambda: step_14_pdfs(p, work)),
        (15, lambda: step_15_geometry(p)),
        (16, lambda: step_16_reduced_motion(p)),
        (17, lambda: step_17_onboarding_again(p)),
        (18, lambda: step_18_files_every_way(p, work / "files")),
        (19, lambda: step_19_groups_and_log(p, work)),
        (20, lambda: step_20_duplicate_and_templates(p)),
        (21, lambda: step_21_recently_deleted(p)),
        (22, lambda: step_22_command_line(p)),
        (23, lambda: step_23_quiet(p)),
        (24, lambda: step_24_people_screen(p)),
        (25, lambda: step_25_backup_and_restore(p, work)),
        (26, lambda: step_26_csv(p, work)),
        (27, lambda: step_27_sync(p, work)),
        (28, lambda: step_28_text_size_and_names(p)),
        (29, lambda: step_29_not_planned(p)),
        (30, lambda: step_30_the_sentence(p)),
    ]

    for number, run_step in steps:
        if number < args.from_step:
            continue
        try:
            run_step()
        except Exception as exc:  # a step that falls over is itself a defect
            p.found.append(f"{p.step}: the step itself fell over: {exc!r}")
            print(f"    DEFECT  the step fell over: {exc!r}", flush=True)

    ui.close()

    print(f"\n{p.checks} things checked")
    if p.found:
        print(f"{len(p.found)} defects:\n")
        for one in p.found:
            print(f"  - {one}")
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
