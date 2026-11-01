"""Entry point.

  python -m digest.main daily [--trigger scheduled|manual|catch-up] [--no-email]
  python -m digest.main catchup        # runs daily only if today's digest is missing
  python -m digest.main recap [--no-email]
  python -m digest.main backfill       # last 6 days + today, no emails
"""
import argparse
from datetime import datetime

from . import ai, config, emailer
from .curate import curate
from .details import enrich, prune_old_details
from .fetch import fetch_all
from .quiz import build_quiz
from .recap import build_recap
from .store import load_digest, rebuild_index, recent_stories, save_digest
from .util import ist_date, last_n_dates, log, now_ist, today_ist


def make_digest(date, cands, source_count, trigger, ai_summaries=True):
    stories, highlights, by = curate(cands)
    # highlights hold urls; enrich may swap Google News links for the real ones
    id_by_url = {s["url"]: s["id"] for s in stories}
    top_ids = [id_by_url[u] for u in highlights if u in id_by_url]
    stories = enrich(stories, date, ai_summaries)
    url_by_id = {s["id"]: s["url"] for s in stories}
    highlights = [url_by_id[i] for i in top_ids]
    for s in stories:
        s.pop("snippet", None)
    digest = {
        "date": date, "stories": stories, "highlights": highlights,
        "updated_at": now_ist().isoformat(), "trigger": trigger, "generated_by": by,
        "candidate_count": len(cands), "source_count": source_count, "email_sent": False,
    }
    save_digest(digest)
    log(f"Saved digest {date}: {len(stories)} stories ({by})")
    return digest


def run_daily(trigger="scheduled", send_email=True):
    cands, nsrc = fetch_all(24)
    date = today_ist()
    if not cands:
        log("No candidates fetched; keeping existing data")
        rebuild_index()
        return
    digest = make_digest(date, cands, nsrc, trigger)
    build_quiz()
    finish()
    if send_email:
        nice = datetime.strptime(date, "%Y-%m-%d").strftime("%a %d %b").replace(" 0", " ")
        ok = emailer.send(f"Daily Tech Digest · {nice} · {len(digest['stories'])} stories",
                          emailer.daily_html(digest))
        if ok:
            digest["email_sent"] = True
            save_digest(digest)


def run_recap(send_email=True):
    recap = build_recap()
    finish()
    if recap and send_email:
        if emailer.send("Daily Tech Digest · Weekly Recap", emailer.recap_html(recap)):
            from .util import data_path, write_json
            recap["email_sent"] = True
            write_json(data_path("recap.json"), recap)


def run_backfill():
    cands, nsrc = fetch_all(24 * 7 + 6)
    today = today_ist()
    for date in last_n_dates(7):  # today first, so it gets the AI budget
        day = [c for c in cands if ist_date(datetime.fromisoformat(c["published"])) == date]
        if not day:
            log(f"{date}: no candidates, skipping")
            continue
        # AI headlines for every day, AI detailed summaries only for today
        make_digest(date, day, nsrc, "backfill", ai_summaries=(date == today))
    build_quiz()
    build_recap()
    finish()
    log("Backfill done (no emails sent)")


def finish():
    keep = {s["id"] for s in recent_stories(45)}
    prune_old_details(keep)
    rebuild_index()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", choices=["daily", "catchup", "recap", "backfill", "index"])
    p.add_argument("--trigger", default="scheduled")
    p.add_argument("--no-email", action="store_true")
    a = p.parse_args()
    log(f"Task={a.task} AI={'on (' + ai.model() + ')' if ai.available() else 'off (fallback mode)'}")
    if a.task == "daily":
        run_daily(a.trigger, not a.no_email)
    elif a.task == "catchup":
        if load_digest(today_ist()):
            log("Today's digest already exists, nothing to catch up")
        else:
            run_daily("catch-up", not a.no_email)
    elif a.task == "recap":
        run_recap(not a.no_email)
    elif a.task == "backfill":
        run_backfill()
    else:
        rebuild_index()


if __name__ == "__main__":
    main()
