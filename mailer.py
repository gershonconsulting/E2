#!/usr/bin/env python3
"""
mailer.py
Render and send the daily E-2 top-10 email via Resend.

Usage:
    python3 mailer.py                    # dry-run: write HTML preview only
        python3 mailer.py --count 10         # dry-run with top N rows
            python3 mailer.py --count 10 --send  # LIVE: actually send via Resend
                python3 mailer.py --date 20260612    # use specific date's CSV
                """

import argparse
import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

OUT_DIR = Path("out")

# Load .env if present
def load_env():
      env_path = Path(__file__).parent / ".env"
      if env_path.exists():
                with open(env_path) as f:
                              for line in f:
                                                line = line.strip()
                                                if line and not line.startswith("#") and "=" in line:
                                                                      k, v = line.split("=", 1)
                                                                      os.environ.setdefault(k.strip(), v.strip())

                                load_env()

        RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM      = os.environ.get("MAIL_FROM", "onboarding@resend.dev")
MAIL_TO        = os.environ.get("MAIL_TO", "aina.rama@gershonconsulting.com")

TIER_COLORS = {
      "Qualified": "#1a7f37",  # green
      "Review":    "#9a6700",  # amber
      "Filler":    "#6e7781",  # grey
}
TIER_BADGES = {
      "Qualified": "&#x2705; Qualified",
      "Review":    "&#x1F50D; Review",
      "Filler":    "&#x23F3; Filler",
}


def find_csv(date_str: str) -> Path:
      """Find the all-rows CSV for the given date."""
    p = OUT_DIR / f"e2_florida_all_{date_str}.csv"
    if p.exists():
              return p
          # fallback: most recent
          candidates = sorted(OUT_DIR.glob("e2_florida_all_*.csv"), reverse=True)
    if candidates:
              return candidates[0]
          raise FileNotFoundError(f"No CSV found for {date_str}. Run florida_pipeline.py first.")


