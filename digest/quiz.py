"""Pre-generate today's AI quiz questions (the website falls back to a headline quiz)."""
import os

from . import ai
from .store import recent_stories
from .util import data_path, log, read_json, today_ist, write_json

LEVELS = {
    "easy": "Easy: 'who launched what' — which company/person did the thing.",
    "medium": "Medium: names, numbers, details mentioned in the stories.",
    "hard": "Hard: specifics and connections between stories (amounts, dates, competitors, implications).",
}


def build_quiz():
    stories = recent_stories(7)
    if len(stories) < 5 or not ai.available():
        log("Quiz: skipping AI quiz (website will use the headline quiz)")
        return
    by_id = {s["id"]: s for s in stories}
    lines = []
    for s in stories:
        det = read_json(data_path("stories", f"{s['id']}.json")) or {}
        extra = " ".join((det.get("detailed") or [])[:3])[:400]
        lines.append(f'{s["id"]} | {s["category"]} | {s["date"]} | {s["summary"]} | {extra}')
    facts = "\n".join(lines)
    out = {"date": today_ist()}
    for level, desc in LEVELS.items():
        prompt = f"""Write 15 multiple-choice quiz questions about the news below (last 7 days), for a tech product manager.
Difficulty — {desc}
Rules: 4 options each, exactly one correct, plausible distractors, answer must be supported by the facts given. Spread questions across different stories and sections. One-sentence explanation.

NEWS (story_id | section | date | headline | details):
{facts}

Return JSON only: {{"questions": [{{"question": "...", "options": ["a","b","c","d"], "answer_index": 0, "explanation": "...", "story_id": "..."}}]}}"""
        res = ai.ask_json(prompt, max_tokens=8000, temperature=0.6)
        qs = []
        for q in (res or {}).get("questions", []) if isinstance(res, dict) else []:
            s = by_id.get(str(q.get("story_id")))
            opts = q.get("options")
            ai_idx = q.get("answer_index")
            if not s or not isinstance(opts, list) or len(opts) != 4 or not isinstance(ai_idx, int) or not 0 <= ai_idx < 4:
                continue
            qs.append({
                "question": str(q.get("question", "")).strip(), "options": [str(o) for o in opts],
                "answer_index": ai_idx, "explanation": str(q.get("explanation", "")).strip(),
                "category": s["category"], "source": s["source"], "url": s["url"],
                "story_date": s["date"], "story_id": s["id"],
            })
        out[level] = qs
        log(f"Quiz {level}: {len(qs)} questions")
    if any(out.get(lv) for lv in LEVELS):
        write_json(data_path("quiz", f"{out['date']}.json"), out)
        write_json(data_path("quiz.json"), out)
    folder = os.path.dirname(data_path("quiz", "x.json"))
    for f in sorted(os.listdir(folder))[:-3]:
        os.remove(os.path.join(folder, f))
