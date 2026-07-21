"""The PDF portfolio.

A portfolio, not a report: what the apps are and what they look like. Bug
sheets are deliberately left out.

The PDF is always the light palette, whatever the app is wearing. It is meant
to be printed, attached to an email, and read by someone else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from dig import paths
from dig.theme.tokens import LIGHT

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 56.0

SERIF = "Dig-Serif"
SERIF_BOLD = "Dig-Serif-Bold"
SANS = "Dig-Sans"
MONO = "Dig-Mono"

MAX_SHOTS_PER_APP = 4

_fonts_registered = False


def register_pdf_fonts() -> None:
    """Embed the bundled fonts so the PDF reads the same on any machine."""
    global _fonts_registered
    if _fonts_registered:
        return
    folder = paths.fonts_dir()
    for name, filename in (
        (SERIF, "Fraunces-Regular.ttf"),
        (SERIF_BOLD, "Fraunces-SemiBold.ttf"),
        (SANS, "IBMPlexSans-Regular.ttf"),
        (MONO, "IBMPlexMono-Regular.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    _fonts_registered = True


# ---------- what goes in ----------


@dataclass
class AppPage:
    """One app's page, gathered before rendering starts."""

    name: str
    description: str = ""
    github_url: str = ""
    version_label: str = ""
    shipped: bool = False
    open_features: int = 0
    screenshots: list[str] = field(default_factory=list)


@dataclass
class IdeaLine:
    title: str
    jotted: str


@dataclass
class Portfolio:
    """Everything the PDF needs, with no database or widget attached.

    Gathered on the main thread so the rendering can run on a worker.
    """

    apps: list[AppPage] = field(default_factory=list)
    ideas: list[IdeaLine] = field(default_factory=list)
    made_on: str = ""

    @property
    def page_count(self) -> int:
        """Cover, one page per app, and the ideas page when there are ideas."""
        return 1 + len(self.apps) + (1 if self.ideas else 0)

    @property
    def is_empty(self) -> bool:
        return not self.apps and not self.ideas


# ---------- drawing ----------


def _colour(token: str) -> tuple[float, float, float]:
    """A hex token as the 0-1 triple reportlab wants."""
    value = token.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    """Break text into lines that fit, on word boundaries."""
    words = (text or "").split()
    if not words:
        return []
    lines: list[str] = []
    line = words[0]
    for word in words[1:]:
        candidate = f"{line} {word}"
        if pdfmetrics.stringWidth(candidate, font, size) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def _draw_wordmark(canvas: pdfcanvas.Canvas, x: float, y: float, size: float) -> None:
    """"Dig" with the tilted gold cross beside it, and the two-tone rule.

    The cross is drawn rather than typeset: it is not in the bundled fonts.
    """
    canvas.setFillColorRGB(*_colour(LIGHT.ink))
    canvas.setFont(SERIF_BOLD, size)
    canvas.drawString(x, y, "Dig")

    reach = size * 0.16
    cross_x = x + pdfmetrics.stringWidth("Dig", SERIF_BOLD, size) + size * 0.28
    cross_y = y + size * 0.30
    canvas.saveState()
    canvas.translate(cross_x, cross_y)
    canvas.rotate(-6)
    canvas.setStrokeColorRGB(*_colour(LIGHT.accent))
    canvas.setLineWidth(max(1.4, size * 0.055))
    canvas.setLineCap(1)
    canvas.line(-reach, -reach, reach, reach)
    canvas.line(reach, -reach, -reach, reach)
    canvas.restoreState()

    # The rule: a run of gold, a gap, then copper. Kept clear of the descender
    # on the "g", which reaches well below the baseline in Fraunces.
    rule_y = y - size * 0.40
    rule_width = size * 3.6
    canvas.setFillColorRGB(*_colour(LIGHT.accent))
    canvas.rect(x, rule_y, rule_width * 0.62, 3, stroke=0, fill=1)
    canvas.setFillColorRGB(*_colour(LIGHT.copper))
    canvas.rect(
        x + rule_width * 0.68, rule_y, rule_width * 0.32, 3, stroke=0, fill=1
    )


