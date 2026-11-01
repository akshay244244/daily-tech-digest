"""'Bold Brutalist' emails, sent through Gmail SMTP (free)."""
import html
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from . import config
from .util import log

CREAM, YELLOW, BLACK = "#F5F2E8", "#FFE14D", "#0A0A0A"
MONO = "'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace"
SANS = "'Space Grotesk','Helvetica Neue',Arial,sans-serif"
e = html.escape


def _card(rank, story, show_section=False, why=None, date=None):
    sec = config.SECTION_BY_SLUG[story["category"]]
    color = sec["color"]
    meta = e(story["source"]).upper()
    if date:
        meta += " · " + e(_short_date(date)).upper()
    section_line = (f'<div style="font:700 10px/1.4 {MONO};letter-spacing:.08em;color:{color};'
                    f'text-transform:uppercase;margin-bottom:4px">{e(sec["name"])}</div>') if show_section else ""
    why_line = (f'<div style="font:400 13px/1.45 {SANS};color:#333;margin-top:6px">{e(why)}</div>') if why else ""
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 14px 0">
<tr><td style="background:#FFFFFF;border:2px solid {BLACK};border-right:6px solid {color};border-bottom:6px solid {color};padding:14px 16px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td valign="top" width="40" style="font:800 22px/1 {SANS};color:{color};padding-right:10px">{rank:02d}</td>
<td valign="top">{section_line}
<a href="{e(story['url'])}" style="font:700 16px/1.35 {SANS};color:{BLACK};text-decoration:none">{e(story['summary'])}</a>
{why_line}
<div style="font:600 10px/1.4 {MONO};letter-spacing:.08em;color:#666;margin-top:8px">{meta}</div>
</td></tr></table></td></tr></table>"""


def _bar(label, color=None, count=None):
    sq = (f'<span style="display:inline-block;width:12px;height:12px;background:{color};'
          f'border:2px solid #fff;vertical-align:-2px;margin-right:8px"></span>') if color else ""
    cnt = (f'<td align="right" style="font:600 11px/1 {MONO};color:#fff;padding:10px 14px;'
           f'text-transform:uppercase;letter-spacing:.08em">{count} stories</td>') if count is not None else ""
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:26px 0 14px 0;background:{BLACK}">
<tr><td style="font:800 13px/1 {SANS};color:#fff;padding:10px 14px;letter-spacing:.1em;text-transform:uppercase">{sq}{e(label)}</td>{cnt}</tr></table>"""


def _short_date(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")


def _shell(date_label, title, subline, body, button_label, link):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{e(title)}</title></head>
<body style="margin:0;padding:0;background:{CREAM}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CREAM}"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px">
<tr><td style="padding:0 6px 6px 0">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{YELLOW};border:4px solid {BLACK};box-shadow:8px 8px 0 {BLACK}">
<tr><td style="padding:22px 22px 20px">
<div style="font:700 11px/1.4 {MONO};letter-spacing:.12em;text-transform:uppercase;color:{BLACK}">{e(date_label)}</div>
<div style="font:900 34px/1.05 {SANS};letter-spacing:-.01em;text-transform:uppercase;color:{BLACK};margin:8px 0 10px">{e(title)}</div>
<div style="font:500 15px/1.4 {SANS};color:{BLACK}">{e(subline)}</div>
</td></tr></table></td></tr>
<tr><td style="padding-top:8px">{body}</td></tr>
<tr><td align="left" style="padding:26px 0 10px">
<a href="{e(link)}" style="display:inline-block;background:{YELLOW};border:3px solid {BLACK};box-shadow:4px 4px 0 {BLACK};padding:14px 22px;font:800 14px/1 {SANS};letter-spacing:.08em;text-transform:uppercase;color:{BLACK};text-decoration:none">{e(button_label)} &rarr;</a>
</td></tr>
<tr><td style="padding:22px 0 8px;font:500 11px/1.6 {MONO};color:#555">Daily Tech Digest · Refreshed daily at 06:30 IST · Public RSS &amp; Google News · No ads<br>
<a href="{e(config.site_url())}" style="color:#555">{e(config.site_url())}</a></td></tr>
</table></td></tr></table></body></html>"""


def daily_html(digest):
    stories = digest["stories"]
    by_url = {s["url"]: s for s in stories}
    top = [by_url[u] for u in digest.get("highlights", []) if u in by_url]
    date_label = datetime.strptime(digest["date"], "%Y-%m-%d").strftime("%A, %B %d, %Y").replace(" 0", " ")
    body = _bar("Today's top 5")
    body += "".join(_card(i, s, show_section=True) for i, s in enumerate(top, 1))
    top_ids = {s["id"] for s in top}
    for sec in config.SECTIONS:
        sec_stories = [s for s in stories if s["category"] == sec["slug"]]
        if not sec_stories:
            continue
        body += _bar(sec["name"], sec["color"], len(sec_stories))
        rest = [s for s in sec_stories if s["id"] not in top_ids][:3]
        body += "".join(_card(s["rank"], s) for s in rest)
    link = config.site_url() + f"#/digest/{digest['date']}"
    return _shell(date_label, "Daily Tech Digest",
                  f"{len(stories)} stories worth your time today, across 5 sections",
                  body, "Open today's digest", link)


def recap_html(recap):
    a = datetime.strptime(recap["week_start"], "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")
    b = datetime.strptime(recap["week_end"], "%Y-%m-%d").strftime("%b %d, %Y").replace(" 0", " ")
    body = ""
    for sec in config.SECTIONS:
        items = [i for i in recap["items"] if i["category"] == sec["slug"]]
        if not items:
            continue
        body += _bar(sec["name"], sec["color"], len(items))
        body += "".join(_card(i["rank"], i, why=i["why"], date=i["date"]) for i in items)
    return _shell(f"Week of {a} – {b}", "Weekly Recap",
                  f"The {len(recap['items'])} stories that mattered most this week",
                  body, "Open the weekly recap", config.site_url() + "#/recap")


def send(subject, html_body):
    if not (config.GMAIL_USER and config.GMAIL_APP_PASSWORD and config.EMAIL_TO):
        log("Email skipped (GMAIL_USER / GMAIL_APP_PASSWORD not set)")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Daily Tech Digest <{config.GMAIL_USER}>"
    msg["To"] = config.EMAIL_TO
    msg.attach(MIMEText(f"Open your digest: {config.site_url()}", "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
            s.sendmail(config.GMAIL_USER, [x.strip() for x in config.EMAIL_TO.split(",")], msg.as_string())
        log(f"Email sent to {config.EMAIL_TO}")
        return True
    except Exception as ex:  # noqa: BLE001
        log(f"Email failed: {ex}")
        return False
