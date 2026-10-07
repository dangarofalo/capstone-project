# SentinelView

A lightweight security monitoring and analytics dashboard for small organizations.
IT Capstone project. The proposal is in [docs/](docs/).

SentinelView collects security events (logins, failed logins, new accounts, admin-group changes,
lockouts) from Windows and Linux computers, stores them centrally, and detects
threats, raising alerts written in plain English with clear next steps. A web dashboard
comes in Stage 3.

## How it works

```
 Monitored computer                          SentinelView server
┌──────────────────────┐   HTTPS + API key   ┌────────────────────────────┐
│ sentinel_agent.py    │ ──────────────────▶ │ FastAPI  /api/ingest/events│
│  reads Security log  │   JSON batches      │   validates, de-duplicates │
│  (or Linux auth.log) │                     │   assigns severity         │
└──────────────────────┘                     │ Detection rules → alerts   │
                                             │   (+ optional email)       │
                                             │ SQLite / PostgreSQL        │
                                             │ /api/events, /api/alerts   │
                                             └────────────────────────────┘
```

| Folder | What it is |
|---|---|
| `backend/` | FastAPI server, database models, admin CLI, tests |
| `agent/` | Collection agent (standard-library Python only, nothing to install) |
| `scripts/` | `simulate_events.py` sends fake attack scenarios for testing and demos |
| `docs/` | Proposal and project documents |

## Roadmap

- [x] **Stage 1**: agent → API → database pipeline, agent API keys, event search API, tests
- [x] **Stage 2**: detection rules (brute force, new admin, off-hours login, offline agent), alerts API, email notifications
- [ ] **Stage 3**: React dashboard: charts, search/filter, alert management, CSV/PDF export
- [ ] **Stage 4**: user login with Admin/Viewer roles, PostgreSQL + Docker deployment, HTTPS

## Setup (Windows)

Requires Python 3.12+.

```powershell
cd SentinelView
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 1. Start the server

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interactive API docs: http://127.0.0.1:8000/docs

> Until Stage 4 adds user login, the event and alert endpoints are open, so keep the server bound to
> `127.0.0.1` (the default above).

### 2. Register a computer

In a second terminal:

```powershell
cd backend
..\.venv\Scripts\python.exe -m app.manage create-agent OFFICE-PC-01
```

Copy the printed API key. Only a hash is stored, so the key can't be shown again.

### 3a. Try it with simulated events (no admin needed)

```powershell
..\.venv\Scripts\python.exe ..\scripts\simulate_events.py --api-key sv_YOUR_KEY
```

This sends a normal day of logins plus a brute-force attack, a privilege escalation, and an
off-hours login. Each attack scenario trips one detection rule; `normal` should raise none.
Scenarios: `--scenario normal|brute-force|privilege-escalation|off-hours|all`.

### 3b. Collect real events from this PC

```powershell
cd agent
copy config.example.json config.json   # then paste your API key into config.json
```

Reading the Windows Security log requires Administrator rights, so open PowerShell with
**Run as administrator**, then:

```powershell
cd C:\Users\<you>\Documents\SentinelView\agent
..\.venv\Scripts\python.exe sentinel_agent.py --once   # one pass, then exit
..\.venv\Scripts\python.exe sentinel_agent.py          # keep running (every 30 s)
```

The first run collects the last 24 hours (`initial_lookback_hours`). After that the agent
only sends new events. It saves its place in `agent_state.json` **after** the server confirms
receipt, so nothing is lost if the server is down, and the server ignores any repeats.

For Linux, set `"source": "linux"` in `config.json` and run with `sudo`.

### 4. Look at the data

```powershell
..\.venv\Scripts\python.exe -m app.manage list-agents
```

- All events: http://127.0.0.1:8000/api/events
- Failed logins only: http://127.0.0.1:8000/api/events?event_type=login_failure
- Filters: `host`, `username`, `source_ip`, `event_type`, `severity`, `start`, `end`, `limit`, `offset`
- Alerts: http://127.0.0.1:8000/api/alerts (filters: `status`, `severity`, `rule`, `host`)
- Alert counts: http://127.0.0.1:8000/api/alerts/summary
- One alert and the events behind it: http://127.0.0.1:8000/api/alerts/1

Acknowledge or resolve alerts from the interactive docs at `/docs`, or:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/alerts/1/acknowledge
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/alerts/1/resolve `
  -ContentType application/json -Body '{"note": "Blocked the IP at the firewall"}'
