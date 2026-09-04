"""Reading projects and ideas out of a CSV somebody else's tool wrote.

Nothing is written until the person has seen what Dig thinks each column is and
what the first few rows will become.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

PROJECT_FIELDS = ("name", "group", "type", "stage", "next")
IDEA_FIELDS = ("text", "notes", "group")

# What a column is probably called, whoever exported it.
GUESSES = {
    "name": ("name", "project", "title", "project name"),
    "group": ("group", "category", "client", "area", "folder"),
    "type": ("type", "kind", "template"),
    "stage": ("stage", "status", "state", "phase", "column"),
    "next": ("next", "next step", "action", "todo", "task"),
    "text": ("text", "idea", "title", "name", "summary"),
    "notes": ("notes", "note", "description", "detail", "details"),
}


def sniff(text: str) -> tuple[list[str], list[list[str]]]:
    """Header and rows. Handles commas, semicolons, and tabs."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(str(c).strip() for c in r)]
    if not rows:
        return [], []
    return [str(c).strip() for c in rows[0]], rows[1:]


def guess_mapping(header: list[str], fields: tuple) -> dict:
    """Which column probably holds which field."""
    lowered = [h.strip().lower() for h in header]
    mapping = {}
    for field in fields:
        for candidate in GUESSES.get(field, (field,)):
            if candidate in lowered:
                mapping[field] = lowered.index(candidate)
                break
        else:
            mapping[field] = -1
    # A single column file is the thing itself.
    first = fields[0]
    if mapping.get(first, -1) < 0 and header:
        mapping[first] = 0
    return mapping


def preview(text: str, kind: str, mapping: dict | None = None, limit: int = 5) -> dict:
    """What Dig would make of this file, without making anything."""
    fields = PROJECT_FIELDS if kind == "projects" else IDEA_FIELDS
    header, rows = sniff(text)
    if not header:
        return {"ok": False, "reason": "That file has nothing in it."}
    mapping = mapping or guess_mapping(header, fields)

    def take(row, field):
        index = mapping.get(field, -1)
        if index is None or index < 0 or index >= len(row):
            return ""
        return str(row[index]).strip()

    made = []
    for row in rows[:limit]:
        made.append({field: take(row, field) for field in fields})
    named = [r for r in rows if take(r, fields[0])]
    return {
        "ok": True,
        "header": header,
        "fields": list(fields),
        "mapping": mapping,
        "rows": made,
        "total": len(named),
        "skipped": len(rows) - len(named),
    }


def read_all(text: str, kind: str, mapping: dict) -> list[dict]:
    """Every row, as plain dictionaries. Rows with no name are left out."""
    fields = PROJECT_FIELDS if kind == "projects" else IDEA_FIELDS
    _, rows = sniff(text)

    def take(row, field):
        index = mapping.get(field, -1)
        if index is None or index < 0 or index >= len(row):
            return ""
        return str(row[index]).strip()

    out = []
    for row in rows:
        made = {field: take(row, field) for field in fields}
        if made[fields[0]]:
            out.append(made)
    return out
