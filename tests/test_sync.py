"""Two devices agreeing on what happened, and the server that lets them."""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from dig.store import BlobStore, Store
from dig.store.store import now_iso
from dig.store.schema import SCHEMA_VERSION
from dig.sync import protocol
from dig.sync.server import SyncServer, tailscale_addresses

BASE = {
    "org": "Example Studio", "you": "Alex", "theme": "light", "setupDone": True,
    "ui": {}, "groups": [{"id": "g", "name": "Work", "color": "#2457F5", "priv": False}],
    "types": [{"id": "t", "name": "Task", "stages": ["Planned", "Done"], "check": {}}],
    "projects": [{
        "id": "p1", "name": "Alpha", "group": "g", "type": "t", "stage": 0,
        "enteredAt": "2026-09-01T09:00:00", "when": "now", "next": "", "notes": "",
        "pub": True, "wait": None, "lastAct": "2026-09-01T09:00:00", "quiet": False,
        "parked": False, "origin": None, "items": [], "decisions": [], "files": [],
        "links": [], "releases": [], "people": [], "hist": [], "waitHist": [],
    }],
    "ideas": [], "inbox": [], "library": [], "activity": [],
}


@pytest.fixture()
def two(tmp_path: Path):
    """Two devices that start from the same document."""
    a = Store(tmp_path / "a.db", tmp_path / "ha")
    b = Store(tmp_path / "b.db", tmp_path / "hb")
    a.save_state(BASE)
    b.save_state(BASE)
    return a, b


def change(collection, record_id, op, payload, at, device, rev=1):
    return {"collection": collection, "record_id": record_id, "op": op, "rev": rev,
            "payload": payload, "at": at, "device": device}


# ------------------------------------------------------------------ the rules


def test_an_edit_from_elsewhere_is_taken(two) -> None:
    a, b = two
    state = b.load().state
    state["projects"][0]["name"] = "Alpha, renamed on B"
    b.save_state(state)

    results = protocol.apply_batch(a, b.changes_since(0))
    assert all(r.result in (protocol.ACCEPTED, protocol.IGNORED) for r in results)
    assert a.load().state["projects"][0]["name"] == "Alpha, renamed on B"


def test_a_record_never_seen_is_taken_whole(two) -> None:
    a, _ = two
    results = protocol.apply_batch(a, [change(
        "ideas", "brand-new", "create",
        {"text": "From another device", "descr": "", "at": "2026-09-04T10:00:00",
         "opened": None, "group_id": None, "example": 0, "position": 0},
        "2026-09-04T10:00:00.000000", "other")])
    assert [r.result for r in results] == [protocol.ACCEPTED]
    assert [i["text"] for i in a.load().state["ideas"]] == ["From another device"]


def test_a_delete_for_something_never_seen_still_leaves_a_tombstone(two) -> None:
    a, _ = two
    protocol.apply_batch(a, [change("ideas", "never-here", "delete", {},
                                    "2026-09-04T10:00:00.000000", "other")])
    conn = a.connect()
    row = conn.execute("SELECT deleted FROM ideas WHERE id='never-here'").fetchone()
    assert row is not None and row["deleted"] == 1, "it cannot arrive later by another route"


def test_a_delete_beats_a_concurrent_edit_and_keeps_the_loser(two) -> None:
    a, _ = two
    state = a.load().state
    state["projects"][0]["notes"] = "edited here, just now"
    a.save_state(state)

    # the delete is stamped earlier than our edit: the race
    protocol.apply_batch(a, [change("projects", "p1", "delete", {},
                                    "2026-09-01T09:00:01.000000", "other")])
    assert a.load().state["projects"] == []
    conflicts = protocol.open_conflicts(a)
    assert len(conflicts) == 1
    assert "deleted elsewhere" in conflicts[0]["reason"]
    assert json.loads(conflicts[0]["losing"])["notes"] == "edited here, just now"


