# SentinelView

A lightweight security monitoring and analytics dashboard for small organizations.
IT Capstone project.

Small businesses, school labs, and nonprofits rarely have a security team or the budget for
enterprise tools. SentinelView collects security events (logins, failed logins, new accounts,
admin-rights changes, lockouts) from Windows and Linux computers, detects common attacks, and
explains them in plain English on an easy-to-use web dashboard.

**Features**

- **Collection agent** for Windows (Security Event Log) and Linux (`auth.log`), with no installs
  beyond Python
- **Threat detection**: password-guessing attacks, new administrators, after-hours logins, and
  computers that stop reporting
- **Alerts written for non-experts**: what happened, why it matters, and what to do, with an
  investigate → resolve workflow and notes
- **Analytics dashboard**: headline numbers, activity chart, most-targeted accounts, attacking
  IP addresses, busiest computers
- **Search & filter** every event; **export** to CSV; **PDF security report**
- **Email notifications** for high-severity alerts (optional)
- **Secure by design**: user accounts with Admin/Viewer roles, hashed passwords, login lockout,
  per-computer API keys, HTTPS deployment with Docker

| Document | For |
|---|---|
| [User manual](docs/USER_MANUAL.md) | People using the dashboard and installing agents |
| [Technical documentation](docs/TECHNICAL.md) | Architecture, API, database, security, known limitations |
| [Test results](docs/TEST_RESULTS.md) | What was tested and the results |
| [Project proposal](docs/SentinelView_Project_Proposal.docx) | Original proposal |

## How it works

```
 Monitored computers                       SentinelView server                 People
┌────────────────────┐  HTTPS + API key  ┌──────────────────────────────┐   ┌──────────────┐
│ sentinel_agent.py  │ ────────────────▶ │ FastAPI                      │   │ Web browser  │
│  Windows Security  │   JSON batches    │  • ingest + de-duplicate     │◀──│ React        │
│  log / Linux       │   every 30 s      │  • detection rules → alerts  │   │ dashboard    │
│  auth.log          │                   │  • REST API (login required) │   └──────────────┘
└────────────────────┘                   │  • CSV / PDF / email         │
                                         │ PostgreSQL (or SQLite in dev)│
                                         └──────────────────────────────┘
```

| Folder | What it is |
|---|---|
| `backend/` | FastAPI server: API, detection rules, database models, admin CLI, tests |
| `frontend/` | React + Vite + Tailwind CSS + Chart.js dashboard |
| `agent/` | Collection agent (standard-library Python only) |
| `scripts/` | `simulate_events.py` sends realistic fake attacks for testing and demos |
| `deploy/`, `Dockerfile`, `docker-compose.yml` | Production deployment with HTTPS |
| `docs/` | Proposal, user manual, technical documentation, test results |

## Quick start (development, Windows)

Requires Python 3.12+ and Node.js 20.19+.

```powershell
cd SentinelView
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd frontend
npm install
npm run build        # builds the dashboard into frontend\dist
cd ..\backend
```

**Shortcut:** after the steps above, you can just double-click **`create-admin.bat`** (once) and
then **`start-server.bat`** (every time) in the SentinelView folder. Forgot a password? Double-click
**`reset-password.bat`**. The commands below do the same.

**1. Create your admin account** (asks for a password: 10+ characters, letters plus numbers or symbols):

```powershell
..\.venv\Scripts\python.exe -m app.manage create-user YOUR-NAME --role admin
```

**2. Start the server:**

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** and sign in. (API docs: http://127.0.0.1:8000/docs)

**3. Add data.** On the **Computers** page click **Add computer** to get an API key, then either:

- **Simulated attacks** (no admin rights needed):
  ```powershell
  ..\.venv\Scripts\python.exe ..\scripts\simulate_events.py --api-key sv_YOUR_KEY --host DEMO-PC
  ```
- **Real events from this PC:** follow the on-screen instructions, or see the
  [user manual](docs/USER_MANUAL.md#connecting-a-computer).

**Working on the dashboard code?** Run `npm run dev` in `frontend/` for live reloading at
http://localhost:5173 (it forwards API calls to the server on port 8000).

## Production deployment (Docker, HTTPS)

Requires Docker Desktop (Windows/Mac) or Docker Engine (Linux).

```bash
cp .env.example .env     # then fill in passwords, secret key, domain, time zone
docker compose up -d --build
```

This starts PostgreSQL, the SentinelView server, and [Caddy](https://caddyserver.com), which
gets and renews an HTTPS certificate automatically. Open `https://<SENTINEL_DOMAIN>` and sign in
with the admin account from `.env`. Details, backups, and the certificate setup for agents are
in the [technical documentation](docs/TECHNICAL.md#deployment).

## Tests

```powershell
cd backend;  ..\.venv\Scripts\python.exe -m pytest     # API, detection, auth, exports
cd ..\agent; ..\.venv\Scripts\python.exe -m pytest     # log parsers and checkpointing
cd ..\frontend; npm test                               # dashboard formatting logic
```

Results: [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

## Project stages

- [x] **Stage 1**: agent → API → database pipeline, agent API keys, event search API
- [x] **Stage 2**: detection rules, alerts API, email notifications
- [x] **Stage 3**: React dashboard: charts, search/filter, alert management, CSV/PDF export
- [x] **Stage 4**: user login with Admin/Viewer roles, PostgreSQL + Docker deployment, HTTPS
