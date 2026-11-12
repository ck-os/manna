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
import planner  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EDITIONS = DOCS / "editions"
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
    others: Step = Field(description="Out in the world: family, friends, coworkers, neighbors, or someone in need")


class WordStudy(BaseModel):
    term: str = Field(description="Original-language word in transliteration (e.g. 'hesed'), or empty string if none fits today")
    english: str = Field(description="How the BSB translates it in today's passage, exactly as it appears")
    gloss: str = Field(description="1-2 plain sentences on what the word means")


class More(BaseModel):
    ref: str = Field(description="Scripture reference, full book name, e.g. 'Luke 17:11-19'")
    line: str = Field(description="Under 10 words: why read it")


LIFE_AREAS = [
    "walking with God", "marriage", "parenting", "home life", "work", "friendship",
    "neighbors and community", "money and generosity", "rest and pace", "conflict and forgiveness",
    "worry and trust", "words and speech", "hard seasons and suffering", "church", "sharing faith",
]


class Content(BaseModel):
    end_verse: int = Field(description="Last verse of today's reading. Pick a natural stopping point inside the verses offered; if the passage is already fixed, return its last verse.")
    life_area: str = Field(description="The one area of everyday life today's application focuses on, chosen from the list in the instructions")
    title: str = Field(description="2-4 word title for the day, drawn from the passage")
    season_line: str = Field(description="One sentence setting the scene for this morning: usually where we are in the book's story; mention the season or calendar only if it genuinely fits")
    big_idea: str = Field(description="The one truth the passage is driving at, as it lands on our lives today. One sentence, max ~20 words. Not a summary of the verses.")
    frame: str = Field(description="One paragraph, 3-5 sentences, framing the day at a higher level: what this truth means for an ordinary day like today, how it lands in the life area you chose, how it connects to the bigger story of Scripture (and to Jesus where it truly does), and the posture to carry into the day. Do not retell or paraphrase the passage.")
    carry_ref: str = Field(description="The single verse (or two) to carry today; must be inside today's passage, e.g. 'Psalm 103:17'")
    glance: list[Glance] = Field(description="2-4 movements covering the whole passage in order")
    understand: list[str] = Field(description="2-4 short paragraphs of plain-language background and meaning; may use {{Book C:V}} references")
    word: WordStudy
    glow: list[str] = Field(description="0-3 short phrases copied exactly from today's passage text to softly highlight")
    steps: Steps
    tonight: str = Field(description="One question for the couple to talk over tonight")
    more: list[More] = Field(description="2-3 related passages for 'if you have five more minutes'")


# ---------------------------------------------------------------- Claude

def _numbered(verses: list) -> str:
    return "\n".join(f"{v[0]} {v[1]}" for v in verses)


def write_with_claude(ctx: dict, day: planner.Day, recent: list[dict]) -> Content:
    import anthropic  # imported here so the template path works without the SDK installed

    book_ch = f"{day.start.book} {day.start.c}"
    if day.kind == "track" and not day.fixed:
        lo, hi = day.window[0][0], day.window[-1][0]
        passage_block = (
            f"Today's reading starts at {book_ch}:{lo}. Choose where it ends: pick end_verse between {lo + planner.MIN_VERSES - 1} and {hi} "
            f"at a natural break (the end of a scene, story, teaching, or thought), usually 10 to 20 verses, enough for about five minutes. "
            f"Write about exactly the verses you choose.\n\nVerses available ({book_ch}, Berean Standard Bible):\n{_numbered(day.window)}"
        )
    else:
        vs = bible.verses(day.passage())
        passage_block = (
            f"Today's passage is {day.passage().display()} (Berean Standard Bible); set end_verse to {vs[-1][0]}.\n\n{_numbered(vs)}"
        )

    if day.kind == "track":
        where = (f"Reading track: {day.track_name} ({'weekdays' if day.track == 'story' else 'weekends'}), "
                 f"currently in {day.label}, day {day.series_day} of this section.")
    else:
        where = f"Today is a special day in the church year: {day.label}. It interrupts the regular reading for one day."

    track_hist = [e for e in recent if day.track and e.get("track") == day.track][-3:]
    lines = [f"- {e['date']}: {e['ref_display']}, \"{e['title']}\" (life area: {e.get('life_area', 'n/a')}). Big idea: {e.get('big_idea', '')}"
             for e in recent[-4:]]
    recent_block = "\n".join(lines) or "- (this is the first day)"
    story_so_far = ""
    if track_hist:
        story_so_far = ("In this track, the last readings were: "
                        + "; ".join(f"{e['ref_display']} (\"{e['title']}\")" for e in track_hist)
                        + ". Pick up the thread from there.")
    recent_areas = [e.get("life_area") for e in recent[-3:] if e.get("life_area")]
    upcoming = ", ".join(f"{u['label']} ({u['when']})" for u in ctx["upcoming"]) or "nothing notable soon"

    user = f"""Today is {ctx['long_date']}.
{where}
{story_so_far}

Recent days (don't repeat their big ideas, steps, or tonight questions):
{recent_block}

Life areas used in the last three days: {', '.join(recent_areas) or 'none yet'}. Choose a different one today unless the passage clearly calls for one of them.
Life areas to choose from: {', '.join(LIFE_AREAS)}.

Background only, use if it genuinely fits: church season {ctx['church_season']}; natural season {ctx['natural_season']} (eastern United States); coming up: {upcoming}.

{passage_block}

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


def template_content(day: planner.Day, ctx: dict) -> Content:
    """Plain fallback used when the API key is missing or the call fails. Scripture still comes from the BSB."""
    ref = day.passage(day.window[0][0] + 14 if day.kind == "track" and not day.fixed else None)
    vs = bible.verses(ref)
    first, last = vs[0][0], vs[-1][0]
    carry = bible.Ref(ref.b, ref.c, first, first)
    return Content(
        end_verse=last,
        life_area="walking with God",
        title=ref.display(),
        season_line=f"Today's reading: {ref.display()}.",
        big_idea="Slow down with one passage, and let it show you who God is.",
        frame=f"Today's reading is {ref.display()}. Read it slowly, maybe twice, and notice what it shows you about God and about us. Then carry one line of it into the day and come back to it together tonight.",
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


QUOTED = re.compile(r"(?<![\w])([\"“'‘])([^\"“”'‘’]{3,}?)([\"”'’])(?=[\s.,;:!?)]|$)")


def unquote_outside(text: str, passage: str) -> str:
    """Drop quotation marks around any phrase that isn't actually in today's passage.

    Only today's BSB text may appear in quotation marks; anything else must read as a paraphrase."""
    flat = passage.lower().replace("’", "'")

    def fix(m: re.Match) -> str:
        inner = m.group(2)
        return m.group(0) if inner.lower().replace("’", "'").strip(" .,;:!?") in flat else inner
    return QUOTED.sub(fix, text)


