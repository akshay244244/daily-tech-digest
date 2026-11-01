"""Shared helpers: India time, HTTP, text normalising, JSON storage."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from . import config

IST = ZoneInfo("Asia/Kolkata")

_session = requests.Session()
_session.headers.update({
    "User-Agent": config.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/rss+xml,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
})


def now_ist():
    return datetime.now(IST)


def today_ist():
    return now_ist().strftime("%Y-%m-%d")


def ist_date(dt):
    return dt.astimezone(IST).strftime("%Y-%m-%d")


def last_n_dates(n=7, end=None):
    end_d = datetime.strptime(end, "%Y-%m-%d") if end else now_ist().replace(tzinfo=None)
    return [(end_d - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n)]


def http_get(url, timeout=15, retries=2, **kw):
    last = None
    for attempt in range(retries + 1):
        try:
            r = _session.get(url, timeout=timeout, allow_redirects=True, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                last = RuntimeError(f"HTTP {r.status_code}")
                time.sleep(1.5 * (attempt + 1))
                continue
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.0 * (attempt + 1))
    raise last


def norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_url(u):
    u = (u or "").strip().lower()
    u = re.sub(r"^https?://(www\.|m\.|amp\.)?", "", u)
    u = u.split("#")[0].split("?")[0].rstrip("/")
    u = re.sub(r"/amp$", "", u)
    return u


def uid(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def clean_text(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'")
          .replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">"))
    return re.sub(r"\s+", " ", s).strip()


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", text or "")
    return [p.strip() for p in parts if 30 <= len(p.strip()) <= 400]


# ---------- JSON storage (the "database" is plain files in the repo) ----------

def data_path(*parts):
    p = os.path.join(config.DATA_DIR, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def log(*a):
    print(f"[{now_ist().strftime('%H:%M:%S')} IST]", *a, flush=True)
