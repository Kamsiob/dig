"""Every defect the review turned up, kept fixed.

One test per confirmed finding. Each one fails on the code as it was.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dig.bridge import _inside_digs_own, _looks_like_dig, safe_id
from dig.store import Store
from tests.uiharness import pump


def setup_done(ui, kinds=("apps",)) -> None:
    picks = "".join(f"S.setupWork.{k}=true;" for k in kinds)
    ui.run(f"S.org='Example Studio';{picks}render();finishSetup();")


# ------------------------------------------- a project with no type to move on


def test_new_project_is_refused_when_there_are_no_types(ui) -> None:
    """The very first thing a new person can click used to brick the app."""
    assert ui.js("S.types.length") == 0
    ui.run("S.view='projects';render();openNew('');")
    assert ui.js("!!document.querySelector('#ov-dlg.open')") is False
    assert any("project type in Settings" in t for t in ui.toasts())
    assert ui.js("S.projects.length") == 0
    assert ui.console == []


def test_a_project_cannot_be_created_without_a_type(ui) -> None:
    setup_done(ui)
    ui.run("openNew('apps');document.getElementById('np-n').value='Would be orphaned';")
    ui.run("S.types=[];document.getElementById('np-t').innerHTML='';createP(null);")
    assert ui.js("S.projects.length") == 0
    assert any("project type in Settings" in t for t in ui.toasts())


def test_a_project_whose_type_went_missing_still_renders(ui) -> None:
    setup_done(ui)
    ui.run("openNew('apps');document.getElementById('np-n').value='Orphan';createP(null);")
    assert ui.js("S.projects.length") == 1
    ui.run("S.projects[0].type='gone-for-good';go('home');")
    assert "Orphan" in ui.html() or ui.js("S.view") == "home"
    ui.run("go('projects');")
    assert "Orphan" in ui.html()
    ui.run("go('roadmap');")
    assert ui.js("S.view") == "roadmap"
    assert ui.console == [], "no view may throw on a project with an unknown type"


def test_the_last_project_type_cannot_be_removed(ui) -> None:
    setup_done(ui)
    ui.run("delType(S.types[0].id);")
    assert ui.js("S.types.length") == 1
    assert any("at least one project type" in t for t in ui.toasts())


# ------------------------------------------------------- undoing a stage move


def test_undo_puts_back_exactly_what_the_move_changed(ui) -> None:
    setup_done(ui)
    ui.run("openNew('apps');document.getElementById('np-n').value='Alpha';"
           "document.getElementById('np-x').value='First step';createP(null);")
    pid = ui.js("S.projects[0].id")
    ui.run(f"S.activity.unshift({{group:'apps',pid:'{pid}',text:'something else entirely',"
           f"at:NOW,kind:'decision'}});")
    before = ui.js("JSON.parse(JSON.stringify({stage:S.projects[0].stage,"
                   "next:S.projects[0].next,when:S.projects[0].when,acts:S.activity.length}))")

    ui.run(f"S.view='project';S.projectId='{pid}';render();openAdvance('{pid}');"
           "document.getElementById('adv-x').value='Second step';"
           f"doAdvance('{pid}');")
    assert ui.js("S.projects[0].stage") == before["stage"] + 1
    assert ui.js("S.projects[0].next") == "Second step"

    ui.run(f"undoAdvance('{pid}');")
    after = ui.js("JSON.parse(JSON.stringify({stage:S.projects[0].stage,"
                  "next:S.projects[0].next,when:S.projects[0].when,acts:S.activity.length}))")
    assert after == before, "the move is put back, and nothing else"
    assert ui.js("S.activity[0].text") == "something else entirely", (
        "undo removed its own log entry, not whichever was newest"
    )


def test_undo_of_a_finishing_move_puts_the_horizon_back(ui) -> None:
    setup_done(ui)
    ui.run("openNew('apps');document.getElementById('np-n').value='Beta';createP(null);")
    pid = ui.js("S.projects[0].id")
    last = ui.js("T(S.projects[0].type).stages.length") - 1
    ui.run(f"S.projects[0].stage={last - 1};S.projects[0].when='now';render();")
    ui.run(f"openAdvance('{pid}');doAdvance('{pid}');")
    assert ui.js("S.projects[0].when") == "done"
    assert ui.js("S.projects[0].quiet") is True

    ui.run(f"undoAdvance('{pid}');")
    assert ui.js("S.projects[0].when") == "now", "it comes back onto the roadmap"
    assert ui.js("S.projects[0].quiet") is False


def test_jumping_to_a_last_stage_also_sets_the_horizon(ui) -> None:
    setup_done(ui)
    ui.run("openNew('apps');document.getElementById('np-n').value='Gamma';createP(null);")
    pid = ui.js("S.projects[0].id")
    last = ui.js("T(S.projects[0].type).stages.length") - 1
    ui.run(f"jumpStage('{pid}',{last});")
    assert ui.js("S.projects[0].quiet") is True
    assert ui.js("S.projects[0].when") == "done"


# ------------------------------------------------------------ what reaches disk


def test_the_last_thing_typed_before_quitting_is_written(ui) -> None:
    """The window used to go before the interface handed its change over."""
    setup_done(ui)
    ui.run("S.org='Before';flushSave();", settle=400)
    ui.bridge.flush()
    assert ui.store.load().state["org"] == "Before"

    ui.raw("S.org='Typed a moment before quitting';scheduleSave();1")
    assert ui.raw("!!saveTimer") is True, "still inside the debounce"

    window = ui.window
    window.close()
    for _ in range(30):
        pump(30)
        if not window.isVisible():
            break
    ui.window = None
    assert ui.store.load().state["org"] == "Typed a moment before quitting"


def test_a_resize_on_its_own_is_remembered(ui) -> None:
    setup_done(ui)
    ui.run("flushSave();", settle=400)
    ui.bridge.flush()

    ui.window.resize(1180, 760)
    pump(900)  # past the geometry timer
    saved = (ui.store.load().state.get("ui") or {}).get("window") or {}
    assert saved.get("w") == 1180 and saved.get("h") == 760


def test_a_save_that_fails_is_said_out_loud(ui) -> None:
    setup_done(ui)
    ui.run("flushSave();", settle=300)
    ui.bridge.flush()

    ui.bridge._store.read_only = True  # the store refuses, as it would for a newer file
    ui.run("S.org='Will not land';scheduleSave();", settle=500)
    ui.bridge.flush()
    pump(200)
    assert any("not able to write" in t for t in ui.toasts())
    assert ui.bridge.has_pending(), "the change is held, not thrown away"


# ------------------------------------------------------------- a newer format


def test_a_newer_format_file_is_explained_and_left_alone(home: Path, launch) -> None:
    from dig import paths

    paths.ensure_data_dirs()
    store = Store(paths.db_path(), paths.history_dir())
    store.save_state({"org": "Example Studio", "setupDone": True, "projects": []})
    store.close()
    conn = sqlite3.connect(str(paths.db_path()))
    try:
        conn.execute("UPDATE meta SET value='99' WHERE key='schema_version'")
        conn.commit()
    finally:
        conn.close()
    before = paths.db_path().read_bytes()

    ui = launch()
    assert any("newer Dig" in t for t in ui.toasts()), "the person is told, not shown a traceback"
    ui.run("S.org='trying to write';scheduleSave();", settle=500)
    ui.bridge.flush()
    assert paths.db_path().read_bytes() == before, "and nothing was written over it"


# -------------------------------------------------------------------- imports


def test_a_document_that_is_not_digs_is_refused() -> None:
    assert _looks_like_dig({"projects": [{"id": "p1"}]}) is True
    assert _looks_like_dig({"nope": 1}) is False
    assert _looks_like_dig({"projects": "not a list"}) is False
    assert _looks_like_dig({"projects": [{"no": "id"}]}) is False
    assert _looks_like_dig({"projects": [], "groups": {"not": "a list"}}) is False
    assert _looks_like_dig([1, 2, 3]) is False


def test_a_ragged_import_does_not_take_the_app_down(ui, tmp_path: Path) -> None:
    setup_done(ui)
    ragged = tmp_path / "ragged.json"
    ragged.write_text(json.dumps({
        "org": "Somewhere else", "setupDone": True,
        "projects": [{"id": "p1", "name": "No type at all", "group": "gone", "type": "gone"}],
        "types": [], "groups": [], "ideas": [], "inbox": [], "library": [], "activity": [],
    }))
    ui.queue_open(str(ragged))
    ui.run("importData();", settle=700)
    ui.run("doImport();", settle=700)

    assert ui.js("S.projects.length") == 1
    for view in ("home", "projects", "roadmap", "week"):
        ui.run(f"go({view!r});")
    assert ui.console == [], "no view throws on an imported project with no type"


# ------------------------------------------------------------------ the paths


def test_an_id_can_never_climb_out_of_its_folder() -> None:
    assert safe_id("../../etc") == "etc"
    assert safe_id("/etc/passwd") == "etcpasswd"
    assert safe_id("") == "loose"
    assert safe_id("good-id_1") == "good-id_1"
    assert "/" not in safe_id("a/b/c") and ".." not in safe_id("..")


def test_open_path_only_opens_digs_own_files(home: Path, tmp_path: Path) -> None:
    from dig import paths

    paths.ensure_data_dirs()
    mine = paths.blobs_dir() / "ab" / "cd" / "abcd"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text("a file Dig is holding")
    theirs = tmp_path / "private.txt"
    theirs.write_text("nothing to do with Dig")

    assert _inside_digs_own(mine.resolve()) is True
    assert _inside_digs_own(theirs.resolve()) is False


# ------------------------------------------------------------------- exports


def test_an_export_says_when_a_project_was_left_out(ui) -> None:
    setup_done(ui, ("apps", "clients"))
    ui.run("openNew('apps');document.getElementById('np-n').value='Shareable';createP(null);")
    ui.run("openNew('apps');document.getElementById('np-n').value='Held back';createP(null);"
           "S.projects[0].pub=false;")
    footer = ui.js("omitted()")
    assert "1 private group" in footer, "the Clients group is private"
    assert "1 private project" in footer, "and one project was marked not shareable"

    ui.run("S.groups.forEach(function(g){g.priv=false});S.projects.forEach(function(p){p.pub=true});")
    assert ui.js("omitted()") == "Nothing was left out"


# ------------------------------------------------------------ reduced motion


def test_reduced_motion_reaches_pseudo_elements() -> None:
    css = (Path(__file__).resolve().parent.parent / "dig" / "ui" / "app.css").read_text()
    for rule in (
        '@media (prefers-reduced-motion: reduce){*,*::before,*::after{',
        ':root[data-motion="reduce"] *::before',
        ':root[data-motion="reduce"] *::after',
    ):
        assert rule in css, rule


def test_reduce_motion_is_re_read_when_the_window_is_come_back_to(ui, monkeypatch) -> None:
    setup_done(ui)
    assert ui.js("document.documentElement.getAttribute('data-motion')") == "full"

    import dig.bridge as bridge_module

    monkeypatch.setattr(bridge_module, "read_reduce_motion", lambda: True)
    ui.bridge.recheck_motion()
    pump(250)
    assert ui.js("document.documentElement.getAttribute('data-motion')") == "reduce"


# ------------------------------------------------------------------ the copy


def test_the_about_dialog_shows_the_address_it_opens(ui) -> None:
    setup_done(ui)
    links = ui.js("ABOUT_LINKS")
    telegram = next(link for link in links if link[0] == "Telegram")
    assert telegram[2] in telegram[1], "the line shown is the address that opens"


def test_no_internal_sentinel_ever_reaches_the_person() -> None:
    source = (Path(__file__).resolve().parent.parent / "dig" / "bridge.py").read_text()
    assert '"reason": "render"' not in source
    assert '"reason": "nothing came back"' not in source
    assert '"reason": str(exc)' not in source, "an exception is not a sentence"
