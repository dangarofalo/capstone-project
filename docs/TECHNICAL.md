# SentinelView Technical Documentation

**Contents**

1. [Architecture](#architecture)
2. [Components](#components)
3. [Database design](#database-design)
4. [API reference](#api-reference)
5. [Detection rules](#detection-rules)
6. [Security design](#security-design)
7. [Configuration](#configuration)
8. [Deployment](#deployment)
9. [Development](#development)
10. [Known limitations](#known-limitations)

---

## Architecture

```
 Monitored computers (1..n)            SentinelView server                         Users
┌─────────────────────────┐          ┌───────────────────────────────────────┐   ┌───────────┐
│ sentinel_agent.py       │  HTTPS   │ Caddy (TLS, HTTP→HTTPS)               │   │ Browser   │
│  collectors/windows.py ─┼─────────▶│   │                                   │◀──┤ (React    │
│   (wevtutil, Security)  │ X-API-Key│   ▼                                   │   │ dashboard)│
│  collectors/linux.py    │  JSON    │ FastAPI (uvicorn)                     │   └───────────┘
│   (auth.log)            │          │  /api/ingest  ─▶ detection.py ─▶ alerts│     Bearer JWT
│  agent_state.json       │          │  /api/*  (JWT, roles)                  │
└─────────────────────────┘          │  /       (built React app)            │
                                     │  background: offline-agent check       │
                                     │  notifications.py ─▶ SMTP (optional)   │
                                     │        │                               │
                                     │        ▼                               │
                                     │ PostgreSQL 17 (prod) / SQLite (dev)    │
                                     └───────────────────────────────────────┘
```

**Data flow**

1. Every 30 s the agent reads new security events since its checkpoint, normalizes them, and
   POSTs them in batches of ≤500 to `/api/ingest/events` with its API key.
2. The server authenticates the key, drops events it already has (`agent_id + record_id`),
   assigns severity, stores the rest, and runs the event detection rules in the same
   transaction. An empty batch is a heartbeat.
3. The agent saves its checkpoint only after the server confirms, so a network outage never
   loses events and resends are harmless.
4. A background task checks every 60 s for agents that have gone quiet.
5. New alerts at or above the email severity threshold are emailed after the response is sent.
6. The dashboard calls the REST API with a JWT and refreshes every 30 s.

**Technology choices**

| Layer | Technology | Why |
|---|---|---|
| Agent | Python 3 standard library | Nothing to install on monitored machines |
| API | FastAPI, Pydantic v2, SQLAlchemy 2 | Validation and OpenAPI docs built in; type-checked models |
| Database | PostgreSQL 17 (production), SQLite (development) | Same code for both through SQLAlchemy |
| Auth | PyJWT (HS256), PBKDF2-SHA256 (stdlib) | Standard, auditable, few dependencies |
| Reports | fpdf2 | Pure-Python PDF generation |
| Dashboard | React 19, React Router 7, Vite 8, Tailwind CSS 4, Chart.js 4 | Modern, fast builds, small runtime |
| Deployment | Docker multi-stage build, Docker Compose, Caddy 2 | One command; automatic HTTPS certificates |

## Components

### Agent (`agent/`)

| File | Purpose |
|---|---|
| `sentinel_agent.py` | Main loop: collect → send in batches → commit checkpoint; retry on errors |
| `collectors/windows.py` | Queries the Security log with `wevtutil` (XPath on event ID and record ID), parses the XML, and filters noise (service logons, computer accounts, local logons) |
| `collectors/linux.py` | Tails `auth.log` / `secure` by byte offset; handles log rotation (inode change) and half-written lines |
| `collectors/state.py` | Atomic JSON checkpoint file (write temp file, then rename) |

Windows events collected: 4624 (logon), 4625 (failed logon), 4720 (account created),
4728/4732/4756 (member added to a group; kept only for admin groups), 4740 (lockout).

### Server (`backend/app/`)

| Module | Purpose |
|---|---|
| `main.py` | App setup, routers, security headers, offline-agent task, first-admin bootstrap, serves the dashboard |
| `config.py` | All settings from environment variables |
| `database.py` | Engine, sessions, table creation, column upgrades for older databases |
| `models.py` | Tables: `Agent`, `Event`, `Alert`, `alert_events`, `User` |
| `schemas.py` | Request/response validation; all times serialized as UTC with `Z` |
| `security.py` | Agent API keys; user JWTs; `get_current_user` and `require_admin` dependencies |
| `passwords.py` | PBKDF2-SHA256 hashing (600,000 iterations) and password rules |
| `detection.py` | The four detection rules |
| `notifications.py` | SMTP email for new alerts |
| `exports.py` | Streaming CSV with formula-injection protection |
| `manage.py` | Command-line admin tool (users, agents) |
| `routers/` | `auth`, `users`, `agents`, `ingest`, `events`, `alerts`, `stats`, `reports` |

### Dashboard (`frontend/src/`)

| Path | Purpose |
|---|---|
| `main.jsx` | Routes; `RequireAuth` / `RequireAdmin` guards |
| `lib/api.js` | Fetch wrapper: adds the token, signs out on 401, file downloads |
| `lib/auth.jsx` | Sign-in state (React context) |
| `lib/format.js` | Plain-English labels, date formatting, query strings |
| `components/` | Layout (sidebar / mobile menu), shared UI, `EventsChart` |
| `pages/` | Login, Overview, Alerts, AlertDetail, Events, Computers, Users, Reports, Account |

The chart palette (blue, orange, aqua) was checked with a color-vision-deficiency validator in
both light and dark mode. Severity and status always use an icon and a word, never color alone.
Every chart has a "View as table" alternative.

## Database design

```
users                      agents                     events
─────                      ──────                     ──────
id PK                      id PK                ┌──── id PK
username UNIQUE            name UNIQUE          │     agent_id FK → agents.id
password_hash              api_key_hash UNIQUE  │     record_id          ┐ UNIQUE together
role (admin|viewer)        hostname             │     host               (de-duplication)
is_active                  os                   │     event_time  INDEX
created_at                 created_at           │     received_at
last_login                 last_seen            │     event_type  INDEX
                           revoked_at           │     severity    INDEX
                                                │     username    INDEX
alerts                     alert_events         │     source_ip   INDEX
──────                     ────────────         │     logon_type
id PK ◀────────────────── alert_id FK           │     source_event_id
rule INDEX                 event_id FK ─────────┘     message
severity INDEX
status INDEX (open|acknowledged|resolved)
title, description, recommendation
dedup_key INDEX     ← groups an ongoing attack into one alert
host, username, source_ip, agent_id FK
event_count, first_seen, last_seen, created_at, updated_at
acknowledged_at, acknowledged_by, resolved_at, resolved_by, resolution_note
```

- All times are stored as UTC without a time zone and sent to clients with a `Z` suffix.
- Only a SHA-256 hash of each agent key and a PBKDF2 hash of each password is stored.
- Tables are created on startup. Columns added after a table first shipped are added with
  `ALTER TABLE` by `database.add_missing_columns()`, so databases from earlier stages upgrade
  in place without losing data.

## API reference

Interactive documentation with request/response schemas: `/docs` on a running server.

| Method & path | Who | Purpose |
|---|---|---|
| `POST /api/auth/login` | anyone | `{username, password}` → `{access_token, expires_in, user}` |
| `GET /api/auth/me` | signed in | Current user |
| `POST /api/auth/change-password` | signed in | Change own password; returns a new token |
| `GET /api/users` | admin | List users |
| `POST /api/users` | admin | Create user `{username, password, role}` |
| `PATCH /api/users/{id}` | admin | Change `role`, `is_active`, or `password` |
| `DELETE /api/users/{id}` | admin | Delete user |
| `GET /api/agents` | signed in | Computers with computed `status` |
| `POST /api/agents` | admin | Add computer `{name}` → `{agent, api_key}` (key shown once) |
| `POST /api/agents/{id}/rotate-key` | admin | New key (old stops working; also un-revokes) |
| `POST /api/agents/{id}/revoke` | admin | Block the computer |
| `POST /api/ingest/events` | agent (`X-API-Key`) | `{hostname, os, events[]}` → `{accepted, duplicates, alerts_created}` |
| `GET /api/events` | signed in | Filters: `q`, `host`, `username`, `source_ip`, `event_type`, `severity`, `start`, `end`; `limit` ≤500, `offset` |
| `GET /api/events/export.csv` | signed in | Same filters, up to 100,000 rows |
| `GET /api/alerts` | signed in | Filters: `status`, `active`, `severity`, `rule`, `host`; paging |
| `GET /api/alerts/summary` | signed in | Counts by status and active severity |
| `GET /api/alerts/{id}` | signed in | Alert with up to 100 related events |
| `POST /api/alerts/{id}/acknowledge` | admin | Mark investigating |
| `POST /api/alerts/{id}/resolve` | admin | Resolve, optional `{note}` |
| `GET /api/alerts/export.csv` | signed in | Alert history |
| `GET /api/stats/overview?hours=` | signed in | Everything the overview page shows |
| `GET /api/reports/summary.pdf?hours=` | signed in | PDF security summary |
| `GET /api/health` | anyone | Liveness check |

Errors use standard status codes with a JSON `detail` message: 401 not signed in or bad key,
403 not an admin, 404 not found, 409 conflict (duplicate name, already resolved), 422
validation, 429 sign-in lockout.

## Detection rules

Implemented in `backend/app/detection.py`. Event rules run inside the ingest transaction.

| Rule | Severity | Logic | Grouping |
|---|---|---|---|
| `brute_force` | high | ≥ `BRUTE_FORCE_THRESHOLD` (5) `login_failure` events on one host from one IP (or for one username if no IP) with event times inside `BRUTE_FORCE_WINDOW_MINUTES` (5) | One active alert per host+IP (or host+user); later attempts are attached to it |
| `admin_added` | high | Any `admin_group_added` event | One alert per event |
| `off_hours_login` | medium | `login_success` with logon type 2, 7, 10, 11, or ssh, outside `WORK_HOURS_START`–`WORK_HOURS_END` in `TIMEZONE` | One alert per event |
| `agent_offline` | medium | `last_seen` older than `AGENT_OFFLINE_MINUTES` (10), checked every `OFFLINE_CHECK_SECONDS` | One active alert per agent; auto-resolves when the agent reports again |

Network logons (type 3) are excluded from the after-hours rule because file shares and printers
produce them constantly.

## Security design

| Threat | Control |
|---|---|
| Stolen dashboard password guessed online | Per-username lockout after 5 failures for 5 minutes; same error message and similar timing for unknown usernames |
| Password database leaked | PBKDF2-SHA256, 600,000 iterations, random salt per password; minimum 10 characters mixing letters with numbers or symbols |
| Session token stolen | Tokens expire after 8 hours; changing a password or disabling a user invalidates existing tokens immediately (token carries a password fingerprint; user reloaded on every request) |
| Viewer tries to change data | `require_admin` on every write endpoint; tested |
| Admin locks everyone out | Can't demote, disable, or delete yourself; at least one active admin is enforced |
| Fake agent sends events | 256-bit random API key per computer; only its SHA-256 hash is stored; revocable and rotatable |
| Agent downplays an attack | The server, not the agent, assigns severity |
| Malformed or oversized input | Pydantic validation on every field; batch ≤500 events; IPs validated |
| SQL injection | SQLAlchemy parameterized queries only |
| XSS | React escapes output; Content-Security-Policy `default-src 'self'`; no inline scripts |
| Clickjacking / MIME sniffing | `X-Frame-Options: DENY`, `frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` |
| Attacker-controlled usernames in CSV exports run as formulas | Cells starting with `= + - @` are prefixed with `'` |
| Eavesdropping | HTTPS through Caddy with HSTS; agents verify certificates (optional private CA via `ca_file`) |
| Container compromise | App runs as a non-root user; database is not exposed outside the Docker network |

## Configuration

All settings are environment variables (see `backend/app/config.py` and `.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `SENTINEL_DATABASE_URL` | SQLite file in `backend/` | e.g. `postgresql+psycopg://user:pass@host:5432/db` |
| `SENTINEL_SECRET_KEY` | generated into `backend/.secret_key` | Signs login tokens. **Set explicitly in production.** |
| `SENTINEL_TOKEN_EXPIRE_MINUTES` | 480 | Session length |
| `SENTINEL_LOGIN_MAX_FAILURES` / `_LOCKOUT_MINUTES` | 5 / 5 | Sign-in lockout |
| `SENTINEL_ADMIN_USERNAME` / `_PASSWORD` | — | Creates the first admin if there are no users |
| `SENTINEL_BRUTE_FORCE_THRESHOLD` / `_WINDOW_MINUTES` | 5 / 5 | Brute-force rule |
| `SENTINEL_WORK_HOURS_START` / `_END` | 7 / 19 | Business hours |
| `SENTINEL_TIMEZONE` | server's zone | IANA name, e.g. `America/New_York` |
| `SENTINEL_AGENT_OFFLINE_MINUTES` | 10 | Offline threshold |
| `SENTINEL_OFFLINE_CHECK_SECONDS` | 60 | Offline check interval |
| `SENTINEL_SMTP_HOST`, `_PORT`, `_USER`, `_PASSWORD`, `_STARTTLS`, `_FROM` | — / 587 / … | Outgoing mail (Gmail needs an app password) |
| `SENTINEL_ALERT_EMAIL_TO` | — | Recipients, comma-separated; email is off if empty |
| `SENTINEL_EMAIL_MIN_SEVERITY` | high | Lowest severity that is emailed |
| `SENTINEL_FRONTEND_DIST` | `frontend/dist` | Built dashboard location |

Agent settings (`agent/config.json`): `server_url`, `api_key`, `source` (`windows`|`linux`),
`interval_seconds`, `initial_lookback_hours`, `state_file`, `linux_log_path`, `ca_file`.

## Deployment

### Docker Compose (recommended)

```bash
cp .env.example .env
# Fill in POSTGRES_PASSWORD (letters/digits), SENTINEL_SECRET_KEY, SENTINEL_ADMIN_PASSWORD,
# SENTINEL_DOMAIN, SENTINEL_TIMEZONE
docker compose up -d --build
docker compose logs -f app        # watch startup
```

Services: `db` (PostgreSQL, data in the `pgdata` volume), `app` (SentinelView, not exposed
directly), `caddy` (ports 80/443, certificates in `caddy_data`).

**HTTPS certificates**

- **Public domain** pointing at the server, with ports 80/443 reachable: Caddy gets a free
  Let's Encrypt certificate automatically. Agents need no extra setup.
- **`localhost` or a LAN name**: Caddy issues a certificate from its own local authority.
  Browsers show a warning until you trust it. For agents, copy the root certificate out and set
  `ca_file` in each agent's `config.json`:
  ```bash
  docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./sentinelview-root.crt
  ```

**Backups**

```bash
docker compose exec db pg_dump -U sentinel sentinelview > sentinelview-backup.sql
# restore:
docker compose exec -T db psql -U sentinel sentinelview < sentinelview-backup.sql
```

**Updating**: `git pull`, then `docker compose up -d --build`. New columns are added
automatically on startup.

### Without Docker

Build the dashboard (`npm run build` in `frontend/`), set the environment variables, and run
`uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/` behind a reverse proxy
that provides HTTPS (Caddy, nginx, IIS). Run it as a service (systemd, NSSM, or Task Scheduler).

## Development

- Backend: `cd backend && ../.venv/Scripts/python.exe -m uvicorn app.main:app --reload`
- Dashboard with hot reload: `cd frontend && npm run dev` → http://localhost:5173 (proxies
  `/api` to port 8000)
- Fake data: create a computer, then `python scripts/simulate_events.py --api-key ... --scenario all`
- Tests: see the README; results in [TEST_RESULTS.md](TEST_RESULTS.md)

## Known limitations

| Limitation | Impact | Possible future work |
|---|---|---|
| The Docker/PostgreSQL/Caddy deployment was written but not run during development (Docker was not installed on the development PC); all testing used SQLite | A Postgres-specific issue could appear on first deployment | Run `docker compose up` on a test server; add PostgreSQL to automated tests |
| Sign-in lockout counters are kept in memory | Reset when the server restarts; not shared across multiple server instances | Store in the database or Redis |
| Dashboard session token is kept in browser `localStorage` | A successful XSS attack could read it (mitigated by CSP and React escaping) | HttpOnly cookie sessions with CSRF protection |
| Agent must run as Administrator / root and needs Python installed | Extra setup per computer | Package as a Windows service / MSI with an embedded Python |
| Agent API key is stored in plain text in `config.json` | Anyone with admin access to that computer can read it | Windows DPAPI / Credential Manager |
| Detection covers four rules and five event types | Other attack types (malware, lateral movement, data exfiltration) aren't detected | More event IDs (4688 process creation, 1102 log cleared), anomaly detection |
| After-hours rule uses one business-hours setting for everyone | Shift workers create false alarms | Per-user or per-computer schedules, allow-lists |
| No automatic data retention | The events table grows indefinitely | Configurable retention / archival job |
| Statistics are calculated by reading rows in Python | Slower above a few hundred thousand events per range | Database-side aggregation or summary tables |
| Linux collector reads one log file; Windows collector reads only the Security log | Sysmon, PowerShell, and application logs are ignored | Additional collectors |
| No multi-tenant support | One installation serves one organization | Organization field on every table |
