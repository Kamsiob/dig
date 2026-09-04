"""Turning the one state document into records, and back.

The interface holds everything as a single object, exactly as the prototype
does. Storage holds it as records, because that is what a sync can reason
about. This module is the whole of the translation between the two.

Records that the prototype gives an id already keep it. Records it writes as
bare values, a link is only a string and a release is only three fields, get a
deterministic id derived from their parent and their content, so that adding
the same release on two devices converges instead of doubling.
"""

from __future__ import annotations

import uuid

# One fixed namespace, so a derived id is the same on every device forever.
NAMESPACE = uuid.UUID("6f6b8f2a-0d1b-4a5e-9a4e-2f3c5d6e7a8b")

SETTING_KEYS = ("org", "you", "theme", "setupDone", "ui", "startHere",
                "backupFolder", "backupEvery")


def derived_id(*parts) -> str:
    return str(uuid.uuid5(NAMESPACE, "\x1f".join("" if p is None else str(p) for p in parts)))


def _b(value) -> int:
    return 1 if value else 0


def _s(value) -> str:
    return "" if value is None else str(value)


def _iso(value):
    """Dates arrive as ISO strings because JSON has no date. Keep them as they are."""
    if value is None or value == "":
        return None
    return str(value)


# --------------------------------------------------------------- state to rows


