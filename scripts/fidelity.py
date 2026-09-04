#!/usr/bin/env python3
"""Compare the app against the prototype, screen by screen, in both themes.

The prototype is the product's interface, so the only honest test of the port is
to put the two side by side on identical data with the clock frozen to the same
instant, and look at what differs. This does that twice over: pixel by pixel,
and in the markup.

    python scripts/fidelity.py --seed seed.json --out shots --data /tmp/run

Anything the pixel diff reports is drift. Anything the markup diff reports is
either drift or one of the bridge seams listed in SEAMS below.

Both sides are given the same locally bundled fonts, the same frozen clock, no
animation, no caret, and the window focus in turn, because otherwise the
comparison measures the font, the stopwatch, or which window happened to be
active rather than the port.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

PROTOTYPE = REPO / "docs" / "handoff-v2" / "design" / "dig-prototype.html"
FONTS = REPO / "dig" / "ui" / "fonts"
FROZEN = "2026-09-04T14:00:00"
RESURF = "e3"
SIZE = (1280, 840)

# One step of one channel is not a difference anyone can see, and it is what a
# compositor gives you when the same picture is put together by a slightly
# different route. The sidebar footer wrapping to a second line moves the whole
# dimmed layer behind a dialog by exactly that much and nothing else.
TOLERANCE = 1

LOCAL_FONTS = "".join(
    f"@font-face{{font-family:{family!r};src:url('file://{FONTS}/{file}.woff2')"
    f" format('woff2');font-weight:{weight};font-style:normal;font-display:block}}"
    for family, file, weight in (
        ("Geist", "Geist-Regular", 400),
        ("Geist", "Geist-Medium", 500),
        ("Geist", "Geist-SemiBold", 600),
        ("Geist", "Geist-Bold", 700),
        ("Geist Mono", "GeistMono-Regular", 400),
        ("Geist Mono", "GeistMono-Medium", 500),
    )
)

PROTO_PREP = f"""
document.querySelector('.proto-bar').remove();
document.querySelectorAll('link[href*="fonts.googleapis"],link[href*="gstatic"]')
  .forEach(function(l){{l.remove()}});