def assemble(d: date, ctx: dict, day: planner.Day, c: Content, source: str) -> dict:
    ref = day.passage(c.end_verse)
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
    uq = lambda t: unquote_outside(t, passage_text)  # noqa: E731
    steps = {}
    for key in ("god", "together", "others"):
        s = getattr(c.steps, key)
        steps[key] = {"short": s.short.strip(), "full": clean_refs(s.full.strip()), "why": uq(clean_refs(s.why.strip()))}  # steps may quote things to say; only "why" cites Scripture
    return {
        "date": d.isoformat(),
        "weekday_line": f"{d.strftime('%A')}, {d.strftime('%B')} {d.day}",
        "series": day.label,
        "series_day": day.series_day,
        "kind": day.kind,
        "track": day.track,
        "track_name": day.track_name,
        "segment": day.segment,
        "pos": {"b": ref.b, "c": ref.c, "v_end": vs[-1][0]},
        "life_area": c.life_area.strip().lower(),
        "church_season": ctx["church_season"],
        "natural_season": ctx["natural_season"],
        "chips": ctx["chips"],
        "ref": ref.canonical(),
        "ref_display": ref.display(),
        "verses": vs,
        "title": c.title.strip(),
        "season_line": uq(c.season_line.strip()),
        "big_idea": uq(c.big_idea.strip()),
        "frame": uq(clean_refs(c.frame.strip())),
        "carry": {"ref": carry.canonical(), "display": carry.display(), "text": bible.text_of(carry)},
        "glance": [g.model_dump() for g in c.glance][:4],
        "understand": [uq(clean_refs(p)) for p in c.understand][:4],
        "word": c.word.model_dump() if c.word.term else None,
        "glow": glow,
        "steps": steps,
        "tonight": c.tonight.strip(),
        "more": more[:3],
        "tomorrow": None,
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
    day = planner.plan_day(d)
    recent = planner._editions_before(d)[-6:]

    if args.content:
        content = Content.model_validate_json(Path(args.content).read_text(encoding="utf-8"))
        source = "hand-written"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        try:
            content = write_with_claude(ctx, day, recent)
            source = MODEL
        except Exception as exc:  # keep the morning edition coming even if the API has a bad day
            print(f"Claude call failed, using the plain template: {exc!r}")
            content, source = template_content(day, ctx), "template"
    else:
        print("ANTHROPIC_API_KEY is not set; using the plain template.")
        content, source = template_content(day, ctx), "template"

    edition = assemble(d, ctx, day, content, source)
    edition["tomorrow"] = planner.preview(d + timedelta(days=1), [edition])
    out.write_text(json.dumps(edition, ensure_ascii=False, indent=1), encoding="utf-8")
    render_page(edition)
    print(f"Built {d}: {edition['ref_display']} · {edition['title']} ({source})")


if __name__ == "__main__":
    main()
