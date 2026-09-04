# Dig v2: combined addendum

This is the combined addendum to the Dig v2 build prompt. It supersedes any separate addendums you may have received. Everything in the original prompt still applies except where this document changes it.

It adds: a first-run onboarding; the requirement that the published app ships as a clean empty shell with none of my personal data; publishing to GitHub; replacing the old version on my computer; sync-ready foundations and a private sync server for a future Android app; a complete file system for any file type with in-app viewing and re-download; and a set of missing features that make Dig a real solo operator's project, program, and portfolio tool. Part 8 says exactly where each part slots into the phased build plan.

Read all of it before starting Phase 1, because Parts 5A and 6 change the storage design and must be built from the start rather than retrofitted.

Dig's philosophy still holds everywhere: no boards, no drag-and-drop, no priorities, no due dates on tasks, no dependencies, no assignees, no time tracking, no money, no notifications, no accounts, no cloud, no AI. Every feature below must respect that, and every screen must match the prototype's design language: same tokens, type, motion, copy voice, both themes, keyboard accessible, reduced-motion safe. American English, no em dashes anywhere.

---

## Part 1: Onboarding

Dig currently drops people into the app with no explanation. Build a real first-run onboarding. It runs only when `setupDone` is false and can be replayed from Settings via "Run setup again" without touching existing data. Progress dots, Back and Continue, and a Skip that jumps to the end and applies defaults.

1. **Welcome.** Headline: "Dig keeps every project you're working on in one place." Three short lines: what stage each one is at, what its next step is, and what you decided along the way. One plain line: everything stays on this computer, there are no accounts, and by default the app never touches the internet.
2. **Who this is for.** Two optional fields: what to call this (organization or your own name) and your first name for the greeting. Sensible fallbacks if skipped.
3. **What you work on.** The checkbox set from SPEC section 3.1 that creates matching groups, project types, stages, and stage checklists, with a live plain-language preview under the checkboxes of what will be created, and a note that all of it is editable later.
4. **Start empty, or look around first.** Starting empty is the default and creates nothing. The other choice loads a small generic example set: roughly four projects across two groups, a few ideas, one waiting item, one inbox item, two decisions, one log entry, one file. Examples must be completely generic and contain none of my work ("Website refresh", "New client onboarding", "Kitchen renovation", "Quarterly report"). Settings gets a "Remove the examples" button that deletes every example record in one click and hides itself once none remain.
5. **Three things to know.** Ctrl K adds anything from anywhere. Projects move through stages, and you decide when. Nothing leaves this computer unless you turn on sync between your own devices. A "See all shortcuts" link opens the shortcuts card; the last button opens Home.

After onboarding, a dismissible "Start here" card sits at the top of Home for the first session only: add your first project, capture something with Ctrl K, set a next step. Each ticks itself when the person does it. It disappears when all three are done or when dismissed, and never returns. No tooltips, coach marks, or modal tours anywhere else; the empty states do the teaching.

**Tests:** appears once on a fresh profile; each work-kind creates exactly the documented defaults; examples load and fully remove; skip applies defaults; replay does not duplicate or destroy data; the Start here card ticks and disappears.

---

## Part 2: The published app is an empty shell with none of my data

The prototype in `docs/handoff-v2` contains my real projects, groups, clients, collaborators, decisions, and notes. It is a design reference only. None of it may ship in the application or reach GitHub.

