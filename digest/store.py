"""Read/write digests and keep site/data/index.json in sync."""
import os

from . import config
from .util import data_path, now_ist, read_json, write_json

KEEP_DAYS = 120


def digest_path(date):
    return data_path("digests", f"{date}.json")


def load_digest(date):
    return read_json(digest_path(date))


def save_digest(d):
    write_json(digest_path(d["date"]), d)


def all_dates():
    folder = os.path.dirname(digest_path("x"))
    return sorted((f[:-5] for f in os.listdir(folder) if f.endswith(".json")), reverse=True)


def rebuild_index():
    dates = all_dates()
    for old in dates[KEEP_DAYS:]:
        os.remove(digest_path(old))
    dates = dates[:KEEP_DAYS]
    rows = []
    for d in dates:
        dg = load_digest(d) or {}
        rows.append({"date": d, "count": len(dg.get("stories", [])),
                     "generated_by": dg.get("generated_by")})
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    idx = {
        "dates": rows,
        "latest": dates[0] if dates else None,
        "sections": [{k: s[k] for k in ("slug", "name", "color", "blurb")} for s in config.SECTIONS],
        "site_url": config.site_url(),
        "refresh_url": f"https://github.com/{repo}/actions/workflows/digest.yml" if repo else "",
        "generated_at": now_ist().isoformat(),
    }
    write_json(data_path("index.json"), idx)
    return idx


def recent_stories(days=7, end=None):
    from .util import last_n_dates
    out = []
    for date in last_n_dates(days, end):
        dg = load_digest(date)
        if not dg:
            continue
        for s in dg.get("stories", []):
            out.append({**s, "date": date})
    return out
