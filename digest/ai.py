"""Tiny Gemini client. Any failure returns None so callers use their fallback."""
import json
import re
import time

from . import config
from .util import _session, log

_disabled_reason = None


def available():
    return bool(config.GEMINI_API_KEY) and _disabled_reason is None


def ask_json(prompt, max_tokens=8192, temperature=0.3):
    """Send a prompt, get parsed JSON back, or None."""
    global _disabled_reason
    if not available():
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    for attempt in range(3):
        time.sleep(4)  # stay well under free-tier requests-per-minute
        try:
            r = _session.post(url, json=body, timeout=120,
                              headers={"x-goog-api-key": config.GEMINI_API_KEY})
        except Exception as ex:  # noqa: BLE001
            log(f"  AI request error: {ex.__class__.__name__}")
            time.sleep(5)
            continue
        if r.status_code == 429:
            wait = 20 * (attempt + 1)
            log(f"  AI rate-limited, waiting {wait}s")
            time.sleep(wait)
            continue
        if r.status_code in (400, 401, 403, 404):
            _disabled_reason = f"HTTP {r.status_code}: {r.text[:200]}"
            log(f"  AI disabled for this run ({_disabled_reason})")
            return None
        if r.status_code != 200:
            log(f"  AI HTTP {r.status_code}")
            time.sleep(5)
            continue
        try:
            data = r.json()
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            return parse_json(text)
        except Exception as ex:  # noqa: BLE001
            log(f"  AI returned unreadable output ({ex.__class__.__name__})")
            return None
    return None


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"[\[{].*[\]}]", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise
