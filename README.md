# Manna

A short daily Bible reading for the morning, made to be added to an iPhone home screen.

Each morning a GitHub Action picks the day's passage from `generator/plan.json`, pulls the verses from the Berean Standard Bible (public domain, `docs/bible/`), and asks Claude to write the summary, background, and three small steps (with God, with each other, with family and friends). The result is published to GitHub Pages from `docs/`.

- Scripture text always comes from the BSB files, never from the model.
- The edition ties the passage to the church season, upcoming holidays, and the natural season. No news.
- If the API key is missing or the call fails, a plain edition (the passage plus simple prompts) still goes out.

## Running it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python generator/generate.py                         # today (New York time); skips if already built
python generator/generate.py --date 2026-11-12 --force
python generator/generate.py --content my.json        # hand-written content, no API call
```

The workflow in `.github/workflows/daily.yml` runs at 4–6 AM Eastern and can be run by hand from the Actions tab. It needs one repository secret, `ANTHROPIC_API_KEY`.

## Files

- `generator/plan.json` reading plan: dated readings (Thanksgiving, Advent, Christmas), then books chapter by chapter
- `generator/prompt.md` instructions Claude writes from
- `generator/church_calendar.py` church seasons, Easter, US holidays
- `template/app.html` the app page; `docs/app.css`, `docs/app.js` its style and logic
- `docs/editions/` every day's edition as JSON

Scripture quotations are from the Berean Standard Bible (BSB), dedicated to the public domain.
