"""Build today's Manna edition and the app page.

    python generator/generate.py                 # today's date in New York; skips if already built
    python generator/generate.py --date 2026-11-12 --force
    python generator/generate.py --content edition-content.json   # use hand-written content, no API call

Scripture text always comes from docs/bible (the Berean Standard Bible). Claude writes only the
commentary, summary, and steps; it never supplies verse text.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bible  # noqa: E402
import church_calendar  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EDITIONS = DOCS / "editions"
PLAN = json.loads((ROOT / "generator" / "plan.json").read_text(encoding="utf-8"))
SYSTEM_PROMPT = (ROOT / "generator" / "prompt.md").read_text(encoding="utf-8")
TEMPLATE = ROOT / "template" / "app.html"
MODEL = "claude-opus-5-5"
TZ = ZoneInfo("America/New_York")


# ---------------------------------------------------------------- content schema (what Claude writes)

class Glance(BaseModel):
    verses: str = Field(description="Verse range inside today's passage, e.g. '15-18'")
    head: str = Field(description="2-5 word heading for this movement of the passage")
    line: str = Field(description="One plain sentence: what these verses say")


class Step(BaseModel):
    short: str = Field(description="One line for the Summary tab, max ~14 words")
    full: str = Field(description="The step written out, 1-2 sentences")
    why: str = Field(description="Optional: one short line tying it to Scripture with a {{Book C:V}} reference, or empty string")


class Steps(BaseModel):
    god: Step
    together: Step = Field(description="With each other (the couple). Must be tiny: one small act or sentence, under 2 minutes, never a project or list")
    others: Step = Field(description="Family and friends")


class WordStudy(BaseModel):
    term: str = Field(description="Original-language word in transliteration (e.g. 'hesed'), or empty string if none fits today")
    english: str = Field(description="How the BSB translates it in today's passage, exactly as it appears")
    gloss: str = Field(description="1-2 plain sentences on what the word means")


class More(BaseModel):
    ref: str = Field(description="Scripture reference, full book name, e.g. 'Luke 17:11-19'")
    line: str = Field(description="Under 10 words: why read it")


class Content(BaseModel):
    title: str = Field(description="2-4 word title for the day, drawn from the passage")
    season_line: str = Field(description="One sentence setting the season/calendar atmosphere for this morning")
    in_a_minute: list[str] = Field(description="Exactly 2 short paragraphs (2-3 sentences each): what the passage says and why it fits today")
    carry_ref: str = Field(description="The single verse (or two) to carry today; must be inside today's passage, e.g. 'Psalm 103:17'")
    glance: list[Glance] = Field(description="2-4 movements covering the whole passage in order")
    understand: list[str] = Field(description="2-4 short paragraphs of plain-language background and meaning; may use {{Book C:V}} references")
    word: WordStudy
    glow: list[str] = Field(description="0-3 short phrases copied exactly from today's passage text to softly highlight")
    steps: Steps
    tonight: str = Field(description="One question for the couple to talk over tonight")
    more: list[More] = Field(description="2-3 related passages for 'if you have five more minutes'")


# ---------------------------------------------------------------- plan

def plan_for(d: date) -> tuple[bible.Ref, str, int]:
    """Return (passage, series name, day number within the series) for a date."""
    dated = PLAN["dated"]
    by_date = {e["date"]: e for e in dated}
    if d.isoformat() in by_date:
        e = by_date[d.isoformat()]
        series = e["series"]
        n = sum(1 for x in dated if x["series"] == series and x["date"] <= e["date"])
        ref = bible.parse_ref(e["ref"])
        if not ref:
            raise SystemExit(f"Bad plan reference: {e['ref']}")
        return ref, series, n
    last = date.fromisoformat(max(by_date))
    if d < date.fromisoformat(min(by_date)):
        raise SystemExit(f"No reading planned for {d}")
    seq = []
    for blk in PLAN["after"]:
        for c in range(blk["from"], blk["to"] + 1):
            seq.append((blk["book"], c, blk["series"]))
    i = ((d - last).days - 1) % len(seq)
    book, c, series = seq[i]
    n = 1
    j = i
    while j > 0 and seq[j - 1][2] == series and seq[j - 1][0] == book:
        n += 1
        j -= 1
    return bible.Ref(bible.NAMES.index(book), c), series, n


# ---------------------------------------------------------------- Claude

def write_with_claude(ctx: dict, ref: bible.Ref, series: str, tomorrow: bible.Ref, prior: dict | None) -> Content:
    import anthropic  # imported here so the template path works without the SDK installed

    passage = "\n".join(f"{v[0]} {v[1]}" for v in bible.verses(ref))
    upcoming = ", ".join(f"{u['label']} ({u['when']})" for u in ctx["upcoming"]) or "nothing major in the next two months"
    user = f"""Today is {ctx['long_date']}.
