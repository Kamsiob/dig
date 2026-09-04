"""Opening the data, in the one way both the app and the tests do it.

Migration, then the read, then the two things that can go wrong with a file
that is nonetheless intact: it was written by a newer Dig, or it cannot be
opened at all. Neither is a reason to show a traceback or to write over it.
"""

from __future__ import annotations

from dig.store import LoadResult, SchemaTooNewError, Store


def open_state(store: Store) -> LoadResult:
    """Bring v1 across if it is there, then read, saying plainly what happened."""
    from dig.migrate_v1 import migrate_if_needed

    try:
        notice = migrate_if_needed(store)
    except Exception:
        notice = (
            "Dig found data from version 1 but could not bring it across."
            " Nothing was deleted."
        )

    try:
        result = store.load()
    except SchemaTooNewError as exc:
        # Intact, just newer than this build. Say so and touch nothing.
        store.read_only = True
        return LoadResult(state=None, notice=f"{exc} Dig has not changed it.")
    except Exception as exc:
        return LoadResult(state=None, notice=str(exc), recovered=True)

    if notice and not result.notice:
        result.notice = notice
    return result