def test_an_edit_does_not_undo_a_delete(two) -> None:
    a, _ = two
    state = a.load().state
    state["projects"] = []
    a.save_state(state)

    results = protocol.apply_batch(a, [change("projects", "p1", "update",
                                              {"name": "trying to come back"},
                                              "2099-01-01T00:00:00.000000", "other")])
    assert [r.result for r in results] == [protocol.CONFLICT]
    assert a.load().state["projects"] == []
    assert len(protocol.open_conflicts(a)) == 1


def test_the_older_change_loses(two) -> None:
    a, _ = two
    state = a.load().state
    state["projects"][0]["name"] = "Newer here"
    a.save_state(state)

    results = protocol.apply_batch(a, [change("projects", "p1", "update",
                                              {"name": "Older there"},
                                              "2020-01-01T00:00:00.000000", "other")])
    assert [r.result for r in results] == [protocol.IGNORED]
    assert a.load().state["projects"][0]["name"] == "Newer here"


def test_an_exact_tie_is_broken_the_same_way_on_both_devices() -> None:
    assert protocol.newer("2026-09-04T10:00:00", "zzz", "2026-09-04T10:00:00", "aaa") is True
    assert protocol.newer("2026-09-04T10:00:00", "aaa", "2026-09-04T10:00:00", "zzz") is False
    assert protocol.newer("2026-09-04T10:00:01", "aaa", "2026-09-04T10:00:00", "zzz") is True


def test_lists_merge_additively(two) -> None:
    a, b = two
    state = a.load().state
    state["projects"][0]["items"] = [{"id": "ia", "text": "From A", "done": False, "tag": ""}]
    a.save_state(state)

    state = b.load().state
    state["projects"][0]["items"] = [{"id": "ib", "text": "From B", "done": False, "tag": ""}]
    b.save_state(state)

    protocol.apply_batch(a, b.changes_since(0))
    texts = [i["text"] for i in a.load().state["projects"][0]["items"]]
    assert sorted(texts) == ["From A", "From B"], "both sides keep both"


def test_the_same_batch_twice_changes_nothing(two) -> None:
    a, b = two
    state = b.load().state
    state["ideas"] = [{"id": "shared", "text": "Once", "desc": "",
                       "at": "2026-09-04T10:00:00", "opened": None, "group": ""}]
    b.save_state(state)

    batch = b.changes_since(0)
    protocol.apply_batch(a, batch)
    before = a.meta()["cursor"]
    protocol.apply_batch(a, batch)
    assert len([i for i in a.load().state["ideas"] if i["text"] == "Once"]) == 1
    assert a.meta()["cursor"] == before, "nothing was written the second time"


def test_a_device_that_was_away_catches_up_in_order(two) -> None:
    a, b = two
    for index in range(30):
        state = b.load().state
        state["ideas"].append({"id": f"i{index}", "text": f"Idea {index}", "desc": "",
                               "at": "2026-09-04T10:00:00", "opened": None, "group": ""})
        b.save_state(state)

    cursor = 0
    applied = 0
    while True:
        batch = b.changes_since(cursor, 7)
        if not batch:
            break
        protocol.apply_batch(a, batch)
        applied += len(batch)
        cursor = batch[-1]["seq"]
    assert len(a.load().state["ideas"]) == 30
    assert applied >= 30


def test_settings_sync_too(two) -> None:
    a, b = two
    state = b.load().state
    state["org"] = "Changed on B"
    b.save_state(state)
    protocol.apply_batch(a, b.changes_since(0))
    assert a.load().state["org"] == "Changed on B"


def test_conflicts_can_be_marked_seen(two) -> None:
    a, _ = two
    state = a.load().state
    state["projects"] = []
    a.save_state(state)
    protocol.apply_batch(a, [change("projects", "p1", "update", {"name": "x"},
                                    "2099-01-01T00:00:00.000000", "other")])
    conflicts = protocol.open_conflicts(a)
    assert len(conflicts) == 1
    protocol.mark_conflicts_seen(a, [c["id"] for c in conflicts])
    assert protocol.open_conflicts(a) == []


