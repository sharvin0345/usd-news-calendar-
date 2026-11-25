#!/usr/bin/env python3
"""Build the USD news JSON and the iPhone calendar feed.

This week comes from the Forex Factory weekly JSON export (no API key).
That host does not publish next week: ff_calendar_nextweek.json returns 404.
When next week is missing, it is filled from TradingView's public economic
calendar, also with no API key. Rows are never invented. If a fetch fails,
events already saved from that source are kept.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "data" / "events.json"
ICS_PATH = ROOT / "usd-news.ics"

FF_THIS_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
FF_NEXT_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.json"
TV_URL = "https://economic-calendar.tradingview.com/events"

SITE_URL = "https://sharvin0345.github.io/usd-news-calendar-/"
UID_DOMAIN = "sharvin0345.github.io"

SOURCE_FF = "Forex Factory"
SOURCE_TV = "TradingView"

NY = ZoneInfo("America/New_York")
MYT = ZoneInfo("Asia/Kuala_Lumpur")
UTC = timezone.utc

# Minutes from midnight, and the label shown on the site.
SESSIONS = (
    (15 * 60 + 30, "3:30 PM"),
    (21 * 60 + 30, "9:30 PM"),
)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

TV_EXCLUDE = re.compile(
    r"\b(auction|bill|mortgage|usda|ethanol)\b"
    r"|rig count|truck sales|car sales|baker hughes|bid-to-cover|allotted",
    re.IGNORECASE,
)
TV_INCLUDE = re.compile(
    r"\b(pmi|ism|confidence|sentiment|claims?|adp|payrolls?|unemployment|"
    r"employment|jolts|cpi|ppi|pce|gdp|fomc|fed|federal|powell|durable|"
    r"factory|housing|beige|philly|empire|chicago|richmond|earnings|"
    r"inflation|michigan)\b"
    r"|retail sales|home sales|building permits|trade balance|"
    r"industrial production|interest rate|consumer credit|dallas fed|"
    r"new home|existing home|pending home",
    re.IGNORECASE,
)
PERCENT_HINT = re.compile(
    r"\b(mom|yoy|qoq|rate|inflation)\b|price index|m/m|y/y|q/q",
    re.IGNORECASE,
)
JOBS_K = re.compile(
    r"non-farm|nonfarm|payroll|jobless|claims",
    re.IGNORECASE,
)


@dataclass
class Fetch:
    name: str
    url: str
    ok: bool
    payload: object = None
    error: str | None = None


def utc_stamp(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def ics_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")


def parse_dt(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value}")
    return dt


def week_start_myt(now: datetime) -> datetime:
    """Sunday 00:00 Malaysia time of the week that contains `now`."""
    local = now.astimezone(MYT)
    days = (local.weekday() + 1) % 7
    return local.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)


def in_window(starts_at: str, now: datetime) -> bool:
    start = week_start_myt(now)
    end = start + timedelta(days=14)
    dt = parse_dt(starts_at).astimezone(MYT)
    return start <= dt < end


def saturday_of(d: date) -> date:
    sunday = d - timedelta(days=(d.weekday() + 1) % 7)
    return sunday + timedelta(days=6)


def format_time_myt(dt: datetime) -> str:
    hour = dt.hour
    suffix = "AM" if hour < 12 else "PM"
    clock = hour % 12 or 12
    return f"{clock}:{dt.minute:02d} {suffix}"


def near_sessions(dt: datetime) -> list[str]:
    minutes = dt.hour * 60 + dt.minute
    labels = []
    for session, label in SESSIONS:
        delta = abs(minutes - session)
        delta = min(delta, 24 * 60 - delta)
        if delta <= 30:
            labels.append(label)
    return labels


def canonical_key(title: str) -> str:
    text = title.lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    drop = {
        "prelim",
        "preliminary",
        "flash",
        "final",
        "advanced",
        "adv",
        "estimate",
        "est",
        "2nd",
        "second",
        "3rd",
        "third",
        "revised",
        "mom",
        "yoy",
        "qoq",
    }
    words = [word for word in text.split() if word not in drop]
    return " ".join(words)


def stable_uid(ny_date: date, title: str) -> str:
    key = canonical_key(title)
    digest = hashlib.sha256(f"USD|{ny_date.isoformat()}|{key}".encode()).hexdigest()[:16]
    return f"usd-{ny_date.strftime('%Y%m%d')}-{digest}@{UID_DOMAIN}"


def gold_note(title: str, impact: str) -> str:
    text = title.lower()
    if impact == "Holiday" or "bank holiday" in text or text.strip() == "holiday":
        return (
            "US holiday: liquidity is thin and spreads can be wide, "
            "so standing aside is the safer choice."
        )
    if any(
        key in text
        for key in (
            "federal funds",
            "interest rate",
            "rate decision",
            "fomc statement",
            "fomc minutes",
            "fomc meeting",
        )
    ) or text.startswith("fomc"):
        return (
            "A hawkish Fed or higher rates usually pushes gold down. "
            "A cut or a dovish tone usually supports gold."
        )
    if "powell" in text or ("speak" in text and any(key in text for key in ("fomc", "fed", "chair"))):
        return (
            "Speeches can move gold fast. Hawkish words usually push gold down. "
            "Dovish words usually support it. If you are new, stay flat."
        )
    if any(key in text for key in ("jobless", "claims")):
        return (
            "More people out of work usually weakens the dollar and can lift gold. "
            "Fewer claims usually push gold down."
        )
    if "unemployment rate" in text:
        return (
            "A higher unemployment rate usually weakens the dollar and can lift gold. "
            "A lower rate usually pushes gold down."
        )
    if any(key in text for key in ("non-farm", "nonfarm", "payroll", "employment change", "adp")):
        return (
            "More jobs than forecast usually strengthens the dollar and pushes gold down. "
            "A weak jobs number can lift gold."
        )
    if any(key in text for key in ("cpi", "ppi", "pce", "inflation", "price index")):
        return (
            "Hotter inflation usually lifts the dollar and pushes gold down. "
            "A cooler print can support gold."
        )
    if "gdp" in text:
        return (
            "Stronger growth usually lifts the dollar and pushes gold down. "
            "Weaker growth can support gold."
        )
    if any(key in text for key in ("pmi", "ism", "confidence", "sentiment", "retail sales")):
        return (
            "A stronger reading usually lifts the dollar and pushes gold down. "
            "A weaker reading can support gold."
        )
    return (
        "Stronger-than-forecast USD data usually lifts the dollar and pushes gold down. "
        "Weaker data usually does the opposite."
    )


def trim_num(num: float) -> str:
    if float(num).is_integer() and abs(num) < 1e12:
        return str(int(num))
    return f"{float(num):.3f}".rstrip("0").rstrip(".")


def format_number(value: float, title: str) -> str:
    text = trim_num(value)
    if PERCENT_HINT.search(title):
        return text if text.endswith("%") else f"{text}%"
    if JOBS_K.search(title) and abs(float(value)) < 10000:
        return text if text.endswith("K") else f"{text}K"
    if re.search(r"\badp\b", title, re.IGNORECASE) and "employment" in title.lower():
        if abs(float(value)) < 5000:
            return text if text.endswith("K") else f"{text}K"
    return text


def as_display(value: object, title: str) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)):
        return format_number(float(value), title)
    return None


def refresh(event: dict) -> dict:
    start = parse_dt(event["startsAt"])
    title = str(event["title"]).strip()
    impact = event["impact"]
    myt = start.astimezone(MYT)
    ny_date = start.astimezone(NY).date()
    return {
        "id": stable_uid(ny_date, title),
        "title": title,
        "impact": impact,
        "forecast": as_display(event.get("forecast"), title),
        "previous": as_display(event.get("previous"), title),
        "startsAt": utc_stamp(start),
        "dateKey": myt.strftime("%Y-%m-%d"),
        "timeMyt": format_time_myt(myt),
        "nearSessions": [] if impact == "Holiday" else near_sessions(myt),
        "goldNote": gold_note(title, impact),
        "source": event.get("source") or "Saved",
    }


def make_event(
    *,
    title: str,
    impact: str,
    forecast: object,
    previous: object,
    start: datetime,
    source: str,
) -> dict:
    return refresh(
        {
            "title": title,
            "impact": impact,
            "forecast": forecast,
            "previous": previous,
            "startsAt": utc_stamp(start),
            "source": source,
        }
    )


def parse_ff_payload(payload: object) -> list[dict]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("Forex Factory file is empty or not a list")
    events = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        if str(row.get("country", "")).strip().upper() != "USD":
            continue
        impact = {"high": "High", "medium": "Medium", "holiday": "Holiday"}.get(
            str(row.get("impact", "")).strip().lower()
        )
        title = str(row.get("title") or "").strip()
        if not impact or not title:
            continue
        try:
            start = parse_dt(str(row["date"]))
        except (KeyError, TypeError, ValueError):
            continue
        events.append(
            make_event(
                title=title,
                impact=impact,
                forecast=row.get("forecast"),
                previous=row.get("previous"),
                start=start,
                source=SOURCE_FF,
            )
        )
    return events


def tv_rows(payload: object) -> list:
    if isinstance(payload, dict):
        status = payload.get("status")
        if status not in (None, "ok"):
            raise ValueError(f"TradingView status {status}")
        rows = payload.get("result")
    else:
        rows = payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("TradingView file is empty or not a list")
    return rows


def tv_impact(title: str, importance: object) -> str | None:
    if TV_EXCLUDE.search(title):
        return None
    try:
        level = int(importance)
    except (TypeError, ValueError):
        return None
    if level >= 1:
        return "High"
    if level == 0 and TV_INCLUDE.search(title):
        return "Medium"
    return None


def parse_tv_payload(payload: object) -> list[dict]:
    events = []
    for row in tv_rows(payload):
        if not isinstance(row, dict):
            continue
        currency = str(row.get("currency") or "USD").strip().upper()
        country = str(row.get("country") or "US").strip().upper()
        if currency != "USD" and country not in {"US", "USA", "USD"}:
            continue
        title = str(row.get("title") or "").strip()
        impact = tv_impact(title, row.get("importance"))
        if not title or not impact:
            continue
        try:
            start = parse_dt(str(row["date"]))
        except (KeyError, TypeError, ValueError):
            continue
        events.append(
            make_event(
                title=title,
                impact=impact,
                forecast=row.get("forecast"),
                previous=row.get("previous"),
                start=start,
                source=SOURCE_TV,
            )
        )
    return events


def coverage_end_from_payload(payload: object) -> date | None:
    rows = payload if isinstance(payload, list) else []
    dates = []
    for row in rows:
        if not isinstance(row, dict) or "date" not in row:
            continue
        try:
            dates.append(parse_dt(str(row["date"])).astimezone(NY).date())
        except (TypeError, ValueError):
            continue
    if not dates:
        return None
    return saturday_of(max(dates))


def coverage_end_from_events(events: list[dict]) -> date | None:
    dates = []
    for event in events:
        try:
            dates.append(parse_dt(event["startsAt"]).astimezone(NY).date())
        except (KeyError, TypeError, ValueError):
            continue
    if not dates:
        return None
    return saturday_of(max(dates))


def usable_cached(event: object) -> bool:
    return (
        isinstance(event, dict)
        and bool(event.get("id"))
        and bool(str(event.get("title") or "").strip())
        and event.get("impact") in {"High", "Medium", "Holiday"}
        and bool(event.get("startsAt"))
    )


def try_parse(parser, payload) -> list[dict] | None:
    try:
        return parser(payload)
    except (TypeError, ValueError):
        return None


def cached_events(previous: dict | None, source: str, now: datetime) -> list[dict]:
    if not previous or not isinstance(previous.get("events"), list):
        return []
    kept = []
    for event in previous["events"]:
        if not usable_cached(event) or event.get("source") != source:
            continue
        try:
            if not in_window(event["startsAt"], now):
                continue
            kept.append(refresh(event))
        except (KeyError, TypeError, ValueError):
            continue
    return kept


def dedupe_window(events: list[dict], now: datetime) -> list[dict]:
    seen = set()
    kept = []
    for event in events:
        if not in_window(event["startsAt"], now):
            continue
        if event["id"] in seen:
            continue
        seen.add(event["id"])
        kept.append(event)
    kept.sort(key=lambda item: (item["startsAt"], item["title"]))
    return kept


def build_notice(
    *,
    ff_this_fresh: bool,
    ff_next_fresh: bool,
    has_ff: bool,
    has_tv: bool,
    kept_ff_cache: bool,
    kept_tv_cache: bool,
) -> str:
    parts = []
    if ff_this_fresh and ff_next_fresh:
        parts.append("Events are from Forex Factory.")
    elif ff_this_fresh and has_tv and not kept_tv_cache:
        parts.append(
            "This week is from Forex Factory. Next week is from TradingView, "
            "because Forex Factory's free file only covers the current week."
        )
    elif ff_this_fresh and kept_tv_cache:
        parts.append(
            "This week is from Forex Factory. Next week is the last saved copy, "
            "because the live next-week source did not respond."
        )
    elif ff_this_fresh:
        parts.append("Events are from Forex Factory. Next week is not in the free file yet.")
    elif has_tv and not has_ff:
        parts.append("Forex Factory did not respond. These events are from TradingView.")
    elif kept_ff_cache:
        parts.append("Forex Factory did not respond, so the saved copy is still showing.")
    if kept_tv_cache and not (ff_this_fresh and kept_tv_cache):
        parts.append("Next week's events are the last saved copy because the live source did not respond.")
    if kept_ff_cache and ff_this_fresh:
        parts.append("Some earlier Forex Factory rows are from the last saved copy.")
    return " ".join(parts)


def build_document(
    ff_this: Fetch,
    ff_next: Fetch,
    tv: Fetch,
    previous: dict | None,
    now: datetime,
) -> dict | None:
    ff_this_events = try_parse(parse_ff_payload, ff_this.payload) if ff_this.ok else None
    ff_next_events = try_parse(parse_ff_payload, ff_next.payload) if ff_next.ok else None
    tv_events = try_parse(parse_tv_payload, tv.payload) if tv.ok else None

    ff_this_fresh = ff_this_events is not None
    ff_next_fresh = ff_next_events is not None
    tv_fresh = tv_events is not None
    if not (ff_this_fresh or ff_next_fresh or tv_fresh):
        return None

    events: list[dict] = []
    kept_ff_cache = False
    kept_tv_cache = False
    coverage_end: date | None = None

    if ff_this_fresh:
        events.extend(ff_this_events or [])
        coverage_end = coverage_end_from_payload(ff_this.payload)
    else:
        cached = cached_events(previous, SOURCE_FF, now)
        if cached:
            events.extend(cached)
            kept_ff_cache = True
            coverage_end = coverage_end_from_events(cached)

    if ff_next_fresh:
        events.extend(ff_next_events or [])
        next_end = coverage_end_from_payload(ff_next.payload)
        if next_end and (coverage_end is None or next_end > coverage_end):
            coverage_end = next_end

    if tv_fresh and not ff_next_fresh:
        for event in tv_events or []:
            ny_date = parse_dt(event["startsAt"]).astimezone(NY).date()
            if coverage_end is not None and ny_date <= coverage_end:
                continue
            events.append(event)
    elif not tv_fresh and not ff_next_fresh:
        cached_tv = cached_events(previous, SOURCE_TV, now)
        if cached_tv:
            kept_tv_cache = True
            for event in cached_tv:
                ny_date = parse_dt(event["startsAt"]).astimezone(NY).date()
                if coverage_end is not None and ny_date <= coverage_end:
                    continue
                events.append(event)

    events = dedupe_window(events, now)
    has_ff = any(event["source"] == SOURCE_FF for event in events)
    has_tv = any(event["source"] == SOURCE_TV for event in events)
    start = week_start_myt(now)
    end_inclusive = (start + timedelta(days=13)).date()

    def source_row(fetch: Fetch, fresh: bool) -> dict:
        error = None if fresh else fetch.error
        if fetch.ok and not fresh:
            error = error or "payload could not be read"
        return {"name": fetch.name, "url": fetch.url, "ok": fresh, "error": error}

    return {
        "version": 1,
        "generatedAt": utc_stamp(now),
        "timezone": "Asia/Kuala_Lumpur",
        "window": {"start": start.date().isoformat(), "end": end_inclusive.isoformat()},
        "notice": build_notice(
            ff_this_fresh=ff_this_fresh,
            ff_next_fresh=ff_next_fresh,
            has_ff=has_ff,
            has_tv=has_tv,
            kept_ff_cache=kept_ff_cache,
            kept_tv_cache=kept_tv_cache,
        ),
        "sources": [
            source_row(ff_this, ff_this_fresh),
            source_row(ff_next, ff_next_fresh),
            source_row(tv, tv_fresh),
        ],
        "events": events,
    }


def escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def fold(line: str) -> str:
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    chunks = []
    limit = 75
    while len(data) > limit:
        cut = limit
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        if cut <= 0:
            cut = limit
        chunks.append(data[:cut])
        data = data[cut:]
        limit = 74
    chunks.append(data)
    parts = [chunks[0].decode("utf-8")]
    for chunk in chunks[1:]:
        parts.append(" " + chunk.decode("utf-8"))
    return "\r\n".join(parts)


def render_ics(document: dict) -> str:
    generated = parse_dt(document["generatedAt"])
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//sharvin0345//USD News for Gold//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:USD News for Gold (MYT)",
        "X-WR-CALDESC:High-impact USD releases in Malaysia time. Alert 30 minutes before. Not financial advice.",
        "X-WR-TIMEZONE:Asia/Kuala_Lumpur",
        "X-PUBLISHED-TTL:PT6H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Kuala_Lumpur",
        "X-LIC-LOCATION:Asia/Kuala_Lumpur",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0800",
        "TZOFFSETTO:+0800",
        "TZNAME:MYT",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for event in document["events"]:
        if event["impact"] != "High":
            continue
        start = parse_dt(event["startsAt"]).astimezone(MYT)
        end = start + timedelta(minutes=15)
        description = "\n".join(
            [
                f"Time: {event['timeMyt']} Malaysia time",
                "Impact: High",
                f"Forecast: {event['forecast'] or 'n/a'}",
                f"Previous: {event['previous'] or 'n/a'}",
                f"What it means for gold: {event['goldNote']}",
                "No new trades 15-30 minutes before or after this release. Not financial advice.",
            ]
        )
        alarm = f"USD news in 30 minutes: {event['title']}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['id']}",
                f"DTSTAMP:{ics_utc(generated)}",
                f"DTSTART;TZID=Asia/Kuala_Lumpur:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Asia/Kuala_Lumpur:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{escape_text('USD: ' + event['title'])}",
                f"DESCRIPTION:{escape_text(description)}",
                f"LOCATION:{escape_text('Malaysia time')}",
                f"URL:{SITE_URL}",
                "STATUS:CONFIRMED",
                "TRANSP:TRANSPARENT",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{escape_text(alarm)}",
                "TRIGGER:-PT30M",
                "END:VALARM",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


def load_previous(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        return None
    return data


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def fetch_json(name: str, url: str, timeout: int = 25, retries: int = 3) -> Fetch:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }
    if "tradingview.com" in url:
        headers["Origin"] = "https://www.tradingview.com"
        headers["Referer"] = "https://www.tradingview.com/"
    last_error = "request failed"
    for attempt in range(retries):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                body = response.read()
            if status != 200:
                last_error = f"HTTP {status}"
            else:
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    return Fetch(name, url, False, error="invalid JSON")
                return Fetch(name, url, True, payload=payload)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code == 404:
                return Fetch(name, url, False, error=last_error)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = f"network error: {exc.__class__.__name__}"
        if attempt + 1 < retries:
            time.sleep(1.5 * (attempt + 1))
    return Fetch(name, url, False, error=last_error[:200])


def tv_window_url(now: datetime) -> str:
    start = week_start_myt(now) - timedelta(days=1)
    end = week_start_myt(now) + timedelta(days=15)
    start_text = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_text = end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"{TV_URL}?from={start_text}&to={end_text}&countries=US"


def write_outputs(document: dict) -> None:
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    atomic_write(EVENTS_PATH, text.encode("utf-8"))
    atomic_write(ICS_PATH, render_ics(document).encode("utf-8"))


def main() -> int:
    now = datetime.now(UTC)
    previous = load_previous(EVENTS_PATH)
    ff_this = fetch_json("Forex Factory this week", FF_THIS_URL)
    ff_next = fetch_json("Forex Factory next week", FF_NEXT_URL)
    tv = fetch_json("TradingView", tv_window_url(now))
    for fetch in (ff_this, ff_next, tv):
        state = "ok" if fetch.ok else f"FAILED ({fetch.error})"
        print(f"{fetch.name}: {state}")
    try:
        document = build_document(ff_this, ff_next, tv, previous, now)
    except Exception as exc:  # keep the last good files if building blows up
        print(f"Could not build the calendar: {exc}")
        return 0 if previous else 1
    if document is None:
        if previous:
            print("All sources failed. Keeping the last saved calendar.")
            return 0
        print("All sources failed and there is no saved calendar.")
        return 1
    write_outputs(document)
    highs = sum(1 for event in document["events"] if event["impact"] == "High")
    print(
        f"Wrote {len(document['events'])} events "
        f"({highs} high-impact) to {EVENTS_PATH.name} and {ICS_PATH.name}."
    )
    if document["notice"]:
        print(document["notice"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
