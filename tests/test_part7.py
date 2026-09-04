"""Group pages, the log, reviews, templates, backups, and the rest of Part 7."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from dig import csvin
from dig.backup import read_manifest, referenced_blobs, scheduled_is_due, trim_scheduled


def started(ui, examples=True, kinds=("apps",)) -> None:
    picks = "".join(f"S.setupWork.{k}=true;" for k in kinds)
    ui.run(f"S.org='Example Studio';S.you='Alex';{picks}obGo(4);"
           f"S.obExamples={'true' if examples else 'false'};obFinish();", settle=600)


def project_named(ui, name: str) -> str:
    return ui.js(f"(S.projects.find(function(p){{return p.name==={name!r}}})||{{}}).id")


# ------------------------------------------------------------ group pages 7.1


def test_a_group_has_its_own_page(ui) -> None:
    started(ui)
    gid = ui.js("S.groups[0].id")
    ui.run(f"openG('{gid}');")
    assert ui.js("S.view") == "group"
    body = ui.html()
    assert "Standing" in body and "Roadmap" in body
    assert "Decisions" in body and "Log" in body and "Files" in body
    assert "Website refresh" in body


def test_the_group_description_saves_as_you_type(ui) -> None:
    started(ui)
    gid = ui.js("S.groups[0].id")
    ui.run(f"openG('{gid}');G('{gid}').description='Everything we build and release.';scheduleSave();")
    assert ui.on_disk()["groups"][0]["description"] == "Everything we build and release."


def test_a_group_can_be_edited_from_its_page(ui) -> None:
    started(ui)
    gid = ui.js("S.groups[0].id")
    ui.run(f"openG('{gid}');editGroup('{gid}');")
    ui.run("document.getElementById('eg-n').value='Products';"
           "document.getElementById('eg-p').value='1';saveGroup(" + json.dumps(gid) + ");")
    group = ui.js("S.groups[0]")
    assert group["name"] == "Products" and group["priv"] is True
    assert all(not p["pub"] for p in ui.js("S.projects") if p["group"] == gid), (
        "making a group private makes its projects unshareable"
    )


def test_a_group_decision_shares_the_numbering(ui) -> None:
    started(ui)
    gid = ui.js("S.groups[0].id")
    highest = ui.js("nextDecNo()")
    ui.run(f"openGroupDec('{gid}');document.getElementById('gdc-t').value="
           "'Every project in here uses the same content structure.';"
           f"recordGroupDecision('{gid}');")
    assert ui.js("S.groups[0].decisions[0].no") == highest
    assert ui.js("nextDecNo()") == highest + 1


# ------------------------------------------------------------------- log 7.3


def test_a_log_entry_lands_on_the_project_and_its_stage(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    stage = ui.js(f"stageName(Pr('{pid}'))")
    ui.run(f"addLog('project','{pid}','Walked the site with fresh eyes.');render();")
    entry = ui.js("Pr(" + json.dumps(pid) + ").logs[0]")
    assert entry["text"] == "Walked the site with fresh eyes."
    assert entry["stage"] == stage
    assert entry["highlight"] is False


def test_the_record_tab_writes_and_lists_the_log(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"S.view='project';S.projectId='{pid}';S.ptab='rec';render();")
    assert ui.count(".logadd textarea") == 1
    ui.run("var t=document.querySelector('.logadd textarea');t.value='First note';"
           f"logFromInput('project','{pid}',t);", settle=400)
    assert ui.count(".logline") >= 1
    assert "First note" in ui.html()


def test_a_highlight_can_be_marked_and_unmarked(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"addLog('project','{pid}','Worth remembering');render();")
    lid = ui.js("Pr(" + json.dumps(pid) + ").logs[0].id")
    ui.run(f"toggleHighlight('project','{pid}','{lid}');")
    assert ui.js("Pr(" + json.dumps(pid) + ").logs[0].highlight") is True
    ui.run(f"toggleHighlight('project','{pid}','{lid}');")
    assert ui.js("Pr(" + json.dumps(pid) + ").logs[0].highlight") is False


def test_a_log_entry_shows_on_the_project_timeline(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"addLog('project','{pid}','Something that happened in this stage');")
    ui.run(f"S.view='project';S.projectId='{pid}';S.ptab='rm';render();")
    assert "Something that happened in this stage" in ui.html()


def test_deleting_a_log_entry_offers_undo(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"addLog('project','{pid}','Take me out');render();")
    lid = ui.js("Pr(" + json.dumps(pid) + ").logs[0].id")
    ui.run(f"delLog('project','{pid}','{lid}');", settle=400)
    assert not any(e["text"] == "Take me out" for e in ui.js("Pr(" + json.dumps(pid) + ").logs"))
    ui.click(".toast .u")
    assert any(e["text"] == "Take me out" for e in ui.js("Pr(" + json.dumps(pid) + ").logs"))


def test_a_group_keeps_its_own_log(ui) -> None:
    started(ui)
    gid = ui.js("S.groups[0].id")
    ui.run(f"addLog('group','{gid}','Something that spans the whole group');render();")
    assert ui.js("S.groups[0].logs[0].text") == "Something that spans the whole group"
    assert ui.on_disk()["groups"][0]["logs"][0]["text"] == "Something that spans the whole group"


# ---------------------------------------------------------------- quiet 7.7


def test_a_project_nobody_has_touched_goes_quiet(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    assert ui.js("quietOnes().length") == 0
    ui.run(f"Pr('{pid}').lastAct=new Date(NOW-30*DAY);render();")
    assert [p["name"] for p in ui.js("quietOnes()")] == ["Website refresh"]
    ui.run("go('home');")
    assert "gone quiet" in ui.html()


def test_a_waiting_or_parked_project_is_not_called_quiet(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"Pr('{pid}').lastAct=new Date(NOW-30*DAY);Pr('{pid}').parked=true;render();")
    assert ui.js("quietOnes().length") == 0
    ui.run(f"Pr('{pid}').parked=false;Pr('{pid}').wait={{what:'a reply',since:NOW}};render();")
    assert ui.js("quietOnes().length") == 0


def test_projects_can_be_filtered_to_the_quiet_ones(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"Pr('{pid}').lastAct=new Date(NOW-30*DAY);S.sort='quiet';go('projects');")
    body = ui.html()
    assert "Website refresh" in body
    assert "Quarterly report" not in body


# --------------------------------------------------------------- review 7.2


def test_the_review_covers_the_period_you_pick(ui) -> None:
    started(ui)
    ui.run("S.view='week';S.period='week';render();")
    assert "Week of" in ui.text(".sheet .top")
    ui.run("S.period='month';render();")
    month = ui.js("new Date().toLocaleDateString('en-US',{month:'long',year:'numeric'})")
    assert month in ui.text(".sheet .top")
    ui.run("S.period='quarter';render();")
    assert "Q" in ui.text(".sheet .top")
    ui.run("S.period='lastmonth';render();")
    assert ui.js("S.view") == "week"


def test_the_review_can_be_scoped_to_one_group(ui) -> None:
    started(ui, kinds=("apps", "personal"))
    gid = ui.js("S.groups[0].id")
    ui.run(f"S.view='week';S.reviewGroup='{gid}';render();")
    assert ui.js("S.groups[0].name") in ui.text(".sheet .top")


def test_the_review_lists_releases_files_issued_and_highlights(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"var p=Pr('{pid}');"
           "p.releases.push({id:uid(),v:'1.0',at:new Date(NOW-1*DAY),note:'Handed over'});"
           "p.files.push({id:uid(),sha256:'',name:'Plan.pdf',type:'PDF',mime:'application/pdf',"
           "size:10,added_at:new Date(NOW-1*DAY).toISOString(),version:'v1.1',doc_id:'',descr:'',"
           "stage:'',previous_file_id:null,superseded:false});")
    ui.run(f"addLog('project','{pid}','A thing worth remembering');Pr('{pid}').logs[0].highlight=true;")
    ui.run("S.view='week';S.period='week';render();")
    body = ui.html()
    assert "Released" in body and "1.0" in body and "Handed over" in body
    assert "Files issued" in body and "Plan.pdf" in body and "v1.1" in body
    assert "Log highlights" in body and "A thing worth remembering" in body


def test_an_empty_review_says_so_and_invents_nothing(ui) -> None:
    started(ui, examples=False)
    ui.run("S.view='week';S.period='lastmonth';render();")
    body = ui.html()
    assert "Nothing shipped in this period." in body
    assert "No stage changes in this period." in body
    assert "Nothing was released in this period." in body
    assert "No documents were issued in this period." in body
    assert "Nothing was marked as a highlight in this period." in body


def test_the_review_states_what_it_left_out(ui) -> None:
    started(ui, kinds=("apps", "clients"))
    ui.run("S.view='week';S.publicOnly=true;render();")
    assert "1 private group left out" in ui.text(".sheet .top")
    ui.run("S.publicOnly=false;render();")
    assert "includes private groups" in ui.text(".sheet .top")


# ------------------------------------------------- duplicate and templates 7.4


def test_a_duplicate_carries_the_shape_and_none_of_the_history(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"duplicateProject('{pid}');closeOv();", settle=400)
    copy = ui.js("S.projects[0]")
    assert copy["name"] == "Copy of Website refresh"
    assert copy["stage"] == 0
    assert len(copy["items"]) == 2 and not any(i["done"] for i in copy["items"])
    assert copy["decisions"] == [] and copy["logs"] == [] and copy["files"] == []
    assert copy["links"] == ["example.com"]
    assert [p["n"] for p in copy["people"]] == ["Client"]


def test_a_template_can_be_saved_and_used(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"saveAsTemplate('{pid}');document.getElementById('tp-n').value='Standard site';"
           f"doSaveTemplate('{pid}');", settle=400)
    assert [t["name"] for t in ui.js("S.templates")] == ["Standard site"]

    ui.run("openNew(S.groups[0].id);document.getElementById('np-n').value='A new one';"
           "document.getElementById('np-tpl').value=S.templates[0].id;createP(null);", settle=400)
    made = ui.js("S.projects[0]")
    assert made["name"] == "A new one"
    assert len(made["items"]) == 2 and not any(i["done"] for i in made["items"])
    assert [p["n"] for p in made["people"]] == ["Client"]


def test_a_template_shows_in_settings_and_can_be_removed(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"saveAsTemplate('{pid}');document.getElementById('tp-n').value='Standard site';"
           f"doSaveTemplate('{pid}');", settle=400)
    ui.run("go('settings');", settle=600)
    assert "Standard site" in ui.html()
    ui.run("delTemplate(S.templates[0].id);")
    assert ui.js("S.templates") == []


# --------------------------------------------------------- recently deleted 7.5


def test_deleting_a_project_asks_first(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"deleteProject('{pid}');", settle=400)
    assert "Delete Website refresh?" in ui.html("#dlg-body")
    assert ui.js("S.projects.length") == 4, "nothing has gone yet"


def test_a_deleted_project_can_be_restored_with_its_children(ui) -> None:
    started(ui)
    pid = project_named(ui, "Website refresh")
    ui.run(f"doDeleteProject('{pid}');", settle=500)
    assert ui.js("S.projects.length") == 3

    ui.run("loadDeleted();", settle=900)
    rows = ui.js("DELETED")
    assert any(r["collection"] == "projects" and r["name"] == "Website refresh" for r in rows)

    ui.run(f"restoreDeleted('projects','{pid}');", settle=1200)
    back = ui.js("(S.projects.find(function(p){return p.id===" + json.dumps(pid) + "})||{})")
    assert back.get("name") == "Website refresh"
    assert len(back.get("items") or []) == 2, "its checklist came back with it"
    assert len(back.get("decisions") or []) == 1


# ---------------------------------------------------------------- people 7.8


def test_the_people_screen_lists_everyone_and_where_they_are(ui) -> None:
    started(ui)
    pid = project_named(ui, "Quarterly report")
    ui.run(f"Pr('{pid}').people.push({{id:uid(),n:'Client',r:'reviewer'}});")
    ui.run("go('people');")
    body = ui.html()
    assert "Client" in body
    assert "Website refresh" in body and "Quarterly report" in body, (
        "the same person shows on both projects"
    )
    names = [x["name"] for x in ui.js("everyone()")]
    assert names == ["Client"], "one row per person, not one per project"


# ----------------------------------------------------------- not planned 7.12


def test_not_planned_says_what_dig_does_not_do(ui) -> None:
    started(ui)
    ui.run("go('notplanned');")
    body = ui.html()
    for item in ("Boards and drag and drop", "Due dates on tasks", "Priorities",
                 "Assignees", "Time tracking", "Money and invoicing", "Notifications",
                 "Accounts and cloud", "AI"):
        assert item in body, item
    assert "Being considered" in body
    assert "!" not in ui.text(".np"), "no exclamation marks in the copy"


# -------------------------------------------------------- backup and restore 7.9


def test_a_backup_holds_the_document_and_the_files(ui, tmp_path: Path) -> None:
    started(ui)
    sample = tmp_path / "spec.txt"
    sample.write_text("a file worth keeping")
    pid = project_named(ui, "Website refresh")
    ui.queue_open(str(sample))
    ui.run(f"addFiles('{pid}','');", settle=700)

    out = tmp_path / "full.zip"
    ui.queue_save(str(out))
    ui.run("backupEverything();", settle=1200)

    manifest = read_manifest(out)
    assert manifest is not None
    assert manifest["projects"] == 4
    assert manifest["blobs"] == 1
    with zipfile.ZipFile(out) as archive:
        names = archive.namelist()
        assert "dig-backup.json" in names and "state.json" in names
        assert any(n.startswith("blobs/") for n in names)
        state = json.loads(archive.read("state.json"))
    assert len(referenced_blobs(state)) == 1


def test_restoring_asks_for_the_word_and_keeps_what_was_here(ui, tmp_path: Path) -> None:
    started(ui)
    out = tmp_path / "full.zip"
    ui.queue_save(str(out))
    ui.run("backupEverything();", settle=1200)

    ui.run("openNew(S.groups[0].id);document.getElementById('np-n').value='Made after the backup';"
           "createP(null);", settle=400)
    assert ui.js("S.projects.length") == 5

    ui.queue_open(str(out))
    ui.run("restoreBackup();", settle=1000)
    assert "Restore from this backup?" in ui.html("#dlg-body")
    assert ui.js("document.getElementById('rb-go').disabled") is True, "the word is required"

    ui.run("doRestore();", settle=1500)
    names = [p["name"] for p in ui.js("S.projects")]
    assert "Made after the backup" not in names
    assert len(names) == 4
    assert any("kept as" in t for t in ui.toasts())


def test_a_backup_from_a_newer_dig_is_refused(ui, tmp_path: Path) -> None:
    started(ui)
    out = tmp_path / "future.zip"
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("dig-backup.json", json.dumps(
            {"dig": "99.0.0", "schema": 999, "made_at": "2030-01-01T00:00:00",
             "projects": 1, "ideas": 0, "blobs": 0}))
        archive.writestr("state.json", json.dumps({"projects": []}))
    ui.queue_open(str(out))
    ui.run("restoreBackup();", settle=900)
    assert any("newer Dig" in t for t in ui.toasts())


def test_a_scheduled_backup_only_runs_when_it_is_due(tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    assert scheduled_is_due(folder, "daily") is True
    assert scheduled_is_due(folder, "") is False
    folder.mkdir()
    (folder / "dig-backup-20260904-120000.zip").write_bytes(b"x")
    assert scheduled_is_due(folder, "daily") is False

    for index in range(14):
        (folder / f"dig-backup-2026090{index % 9}-1200{index:02d}.zip").write_bytes(b"x")
    removed = trim_scheduled(folder, keep=10)
    assert removed > 0
    assert len(list(folder.glob("dig-backup-*.zip"))) == 10


# ------------------------------------------------------------ csv import 7.10


def test_a_csv_is_previewed_before_anything_is_written(ui, tmp_path: Path) -> None:
    started(ui, examples=False)
    csv_file = tmp_path / "projects.csv"
    csv_file.write_text("Name,Client,Status,Next Step\n"
                        "Website refresh,Acme,Plan,Agree the pages\n"
                        "Quarterly report,Acme,Build,Pull the numbers\n")
    ui.queue_open(str(csv_file))
    ui.run("importCsv('projects');", settle=900)

    assert "Import projects.csv" in ui.html("#dlg-body")
    assert "Website refresh" in ui.html("#csv-prev")
    assert ui.js("S.projects.length") == 0, "nothing written yet"

    ui.run("doCsvImport();", settle=900)
    names = [p["name"] for p in ui.js("S.projects")]
    assert sorted(names) == ["Quarterly report", "Website refresh"]
    assert "Acme" in [g["name"] for g in ui.js("S.groups")], "the missing group was created"


def test_csv_columns_can_be_remapped() -> None:
    text = "one,two,three\nAlpha,note here,Work\n"
    guessed = csvin.preview(text, "ideas")
    assert guessed["ok"] is True
    remapped = csvin.preview(text, "ideas", {"text": 0, "notes": 1, "group": 2})
    assert remapped["rows"][0] == {"text": "Alpha", "notes": "note here", "group": "Work"}


def test_ideas_come_in_from_a_csv(ui, tmp_path: Path) -> None:
    started(ui, examples=False)
    csv_file = tmp_path / "ideas.csv"
    csv_file.write_text("Idea,Notes\nA better way to file receipts,One folder\nWalking routes,\n")
    ui.queue_open(str(csv_file))
    ui.run("importCsv('ideas');", settle=900)
    ui.run("doCsvImport();", settle=900)
    assert sorted(i["text"] for i in ui.js("S.ideas")) == [
        "A better way to file receipts", "Walking routes"
    ]


# --------------------------------------------- text size and reachability 7.11


def test_the_text_size_can_be_changed_and_is_remembered(ui) -> None:
    started(ui)
    assert ui.js("getComputedStyle(document.body).fontSize") == "14px"
    ui.run("setTextSize('l');", settle=300)
    assert ui.js("getComputedStyle(document.body).fontSize") == "15.5px"
    ui.restart()
    assert ui.js("S.textSize") == "l"
    assert ui.js("getComputedStyle(document.body).fontSize") == "15.5px"


def test_everything_clickable_can_be_reached_by_keyboard(ui) -> None:
    started(ui)
    for view in ("home", "projects", "roadmap", "ideas", "library", "week", "settings"):
        ui.run(f"go({view!r});", settle=300)
        # The dim behind a dialog closes it on a click but is deliberately not a
        # control: a keyboard closes the dialog with Esc.
        unreachable = ui.js(
            "Array.prototype.filter.call(document.querySelectorAll('#app [onclick]'),"
            "function(e){return ['BUTTON','INPUT','SELECT','TEXTAREA'].indexOf(e.tagName)<0"
            "&&!e.classList.contains('overlay')&&!e.hasAttribute('tabindex')}).length"
        )
        assert unreachable == 0, f"{view} has clickable things a keyboard cannot reach"


def test_icon_only_controls_have_a_name(ui) -> None:
    started(ui)
    ui.run("openKeys();", settle=400)
    unnamed = ui.js(
        "Array.prototype.filter.call(document.querySelectorAll('#app [onclick]'),"
        "function(e){var t=(e.textContent||'').trim();"
        "return t.length<2&&!e.getAttribute('aria-label')"
        "&&!e.classList.contains('overlay')}).length"
    )
    assert unnamed == 0


def test_the_two_halves_are_landmarks(ui) -> None:
    started(ui)
    assert ui.js("document.querySelector('.side').getAttribute('role')") == "navigation"
    assert ui.js("document.querySelector('.main').getAttribute('role')") == "main"
    assert ui.js("document.getElementById('toasts').getAttribute('aria-live')") == "polite"
    assert ui.js("document.querySelector('.nav a.on').getAttribute('aria-current')") == "page"


def test_the_contrast_meets_double_a_in_both_themes() -> None:
    """Every foreground on the surface it actually sits on."""
    def lum(value: str) -> float:
        value = value.lstrip("#")
        parts = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        adjusted = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in parts]
        return 0.2126 * adjusted[0] + 0.7152 * adjusted[1] + 0.0722 * adjusted[2]

    def ratio(a: str, b: str) -> float:
        first, second = lum(a), lum(b)
        return (max(first, second) + 0.05) / (min(first, second) + 0.05)

    css = (Path(__file__).resolve().parent.parent / "dig" / "ui" / "app.css").read_text()

    def token(theme: str, name: str) -> str:
        block = css.split(f':root[data-theme="{theme}"]')[1].split("}")[0]
        return block.split(f"{name}:")[1].split(";")[0].strip()

    for theme in ("light", "dark"):
        surfaces = [token(theme, n) for n in ("--panel", "--bg", "--panel-2")]
        for name in ("--ink", "--ink-2", "--ink-3"):
            for surface in surfaces:
                assert ratio(token(theme, name), surface) >= 4.5, f"{theme} {name} on {surface}"
        for name in ("--blue", "--teal", "--green", "--amber", "--coral", "--rose"):
            soft = token(theme, name + "-soft")
            assert ratio(token(theme, name), soft) >= 4.5, f"{theme} {name} on its soft background"
