# DESIGN.md — Dig by Kamsiob

This file is the design authority for Dig. Every visual and interaction decision in the app derives from it. When in doubt, follow this file over instinct or defaults. The approved reference mockup is `design/dig-design.html` (interactive: theme switcher, capture dialog, Home and App Detail views).

## 1. Concept

Dig is a local-first personal app registry for vibe coders: a place to bury ideas and dig them back up. The design language is **expedition field notes**: a hand-sketched treasure map, expedition paper, ink, and the glint of a find. It is warm, crafted, and quietly playful. It is never corporate, never "AI-slop modern," never gamer-coded.

Two moods, one identity:
- **Light ("Field Notes")**: warm expedition paper, green-black ink, gold accent. Default.
- **Dark ("Excavation at Dusk")**: deep green-black forest floor, bone text, amber accent.

## 2. Anti-slop rules (hard constraints)

These are banned because they are the recognized fingerprint of AI-generated design:
- NO purple/indigo/violet anywhere. No purple-to-blue or purple-to-cyan gradients.
- NO gradients at all except the two explicitly specified (strata ruler ticks, wordmark rule, both are flat two-tone constructions, not soft fades).
- NO glassmorphism, no backdrop blur, no frosted panels, no neon glows.
- NO Inter, Roboto, Space Grotesk, or system-default font stacks for visible text.
- NO rounded-corner card grids, no three-feature-cards-in-a-row, no icon-on-top cards.
- NO thin gray 1px-border cards with soft drop shadows as a repeating pattern.
- NO gradient text, no pill badges floating over centered heroes, no fade-in-on-scroll.
- Corners are square (0 border-radius) everywhere except the status lamp dot.
- Layout is left-aligned. Nothing is centered except dialog content positioning.

## 3. Color tokens

Both palettes must ship. Theme setting offers Light / Dark / System (follows OS preference live).

### Light — "Field Notes" (default)
| Token | Hex | Use |
|---|---|---|
| bg | #EFE8D8 | behind the window |
| surface | #F5EFE1 | main surface |
| surface-deep | #EBE3CF | rail, input wells |
| surface-raised | #FAF6EB | hover, raised blocks, dialogs |
| seam | #D9CFB6 | hairline separators |
| ink | #33372A | primary text |
| ink-dim | #6C6D59 | secondary text |
| ink-faint | #9B9781 | metadata, hints |
| accent (gold) | #A97A16 | ideas, primary actions, active nav |
| accent-hover | #8F6708 | |
| on-accent | #FFFDF4 | text on gold/copper buttons |
| copper | #A5572E | features/bugs, unearthed specimen |
| verdigris | #4E7A62 | completed items, status lamp |
| map-ink | rgba(64,66,48,0.16) | treasure map linework |
| map-accent | rgba(169,122,22,0.28) | map route, X, shovel blade |

### Dark — "Excavation at Dusk"
| Token | Hex |
|---|---|
| bg | #0B0F0B |
| surface | #16201A |
| surface-deep | #10160F |
| surface-raised | #1E2C22 |
| seam | #2E3F32 |
| ink | #EFE6D4 |
| ink-dim | #A9A493 |
| ink-faint | #6F6F60 |
| accent (amber) | #D9A13B |
| accent-hover | #EDB44E |
| on-accent | #1A1305 |
| copper | #C46A3F |
| verdigris | #6FA08A |
| map-ink | rgba(239,230,212,0.10) |
| map-accent | rgba(217,161,59,0.22) |

**Color semantics (both themes):** gold/amber = new ideas and primary actions. Copper = features, bugs, and the unearthed specimen. Verdigris = done/healthy. This split is load-bearing; never swap them.

## 4. Typography

Bundle the font files with the app (all are SIL OFL licensed):
- **Fraunces** (display serif): idea titles, app names, screen headings, the wordmark, jot input text. Weights 400 to 700.
- **IBM Plex Sans** (UI): body, buttons, nav, descriptions. Weights 400 to 600.
- **IBM Plex Mono** (utility): metadata, timestamps, section eyebrows, keyboard hints, counts, file rows, chips. Weights 400 to 500.

Eyebrow style (used for all section headers): Plex Mono, ~11px, uppercase, letter-spacing 0.15em, ink-dim.

Never use the OS default font for visible text.

## 5. Signature elements

