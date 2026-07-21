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

/* ---------- editors and forms ---------- */

/* The title edits in place: it reads as the heading it is, not as a box. */
#EditorTitle {{
    background: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    padding: 2px 0px;
    font-family: "{serif}";
    font-size: 30px;
    font-weight: 600;
    color: {p.ink};
}}

#EditorTitle:hover {{
    border-bottom: 1px solid {p.seam};
}}

#EditorTitle:focus {{
    border-bottom: 1px solid {p.accent};
}}

#EditorMeta {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

#EditorNote {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    padding: 14px 16px;
    font-size: 15px;
    color: {p.ink};
}}

#EditorNote:focus {{
    border: 1px solid {p.accent};
}}

#FieldLabel {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_faint};
}}

#FormField, #FormArea {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    color: {p.ink};
    padding: 9px 12px;
    font-size: 14px;
}}

#FormField:focus, #FormArea:focus {{
    border: 1px solid {p.accent};
}}

#SearchField {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    color: {p.ink};
    padding: 9px 12px;
    font-size: 14px;
}}

#SearchField:focus {{
    border: 1px solid {p.accent};
}}

#ShowPromoted, #ShippedToggle {{
    font-size: 13px;
    color: {p.ink_dim};
}}

/* Delete stays quiet until it is reached for. */
#QuietDanger {{
    background: transparent;
    border: none;
    padding: 8px 4px;
    font-size: 13.5px;
    color: {p.ink_faint};
}}

#QuietDanger:hover, #QuietDanger:focus {{
    color: {p.copper};
    outline: none;
}}

#ConfirmDialog {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
}}

#ConfirmText {{
    font-size: 15px;
    color: {p.ink};
}}

#DangerButton {{
    background: {p.copper};
    color: {p.on_accent};
    border: none;
    padding: 8px 18px;
    font-size: 13.5px;
    font-weight: 600;
}}

#DangerButton:hover {{
    background: {p.accent_hover};
}}

#DangerButton:focus {{
    outline: none;
    border: 2px solid {p.ink};
    padding: 6px 16px;
}}

/* ---------- chips: square mono outlines, never filled pills ---------- */

#Chip {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_dim};
    border: 1px solid {p.seam};
    padding: 3px 9px;
}}

#ChipShipped {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.verdigris};
    border: 1px solid {p.verdigris};
    padding: 3px 9px;
}}

/* ---------- app detail ---------- */

#DetailDescription {{
    background: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    padding: 0px;
    font-size: 15px;
    color: {p.ink_dim};
}}

#DetailDescription:hover {{
    border-bottom: 1px solid {p.seam};
}}

#DetailDescription:focus {{
    border-bottom: 1px solid {p.accent};
    color: {p.ink};
}}

#MetaLink {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.accent};
    text-align: left;
}}

/* The GitHub address is both the link and the field that edits it. */
#MetaLinkField {{
    background: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    padding: 2px 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.accent};
}}

#MetaLinkField:hover {{
    border-bottom: 1px solid {p.seam};
}}

#MetaLinkField:focus {{
    border-bottom: 1px solid {p.accent};
}}

#MetaLink:hover, #MetaLink:focus {{
    color: {p.accent_hover};
    outline: none;
}}

#MetaField {{
    background: transparent;
    border: none;
    border-bottom: 1px solid transparent;
    padding: 2px 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.ink_faint};
}}

#MetaField:hover {{
    border-bottom: 1px solid {p.seam};
}}

#MetaField:focus {{
    border-bottom: 1px solid {p.accent};
    color: {p.ink};
}}

#MetaToggle {{
    background: transparent;
    border: none;
    padding: 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.ink_faint};
}}

#MetaToggle:hover, #MetaToggle:focus {{
    color: {p.verdigris};
    outline: none;
}}

/* The thread back to the jot this app came from. */
#OriginCallout {{
    background: {p.surface_raised};
    border-left: 3px solid {p.accent};
}}

#OriginTag {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.accent};
}}

#OriginText {{
    font-size: 13.5px;
    color: {p.ink_dim};
}}

/* ---------- sheets ---------- */

/* The two rules that name the sheets: gold for what it could do,
   copper for what is wrong with it. */
#SheetHeadFeature {{
    border-bottom: 2px solid {p.accent};
}}

