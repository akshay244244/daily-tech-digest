"""Tiny Gemini client. Any failure returns None so callers use their fallback.

Free-tier safety:
- tries a fast model first (Flash-Lite), falls back to Flash if it doesn't exist
- turns "thinking" off so answers come back in seconds
- if Gemini keeps timing out / rate-limiting, AI is switched off for the rest of
  the run and everything falls back instantly instead of waiting
"""
import json
import re
import time

from . import config
from .util import _session, log

_disabled_reason = None
_failed_calls = 0
_started = time.time()
AI_TIME_BUDGET = 15 * 60   # seconds of total run time after which AI is skipped
MAX_FAILED_CALLS = 2       # consecutive failed calls before giving up
REQUEST_TIMEOUT = 75

# Model order: explicit GEMINI_MODEL variable first, else fast -> standard.
_models = ([config.GEMINI_MODEL] if config.GEMINI_MODEL_SET else []) + \
          ["gemini-flash-lite-latest", "gemini-flash-latest"]
_models = list(dict.fromkeys(_models))
_send_thinking_off = True


def available():
    return bool(config.GEMINI_API_KEY) and _disabled_reason is None


def model():
    return _models[0] if _models else "none"


def _disable(reason):
    global _disabled_reason
    _disabled_reason = reason
    log(f"  AI switched off for this run -> using fallbacks ({reason})")


def _err_msg(r):
    try:
        msg = r.json().get("error", {}).get("message", "")
    except Exception:  # noqa: BLE001
        msg = r.text
    return re.sub(r"\s+", " ", msg or "")[:300]


def _body(prompt, max_tokens, temperature):
    gen = {"temperature": temperature, "maxOutputTokens": max_tokens,
           "responseMimeType": "application/json"}
    if _send_thinking_off:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    return {"contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}


def ask_json(prompt, max_tokens=4096, temperature=0.3):
    """Send a prompt, get parsed JSON back, or None."""
    global _failed_calls, _send_thinking_off
    if not available():
        return None
    if time.time() - _started > AI_TIME_BUDGET:
        _disable("time budget used up")
        return None

    attempts = 0
    while attempts < 2 and _models:
        attempts += 1
        time.sleep(4)  # stay under free-tier requests-per-minute
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model()}:generateContent"
        try:
            r = _session.post(url, json=_body(prompt, max_tokens, temperature),
                              timeout=REQUEST_TIMEOUT,
                              headers={"x-goog-api-key": config.GEMINI_API_KEY})
        except Exception as ex:  # noqa: BLE001
            log(f"  AI request error: {ex.__class__.__name__} ({model()})")
            continue

        if r.status_code == 404:          # model name not available -> try next one
            log(f"  AI model {model()} not found, trying next")
            _models.pop(0)
            attempts -= 1
            continue
        if r.status_code == 400 and _send_thinking_off:
            log(f"  AI 400 with thinking off ({_err_msg(r)}); retrying without that setting")
            _send_thinking_off = False    # this model can't turn thinking off; resend without it
            attempts -= 1
            continue
        if r.status_code == 429:
            why = _err_msg(r)
            log(f"  AI rate-limited ({model()}): {why}")
            if re.search(r"per[ _]?day|PerDay|limit: ?0\b|billing", why, re.I):
                if len(_models) > 1:      # daily quota is per model: try the other one
                    _models.pop(0)
                    attempts -= 1
                    continue
                _disable("daily free quota reached")
                return None
            time.sleep(30)
            continue
        if r.status_code in (400, 401, 403):
            _disable(f"HTTP {r.status_code}: {_err_msg(r)}")
            return None
        if r.status_code != 200:
            log(f"  AI HTTP {r.status_code} ({model()})")
            time.sleep(8)
            continue
        try:
            data = r.json()
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]
                           if not p.get("thought"))
            out = parse_json(text)
            _failed_calls = 0
            return out
        except Exception as ex:  # noqa: BLE001
            log(f"  AI returned unreadable output ({ex.__class__.__name__})")
            return None

    if not _models:
        _disable("no Gemini model available for this key")
        return None
    _failed_calls += 1
    if _failed_calls >= MAX_FAILED_CALLS:
        _disable("Gemini kept timing out / failing")
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
