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

## The addendum

`docs/handoff-v2/ADDENDUM.md` arrived partway through Phase 6 and supersedes
parts of the original prompt. It restructures the build plan (its Part 8) and
adds: first run onboarding, a published app that ships empty, GitHub publishing
with an AppImage, replacing the local install, a sync ready per record data model
with an oplog, a private sync server over Tailscale for a future Android client,
a complete file system with in app viewing, and the Part 7 feature set.

It asked for Parts 5A and 6 to be built in Phase 1, before anything else. They
arrived after Phase 5, so they are being retrofitted. That is contained: the
interface holds the whole state as one object either way, and only persistence
changes, so `adopt()` and `persist()` in `app.js` are the entire seam.

## Build plan progress

Phases as restructured by the addendum's Part 8.

- [x] Phase 0: read, plan, checkpoint
- [x] Phase 1: shell and bridge (single document storage)
- [x] Phase 1R: Part 5A per record model with oplog, Part 6 blob store
- [x] Phase 2: move the prototype in
- [x] Phase 3: native pieces (basic files, export, import, PDF)
- [x] Phase 3R: the full Part 6 file pipeline
- [x] Phase 4: setup defaults and v1 migration
- [x] Phase 4.5: the Part 7 feature set
- [x] Phase 5: desktop integration
- [x] Phase 5.5: Part 1 onboarding
- [x] Phase 5.75: Part 5B sync server, conformance client, docs/SYNC.md
- [~] Phase 6: fidelity pass (done against the prototype; redo after the above)
- [ ] Phase 7: automated tests, extended
- [ ] Phase 8: scripted user testing, extended
- [ ] Phase 9: screenshots, README, release, publish, replace the local install

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
18. **The icon is three ascending bars.** DESIGN asks for "a simple white upward
   step arrow (three ascending bars, the middle one taller)". Ascending and
   middle-tallest cannot both hold, so the icon follows the primary description:
   three bars climbing left to right on the blue rounded square, which is what
   reads as stages. `scripts/build_icons.py` redraws the whole set.
19. **The light palette is a little darker than DESIGN.md's, to meet WCAG AA.**
   The addendum's 7.11 says contrast must meet AA in both themes and any failure
   must be fixed. Measured, the light theme failed: `--ink-3` was 2.76:1 on
   `--panel-2` where helper text needs 4.5, and teal, green, amber, coral, and
   rose were all between 2.46 and 3.48 on their own soft backgrounds. Each was
   moved the minimum distance to reach 4.5, keeping its hue and saturation:
   ink-3 #8593A6 to #606F84, teal #0BA39E to #087A77, green #1E9E5A to #187C47,
   amber #D9890B to #9A6108, coral #E4573F to #C5341C, rose #D14A7A to #BF3163,
   red #D64545 to #C23B3B, and dark ink-3 #5E6C82 to #7B89A0. Dark mode passed
   everywhere else. This is the one place the app deliberately differs from the
   prototype's palette, and `test_the_contrast_meets_double_a_in_both_themes`
   holds it.
20. **The viewer reaches bytes through a hard link, not a custom scheme.**
   A `dig://` scheme was built first and abandoned: QtWebEngine will not let a
   `file://` page fetch or even `<img>` one, and there is no way to attach the
   CORS headers it would want. The bridge hands the page a `file://` path into
   `blobs/.views/<sha><ext>` instead.
21. **The sync server is `http.server`, not QtHttpServer.** QtHttpServer's
   Python bindings cannot express this API: a route handler cannot return a
   `QHttpServerResponse` (it is move-only in C++ and PySide refuses to copy it),
   and `QAbstractHttpServer`'s virtuals are not exposed to subclass. A threaded
   `http.server` on its own thread, with a SQLite connection per thread, does
   the job with fewer moving parts.
22. **`segno` is pinned for the pairing QR code.** Pure Python, no dependencies
   of its own, and it only ever draws a code that is shown on this screen.
23. **The web view is hard-wired to this computer.** A URL request interceptor
   refuses every scheme except file, qrc, data, blob, and about, so "no network
   calls" is enforced rather than merely intended. Navigation away from the one
   local document is refused and handed to `openUrl` instead. The context menu is
   cut down to Cut, Copy, Paste, and Select all, because a browser's Back and
   Reload menu inside a desktop app is wrong.