# ---------------------------------------------------------------- the server


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture()
def server(tmp_path: Path, qt_app):
    store = Store(tmp_path / "s.db", tmp_path / "hs")
    store.save_state(BASE)
    blobs = BlobStore(tmp_path / "blobs")
    running = SyncServer(tmp_path / "s.db", tmp_path / "hs", blobs)
    port = free_port()
    status = running.start(port)
    if not status["running"]:
        pytest.skip("no Tailscale address on this machine, so the server cannot start")
    yield running, port, store, blobs
    running.stop()


def call(port, path, method="GET", body=None, token="", raw=None):
    url = f"http://127.0.0.1:{port}{path}"
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    request = urllib.request.Request(url, data=data, method=method)
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = response.read()
            kind = response.headers.get("Content-Type", "")
            if "octet-stream" in kind:
                return response.status, payload
            return response.status, json.loads(payload.decode())
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode())
        except Exception:
            return error.code, {}


def test_it_refuses_to_start_without_tailscale(tmp_path: Path, qt_app, monkeypatch) -> None:
    import dig.sync.server as module

    monkeypatch.setattr(module, "tailscale_addresses", lambda: [])
    running = module.SyncServer(tmp_path / "x.db", tmp_path / "hx", BlobStore(tmp_path / "b"))
    status = running.start(free_port())
    assert status["running"] is False
    assert "Tailscale" in status["reason"]
    assert status["bound"] == []


def test_it_never_binds_to_everything(server) -> None:
    running, port, _, _ = server
    assert "0.0.0.0" not in running.bound
    assert "127.0.0.1" in running.bound
    assert all(a == "127.0.0.1" or a.startswith("100.") for a in running.bound)


def test_hello_needs_no_token_and_says_the_schema(server) -> None:
    _, port, _, _ = server
    status, body = call(port, "/v1/hello")
    assert status == 200
    assert body["schema"] == SCHEMA_VERSION and body["app"] == "Dig"


def test_everything_else_needs_pairing(server) -> None:
    _, port, _, _ = server
    for path in ("/v1/state", "/v1/changes"):
        status, body = call(port, path)
        assert status == 401 and body["ok"] is False


def test_pairing_takes_one_code_once(server) -> None:
    running, port, _, _ = server
    made = running.make_code()
    assert made["ok"] and made["code"]

    status, _ = call(port, "/v1/pair", "POST",
                     {"code": "WRONG", "name": "x", "device": "d1", "schema": SCHEMA_VERSION})
    assert status == 403

    status, body = call(port, "/v1/pair", "POST",
                        {"code": made["code"], "name": "Pixel", "device": "d1",
                         "schema": SCHEMA_VERSION})
    assert status == 200 and body["token"]
    token = body["token"]

    status, _ = call(port, "/v1/pair", "POST",
                     {"code": made["code"], "name": "again", "device": "d2",
                      "schema": SCHEMA_VERSION})
    assert status == 403, "the code is single use"

    status, body = call(port, "/v1/state", token=token)
    assert status == 200 and body["ok"]


def test_a_different_schema_is_refused(server) -> None:
    running, port, _, _ = server
    made = running.make_code()
    status, _ = call(port, "/v1/pair", "POST",
                     {"code": made["code"], "name": "x", "device": "d", "schema": 999})
    assert status == 409


def paired(server) -> str:
    running, port, _, _ = server
    made = running.make_code()
    _, body = call(port, "/v1/pair", "POST",
                   {"code": made["code"], "name": "Test device", "device": "dev-1",
                    "schema": SCHEMA_VERSION})
    return body["token"]


