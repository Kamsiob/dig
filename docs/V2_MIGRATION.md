# v1 to v2 migration

Dig v1 stored a normalized SQLite database: ideas, apps, per-app feature and bug
sheets, and managed attachments. Dig v2 stores one record per thing across a
table per collection, with an append only log of every change, and keeps files
by their SHA256 in a blob store. This document describes exactly how the old
data becomes the new data.

The migration runs once, on first launch, when a v1 database is found at
`~/.local/share/dig/dig.db`. The original file is kept as
`~/.local/share/dig/dig-v1.db.bak` and never written to again.

## How v1 is recognized

A v1 database has an `apps` table and no `projects` table. A v2 database has a
`projects` table. If both are somehow present, v2 wins and no migration runs.

## What maps to what

### Settings

| v1 | v2 |
|---|---|
| `settings.appearance` (`light` / `dark` / `system`) | `state.theme` |
| `settings.window_geometry` (Qt base64 blob) | dropped; v2 stores `ui.window` as plain numbers |
| `settings.schema_version` | dropped; v2 keeps its own `schema_version` in `meta` |

`state.org` is set to the machine's full name if one is readable, otherwise
`"Your projects"`. `state.you` is set to the first word of that name. Both are
editable in Settings on the first run, and Setup is not forced on a migrated
install: `setupDone` is set to true because the person already has data.

### Groups

v1 had no grouping. The migration creates one group so nothing is left homeless:

| Field | Value |
|---|---|
| `id` | `apps` |
| `name` | `Apps` |
| `color` | `#0BA39E` (teal, the v2 default for an Apps group) |
| `priv` | `false` |

Every migrated project lands in it. Groups are fully editable in Settings
afterward.

### Types

The migration creates the v2 App type exactly as SPEC 3.1 defines it, so a
migrated install and a fresh Apps install are identical:

- `id`: `app`, `name`: `App`
- stages: Idea, Plan, Design, Build, Test, Release, Keep up
- checklist suggestions: Plan `Write the spec`; Design `Approve the mockup`,
  `Write DESIGN.md`; Build `Make the repo public`, `Keep HANDOFF.md current`;
  Test `Test on a real device`; Release `Store listing live`,
  `Publish the release post`; Keep up `Review the bug list`

### Ideas

Each `ideas` row becomes one entry in `state.ideas`:

| v1 column | v2 field |
|---|---|
| `title` | `text` |
| `note` | `desc` |
| `created_at` | `at` |
| `last_opened_at` | `opened` (null when never opened) |
| (none) | `group`: `""` |

An idea whose `promoted_app_id` is set was already turned into an app in v1. It is
**not** carried into `state.ideas`, because v2 removes an idea from Ideas when it
is started as a project. Its title is written to the resulting project's `origin`
field instead, which is what produces the "Started as an idea" callout.

### Apps become projects

Each `apps` row becomes one entry in `state.projects`:

| v1 column | v2 field |
|---|---|
| `name` | `name` |
| `notes` | `notes` |
| `description` | appended to `notes` when `notes` is empty, so nothing is lost |
| `github_url` | one entry in `links[]` when it is not empty |
| `created_at` | `enteredAt` and `lastAct` |
| `shipped` | decides `stage` (see below) |
| `origin_idea_id` | `origin`: the title of that idea |
| (none) | `group`: `apps`, `type`: `app` |

Stage and horizon:

| v1 `shipped` | v2 `stage` | v2 `when` | v2 `quiet` |
|---|---|---|---|
| 1 | 6 (`Keep up`, the last stage) | `done` | `true` |
| 0 | 3 (`Build`) | `next` | `false` |

Rationale: a shipped v1 app is one being kept up, which is the last App stage and
therefore finished by v2's rules. An unshipped v1 app is one being built, which is
the App stage that matches what v1 actually tracked (features and bugs).

`version_label`, when it is not empty, becomes a single release:
`{v: version_label, at: created_at, note: "Carried over from Dig v1"}`.

Every other project field starts empty: `next: ""`, `decisions: []`, `people: []`,
`hist: []`, `wait: null`, `waitHist: []`, `parked: false`. `pub` is `true`,
because the `Apps` group is not private.

### Feature and bug sheets become checklist items

Each `sheet_items` row becomes one entry in that project's `items[]`:

| v1 column | v2 field |
|---|---|
| `text` | `text` |
| `done` | `done` |
| `kind` = `bug` | `tag`: `"bug"` |
| `kind` = `feature` | `tag`: `""` |

`created_at` and `done_at` have no home in the v2 item shape and are dropped. The
`tag` value `"exp"` is never produced by migration; it only appears when someone
clicks a stage's suggested item into existence.

### Attachments become files

v2 keeps files by what they are rather than by what they are called: every file
is hashed and stored once under `~/.local/share/dig/blobs/` by its SHA256, and a
file record points at that hash. Two records holding the same bytes cost one
copy, and renaming a file or moving it between projects never touches the bytes.

Each v1 `attachments` row becomes one file record:

| v1 column | v2 field |
|---|---|
| `filename` | `name` |
| `stored_path` | read, hashed, and copied into the blob store; the record keeps `sha256` |
| `size` | `size`, re-measured from the bytes that were actually copied |
| `added_at` | `added_at` |

`type` is the file's extension in upper case, capped at four characters, which is
what the file type chip shows. A file with no extension gets `FILE`. `mime` is
detected from the name.

v1's `~/.local/share/dig/attachments/` folder is **left exactly as it was**. The
bytes are copied, never moved, so a migration that goes wrong cannot cost anyone
a file. A v1 record whose file is already missing from disk still becomes a
record, with an empty hash, so nothing silently disappears.

### Everything with no v1 equivalent

`inbox`, `library`, `activity`, and `state.ideas` entries for promoted ideas all
start empty. v1 recorded no decisions, waits, releases beyond `version_label`,
people, or stage history, so none are invented. The week report on a freshly
migrated install correctly says nothing happened.

### The database itself

v1's tables carry some of the same names as v2's with a different shape, so the
v2 database is not built on top of the v1 file. The original is copied to
`dig-v1.db.bak` first, then `dig.db` is replaced by a fresh v2 database. If
anything fails after that point, the backup is copied back so the next launch
can try again.

## After the migration

The new state is written through the normal save path, so the first history
snapshot is the migrated state. A toast confirms in plain words what came
across, for example: "Brought 1 app and 0 ideas over from Dig v1. The old file is
kept as dig-v1.db.bak."

If the migration fails for any reason, v1's file is left exactly where it is,
nothing is deleted, and the app starts on a fresh v2 state with a toast that says
so. The failure never costs the person their v1 data.