def flatten(state: dict) -> tuple[dict[str, list[dict]], dict]:
    """Split the state document into records per collection, plus settings."""
    out: dict[str, list[dict]] = {name: [] for name in COLLECTIONS}

    for index, group in enumerate(state.get("groups") or []):
        out["groups"].append(
            {
                "id": group["id"],
                "name": _s(group.get("name")),
                "color": _s(group.get("color")),
                "priv": _b(group.get("priv")),
                "description": _s(group.get("description")),
                "position": index,
            }
        )
        for j, url in enumerate(group.get("links") or []):
            out["links"].append(
                {
                    "id": derived_id("link", "group", group["id"], url),
                    "project_id": None,
                    "group_id": group["id"],
                    "url": _s(url),
                    "position": j,
                }
            )

    for index, kind in enumerate(state.get("types") or []):
        out["types"].append(
            {
                "id": kind["id"],
                "name": _s(kind.get("name")),
                "stages": kind.get("stages") or [],
                "checks": kind.get("check") or {},
                "position": index,
            }
        )

    decision_ids: dict[int, str] = {}
    for project in state.get("projects") or []:
        for decision in project.get("decisions") or []:
            decision_ids[decision.get("no")] = decision.get(
                "id"
            ) or derived_id("decision", project["id"], decision.get("at"), decision.get("text"))

    for index, project in enumerate(state.get("projects") or []):
        wait = project.get("wait") or None
        out["projects"].append(
            {
                "id": project["id"],
                "name": _s(project.get("name")),
                "group_id": project.get("group") or None,
                "type_id": project.get("type") or None,
                "stage": int(project.get("stage") or 0),
                "entered_at": _iso(project.get("enteredAt")),
                "horizon": _s(project.get("when") or "later"),
                "next": _s(project.get("next")),
                "notes": _s(project.get("notes")),
                "pub": _b(project.get("pub", True)),
                "wait_what": _s(wait.get("what")) if wait else None,
                "wait_since": _iso(wait.get("since")) if wait else None,
                "last_act": _iso(project.get("lastAct")),
                "quiet": _b(project.get("quiet")),
                "parked": _b(project.get("parked")),
                "origin": project.get("origin"),
                "template_of": project.get("templateOf"),
                "example": _b(project.get("example")),
                "position": index,
            }
        )
        pid = project["id"]
        for j, item in enumerate(project.get("items") or []):
            out["checklist_items"].append(
                {
                    "id": item.get("id") or derived_id("item", pid, item.get("text")),
                    "project_id": pid,
                    "text": _s(item.get("text")),
                    "done": _b(item.get("done")),
                    "tag": _s(item.get("tag")),
                    "position": j,
                }
            )
        for decision in project.get("decisions") or []:
            supersedes = decision.get("supersedes")
            out["decisions"].append(
                {
                    "id": decision_ids[decision.get("no")],
                    "project_id": pid,
                    "group_id": None,
                    "text": _s(decision.get("text")),
                    "at": _iso(decision.get("at")),
                    "supersedes_id": decision_ids.get(supersedes) if supersedes else None,
                    "superseded": _b(decision.get("superseded")),
                }
            )
        for release in project.get("releases") or []:
            out["releases"].append(
                {
                    "id": release.get("id")
                    or derived_id("release", pid, release.get("v"), release.get("at")),
                    "project_id": pid,
                    "v": _s(release.get("v")),
                    "at": _iso(release.get("at")),
                    "note": _s(release.get("note")),
                }
            )
        for j, person in enumerate(project.get("people") or []):
            out["people"].append(
                {
                    "id": person.get("id")
                    or derived_id("person", pid, person.get("n"), person.get("r")),
                    "project_id": pid,
                    "name": _s(person.get("n")),
                    "role": _s(person.get("r")),
                    "position": j,
                }
            )
        for j, url in enumerate(project.get("links") or []):
            out["links"].append(
                {
                    "id": derived_id("link", "project", pid, url),
                    "project_id": pid,
                    "group_id": None,
                    "url": _s(url),
                    "position": j,
                }
            )
        for j, span in enumerate(project.get("hist") or []):
            out["stage_history"].append(
                {
                    "id": derived_id("hist", pid, span.get("stage"), span.get("from")),
                    "project_id": pid,
                    "stage": _s(span.get("stage")),
                    "from_at": _iso(span.get("from")),
                    "to_at": _iso(span.get("to")),
                    "position": j,
                }
            )
        for j, waited in enumerate(project.get("waitHist") or []):
            out["wait_history"].append(
                {
                    "id": derived_id("wait", pid, waited.get("what"), waited.get("days"), j),
                    "project_id": pid,
                    "what": _s(waited.get("what")),
                    "days": int(waited.get("days") or 0),
                    "position": j,
                }
            )
        for entry in project.get("logs") or []:
            out["log_entries"].append(_log_row(entry, project_id=pid))
        for j, item in enumerate(project.get("files") or []):
            out["files"].append(_file_row(item, j, project_id=pid))

    for group in state.get("groups") or []:
        for entry in group.get("logs") or []:
            out["log_entries"].append(_log_row(entry, group_id=group["id"]))
        for j, item in enumerate(group.get("files") or []):
            out["files"].append(_file_row(item, j, group_id=group["id"]))
        for decision in group.get("decisions") or []:
            out["decisions"].append(
                {
                    "id": decision.get("id")
                    or derived_id("decision", group["id"], decision.get("at"), decision.get("text")),
                    "project_id": None,
                    "group_id": group["id"],
                    "text": _s(decision.get("text")),
                    "at": _iso(decision.get("at")),
                    "supersedes_id": None,
                    "superseded": _b(decision.get("superseded")),
                }
            )

    for index, idea in enumerate(state.get("ideas") or []):
        out["ideas"].append(
            {
                "id": idea["id"],
                "text": _s(idea.get("text")),
                "descr": _s(idea.get("desc")),
                "at": _iso(idea.get("at")),
                "opened": _iso(idea.get("opened")),
                "group_id": idea.get("group") or None,
                "example": _b(idea.get("example")),
                "position": index,
            }
        )

    for index, item in enumerate(state.get("inbox") or []):
        out["inbox"].append(
            {
                "id": item["id"],
                "text": _s(item.get("text")),
                "kind": _s(item.get("type") or "idea"),
                "at": _iso(item.get("at")),
                "guess": item.get("guess") or None,
                "example": _b(item.get("example")),
                "position": index,
            }
        )

    for index, entry in enumerate(state.get("library") or []):
        out["library"].append(
            {
                "id": entry["id"],
                "kind": _s(entry.get("kind") or "link"),
                "title": _s(entry.get("title")),
                "meta": _s(entry.get("meta")),
                "group_id": entry.get("group") or None,
                "file_id": entry.get("file_id") or None,
                "example": _b(entry.get("example")),
                "position": index,
            }
        )

    for entry in state.get("activity") or []:
        out["activity"].append(
            {
                "id": entry.get("id")
                or derived_id("activity", entry.get("pid"), entry.get("at"), entry.get("text")),
                "group_id": entry.get("group") or None,
                "project_id": entry.get("pid") or None,
                "text": _s(entry.get("text")),
                "at": _iso(entry.get("at")),
                "kind": _s(entry.get("kind") or "move"),
                "example": _b(entry.get("example")),
            }
        )

    for item in state.get("libraryFiles") or []:
        out["files"].append(_file_row(item, item.get("position", 0)))

    for template in state.get("templates") or []:
        out["templates"].append(
            {
                "id": template["id"],
                "name": _s(template.get("name")),
                "type_id": template.get("type") or None,
                "payload": template.get("payload") or {},
            }
        )

    settings = {key: state.get(key) for key in SETTING_KEYS if key in state}
    return out, settings


