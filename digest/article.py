"""Resolve Google News links, fetch article pages, pull og:image and text."""
import json
import re
from collections import Counter
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

from .fetch import good_image
from .util import http_get, log, split_sentences, _session

STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being
this that these those it its it's into over after before about than then so such not no new says
said will can could would should has have had do does did up out more most also just how what why
who when where which their them they he she his her we our you your i -- s""".split())


def resolve_google_news(url):
    """Google News RSS links are JS redirects. Decode to the real publisher URL."""
    if "news.google.com" not in url:
        return url
    try:
        m = re.search(r"/(?:rss/)?articles/([^?/]+)", url)
        if not m:
            return url
        gid = m.group(1)
        page = http_get(f"https://news.google.com/articles/{gid}", timeout=15)
        soup = BeautifulSoup(page.text, "html.parser")
        div = soup.select_one("c-wiz > div[jscontroller]") or soup.select_one("[data-n-a-sg]")
        if div is None or not div.get("data-n-a-sg"):
            return url
        sig, ts = div.get("data-n-a-sg"), div.get("data-n-a-ts")
        payload = [
            "Fbv4je",
            f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
            f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{gid}",{ts},"{sig}"]',
        ]
        r = _session.post(
            "https://news.google.com/_/DotsSplashUi/data/batchexecute",
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data=f"f.req={quote(json.dumps([[payload]]))}",
            timeout=15,
        )
        chunk = r.text.split("\n\n")[1]
        decoded = json.loads(json.loads(chunk)[:-2][0][2])[1]
        if decoded.startswith("http"):
            return decoded
    except Exception as ex:  # noqa: BLE001
        log(f"  ~ could not decode Google News link ({ex.__class__.__name__})")
    return url


def fetch_article(url):
    """Return {url, image, text, sentences} (best effort, never raises)."""
    out = {"url": url, "image": None, "text": "", "sentences": []}
    try:
        r = http_get(url, timeout=15, retries=1)
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            return out
        out["url"] = r.url if "news.google.com" not in r.url else url
        soup = BeautifulSoup(r.text, "html.parser")
        for sel in ('meta[property="og:image"]', 'meta[name="og:image"]',
                    'meta[name="twitter:image"]', 'meta[property="twitter:image"]',
                    'meta[name="twitter:image:src"]'):
            tag = soup.select_one(sel)
            if tag and good_image(tag.get("content")):
                out["image"] = good_image(tag.get("content"))
                break
        for bad in soup(["script", "style", "nav", "footer", "header", "aside", "form",
                         "noscript", "figure", "button"]):
            bad.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        paras = []
        for p in root.find_all("p"):
            t = re.sub(r"\s+", " ", p.get_text(" ", strip=True))
            if len(t) >= 60 and not re.search(r"(cookie|subscribe|sign up|newsletter|all rights reserved|©)", t, re.I):
                paras.append(t)
        text = "\n".join(paras)[:12000]
        out["text"] = text
        out["sentences"] = split_sentences(text)[:60]
    except Exception as ex:  # noqa: BLE001
        log(f"  ~ article fetch failed: {urlparse(url).netloc} ({ex.__class__.__name__})")
    return out


def words(s):
    return [w for w in re.findall(r"[a-z0-9$%.]+", s.lower()) if w not in STOP and len(w) > 1]


def extractive_summary(sentences, title="", n=4):
    """Opening sentence + highest-scoring key sentences, in original order."""
    if not sentences:
        return []
    freq = Counter(w for s in sentences for w in words(s))
    tw = set(words(title))
    scored = []
    for i, s in enumerate(sentences):
        ws = words(s)
        if not ws:
            continue
        score = sum(freq[w] for w in ws) / (len(ws) ** 0.6)
        score += 3 * len(tw.intersection(ws))
        if re.search(r"\d", s):
            score *= 1.25
        scored.append((score, i))
    picks = {0}
    for _, i in sorted(scored, reverse=True):
        if len(picks) >= n:
            break
        picks.add(i)
    return [sentences[i] for i in sorted(picks)]
