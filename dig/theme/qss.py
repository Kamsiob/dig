"""Build the application stylesheet from a palette.

Every colour is a token. Corners are square everywhere. Nothing here uses a
gradient, a rounded card, or a system font.

Qt stylesheets have no box-shadow, so the two soft shadows in the design (the
gold focus glow on the jot box, the lift under the Unearthed block) are drawn
with QGraphicsDropShadowEffect where they are built, not here.
"""

from __future__ import annotations

from dig.theme import fonts
from dig.theme.tokens import Palette

# Type scale, in px, taken from design/dig-design.html.
EYEBROW_SIZE = 11
MONO_SMALL = 10.5
BODY_SIZE = 15


def build(p: Palette) -> str:
    """The full stylesheet for one palette."""
    serif = fonts.serif()
    sans = fonts.sans()
    mono = fonts.mono()

    return f"""
/* ---------- foundation ---------- */

QWidget {{
    background: transparent;
    color: {p.ink};
    font-family: "{sans}";
    font-size: {BODY_SIZE}px;
    border-radius: 0px;
}}

QMainWindow, #Root {{
    background: {p.surface};
}}

QToolTip {{
    background: {p.surface_raised};
    color: {p.ink};
    border: 1px solid {p.seam};
    padding: 5px 8px;
    font-family: "{mono}";
    font-size: 11px;
}}

/* ---------- left rail ---------- */

#Rail {{
    background: {p.surface_deep};
    border-right: 1px solid {p.seam};
}}

#Wordmark {{
    font-family: "{serif}";
    font-size: 40px;
    font-weight: 700;
    color: {p.ink};
}}

#Byline {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_faint};
}}

/* Navigation. The active item takes ink text, the main surface, and a
   three pixel gold bar down its left edge. */
#NavItem {{
    background: transparent;
    color: {p.ink_dim};
    border: none;
    border-left: 3px solid transparent;
    padding: 9px 24px 9px 21px;
    text-align: left;
    font-size: 14px;
}}

#NavItem:hover {{
    color: {p.ink};
}}

#NavItem[active="true"] {{
    color: {p.ink};
    background: {p.surface};
    border-left: 3px solid {p.accent};
    font-weight: 500;
}}

#NavItem:focus {{
    outline: none;
    color: {p.ink};
    background: {p.surface_raised};
}}

#NavItem[active="true"]:focus {{
    background: {p.surface};
}}

#NavHint {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.ink_faint};
    background: transparent;
}}

/* ---------- segmented control (Appearance) ---------- */

#SegmentLabel {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.ink_faint};
}}

#Segmented {{
    border: 1px solid {p.seam};
    background: transparent;
}}

#Segment {{
    background: transparent;
    color: {p.ink_dim};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 4px;
    font-size: 12px;
}}

#Segment:hover {{
    color: {p.ink};
}}

#Segment[active="true"] {{
    background: {p.surface};
    color: {p.ink};
    border-bottom: 2px solid {p.accent};
    font-weight: 600;
}}

#Segment:focus {{
    outline: none;
    color: {p.ink};
    background: {p.surface_raised};
}}

/* ---------- rail footer ---------- */

#RailFoot {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.ink_faint};
}}

#AboutTrigger {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_faint};
    text-align: left;
}}

#AboutTrigger:hover, #AboutTrigger:focus {{
    color: {p.accent};
    outline: none;
}}

/* ---------- main content ---------- */

#MainArea {{
    background: transparent;
}}

#Eyebrow {{
    font-family: "{mono}";
    font-size: {EYEBROW_SIZE}px;
    color: {p.ink_faint};
}}

#SectionEyebrow {{
    font-family: "{mono}";
    font-size: {EYEBROW_SIZE}px;
    font-weight: 500;
    color: {p.ink_dim};
}}

#H1 {{
    font-family: "{serif}";
    font-size: 32px;
    font-weight: 500;
    color: {p.ink};
}}

#H1Accent {{
    font-family: "{serif}";
    font-size: 32px;
    font-weight: 500;
    color: {p.accent};
}}

#Placeholder {{
    font-family: "{mono}";
    font-size: 12px;
    color: {p.ink_faint};
}}

#BodyText {{
    color: {p.ink_dim};
}}

/* ---------- home: the jot well ---------- */

#BoxLabel {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_dim};
}}

/* The one well in the app that carries a gold underline: this is where a
   new idea goes. */
#JotBox {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    border-bottom: 2px solid {p.accent};
}}

#JotField {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{serif}";
    font-size: 19px;
    color: {p.ink};
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}

#JotHint {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

/* ---------- home: the capture panel ---------- */

/* The only dashed element in Dig, echoing the route on the map. */
#CapturePanel {{
    background: {p.surface_raised};
    border: 2px dashed {p.copper};
}}

#CapturePanel:hover {{
    background: {p.surface_deep};
}}

#CapturePlus {{
    font-size: 26px;
    font-weight: 600;
    color: {p.copper};
}}

#CaptureLabel {{
    font-size: 14px;
    font-weight: 600;
    color: {p.ink};
}}

#CaptureSub {{
    font-size: 12px;
    color: {p.ink_dim};
}}

#CaptureKey {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.copper};
    border: 1px solid {p.copper};
    padding: 2px 7px;
}}

/* ---------- ledger rows ---------- */

#RowWhen {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

#RowTitle {{
    font-family: "{serif}";
    font-size: 16.5px;
    font-weight: 600;
    color: {p.ink};
}}

#RowTitleDim {{
    font-family: "{serif}";
    font-size: 16.5px;
    font-weight: 600;
    color: {p.ink_faint};
}}

#RowSuffix {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

#RowGist {{
    font-size: 13.5px;
    color: {p.ink_dim};
}}

#RowPromote {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{mono}";
    font-size: 11px;
    color: {p.accent};
    text-align: left;
}}

#RowPromote:hover, #RowPromote:focus {{
    color: {p.accent_hover};
    outline: none;
}}

#RowDelete {{
    background: transparent;
    border: none;
    padding: 0px 4px;
    font-family: "{mono}";
    font-size: 12px;
    color: {p.ink_faint};
}}

#RowDelete:hover, #RowDelete:focus {{
    color: {p.copper};
    outline: none;
}}

#EmptyState {{
    color: {p.ink_faint};
    font-size: 13.5px;
    padding: 14px 8px;
}}

/* ---------- unearthed ---------- */

#Unearthed {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
}}

#UnearthedBody {{
    background: transparent;
}}

#UnearthedTag {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    font-weight: 500;
    color: {p.copper};
}}

#UnearthedTitle {{
    font-family: "{serif}";
    font-size: 22px;
    font-weight: 600;
    color: {p.ink};
}}

#UnearthedGist {{
    font-size: 15px;
    color: {p.ink_dim};
}}

#UnearthedMeta {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

#UnearthedOpen {{
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 13px;
    font-weight: 600;
    color: {p.accent};
}}

#UnearthedOpen:hover, #UnearthedOpen:focus {{
    color: {p.accent_hover};
    outline: none;
}}

#UnearthedAgain {{
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 13px;
    color: {p.ink_dim};
}}

#UnearthedAgain:hover, #UnearthedAgain:focus {{
    color: {p.ink};
    outline: none;
}}

/* ---------- notices ---------- */

#NoticeBar {{
    background: {p.surface_raised};
    border-bottom: 2px solid {p.copper};
}}

#NoticeText {{
    color: {p.ink};
    font-size: 13.5px;
}}

/* ---------- links and quiet actions ---------- */

#LinkAccent {{
    background: transparent;
    border: none;
    padding: 0px;
    color: {p.accent};
    font-size: 13px;
    font-weight: 500;
    text-align: left;
}}

#LinkAccent:hover, #LinkAccent:focus {{
    color: {p.accent_hover};
    outline: none;
}}

#BackLink {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.ink_dim};
    text-align: left;
}}

#BackLink:hover, #BackLink:focus {{
    color: {p.accent};
    outline: none;
}}

/* ---------- buttons ---------- */

#PrimaryButton {{
    background: {p.accent};
    color: {p.on_accent};
    border: none;
    padding: 8px 20px;
    font-size: 13.5px;
    font-weight: 600;
}}

#PrimaryButton:hover {{
    background: {p.accent_hover};
}}

#PrimaryButton:focus {{
    outline: none;
    border: 2px solid {p.ink};
    padding: 6px 18px;
}}

#PrimaryButton:disabled {{
    background: {p.seam};
    color: {p.ink_faint};
}}

#CopperButton {{
    background: {p.copper};
    color: {p.on_accent};
    border: none;
    padding: 8px 20px;
    font-size: 13.5px;
    font-weight: 600;
}}

#CopperButton:hover {{
    background: {p.accent_hover};
}}

#CopperButton:focus {{
    outline: none;
    border: 2px solid {p.ink};
    padding: 6px 18px;
}}

#CopperButton:disabled {{
    background: {p.seam};
    color: {p.ink_faint};
}}

#GhostButton {{
    background: transparent;
    color: {p.ink_dim};
    border: none;
    padding: 8px 16px;
    font-size: 13.5px;
    font-weight: 600;
}}

#GhostButton:hover, #GhostButton:focus {{
    color: {p.ink};
    outline: none;
}}

/* ---------- inputs ---------- */

QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {p.surface_deep};
    border: 1px solid {p.seam};
    color: {p.ink};
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
    padding: 8px 10px;
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}

QComboBox {{
    background: {p.surface_deep};
    border: 1px solid {p.seam};
    color: {p.ink};
    padding: 8px 10px;
}}

QComboBox:focus {{
    border: 1px solid {p.copper};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    color: {p.ink};
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
    outline: none;
}}

QCheckBox {{
    color: {p.ink};
    spacing: 9px;
}}

QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {p.ink_faint};
    background: {p.surface_raised};
}}

QCheckBox::indicator:checked {{
    background: {p.verdigris};
    border: 1px solid {p.verdigris};
}}

QCheckBox::indicator:focus {{
    border: 1px solid {p.accent};
}}

/* ---------- scrollbars: quiet, square, no arrows ---------- */

QScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {p.seam};
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background: {p.ink_faint};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: {p.seam};
    min-width: 32px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {p.ink_faint};
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
    background: none;
    border: none;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ---------- dialogs ---------- */

QDialog {{
    background: {p.surface_raised};
}}

#DialogTitle {{
    font-family: "{serif}";
    font-size: 24px;
    font-weight: 700;
    color: {p.ink};
}}
"""
