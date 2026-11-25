#!/usr/bin/env python3
"""Offline tests for the calendar builder. They do not touch the network."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_calendar as cal  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "ff_thisweek.json"
NOW = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)


def ok_fetch(name, url, payload):
    return cal.Fetch(name, url, True, payload, None)


def bad_fetch(name, url, error="HTTP 404"):
    return cal.Fetch(name, url, False, None, error)


def unfold(text: str) -> str:
    return text.replace("\r\n ", "").replace("\r\n\t", "")


def tv_payload(rows):
    return {"status": "ok", "result": rows, "total": len(rows)}


class CalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ff = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def tv_rows(self):
        return [
            {
                "title": "Fake Extra High",
                "country": "US",
                "currency": "USD",
                "importance": 1,
                "date": "2026-11-25T15:00:00.000Z",
                "forecast": 1,
                "previous": 1,
            },
            {
                "title": "3-Month Bill Auction Bid-to-Cover",
                "country": "US",
                "currency": "USD",
                "importance": 1,
                "date": "2026-12-01T16:30:00.000Z",
                "forecast": None,
                "previous": 2.7,
            },
            {
                "title": "Chicago PMI",
                "country": "US",
                "currency": "USD",
                "importance": 0,
                "date": "2026-11-30T14:45:00.000Z",
                "forecast": 43.2,
                "previous": 55.3,
            },
            {
                "title": "Non Farm Payrolls",
                "country": "US",
                "currency": "USD",
                "importance": 1,
                "date": "2026-12-04T13:30:00.000Z",
                "forecast": 90,
                "previous": 165,
            },
            {
                "title": "EIA Crude Oil Stocks Change",
                "country": "US",
                "currency": "USD",
                "importance": 0,
                "date": "2026-12-02T15:30:00.000Z",
                "forecast": 1.3,
                "previous": 3.4,
            },
        ]

    def build(self, ff_next=None, tv=True, previous=None, ff_this=True):
        return cal.build_document(
            ok_fetch("ff-this", cal.FF_THIS_URL, self.ff) if ff_this else bad_fetch("ff-this", cal.FF_THIS_URL),
            ok_fetch("ff-next", cal.FF_NEXT_URL, ff_next) if ff_next is not None else bad_fetch("ff-next", cal.FF_NEXT_URL),
            ok_fetch("tv", "https://economic-calendar.tradingview.com/events", tv_payload(self.tv_rows()))
            if tv
            else bad_fetch("tv", "https://economic-calendar.tradingview.com/events", "network error"),
            previous,
            NOW,
        )

    def test_week_window_is_sunday_to_saturday_myt(self):
        start = cal.week_start_myt(NOW)
        self.assertEqual(start.date().isoformat(), "2026-11-22")
        self.assertEqual(start.hour, 0)
        self.assertEqual(str(start.tzinfo), "Asia/Kuala_Lumpur")

    def test_session_window_includes_the_half_hour_boundary(self):
        def labels(hour, minute):
            dt = datetime(2026, 11, 25, hour, minute, tzinfo=cal.MYT)
            return cal.near_sessions(dt)

        self.assertEqual(labels(15, 0), ["3:30 PM"])
        self.assertEqual(labels(15, 30), ["3:30 PM"])
        self.assertEqual(labels(16, 0), ["3:30 PM"])
        self.assertEqual(labels(14, 59), [])
        self.assertEqual(labels(16, 1), [])
        self.assertEqual(labels(21, 0), ["9:30 PM"])
        self.assertEqual(labels(21, 30), ["9:30 PM"])
        self.assertEqual(labels(22, 0), ["9:30 PM"])
        self.assertEqual(labels(22, 1), [])

    def test_fixture_keeps_ff_high_and_medium_and_drops_low(self):
        doc = self.build()
        by_title = {event["title"]: event for event in doc["events"]}
        self.assertIn("Core PCE Price Index m/m", by_title)
        self.assertIn("Prelim GDP q/q", by_title)
        self.assertIn("Flash Manufacturing PMI", by_title)
        self.assertIn("CB Consumer Confidence", by_title)
        self.assertIn("Bank Holiday", by_title)
        self.assertNotIn("Unemployment Claims", by_title)
        self.assertNotIn("Durable Goods Orders m/m", by_title)
        self.assertNotIn("Core Retail Sales q/q", by_title)

        pce = by_title["Core PCE Price Index m/m"]
        self.assertEqual(pce["impact"], "High")
        self.assertEqual(pce["source"], "Forex Factory")
        self.assertEqual(pce["forecast"], "0.3%")
        self.assertEqual(pce["previous"], "0.3%")
        self.assertEqual(pce["startsAt"], "2026-11-25T13:30:00Z")
        self.assertEqual(pce["timeMyt"], "9:30 PM")
        self.assertEqual(pce["dateKey"], "2026-11-25")
        self.assertEqual(pce["nearSessions"], ["9:30 PM"])
        self.assertIn("gold", pce["goldNote"].lower())
        self.assertIn("down", pce["goldNote"].lower())

        holiday = by_title["Bank Holiday"]
        self.assertEqual(holiday["nearSessions"], [])
        self.assertEqual(holiday["impact"], "Holiday")

    def test_next_week_from_tradingview_skips_auctions_and_this_week_overlap(self):
        doc = self.build()
        titles = {event["title"] for event in doc["events"]}
        self.assertIn("Non Farm Payrolls", titles)
        self.assertIn("Chicago PMI", titles)
        self.assertNotIn("Fake Extra High", titles)
        self.assertNotIn("3-Month Bill Auction Bid-to-Cover", titles)
        self.assertNotIn("EIA Crude Oil Stocks Change", titles)
        nfp = next(event for event in doc["events"] if event["title"] == "Non Farm Payrolls")
        self.assertEqual(nfp["source"], "TradingView")
        self.assertEqual(nfp["impact"], "High")
        self.assertEqual(nfp["forecast"], "90K")
        self.assertEqual(nfp["previous"], "165K")
        self.assertEqual(nfp["timeMyt"], "9:30 PM")
        self.assertEqual(nfp["nearSessions"], ["9:30 PM"])
        self.assertIn("TradingView", doc["notice"])
        self.assertIn("Forex Factory", doc["notice"])

    def test_ff_next_week_suppresses_tradingview(self):
        ff_next = [
            {
                "title": "Non-Farm Employment Change",
                "country": "USD",
                "date": "2026-12-04T08:30:00-05:00",
                "impact": "High",
                "forecast": "90K",
                "previous": "165K",
            }
        ]
        doc = self.build(ff_next=ff_next)
        payrolls = [event for event in doc["events"] if "payroll" in event["title"].lower() or "Non-Farm" in event["title"]]
        self.assertEqual([event["title"] for event in payrolls], ["Non-Farm Employment Change"])
        self.assertEqual(payrolls[0]["source"], "Forex Factory")
        self.assertEqual(payrolls[0]["forecast"], "90K")
        self.assertNotIn("TradingView", doc["notice"])

    def test_ics_is_high_impact_only_with_myt_and_30_minute_alarm(self):
        doc = self.build()
        ics = cal.render_ics(doc)
        unfolded = unfold(ics)
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertIn("\r\n", ics)
        self.assertIn("TZID:Asia/Kuala_Lumpur", unfolded)
        self.assertIn("DTSTART;TZID=Asia/Kuala_Lumpur:20261125T213000", unfolded)
        self.assertIn("DTSTART;TZID=Asia/Kuala_Lumpur:20261204T213000", unfolded)
        self.assertIn("TRIGGER:-PT30M", unfolded)
        self.assertEqual(unfolded.count("BEGIN:VALARM"), unfolded.count("BEGIN:VEVENT"))
        highs = [event for event in doc["events"] if event["impact"] == "High"]
        self.assertEqual(unfolded.count("BEGIN:VEVENT"), len(highs))
        self.assertIn("USD: Core PCE Price Index m/m", unfolded)
        self.assertIn("USD: Non Farm Payrolls", unfolded)
        self.assertNotIn("Flash Manufacturing", unfolded)
        self.assertNotIn("Bank Holiday", unfolded)
        self.assertNotIn("Chicago PMI", unfolded)
        self.assertNotIn("Bill Auction", unfolded)
        for event in highs:
            self.assertRegex(event["id"], r"^usd-\d{8}-[0-9a-f]{16}@sharvin0345\.github\.io$")
            self.assertIn(f"UID:{event['id']}", unfolded)

    def test_uid_stays_stable_when_the_clock_time_changes(self):
        first = cal.stable_uid(cal.date(2026, 12, 4), "Non Farm Payrolls")
        second = cal.stable_uid(cal.date(2026, 12, 4), "Non Farm Payrolls")
        moved = cal.make_event(
            title="Non Farm Payrolls",
            impact="High",
            forecast=90,
            previous=165,
            start=datetime(2026, 12, 4, 13, 45, tzinfo=timezone.utc),
            source="TradingView",
        )
        original = cal.make_event(
            title="Non Farm Payrolls",
            impact="High",
            forecast=90,
            previous=165,
            start=datetime(2026, 12, 4, 13, 30, tzinfo=timezone.utc),
            source="TradingView",
        )
        self.assertEqual(first, second)
        self.assertEqual(original["id"], moved["id"])

    def test_ics_escapes_commas(self):
        event = cal.make_event(
            title="Retail Sales, Ex Autos",
            impact="High",
            forecast="1,200",
            previous="1,100",
            start=datetime(2026, 12, 4, 13, 30, tzinfo=timezone.utc),
            source="Forex Factory",
        )
        ics = unfold(cal.render_ics({"generatedAt": "2026-11-25T06:00:00Z", "events": [event]}))
        self.assertIn("Retail Sales\\, Ex Autos", ics)
        self.assertIn("1\\,200", ics)

    def test_window_edges(self):
        rows = [
            {
                "title": "Too Early",
                "country": "USD",
                "date": "2026-11-21T08:30:00-05:00",
                "impact": "High",
                "forecast": "1",
                "previous": "1",
            },
            {
                "title": "Week Start",
                "country": "USD",
                "date": "2026-11-21T11:00:00-05:00",
                "impact": "High",
                "forecast": "1",
                "previous": "1",
            },
            {
                "title": "Next Week End",
                "country": "USD",
                "date": "2026-12-05T10:59:00-05:00",
                "impact": "High",
                "forecast": "1",
                "previous": "1",
            },
            {
                "title": "Too Late",
                "country": "USD",
                "date": "2026-12-05T11:00:00-05:00",
                "impact": "High",
                "forecast": "1",
                "previous": "1",
            },
        ]
        # 2026-11-21 11:00 EST = 2026-11-22 00:00 MYT (inside).
        # 2026-12-05 10:59 EST = 2026-12-05 23:59 MYT (inside).
        # 2026-12-05 11:00 EST = 2026-12-06 00:00 MYT (outside).
        doc = cal.build_document(
            ok_fetch("ff-this", cal.FF_THIS_URL, rows),
            bad_fetch("ff-next", cal.FF_NEXT_URL),
            bad_fetch("tv", "https://example.invalid"),
            None,
            NOW,
        )
        titles = {event["title"] for event in doc["events"]}
        self.assertEqual(titles, {"Week Start", "Next Week End"})

    def test_source_failure_keeps_saved_events_and_total_failure_writes_nothing(self):
        fresh = self.build()
        nfp = next(event for event in fresh["events"] if event["title"] == "Non Farm Payrolls")
        previous = {"events": [nfp]}
        kept = self.build(tv=False, previous=previous)
        titles = {event["title"] for event in kept["events"]}
        self.assertIn("Non Farm Payrolls", titles)
        self.assertIn("Core PCE Price Index m/m", titles)
        self.assertIn("saved copy", kept["notice"])

        nothing = self.build(ff_this=False, tv=False, previous=None)
        self.assertIsNone(nothing)
        cached_only = self.build(ff_this=False, tv=False, previous=previous)
        self.assertIsNone(cached_only)

    def test_number_formatting_does_not_invent_units_for_unknown_series(self):
        self.assertEqual(cal.format_number(0.3, "Core PCE Price Index MoM"), "0.3%")
        self.assertEqual(cal.format_number(4.1, "Unemployment Rate"), "4.1%")
        self.assertEqual(cal.format_number(90, "Non Farm Payrolls"), "90K")
        self.assertEqual(cal.format_number(200, "Initial Jobless Claims"), "200K")
        self.assertEqual(cal.format_number(7.523, "JOLTs Job Openings"), "7.523")
        self.assertEqual(cal.format_number(21000, "ADP Employment Change Weekly"), "21000")

    def test_gold_notes_follow_the_release_type(self):
        self.assertIn("inflation", cal.gold_note("Prelim GDP Price Index q/q", "Medium").lower())
        self.assertIn("growth", cal.gold_note("Prelim GDP q/q", "High").lower())
        self.assertIn("jobs", cal.gold_note("Non Farm Payrolls", "High").lower())
        self.assertIn("holiday", cal.gold_note("Bank Holiday", "Holiday").lower())

    def test_two_builds_share_uids(self):
        first = self.build()
        later = cal.build_document(
            ok_fetch("ff-this", cal.FF_THIS_URL, self.ff),
            bad_fetch("ff-next", cal.FF_NEXT_URL),
            ok_fetch("tv", "https://economic-calendar.tradingview.com/events", tv_payload(self.tv_rows())),
            None,
            NOW + timedelta(hours=3),
        )
        self.assertEqual(
            [event["id"] for event in first["events"]],
            [event["id"] for event in later["events"]],
        )


if __name__ == "__main__":
    unittest.main()