1. First launch state is empty: no organization name, no groups, no project types beyond what onboarding creates, no projects, ideas, library entries, inbox items, activity, people, log entries, or files. Delete the prototype's seed data from the shipped JavaScript. The only built-in data is the generic example set from onboarding.
2. Before committing anything from the handoff folder, replace the prototype's seed data with that same generic example set. If impractical, do not commit the prototype at all: keep it locally and commit only the markdown documents, with a line in that folder's README saying the prototype is kept locally because it contained real data.
3. Scan the working tree and full git history for personal data: my real project names, client and organization names other than my own brand, people's names, addresses, device or host names, Tailscale addresses or IPs, absolute paths containing my username, any email other than the public support address, anything resembling a key or token, and any exported JSON, database, or blob. Report what you find. If anything sensitive is already in committed history, stop and tell me what and where with options; never rewrite or force-push history without my say-so.
4. `.gitignore` must exclude the runtime database, blobs, state history, backups, exported files, venvs, build artifacts, and screenshot staging.
5. Keep my public brand identity, which is intentional: Kamsiob, https://youtube.com/@kamsiob, https://github.com/kamsiob, https://kamsiob.com, https://buymeacoffee.com/kamsiob, https://t.me/+g5LKm9rUnNcxMjk5, hello@kamsiob.com, AGPLv3, and the support line already specified for the About dialog. None of that is personal data to strip.
6. README screenshots use the generic example data only, in a throwaway profile, and must not show a path containing my username.
7. Verify by launching the built app with a temporary empty home: it opens onboarding, shows no data, and makes no network requests.

---

## Part 5A: Sync-ready data model

Build in Phase 1. This replaces the single JSON document in SPEC section 1.

1. **Identifiers:** every record gets a globally unique id (UUIDv4 or ULID) generated by whichever device creates it. Remove the sequential counter from the prototype.
2. **Per-record storage:** a table per collection (groups, types, projects, ideas, inbox, library, activity, log entries, files, blobs, people, decisions, releases, checklist items, links, wait history, stage history, group-level notes/links/decisions, devices, conflicts) with proper parent ids. The UI may still hold the whole state as one object; only persistence changes.
3. **Sync metadata on every row:** `created_at`, `updated_at`, `updated_by` (device id), `rev`, `deleted`, `deleted_at`. Deletes are tombstones, never hard deletes; purge tombstones only after 90 days and acknowledgment by every known device.
4. **An append-only oplog** (`seq`, `collection`, `record_id`, `rev`, `op`, `payload`, `at`, `device`). Every write goes through one function that updates the row and appends to the log in the same transaction.
5. **Device identity table:** this device's id and name, and the last cursor seen from every other known device.
6. **Files are content-addressed:** blobs stored under a blobs folder by SHA256, with file records pointing at the hash (see Part 6 for the full file model).
7. **Decision numbers:** the number is display-only and derived; identity is the uuid. On merge, order by `created_at` then device id and recompute numbers so they stay dense and stable. Never key anything off the number. Document it.
8. **Schema version** stamped in the database and included in every sync exchange; incompatible clients are refused, never allowed to corrupt.
9. Migrate the existing v1 database into this schema; keep atomic writes, debounce, rolling history, and corrupt-file recovery.
10. **Tests:** id uniqueness under concurrent creation; oplog captures every mutation exactly once; tombstones survive round trips and suppress resurrection; blob deduplication; deterministic decision renumbering; schema mismatch refused cleanly.

---

## Part 6: Files, any type, view in-app, get them back out

Files are first-class. Everything below builds on the content-addressed blob store from Part 5A.

### 6.1 What a file is

