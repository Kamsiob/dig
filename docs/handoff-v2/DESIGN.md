# Dig v2: Design system

The prototype's CSS is the source of truth; this document explains it so the parts that live outside the web view (icon, launcher assets, PDF exports, About dialog) match.

## Feel
Crisp, cool, calm, alive. White surfaces on cool gray in light mode; deep navy-black in dark mode. One action color (blue), one progress color per group, and a small semantic set. Color comes mostly from the person's own groups. Nothing shouts; things move a little when you touch them.

## Anti-slop rules (hard constraints)
No purple or violet anywhere. No gradients except the avatar's conic gradient and the faint radial in hover glows. No glassmorphism or backdrop blur. No Inter, Roboto, or system fonts for visible text. No identical three-card feature grids. No decorative illustrations. No exclamation marks in copy. No emoji in the UI.

## Tokens

Light:
```
--bg #F4F6FA   --panel #FFFFFF   --panel-2 #EDF1F7   --line #E1E7EF   --line-2 #C8D2DF
--ink #0E1421  --ink-2 #4A5568   --ink-3 #8593A6
--blue #2457F5 (hover #1A45D6, soft #E6EDFF)     action, links, focus
--teal #0BA39E (soft #DCF5F2)                    ideas, library files
--green #1E9E5A (soft #DDF4E7)                   done, shipped, releases
--amber #D9890B (soft #FBF0D6)                   waiting, hardware type, notes
--coral #E4573F (soft #FCE6E1)                   bugs, inbox badge, PDF chips
--rose #D14A7A (soft #FBE3EC)                    client-work type, roadmap icon
--red #D64545                                    destructive text only
```
Dark:
```
--bg #0B0F16   --panel #121823   --panel-2 #1A2231   --line #202A3A   --line-2 #2E3B50
--ink #E9EEF6  --ink-2 #9BA7BA   --ink-3 #5E6C82
--blue #5B9AFF (hover #7DB0FF, soft #15274E)  --teal #2FD6C9 (soft #0E302E)
--green #4ADE80 (soft #12301E)  --amber #F2B43E (soft #3B2D10)
--coral #FF7A62 (soft #3D1F18)  --rose #F472A6 (soft #3A1A29)  --red #F07171
```
Default group colors: teal #0BA39E, blue #2457F5, coral #E4573F, sage #6B8F71. New groups default to rose #D14A7A. Groups may be any color the person picks.

Shadows: `--shadow` for resting cards, `--shadow-2` for hover and sheets, `--shadow-lg` for dialogs. Every surface has a 1px inner top highlight (`--hi`). Focus: `--glow` 3px ring in the action color.

## Typography
Geist (400, 500, 600, 700) for everything visible. Geist Mono (400, 500) for decision numbers, counts, keyboard hints, file-type chips, stage numbers. Bundle both (SIL OFL).

Sizes: page title 24/600 with -0.025em tracking; section title 15/600; card title 15/600; body 13.5–14; helper and meta 12–12.5 in `--ink-3`; badges 11/600; mono chips 9.5–11. Tabular numerals on counts.

## Components
- **Buttons:** 9px radius; primary is blue with a soft blue shadow; ghost has no border; press compresses to 97%; hover lifts 1px.
- **Cards and boxes:** 12px radius, `--line` border, inner highlight, `--shadow`; hover lifts 2px and reveals a 3px group-colored edge on the left.
- **Rows:** 11px 14px padding, `--line` separators, hover fills `--panel-2`.
- **Badges:** pill, 11px, semantic soft background + strong text. Type badges: App blue, Hardware amber, Client work rose, Task neutral, other types teal.
- **Stage bar:** segmented, 6px tall, 3px radius; done segments group color at 45%, current at 100% with a soft ring, future `--panel-2`. Segments draw in from the left, staggered.
- **Stage strip (project page):** chips; done = tinted with the group color; current = solid group color with white text and a soft colored shadow.
- **Checkbox:** 17px, 5px radius; checked fills with the group color and springs (scale 0.8 → 1.15 → 1).
- **Section headings:** small 24px rounded colored icon + title + gray helper text + optional right-side link.
- **Dialogs:** 14px radius, spring in (translate -8px, scale .98 → 1). Footer on `--panel-2`.
- **Toasts:** bottom right, ink background, spring in; optional Undo in light blue.
- **Timeline (project roadmap):** 28px nodes on a 2px line; done nodes filled with the group color and a check; current node outlined in the group color with a pulsing halo.

## Motion
`--t` 180ms ease-out for color, background, and lift. `--spring` 320ms overshoot for checks, nav indicator, dialogs, toasts. Rows and cards enter with a 4px rise and staggered delays (20–140ms). Finished or resolved rows slide 24px right and fade before the list re-renders. All motion is disabled under `prefers-reduced-motion`.

## App icon and launcher
Rounded square (22% radius) in `--blue` with a simple white upward step-arrow (three ascending bars, the middle one taller) suggesting stages. SVG master plus PNGs at 16/24/32/48/64/128/256/512. Dark-mode-safe on both light and dark panels.

## PDF exports
Rendered from HTML through the web engine using the light palette regardless of app theme, Geist embedded. The week sheet exports exactly as the on-screen sheet. The project one-pager: name, type · group · stage, three stat tiles, notes, stage bar, releases. The projects overview and roadmap exports list shareable projects only, with a footer stating how many private groups were omitted.
