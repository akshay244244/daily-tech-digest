"""AI editor (Gemini) that picks and rewrites stories, with a non-AI fallback."""
import re

from . import ai, config
from .fetch import is_competitor_story
from .util import log

PER_SECTION_CANDIDATES = 30

# Used when ranking without AI (and to choose what the AI sees).
SECTION_WORDS = {
    "frontier-ai": r"\b(AI|A\.I\.|LLMs?|GPT[- ]?\w*|OpenAI|Anthropic|Claude|Gemini|DeepMind|Llama|Mistral|DeepSeek|Qwen|Grok|xAI|Copilot|chatbots?|agents?|agentic|models?|neural|machine learning|inference|reasoning|benchmark|research|paper)\b",
    "global-tech": r"\b(Apple|Microsoft|Amazon|AWS|Google|Alphabet|Nvidia|Meta|Tesla|Samsung|Intel|AMD|TSMC|Qualcomm|Netflix|Spotify|chips?|semiconductors?|antitrust|regulat\w*|lawsuit|earnings|revenue|acqui\w*|launch\w*|EU|FTC|DOJ|data centers?|iPhone|Android|Windows)\b",
    "india-startups": r"\b(rais\w*|funding|fund|IPO|DRHP|layoffs?|startups?|SEBI|RBI|NPCI|UPI|crore|lakh|valuation|acqui\w*|Series [A-F]|seed|unicorn|fintech|edtech|quick commerce|Zepto|Swiggy|Zomato|Blinkit|Flipkart|Paytm|PhonePe|Razorpay|Ola|Meesho|Groww|Zerodha|launch\w*|policy)\b",
    "product-craft": r"\b(product|PMs?|growth|strateg\w*|framework|launch\w*|features?|redesign\w*|users|retention|onboarding|pricing|roadmap|lessons?|metrics?|experiment\w*|design)\b",
    "creative-tools": r"\b(Adobe|Photoshop|Lightroom|Firefly|Premiere|Illustrator|After Effects|Generative Fill|cameras?|lens(es)?|Sony|Canon|Nikon|Fujifilm|Leica|Panasonic|DJI|GoPro|Midjourney|Stable Diffusion|Flux|image generat\w*|AI image|photo\w*|edit\w*|creators?)\b",
}
JUNK = (r"(\bdeals?\b|discount|% off|\bsale\b|save \$|coupon|giveaway|days left|last chance|"
        r"register now|tickets|webinar|sponsored|horoscope|best .{0,40}(to buy|deals|for \d{4})|"
        r"gift guide|how to watch|livestream|wordle|crossword|weekly roundup|this week in|newsletter:)")


def relevance(c):
    """Rough non-AI importance score for a candidate within its section."""
    t = c["title"]
    hits = len(re.findall(SECTION_WORDS.get(c["category"], r"$^"), t, re.I))
    score = min(hits, 3) * 2
    if re.search(JUNK, t, re.I):
        score -= 100
    if c["source"].startswith("Hacker News") and hits == 0:
        score -= 100           # off-topic HN front page items
    if c["source"].startswith("Reddit"):
        score -= 1             # forum chatter ranks below news
    if re.search(r"\d", t):
        score += 1             # numbers usually mean concrete news
    if c.get("via") == "feed":
        score += 1             # original publisher over aggregator
    if t.endswith("?") or t.lower().startswith(("why ", "how ", "what ", "opinion", "the case for")):
        score -= 2             # explainers / opinion
    return score



def _prompt(cands):
    secs = "\n".join(f'- "{s["slug"]}" ({s["name"]}): {s["brief"]}' for s in config.SECTIONS)
    lines = "\n".join(
        f'{c["id"]} | {c["category"]} | {c["source"]} | {c["title"]} | {c["snippet"][:100]}'
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
    # keep the prompt a sensible size: most relevant + newest first per section
    trimmed = []
    for s in config.SECTIONS:
        sec = [c for c in cands if c["category"] == s["slug"]]
        scored = [(relevance(c), c) for c in sec]
        scored = [x for x in scored if x[0] > -50]
        scored.sort(key=lambda x: (x[0], x[1]["published"]), reverse=True)
        trimmed += [c for _, c in scored][:PER_SECTION_CANDIDATES]

    if ai.available() and trimmed:
        log(f"AI curation over {len(trimmed)} candidates ({ai.model()})...")
        res = ai.ask_json(_prompt(trimmed), max_tokens=6000)
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