def load_top_n(csv_path: Path, n: int) -> list:
      """Return top-n rows, prioritising Qualified > Review > Filler."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
              reader = csv.DictReader(f)
              for row in reader:
                            rows.append(row)
                    tier_order = {"Qualified": 0, "Review": 1, "Filler": 2}
    rows.sort(key=lambda r: tier_order.get(r.get("tier", "Filler"), 9))
    return rows[:n]


def render_html(rows: list, date_str: str) -> str:
      subject_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

    rows_html = ""
    for i, row in enumerate(rows, 1):
              tier = row.get("tier", "Filler")
        color = TIER_COLORS.get(tier, "#6e7781")
        badge = TIER_BADGES.get(tier, tier)
        corp = row.get("corp_name", "")
        country = row.get("treaty_country") or row.get("principal_country", "")
        city  = row.get("principal_city", "")
        state = row.get("principal_state", "")
        officers = row.get("officers", "")
        reason = row.get("reason", "")
        doc = row.get("document_number", "")
        filed = row.get("date_filed", "")

        rows_html += f"""
                <tr style="border-bottom:1px solid #e1e4e8;">
                          <td style="padding:8px 4px;font-weight:bold;color:#24292f;">{i}</td>
                                    <td style="padding:8px 4px;">
                                                <strong style="color:#24292f;">{corp}</strong><br>
                                                            <small style="color:#57606a;">Doc# {doc} &nbsp;|&nbsp; Filed: {filed}</small>
                                                                      </td>
                                                                                <td style="padding:8px 4px;color:#24292f;">{city}, {state}</td>
                                                                                          <td style="padding:8px 4px;font-weight:bold;color:{color};">{country}</td>
                                                                                                    <td style="padding:8px 4px;"><span style="color:{color};font-size:0.85em;">{badge}</span></td>
                                                                                                              <td style="padding:8px 4px;font-size:0.8em;color:#57606a;">{reason}</td>
                                                                                                                      </tr>"""

    return f"""<!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>E2 Daily Report {subject_date}</title></head>
    <body style="font-family:Arial,sans-serif;max-width:900px;margin:auto;padding:20px;">
      <h2 style="color:#24292f;">Daily Report E2 Companies for BotDog Campaign {subject_date}</h2>
        <p style="color:#57606a;">Top {len(rows)} prospects from Florida new-business filings &mdash; {subject_date}</p>
          <table style="width:100%;border-collapse:collapse;font-size:0.9em;">
              <thead>
                    <tr style="background:#f6f8fa;border-bottom:2px solid #d0d7de;">
                            <th style="padding:8px 4px;text-align:left;">#</th>
                                    <th style="padding:8px 4px;text-align:left;">Company</th>
                                            <th style="padding:8px 4px;text-align:left;">City/State</th>
                                                    <th style="padding:8px 4px;text-align:left;">Country Signal</th>
                                                            <th style="padding:8px 4px;text-align:left;">Tier</th>
                                                                    <th style="padding:8px 4px;text-align:left;">Reason</th>
                                                                          </tr>
                                                                              </thead>
                                                                                  <tbody>
                                                                                        {rows_html}
                                                                                            </tbody>
                                                                                              </table>
                                                                                                <hr style="margin-top:30px;border:none;border-top:1px solid #e1e4e8;">
                                                                                                  <p style="font-size:0.75em;color:#57606a;">
                                                                                                      <strong>Tier guide:</strong>
                                                                                                          &#x2705; <strong>Qualified</strong> = foreign treaty-country address confirmed &nbsp;|&nbsp;
                                                                                                              &#x1F50D; <strong>Review</strong> = treaty signal, needs verification &nbsp;|&nbsp;
                                                                                                                  &#x23F3; <strong>Filler</strong> = no signal, domestic or unknown.<br>
                                                                                                                      Filler rows are NOT vetted E-2 prospects. Non-treaty-country companies are never included.
                                                                                                                        </p>
                                                                                                                        </body>
                                                                                                                        </html>"""


def send_email(subject: str, html: str) -> bool:
      """Send via Resend API. Returns True on success."""
    try:
              import urllib.request
        import json
        payload = json.dumps({
                      "from":    MAIL_FROM,
                      "to":      [MAIL_TO],
                      "subject": subject,
                      "html":    html,
        }).encode("utf-8")
        req = urllib.request.Request(
                      "https://api.resend.com/emails",
                      data=payload,
                      headers={
                                        "Authorization": f"Bearer {RESEND_API_KEY}",
                                        "Content-Type":  "application/json",
                      },
                      method="POST",
        )
        with urllib.request.urlopen(req) as resp:
                      body = resp.read()
                      print(f"[mailer] Resend response: {resp.status} {body}")
                      return resp.status in (200, 201)
except Exception as e:
        print(f"[mailer] Send error: {e}", file=sys.stderr)
        return False


def main():
      parser = argparse.ArgumentParser(description="E-2 daily mailer")
    parser.add_argument("--date",  help="Date string YYYYMMDD")
    parser.add_argument("--count", type=int, default=10, help="Number of rows (default 10)")
    parser.add_argument("--send",  action="store_true", help="Actually send (default: dry-run)")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y%m%d")
    subject_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    subject = f"Daily Report E2 Companies for BotDog Campaign {subject_date}"

    csv_path = find_csv(date_str)
    print(f"[mailer] Loading from {csv_path}")
    rows = load_top_n(csv_path, args.count)
    print(f"[mailer] Top {len(rows)} rows loaded")

    html = render_html(rows, date_str)

    OUT_DIR.mkdir(exist_ok=True)
    preview_path = OUT_DIR / f"email_preview_{date_str}.html"
    preview_path.write_text(html, encoding="utf-8")
    print(f"[mailer] Preview written: {preview_path}")

    if args.send:
              if not RESEND_API_KEY:
                            print("[mailer] ERROR: RESEND_API_KEY not set. Aborting.", file=sys.stderr)
                            sys.exit(1)
                        print(f"[mailer] Sending to {MAIL_TO} ...")
        ok = send_email(subject, html)
        if ok:
                      print("[mailer] Email sent successfully.")
else:
            print("[mailer] Send failed.", file=sys.stderr)
            sys.exit(1)
else:
        print(f"[mailer] DRY-RUN: open {preview_path} to review. Pass --send to actually send.")


if __name__ == "__main__":
      main()