Church season: {ctx['church_season']}. Natural season: {ctx['natural_season']} (we live in the eastern United States).
Coming up: {upcoming}.
Reading series: {series}.

Today's passage is {ref.display()} (Berean Standard Bible):
{passage}

Tomorrow's passage: {tomorrow.display()}.
{('Yesterday was ' + prior['ref_display'] + ', titled "' + prior['title'] + '". Do not repeat its steps or tonight question.') if prior else ''}

Write today's Manna edition."""

    client = anthropic.Anthropic()
    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "high"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        output_format=Content,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"No usable output (stop_reason={response.stop_reason})")
    print(f"Claude: {response.usage.input_tokens} in / {response.usage.output_tokens} out, request {response._request_id}")
    return response.parsed_output


def template_content(ref: bible.Ref, ctx: dict) -> Content:
    """Plain fallback used when the API key is missing or the call fails. Scripture still comes from the BSB."""
    vs = bible.verses(ref)
    first, last = vs[0][0], vs[-1][0]
    carry = bible.Ref(ref.b, ref.c, first, first)
    return Content(
        title=ref.display(),
        season_line=f"A {ctx['natural_season']} morning in {ctx['church_season']}.",
        in_a_minute=[
            f"Today's reading is {ref.display()}. Read it slowly, maybe twice, and notice what it shows you about who God is.",
            "Then take one thing with you into the day and come back to it tonight together.",
        ],
        carry_ref=carry.canonical(),
        glance=[Glance(verses=f"{first}-{last}", head="Today's passage", line="Read it through once, then again more slowly.")],
        understand=["Ask three questions as you read: What does this show about God? What does it show about us? What is one thing to do about it today?"],
        word=WordStudy(term="", english="", gloss=""),
        glow=[],
        steps=Steps(
            god=Step(short="Pray one sentence of today's passage back to God.", full="Pick one sentence from today's passage and pray it back to God in your own words.", why=""),
            together=Step(short="Share one line that stood out to you.", full="Tell each other one line from today's reading that stood out.", why=""),
            others=Step(short="Send someone a short encouragement.", full="Text one person a short word of encouragement today.", why=""),
        ),
        tonight="What did today's passage show us about God?",
        more=[],
    )


# ---------------------------------------------------------------- validation & assembly

REF_TOKEN = re.compile(r"\{\{([^}|]+)(?:\|([^}]*))?\}\}")


def clean_refs(text: str) -> str:
    """Keep {{ref}} tokens that parse; turn the rest into plain text."""
    def fix(m: re.Match) -> str:
        r = bible.parse_ref(m.group(1))
        label = (m.group(2) or m.group(1)).strip()
        return "{{" + r.canonical() + "|" + label.replace("-", "–") + "}}" if r else label
    return REF_TOKEN.sub(fix, text)