24. **Text size scales the interface through the web engine's zoom.** 7.11 asks
   for a control that scales the interface. The prototype's CSS sizes nearly
   every piece of text in pixels, so moving a base size would have moved the
   sidebar and left everything else. Rewriting every size into `em` would have
   meant changing hundreds of the prototype's own numbers, which the brief
   forbids. `Bridge.setZoom` sets the page's zoom factor instead, which scales
   the words, the boxes and the space between them together. A CSS `zoom`
   fallback covers the fidelity harness, which runs the interface with no bridge.
25. **The fidelity harness distinguishes the addendum from drift.** The addendum
   changed things that appear on every screen: group pages rerouted the sidebar,
   the log joined the Record tab, files became real, and every control gained a
   name for a screen reader. Comparing raw markup after that would have reported
   every screen as different and said nothing. `ADDENDUM_APP` and
   `ADDENDUM_PROTO` in `scripts/fidelity.py` bring both sides to the same place
   first, each rule naming the part of the addendum that asked for it, so what
   is left over is drift. The pixel diff now also reports the box the difference
   sits in, because where it is says more than how much of it there is.

26. **The sidebar footer is allowed a second line.** The brief says to match
   the prototype, and everywhere else this port does. The footer is the one
   place where matching it means shipping a horizontal scrollbar and a label
   broken in half, which is a defect in the prototype rather than a decision in
   it. Every word and every control is unchanged and it still reads as one
   footer; it simply wraps when it has to. Checked at all four text sizes.

## Current state

Addendum Parts 1, 2, 5A and 6 are in, and every defect the adversarial review
confirmed is fixed. 123 tests green.

Onboarding is five steps with progress dots, Back, Continue, and a Skip that
jumps to the end and still applies the defaults. Step three shows a live plain
sentence saying exactly which groups, types, and stages will be made. Step four
offers a generic example set, four projects across two groups with ideas, a
wait, an inbox item, two decisions and a log entry, all marked `example` so
Settings can take every one of them out in a click without touching anything the
person made. After it, a Start here card sits on Home until its three things are
done or it is dismissed, and never comes back.

**Part 2 verified.** Launched against an empty home inside a network namespace
with no interfaces at all: it opens on step one of onboarding, holds no data of
any kind, renders Geist from the bundled files, walks every screen, creates a
project, and attempts zero network requests.

Files are first class: a picker that takes several at once, drag and drop onto a
project, a group page, or the Library, paste from the clipboard, deduplication by
SHA256, replace-as-a-version or keep-both when a name clashes, and a viewer that
reads images, PDFs, text with line numbers, Markdown either way, CSV as a table,
audio and video, and says so plainly for anything else. Save a copy writes the
exact original bytes; Save all files writes a zip with a manifest.csv carrying
name, document id, version, size, date, and hash.

**How the viewer reaches the bytes.** A custom `dig://` URL scheme was built
first and abandoned: QtWebEngine will not let a `file://` page fetch or even
`<img>` a custom scheme, and there is no way to attach the CORS headers that
would be needed. Instead the bridge hands the page a `file://` path into
`blobs/.views/<sha><ext>`, a hard link to the same bytes carrying the real
extension, which is what lets the built in PDF viewer and the media elements
know what they have been given. Text files come through `readText` instead, so
no fetch is involved at all. `.views` never counts as a blob.

Phase 5 complete. The app has an icon, a launcher, and an About dialog.

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

Desktop integration verified on this machine: `install.sh` writes only under
`$HOME` (icons into `~/.local/share/icons/hicolor`, `dig.desktop` into
`~/.local/share/applications`, a `dig` symlink into `~/.local/bin`), reuses the
system PySide6 rather than downloading a second copy, and the app reports
`desktopFileName = dig` on `platform = wayland`, which is what makes KDE Plasma
group the window with the launcher. Confirmed running on the real display at
device pixel ratio 1 with Geist.

