#!/usr/bin/env python3
"""
E2 weekly report — campaign CC01 (Claude Campaign #1).

Reads the Streak "GC Pipeline" (every E2 lead from task #08 has Origin = CC01),
builds a 7-day report and emails it via Resend.

Env:
  STREAK_API_KEY   Streak API key (Gmail > Streak > Settings > API key)
  RESEND_API_KEY   Resend key with sending access for gershon.ai
  REPORT_TO        default report@gershonconsulting.com (comma-separated allowed)
  REPORT_FROM      default "GC E2 Weekly <reports@gershon.ai>"
  DAYS             window length, default 7
  DRY_RUN=1        write out/e2_weekly.html only, do not send
Standard library only.
"""
import base64
import html
import json
import os
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

PIPELINE_KEY = ("agxzfm1haWxmb29nYWVyNwsSDE9yZ2FuaXphdGlvbiIQb2F0dGlhQGdtYWlsLmNvbQwL"
                "EghXb3JrZmxvdxiAgICAwLWbCgw")
ORIGIN_FIELD = "1003"
COUNTRY_FIELD = "1044"
CAMPAIGN = "CC01"
CAMPAIGN_OPTION_KEY = "9230"   # "CC01" in the Origin dropdown (checked 2026-11-04)
DAILY_TARGET = 10