def _log_row(entry: dict, project_id=None, group_id=None) -> dict:
    return {
        "id": entry.get("id")
        or derived_id("log", project_id or group_id, entry.get("at"), entry.get("text")),
        "project_id": project_id,
        "group_id": group_id,
        "text": _s(entry.get("text")),
        "at": _iso(entry.get("at")),
        "stage": _s(entry.get("stage")),
        "highlight": _b(entry.get("highlight")),
    }


def _file_row(item: dict, position: int, project_id=None, group_id=None) -> dict:
    return {
        "id": item.get("id") or derived_id("file", project_id or group_id, item.get("sha256"), item.get("name")),
        "sha256": _s(item.get("sha256")),
        "name": _s(item.get("name")),
        "mime": _s(item.get("mime")),
        "ext": _s(item.get("type")),
        "size": int(item.get("size") or 0),
        "added_at": _iso(item.get("added_at")),
        "project_id": item.get("project_id", project_id),
        "group_id": item.get("group_id", group_id),
        "doc_id": _s(item.get("doc_id")),
        "version": _s(item.get("version")),
        "descr": _s(item.get("descr")),
        "stage": _s(item.get("stage")),
        "previous_file_id": item.get("previous_file_id"),
        "superseded": _b(item.get("superseded")),
        "example": _b(item.get("example")),
        "position": position,
    }


COLLECTIONS = (
    "groups",
    "types",
    "projects",
    "checklist_items",
    "decisions",
    "releases",
    "people",
    "links",
    "stage_history",
    "wait_history",
    "log_entries",
    "ideas",
    "inbox",
    "library",
    "activity",
    "files",
    "templates",
)

# Columns holding JSON rather than a scalar.
JSON_COLUMNS = {"types": ("stages", "checks"), "templates": ("payload",)}


# --------------------------------------------------------------- rows to state


def number_decisions(rows: list[dict]) -> dict[str, int]:
    """Decision numbers are display only and derived, never stored.

    Ordered by when the decision was made, then by the device that made it, so
    every device arrives at the same dense numbering from the same records.
    """
    live = [r for r in rows if not r.get("deleted")]
    live.sort(key=lambda r: (r.get("at") or "", r.get("updated_by") or "", r["id"]))
    return {row["id"]: index + 1 for index, row in enumerate(live)}