```

## Detection rules

| Rule | Severity | Fires when |
|---|---|---|
| `brute_force` | high | 5+ failed logins from one IP (or to one account, if there's no IP) on one computer within 5 minutes |
| `admin_added` | high | an account is added to Administrators / Domain Admins / sudo / wheel |
| `off_hours_login` | medium | someone logs in at the keyboard, by Remote Desktop, or by SSH outside 7:00–19:00 |
| `agent_offline` | medium | a computer's agent hasn't reported for 10 minutes (resolves itself when it reports again) |

Each alert has a plain-English **description** (what happened and why it matters) and a
**recommendation** (what to do). An ongoing attack updates its existing alert instead of
creating hundreds of new ones. Alerts move from `open` to `acknowledged` to `resolved`.

## Configuration

All settings are optional environment variables. Set them before starting the server, e.g.
`$env:SENTINEL_TIMEZONE = "America/New_York"`.

| Variable | Default | Meaning |
|---|---|---|
| `SENTINEL_DATABASE_URL` | SQLite file in `backend/` | Database connection |
| `SENTINEL_BRUTE_FORCE_THRESHOLD` | `5` | Failed logins that count as an attack |
| `SENTINEL_BRUTE_FORCE_WINDOW_MINUTES` | `5` | ...within this many minutes |
| `SENTINEL_WORK_HOURS_START` / `_END` | `7` / `19` | Business hours (24-hour clock) |
| `SENTINEL_TIMEZONE` | this computer's zone | Time zone for business hours |
| `SENTINEL_AGENT_OFFLINE_MINUTES` | `10` | Silence before an agent counts as offline |
| `SENTINEL_OFFLINE_CHECK_SECONDS` | `60` | How often to check for offline agents |

### Email alerts (optional)

Set these to receive an email for each new alert at or above `SENTINEL_EMAIL_MIN_SEVERITY`
(default `high`). For Gmail, use an [app password](https://support.google.com/accounts/answer/185833),
not your normal password.

| Variable | Example |
|---|---|
| `SENTINEL_SMTP_HOST` | `smtp.gmail.com` |
| `SENTINEL_SMTP_PORT` | `587` |
| `SENTINEL_SMTP_USER` / `SENTINEL_SMTP_PASSWORD` | your SMTP login |
| `SENTINEL_SMTP_FROM` | `sentinelview@yourdomain.com` |
| `SENTINEL_ALERT_EMAIL_TO` | `it@yourdomain.com` (comma-separate several) |

## Events collected

| SentinelView type | Windows event ID | Linux source | Severity |
|---|---|---|---|
| `login_success` | 4624 (interactive, remote, network from another IP) | sshd `Accepted ...` | info |
| `login_failure` | 4625 | sshd `Failed password ...` | low |
| `account_lockout` | 4740 | n/a | medium |
| `account_created` | 4720 | `useradd` | medium |
| `admin_group_added` | 4728 / 4732 / 4756 (admin groups only) | `usermod` to sudo/wheel/admin | high |

Background noise is filtered out on the agent: service logons, computer accounts (`PC01$`),
SYSTEM, and a machine logging on to itself.

## Tests

```powershell
cd backend; ..\.venv\Scripts\python.exe -m pytest
cd ..\agent; ..\.venv\Scripts\python.exe -m pytest
```

## Security notes

- Agents authenticate with a random API key; the server stores only its SHA-256 hash.
- The server, not the agent, decides each event's severity.
- All input is validated (event types, field lengths, IP addresses, batch size ≤ 500).
- Use HTTPS for `server_url` whenever the agent and server are on different machines.
