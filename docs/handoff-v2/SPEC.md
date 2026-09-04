# Dig v2: Specification

Dig keeps every project you're working on in one place: what stage each one is at, what its next step is, and what you decided along the way. Ideas wait until you start them. Everything stays on this computer.

It is built for one person running several lines of work (apps, client work, personal projects, content, programs) and must be usable by anyone: every group, project type, stage, and checklist is user-defined; the setup screen picks sensible defaults from what the person says they work on.

It is NOT a project manager. No boards, no drag-and-drop, no priorities, no due dates, no dependencies, no assignees, no time tracking, no money, no notifications, no cloud, no AI, no network calls of any kind.

## 1. Architecture (decided, not optional)

The prototype's UI is the product's UI. To replicate it exactly rather than approximate it:

- **Shell:** Python + PySide6. A single `QMainWindow` hosting a `QWebEngineView` that loads the app's HTML/CSS/JS from the package (`dig/ui/`). Window minimum 1100×720, size and position remembered.
- **UI:** the prototype's HTML, CSS, and JS, moved into `dig/ui/index.html`, `dig/ui/app.css`, `dig/ui/app.js`, with these changes only: (1) remove the prototype bar (App / Screen grid / Reset data) and the outer `.proto` wrapper; the `.app` element fills the window; (2) replace the in-memory `seed()` with state loaded from the bridge; (3) call the bridge to persist after every state change; (4) route file pickers, folder opening, link opening, exports, and imports through the bridge. Everything else, every render function, every workflow function, every keyboard handler, every animation, stays as written.
- **Bridge:** `QWebChannel` exposing a `Bridge` QObject with slots: `load() -> str` (JSON state), `save(json: str)`, `pickFile(filter: str) -> str` (copies the chosen file into the managed attachments folder and returns `{name,type,size,stored_path}` JSON), `openPath(path: str)`, `openUrl(url: str)`, `openDataFolder()`, `exportJson()` (save dialog, writes the full state), `importJson() -> str` (open dialog, returns the JSON to replace state), `printPdf(html: str, suggested_name: str)` (renders the given HTML in an offscreen `QWebEnginePage` and `printToPdf` to a chosen path), `setDesktopFileName()`, `theme()` (returns the OS color scheme so "Follow system" works and updates live via `QStyleHints.colorSchemeChanged`).
- **Storage:** one SQLite file at `~/.local/share/dig/dig.db` holding the whole state as a single JSON document in a `state` table (`id INTEGER PRIMARY KEY CHECK(id=1), json TEXT, schema_version INTEGER, updated_at TEXT`), written atomically (write temp, fsync, rename) on every change and debounced to at most one write per 300 ms. Keep a rolling set of the last 20 saves in `~/.local/share/dig/history/` as timestamped JSON for recovery. Attachments live in `~/.local/share/dig/attachments/{project_id}/`. Corrupt file on load: back it up as `dig.db.broken-{timestamp}`, start from the newest good history file if any, otherwise start fresh, and tell the person plainly in a toast.
- **Fonts:** bundle Geist and Geist Mono (SIL OFL) in `dig/ui/fonts/` and reference them with `@font-face` instead of the Google Fonts link. No OS default fonts for visible text.
- **No network.** Remove the `<link>` to Google Fonts. The app must work with networking disabled and make zero requests.

## 2. Data model

State is one JSON document. Dates are ISO 8601 strings. IDs are short unique strings.

```
state
  org: string                       // organization or person name
  you: string                       // first name for the greeting
  theme: "light" | "dark" | "system"
  setupDone: bool
  groups[]:   { id, name, color (hex), priv: bool }
  types[]:    { id, name, stages: string[], check: { [stageName]: string[] } }
  projects[]: { id, name, group (group id), type (type id), stage (index), enteredAt,
                when: "now"|"next"|"later"|"someday"|"done", next: string,
                items[]: { id, text, done: bool, tag: ""|"bug"|"exp" },
                decisions[]: { no: int, text, at, supersedes: int|null, superseded: bool },
                files[]: { type, name, meta, stored_path },
                links[]: string,
                notes: string,
                pub: bool,                          // shareable (default = group not private)
                wait: null | { what, since },
                lastAct,
                releases[]: { v, at, note },
                people[]: { n, r },
                hist[]: { stage, from, to },        // completed stage spans
                quiet: bool, parked: bool, origin: string|null,
                waitHist[]: { what, days } }
  ideas[]:    { id, text, desc, at, opened: null|date, group: ""|group id }
  inbox[]:    { id, text, type: "idea"|"todo"|"bug"|"note"|"link"|"decision", at, guess: project id|null }
  library[]:  { id, kind: "link"|"note"|"file", title, meta, group, stored_path? }
  activity[]: { group, pid, text, at, kind: "move"|"ship"|"decision" }
  ui: { filterGroup, sort, ideaSort, libFilter, publicOnly, ptab, resurfId, window: {x,y,w,h} }
```

