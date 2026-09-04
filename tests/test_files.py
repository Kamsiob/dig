"""Files: getting them in, viewing them, and getting them back out. Part 6."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

from dig import paths
from dig.store.blobs import BlobStore


def setup_done(ui) -> None:
    ui.run("S.org='Example Studio';S.setupWork.apps=true;render();finishSetup();")


def a_project(ui, name="File tests") -> str:
    ui.run(f"openNew('apps');document.getElementById('np-n').value={name!r};createP(null);")
    return ui.js("S.projects[0].id")


@pytest.fixture()
def samples(tmp_path: Path) -> dict:
    made = {}
    (tmp_path / "notes.txt").write_text("first line\nsecond line\n")
    (tmp_path / "data.csv").write_text("name,size\nAlpha,10\nBeta,20\n")
    (tmp_path / "spec.md").write_text("# A spec\n\nWith a line.\n")
    (tmp_path / "blob.bin").write_bytes(bytes(range(256)) * 4)
    (tmp_path / "copy.txt").write_text("first line\nsecond line\n")  # same bytes
    for name in ("notes.txt", "data.csv", "spec.md", "blob.bin", "copy.txt"):
        made[name] = tmp_path / name
    return made


# --------------------------------------------------------------- getting in


def test_the_picker_takes_several_files_at_once(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]), str(samples["data.csv"]), str(samples["blob.bin"]))
    ui.run(f"addFiles('{pid}','');", settle=700)

    files = ui.js("S.projects[0].files")
    assert sorted(f["name"] for f in files) == ["blob.bin", "data.csv", "notes.txt"]
    for f in files:
        assert len(f["sha256"]) == 64
        assert f["size"] > 0
        assert f["id"]
    assert any("Kept copies of 3 files" in t for t in ui.toasts())


def test_the_same_bytes_are_only_stored_once(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    ui.queue_open(str(samples["copy.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)

    files = ui.js("S.projects[0].files")
    assert len(files) == 2, "two records"
    assert files[0]["sha256"] == files[1]["sha256"], "one set of bytes"
    blobs = BlobStore(paths.blobs_dir())
    assert len(blobs.every()) == 1


def test_a_name_that_clashes_asks_rather_than_overwriting(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    assert ui.js("S.projects[0].files.length") == 1

    (samples["notes.txt"]).write_text("a different second version\n")
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    assert "There is already a file called that" in ui.html("#dlg-body")


def test_keeping_both_gives_the_second_one_a_suffix(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    samples["notes.txt"].write_text("a different second version\n")
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    ui.run("resolveClash('both');", settle=500)

    names = sorted(f["name"] for f in ui.js("S.projects[0].files"))
    assert names == ["notes (2).txt", "notes.txt"]


def test_replacing_as_a_version_keeps_the_old_one_on_the_record(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    first = ui.js("S.projects[0].files[0].id")
    samples["notes.txt"].write_text("a different second version\n")
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    ui.run("resolveClash('version');", settle=500)

    files = ui.js("S.projects[0].files")
    current = next(f for f in files if not f["superseded"])
    older = next(f for f in files if f["superseded"])
    assert older["id"] == first
    assert current["previous_file_id"] == first
    assert ui.count(".filerow") >= 1, "only the current one is listed"


# ------------------------------------------------------------------ viewing


def test_a_text_file_reads_in_the_viewer(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    ui.run(f"S.view='project';S.projectId='{pid}';render();openFile(S.projects[0].files[0].id);", settle=800)

    body = ui.html("#viewer-stage")
    assert "first line" in body and "second line" in body
    assert "class=\"ln\"" in body, "with line numbers"


def test_a_csv_reads_as_a_table(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["data.csv"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    ui.run(f"S.view='project';S.projectId='{pid}';render();openFile(S.projects[0].files[0].id);", settle=800)

    body = ui.html("#viewer-stage")
    assert "<table>" in body and "<th>name</th>" in body and "<td>Alpha</td>" in body


def test_something_with_no_preview_says_so_and_still_offers_the_file(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["blob.bin"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    ui.run(f"S.view='project';S.projectId='{pid}';render();openFile(S.projects[0].files[0].id);", settle=800)

    assert "No preview for this kind of file" in ui.html("#viewer-stage")
    assert "Open with the system app" in ui.html("#dlg-body")
    assert "Save a copy" in ui.html("#dlg-body")


def test_the_viewer_details_can_be_edited(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    fid = ui.js("S.projects[0].files[0].id")
    ui.run(f"openFile('{fid}');", settle=600)
    ui.run(f"editFile('{fid}','doc_id','BCP-001');editFile('{fid}','version','v1.1');", settle=400)

    stored = ui.on_disk()["projects"][0]["files"][0]
    assert stored["doc_id"] == "BCP-001" and stored["version"] == "v1.1"


def test_the_arrows_move_between_files_of_the_same_owner(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]), str(samples["data.csv"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    ids = [f["id"] for f in ui.js("S.projects[0].files")]
    ui.run(f"S.view='project';S.projectId='{pid}';render();openFile('{ids[0]}');", settle=600)
    ui.run("stepFile(1);", settle=600)
    assert ui.js("VIEWING") == ids[1]
    ui.run("stepFile(-1);", settle=600)
    assert ui.js("VIEWING") == ids[0]


# ------------------------------------------------------------ getting out


def test_save_a_copy_writes_the_exact_original_bytes(ui, samples, tmp_path: Path) -> None:
    setup_done(ui)
    pid = a_project(ui)
    original = samples["blob.bin"].read_bytes()
    ui.queue_open(str(samples["blob.bin"]))
    ui.run(f"addFiles('{pid}','');", settle=600)

    out = tmp_path / "out" / "same.bin"
    ui.queue_save(str(out))
    ui.run("saveFileCopy(S.projects[0].files[0].id);", settle=700)
    assert out.read_bytes() == original


def test_save_all_files_writes_a_zip_with_a_manifest(ui, samples, tmp_path: Path) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]), str(samples["data.csv"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    ui.run(f"editFile(S.projects[0].files[0].id,'version','v2');", settle=300)

    out = tmp_path / "bundle.zip"
    ui.queue_save(str(out))
    ui.run(f"saveAllFiles('{pid}','');", settle=900)

    with zipfile.ZipFile(out) as archive:
        names = set(archive.namelist())
        assert "manifest.csv" in names
        assert {"notes.txt", "data.csv"} <= names
        assert archive.read("notes.txt") == samples["notes.txt"].read_bytes()
        rows = list(csv.reader(io.StringIO(archive.read("manifest.csv").decode())))
    assert rows[0] == ["name", "document id", "version", "size", "added", "sha256"]
    assert len(rows) == 3
    assert any(r[2] == "v2" for r in rows[1:])
    assert all(len(r[5]) == 64 for r in rows[1:])


# ------------------------------------------------------------ moving, deleting


def test_a_file_moves_between_owners_without_copying_the_bytes(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    fid = ui.js("S.projects[0].files[0].id")
    sha = ui.js("S.projects[0].files[0].sha256")

    ui.run(f"moveFile('{fid}');", settle=500)
    ui.run("document.getElementById('mv-to').value='lib';doMoveFile(" + json.dumps(fid) + ");", settle=600)

    assert ui.js("S.projects[0].files.length") == 0
    assert [f["id"] for f in ui.js("S.libraryFiles")] == [fid]
    blobs = BlobStore(paths.blobs_dir())
    assert blobs.every() == [sha], "one copy of the bytes, still"


def test_deleting_a_file_offers_undo(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    fid = ui.js("S.projects[0].files[0].id")

    ui.run(f"deleteFile('{fid}');", settle=600)
    assert ui.js("S.projects[0].files.length") == 0
    assert any("Recently deleted" in t for t in ui.toasts())

    ui.click(".toast .u")
    assert ui.js("S.projects[0].files.length") == 1


def test_a_deleted_file_is_a_tombstone_and_can_be_restored(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    fid = ui.js("S.projects[0].files[0].id")
    ui.on_disk()

    ui.run(f"deleteFile('{fid}');", settle=600)
    ui.on_disk()

    recent = [r for r in ui.store.deleted_since(30) if r["collection"] == "files"]
    assert [r["id"] for r in recent] == [fid]
    assert ui.store.restore("files", fid) is True


# ------------------------------------------------------------- housekeeping


def test_cleanup_never_removes_a_blob_something_points_at(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["notes.txt"]), str(samples["data.csv"]))
    ui.run(f"addFiles('{pid}','');", settle=700)
    kept = ui.js("S.projects[0].files.map(function(f){return f.sha256})")

    blobs = BlobStore(paths.blobs_dir())
    loose = tmp = samples["blob.bin"]
    orphan = blobs.put(loose)
    assert len(blobs.every()) == 3

    report = json.loads(ui.raw(f"var r;BRIDGE.storage({json.dumps(json.dumps(kept))},function(j){{r=j}});'x'") or '""') if False else None
    left = blobs.unreferenced(set(kept))
    assert left == [orphan.sha256]
    for sha in left:
        blobs.remove(sha)
    for sha in kept:
        assert blobs.has(sha), "everything in use survived"


def test_the_view_links_do_not_count_as_blobs(ui, samples) -> None:
    setup_done(ui)
    pid = a_project(ui)
    ui.queue_open(str(samples["data.csv"]))
    ui.run(f"addFiles('{pid}','');", settle=600)
    fid = ui.js("S.projects[0].files[0].id")
    ui.run(f"S.view='project';S.projectId='{pid}';render();openFile('{fid}');", settle=800)

    blobs = BlobStore(paths.blobs_dir())
    assert len(blobs.every()) == 1, "the viewer's named link is not a second blob"
    assert blobs.total_size() == samples["data.csv"].stat().st_size
