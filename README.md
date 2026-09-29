# SentinelView

A lightweight security monitoring and analytics dashboard for small organizations.
IT Capstone project. The proposal is in [docs/](docs/).

SentinelView collects security events (logins, failed logins, new accounts, admin-group changes,
lockouts) from Windows and Linux computers, stores them centrally, and (in later stages) detects
threats and shows them on an easy-to-use web dashboard.

## How it works

```
 Monitored computer                          SentinelView server
┌──────────────────────┐   HTTPS + API key   ┌────────────────────────────┐
│ sentinel_agent.py    │ ──────────────────▶ │ FastAPI  /api/ingest/events│
│  reads Security log  │   JSON batches      │   validates, de-duplicates │
│  (or Linux auth.log) │                     │   assigns severity         │
└──────────────────────┘                     │ SQLite / PostgreSQL        │
                                             │ /api/events  (dashboard)   │
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
- [ ] **Stage 2**: detection rules (brute force, new admin, off-hours login, offline agent) and alerts
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

> Until Stage 4 adds user login, the read endpoints are open, so keep the server bound to
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
off-hours login. Scenarios: `--scenario normal|brute-force|privilege-escalation|off-hours|all`.

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