def _draw_chip(
    canvas: pdfcanvas.Canvas, x: float, y: float, text: str, colour: str
) -> float:
    """A square-cornered mono outline. Returns its width."""
    size = 7.5
    padding = 5.0
    width = pdfmetrics.stringWidth(text, MONO, size) + padding * 2
    height = 14.0
    canvas.setStrokeColorRGB(*_colour(colour))
    canvas.setLineWidth(0.7)
    canvas.rect(x, y - 3.5, width, height, stroke=1, fill=0)
    canvas.setFillColorRGB(*_colour(colour))
    canvas.setFont(MONO, size)
    canvas.drawString(x + padding, y + 0.5, text)
    return width


def _cover(canvas: pdfcanvas.Canvas, portfolio: Portfolio) -> None:
    canvas.setFillColorRGB(*_colour(LIGHT.surface))
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)

    _draw_wordmark(canvas, MARGIN, PAGE_HEIGHT - 300, 54)

    canvas.setFillColorRGB(*_colour(LIGHT.ink_dim))
    canvas.setFont(SANS, 13)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 340, "by Kamsiob")

    canvas.setFillColorRGB(*_colour(LIGHT.ink_faint))
    canvas.setFont(MONO, 9.5)
    canvas.drawString(MARGIN, PAGE_HEIGHT - 362, portfolio.made_on.upper())

    canvas.setFillColorRGB(*_colour(LIGHT.ink_dim))
    canvas.setFont(SERIF, 15)
    canvas.drawString(
        MARGIN, 150, "A place to bury ideas and dig them back up."
    )
    canvas.setFillColorRGB(*_colour(LIGHT.ink_faint))
    canvas.setFont(MONO, 8.5)
    canvas.drawString(MARGIN, 128, "LOCAL ONLY · NOTHING LEAVES")


def _app_page(canvas: pdfcanvas.Canvas, app: AppPage) -> None:
    canvas.setFillColorRGB(*_colour(LIGHT.surface))
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)

    y = PAGE_HEIGHT - MARGIN - 20
    content_width = PAGE_WIDTH - MARGIN * 2

    canvas.setFillColorRGB(*_colour(LIGHT.ink))
    canvas.setFont(SERIF_BOLD, 26)
    canvas.drawString(MARGIN, y, app.name)
    y -= 26

    chip_x = MARGIN
    if app.shipped:
        chip_x += _draw_chip(canvas, chip_x, y, "SHIPPED", LIGHT.verdigris) + 8
    if app.version_label.strip():
        _draw_chip(canvas, chip_x, y, app.version_label.upper(), LIGHT.ink_faint)
    if app.shipped or app.version_label.strip():
        y -= 26
    else:
        y -= 8

    if app.description.strip():
        canvas.setFillColorRGB(*_colour(LIGHT.ink_dim))
        canvas.setFont(SANS, 11)
        for line in _wrap(app.description, SANS, 11, content_width):
            canvas.drawString(MARGIN, y, line)
            y -= 16
        y -= 6

    if app.github_url.strip():
        canvas.setFillColorRGB(*_colour(LIGHT.accent))
        canvas.setFont(MONO, 9.5)
        canvas.drawString(MARGIN, y, app.github_url.strip())
        y -= 22

    # A seam under the header.
    canvas.setStrokeColorRGB(*_colour(LIGHT.seam))
    canvas.setLineWidth(0.7)
    canvas.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
    y -= 26

    y = _draw_screenshots(canvas, app, y, content_width)

    # One quiet line. No bug counts: this is a portfolio, not a report.
    canvas.setFillColorRGB(*_colour(LIGHT.ink_faint))
    canvas.setFont(MONO, 9)
    word = "feature" if app.open_features == 1 else "features"
    canvas.drawString(MARGIN, MARGIN, f"{app.open_features} {word} still open")