def rebuild(rows: dict[str, list[dict]], settings: dict) -> dict:
    """Put the records back together into the document the interface holds."""
    by_project: dict[str, dict[str, list]] = {}

    def bucket(collection: str, key: str = "project_id"):
        grouped: dict[str, list[dict]] = {}
        for row in rows.get(collection, []):
            owner = row.get(key)
            if owner:
                grouped.setdefault(owner, []).append(row)
        for items in grouped.values():
            items.sort(key=lambda r: (r.get("position", 0), r.get("created_at") or ""))
        return grouped

    items = bucket("checklist_items")
    releases = bucket("releases")
    people = bucket("people")
    project_links = bucket("links")
    group_links = bucket("links", "group_id")
    hist = bucket("stage_history")
    waits = bucket("wait_history")
    project_logs = bucket("log_entries")
    group_logs = bucket("log_entries", "group_id")
    project_files = bucket("files")
    group_files = bucket("files", "group_id")
    project_decisions = bucket("decisions")
    group_decisions = bucket("decisions", "group_id")

    numbers = number_decisions(rows.get("decisions", []))

    def decision_view(row: dict) -> dict:
        supersedes = row.get("supersedes_id")
        return {
            "id": row["id"],
            "no": numbers.get(row["id"], 0),
            "text": row.get("text") or "",
            "at": row.get("at"),
            "supersedes": numbers.get(supersedes) if supersedes else None,
            "superseded": bool(row.get("superseded")),
        }

    def file_view(row: dict) -> dict:
        return {
            "id": row["id"],
            "sha256": row.get("sha256"),
            "name": row.get("name") or "",
            "mime": row.get("mime") or "",
            "type": row.get("ext") or "",
            "size": row.get("size") or 0,
            "added_at": row.get("added_at"),
            "project_id": row.get("project_id"),
            "group_id": row.get("group_id"),
            "doc_id": row.get("doc_id") or "",
            "version": row.get("version") or "",
            "descr": row.get("descr") or "",
            "stage": row.get("stage") or "",
            "previous_file_id": row.get("previous_file_id"),
            "superseded": bool(row.get("superseded")),
            "example": bool(row.get("example")),
            "meta": _file_meta(row),
        }

    def log_view(row: dict) -> dict:
        return {
            "id": row["id"],
            "text": row.get("text") or "",
            "at": row.get("at"),
            "stage": row.get("stage") or "",
            "highlight": bool(row.get("highlight")),
        }

    ordered = sorted(
        rows.get("projects", []), key=lambda r: (r.get("position", 0), r.get("created_at") or "")
    )
    projects = []
    for row in ordered:
        pid = row["id"]
        wait = None
        if row.get("wait_what"):
            wait = {"what": row["wait_what"], "since": row.get("wait_since")}
        projects.append(
            {
                "id": pid,
                "name": row.get("name") or "",
                "group": row.get("group_id") or "",
                "type": row.get("type_id") or "",
                "stage": row.get("stage") or 0,
                "enteredAt": row.get("entered_at"),
                "when": row.get("horizon") or "later",
                "next": row.get("next") or "",
                "items": [
                    {"id": r["id"], "text": r.get("text") or "", "done": bool(r.get("done")),
                     "tag": r.get("tag") or ""}
                    for r in items.get(pid, [])
                ],
                "decisions": [decision_view(r) for r in project_decisions.get(pid, [])],
                "files": [file_view(r) for r in project_files.get(pid, [])],
                "links": [r.get("url") or "" for r in project_links.get(pid, [])],
                "notes": row.get("notes") or "",
                "pub": bool(row.get("pub")),
                "wait": wait,
                "lastAct": row.get("last_act"),
                "releases": [
                    {"id": r["id"], "v": r.get("v") or "", "at": r.get("at"), "note": r.get("note") or ""}
                    for r in releases.get(pid, [])
                ],
                "people": [
                    {"id": r["id"], "n": r.get("name") or "", "r": r.get("role") or ""}
                    for r in people.get(pid, [])
                ],
                "hist": [
                    {"stage": r.get("stage") or "", "from": r.get("from_at"), "to": r.get("to_at")}
                    for r in hist.get(pid, [])
                ],
                "logs": [log_view(r) for r in project_logs.get(pid, [])],
                "quiet": bool(row.get("quiet")),
                "origin": row.get("origin"),
                "parked": bool(row.get("parked")),
                "templateOf": row.get("template_of"),
                "example": bool(row.get("example")),
                "waitHist": [
                    {"what": r.get("what") or "", "days": r.get("days") or 0}
                    for r in waits.get(pid, [])
                ],
            }
        )

    groups = []
    for row in sorted(rows.get("groups", []), key=lambda r: (r.get("position", 0), r.get("created_at") or "")):
        gid = row["id"]
        groups.append(
            {
                "id": gid,
                "name": row.get("name") or "",
                "color": row.get("color") or "",
                "priv": bool(row.get("priv")),
                "description": row.get("description") or "",
                "links": [r.get("url") or "" for r in group_links.get(gid, [])],
                "logs": [log_view(r) for r in group_logs.get(gid, [])],
                "files": [file_view(r) for r in group_files.get(gid, [])],
                "decisions": [decision_view(r) for r in group_decisions.get(gid, [])],
            }
        )

    def plain(collection: str, shape):
        return [
            shape(r)
            for r in sorted(
                rows.get(collection, []),
                key=lambda r: (r.get("position", 0), r.get("created_at") or ""),
            )
        ]

    state = {
        "groups": groups,
        "types": plain(
            "types",
            lambda r: {
                "id": r["id"],
                "name": r.get("name") or "",
                "stages": r.get("stages") or [],
                "check": r.get("checks") or {},
            },
        ),
        "projects": projects,
        "ideas": plain(
            "ideas",
            lambda r: {
                "id": r["id"], "text": r.get("text") or "", "desc": r.get("descr") or "",
                "at": r.get("at"), "opened": r.get("opened"), "group": r.get("group_id") or "",
                "example": bool(r.get("example")),
            },
        ),
        "inbox": plain(
            "inbox",
            lambda r: {
                "id": r["id"], "text": r.get("text") or "", "type": r.get("kind") or "idea",
                "at": r.get("at"), "guess": r.get("guess"), "example": bool(r.get("example")),
            },
        ),
        "library": plain(
            "library",
            lambda r: {
                "id": r["id"], "kind": r.get("kind") or "link", "title": r.get("title") or "",
                "meta": r.get("meta") or "", "group": r.get("group_id") or "",
                "file_id": r.get("file_id"), "example": bool(r.get("example")),
            },
        ),
        "activity": sorted(
            [
                {
                    "id": r["id"], "group": r.get("group_id") or "", "pid": r.get("project_id") or "",
                    "text": r.get("text") or "", "at": r.get("at"), "kind": r.get("kind") or "move",
                    "example": bool(r.get("example")),
                }
                for r in rows.get("activity", [])
            ],
            key=lambda a: a.get("at") or "",
            reverse=True,
        ),
        "libraryFiles": [
            file_view(r)
            for r in sorted(
                [r for r in rows.get("files", []) if not r.get("project_id") and not r.get("group_id")],
                key=lambda r: (r.get("position", 0), r.get("created_at") or ""),
            )
        ],
        "templates": plain(
            "templates",
            lambda r: {"id": r["id"], "name": r.get("name") or "",
                       "type": r.get("type_id"), "payload": r.get("payload") or {}},
        ),
    }
    for key in SETTING_KEYS:
        if key in settings:
            state[key] = settings[key]
    return state


def _file_meta(row: dict) -> str:
    """The one line a file row shows under its name."""
    bits = []
    if row.get("doc_id"):
        bits.append(row["doc_id"])
    if row.get("version"):
        bits.append(row["version"])
    if not bits:
        bits.append(human_size(row.get("size") or 0))
    return " · ".join(bits)


def human_size(num: int) -> str:
    value = float(num)
    for unit in ("bytes", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{int(value)} bytes"
            return f"{value:.1f} {unit}".replace(".0 ", " ")
        value /= 1024
    return f"{value:.1f} GB"
