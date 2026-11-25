import os, sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reporting"))
import weekly_report as w

def ms(dt): return int(dt.timestamp() * 1000)

PIPE = {
    "stageOrder": ["5001", "5002", "5010", "5003", "5004"],
    "stages": {"5001": {"name": "1. Lead"}, "5002": {"name": "2. Contacted"}, "5010": {"name": "3. Scheduled"},
               "5003": {"name": "4. Pitched"}, "5004": {"name": "5. Won"}},
    "fields": [{"key": "1003", "dropdownSettings": {"items": [{"key": 9230, "name": "CC01"}, {"key": 9226, "name": "CC02"}]}},
               {"key": "1044", "dropdownSettings": {"items": [{"key": 9002, "name": "France"}]}}],
}
# Monday 2026-11-23 12:52 UTC = 07:52 ET -> period Mon Nov 16 .. Sun Nov 22 (ET)
NOW = datetime(2026, 11, 23, 12, 52, tzinfo=timezone.utc)

def box(key, created, stage, origin=9230, recv=None):
    return {"boxKey": key, "name": key, "stageKey": stage, "creationTimestamp": ms(created),
            "lastEmailReceivedTimestamp": ms(recv) if recv else None,
            "fields": {"1003": origin, "1044": 9002}}

def D(d, h=15): return datetime(2026, 11, d, h, 0, tzinfo=timezone.utc)

def test_period_ends_yesterday_et():
    s, e, first = w.report_period(NOW)
    assert first.isoformat() == "2026-11-16"
    assert e == datetime(2026, 11, 23, 5, 0, tzinfo=timezone.utc)   # midnight ET Monday
    assert (e - s).days == 7

def test_subject_idempotency_and_task_number():
    r = w.build_report(PIPE, [], NOW, "✅ ok")
    assert r["subject"] == "[30] E2 weekly report — Nov 23: 0 new companies, 0 intros, 0 replies"
    assert r["idem"] == "e2-weekly-30-2026-11-23"
    assert "Task #30" in r["html"] and "Task #30" in r["text"]

def test_kpis_and_boundaries():
    boxes = [
        box("a", D(16), "5002"),                         # in period, intro
        box("b", D(17), "5001"),                         # linkedin only
        box("c", D(22, 4), "5010", recv=D(22, 20)),      # created 23:00 ET Nov 21 -> in, scheduled + replied
        box("old", D(10), "5003", recv=D(18)),           # old box, reply in period, scheduled-or-later
        box("today", D(23, 12), "5002"),                 # Monday, outside period
        box("other", D(17), "5002", origin=9226),        # CC02, ignored
    ]
    r = w.build_report(PIPE, boxes, NOW, "✅ ok")
    k = r["kpi"]
    assert k["new"] == 3 and k["intros"] == 2 and k["linkedin_only"] == 1
    assert k["replies"] == 2
    assert k["scheduled"] == 2          # stage 3 (c) and 4 (old); later stages count
    assert "other" not in r["html"] and "today" not in [x["name"] for x in r["week"]]

def test_bounce_excluded_from_replies():
    boxes = [box("a", D(16), "5002", recv=D(18))]
    r = w.build_report(PIPE, boxes, NOW, "✅ ok", comments_fn=lambda b: True)
    assert r["kpi"]["replies"] == 0 and r["kpi"]["bounces"] == 1

def test_problems_flag_target_and_health():
    r = w.build_report(PIPE, [], NOW, "❌ collector stale")
    assert any("Objective missed" in p for p in r["problems"])
    assert any("collector stale" in p for p in r["problems"])
    assert "No new company on" in " ".join(r["problems"])

def test_recipient_defaults():
    assert w.REPORT_TO == ["report@gershonconsulting.com"]
    assert "reports@gershon.ai" in w.REPORT_FROM
