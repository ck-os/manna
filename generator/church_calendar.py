"""Seasons and dates Manna ties each reading to: the church year, US holidays, and the natural seasons."""
from __future__ import annotations

from datetime import date, timedelta


def easter(y: int) -> date:
    """Western (Gregorian) Easter, anonymous Gregorian algorithm."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def advent_start(y: int) -> date:
    """First Sunday of Advent: the fourth Sunday before Christmas."""
    xmas = date(y, 12, 25)
    # Sunday on or before Dec 24, minus three weeks
    last_sunday = xmas - timedelta(days=(xmas.weekday() + 1) % 7 or 7)
    return last_sunday - timedelta(weeks=3)


def _nth_weekday(y: int, month: int, weekday: int, n: int) -> date:
    d = date(y, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(y: int, month: int, weekday: int) -> date:
    d = date(y, month + 1, 1) - timedelta(days=1) if month < 12 else date(y, 12, 31)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def events(y: int) -> list[tuple[date, str]]:
    e = easter(y)
    return [
        (date(y, 1, 1), "New Year's Day"),
        (date(y, 1, 6), "Epiphany"),
        (e - timedelta(days=46), "Ash Wednesday"),
        (_nth_weekday(y, 2, 0, 3), "Presidents' Day"),
        (e - timedelta(days=7), "Palm Sunday"),
        (e - timedelta(days=2), "Good Friday"),
        (e, "Easter"),
        (_nth_weekday(y, 5, 6, 2), "Mother's Day"),
        (_last_weekday(y, 5, 0), "Memorial Day"),
        (e + timedelta(days=49), "Pentecost"),
        (_nth_weekday(y, 6, 6, 3), "Father's Day"),
        (date(y, 7, 4), "Independence Day"),
        (_nth_weekday(y, 9, 0, 1), "Labor Day"),
        (date(y, 11, 11), "Veterans Day"),
        (_nth_weekday(y, 11, 3, 4), "Thanksgiving"),
        (advent_start(y), "Advent begins"),
        (date(y, 12, 24), "Christmas Eve"),
        (date(y, 12, 25), "Christmas"),
        (date(y, 12, 31), "New Year's Eve"),
    ]


def church_season(d: date) -> str:
    y = d.year
    e = easter(y)
    ash = e - timedelta(days=46)
    pent = e + timedelta(days=49)
    adv = advent_start(y)
    if d >= adv and d < date(y, 12, 25):
        return "Advent"
    if d >= date(y, 12, 25) or d <= date(y, 1, 5):
        return "Christmastide"
    if date(y, 1, 6) <= d < ash:
        return "Epiphany season"
    if ash <= d < e - timedelta(days=7):
        return "Lent"
    if e - timedelta(days=7) <= d < e:
        return "Holy Week"
    if e <= d <= pent:
        return "Eastertide"
    return "Ordinary Time"


def natural_season(d: date) -> str:
    md = (d.month, d.day)
    if md >= (12, 21) or md < (3, 20):
        return "winter"
    if md < (6, 21):
        return "spring"
    if md < (9, 22):
        return "summer"
    return "autumn"


def _when(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def chips(d: date, horizon: int = 45, limit: int = 3) -> list[dict]:
    """Upcoming (or today's) dates worth naming, soonest first."""
    upcoming = []
    for y in (d.year, d.year + 1):
        for when, name in events(y):
            delta = (when - d).days
            if 0 <= delta <= horizon:
                upcoming.append((delta, name))
    upcoming.sort()
    seen, out = set(), []
    for delta, name in upcoming:
        if name in seen:
            continue
        seen.add(name)
        out.append({"label": name, "when": _when(delta), "days": delta})
        if len(out) == limit:
            break
    return out


def context(d: date) -> dict:
    return {
        "date": d.isoformat(),
        "weekday": d.strftime("%A"),
        "long_date": f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}, {d.year}",
        "church_season": church_season(d),
        "natural_season": natural_season(d),
        "upcoming": chips(d, horizon=60, limit=6),
        "chips": chips(d),
    }