def test_a_full_snapshot_and_then_changes(server) -> None:
    running, port, store, _ = server
    token = paired(server)

    status, body = call(port, "/v1/state", token=token)
    assert status == 200
    assert [p["name"] for p in body["state"]["projects"]] == ["Alpha"]
    cursor = body["cursor"]

    status, body = call(port, f"/v1/changes?since={cursor}", token=token)
    assert status == 200 and body["changes"] == []

    status, body = call(port, "/v1/push", "POST", {
        "schema": SCHEMA_VERSION,
        "changes": [change("ideas", "from-phone", "create",
                           {"text": "Written on the phone", "descr": "",
                            "at": "2026-09-04T10:00:00", "opened": None,
                            "group_id": None, "example": 0, "position": 0},
                           "2099-01-01T00:00:00.000000", "dev-1")],
    }, token=token)
    assert status == 200 and body["results"][0]["result"] == "accepted"

    status, body = call(port, "/v1/state", token=token)
    assert "Written on the phone" in [i["text"] for i in body["state"]["ideas"]]

    status, body = call(port, f"/v1/changes?since={cursor}", token=token)
    assert any(c["record_id"] == "from-phone" for c in body["changes"])


def test_a_revoked_device_is_refused(server) -> None:
    running, port, _, _ = server
    token = paired(server)
    assert call(port, "/v1/state", token=token)[0] == 200

    running.revoke("dev-1")
    status, body = call(port, "/v1/state", token=token)
    assert status == 401 and body["ok"] is False


def test_files_go_both_ways_and_are_checked(server) -> None:
    _, port, _, blobs = server
    token = paired(server)
    payload = b"some bytes worth syncing" * 40
    sha = hashlib.sha256(payload).hexdigest()

    status, body = call(port, f"/v1/blobs/{sha}/upload", "POST", token=token, raw=payload)
    assert status == 200 and body["sha256"] == sha
    assert blobs.has(sha)

    status, back = call(port, f"/v1/blobs/{sha}", token=token)
    assert status == 200 and back == payload

    status, _ = call(port, "/v1/blobs/" + "0" * 64, token=token)
    assert status == 404

    wrong = hashlib.sha256(b"different").hexdigest()
    status, body = call(port, f"/v1/blobs/{wrong}/upload", "POST", token=token, raw=payload)
    assert status == 400, "bytes that are not that hash are refused"


def test_a_big_batch_is_answered_without_dying(server) -> None:
    _, port, _, _ = server
    token = paired(server)
    batch = [
        change("ideas", f"bulk-{i}", "create",
               {"text": f"Bulk {i}", "descr": "", "at": "2026-09-04T10:00:00",
                "opened": None, "group_id": None, "example": 0, "position": i},
               "2099-01-01T00:00:00.000000", "dev-1")
        for i in range(200)
    ]
    started = time.monotonic()
    status, body = call(port, "/v1/push", "POST",
                        {"schema": SCHEMA_VERSION, "changes": batch}, token=token)
    assert status == 200 and len(body["results"]) == 200
    assert time.monotonic() - started < 20


def test_every_exchange_is_written_down(server) -> None:
    running, port, _, _ = server
    token = paired(server)
    call(port, "/v1/state", token=token)
    call(port, "/v1/state")  # refused
    entries = running.status()["log"]
    assert any(e["outcome"] == "ok" and "snapshot" in e["what"] for e in entries)
    assert any("refused" in e["outcome"] for e in entries)
    assert all({"at", "device", "what", "outcome"} <= set(e) for e in entries)


def test_the_pairing_payload_is_what_the_qr_holds(server) -> None:
    running, _, _, _ = server
    made = running.make_code()
    payload = json.loads(made["pairing"])
    assert payload["v"] == 1
    assert payload["code"] == made["code"]
    assert payload["port"] == running.port
    assert payload["address"].startswith("100."), "the tailnet address, not the local one"


def test_a_change_arriving_does_not_empty_an_open_dialog(ui) -> None:
    """Redrawing the window empties every dialog in it, so a change that turns
    up while you are typing has to wait until you have closed what you are in."""
    ui.run("S.org='Riverbank';S.setupWork.apps=true;obGo(4);obFinish();", settle=600)
    ui.run("openCap();document.getElementById('cap-in').value='Half a thought';",
           settle=300)

    ui.run("reloadFromDisk();", settle=600)
    assert ui.count("#ov-cap.open") == 1, "the dialog was closed under the person"
    assert ui.js("document.getElementById('cap-in').value") == "Half a thought", (
        "what was typed disappeared"
    )
    assert ui.js("WAITING_TO_RELOAD") is True

    ui.run("doCapture();", settle=800)
    assert ui.js("WAITING_TO_RELOAD") is False, "the held change was never brought in"
    assert any(i["text"] == "Half a thought" for i in ui.js("S.ideas")), (
        "the thought was lost on the way"
    )


