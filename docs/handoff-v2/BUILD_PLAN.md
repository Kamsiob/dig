# Dig v2: Build plan

Work through the phases in order. Every phase ends with a commit and push. Do not merge or skip phases. Do not export anything to the desktop before Phase 8 passes.

## Ground rules (every phase)
- Replicate the prototype. When in doubt, open `design/dig-prototype.html` and match it. Do not redesign, rename, reword, or "improve" anything.
- Single copy on this machine: delete or overwrite old builds, test artifacts, and prior exported copies as you go.
- Git identity: user.name `Kamsiob`, user.email `306265999+Kamsiob@users.noreply.github.com`. Conventional commit messages. No em dashes in commit messages or any user-facing text. American English.
- Context discipline: read `HANDOFF.md` fully at session start if it exists; search other docs for the sections you need rather than loading whole files. Update `HANDOFF.md` at every commit, before any pause, when context runs low, when anything fails, and when any decision is made.
- The existing v1 repo (if present) is the starting point. v2 replaces the v1 UI and data model entirely. Preserve v1's license, README history, and `.desktop`/icon plumbing where still valid.

## Phase 0: Read, plan, checkpoint
1. Read `README.md`, `SPEC.md`, `BUILD_PLAN.md`, `DESIGN.md`. Open the prototype in a browser and click through every screen, tab, and dialog. Use Screen grid.
2. Inspect the existing repo. Write `docs/V2_MIGRATION.md` describing how v1 data (ideas, apps with feature/bug sheets, attachments) maps into v2 (`ideas` → ideas; apps → projects of type App, stage Keep up if shipped else Build, feature/bug lines → checklist items with bug tag, attachments → files).
3. Add the handoff folder to the repo under `docs/handoff-v2/` (all four documents and the prototype).
4. **Commit + push:** `docs: v2 handoff, migration plan`.

## Phase 1: Shell and bridge
1. PySide6 `QMainWindow` with a `QWebEngineView` loading `dig/ui/index.html`. Minimum 1100×720; remember geometry.
2. `Bridge` QObject over `QWebChannel` with the slots listed in SPEC § Architecture. Implement `load`, `save`, `theme`, `openUrl`, `openPath`, `openDataFolder`, `setDesktopFileName` first; stub the rest to return clearly.
3. Storage module: SQLite state document with atomic writes, 300 ms debounce, 20-file history, corrupt-file recovery.
4. Unit tests for the storage module (pytest): save/load round trip, atomic write, history rotation, corrupt recovery.
5. **Commit + push:** `feat: web shell, bridge, state storage`.

## Phase 2: Move the prototype in
1. Split the prototype into `index.html`, `app.css`, `app.js`. Remove the prototype bar and wrapper. Bundle Geist and Geist Mono under `dig/ui/fonts/` with `@font-face`; remove the Google Fonts link.
2. Replace `seed()` with `bridge.load()`; if `setupDone` is false, open Setup. After every state mutation call a debounced `bridge.save(JSON.stringify(S))`. Keep every render and workflow function unchanged.
3. Wire theme: `S.theme === 'system'` resolves through `bridge.theme()` and re-renders on `colorSchemeChanged`.
4. Verify visually against the prototype screen by screen in both themes.
5. **Commit + push:** `feat: prototype ui integrated with persistent state`.

## Phase 3: Native pieces
1. `pickFile` copying into `~/.local/share/dig/attachments/{project_id}/` with collision suffixes; Files and Library file rows open via `openPath`; links via `openUrl`.
2. `exportJson` / `importJson` with a confirmation before replacing state on import; the Settings buttons use them.
3. `printPdf`: offscreen page, light palette, embedded fonts; wire Your week "Save as PDF", project Share, projects Share, roadmap Share. Each export excludes private groups and states the count omitted.
4. `HANDOFF.md` update. **Commit + push:** `feat: files, export, import, pdf`.

## Phase 4: Setup defaults and migration
1. Implement the Setup defaults table from SPEC § 3.1 exactly. Revisiting Setup only adds missing defaults.
2. Implement the v1 → v2 migration on first launch when a v1 database is found; keep the v1 file as `dig-v1.db.bak`.
3. Tests for defaults and migration.
4. **Commit + push:** `feat: setup defaults, v1 migration`.