The owner's real v1 profile at `~/.local/share/dig` has NOT been migrated. It is
backed up in this session's scratchpad, and every test runs against a throwaway
`XDG_DATA_HOME`. Migration happens the first time they launch it themselves.

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

## The personal data situation (addendum Part 2)

Handled on 2026-09-04. What was found, what was done, and what is left.

**Found.** Everything sensitive sat in `docs/handoff-v2/design/dig-prototype.html`:
the owner's real groups, thirteen real projects, two collaborators by name, a
client and its town, a child's first name and age in a project note, and four
real decisions. Six v2 commits carried it, all pushed to a repository that was
public at the time, for about 53 minutes, with 0 stars and 0 forks. A second
sweep found the same class of thing in the v1 history: real project and idea
names in the v1 design mockup, the v1 screenshot generator, the v1 test suite,
and four v1 screenshots that pictured them.

Clean throughout: no absolute paths carrying the username, no IPs or Tailscale
addresses, no keys or tokens, no database or export ever committed, no email
beyond the public `hello@kamsiob.com` and the GitHub noreply.

**Done.**
1. The repository was made private immediately, on the owner's instruction.
2. The original prototype is preserved outside the repository at
   `~/Dig design reference (private, not in git)/`. Nothing was deleted.
3. The prototype's seed was replaced with the generic example set from the
   addendum's Part 1.4 (Website refresh, New client onboarding, Quarterly
   report, Kitchen renovation, across Work and Home). It still runs on every
   screen, tab, and dialog with no console errors.
4. History was rewritten with `git filter-repo`: the prototype blob swapped for
   the sanitized one in every commit, name substitutions applied to every other
   blob, and `docs/screenshots/` removed entirely. Force pushed with lease.
5. Verified by scanning every blob of every reachable commit in a fresh clone
   from GitHub against 49 markers: none survive.

**Left, and it matters before Phase 9.** GitHub still serves the old commits by
exact SHA (`a966f94` through `cd94c5d`), because it does not garbage collect
unreferenced objects on demand. That is harmless while the repository is private
and only the owner can reach them. It stops being harmless the moment Part 3
makes it public again. Before publishing, either ask GitHub Support to purge the
unreferenced objects, or delete and recreate the repository. Do not make it
public until one of those is done.

## Defects found and fixed

1. **Opening a finished project rendered nothing.** Advancing into a last stage
   sets the horizon to `done`, which is not one of the four roadmap columns, so
   the project page's `HZ.find(...)[1]` threw on undefined and the whole view
   went blank. Confirmed in the prototype itself. Fixed in Phase 4, because it
   blocked the migration tests: a new `hzLabel()` returns "Finished", which is
   the word the rest of the app already uses for that state.
2. **The last thing typed before quitting was lost.** The interface held a
   change for 150 ms before handing it over, and the window closed straight
   away, so anything typed in that instant never reached the disk. Worst for
   Notes and Next step, which save without re-rendering. `MainWindow.closeEvent`
   now refuses the first close, asks the interface to hand over what it is
   holding, waits up to 400 ms, writes it, and only then goes.
3. **An empty project type bricked the app.** `createP` would write `type:""`,
   and every screen that looked the type up then threw. Guards in `openNew` and
   `createP`, a fallback in `T()`, and `delType` keeping the last type.
4. **Undo on a stage move deleted the wrong activity.** `LAST_ADVANCE` now
   captures what the move wrote so undo puts back exactly that.
5. **Your review was still called Your week in two places.** The sidebar was
   renamed but the release dialog's helper line and one toast were not. Found by
   the Phase 6 markup comparison.
6. **The Share button on a group page shared every project.** `doShare` had no
   case for a group, so `g:<id>` fell through to the whole projects page. Part
   7.1 asks for a group one pager. `pdfGroup` and `openShareGroup` now build
   it: what the group is, where each project has got to, the decisions, and
   what shipped. A private group says it is private and shows nothing else.
7. **Text size only moved the sidebar.** The interface sizes nearly every piece
   of text itself, in pixels, so setting a base size alone left the rest where
   it was. 7.11 asks for a control that scales the interface, so text size now
   goes through the web engine's own zoom, with a CSS fallback when there is no
   bridge. See decision 24.