def test_a_redraw_leaves_an_open_dialog_where_it_is(ui) -> None:
    """Anything that redraws the window while a dialog is open would otherwise
    replace the box a person is typing into, and take what they typed with it."""
    ui.run("S.org='Riverbank';S.setupWork.apps=true;obGo(4);obFinish();", settle=600)
    ui.run("openCap();document.getElementById('cap-in').value='Mid sentence';",
           settle=300)

    ui.run("render();", settle=400)
    assert ui.count("#ov-cap.open") == 1, "the redraw closed the dialog"
    assert ui.js("document.getElementById('cap-in').value") == "Mid sentence"

    order = ui.js("Array.prototype.map.call(document.getElementById('app').children,"
                  "function(e){return e.id||e.className})")
    assert order.index("ov-dlg") < order.index("drop-veil"), (
        "the overlays came back in the wrong place"
    )

    ui.run("closeOv();render();", settle=400)
    assert ui.count("#ov-cap.open") == 0


def test_a_field_this_computer_does_not_know_is_dropped(store) -> None:
    """Column names go into the statement itself, and a paired device is the
    one thing that can put a name there this computer did not choose."""
    conn = store.connect()
    with conn:
        store.write(conn, "ideas", "one", "create",
                    {"text": "Real", "group": "", "desc": "", "nonsense": 1})
    row = conn.execute("SELECT * FROM ideas WHERE id = 'one'").fetchone()
    assert row["text"] == "Real", "the record was written without the unknown fields"
    assert "group" not in row.keys() and "nonsense" not in row.keys()


def test_a_field_name_cannot_carry_sql(store) -> None:
    conn = store.connect()
    with conn:
        store.write(conn, "ideas", "two", "create",
                    {"text": "Still here", "x = 1, text": "smuggled"})
    row = conn.execute("SELECT * FROM ideas WHERE id = 'two'").fetchone()
    assert row["text"] == "Still here"
    assert conn.execute("SELECT count(*) FROM ideas").fetchone()[0] >= 1


def test_a_local_save_does_not_delete_what_just_arrived(store) -> None:
    """The interface saves the whole document, so anything not in it is taken
    to have been deleted. Something another device wrote a moment ago is not in
    it because the interface has never seen it, not because it went away."""
    store.save_state({"ideas": [{"id": "mine", "text": "Mine"}]})
    handed_out = int(store.meta()["cursor"])

    conn = store.connect()
    with conn:
        # Dated in the past on purpose: the other device's clock is not ours to
        # trust, so this cannot rest on the timestamp being newer.
        store.write(conn, "ideas", "theirs", "create", {"text": "Theirs"},
                    "another-device", "2019-01-01T00:00:00.000000")

    # The interface saves the document it was holding, which knows nothing
    # about the idea that arrived while it was open.
    summary = store.save_state({"ideas": [{"id": "mine", "text": "Mine"}]}, handed_out)
    assert summary["kept"] == 1, "the arriving idea was not kept"

    alive = {r["id"] for r in store.connect().execute(
        "SELECT id FROM ideas WHERE deleted = 0").fetchall()}
    assert alive == {"mine", "theirs"}


def test_deleting_something_that_came_from_elsewhere_still_works(store) -> None:
    """The rule above must not make records from another device undeletable."""
    conn = store.connect()
    with conn:
        store.write(conn, "ideas", "theirs", "create", {"text": "Theirs"},
                    "another-device", "2020-01-01T00:00:00.000000")
    store.save_state({"ideas": []}, int(store.meta()["cursor"]))
    row = store.connect().execute("SELECT deleted FROM ideas WHERE id='theirs'").fetchone()
    assert row["deleted"] == 1, "a record from another device could not be deleted here"