1. **The treasure map background** (Home only): a full-height sketched map behind content at whisper opacity: island coastlines (double contour), 4 small mountain ranges, a river squiggle, curved wind gusts with curled ends, a dashed gold route leading to a bold gold X, and a planted shovel (D-grip handle, angled shaft, blade with faint gold wash, soil flecks) in the top right. Linework uses map-ink; route/X/shovel-blade use map-accent. It must never compete with content. Implemented as a static SVG (reference paths in the mockup).
2. **Paper grain**: full-window fractal-noise texture at ~5% opacity over everything.
3. **The strata gauge**: left edge of the Unearthed block. Four stacked flat soil-color bands (light: #CDC3A4, #B3A57E, #C0954C, copper; dark: #2A3A2C, #40492E, #6E5A2E, copper) with a tick-ruler column of repeating 1px seam-color marks on its right edge.
4. **The wordmark**: "Dig" in Fraunces bold (large), followed by a small gold ✕ rotated about -6°, with a two-tone flat rule beneath (gold ~62%, gap, copper remainder). X marks the spot. The About dialog reuses a mini version.

Spend boldness only on these. Everything else stays quiet.

## 6. Screens & layout

App window: left rail (~216px) + main content. Rail on surface-deep with a seam border.

### Rail
Top to bottom: wordmark + rule, "BY KAMSIOB" byline (mono eyebrow), nav (Home, Ideas, Apps, Export, Settings, each with a mono number hint 1 to 5; active item gets ink text, surface background, 3px inset gold left bar), Appearance segmented control (Light / Dark / System; active segment has 2px gold bottom inset), then bottom-left footer: verdigris status lamp + "local only · nothing leaves", and a small underlined "About Dig" trigger + version in mono faint.

### Home
1. Mono date eyebrow, then H1 in Fraunces: `What did you just think of?` with "think of?" in accent color.
2. **Capture row**, two labeled columns side by side:
   - Left (flexible): eyebrow label with gold square dot, "NEW APP IDEA". The jot box: surface-raised well, seam border, 2px gold bottom border. Serif textarea, placeholder "Jot the new idea before it goes…". Below: mono hint "Shift+Enter for a new line" and a gold "Keep it ↵" button. Focus state: 1px gold ring + soft gold glow shadow (the one glow in the app).
   - Right (172px): eyebrow label with copper square dot, "EXISTING APP". The Capture panel: 2px dashed copper border (the only dashed element, echoing the map route), background tinted ~8% copper over surface-raised (16% on hover + soft copper shadow), containing large +, "Capture" label, "feature or bug" sub-label, and a Ctrl K key badge. Opens the capture dialog.
3. **Recent**: eyebrow + "All ideas →" link. Exactly 3 ledger rows (no cards): mono timestamp, Fraunces title, dimmed one-line gist, seam bottom border, surface-raised hover. On hover/focus a mono gold "→ make it an app" action fades in (the promote flow).
4. **Unearthed** (the signature moment): raised block with seam border and soft shadow, strata gauge on the left edge. Content: copper mono tag "UNEARTHED · BURIED {duration}", Fraunces title, dimmed gist, mono meta line (e.g. "jotted May 29 · never opened since"). Top right actions: "Open it" (gold, semibold) and "Dig again ↻" (dim). Selection is pure random from ideas older than the recent set; "Dig again" redraws (never returning the same idea it just showed).

Saving a jot: the new idea appears at the top of Recent immediately with a brief highlight so the save is trusted.

### Capture dialog (Ctrl K from anywhere in-app, or the panel)
Modal on a translucent surface-deep scrim. Dialog: surface-raised, seam border, 3px copper top border, ✕ close. Contents in order: copper-dotted "CAPTURE" eyebrow, Feature/Bug segmented toggle (active segment: copper bottom inset), mono field label "WHAT IS IT?", one-line text input, mono field label "WHICH APP?", app dropdown, then Cancel (ghost) and "Keep it ↵" (copper) right-aligned. Fully keyboard drivable: type, Tab, Enter.

### App Detail (Apps → an app)
Top to bottom:
1. "← All apps" mono back link.
2. App name (Fraunces H1) + chips: "SHIPPED" (verdigris outline) and version (seam outline). Chips are square-cornered mono outlines, never filled pills.
3. Description paragraph (ink-dim), then a mono meta row: GitHub link (gold), license, stack.
4. **Origin callout**: 3px gold left border on surface-raised: mono gold tag "DUG FROM AN IDEA · JOTTED {date}", the original jot text in bold, and its promote date. This is the idea-to-app thread made visible.
5. **Sheets**, two equal columns: Feature sheet (2px gold bottom rule on its header) and Bug sheet (copper rule). Header: eyebrow + mono count "N open · N done". Line items: mono `[ ]` / `[✓]` marker + text, seam separators, click toggles done. Done items: verdigris marker, faint struck-through text. Each sheet ends with a mono "+ add feature" / "+ add bug" link. Deliberately no priorities, statuses, dates, or assignees. Not Jira.
6. **Notes & talking points**: bordered surface-raised block, simple list.
7. **Screenshots**: horizontal thumbnails (seam border, surface-deep, mono filename label), click to view.
8. **Attachments**: mono file rows (name + size), seam separators. Files are copied into the app-managed data folder on attach.

### Ideas screen
Same ledger-row language as Recent, full list, newest first, with search. Row actions: open, promote to app, delete.

### Export screen
Choose what goes in the PDF (shipped apps, ideas, or both; per-entry include/exclude), then export. The PDF is the shareable portfolio: same palette (light theme), Fraunces headings, one page per app with description, links, and screenshots.

### Settings
Appearance (Light/Dark/System), data folder location display, content licensing note. Nothing else in v1.

### About dialog (from the rail trigger)
Mini wordmark, tagline "A place to bury ideas and dig them back up.", link list: YouTube (Kamsiob on Linux) https://youtube.com/@kamsiob · GitHub https://github.com/kamsiob · Website https://kamsiob.com · Buy Me a Coffee https://buymeacoffee.com/kamsiob · Telegram (Kamsiob Lab) https://t.me/+g5LKm9rUnNcxMjk5 · Feedback hello@kamsiob.com. Footer in mono: "Free and open source · AGPLv3 / Everything stays on your machine."

## 7. Interaction & motion

- Transitions: 120 to 160ms ease on color/background/shadow only. No bounce, no elastic, no scroll-triggered animation, no parallax.
- Every primary action displays its key hint in mono (↵ on Keep it, Ctrl K on Capture, 1 to 5 on nav).
- Keyboard-first: jot saves on Enter; Shift+Enter for newline; Ctrl K opens capture from any screen; nav via number keys.
- Visible focus states everywhere (gold or copper outlines). Respect reduced-motion preference.
- System-wide OS-level capture hotkey is deferred (later: KDE custom shortcut invoking the running app; never an in-app global key grab on Wayland).

## 8. Voice

Copy is plain, warm, and specific. Buttons say what they do ("Keep it", "Dig again", "make it an app"). Metadata is honest and lightly evocative ("buried 6 weeks", "never opened since", "local only · nothing leaves"). No exclamation marks, no marketing speak, no "unleash/supercharge/seamless", no emoji in the UI.