def _draw_screenshots(
    canvas: pdfcanvas.Canvas, app: AppPage, y: float, content_width: float
) -> float:
    """Up to four screenshots, two across, each scaled to fit its cell."""
    shots = [s for s in app.screenshots if Path(s).is_file()][:MAX_SHOTS_PER_APP]
    if not shots:
        return y

    gap = 16.0
    cell_width = (content_width - gap) / 2.0
    cell_height = 165.0

    for index, shot in enumerate(shots):
        column = index % 2
        row = index // 2
        cell_x = MARGIN + column * (cell_width + gap)
        cell_y = y - (row + 1) * cell_height - row * gap

        try:
            image = ImageReader(shot)
            width, height = image.getSize()
        except Exception:  # noqa: BLE001 - a bad image must not stop the export
            continue
        if not width or not height:
            continue

        scale = min(cell_width / width, cell_height / height)
        drawn_width = width * scale
        drawn_height = height * scale
        offset_x = cell_x + (cell_width - drawn_width) / 2.0
        offset_y = cell_y + (cell_height - drawn_height) / 2.0

        canvas.setStrokeColorRGB(*_colour(LIGHT.seam))
        canvas.setLineWidth(0.7)
        canvas.rect(offset_x, offset_y, drawn_width, drawn_height, stroke=1, fill=0)
        canvas.drawImage(
            image,
            offset_x,
            offset_y,
            width=drawn_width,
            height=drawn_height,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )

    rows = (len(shots) + 1) // 2
    return y - rows * cell_height - max(0, rows - 1) * gap - 20


def _ideas_page(canvas: pdfcanvas.Canvas, portfolio: Portfolio) -> None:
    canvas.setFillColorRGB(*_colour(LIGHT.surface))
    canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)

    y = PAGE_HEIGHT - MARGIN - 20
    canvas.setFillColorRGB(*_colour(LIGHT.ink))
    canvas.setFont(SERIF_BOLD, 24)
    canvas.drawString(MARGIN, y, "Ideas in the ground")
    y -= 20

    canvas.setFillColorRGB(*_colour(LIGHT.ink_faint))
    canvas.setFont(MONO, 9)
    canvas.drawString(MARGIN, y, "NOT BUILT YET")
    y -= 28

    canvas.setStrokeColorRGB(*_colour(LIGHT.seam))
    canvas.setLineWidth(0.7)

    for idea in portfolio.ideas:
        if y < MARGIN + 40:
            canvas.showPage()
            canvas.setFillColorRGB(*_colour(LIGHT.surface))
            canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, stroke=0, fill=1)
            y = PAGE_HEIGHT - MARGIN - 20

        canvas.setFillColorRGB(*_colour(LIGHT.ink_faint))
        canvas.setFont(MONO, 8.5)
        canvas.drawString(MARGIN, y, idea.jotted.upper())

        canvas.setFillColorRGB(*_colour(LIGHT.ink))
        canvas.setFont(SERIF, 13)
        canvas.drawString(MARGIN + 78, y, idea.title)

        y -= 10
        canvas.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
        y -= 20


def write_portfolio(portfolio: Portfolio, destination: Path | str) -> Path:
    """Render the PDF. Safe to run on a worker thread: no store, no widgets."""
    register_pdf_fonts()
    target = Path(destination).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)

    canvas = pdfcanvas.Canvas(str(target), pagesize=A4)
    canvas.setTitle("Dig Portfolio")
    canvas.setAuthor("Kamsiob")
    canvas.setSubject("A portfolio of apps and ideas")

    _cover(canvas, portfolio)
    canvas.showPage()

    for app in portfolio.apps:
        _app_page(canvas, app)
        canvas.showPage()

    if portfolio.ideas:
        _ideas_page(canvas, portfolio)
        canvas.showPage()

    canvas.save()
    return target