document.body.style.padding='0';
document.body.style.display='block';
var st=document.createElement('style');
st.textContent={LOCAL_FONTS!r}+'.proto{{max-width:none}}.app{{height:840px;border:none;border-radius:0;box-shadow:none}}';
document.head.appendChild(st);
NOW=new Date('{FROZEN}');
S.resurfId={RESURF!r};
document.fonts.ready.then(function(){{window.__fontsReady=1}});
1
"""

APP_PREP = f"""
Object.defineProperty(window,'NOW',{{get:function(){{return new Date('{FROZEN}')}},configurable:true}});
S.resurfId={RESURF!r};
S.setupWork={{apps:false,clients:true,content:false,personal:true,programs:false}};
document.fonts.ready.then(function(){{window.__fontsReady=1}});
1
"""

# Both palettes were moved to meet WCAG AA (see HANDOFF decision 19): the light
# one in seven places, the dark one only in the third rank of text. For the
# comparison the prototype's original values go back, so what is measured is the
# port rather than that one deliberate decision.
PROTOTYPE_PALETTE = (
    "var s=document.createElement('style');"
    "s.textContent=':root[data-theme=\"light\"]{--ink-3:#8593A6;--teal:#0BA39E;"
    "--green:#1E9E5A;--amber:#D9890B;--coral:#E4573F;--rose:#D14A7A;--red:#D64545}"
    ":root[data-theme=\"dark\"]{--ink-3:#5E6C82}';"
    "document.head.appendChild(s);1"
)

STILL = (
    "var s=document.createElement('style');"
    "s.textContent='*{animation:none!important;transition:none!important;"
    "caret-color:transparent!important}';"
    "document.head.appendChild(s);1"
)

REFOCUS = (
    "var f=document.querySelector('#cap-in')||document.querySelector('#pal-in')"
    "||document.querySelector('#dlg-body input[type=text],#dlg-body textarea,"
    "#dlg-body select');if(f)f.focus();1"
)

# Screens the addendum deliberately changed. They are compared, and what differs
# is expected to be exactly the addition.
CHANGED_BY_THE_ADDENDUM = {
    "setup": "replaced by the five step onboarding",
    "home": "a soft line about projects that have gone quiet, and the Start here card",
    "week": "Your week became Your review, with a period and a scope",
    "week-private": "the same",
    "settings": "sync, templates, recently deleted, people, text size, backups",
    "project-work": "a More button, and Add files instead of the stand-in dialog",
    "project-work-wait": "the same",
    "project-empty": "the same",
    "project-rec": "the log",
    "project-rec-empty": "the log",
    "library": "files listed alongside links and notes, and an Add files button",
    "library-unsorted": "the same",
    "dlg-library-move": "the library underneath it",
    "project-rm": "a More button in the header",
    "project-rm-empty": "the same",
    "dlg-decision": "the record tab underneath it, which now carries the log",
    "dlg-wait": "the same",
    "dlg-person": "the same",
    "dlg-release": "the same",
    "dlg-link": "the same",
    "dlg-share-project": "the same",
    "dlg-advance": "the work tab underneath it",
    "dlg-advance-clean": "the same",
    "projects": "one more way to sort the list, for what has gone quiet",
    "projects-waiting": "the same",
    "projects-finished": "the same",
    "projects-parked": "the same",
    "projects-group": "the same",
    "dlg-new": "the same",
    "dlg-share-projects": "the same",
    "dlg-keys": "Your week became Your review",
}

# Differences that are not the addendum and are not drift either. Each one was
# taken apart before it was written down here: the elements are in the same
# places, to the pixel, with the same computed styles, and the markup is
# identical. What differs is how the picture was put together underneath.
EXPLAINED_OTHERWISE = {
    "dlg-capture": "the dim over a light screen, rasterised a shade differently",
    "dlg-capture-empty": "the same",
    "dlg-find": "the same",
    "dlg-idea": "the same",
    "dlg-start-idea": "the same",
    "dlg-inbox-sort": "the same",
    "dlg-share-roadmap": "the same",
}

# Every screen carries the sidebar, and the sidebar differs on purpose: it says
# Your review where it said Your week, and its footer is allowed a second line
# rather than breaking "Shortcuts" from its "?" and growing a scrollbar, which
# is what the prototype does with real Geist. So no screen can be pixel
# identical including it. The comparison measures the rest of the window
# separately for that reason.
SIDEBAR_WIDTH = 232

SCREENS = [
    ("home", "S.view='home';S.filterGroup='all'"),
    ("projects", "S.view='projects';S.sort='activity';S.filterGroup='all'"),
    ("projects-waiting", "S.view='projects';S.sort='waiting'"),
    ("projects-finished", "S.view='projects';S.sort='done'"),
    ("projects-parked", "S.view='projects';S.sort='parked'"),
    ("projects-group", "S.view='projects';S.sort='activity';S.filterGroup='work'"),
    ("roadmap", "S.view='roadmap';S.filterGroup='all'"),
    ("roadmap-private", "S.view='roadmap';S.filterGroup='home'"),
    ("project-work", "S.view='project';S.projectId='wr';S.ptab='work';S.filterGroup='all'"),
    ("project-work-wait", "S.view='project';S.projectId='nco';S.ptab='work'"),
    ("project-rm", "S.view='project';S.projectId='wr';S.ptab='rm'"),
    ("project-rec", "S.view='project';S.projectId='wr';S.ptab='rec'"),
    ("project-empty", "S.view='project';S.projectId='kr';S.ptab='work'"),
    ("project-rm-empty", "S.view='project';S.projectId='kr';S.ptab='rm'"),
    ("project-rec-empty", "S.view='project';S.projectId='kr';S.ptab='rec'"),
    ("week", "S.view='week';S.publicOnly=true"),
    ("week-private", "S.view='week';S.publicOnly=false"),
    ("ideas", "S.view='ideas';S.filterGroup='all';S.ideaSort='oldest'"),
    ("ideas-newest", "S.view='ideas';S.ideaSort='newest'"),
    ("library", "S.view='library';S.libFilter='all'"),
    ("library-unsorted", "S.view='library';S.libFilter='unsorted'"),
    ("settings", "S.view='settings'"),
]

DIALOGS = [
    ("dlg-capture", "S.view='home';render();openCap();"
     "document.getElementById('cap-in').value='Old gallery page still 404s';"
     "S.capProject='wr';document.getElementById('cap-p').value='wr';capDetect()"),
    ("dlg-capture-empty", "S.view='home';render();openCap()"),
    ("dlg-find", "S.view='home';render();openPal();"
     "document.getElementById('pal-in').value='we';palFilter('we')"),
    ("dlg-advance", "S.view='project';S.projectId='wr';S.ptab='work';render();openAdvance('wr')"),
    ("dlg-advance-clean", "S.view='project';S.projectId='qr';S.ptab='work';render();openAdvance('qr')"),
    ("dlg-decision", "S.view='project';S.projectId='wr';S.ptab='rec';render();openDec('wr')"),
    ("dlg-wait", "S.view='project';S.projectId='wr';render();openWait('wr')"),
    ("dlg-new", "S.view='projects';render();openNew('work')"),
    ("dlg-idea", "S.view='ideas';render();openIdea('e3')"),
    ("dlg-start-idea", "S.view='ideas';render();startIdea('e3')"),
    ("dlg-inbox-sort", "S.view='home';render();openSort('e5')"),
    ("dlg-library-move", "S.view='library';render();openSortLib('e7')"),
    ("dlg-share-project", "S.view='project';S.projectId='wr';render();openShare('wr')"),
    ("dlg-share-projects", "S.view='projects';render();openShare(null)"),
    ("dlg-share-roadmap", "S.view='roadmap';render();openShare('rm')"),
    ("dlg-keys", "S.view='home';render();openKeys()"),
    ("dlg-person", "S.view='project';S.projectId='wr';render();addPerson('wr')"),
    ("dlg-release", "S.view='project';S.projectId='wr';render();addRelease('wr')"),
    ("dlg-link", "S.view='project';S.projectId='wr';render();addLink('wr')"),
]

# Everything the port is allowed to differ by: the bridge seams SPEC section 1
# asks for. Each rule rewrites the app's markup back to the prototype's.
SEAMS = [
    (r'<a onclick="openLink\(&quot;[^"]*?&quot;\)">', "<a>"),
    (r'<div class="file" onclick="openStored\(&quot;[^"]*?&quot;\)">', '<div class="file">'),
    (r'<div class="row click" onclick="openLink\(&quot;[^"]*?&quot;\)">', '<div class="row">'),
    (r'<div class="row click" onclick="openStored\(&quot;[^"]*?&quot;\)">', '<div class="row">'),
    (r'<div class="row" onclick="openStored\(&quot;[^"]*?&quot;\)">', '<div class="row">'),
    (r"event\.stopPropagation\(\);openSortLib", "openSortLib"),
    (r";scheduleSave\(\)", ""),
    (r'onclick="openDataFolder\(\)"', "onclick=\"toast('Opens the folder in the real app')\""),
    (r'onclick="importData\(\)"', "onclick=\"toast('Import opens a file picker in the real app')\""),
    (r'onclick="openAbout\(\)"', "onclick=\"toast('About dialog lives here in the real app')\""),
    (r'onclick="savePdfWeek\(\)"', "onclick=\"toast('In the real app this saves a PDF.')\""),
    (r'onclick="doShare\([^"]*?\)"',
     "onclick=\"closeOv();toast('In the real app this saves the file.')\""),
    (r'onclick="finishSetup\(\)"',
     "onclick=\"go('home');toast('You\\'re set. Press Ctrl K any time to add something.')\""),
]

# The addendum asked for things that show up on every screen rather than on one.
# Leaving them in would drown the comparison, so each side is brought to the
# same place first and what is left over is drift. Every rule here names the
# part of the addendum that asked for it.
ADDENDUM_APP = [
    # Part 7, text size and accessibility: the keyboard and screen reader
    # attributes are additions to the prototype's markup, not changes to it.
    (r'\s(?:tabindex="[^"]*"|role="[^"]*"|aria-[a-z-]+="[^"]*")', ""),
    # Part 6, files: anywhere can be dropped on, so the veil sits in the shell.
    (r'<div class="drop-veil" id="drop-veil">.*?</div></div>', ""),
    # Part 7, group pages: a group heading on the Projects list opens the group.
    (r'<span class="n" style="cursor:pointer" onclick="openG\(\'[^\']*\'\)">',
     '<span class="n">'),
    # Part 7, duplicate, template, not planned and delete live behind More.
    (r'<button class="btn" onclick="openProjectMore\(\'[^\']*\'\)">More</button>', ""),
    # Part 1, the Start here card ticks itself off as the work gets done.
    (r";tickStartHere\(&#39;[a-zA-Z]+&#39;\)", ""),
    (r";tickStartHere\('[a-zA-Z]+'\)", ""),
    # Part 7, the log on the Record tab, which also shows under six dialogs.
    (r'<div class="sec-t" style="margin-top:22px"><h2>Log</h2>.*?'
     r'(?=<div class="sec-t" style="margin-top:22px"><h2>Past waits</h2>)', ""),
    # Part 6, files are first class, so the stand-in became the real thing.
    (r'<a class="rt" onclick="addFiles\(\'([^\']*)\',\'\'\)">\+ add files</a>',
     '<a class="rt" onclick="addFile(\'\\1\')">+ add</a>'),
    (r'<button class="btn" onclick="addFiles\(\'\',\'\'\)">Add files</button>', ""),
    (r" Drop them anywhere on this page\.| Drop a file anywhere on this page\.", ""),
    (r'<div class="filerow" onclick="openFile\(\'[^\']*\'\)">'
     r'<span class="ic ([A-Z]+)"[^>]*>\1</span><div class="grow">'
     r'<div class="n">([^<]*)</div><div class="m">[^<]*</div></div></div>',
     r'<div class="file"><span class="ic \1">\1</span><div>\2<div class="m">v1</div>'
     r'</div></div>'),
]

ADDENDUM_PROTO = [
    # Part 7, group pages: a group in the sidebar used to filter the list.
    # Everything is not a real group, so it still only filters.
    # A chip on the Ideas list still filters; only the sidebar opens a group.
    ("<a class=\"([^\"]*)\" onclick=\"setGroup\\('(?!all')([a-z0-9]+)'\\)",
     "<a class=\"\\1\" onclick=\"openG('\\2')"),
    ("onclick=\"S\\.filterGroup='([a-z0-9]+)';go\\('projects'\\)",
     "onclick=\"openG('\\1')"),
    # Part 7, reviews with periods: Your week became Your review.
    (r"Your week", "Your review"),
    # Part 7, quiet projects: one more way to sort the list.
    (r'<option value="parked"([^>]*)>Only parked</option>',
     r'<option value="parked"\1>Only parked</option>'
     r'<option value="quiet">Only gone quiet</option>'),
]


def normalize(markup: str) -> str:
    for pattern, replacement in ADDENDUM_APP + SEAMS:
        markup = re.sub(pattern, replacement, markup, flags=re.S)
    return markup


def forward(markup: str) -> str:
    """The prototype's markup, brought forward to what the addendum asked for."""
    for pattern, replacement in ADDENDUM_PROTO:
        markup = re.sub(pattern, replacement, markup)
    return markup


