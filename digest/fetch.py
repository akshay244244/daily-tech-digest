"""Fetch candidates from RSS feeds + Google News, filter by age, remove duplicates."""
import calendar
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import feedparser

from . import config
from .util import clean_text, http_get, log, norm_title, norm_url, uid

TRACKING_HINTS = ("/pixel", "pixel.gif", "pixel.png", "tracking", "1x1", "spacer", "blank.gif",
                  "feeds.feedburner", "doubleclick", "/stats/", "beacon", "/b/ss/")


def good_image(url):
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith("https://"):
        return None
    low = url.lower()
    if any(h in low for h in TRACKING_HINTS):
        return None
    if re.search(r"[?&](w|width|h|height)=1(&|$)", low):
        return None
    return url


def entry_image(e):
    for key in ("media_content", "media_thumbnail"):
        for m in e.get(key, []) or []:
            img = good_image(m.get("url"))
            if img and (m.get("width") in (None, "") or str(m.get("width")) not in ("1", "0")):
                return img
    for enc in e.get("enclosures", []) or []:
        if (enc.get("type") or "").startswith("image"):
            img = good_image(enc.get("href") or enc.get("url"))
            if img:
                return img
    html = ""
    if e.get("content"):
        html = " ".join(c.get("value", "") for c in e["content"])
    html += " " + (e.get("summary") or "")
    for m in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I):
        img = good_image(m.group(1))
        if img:
            return img
    return None


def entry_time(e):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = e.get(key)
        if t:
            return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
    return None


def is_competitor_story(title, snippet=""):
    """True if the story's subject is an Adobe competitor (not just a mention)."""
    t = title.lower()
    hits = [c for c in config.COMPETITORS if re.search(rf"\b{re.escape(c)}\b", t)]
    if not hits:
        return False
    if re.search(r"\badobe\b|photoshop|lightroom|firefly|premiere|illustrator", t):
        # Mainly about Adobe and mentions a rival -> allowed only if Adobe comes first
        first_adobe = re.search(r"\badobe\b|photoshop|lightroom|firefly|premiere|illustrator", t).start()
        first_rival = min(re.search(rf"\b{re.escape(c)}\b", t).start() for c in hits)
        return first_rival < first_adobe
    return True


def parse_feed(url, source, category, max_age_h, is_gnews, now):
    try:
        r = http_get(url, timeout=20)
        if r.status_code != 200:
            log(f"  ! {source}: HTTP {r.status_code}")
            return []
        feed = feedparser.parse(r.content)
    except Exception as ex:  # noqa: BLE001
        log(f"  ! {source}: {ex}")
        return []
    items = []
    for e in feed.entries:
        title = clean_text(e.get("title"))
        link = (e.get("link") or "").strip()
        if not title or not link:
            continue
        published = entry_time(e)
        if published is None:
            continue
        age_h = (now - published).total_seconds() / 3600
        if age_h > max_age_h or age_h < -6:
            continue
        src = source
        if is_gnews:
            gsrc = (e.get("source") or {}).get("title") if isinstance(e.get("source"), dict) else None
            src = clean_text(gsrc) or "Google News"
            # strip " - Source" suffix
            if title.endswith(" - " + src):
                title = title[: -len(" - " + src)].strip()
            else:
                title = re.sub(r"\s+-\s+[^-]{2,60}$", "", title).strip()
        snippet = clean_text(e.get("summary") or "")
        if is_gnews:
            snippet = ""  # Google News descriptions are just the title + link
        if snippet.lower().startswith(title.lower()[:40]):
            snippet = snippet[len(title):].strip()
        items.append({
            "id": uid(link),
            "category": category,
            "title": title,
            "snippet": snippet[:300],
            "url": link,
            "source": src,
            "image": None if is_gnews else entry_image(e),
            "published": published.isoformat(),
            "via": "gnews" if is_gnews else "feed",
        })
    return items


def fetch_all(window_hours=24):
    """Return (candidates, source_count). window_hours>24 is used by the backfill."""
    now = datetime.now(timezone.utc)
    jobs = []
    for cat, feeds in config.FEEDS.items():
        for url, src, max_h in feeds:
            jobs.append((url, src, cat, max(max_h, window_hours), False))
    gwin = "1d" if window_hours <= 24 else f"{max(1, round(window_hours / 24))}d"
    for cat, qs in config.QUERIES.items():
        for q in qs:
            jobs.append((config.gnews(q, gwin), "Google News", cat, max(window_hours, 26), True))

    log(f"Fetching {len(jobs)} feeds...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda j: parse_feed(j[0], j[1], j[2], j[3], j[4], now), jobs))

    ok_sources = sum(1 for r in results if r)
    # direct feeds first so the original publisher wins over the aggregator copy
    ordered = [it for (job, res) in zip(jobs, results) if not job[4] for it in res]
    ordered += [it for (job, res) in zip(jobs, results) if job[4] for it in res]

    seen_t, seen_u, out = set(), set(), []
    for it in ordered:
        t, u = norm_title(it["title"]), norm_url(it["url"])
        if not t or t in seen_t or u in seen_u:
            continue
        # near-duplicate title check (same first 8 words)
        key8 = " ".join(t.split()[:8])
        if len(t.split()) >= 8 and key8 in seen_t:
            continue
        seen_t.add(t)
        seen_t.add(key8)
        seen_u.add(u)
        if it["category"] == "creative-tools" and is_competitor_story(it["title"], it["snippet"]):
            continue
        if is_competitor_story(it["title"]) and re.search(r"canva|figma|affinity|pixelmator|luminar|capture one|corel", it["title"], re.I):
            # never let a rival story slip into Creative Tools via re-sectioning later
            it["no_creative"] = True
        out.append(it)
    log(f"Got {len(out)} unique candidates from {ok_sources}/{len(jobs)} sources")
    return out, ok_sources
