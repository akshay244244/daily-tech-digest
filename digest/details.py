"""Fill images, resolve links, and build each story's detail file (summary + sentences)."""
import os
from concurrent.futures import ThreadPoolExecutor

from . import ai
from .article import extractive_summary, fetch_article, resolve_google_news
from .util import data_path, log, read_json, write_json

BATCH = 8


def _detail_path(sid):
    return data_path("stories", f"{sid}.json")


def enrich(stories, date, ai_summaries=True):
    """Mutates stories (url, image). Writes site/data/stories/<id>.json for each."""
    todo = []
    for s in stories:
        existing = read_json(_detail_path(s["id"]))
        if existing and existing.get("sentences"):
            s["url"] = existing.get("url", s["url"])
            s["image"] = s.get("image") or existing.get("image")
            continue
        todo.append(s)

    def work(s):
        url = resolve_google_news(s["url"])
        art = fetch_article(url)
        return s, url, art

    log(f"Fetching {len(todo)} articles for images + summaries...")
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(work, todo))

    new_details = []
    for s, url, art in results:
        s["url"] = art.get("url") or url
        if not s.get("image"):
            s["image"] = art.get("image")
        sentences = art.get("sentences") or []
        if not sentences and s.get("snippet"):
            sentences = [s["snippet"]]
        detail = {
            "id": s["id"], "url": s["url"], "title": s["title"], "summary": s["summary"],
            "source": s["source"], "category": s["category"], "date": date, "image": s.get("image"),
            "detailed": extractive_summary(sentences, s["title"]),
            "detail_kind": "extractive",
            "sentences": sentences,
            "text": (art.get("text") or "")[:6000],
        }
        new_details.append(detail)

    if ai_summaries and ai.available() and new_details:
        _ai_summaries([d for d in new_details if len(d["text"]) > 400])

    for d in new_details:
        d.pop("text", None)
        write_json(_detail_path(d["id"]), d)
    return stories


def _ai_summaries(details):
    for i in range(0, len(details), BATCH):
        chunk = details[i:i + BATCH]
        body = "\n\n".join(
            f'### id: {d["id"]}\nTitle: {d["title"]}\nArticle:\n{d["text"][:4500]}' for d in chunk
        )
        prompt = (
            "For each article below, write a detailed summary for a tech product manager: "
            "3 to 5 short bullet sentences covering what happened, key numbers, who is involved, "
            "and why it matters. Use only facts from the article. No hype.\n\n"
            f"{body}\n\nReturn JSON only: {{\"items\": [{{\"id\": \"...\", \"bullets\": [\"...\"]}}]}}"
        )
        res = ai.ask_json(prompt, max_tokens=4096)
        if not isinstance(res, dict):
            continue
        by = {d["id"]: d for d in chunk}
        for it in res.get("items", []) or []:
            d = by.get(str(it.get("id")))
            bullets = [b.strip() for b in (it.get("bullets") or []) if isinstance(b, str) and b.strip()]
            if d and bullets:
                d["detailed"] = bullets[:6]
                d["detail_kind"] = "ai"


def prune_old_details(keep_ids):
    folder = os.path.dirname(data_path("stories", "x.json"))
    removed = 0
    for f in os.listdir(folder):
        if f.endswith(".json") and f[:-5] not in keep_ids:
            os.remove(os.path.join(folder, f))
            removed += 1
    if removed:
        log(f"Pruned {removed} old story files")