class Page:
    """One loaded document we can drive and photograph."""

    def __init__(self, view, page) -> None:
        self.view, self.page = view, page

    def js(self, code: str):
        from PySide6.QtCore import QEventLoop, QTimer

        box, loop = {}, QEventLoop()
        QTimer.singleShot(15000, loop.quit)
        self.page.runJavaScript(code, lambda v: (box.setdefault("v", v), loop.quit()))
        loop.exec()
        return box.get("v")

    def settle(self, ms: int = 420) -> None:
        from PySide6.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def await_fonts(self) -> None:
        for _ in range(20):
            self.settle(150)
            if self.js("window.__fontsReady||0"):
                return

    def focus(self) -> None:
        self.view.activateWindow()
        self.view.raise_()
        self.view.setFocus()
        self.settle(120)
        self.js(REFOCUS)
        self.settle(140)

    def shoot(self, path: Path):
        image = self.view.grab().toImage()
        image.save(str(path))
        return image

    def markup(self) -> str:
        return self.js("document.getElementById('app').innerHTML") or ""


def pixel_diff(a, b) -> tuple[float, int, tuple]:
    """Share of pixels that differ, how many of them outside the sidebar, and
    the box those sit in.

    The sidebar is counted but not located, because Your week became Your
    review and that alone puts a difference on all eighty two screens. What
    matters is the rest of the window: a change the addendum asked for shows up
    in one region, and drift shows up somewhere it has no business being.
    """
    if a.size() != b.size():
        return 100.0, -1, ()
    a = a.convertToFormat(a.Format.Format_RGB32)
    b = b.convertToFormat(b.Format.Format_RGB32)
    width, height = a.width(), a.height()
    differing = 0
    body = 0
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        row_a = bytes(a.constScanLine(y))[: width * 4]
        row_b = bytes(b.constScanLine(y))[: width * 4]
        if row_a == row_b:
            continue
        for x in range(0, width * 4, 4):
            if row_a[x : x + 3] == row_b[x : x + 3]:
                continue
            if max(abs(row_a[x + n] - row_b[x + n]) for n in range(3)) <= TOLERANCE:
                continue
            differing += 1
            column = x // 4
            if column >= SIDEBAR_WIDTH:
                body += 1
                left = min(left, column)
                right = max(right, column)
                top = min(top, y)
                bottom = max(bottom, y)
    box = (left, top, right, bottom) if body else ()
    return (differing * 100.0 / (width * height)), body, box


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True, help="the prototype's data as a v2 document")
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--report", default="")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    os.environ["XDG_DATA_HOME"] = str(Path(args.data).resolve())
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --no-sandbox --in-process-gpu --disable-dev-shm-usage",
    )

    from PySide6.QtCore import QUrl
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    from dig import paths
    from dig.bridge import Bridge
    from dig.store import Store
    from dig.window import LocalOnlyInterceptor, MainWindow

    out = Path(args.out)
    for sub in ("proto", "app", "markup"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    app = QApplication([])

    # The prototype, in its own window, held to the same no network rule.
    proto_profile = QWebEngineProfile("fidelity-proto")
    proto_blocker = LocalOnlyInterceptor()
    proto_profile.setUrlRequestInterceptor(proto_blocker)
    proto_view = QWebEngineView()
    proto_page = QWebEnginePage(proto_profile, proto_view)
    proto_view.setPage(proto_page)
    proto_page.settings().setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
    )
    proto_view.resize(*SIZE)
    proto_view.show()
    proto_view.setUrl(QUrl.fromLocalFile(str(PROTOTYPE)))
    proto = Page(proto_view, proto_page)
    proto.settle(2500)
    proto.js(PROTO_PREP)
    proto.js(STILL)
    proto.await_fonts()
    proto.js("render();1")
    proto.settle(400)

    # The app, in its real window, against the same data.
    paths.ensure_data_dirs()
    store = Store(paths.db_path(), paths.history_dir())
    store.save_state(json.loads(Path(args.seed).read_text(encoding="utf-8")))
    result = store.load()
    bridge = Bridge(store)
    window = MainWindow(bridge)
    bridge.attach_window(window)
    bridge.prime(result)
    window.resize(*SIZE)
    window.load_ui()
    window.show()
    real = Page(window, window.page)
    real.settle(2500)
    real.js(APP_PREP)
    real.js(STILL)
    real.js(PROTOTYPE_PALETTE)
    real.await_fonts()
    real.js("render();1")
    real.settle(400)

    console: list[str] = []
    original = window.page.javaScriptConsoleMessage
    window.page.javaScriptConsoleMessage = lambda lvl, msg, line, src: (
        console.append(f"{msg} ({Path(src).name}:{line})"),
        original(lvl, msg, line, src),
    )

    cases = [(n, s, False) for n, s in SCREENS] + [(n, s, True) for n, s in DIALOGS]
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c[0] in wanted]

    findings = []
    for theme in ("light", "dark"):
        for name, script, is_dialog in cases:
            label = f"{name}-{theme}"
            prelude = f"closeOv();S.theme={theme!r};S.resurfId={RESURF!r};"
            body = script if is_dialog else f"{script};render()"
            for page in (proto, real):
                page.focus()
                page.js(f"(function(){{{prelude}{body};return 1}})()")
                page.settle(520)
            for page in (proto, real):
                page.focus()

            proto_image = proto.shoot(out / "proto" / f"{label}.png")
            app_image = real.shoot(out / "app" / f"{label}.png")
            share, count, box = pixel_diff(proto_image, app_image)

            proto_markup = forward(proto.markup())
            app_markup = normalize(real.markup())
            same_markup = proto_markup == app_markup
            if not same_markup:
                (out / "markup" / f"{label}.proto.html").write_text(proto_markup)
                (out / "markup" / f"{label}.app.html").write_text(app_markup)

            findings.append(
                {
                    "case": label,
                    "pixel_pct": round(share, 4),
                    "pixels": count,
                    "box": list(box),
                    "markup_identical": same_markup,
                }
            )
            note = CHANGED_BY_THE_ADDENDUM.get(name, "") or \
                EXPLAINED_OTHERWISE.get(name, "")
            if count == 0 and same_markup:
                flag = ""
            elif note:
                flag = f"   expected: {note}"
            else:
                flag = "   <-- LOOK"
            where = (
                f"  {count} outside the sidebar, in "
                f"{box[0]},{box[1]} to {box[2]},{box[3]}"
                if box else "  none outside the sidebar"
            )
            print(
                f"{label:36s} pixels {share:7.4f}%  markup "
                f"{'same' if same_markup else 'DIFFERS'}{flag}{where}",
                flush=True,
            )

    clean = [f for f in findings if f["pixels"] == 0 and f["markup_identical"]]
    drifted = [
        f for f in findings
        if not (f["pixels"] == 0 and f["markup_identical"])
        and f["case"].rsplit("-", 1)[0] not in CHANGED_BY_THE_ADDENDUM
        and f["case"].rsplit("-", 1)[0] not in EXPLAINED_OTHERWISE
    ]
    print(f"\n{len(clean)} of {len(findings)} cases identical to the prototype"
          " outside the sidebar")
    addendum = [
        f for f in findings
        if f["case"].rsplit("-", 1)[0] in CHANGED_BY_THE_ADDENDUM and f not in clean
    ]
    print(f"{len(addendum)} differ where the addendum changed them")
    print(f"{len(findings) - len(clean) - len(drifted) - len(addendum)}"
          " differ for a reason that is written down and was checked")
    print(f"{len(drifted)} differ with no reason to: " + (", ".join(f["case"] for f in drifted) or "none"))
    if console:
        print("console messages:", console)
    print("blocked requests, app:", window.interceptor.blocked)
    print("blocked requests, prototype:", proto_blocker.blocked)

    if args.report:
        Path(args.report).write_text(
            json.dumps(
                {
                    "findings": findings,
                    "console": console,
                    "blocked": list(window.interceptor.blocked) + list(proto_blocker.blocked),
                },
                indent=1,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