A file record has: uuid, blob hash, display name, detected type (MIME), extension, size, `added_at`, added_by device, an optional document id (free text, for things like BCP-HT-FSD-001), an optional version label (free text like v1.1), an optional one-line description, an optional stage it belongs to (one of the parent project's stage names) so the project roadmap can stamp it where it was produced, and a `previous_file_id` link for versions. It attaches to exactly one owner: a project, a group, or the Library (unowned). Moving a file between owners is a metadata change, not a copy.

### 6.2 Getting files in

- On any project page, any group page, and the Library: an "Add files" button opening the native file picker with multi-select; drag-and-drop anywhere onto that page (a full-page drop highlight in the design language appears while dragging); and paste from the clipboard (Ctrl V with an image or file on the clipboard) which creates a file named with the date and time.
- Every file added is copied into the blob store, hashed, and deduplicated. The original is never referenced in place and never modified.
- Adding a file whose display name matches an existing file on the same owner asks: "Replace as a new version" (creates a new record linked to the old one, both kept, the old shown as superseded) or "Keep both" (adds a numeric suffix). Never overwrite silently.
- Large files are copied off the main thread with a quiet progress indicator; nothing blocks. Warn once, without preventing, when a single file is over 250 MB.

### 6.3 Viewing files in-app

Clicking any file opens a viewer as a popup window inside the app (same dialog language, larger, with a close X, Esc to close, and left/right arrows to move between files of the same owner). The viewer shows the name, type, size, added date, document id, version, description, and stage at the top, with inline editing of the editable fields.

- **Images** (png, jpg, gif, webp, svg, bmp, heic if decodable): shown fit-to-window with zoom to 100% on click and pan when zoomed.
- **PDF:** rendered in-app using QtWebEngine's built-in PDF viewer (enable the PdfViewer setting), with page navigation and text search.
- **Text, Markdown, code, JSON, CSV, logs:** shown monospace with line numbers; Markdown offers a rendered toggle; CSV shows as a simple table.
- **Audio and video** (mp4, webm, mp3, ogg, wav, m4a where the engine supports it): an HTML5 player.
- **Office formats and everything else:** no inline preview; the viewer shows the metadata, a large "Open with the system app" button, and "Save a copy".
- Every viewer has: "Open with the system app", "Save a copy…" (native save dialog, writes the exact original bytes from the blob, default name is the display name), "Reveal in folder" (opens the blob's containing folder), "Copy path", version history when the file has versions, "Move to…" (another project, a group, or the Library), and "Delete" (tombstone, goes to Recently deleted, undoable).
- Viewing never modifies the blob. The viewer works with no network.

### 6.4 Getting files back out

- "Save a copy…" on any file, as above.
- "Save all files…" on a project or group: writes a zip named after the project with the files inside, using display names, with a `manifest.csv` listing name, document id, version, size, added date, and SHA256.
- Full backup: see Part 7.9. The JSON export alone is not a backup because it does not contain blobs; the Settings copy must say so and point to the full backup.

### 6.5 Where files appear

- **Project page, Work tab:** the Files rail lists files newest first with type chip, name, version, and size; "Add files" and drag-and-drop. Files that belong to a stage also appear stamped on that stage in the project's Roadmap tab.
- **Group page** (Part 7.1): its own Files section.
- **Library:** unowned files, with the same chips, plus "put in a project or group".
- **Search** (Find anything) matches file names, document ids, and descriptions. For text, Markdown, and CSV files under 2 MB, also index their contents so a search can find a phrase inside a spec.

### 6.6 Storage housekeeping

- Settings, Your data: total blob size, number of files, number of unreferenced blobs (blobs no live record points to), and "Clean up unreferenced files" which removes only blobs referenced by nothing, including tombstoned records older than 30 days, after a confirmation stating the size to be freed.
- **Tests:** add via picker, drop, and paste; deduplication of identical bytes; version replace vs keep both; every viewer type renders or falls back correctly; save a copy is byte-identical to the original; save all files produces a correct zip and manifest; move between owners; delete to Recently deleted and restore; cleanup never removes a referenced blob.

---

## Part 7: The holes, filled

### 7.1 Group pages (the program and portfolio level)

A group is currently only a filter. Give every group its own page, reached by clicking the group name anywhere. Header: color square, name, private/shareable badge, project count, "Edit" (name, color, visibility). Sections: a short description (editable, saves as you type); Standing, which lists the group's projects by stage with counts per stage and a compact stage bar per project; the group's roadmap (the existing roadmap filtered to this group, embedded); Files (Part 6); Links; Decisions at the group level (same numbering scheme, same dialog) for choices that span projects; Log (7.3) at the group level; and Recent activity. Share: a group one-pager PDF with description, standing, roadmap, and recent releases, excluding private projects and stating so.

### 7.2 Reports beyond a week

"Your week" becomes "Your review" with a period control: This week, Last week, This month, Last month, This quarter, and a custom range. Scope control: everything or one group. Sections and KPIs as today, plus Released (releases in the period), Files issued (files with a version or document id added in the period), and Log highlights (log entries marked as highlights). Save as PDF for any period and scope; private groups hidden by default with the count stated. The report never invents anything; empty sections say so.

### 7.3 The log (dated progress notes)

Add a dated log to every project and group: short entries with a timestamp, plain text, and an optional "highlight" mark. Add one from the project page (a single-line input at the top of the Record tab, Enter saves, Shift+Enter for a new line), from the capture dialog (a new type, Log, routed to the chosen project), and from the command line (7.6). Entries show newest first in the Record tab, appear on the project's Roadmap timeline inside the stage they were written in, and feed Your review. This is separate from the single Notes field, which stays as the standing notes.

### 7.4 Duplicate and templates

"Duplicate project" on any project creates a copy with the same group, type, links, people, and checklist items reset to not done, no files, no decisions, no log, at stage one, named "Copy of …" with the name field focused. "Save as template" saves the project's type, checklist items, links, and people as a named template; New project offers "Start from a template". Templates are edited in Settings.

### 7.5 Recently deleted

Deleting a project, idea, library entry, file, decision, release, or log entry sends it to Recently deleted (it is a tombstone from Part 5A) where it stays for 30 days and can be restored in one click, then is purged per the tombstone rule. Settings gets a "Recently deleted" section listing them with type, name, when, and Restore. Every delete confirms once; the toast offers Undo. Nothing is ever permanently gone by accident.

### 7.6 Command-line entry and single instance

The app runs as a single instance. A second launch hands its arguments to the running instance and exits. Provide `dig add "text"` which captures into the inbox (or with `--project "name"` onto that project's checklist, with `--log` for a log entry, `--idea`, `--bug`, `--link`, `--note`) and `dig open "project name"`. Document in the README how to bind a KDE custom shortcut to `dig add`, which is the honest way to get a system-wide quick capture on Wayland without an in-app global key grab. Show a toast in the running app when something arrives this way.

### 7.7 Quiet projects, surfaced gently

An active, non-waiting, non-parked project with no activity, no log entry, and no checklist change for 21 days is "quiet". Show quiet projects only in Your review under a section "Gone quiet", and as a soft gray line under the Up next section on Home reading "N projects have gone quiet" that links to the Projects screen filtered to them. No badges, no nagging.

### 7.8 People, across projects

Keep people as name and role per project. Add a read-only People screen reachable from Settings that lists every distinct name with the projects they appear on, so the same reviewer or client is visible across the portfolio. No contact fields, no notes on people, no CRM.

### 7.9 Backup and restore, complete

Settings, Your data: "Back up everything…" writes a single zip containing the database export as JSON, every blob, templates, and a manifest with schema version and date, to a chosen location. "Restore from a backup…" reads such a zip, shows what it contains and its date, warns that it replaces the current data, and requires typing RESTORE to proceed; it makes a backup of the current data first, automatically. Optional scheduled backup: a folder and a cadence (daily, weekly), off by default, run quietly on launch when due, keeping the last 10.

### 7.10 Import from elsewhere

"Import from CSV…" in Settings accepts a CSV of projects (name, group, type, stage, next step) and a CSV of ideas (text, notes, group), with a preview and column mapping before anything is written, creating missing groups and types as needed.

### 7.11 Text size and accessibility

Settings, Appearance: a text size control (Small, Default, Large, Larger) that scales the interface. Every interactive element has an accessible name; every icon-only control has a label for screen readers; focus order is logical on every screen and dialog; contrast meets WCAG AA in both themes (verify with a checker and fix any failure).

### 7.12 Not planned

An in-app "Not planned" screen, reached from About, listing what Dig deliberately does not do and why, in one sentence each: boards and drag-and-drop, due dates on tasks, priorities, assignees, time tracking, money and invoicing, notifications, accounts and cloud, AI. Framed as decisions, not apologies. Also a short "Being considered" list with no dates and no promises: encryption at rest with a passphrase, an Android companion, more file previews.

---

## Part 5B: The sync server on my machine

My computer is the server. It publishes nothing publicly. The connection between my phone and my computer runs over Tailscale, which already provides an encrypted private network and device identity.

1. A local HTTP server inside the desktop app, off by default, started only when I turn it on in Settings. Bind to the Tailscale interface address and loopback only, never 0.0.0.0, never a public interface. If the Tailscale interface is absent, refuse to start and say why in plain language. Default port 8787, configurable.
2. **Pairing and authorization**, on top of Tailscale. Settings, "Sync with my other devices": "Pair a device" generates a one-time code and a QR code containing address, port, and code, valid five minutes, single use. Paired devices are stored with id, name, token, paired at, last synced; any device can be revoked with one click, immediately invalidating its token. No accounts, passwords, or third-party services.
3. **API**, versioned under `/v1`, JSON over HTTP:

   | Endpoint | Purpose |
   |---|---|
   | `GET /v1/hello` | identity, schema version, server version, device name |
   | `POST /v1/pair` | exchange a one-time code for a device token |
   | `GET /v1/changes?since=cursor` | ordered changes after a cursor, paginated, with a next cursor |
   | `POST /v1/changes` | push a batch, returns per-record accept or conflict |
   | `GET /v1/blobs/{sha256}` | download, supporting HTTP range requests |
   | `POST /v1/blobs/{sha256}` | upload, chunked and resumable, verified by hash |
   | `GET /v1/state` | full snapshot for a first sync |

   All authenticated with the device token; every request logged locally with device, time, and outcome.
4. **Conflict policy**, implemented and documented: last write wins per field by `updated_at` with device id as tiebreaker; checklist items, decisions, releases, people, files, log entries, and links merge additively by id; a delete beats a concurrent edit; a delete racing an edit keeps the tombstone but writes the conflicting version to a conflicts table surfaced in Settings so nothing is silently lost.
5. **Sync status in the UI:** one line in the sidebar footer with the server state, and the Settings panel listing paired devices, last sync each, port, bound address, pairing and revoke controls. Nothing else.
6. **A conformance test client** under `tools/sync-client`, in Python, acting as a fake second device: pairs, pulls a snapshot, edits, pushes, pulls back, uploads and downloads a blob, and prints pass or fail. This is how I will validate the Android app later.
7. **Tests using it:** first sync from empty; incremental both ways; concurrent edits to the same field and to different fields; a delete racing an edit; an offline device catching up after many changes; blob upload and resumed download with hash verification; a revoked token refused; an unpaired device refused; a schema mismatch refused; a large batch not blocking the interface.
8. **`docs/SYNC.md`:** schema, oplog, API with examples, conflict rules, pairing flow, and a section "What the Android client must implement", complete enough to build the client from alone.

---

## Part 5C: Honest copy

The default build makes no outbound internet requests of any kind, has no accounts, and no cloud. Sync is off by default, and when turned on it is a direct connection between the person's own devices on their own private network, with nothing passing through anyone else's servers. Say exactly that, no more and no less, in the onboarding welcome step, the Settings data section, the README privacy section, and the About dialog.

---

## Part 3: Publish to GitHub so anyone can get it

1. **Repository settings:** one-line description; website https://kamsiob.com; topics such as linux, pyside6, qt, local-first, project-management, portfolio, agplv3, privacy, desktop-app, no-cloud. AGPLv3 detected by GitHub.
2. **README for a stranger:** one sentence on what Dig is and who it is for; screenshots; what it does in plain language (projects and stages, next steps, waiting on others, group pages, the roadmap at every level, ideas and resurfacing, the log, decisions, releases, files with in-app viewing, people, reviews and PDF sharing, backups, sync between your own devices); an honest "What Dig is not" list; install instructions; keyboard shortcuts table including the command line; privacy; the support line and links; contributing; license.
3. **A distributable Linux artifact:** an x86_64 AppImage bundling Python, PySide6, and QtWebEngine with the PDF viewer, tested in a clean environment with an empty home directory, plus a source tarball. Note in the README that the AppImage is large because it bundles a browser engine.
4. **A GitHub Release** for the new version with the AppImage, the source tarball, and SHA256SUMS. Human release notes: what Dig is now, what changed, how to install, and that this version migrates existing data on first launch.
5. **Verify as a stranger:** download the AppImage from the release URL into a clean directory, check the checksum, run it with an empty home, confirm onboarding, no data, and offline operation. Report the result.

---

## Part 4: Replace the old version on my computer

My local install keeps my real data; only the published version is empty.

1. **Back up first:** copy my existing Dig data, database and attachments, into a timestamped folder in my home directory and tell me the exact path. Never delete any of my data.
2. Run the old version's uninstall path if it exists; remove the old desktop entry, icons, venv, and any exported build on my desktop, so exactly one copy of Dig exists on this machine.
3. **Install user-level only** (Bazzite's /usr is immutable): application files, icons into `~/.local/share/icons/hicolor`, the desktop entry into `~/.local/share/applications`, the `dig` command on my PATH, then refresh the desktop database.
4. **Launch it.** Confirm my data migrated per the migration document, the window groups with the launcher under KDE on Wayland, both themes work, and the app makes no network calls.
5. **Report:** backup path, what was removed, where it is installed, the version, the release URL, and anything decided on my behalf.

---

## Part 8: Where everything goes in the phased plan

Follow `BUILD_PLAN.md` with these changes. Every phase still ends with a commit and push. Update `HANDOFF.md` at every commit, before any pause, when context runs low, when anything fails, and when any decision is made.

| Phase | What happens |
|---|---|
| **0** | Add `docs/V2_MIGRATION.md` as planned, and apply Part 2 item 2 before committing the handoff folder. |
| **1** | Build the Part 5A model (per-record tables, uuids, sync metadata, tombstones, oplog, devices, schema version) and the Part 6 blob store instead of the single JSON document. Tests for both. |
| **2** | Integrate the prototype UI against the new model. Remove the seed data (Part 2 item 1). |
| **3** | Native pieces as planned, now including the full Part 6 file pipeline: picker, drag-and-drop, paste, viewer for every type, save a copy, save all files, reveal, move, delete to Recently deleted. |
| **4** | Setup defaults and v1 migration as planned. |
| **4.5 (new)** | Part 7 features: group pages, Your review with periods, the log, duplicate and templates, Recently deleted, command line and single instance, quiet projects, People screen, backup and restore, CSV import, text size and accessibility, Not planned. Commit after each numbered item. |
| **5** | Desktop integration as planned, plus the `dig` command on PATH and the KDE shortcut documentation. |
| **5.5 (new)** | Part 1 onboarding. |
| **5.75 (new)** | Part 5B sync server, pairing, conformance client, `docs/SYNC.md`, and the Part 5C copy updates. |
| **6** | Fidelity pass against the prototype for everything the prototype covers, and a design-consistency pass for every new screen and dialog so nothing new looks or reads differently from the prototype's language. |
| **7** | Automated tests, extended to cover every test listed in this addendum. |
| **8** | Scripted user testing, extended (see below). Nothing is exported to my desktop before this passes. |
| **9** | Screenshots with example data only, README per Part 3, the semver release with one line of reasoning, then Part 3 publishing, then Part 4 replacing my local install. |

**Phase 8 additions:** complete onboarding both ways and replay it; add every kind of file by every route, view each type, save copies and verify bytes, replace as version, move, delete and restore; use group pages and export a group one-pager; write log entries and see them on the timeline and in a monthly review; duplicate a project and start one from a template; run `dig add` from a terminal and a KDE shortcut; make a project go quiet and find it; back up everything, wipe, restore, and verify files and data are identical; import a CSV; pair the conformance client, sync both directions, force a conflict, revoke; change text size; verify screen reader labels on every screen. Fix, commit, repeat until clean.

**Final report:** version and reasoning; every decision made on my behalf; every defect found and fixed in Phase 8; the personal-data scan result; the backup path; the release URL; anything deferred.

Do not end a turn while work remains; finishing one phase means starting the next in the same turn. If anything in this document is genuinely infeasible or a bad idea once you are in the code, stop and tell me with your reasoning and options rather than working around it.
