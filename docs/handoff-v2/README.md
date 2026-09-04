# Dig v2 handoff

This folder is the complete reference for building Dig v2. Nothing in it is a suggestion. The prototype is the app; the documents describe it so nothing has to be inferred.

| File | What it is | How to use it |
|---|---|---|
| `design/dig-prototype.html` | The approved, working prototype. Every screen, dialog, workflow, color, animation, and word of copy. Fully interactive with in-memory state. | This IS the UI. Ship its HTML, CSS, and JS as the app's interface (see `SPEC.md` § Architecture). When any question comes up about how something looks or behaves, open this file and match it. |
| `DESIGN.md` | The design system extracted from the prototype: tokens, typography, components, motion, and the anti-slop rules. | Use for the icon, the PDF exports, the launcher assets, and any surface that is not already covered by the prototype's own CSS. |
| `SPEC.md` | The data model, every screen, every workflow, every rule, extracted from the prototype's JavaScript. | The behavioral contract. The Python side must implement exactly this. |
| `BUILD_PLAN.md` | Phased build with a commit at the end of every phase, a mandatory testing phase, and a release phase. | Follow it in order. Do not skip or merge phases. |

Read `README.md` (this file), then `SPEC.md` fully, then `BUILD_PLAN.md` fully, then open the prototype in a browser and click through every screen and dialog before writing any code. Refer to `DESIGN.md` as needed.

Open the prototype by double-clicking it or `xdg-open design/dig-prototype.html`. Use the "Screen grid" button at the top to see every screen at once. Use "Reset data" to restore the sample state.