## Phase 8, the scripted user pass

`scripts/userpass.py` uses the app the way a person would, on a fresh profile,
through all sixteen steps BUILD_PLAN lists and the fourteen the addendum adds.
It drives the window a person launches, not a stand in for it, and it records
every failure rather than stopping at the first, because a pass that halts on
the first defect hides the nine behind it. 262 things checked.

Run it with `./.venv/bin/python scripts/userpass.py --data /tmp/pass`.

### Defects it found, and what was done

1. **The Share button on a group page shared every project.** Found in Phase 6
   and fixed there. See above.
2. **A change arriving from another device emptied whatever dialog was open.**
   Redrawing the window replaces every element in it, including the box being
   typed into, so a sync landing mid sentence took the sentence with it.
   `render` now leaves an open dialog exactly where it is and redraws only what
   is behind it, and a change arriving while something is open waits until it
   is closed.
3. **A field name from another device went straight into the statement.**
   `Store.write` built its SQL from the keys of whatever it was handed, and a
   paired device is the one thing that can choose those keys. A push carrying a
   field called `group` produced a syntax error that was swallowed as "ignored";
   a field named to close the statement would have been worse. Unknown columns
   are now dropped before anything is built.
4. **The first local save after a sync deleted everything that had arrived.**
   The interface saves the whole document, so anything missing from it reads as
   deleted. A record another device wrote a moment ago is missing because the
   interface has never seen it. `save_state` now takes the oplog cursor the
   document was read at, and leaves alone anything another device wrote after
   it. The cursor rather than a timestamp, because the other device's clock is
   not ours to trust, and stamped when the interface says it has taken the
   document rather than when Python handed it over, because there is a moment
   between the two in which the old document is still the live one.

### The two defects inherited from the prototype

Both were logged during the build rather than fixed quietly out of phase. Both
are fixed now.

5. **The sidebar footer collided.** Settings, "Shortcuts ?", and the Light /
   Dark / Auto switch come to 214px of content in a 207px sidebar with real
   Geist, so "Shortcuts" broke away from its "?" and the sidebar grew a sideways
   scrollbar. Confirmed in the prototype itself. The words and the controls are
   unchanged; they were given the few pixels they were short, and permission to
   fall onto a second line rather than break a label in half. See decision 26.
6. **An apostrophe in a stage name or a checklist suggestion broke its button.**
   `addExpected`, `addExp`, and `delExp` built single quoted JavaScript string
   literals inside double quoted HTML attributes, so a stage called "Don't ship
   Friday" produced a handler that did nothing. They go through `jsq()` now.

## Known risks

- QtWebEngine on Wayland needs checking for the correct scale factor and for
  `setDesktopFileName` grouping.

## Phase 6, how it came out

`scripts/fidelity.py` puts the app and the prototype side by side on the same
data, with the clock frozen, the same bundled fonts, no animation, no caret, and
the window focus handed to each in turn. Eighty two cases, every screen and
every dialog, in both themes.

- 74 of 82 are markup identical. The eight that are not are Your review, the
  Library, and Settings, in both themes, which the addendum redesigned.
- 24 of 82 are pixel identical outside the sidebar. Every screen carries the
  sidebar, and the sidebar now says Your review where it said Your week, so no
  screen can be identical including it.
- 0 differ with no reason to. Every remaining difference is named in
  `CHANGED_BY_THE_ADDENDUM` and the report says the box it sits in.
- No network request was made by either side.

Three things the comparison turned up were fixed rather than excused: the
release dialog and one toast still said Your week, the new project dialog
carried a stray empty div, and the group page's Share button shared every
project instead of that group.

## Where to pick up

1. **Phase 8**, the scripted user pass, extended as the addendum's Phase 8
   additions list. `scripts/userpass.py` is that pass.
2. **Phase 9**: screenshots with example data only, the release, the AppImage,
   publishing, and replacing the local install.

**Before Phase 9 publishing**, settle the GitHub residue described above.

Run the suite with `./.venv/bin/python -m pytest tests/ -q`. Compare against the
prototype with `scripts/fidelity.py`. Drive the real app with `scripts/drive.py`.