def assemble(d: date, ctx: dict, ref: bible.Ref, series: str, n: int, tomorrow: bible.Ref, c: Content, source: str) -> dict:
    vs = bible.verses(ref)
    lo, hi = vs[0][0], vs[-1][0]
    carry = bible.parse_ref(c.carry_ref)
    if not carry or carry.b != ref.b or carry.c != ref.c or carry.v1 < lo or carry.v2 > hi:
        carry = bible.Ref(ref.b, ref.c, lo, lo)
    passage_text = " ".join(v[1] for v in vs)
    glow = [g for g in c.glow if g and g in passage_text][:3]
    if c.word.english and c.word.english in passage_text and c.word.english not in glow:
        glow.append(c.word.english)
    more = []
    for m in c.more:
        r = bible.parse_ref(m.ref)
        if r:
            more.append({"ref": r.canonical(), "display": r.display(), "line": m.line})
    steps = {}
    for key in ("god", "together", "others"):
        s = getattr(c.steps, key)
        steps[key] = {"short": s.short.strip(), "full": clean_refs(s.full.strip()), "why": clean_refs(s.why.strip())}
    return {
        "date": d.isoformat(),
        "weekday_line": f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}",
        "series": series,
        "series_day": n,
        "church_season": ctx["church_season"],
        "natural_season": ctx["natural_season"],
        "chips": ctx["chips"],
        "ref": ref.canonical(),
        "ref_display": ref.display(),
        "verses": vs,
        "title": c.title.strip(),
        "season_line": c.season_line.strip(),
        "in_a_minute": [clean_refs(p) for p in c.in_a_minute][:3],
        "carry": {"ref": carry.canonical(), "display": carry.display(), "text": bible.text_of(carry)},
        "glance": [g.model_dump() for g in c.glance][:4],
        "understand": [clean_refs(p) for p in c.understand][:4],
        "word": c.word.model_dump() if c.word.term else None,
        "glow": glow,
        "steps": steps,
        "tonight": c.tonight.strip(),
        "more": more[:3],
        "tomorrow": {"ref": tomorrow.canonical(), "display": tomorrow.display()},
        "generated_by": source,
        "built_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }


def render_page(edition: dict) -> None:
    page = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(edition, ensure_ascii=False).replace("</", "<\\/")
    page = page.replace("/*EDITION_JSON*/{}", payload)
    page = page.replace("{{TITLE}}", html.escape(f"Manna · {edition['title']}"))
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / "latest.json").write_text(json.dumps({"date": edition["date"], "title": edition["title"]}), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (default: today in New York)")
    ap.add_argument("--force", action="store_true", help="rebuild even if this date already has an edition")
    ap.add_argument("--content", help="path to a JSON file matching the Content schema; skips the API")
    ap.add_argument("--render-only", action="store_true", help="re-render docs/index.html from the newest edition")
    args = ap.parse_args()

    EDITIONS.mkdir(parents=True, exist_ok=True)
    if args.render_only:
        newest = sorted(EDITIONS.glob("*.json"))[-1]
        render_page(json.loads(newest.read_text(encoding="utf-8")))
        print(f"Rendered {newest.name}")
        return

    d = date.fromisoformat(args.date) if args.date else datetime.now(TZ).date()
    out = EDITIONS / f"{d.isoformat()}.json"
    if out.exists() and not args.force:
        print(f"{d} already built; nothing to do.")
        return

    ctx = church_calendar.context(d)
    ref, series, n = plan_for(d)
    tomorrow, _, _ = plan_for(d + timedelta(days=1))
    prior_path = EDITIONS / f"{(d - timedelta(days=1)).isoformat()}.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8")) if prior_path.exists() else None

    if args.content:
        content = Content.model_validate_json(Path(args.content).read_text(encoding="utf-8"))
        source = "hand-written"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        try:
            content = write_with_claude(ctx, ref, series, tomorrow, prior)
            source = MODEL
        except Exception as exc:  # keep the morning edition coming even if the API has a bad day
            print(f"Claude call failed, using the plain template: {exc!r}")
            content, source = template_content(ref, ctx), "template"
    else:
        print("ANTHROPIC_API_KEY is not set; using the plain template.")
        content, source = template_content(ref, ctx), "template"

    edition = assemble(d, ctx, ref, series, n, tomorrow, content, source)
    out.write_text(json.dumps(edition, ensure_ascii=False, indent=1), encoding="utf-8")
    render_page(edition)
    print(f"Built {d}: {edition['ref_display']} · {edition['title']} ({source})")


if __name__ == "__main__":
    main()
