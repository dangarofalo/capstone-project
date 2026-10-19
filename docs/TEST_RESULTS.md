# SentinelView Test Results

**Date:** October 12, 2026 · **Version:** 1.0.0
**Environment:** Windows 11, Python 3.12.10, Node.js 24.19, SQLite database

## Summary

| Suite | Tests | Passed | Failed |
|---|---:|---:|---:|
| Backend (pytest) | 69 | 69 | 0 |
| Agent (pytest) | 11 | 11 | 0 |
| Dashboard (Vitest) | 11 | 11 | 0 |
| **Total automated** | **91** | **91** | **0** |
| Manual end-to-end checks | 17 | 17 | 0 |

Re-run with the commands in the [README](../README.md#tests).

## Automated tests

### Backend: 69 tests

| File | Tests | What it covers |
|---|---:|---|
| `test_ingest.py` | 8 | Health check; agent API-key rejection; storing events; server-assigned severity; duplicate resends ignored; heartbeat; invalid IPs; unknown event types rejected; filters and paging |
| `test_detection.py` | 20 | Brute force: 4 failures no alert, 5 alert, spread-out failures ignored, ongoing attack updates one alert, new alert after resolve, separate IPs, password spraying, no-IP grouping. Admin-added alert. After-hours: 3 AM remote login, business hours and network logins ignored, time zone setting. Offline agent: alert, no duplicates, auto-resolve, never-reported agents ignored. Alert API: detail, acknowledge → resolve, 409 on repeat, 404, filters, summary. Email: only high alerts and only when configured; message contents |
| `test_auth.py` | 15 | Sign-in returns a working token; case-insensitive username; same error for wrong password and unknown user; lockout after 5 failures; disabled user's token stops working; every data endpoint requires sign-in (3 kinds of bad credentials); expired token; token signed with another key; password change signs out old sessions; password checks; viewer can read everything; viewer can't change anything |
| `test_users_agents.py` | 13 | Create/list/delete users; new user can sign in; duplicate and weak passwords rejected; role change and password reset; admins can't lock themselves out; demoting other admins; 404s. Add computer → key works → status Online; duplicate and invalid names; Offline status; revoke blocks the key, new key restores; upgrading a Stage 1 database adds new columns without losing data |
| `test_stats_exports.py` | 13 | Overview totals, top lists, and agent counts; hourly and daily timeline buckets; daily buckets follow the business time zone; active alert counts; CSV export respects filters; CSV formula injection neutralized; text search; alert CSV; acknowledge/resolve records who did it; PDF report (with non-Latin characters and with no data); security headers; unknown API paths return 404 JSON |

### Agent: 11 tests

| File | Tests | What it covers |
|---|---:|---|
| `test_windows_parser.py` | 5 | Failed logon parsing (7-digit timestamps); noise filtering (service logons, computer accounts, local logons, non-admin groups) while still advancing the checkpoint; interactive logon and admin-group add; `-` IP becomes empty; query uses checkpoint or look-back |
| `test_linux_parser.py` | 6 | ISO and classic syslog timestamps; failed and accepted SSH logins; useradd and sudo-group add; unrelated lines ignored; only complete new lines read; uncommitted events are collected again |

### Dashboard: 11 tests

`format.test.js`: plain-English labels and fallbacks; "time ago" wording, including rounding
(38 hours shows as "1 day ago"); query-string building drops empty filters; local date input
converts to UTC.

## Manual end-to-end tests

Performed in a browser against the production build served by FastAPI, using a demo database
seeded with three simulated computers (normal activity plus brute-force, privilege-escalation,
and after-hours scenarios).

| # | Test | Expected | Result |
|---|---|---|---|
| 1 | Start server with `SENTINEL_ADMIN_*` set and an empty database | First admin created | Pass |
| 2 | Visit `/` while signed out | Redirect to sign-in page | Pass |
| 3 | Sign in as admin | Overview loads, no console errors | Pass |
| 4 | Overview numbers | Match seeded data (3 open alerts, 2 high; 16 failed logins; 3 of 4 computers online) | Pass |
| 5 | Activity chart, dark mode | Stacked bars, legend, readable axes | Pass |
| 6 | Light mode at phone width (375 px) | Mobile menu, stacked tiles, no sideways scrolling | Pass |
| 7 | Open brute-force alert | Description, recommendation, 15 related events | Pass |
| 8 | Click "I'm investigating" | Status shows Investigating, records name and time | Pass |
| 9 | Mark resolved with a note | Status Resolved; note saved | Pass |
| 10 | Add a computer | One-time key dialog with ready-to-copy config | Pass |
| 11 | Overview IP link → Events | Events page pre-filtered to that IP and failed logins | Pass |
| 12 | Users page | Lists users; own account can't be demoted or deleted | Pass |
| 13 | Deep link `/alerts/1` loaded directly | Dashboard handles the route | Pass |
| 14 | PDF report | 2 pages: summary tiles, chart, alert and event tables, computer status | Pass (two layout bugs found and fixed: leftover table fill color, justified text) |
| 15 | Simulator `normal` scenario | 0 alerts (no false positives) | Pass |
| 16 | Upgrade the Stage 1–2 development database | New columns and users table added; existing data kept | Pass |
| 17 | Windows agent without Administrator rights | Clear "Run as Administrator" message, exit code 1 | Pass |

## Issues found and fixed during testing

| Issue | Found by | Fix |
|---|---|---|
| Agent crashed on `config.json` saved with a byte-order mark (Notepad/PowerShell) | Stage 1 end-to-end run | Read config and state as `utf-8-sig` |
| New-administrator alert ran two sentences together | Stage 2 live run | Punctuation fix plus a regression test |
| API times had no time zone, so browsers would show UTC as local time | Code review in Stage 4 | All API times now end in `Z`; test added |
| CSV export streamed after the database session closed | Code review | Rows loaded before streaming |
| PDF tables had a stray fill color and justified text | Visual check of the PDF | Reset fill color; left-aligned cells |
| "2 days ago" shown for 38-hour-old alerts | Visual check of the overview | Days now round down; test added |
| Usernames like `=HYPERLINK(...)` would run as formulas in Excel | Security review | Formula prefixes neutralized; test added |
| 7- and 30-day charts labeled each day one day early (days were split at UTC midnight, 8 PM in New York) | Screenshots for the final presentation | Days now split at local midnight in the business time zone; test added |

## Not tested

- **Docker Compose deployment with PostgreSQL and Caddy.** Docker isn't installed on the
  development PC. The SQL is written through SQLAlchemy and avoids database-specific features,
  but the first real deployment should be treated as its test.
- **Real Windows Security log collection** ran only up to the permission check. Parsing was
  tested with sample event XML in the same format `wevtutil` produces.
- **Email delivery** was tested against a fake SMTP server, not a real mailbox.
- **Linux agent** was tested with sample log files on Windows, not on a Linux machine.