## Phase 5: Desktop integration
1. App icon per DESIGN § App icon: SVG master, PNGs at all sizes, installed to `~/.local/share/icons/hicolor`. `.desktop` launcher in `~/.local/share/applications`. `QGuiApplication.setDesktopFileName("dig")` so KDE Plasma on Wayland groups the window with the launcher.
2. User-level installs only; Bazzite's `/usr` is immutable. `install.sh`, `uninstall.sh`, pinned `requirements.txt`, `run` script (venv + `python -m dig`).
3. About dialog (from Settings): version, AGPLv3, the Kamsiob links (YouTube https://youtube.com/@kamsiob, GitHub https://github.com/kamsiob, Website https://kamsiob.com, Buy Me a Coffee https://buymeacoffee.com/kamsiob, Telegram https://t.me/+g5LKm9rUnNcxMjk5, Feedback hello@kamsiob.com), and the support line "Built and carried by one person. If software made this way matters to you, there's a place to stand behind it. Either way, it's yours." with a "Support this work" button.
4. **Commit + push:** `feat: launcher, icon, about`.

## Phase 6: Fidelity pass
1. Side-by-side with the prototype: every screen, both tabs of the project page, every dialog, both themes. Fix any spacing, color, wording, or motion drift. Nothing may differ from the prototype except the removed prototype bar and the bridge-backed features.
2. Confirm zero network requests with networking disabled.
3. **Commit + push:** `fix: fidelity pass against prototype`.

## Phase 7: Automated tests
Playwright (or pytest-qt driving the web view) tests committed to the repo, covering: capture routing for every type with and without a project; inbox quick file and choose; done ✓ with undo; waiting set/resolve with day counts and history; stage move with unmet-checklist warning and undo; jump stage; checklist toggle/add/remove with bug tag; decision numbering, supersede, and cross-out; release recording feeding the week report; people add; file add copies the file; park/unpark effects on Home and roadmap; roadmap horizon moves at all, group, and project levels; resurfacing non-repeat; week report with private groups hidden and shown; settings edits reshaping types/stages/checklists; theme modes including live system change; persistence across restart; corrupt-state recovery; import replacing state; keyboard map.
**Commit + push:** `test: end-to-end suite`.

## Phase 8: Scripted user testing (mandatory before any export)
Drive the real app like a person for a week, on a fresh profile, and log every defect:
1. Fresh start, Setup with three work kinds, verify defaults and every empty state.
2. Add twelve things through Ctrl K of every type, with and without projects; verify each landed where the sentence said.
3. Sort the inbox both ways; throw one away.
4. Create three projects of different types; set next steps; move one through two stages with an unmet warning; undo one move.
5. Mark two projects waiting; resolve one; verify Home, roadmap, week, and the project's past waits.
6. Record four decisions, one replacing another; verify numbering across projects.
7. Record two releases; verify the project roadmap timeline and the week report.
8. Add people, links, files (including a name collision); open each.
9. Move projects across horizons at all three roadmap levels; park one; unpark it.
10. Start an idea as a project; verify origin callout and removal from Ideas; hit Show another five times.
11. Edit types, stages, and checklists in Settings; verify projects reflect it.
12. Export JSON, wipe, import; verify identical state. Corrupt the DB; verify recovery.
13. Switch Light → Dark → Follow system; change the OS scheme; restart; verify.
14. Export every PDF; open each; verify content, fonts, and private exclusion note.
15. Resize to minimum and large; restart; verify geometry memory.
16. Turn on reduce motion; verify stillness.
17. Fix every defect found, commit each (`fix: …`), and repeat the full pass until clean.
**Commit + push:** `test: scripted user pass complete`.

## Phase 9: Screenshots, README, release, export
1. Launch the finished app and take real screenshots (Home light, Home dark, Projects, Roadmap, project Work tab, project Roadmap tab, Your week, Add something dialog) into `docs/screenshots/`.
2. README: what Dig is (the setup sentence), philosophy (local only, no network, AGPLv3, donate-only), features, install/run for Bazzite/Linux, keyboard shortcuts table, screenshots, About links.
3. Version: this is a major release; choose the number by semver, state the number and one line of reasoning, tag it.
4. **Commit + push:** `docs: readme and screenshots; release {version}`.
5. Only now: export exactly one runnable copy to the desktop, deleting any previous exported build first.
6. Final summary: version and reasoning, decisions made on the person's behalf, defects found and fixed in Phase 8, anything deferred.
