"""How Dig talks about time.

Metadata is honest and lightly evocative: "2d ago", "buried 6 weeks",
"never opened since". Never a raw timestamp in front of the user.
"""

from __future__ import annotations

from datetime import datetime, timezone

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
WEEK = 7 * DAY

# Past roughly two months, a relative distance stops meaning anything and the
# date itself is more use.
DATE_CUTOFF = 8 * WEEK


def parse(stamp: str | None) -> datetime | None:
    """Read a stored timestamp. Returns None for anything unreadable."""
    if not stamp:
        return None
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_since(stamp: str | None, now: datetime | None = None) -> float | None:
    moment = parse(stamp)
    if moment is None:
        return None
    return ((now or _now()) - moment).total_seconds()


def on_date(stamp: str | None, now: datetime | None = None) -> str:
    """A plain calendar date: "May 29", or "May 29, 2025" in another year."""
    moment = parse(stamp)
    if moment is None:
        return ""
    local = moment.astimezone()
    reference = (now or _now()).astimezone()
    day = local.day
    if local.year == reference.year:
        return f"{local:%b} {day}"
    return f"{local:%b} {day}, {local.year}"


def relative(stamp: str | None, now: datetime | None = None) -> str:
    """How long ago something happened, as a ledger row shows it.

    just now, 12m ago, 2h ago, 2d ago, 1w ago, 6 weeks, then the date.
    """
    elapsed = seconds_since(stamp, now)
    if elapsed is None:
        return ""
    if elapsed < 0:
        elapsed = 0.0

    if elapsed < MINUTE:
        return "just now"
    if elapsed < HOUR:
        return f"{int(elapsed // MINUTE)}m ago"
    if elapsed < DAY:
        return f"{int(elapsed // HOUR)}h ago"
    if elapsed < WEEK:
        return f"{int(elapsed // DAY)}d ago"
    if elapsed < 2 * WEEK:
        return "1w ago"
    if elapsed < DATE_CUTOFF:
        return f"{int(elapsed // WEEK)} weeks"
    return on_date(stamp, now)


def duration(stamp: str | None, now: datetime | None = None) -> str:
    """How long something has been in the ground: "6 weeks", "3 months"."""
    elapsed = seconds_since(stamp, now)
    if elapsed is None:
        return ""
    if elapsed < 0:
        elapsed = 0.0

    if elapsed < MINUTE:
        return "moments"
    if elapsed < HOUR:
        minutes = int(elapsed // MINUTE)
        return f"{minutes} minute" + ("" if minutes == 1 else "s")
    if elapsed < DAY:
        hours = int(elapsed // HOUR)
        return f"{hours} hour" + ("" if hours == 1 else "s")
    if elapsed < WEEK:
        days = int(elapsed // DAY)
        return f"{days} day" + ("" if days == 1 else "s")
    if elapsed < 9 * WEEK:
        weeks = int(elapsed // WEEK)
        return f"{weeks} week" + ("" if weeks == 1 else "s")
    months = int(elapsed // (30 * DAY))
    if months < 18:
        return f"{months} month" + ("" if months == 1 else "s")
    years = int(elapsed // (365 * DAY))
    return f"{years} year" + ("" if years == 1 else "s")


def buried(stamp: str | None, now: datetime | None = None) -> str:
    """The Unearthed tag: "buried 6 weeks"."""
    how_long = duration(stamp, now)
    return f"buried {how_long}" if how_long else ""


def today_eyebrow(now: datetime | None = None) -> str:
    """The date line at the top of Home: "Tuesday, July 21"."""
    moment = (now or _now()).astimezone()
    return f"{moment:%A}, {moment:%B} {moment.day}"
