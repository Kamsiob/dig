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
- [x] Phase 2: move the prototype in
- [x] Phase 3: native pieces
- [x] Phase 4: setup defaults and migration
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
11. **Setup starts with nothing checked, and Follow system is the default theme.**
   The prototype's setup screen shows three boxes ticked and a light theme because
   that is its sample data, the same way the org field reads "Example Studio". A
   fresh install pre-fills none of them, and follows the desktop's own scheme.
12. **Setup fills in `you` from the organization name.** The setup screen has one
   name field, bound to `org`, and Home greets `you`. On finishing setup, `you` is
   set to the first word of what was typed if it is still empty. Settings has an
   explicit "Your name" field to change it.
13. **The resurfaced idea is picked again at every launch.** SPEC's rule is that
   resurfacing never repeats the idea just shown. `resurfId` is persisted so the
   next launch can exclude it, and `pickResurf()` runs at startup, which is what
   makes the empty state's promise of "one will show up here each day" true.
14. **Nothing guesses at what a date looks like.** Dates go to disk as ISO strings
   and are turned back into Date objects at the exact paths the data model names,
   rather than by sniffing every string in the document, so a note that happens to
   read like a date is left alone.
15. **A single project's one pager can be exported even from a private group.**
   SPEC 4 says private groups never appear in any export. The three overview
   exports (projects, roadmap, the week sheet) honor that and state the count
   left out. Sharing one named project is a deliberate act, and the prototype
   offers Share on every project page, so it exports, with a footer that says
   "This project is in a private group. It never appears in a shared overview."
16. **Parked projects still show on the roadmap, under Someday.** SPEC 4 says
   parking removes a project from Home and the roadmap; the prototype removes it
   from Home and from the Projects Active filter but keeps it on the roadmap in
   Someday, which is where parking puts its horizon. The prototype settles
   questions of behavior, so that is what the app does. One line in
   `renderRoadmap` changes it if you would rather it disappeared.
17. **`exportJson` is handed the live document.** SPEC writes it as
   `exportJson()`. The freshest state lives in the interface, not on disk, so the
   slot takes the document to write rather than racing the debounced save.
18. **The web view is hard-wired to this computer.** A URL request interceptor
   refuses every scheme except file, qrc, data, blob, and about, so "no network
   calls" is enforced rather than merely intended. Navigation away from the one
   local document is refused and handed to `openUrl` instead. The context menu is
   cut down to Cut, Copy, Paste, and Select all, because a browser's Back and
   Reload menu inside a desktop app is wrong.

## Current state

Phase 4 complete. Setup defaults and the v1 migration are in.

`dig/ui/` holds `index.html`, `app.css`, `app.js`, the six Geist weights the
design calls for (SIL OFL, license alongside them), and the vendored
`qwebchannel.js` (Qt, LGPLv3, compatible with AGPLv3). `app.css` and `app.js`
were produced from the prototype by an exact-match transform with an assertion
per edit, so every change is one of the nineteen the build plan asks for and
nothing else moved.

Verified in the running app: Geist and Geist Mono load, zero requests are
blocked because zero are made, no console errors, and capture, checklist
toggles, horizon moves, and the theme all survive a restart with dates revived
as real Date objects.

`scripts/drive.py` starts the real app against a data folder of your choosing
and walks a JSON plan of steps, recording values and screenshots. It can queue
answers for file dialogs with `--open` and `--save`, because a modal dialog has
nobody to click it in a headless run. The fidelity pass, the test suite, and the
scripted user pass all run on it.

`dig/migrate_v1.py` runs on the first launch that finds a v1 file: it copies the
old database to `dig-v1.db.bak` first, renames each app's attachment folder to
its new project ID, and writes the v2 document through the normal atomic save.
If anything fails, nothing is deleted and the person is told plainly.

Test counts so far: 17 storage, 18 migration, 16 setup, 6 migrated-install, all
57 green. `tests/uiharness.py` starts the real window against a data folder the
test owns and runs JavaScript in it synchronously, so a test reads the app's own
state back rather than a stand in for it.

Phase 3 verified end to end in the running app: a file picker copies into
`attachments/{project_id}/` with `(2)` style collision suffixes, export writes
the full document, import reads it back behind a confirmation and refuses a file
Dig did not write, and all four PDFs render through the web engine in the light
palette with Geist embedded. The week sheet exports as literally the on screen
sheet's own markup. The overview exports leave private groups out and say how
many.

Development environment: `.venv` created with `--system-site-packages` so it
picks up the system PySide6 6.11.1 rather than downloading a second copy.
Run tests with `./.venv/bin/python -m pytest tests/ -q`.

The handoff is committed under `docs/handoff-v2/`.
`docs/V2_MIGRATION.md` describes how v1 data becomes v2 data.

There is real v1 data on this machine at `~/.local/share/dig/dig.db`: one app
("Dig", shipped, created 2026-07-21), no ideas, no sheet items, no attachments,
plus the v1 `appearance` and `window_geometry` settings. The migration must
handle it and keep the original file as `dig-v1.db.bak`.

## Defects found and fixed

1. **Opening a finished project rendered nothing.** Advancing into a last stage
   sets the horizon to `done`, which is not one of the four roadmap columns, so
   the project page's `HZ.find(...)[1]` threw on undefined and the whole view
   went blank. Confirmed in the prototype itself (open a project in its last stage). Fixed in Phase
   4, because it blocked the migration tests: a new `hzLabel()` returns
   "Finished", which is the word the rest of the app already uses for that state.

## Known defects to fix in Phase 8

Both are inherited from the prototype and both will bite real data, so they are
logged here rather than fixed quietly out of phase.

1. **The sidebar footer collides.** At the design's 232px sidebar, Settings,
   "Shortcuts ?", and the Light / Dark / Auto switch do not fit on one line, so
   "Shortcuts" wraps onto "Settings" and the sidebar grows a horizontal
   scrollbar. Confirmed in the prototype itself with real Geist metrics.
2. **An apostrophe in a stage name or a checklist suggestion breaks its button.**
   `addExpected`, `addExp`, and `delExp` build single quoted JavaScript string
   literals inside double quoted HTML attributes. A stage called "Don't ship
   Friday" would produce a broken handler. The `jsq()` helper added in Phase 2 is
   the fix; apply it in Phase 8 when the pass turns it up.

## Known risks

- QtWebEngine on Wayland needs checking for the correct scale factor and for
  `setDesktopFileName` grouping.
