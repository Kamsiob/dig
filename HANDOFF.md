# HANDOFF

Cross-session memory for Dig. Read this file in full at the start of every session.
The GitHub issue tracker is the only other place session state is kept.

## What Dig is now

Dig v2. A local-only desktop app that keeps every project you are working on in
one place: what stage each one is at, what its next step is, and what you decided
along the way. Ideas wait until you start them. Everything stays on this computer.

v2 replaces the v1 design and data model entirely. The approved design lives in
`docs/handoff-v2/`. The prototype at `docs/handoff-v2/design/dig-prototype.html`
is the product's interface, not a mockup of it. Match it exactly. Do not redesign,
rename, reword, or improve anything.

## Architecture (settled, see SPEC section 1)

PySide6 `QMainWindow` hosting a `QWebEngineView` that loads the prototype's own
HTML, CSS, and JS from `dig/ui/`. A `QWebChannel` bridge exposes Python for
storage, file copying, export and import, PDF rendering, opening links and paths,
and the live OS theme. One SQLite file at `~/.local/share/dig/dig.db` holds the
whole state as a single JSON document. Zero network requests, ever.

## Standing rules

- Git identity: `Kamsiob` / `306265999+Kamsiob@users.noreply.github.com`.
- Conventional commit messages. Commit and push at the end of every phase.
- No em dashes anywhere: code comments, commit messages, user-facing text.
- American English.
- Exactly one copy of the app on this machine. Delete old builds and test
  artifacts as you go. No export to the desktop before Phase 8 passes clean.
- User-level installs only. Bazzite's `/usr` is immutable.
- Call `QGuiApplication.setDesktopFileName("dig")` so KDE on Wayland groups the
  window with the launcher.
- Desktop app only. Never test on a phone or in an emulator.
- Update this file at every commit, before any pause, when context runs low, when
  anything fails, and when any decision is made.

## Build plan progress

Phases are defined in `docs/handoff-v2/BUILD_PLAN.md`. Do not merge or skip them.

- [x] Phase 0: read, plan, checkpoint
- [x] Phase 1: shell and bridge
- [ ] Phase 2: move the prototype in
- [ ] Phase 3: native pieces
- [ ] Phase 4: setup defaults and migration
- [ ] Phase 5: desktop integration
- [ ] Phase 6: fidelity pass
- [ ] Phase 7: automated tests
- [ ] Phase 8: scripted user testing
- [ ] Phase 9: screenshots, README, release, export

## Decisions made on the owner's behalf

Each of these is a place where the prototype could not answer the question by
itself, because the prototype runs on frozen sample data and has no operating
system underneath it.

1. **`NOW` becomes the real clock.** The prototype pins `NOW` to
   `2026-09-04T14:00:00` so its sample data reads well. The app uses the live
   date. Every `ago()`, `days()`, and `fmt()` call is unchanged.
2. **The greeting follows the clock.** SPEC 3.2 asks for a greeting by time of
   day. The prototype only ever shows "Good afternoon" because its clock is
   frozen at 14:00. Rule used: before 12:00 "Good morning", before 18:00
   "Good afternoon", otherwise "Good evening".
3. **"Week of ..." is derived, not hardcoded.** The prototype prints
   "Week of August 29, 2026", which is exactly six days before its frozen `NOW`,
   and covers the same seven day window the report filters on. The app prints
   `NOW` minus six days in the same `Month D, YYYY` format.
4. **The persisted document uses SPEC's shape; the runtime object uses the
   prototype's.** SPEC 2 puts `filterGroup`, `sort`, `ideaSort`, `libFilter`,
   `publicOnly`, `ptab`, `resurfId`, and `window` under a `ui` key. The
   prototype's render functions read them off the top level of `S`. The storage
   glue folds them into `ui` on save and spreads them back on load, so the file
   matches SPEC and not one render function has to change.
5. **`uid()` is made collision-proof across sessions.** The prototype's counter
   restarts at 100 every reload, which would reuse IDs once state persists.
   Replaced with a timestamp plus counter in base 36. Still a short unique string.
6. **A neutral default for unknown file type chips.** The prototype's fake file
   picker only ever produces PDF, MD, PNG, SVG, ZIP, and HTML, so `.file .ic` has
   no base background. A real file picker produces any extension. A neutral
   `--panel-2` base was added under the existing specific rules, which is
   invisible for every type the prototype exercises.
7. **Reduced motion is read from the desktop, not from Chromium.** QtWebEngine
   does not forward the OS reduce-motion setting to `prefers-reduced-motion`. The
   bridge reads it (GNOME `enable-animations`, KDE `AnimationDurationFactor`) and
   sets `data-motion="reduce"` on the root element. The existing media query is
   kept as well, so both routes work.
8. **Grid mode is removed with the prototype bar.** The Screen grid button is part
   of the prototype bar, so `renderGrid`, `setMode`, and `resetAll` go with it.
9. **`pickFile` takes the project it is filing into.** SPEC writes the slot as
   `pickFile(filter)`, but SPEC's own storage rule puts attachments under
   `attachments/{project_id}/`, so the slot cannot know where to copy without
   being told. The signature is `pickFile(projectId, fileFilter)`.
10. **Python owns `ui.window`.** The interface cannot know where its window sits
   on the desktop, so the bridge stamps the geometry into the document on the way
   to disk. Nothing in the interface has to think about it.
11. **The web view is hard-wired to this computer.** A URL request interceptor
   refuses every scheme except file, qrc, data, blob, and about, so "no network
   calls" is enforced rather than merely intended. Navigation away from the one
   local document is refused and handed to `openUrl` instead. The context menu is
   cut down to Cut, Copy, Paste, and Select all, because a browser's Back and
   Reload menu inside a desktop app is wrong.

## Current state

Phase 1 complete. The v1 application code is gone; the v2 skeleton is in place:
`dig/paths.py`, `dig/storage.py`, `dig/bridge.py`, `dig/window.py`, `dig/app.py`,
a placeholder `dig/ui/index.html` that Phase 2 replaces, and the vendored
`dig/ui/qwebchannel.js` (Qt, LGPLv3, compatible with AGPLv3). 17 storage tests
pass. A smoke run confirms the page loads, calls `bridge.load()`, calls
`bridge.save()`, and the state lands in SQLite with a history snapshot.

Development environment: `.venv` created with `--system-site-packages` so it
picks up the system PySide6 6.11.1 rather than downloading a second copy.
Run tests with `./.venv/bin/python -m pytest tests/ -q`.

The handoff is committed under `docs/handoff-v2/`.
`docs/V2_MIGRATION.md` describes how v1 data becomes v2 data.

There is real v1 data on this machine at `~/.local/share/dig/dig.db`: one app
("Dig", shipped, created 2026-07-21), no ideas, no sheet items, no attachments,
plus the v1 `appearance` and `window_geometry` settings. The migration must
handle it and keep the original file as `dig-v1.db.bak`.

## Known risks

- The sidebar footer (Settings, Shortcuts, theme switch) is tight at a 232px
  sidebar. Verify with real Geist metrics, which are narrower than the fallback
  the prototype falls back to offline.
- QtWebEngine on Wayland needs checking for the correct scale factor and for
  `setDesktopFileName` grouping.