Derived, never stored: `stageName(p)`, `nextStage(p)`, `isLast(p)`, `unmet(p)` (checklist suggestions for the current stage that aren't done), `nextDecNo()` (max decision number across all projects + 1), relative times.

## 3. Screens

Left sidebar on every screen: organization name with a gradient avatar, "Add something" (Ctrl K), nav (Home 1, Projects 2, Roadmap 3, Ideas 4, Library 5, Your week 6), Groups list with counts and "Everything", footer with Settings, Shortcuts (?), and the Light / Dark / Auto switch. The Home item shows a coral badge with the inbox count when the inbox isn't empty.

### 3.1 Welcome and setup (first run only, reachable later from Setup)
Headline sentence explaining Dig. Name field. Checkboxes for what the person works on: Apps or software, Client work, Content, Personal projects, Programs or events. "Let's go" creates defaults:
- Apps → group "Apps" (teal) and type App (Idea → Plan → Design → Build → Test → Release → Keep up, with the checklist suggestions from the prototype).
- Client work → group "Clients" (rose, private by default) and type Client work (Anchor → Align → Advance → Close).
- Content → group "Content" (blue) and type Content (Idea → Script → Record → Edit → Publish).
- Personal projects → group "Personal" (sage, private) and type Task (Planned → In progress → Done).
- Programs or events → group "Programs" (amber) and type Program (Planned → Funded → Running → Wrapped).
Nothing selected → one group "Projects" and the Task type. Everything is editable in Settings afterward. A returning user's data is never touched by revisiting Setup; it only adds missing defaults.

### 3.2 Home
Greeting by time of day and name. Subline: N projects active · N waiting on someone else · N in your inbox. Four sections, each with a colored icon, a title, and one line of gray helper text:
1. **Up next.** The next step of up to four active, non-waiting, non-parked projects, ordered by longest time in current stage. Row: group dot, next-step text, project · stage · days. Buttons: Done ✓ (clears the step, slides the row out, toast with Undo), Open.
2. **Waiting on someone else.** Every project with a wait: what, project, days badge, "It arrived" (resolves, records to waitHist, slides out, toast).
3. **Inbox.** Captured things not yet placed. Type badge, text, age, "looks like X" when Dig can guess a project. Buttons: "Put in X" when guessed (one click), "Choose…" (dialog).
4. **An old idea worth a second look.** One idea chosen at random from ideas older than the three newest, excluding the one shown last. Buttons: Start it, Open, Show another.
Every section has a designed empty state.

### 3.3 Projects
Header, search, Share as PDF, New project. Group chips plus a filter: Active (default, hides parked), Only waiting, Only finished, Only parked. Projects grouped under their group with a count, a private label when private, a "roadmap" link, and "+ project". Cards: name, type badge, segmented stage bar in the group color, "Stage · stage n of m · days here" (or Waiting badge, Finished badge, Parked badge), Next step (or Waiting on / Quiet since). Hover reveals: Move to {next stage} →, Waiting on… (or It arrived, or Unpark).

### 3.4 Roadmap
Filter chips (All groups or one group). Summary strip: counts for Now / Next / Later / Someday. Four columns, each listing non-finished projects for that horizon, grouped under group labels when viewing all groups. Card: dot, name, waiting badge, stage · stage n of m · next step, mini stage bar; hover reveals ← previous horizon / next horizon → buttons. Finished projects listed below with latest release. Share roadmap button. When filtered to a private group, a "private · never shared" badge shows.

### 3.5 Project page
Breadcrumb Projects / Group. Header: initials square in the group color, name, type badge, "Can be shared"/"Private" badge, horizon badge, links, "+ link". Buttons: Share, Park/Unpark, Waiting on… / It arrived, Move to {next} → (or Finished, disabled). Amber wait bar when waiting. Stage strip: each stage a chip (done / you are here · days / later); clicking a later stage jumps (the immediate next stage opens the Move dialog). Three tabs:
- **Work:** origin callout when started from an idea; Next step (single line input, saves on change); the current stage's checklist (suggested items appear dashed until clicked into existence; items sort open first; click toggles done; hover ✕ removes with Undo; add row, "!" prefix makes a bug); Notes (contenteditable, saves as you type). Right rail: People (+ add, name and role), Files (+ add via file picker; copied into the attachments folder), Releases (+ add version and one line; dated now; logs a "ship" activity).
- **Roadmap:** vertical timeline of every stage: past stages with from → to dates and duration and any releases stamped inside them; the current stage pulsing with "since {date} · N days", the next step, open then done items; future stages with "Will need: …" from the type's checklist. Rail: horizon chips to place the project on the group roadmap; releases.
- **Record:** decisions (numbered D-0001 style, dated, replaced ones crossed out, "+ record one"), past waits, and the project's activity history.

### 3.6 Your week
Written from activity in the last 7 days: KPIs (Shipped, Moved forward, Decisions made, Waiting on others), sections Shipped / Moved forward / Decided / Waiting on / Next week, each row colored by group. "Hiding private groups ✓" toggle (default on) excludes private groups and states how many were left out. Save as PDF renders the sheet through `printPdf`. If nothing happened, sections say so; nothing is invented.

### 3.7 Ideas
Cards (teal accent). Group chips, oldest/newest sort. Open (edit title, notes, group; delete), Start (opens New project prefilled; the idea becomes the project's origin and is removed from Ideas).

### 3.8 Library
Links, notes, files, with type chips and "Not in a group". Each row: colored kind chip, title, meta, group, move/put in a group, delete. Links open via `openUrl`; files via `openPath`.

### 3.9 Settings
You (organization, name). Groups (color, name, shareable/private toggle, remove; can't remove a group with projects). Project types (name, stages as editable chips with add/remove, per-stage checklist suggestions with add/remove; can't remove a type in use; a type needs at least two stages; deleting a stage clamps projects on it). Appearance (Light / Dark / Follow system; motion follows the OS reduce-motion setting). Your data (path with Open folder, Export / Import JSON, "Internet: never used", license line with an About dialog).

### 3.10 Dialogs
Add something (Ctrl K): big input, type buttons (Let Dig guess, Idea, To-do, Bug, Note, Link, Decision), "Put it in" (Inbox or a project), a live sentence "Saving as a {type} → {place}". Enter saves. Guessing: URL → link; leading "!" or words like bug/broken/crash/stale → bug; leading verb like fix/add/write/ship/call → to-do; else idea. Routing: with a project chosen, to-do/bug/idea → its checklist, decision → recorded on it, note/link → Library under its group; with no project, link/note → Library, idea → Ideas, anything else → Inbox.
Find anything (/): fuzzy list over projects, ideas, library, decisions; arrow keys and Enter.
Where should this go? (inbox sort). Idea. New project / Start this idea. Move to {next stage} (shows unmet checklist items as a gentle warning, "Move anyway"; optional next step). Waiting on. Record a decision (auto number, optional "replaces"). Add link / file / person / release. Share (preview of the one-pager, the projects overview, or the roadmap; private groups always excluded and stated). Keyboard shortcuts.

## 4. Rules that must hold

- Private groups and private projects never appear in any export, share, or the week report unless the person explicitly turns "Hiding private groups" off, and every export states what was left out.
- Toasts confirm every change in the app's voice; destructive or big changes offer Undo where the prototype does (Done ✓, remove checklist item, stage move).
- Resurfacing never repeats the idea just shown when another exists.
- Advancing into a last stage marks the project quiet and horizon "done". Parking a project sets horizon "someday", clears any wait, and removes it from Home and the roadmap until unparked.
- Decision numbers are global across all projects and never reused; replaced decisions remain visible, crossed out.
- Relative time wording follows the prototype's `ago()` exactly.
- All copy is the prototype's copy. American English. No em dashes anywhere in the UI.
- Keyboard: Ctrl K, /, ?, 1–6, Esc, Enter/Shift+Enter as the prototype defines; suppressed while typing in a field.
- Reduced motion disables all animations and transitions.