#SheetHeadBug {{
    border-bottom: 2px solid {p.copper};
}}

#SheetCount {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

#SheetMarker {{
    font-family: "{mono}";
    font-size: 13px;
    color: {p.ink_faint};
}}

#SheetMarkerDone {{
    font-family: "{mono}";
    font-size: 13px;
    color: {p.verdigris};
}}

#SheetText {{
    font-size: 14px;
    color: {p.ink};
}}

#SheetTextDone {{
    font-size: 14px;
    color: {p.ink_faint};
}}

#SheetAdd {{
    background: transparent;
    border: none;
    padding: 8px 0px 0px 0px;
    font-family: "{mono}";
    font-size: 11.5px;
    color: {p.ink_dim};
    text-align: left;
}}

#SheetAdd:hover, #SheetAdd:focus {{
    color: {p.accent};
    outline: none;
}}

#SheetAdd:disabled {{
    color: {p.ink_faint};
}}

#SheetAddField {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    border-bottom: 2px solid {p.accent};
    padding: 8px 10px;
    font-size: 14px;
    color: {p.ink};
    margin-top: 6px;
}}

#SheetAddField:focus {{
    border: 1px solid {p.accent};
    border-bottom: 2px solid {p.accent};
}}

#SheetRemove {{
    background: transparent;
    border: none;
    padding: 0px 4px;
    font-family: "{mono}";
    font-size: 12px;
    color: {p.ink_faint};
}}

#SheetRemove:hover, #SheetRemove:focus {{
    color: {p.copper};
    outline: none;
}}

#SheetEmpty {{
    font-size: 13px;
    color: {p.ink_faint};
    padding: 10px 4px;
}}

/* ---------- screenshots and files ---------- */

#Thumb {{
    background: {p.surface_deep};
    border: 1px solid {p.seam};
}}

#ThumbImage {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.ink_faint};
    background: transparent;
}}

#ThumbName {{
    font-family: "{mono}";
    font-size: 10px;
    color: {p.ink_faint};
}}

#FileName {{
    font-family: "{mono}";
    font-size: 12.5px;
    color: {p.ink_dim};
}}

#FileSize {{
    font-family: "{mono}";
    font-size: 11px;
    color: {p.ink_faint};
}}

/* ---------- capture dialog ---------- */

/* Copper across the top: this is the existing-app side of the app. */
#CaptureDialog {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    border-top: 3px solid {p.copper};
}}

#CaptureSegment {{
    background: transparent;
    color: {p.ink_dim};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 0px;
    font-size: 13px;
}}

#CaptureSegment:hover {{
    color: {p.ink};
}}

#CaptureSegment[active="true"] {{
    background: {p.surface};
    color: {p.ink};
    border-bottom: 2px solid {p.copper};
    font-weight: 600;
}}

#CaptureSegment:focus {{
    outline: none;
    color: {p.ink};
}}

#CaptureField, #CapturePicker {{
    background: {p.surface_deep};
    border: 1px solid {p.seam};
    color: {p.ink};
    padding: 10px 12px;
    font-size: 14px;
}}

#CaptureField:focus, #CapturePicker:focus {{
    border: 1px solid {p.copper};
}}

#CaptureNoApps {{
    font-size: 13px;
    color: {p.ink_faint};
}}

/* ---------- about ---------- */

#AboutDialog {{
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    border-top: 3px solid {p.accent};
}}

#AboutTagline {{
    font-size: 13.5px;
    color: {p.ink_dim};
}}

#AboutLink {{
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 13.5px;
    font-weight: 600;
    color: {p.ink};
    text-align: left;
}}

#AboutLink:hover, #AboutLink:focus {{
    color: {p.accent};
    outline: none;
}}

#AboutLinkDetail {{
    font-size: 13.5px;
    color: {p.ink_dim};
}}

#AboutLicence {{
    font-family: "{mono}";
    font-size: {MONO_SMALL}px;
    color: {p.ink_faint};
}}

/* ---------- settings ---------- */

#FolderPath {{
    font-family: "{mono}";
    font-size: 12.5px;
    color: {p.ink_dim};
    background: {p.surface_raised};
    border: 1px solid {p.seam};
    padding: 9px 12px;
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
