"""Which passage a date gets.

Weekdays follow the 'story' track and weekends the 'wisdom' track. Each track resumes where its
most recent edition stopped, so the reading moves through whole books in order. A handful of
special days (Easter, Christmas, ...) get a fixed passage and leave both tracks where they were.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import bible
import church_calendar

ROOT = Path(__file__).resolve().parent.parent
PLAN = json.loads((ROOT / "generator" / "plan.json").read_text(encoding="utf-8"))
EDITIONS = ROOT / "docs" / "editions"

SHORT_ENOUGH = 22   # at or under this many verses left in a chapter: read them all
WINDOW = 45         # most verses offered to Claude to choose a stopping point from
MIN_VERSES = 8      # fewest verses Claude may choose (unless the chapter has fewer left)


@dataclass
class Day:
    date: date
    kind: str                       # "track", "special", or "legacy"
    track: str | None               # "story" / "wisdom" for track days
    track_name: str
    label: str                      # series label shown on the card, e.g. "The Gospel of Mark"
    series_day: int
    start: bible.Ref                # first verse (track days) or the whole fixed passage
    window: list = field(default_factory=list)   # verses Claude may choose from (track days)
    fixed: bool = True              # True if the passage is already decided
    segment: int = -1

    def passage(self, end_verse: int | None = None) -> bible.Ref:
        if self.kind != "track":
            return self.start
        lo, hi = self.window[0][0], self.window[-1][0]
        if self.fixed or end_verse is None:
            end = hi
        else:
            end = max(min(end_verse, hi), min(lo + MIN_VERSES - 1, hi))
            last_in_chapter = bible.chapter(self.start.b, self.start.c)[-1][0]
            # never leave a stub of a few verses for tomorrow
            if 0 < last_in_chapter - end < 6 and last_in_chapter - lo + 1 <= 30:
                end = last_in_chapter
        return bible.Ref(self.start.b, self.start.c, lo, end)


def _special_dates(y: int) -> dict[date, dict]:
    ev = {name: d for d, name in church_calendar.events(y)}
    adv = church_calendar.advent_start(y)
    for i in range(4):
        ev[f"Advent {i + 1}"] = adv + timedelta(weeks=i)
    out = {}
    for s in PLAN["special"]:
        if s["event"] in ev:
            out[ev[s["event"]]] = s
    return out


def _editions_before(d: date) -> list[dict]:
    eds = []
    for p in sorted(EDITIONS.glob("*.json")):
        if p.stem < d.isoformat():
            try:
                eds.append(json.loads(p.read_text(encoding="utf-8")))
            except ValueError:
                pass
    return eds


def _segments(track: str) -> list[dict]:
    return PLAN["tracks"][track]["segments"]


def _next_position(track: str, last: dict | None) -> tuple[int, int, int, int]:
    """(segment index, book index, chapter, verse) where the track picks up."""
    segs = _segments(track)
    if not last or "pos" not in last:
        s = segs[0]
        return 0, bible.NAMES.index(s["book"]), s["from"], 1
    seg, b, c, v_end = last["segment"], last["pos"]["b"], last["pos"]["c"], last["pos"]["v_end"]
    if v_end < bible.chapter(b, c)[-1][0]:
        return seg, b, c, v_end + 1
    s = segs[seg]
    if c + 1 <= s["to"]:
        return seg, b, c + 1, 1
    seg = (seg + 1) % len(segs)
    s = segs[seg]
    return seg, bible.NAMES.index(s["book"]), s["from"], 1


def plan_day(d: date, extra: list[dict] | None = None) -> Day:
    """Plan a date. `extra` lets the caller include an edition not yet on disk (for previewing tomorrow)."""
    for e in PLAN["legacy"]:
        if e["date"] == d.isoformat():
            n = sum(1 for x in PLAN["legacy"] if x["series"] == e["series"] and x["date"] <= e["date"])
            return Day(d, "legacy", None, e["series"], e["series"], n, bible.parse_ref(e["ref"]))

    special = _special_dates(d.year).get(d)
    if special:
        return Day(d, "special", None, special["label"], special["label"], 0, bible.parse_ref(special["ref"]))

    track = PLAN["weekend_track"] if d.weekday() >= 5 else PLAN["weekday_track"]
    history = [e for e in _editions_before(d) + (extra or []) if e.get("track") == track]
    last = history[-1] if history else None
    seg, b, c, v = _next_position(track, last)
    label = _segments(track)[seg]["label"]
    n = 1
    for e in reversed(history):
        if e.get("segment") == seg:
            n += 1
        else:
            break
    remaining = [x for x in bible.chapter(b, c) if x[0] >= v]
    fixed = len(remaining) <= SHORT_ENOUGH
    window = remaining if fixed else remaining[:WINDOW]
    return Day(d, "track", track, PLAN["tracks"][track]["name"], label, n,
               bible.Ref(b, c, v, window[-1][0]), window, fixed, seg)


def preview(d: date, extra: list[dict]) -> dict:
    """What tomorrow will be, for the 'Tomorrow' line."""
    day = plan_day(d, extra)
    if day.kind == "track":
        r = bible.Ref(day.start.b, day.start.c, day.start.v1, day.start.v1)
        return {"ref": r.canonical(), "display": f"{day.label} continues at {r.display()}"}
    return {"ref": day.start.canonical(), "display": f"{day.label}: {day.start.display()}"}
