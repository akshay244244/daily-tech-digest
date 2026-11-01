"""Weekly recap: top 5 per section from the last 7 days, each with a 'why it matters'."""
from . import ai, config
from .store import recent_stories
from .util import data_path, last_n_dates, log, read_json, today_ist, write_json


def _fallback_why(s):
    det = read_json(data_path("stories", f"{s['id']}.json")) or {}
    sents = det.get("detailed") or det.get("sentences") or []
    if sents:
        w = sents[0].split()
        return " ".join(w[:25]) + ("…" if len(w) > 25 else "")
    sec = config.SECTION_BY_SLUG[s["category"]]["name"]
    return f"Ranked #{s['rank']} in {sec} on {s['date']}"


def build_recap():
    dates = last_n_dates(7)
    week_end, week_start = dates[0], dates[-1]
    stories = recent_stories(7)
    if not stories:
        log("No stories in the last 7 days, skipping recap")
        return None
    by_id = {s["id"]: s for s in stories}
    picks = None

    if ai.available():
        lines = "\n".join(f'{s["id"]} | {s["category"]} | {s["date"]} | {s["source"]} | {s["summary"]}' for s in stories)
        prompt = f"""You are the editor of "Daily Tech Digest" for a tech product manager in India. Build the weekly recap.
From the stories below (last 7 days), pick the 5 most significant per section (sections: {", ".join(s["slug"] for s in config.SECTIONS)}), most important first. Keep each story in its current section. Avoid picking two stories about the same event.
For each, write "why": one line (max 22 words) on why it matters for a tech PM. Factual, no hype.

STORIES (id | section | date | source | headline):
{lines}

Return JSON only: {{"sections": {{"frontier-ai": [{{"id": "...", "why": "..."}}], "global-tech": [], "india-startups": [], "product-craft": [], "creative-tools": []}}}}"""
        res = ai.ask_json(prompt, max_tokens=6000)
        if isinstance(res, dict) and isinstance(res.get("sections"), dict):
            picks = res["sections"]

    items, generated_by = [], "ai" if picks else "fallback"
    for sec in config.SECTIONS:
        chosen = []
        if picks:
            for it in picks.get(sec["slug"], []) or []:
                s = by_id.get(str(it.get("id")))
                if s and s["category"] == sec["slug"] and s["id"] not in {c[0]["id"] for c in chosen}:
                    chosen.append((s, (it.get("why") or "").strip().rstrip(".")))
        pool = sorted((s for s in stories if s["category"] == sec["slug"]),
                      key=lambda s: (s["rank"], -int(s["date"].replace("-", ""))))
        for s in pool:  # fill any gaps without AI
            if len(chosen) >= 5:
                break
            if s["id"] not in {c[0]["id"] for c in chosen}:
                chosen.append((s, ""))
        for rank, (s, why) in enumerate(chosen[:5], 1):
            items.append({
                "id": s["id"], "category": sec["slug"], "rank": rank, "summary": s["summary"],
                "why": why or _fallback_why(s), "source": s["source"], "url": s["url"],
                "date": s["date"], "image": s.get("image"),
            })

    recap = {"week_start": week_start, "week_end": week_end, "items": items,
             "generated_by": generated_by, "created": today_ist(), "email_sent": False}
    write_json(data_path("recaps", f"{week_start}_{week_end}.json"), recap)
    write_json(data_path("recap.json"), recap)
    log(f"Recap built: {len(items)} items ({generated_by})")
    return recap
