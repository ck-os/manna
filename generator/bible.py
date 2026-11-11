"""Berean Standard Bible access and reference parsing (mirrors the app's JS parser)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BIBLE_DIR = Path(__file__).resolve().parent.parent / "docs" / "bible"

BOOKS: list[tuple[str, int]] = [tuple(x) for x in json.loads((BIBLE_DIR / "index.json").read_text(encoding="utf-8"))]
NAMES = [b[0] for b in BOOKS]

ALIAS = {
    "gen": 0, "ge": 0, "gn": 0, "ex": 1, "exo": 1, "exod": 1, "lev": 2, "lv": 2, "num": 3, "nm": 3,
    "deut": 4, "dt": 4, "josh": 5, "jos": 5, "judg": 6, "jdg": 6, "ru": 7, "1sam": 8, "1sa": 8,
    "2sam": 9, "2sa": 9, "1kgs": 10, "1ki": 10, "2kgs": 11, "2ki": 11, "1chr": 12, "1ch": 12,
    "2chr": 13, "2ch": 13, "neh": 15, "est": 16, "esth": 16, "ps": 18, "psa": 18, "pss": 18,
    "psalms": 18, "prov": 19, "pr": 19, "prv": 19, "eccl": 20, "ecc": 20, "qoh": 20, "song": 21,
    "sos": 21, "songofsongs": 21, "canticles": 21, "isa": 22, "jer": 23, "lam": 24, "ezek": 25,
    "eze": 25, "dan": 26, "hos": 27, "obad": 30, "ob": 30, "mic": 32, "nah": 33, "hab": 34,
    "zeph": 35, "hag": 36, "zech": 37, "mal": 38, "matt": 39, "mt": 39, "mk": 40, "mrk": 40,
    "lk": 41, "luk": 41, "jn": 42, "jhn": 42, "rom": 44, "ro": 44, "1cor": 45, "2cor": 46,
    "gal": 47, "eph": 48, "phil": 49, "php": 49, "col": 50, "1thess": 51, "1th": 51, "2thess": 52,
    "2th": 52, "1tim": 53, "1ti": 53, "2tim": 54, "2ti": 54, "tit": 55, "phlm": 56, "philem": 56,
    "phm": 56, "heb": 57, "jas": 58, "jm": 58, "1pet": 59, "1pe": 59, "2pet": 60, "2pe": 60,
    "1jn": 61, "1jo": 61, "2jn": 62, "3jn": 63, "jude": 64, "rev": 65, "re": 65, "revelations": 65,
}


def _norm(s: str) -> str:
    s = s.lower().replace(".", "").strip()
    s = re.sub(r"^(first|1st|i)\s+", "1", s)
    s = re.sub(r"^(second|2nd|ii)\s+", "2", s)
    s = re.sub(r"^(third|3rd|iii)\s+", "3", s)
    return re.sub(r"\s+", "", s)


_NAMEKEYS = [_norm(n) for n in NAMES]


def find_book(raw: str) -> int:
    k = _norm(raw)
    if not k:
        return -1
    if k in ALIAS:
        return ALIAS[k]
    if k in _NAMEKEYS:
        return _NAMEKEYS.index(k)
    if len(k) < 3:
        return -1
    for i, nk in enumerate(_NAMEKEYS):
        if nk.startswith(k):
            return i
    return -1


@dataclass(frozen=True)
class Ref:
    b: int
    c: int
    v1: int = 0
    v2: int = 0

    @property
    def book(self) -> str:
        return NAMES[self.b]

    def canonical(self) -> str:
        """Machine form used in data-ref attributes: 'Psalm 103:1-14'."""
        s = self.book if BOOKS[self.b][1] == 1 else f"{self.book} {self.c}"
        if self.v1:
            sep = " " if BOOKS[self.b][1] == 1 else ":"
            s += f"{sep}{self.v1}" + (f"-{self.v2}" if self.v2 and self.v2 != self.v1 else "")
        return s

    def display(self) -> str:
        return self.canonical().replace("-", "–")


_REF_RX = re.compile(
    r"^((?:[1-3]|i{1,3}|first|second|third|1st|2nd|3rd)?\s*[a-z][a-z .]*?)\s*(\d+)?\s*"
    r"(?:[:.]\s*(\d+)\s*(?:[-–—]\s*(\d+))?)?\s*$",
    re.I,
)


def parse_ref(q: str) -> Ref | None:
    m = _REF_RX.match(q.strip())
    if not m:
        return None
    b = find_book(m.group(1))
    if b < 0:
        return None
    ch = int(m.group(2)) if m.group(2) else 1
    v1 = int(m.group(3)) if m.group(3) else 0
    v2 = int(m.group(4)) if m.group(4) else 0
    if BOOKS[b][1] == 1 and m.group(2) and not m.group(3):
        v1, ch = ch, 1
    if ch < 1 or ch > BOOKS[b][1]:
        return None
    if v1:
        nverses = max(v[0] for v in chapter(b, ch))
        if v1 > nverses:
            return None
        v2 = min(v2 or v1, nverses)
        if v2 < v1:
            return None
    return Ref(b, ch, v1, v2 or v1)


@lru_cache(maxsize=None)
def _book(b: int) -> dict:
    return json.loads((BIBLE_DIR / f"{b + 1:02d}.json").read_text(encoding="utf-8"))


def chapter(b: int, c: int) -> list[list]:
    return _book(b)["c"][c - 1]


def verses(ref: Ref) -> list[list]:
    vs = chapter(ref.b, ref.c)
    if not ref.v1:
        return vs
    return [v for v in vs if ref.v1 <= v[0] <= ref.v2]


def text_of(ref: Ref) -> str:
    return " ".join(v[1] for v in verses(ref))
