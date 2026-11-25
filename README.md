# USD news for gold

A phone-friendly list of USD economic releases for a beginner XAUUSD trader in Malaysia, plus a calendar feed that alerts an iPhone 30 minutes before each high-impact number.

Live site: <https://sharvin0345.github.io/usd-news-calendar-/>

Calendar file: <https://sharvin0345.github.io/usd-news-calendar-/usd-news.ics>

Subscribe link: `webcal://sharvin0345.github.io/usd-news-calendar-/usd-news.ics`

Times are Malaysia time (MYT, Asia/Kuala_Lumpur, UTC+8). This is not financial advice.

## Get alerts on iPhone

The feed contains high-impact USD events only. Each event has a 30-minute alarm (`TRIGGER:-PT30M`). Times use the `Asia/Kuala_Lumpur` timezone so the phone shows MYT.

Tap the subscribe link on the phone, or add it by hand:

1. Open Settings.
2. Tap Calendar.
3. Tap Accounts.
4. Tap Add Account.
5. Tap Other.
6. Tap Add Subscribed Calendar.
7. Paste `https://sharvin0345.github.io/usd-news-calendar-/usd-news.ics` (or the `webcal://` link above).
8. Leave Calendar notifications on: Settings → Notifications → Calendar → Allow Notifications.

The feed refreshes on its own. You do not add each event by hand. Medium-impact events stay on the website and are not in the phone calendar.

## What the site shows

- This week and next week.
- Date, Malaysia time, event, impact, forecast, previous, and a one-line note on what it usually means for gold.
- High impact is the default. A button shows medium impact too.
- Cards with a gold edge land at, or within 30 minutes of, the 3:30 PM or 9:30 PM MYT sessions.

## News trading rules

- Do not open a new gold trade from 15 to 30 minutes before a high-impact USD number until 15 to 30 minutes after it.
- Spreads widen when the number comes out. A stop that looked safe can get jumped.
- Learn on a demo account, and use 0.01 lot.
- This is not financial advice. It is a clock and a reminder, not a signal to buy or sell gold.

## Where the numbers come from

The updater reads public files. It does not use an API key, and it does not invent rows.

- This week: [Forex Factory weekly JSON](https://nfs.faireconomy.media/ff_calendar_thisweek.json), filtered to USD. High, medium, and US holidays are kept. Low-impact rows are left out. Forecast and previous are copied as published.
- Next week: `https://nfs.faireconomy.media/ff_calendar_nextweek.json` when that file exists. It currently returns 404, so the job fills the gap from [TradingView's public calendar](https://economic-calendar.tradingview.com/events) (USD only). TradingView importance 1 is shown as high, and importance 0 is shown as medium for major data (jobs, inflation, PMI, Fed, GDP, and similar). Bill auctions, mortgage rates, and similar rows are left out.
- If Forex Factory later publishes the next-week file, that file replaces the TradingView rows.
- If a source fails, the last saved events from that source stay in `data/events.json` and `usd-news.ics`. A bad response does not wipe the site.

Job and claims figures from TradingView are shown with a K when the feed prints them in thousands (90 becomes 90K). Percent prints get a % sign. Other TradingView numbers are shown as returned.

## Updates

GitHub Actions runs [`.github/workflows/update-calendar.yml`](.github/workflows/update-calendar.yml) at 00:15 and 12:15 UTC (8:15 AM and 8:15 PM Malaysia time) and when someone starts the workflow by hand. It fetches the sources, regenerates `data/events.json` and `usd-news.ics`, and commits them when they change.

The workflow needs permission to push that commit. The workflow file sets `contents: write`. If a run fails on the push, the owner also has to set **Settings → Actions → General → Workflow permissions → Read and write permissions**.

## GitHub Pages

The site is the root of `main` (`index.html`, `css/`, `js/`, `data/events.json`, `usd-news.ics`). Pages should deploy from the `main` branch, folder `/ (root)`.

If the site URL above 404s, the owner sets **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` → Folder: `/ (root)` → Save**.

## Local check

```bash
python3 tests/test_update_calendar.py -v
node tests/calendar.test.js
python3 scripts/update_calendar.py
```
