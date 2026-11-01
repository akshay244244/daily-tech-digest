"""AI editor (Gemini) that picks and rewrites stories, with a non-AI fallback."""
import re

from . import ai, config
from .fetch import is_competitor_story
from .util import log

PER_SECTION_CANDIDATES = 60


def _prompt(cands):
    secs = "\n".join(f'- "{s["slug"]}" ({s["name"]}): {s["brief"]}' for s in config.SECTIONS)
    lines = "\n".join(
        f'{c["id"]} | {c["category"]} | {c["source"]} | {c["title"]} | {c["snippet"][:160]}'
        for c in cands
    )
    return f"""You are the editor of "Daily Tech Digest", a daily news digest for one reader: a tech product manager in India.

SECTIONS:
{secs}

TASK
- Pick up to {config.MAX_PER_SECTION} stories per section, most important first. A story may move to a better-fitting section.
- Prefer launches, funding, research and moves that change what people build or buy.
- Skip gossip, opinion, deals and discounts, listicles, minor reviews and forum chatter.
- Merge duplicates (same event from several outlets): keep the most authoritative original source. Never repeat a story across sections.
- Creative Tools must NEVER include a story whose subject is Canva, Affinity, Capture One, Figma, Corel/CorelDRAW, PaintShop, Pixelmator or Luminar/Skylum. A story mainly about Adobe that mentions a rival is fine. AI image generators are allowed.
- For each story write "summary": a one-line headline, max 15 words, factual and specific (names, numbers), no clickbait, no trailing period, no source name.
- Choose the {config.TOP_N} most significant stories overall as "top" (list of ids, most significant first).

CANDIDATES (id | suggested section | source | title | snippet):
{lines}

Return JSON only, exactly this shape:
{{"sections": {{"frontier-ai": [{{"id": "...", "summary": "..."}}], "global-tech": [], "india-startups": [], "product-craft": [], "creative-tools": []}}, "top": ["id1","id2","id3","id4","id5"]}}"""


def _clean_summary(s, fallback):
    s = re.sub(r"\s+", " ", (s or "").strip()).rstrip(".").strip()
    if not s:
        s = fallback
    w = s.split()
    if len(w) > 18:
        s = " ".join(w[:15])
    return s


def _shorten_title(t):
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    w = t.split()
    return t if len(w) <= 15 else " ".join(w[:15]) + "…"


def curate(cands):
    """Return (stories, top_urls, generated_by)."""
    by_id = {c["id"]: c for c in cands}
    # keep the prompt a sensible size: newest first per section
    trimmed = []
    for s in config.SECTIONS:
        sec = [c for c in cands if c["category"] == s["slug"]]
        sec.sort(key=lambda c: (c["via"] != "feed", c["published"]), reverse=False)
        feeds = sorted([c for c in sec if c["via"] == "feed"], key=lambda c: c["published"], reverse=True)
        gn = sorted([c for c in sec if c["via"] != "feed"], key=lambda c: c["published"], reverse=True)
        trimmed += (feeds + gn)[:PER_SECTION_CANDIDATES]

    if ai.available() and trimmed:
        log(f"AI curation over {len(trimmed)} candidates ({config.GEMINI_MODEL})...")
        res = ai.ask_json(_prompt(trimmed), max_tokens=8192)
        stories = _from_ai(res, by_id)
        if stories:
            top_ids = [i for i in (res.get("top") or []) if i in {s["id"] for s in stories}]
            top = _fill_top(stories, top_ids)
            log(f"AI picked {len(stories)} stories")
            return stories, top, "ai"
        log("AI curation failed, using fallback")
    stories = _fallback(trimmed)
    return stories, _fill_top(stories, []), "fallback"


def _from_ai(res, by_id):
    if not isinstance(res, dict) or not isinstance(res.get("sections"), dict):
        return None
    used, stories = set(), []
    for s in config.SECTIONS:
        rank = 0
        for item in res["sections"].get(s["slug"], []) or []:
            if not isinstance(item, dict):
                continue
            c = by_id.get(str(item.get("id", "")).strip())
            if not c or c["id"] in used:
                continue
            if s["slug"] == "creative-tools" and (c.get("no_creative") or is_competitor_story(c["title"])):
                continue
            rank += 1
            if rank > config.MAX_PER_SECTION:
                break
            used.add(c["id"])
            stories.append(_story(c, s["slug"], rank, _clean_summary(item.get("summary"), _shorten_title(c["title"]))))
    return stories if len(stories) >= 5 else None


def _fallback(cands):
    stories = []
    for s in config.SECTIONS:
        rank = 0
        for c in cands:
            if c["category"] != s["slug"]:
                continue
            if s["slug"] == "creative-tools" and is_competitor_story(c["title"]):
                continue
            rank += 1
            if rank > config.MAX_PER_SECTION:
                break
            stories.append(_story(c, s["slug"], rank, _shorten_title(c["title"])))
    return stories


def _story(c, cat, rank, summary):
    return {
        "id": c["id"], "category": cat, "rank": rank, "summary": summary,
        "title": c["title"], "snippet": c.get("snippet", ""), "source": c["source"],
        "url": c["url"], "image": c.get("image"), "published": c.get("published"),
    }


def _fill_top(stories, top_ids):
    ids = list(dict.fromkeys(top_ids))[: config.TOP_N]
    # round-robin through section #1s, #2s... to fill gaps
    for rank in range(1, config.MAX_PER_SECTION + 1):
        for s in stories:
            if len(ids) >= config.TOP_N:
                break
            if s["rank"] == rank and s["id"] not in ids:
                ids.append(s["id"])
    by = {s["id"]: s["url"] for s in stories}
    return [by[i] for i in ids]