STREAK_KEY = os.environ.get("STREAK_API_KEY", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
REPORT_TO = [a.strip() for a in os.environ.get("REPORT_TO", "report@gershonconsulting.com").split(",") if a.strip()]
REPORT_FROM = os.environ.get("REPORT_FROM", "GC E2 Weekly <reports@gershon.ai>")
DAYS = int(os.environ.get("DAYS", "7"))
DRY_RUN = os.environ.get("DRY_RUN") == "1"


def streak(path):
    auth = base64.b64encode(f"{STREAK_KEY}:".encode()).decode()
    req = urllib.request.Request(f"https://api.streak.com/api{path}",
                                 headers={"Authorization": f"Basic {auth}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def ts(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc) if ms else None


def collector_health():
    log = Path(__file__).resolve().parent.parent / "data" / "candidates" / "latest.log"
    if not log.exists():
        return "❌ data/candidates/latest.log not found"
    lines = log.read_text(errors="ignore").splitlines()
    total = next((l for l in reversed(lines) if l.startswith("TOTAL")), "TOTAL candidates: ?")
    dates = sorted({w for l in lines for w in l.replace(":", " ").split() if len(w) == 10 and w[4] == "-" and w[7] == "-"})
    newest = dates[-1] if dates else "?"
    try:
        age = (datetime.now(timezone.utc).date() - datetime.strptime(newest, "%Y-%m-%d").date()).days
    except ValueError:
        age = 99
    mark = "✅" if age <= 4 else "❌"
    return f"{mark} Visa-signal collector: newest filing date {newest} ({age} days old). {total}"


def main():
    if not STREAK_KEY:
        sys.exit("STREAK_API_KEY missing")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAYS)

    pipe = streak(f"/v1/pipelines/{PIPELINE_KEY}")
    stages = {k: v.get("name", k) for k, v in (pipe.get("stages") or {}).items()}
    origin_opts, country_opts = {}, {}
    for f in pipe.get("fields", []):
        items = (f.get("dropdownSettings") or {}).get("items", [])
        if f.get("key") == ORIGIN_FIELD:
            origin_opts = {str(i["key"]): i["name"] for i in items}
        if f.get("key") == COUNTRY_FIELD:
            country_opts = {str(i["key"]): i["name"] for i in items}
    cc_keys = {k for k, n in origin_opts.items() if n.strip().upper() == CAMPAIGN} | {CAMPAIGN_OPTION_KEY, CAMPAIGN}

    boxes = streak(f"/v1/pipelines/{PIPELINE_KEY}/boxes")
    cc = [b for b in boxes if str((b.get("fields") or {}).get(ORIGIN_FIELD, "")) in cc_keys]

    rows = []
    for b in cc:
        created = ts(b.get("creationTimestamp"))
        sent = ts(b.get("lastEmailSentTimestamp"))
        recv = ts(b.get("lastEmailReceivedTimestamp"))
        stage = stages.get(b.get("stageKey"), b.get("stageKey"))
        bounced = False
        for path in (f"/v2/boxes/{b['boxKey']}/comments", f"/v1/boxes/{b['boxKey']}/comments"):
            try:
                data = streak(path)
                items = data.get("results", data) if isinstance(data, dict) else data
                bounced = any(str(c.get("message", "")).lower().startswith("bounced") for c in items or [])
                break
            except Exception:
                continue
        replied = bool(recv and created and recv > created and not bounced)
        country = (b.get("fields") or {}).get(COUNTRY_FIELD, "")
        rows.append({
            "name": b.get("name", "?"), "key": b["boxKey"], "stage": stage,
            "stage_key": b.get("stageKey"), "created": created, "sent": sent, "recv": recv,
            "replied": replied, "bounced": bounced,
            "country": country_opts.get(str(country), str(country or "")),
        })

    week = [r for r in rows if r["created"] and r["created"] >= start]
    contacted = lambda r: r["stage_key"] != "5001"
    kpi = {
        "new": len(week),
        "intros": sum(1 for r in week if contacted(r)),
        "linkedin_only": sum(1 for r in week if not contacted(r)),
        "replies": sum(1 for r in rows if r["replied"] and r["recv"] >= start),
        "scheduled": sum(1 for r in rows if "schedul" in str(r["stage"]).lower()),
        "bounces": sum(1 for r in week if r["bounced"]),
    }
    per_day = Counter(r["created"].astimezone(timezone(timedelta(hours=-5))).date() for r in week)
    days = [(start + timedelta(days=i + 1)).astimezone(timezone(timedelta(hours=-5))).date() for i in range(DAYS)]
    by_stage = Counter(r["stage"] for r in rows)
    target = DAILY_TARGET * DAYS
    health = collector_health()

    # ---------- HTML ----------
    e = html.escape
    S = "font-family:Arial,sans-serif;color:#12211d"
    def card(label, val, sub=""):
        return (f'<td style="padding:10px;border:1px solid #d8e2de;text-align:center;{S}">'
                f'<div style="font-size:24px;font-weight:bold">{val}</div>'
                f'<div style="font-size:12px;color:#4a5a55">{label}{sub}</div></td>')
    hot = [r for r in rows if r["replied"]]
    def link(r):
        return f'<a href="https://www.streak.com/a/boxes/{e(r["key"])}" style="color:#1f6f5c">{e(r["name"])}</a>'
    tbl = "".join(
        f'<tr><td style="padding:5px;border-bottom:1px solid #eee">{link(r)}</td>'
        f'<td style="padding:5px;border-bottom:1px solid #eee">{e(r["country"])}</td>'
        f'<td style="padding:5px;border-bottom:1px solid #eee">{e(str(r["stage"]))}</td>'
        f'<td style="padding:5px;border-bottom:1px solid #eee">{r["created"].strftime("%a %d %b")}</td>'
        f'<td style="padding:5px;border-bottom:1px solid #eee">{"✅ replied" if r["replied"] else ("❌ bounced" if r["bounced"] else ("sent" if contacted(r) else "LinkedIn only"))}</td></tr>'
        for r in sorted(week, key=lambda r: r["created"]))
    daily = "".join(
        f'<td style="padding:6px;border:1px solid #d8e2de;text-align:center;{S}"><div style="font-size:11px">{d.strftime("%a %d")}</div>'
        f'<div style="font-weight:bold;color:{"#1f6f5c" if per_day[d] >= DAILY_TARGET else "#b42318"}">{per_day[d]}</div></td>'
        for d in days)
    hot_html = ("".join(f"<li>{link(r)} — {e(str(r['stage']))}, last reply {r['recv'].strftime('%d %b')}</li>" for r in hot)
                or "<li>No replies yet.</li>")
    stage_html = "".join(f"<li>{e(str(k))}: {v}</li>" for k, v in by_stage.most_common())
    period = f"{(start + timedelta(days=1)).strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    status = "✅" if kpi["new"] >= target else "❌"
    body = f"""<!DOCTYPE html><html><body style="background:#ffffff;margin:0;padding:16px">
<div style="max-width:680px;margin:auto;{S}">
<h2 style="margin:0 0 4px">E2 weekly report — {period}</h2>
<p style="margin:0 0 14px;color:#4a5a55">Campaign CC01 (Claude Campaign #1) · objective {DAILY_TARGET} new companies a day</p>
<table style="border-collapse:collapse;width:100%"><tr>
{card("new companies", kpi["new"], f" / {target} {status}")}{card("intros sent", kpi["intros"])}{card("replies", kpi["replies"])}
{card("calls scheduled", kpi["scheduled"])}{card("bounces", kpi["bounces"])}{card("LinkedIn only", kpi["linkedin_only"])}
</tr></table>
<h3>New companies per day</h3><table style="border-collapse:collapse"><tr>{daily}</tr></table>
<h3>🔥 Replies (all CC01 leads)</h3><ul>{hot_html}</ul>
<h3>This week's companies</h3>
<table style="border-collapse:collapse;width:100%;font-size:13px"><tr style="background:#eef4f2">
<th style="padding:5px;text-align:left">Company</th><th style="padding:5px;text-align:left">Country</th>
<th style="padding:5px;text-align:left">Stage</th><th style="padding:5px;text-align:left">Added</th><th style="padding:5px;text-align:left">Email</th></tr>
{tbl or '<tr><td colspan="5" style="padding:5px">No new companies this week.</td></tr>'}</table>
<h3>All CC01 leads by stage ({len(rows)} total)</h3><ul>{stage_html or "<li>none</li>"}</ul>
<h3>Sources</h3><p>{e(health)}</p>
<p style="font-size:11px;color:#4a5a55;margin-top:20px">Built by the E2 app (github.com/gershonconsulting/E2, reporting/weekly_report.py) from the Streak GC Pipeline. Replies = an email received on the box after it was created, excluding bounces.</p>
</div></body></html>"""
    text = (f"E2 weekly report — {period}\nNew companies: {kpi['new']} / {target}\nIntros sent: {kpi['intros']}\n"
            f"Replies: {kpi['replies']}\nCalls scheduled: {kpi['scheduled']}\nBounces: {kpi['bounces']}\n"
            f"LinkedIn only: {kpi['linkedin_only']}\n\n" + "\n".join(
                f"- {r['name']} ({r['country']}) — {r['stage']}" for r in sorted(week, key=lambda r: r["created"]))
            + f"\n\n{health}\n")

    out = Path("out"); out.mkdir(exist_ok=True)
    (out / "e2_weekly.html").write_text(body, encoding="utf-8")
    print(text)
    if DRY_RUN:
        return
    if not RESEND_KEY:
        sys.exit("RESEND_API_KEY missing")
    payload = json.dumps({
        "from": REPORT_FROM, "to": REPORT_TO,
        "subject": f"[E2] Weekly report — {now.strftime('%b %d')}: {kpi['new']} new companies, {kpi['intros']} intros, {kpi['replies']} replies",
        "html": body, "text": text,
    }).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=payload, method="POST", headers={
        "Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json",
        "Idempotency-Key": f"e2-weekly-{now.strftime('%Y-%m-%d')}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print("Resend:", r.status, r.read().decode())


if __name__ == "__main__":
    main()
