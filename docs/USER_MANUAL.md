# SentinelView User Manual

SentinelView watches the computers in your organization for signs of attack and tells you, in
plain English, what happened and what to do about it. This manual is for the people who use the
dashboard day to day and for whoever installs the agent on each computer.

**Contents**

1. [Signing in](#signing-in)
2. [Roles: Administrator and Viewer](#roles-administrator-and-viewer)
3. [Overview page](#overview-page)
4. [Alerts](#alerts)
5. [Events](#events)
6. [Computers](#computers)
7. [Connecting a computer](#connecting-a-computer)
8. [Reports](#reports)
9. [Users](#users)
10. [My account](#my-account)
11. [Email alerts](#email-alerts)
12. [Troubleshooting](#troubleshooting)

---

## Signing in

Open the SentinelView address your administrator gave you (for example
`https://sentinel.yourcompany.com`, or `http://127.0.0.1:8000` on a test machine) and enter
your username and password.

- After **5 wrong passwords**, sign-in is blocked for that username for **5 minutes**. This
  stops password-guessing attacks against SentinelView itself.
- Sessions last **8 hours**, then you'll be asked to sign in again.
- Forgot your password? An administrator can reset it on the **Users** page.

## Roles: Administrator and Viewer

| | Viewer | Administrator |
|---|:---:|:---:|
| See the overview, alerts, events, computers | ✓ | ✓ |
| Download CSV exports and PDF reports | ✓ | ✓ |
| Mark alerts as investigating or resolved | | ✓ |
| Add computers, replace or revoke their keys | | ✓ |
| Add, disable, and delete users; reset passwords | | ✓ |

Give managers and auditors the **Viewer** role so they can see everything without being able
to change anything.

## Overview page

The first page after signing in. It refreshes itself every 30 seconds.

- **Time range** (top right): 24 hours, 7 days, or 30 days.
- **Open alerts**: alerts nobody has resolved yet. Red means at least one is *high* severity.
- **Failed logins**: wrong-password attempts in the chosen period.
- **Security events**: everything collected in the period.
- **Computers online**: computers whose agent reported in the last 10 minutes. Red means one
  or more have stopped reporting.
- **Activity over time**: a bar chart of successful logins (blue), failed logins (orange), and
  account changes and lockouts (green). Hover over a bar for exact numbers, or click
  **View as table**. A sudden orange spike usually means password guessing.
- **Needs attention**: the most recent open alerts. Click one to open it.
- **Most-targeted accounts / Top sources of failed logins / Busiest computers**: click any
  name to jump to the matching events.

## Alerts

An alert means SentinelView found something suspicious. There are four kinds:

| Alert | Severity | What it means |
|---|---|---|
| **Password-guessing attack** | High | 5 or more failed logins from one address within 5 minutes. A program is probably guessing passwords. |
| **New administrator** | High | An account was given full control of a computer. Attackers do this so they can get back in later. |
| **After-hours login** | Medium | Someone signed in at the keyboard, by Remote Desktop, or by SSH outside business hours (7 AM–7 PM by default). |
| **Computer stopped reporting** | Medium | A computer's agent hasn't checked in for 10 minutes. It may be off, or someone may have stopped the agent. This alert closes itself when the computer reports again. |

Severity is always shown with a symbol *and* a word (▲ High, ◆ Medium, ● Low), so it never
depends on color alone.

**Working an alert**

1. Open the alert from the **Alerts** page or the overview.
2. Read **What happened** and **What to do**. The **Events behind this alert** table lists
   the exact log entries.
3. *(Admins)* Click **I'm investigating** so others know someone is on it. The alert shows
   *Investigating* and records your name and the time.
4. Follow the recommendation.
5. *(Admins)* Click **Mark resolved** and write what you found or did, for example *"Blocked
   203.0.113.45 at the firewall."* The note is saved as an audit trail.

If an attack keeps going, SentinelView adds the new attempts to the same alert instead of
creating hundreds of new ones. If the same attack returns after you resolved it, a new alert
is raised.

Use the **Show / Severity / Type** filters to find older or resolved alerts, and **Export CSV**
to download the list.

## Events

Every security event collected from every computer, newest first.

- **Search** looks in usernames, IP addresses, computer names, and messages.
- **Filters**: event type, severity, computer, exact username, and a date/time range. Click
  **Apply filters**; **Clear filters** removes them all.
- **What do these mean?** explains each event type.
- **Export CSV** downloads exactly the events that match your filters (up to 100,000).
- Use **← Newer / Older →** to page through results.

| Event | Meaning |
|---|---|
| Successful login | Someone signed in. The line underneath says how (at the keyboard, Remote Desktop, over the network, SSH…). |
| Failed login | A sign-in with a wrong password. A few are normal typos; many in a row are not. |
| Account locked out | Windows locked an account after too many wrong passwords. |
| Account created | A new user account was added to the computer. |
| Admin rights granted | An account was added to Administrators (or `sudo` on Linux). |

## Computers

Lists every computer SentinelView watches, with its status:

| Status | Meaning |
|---|---|
| ● Online | Reported within the last 10 minutes |
| ▲ Offline | Hasn't reported for over 10 minutes |
| ○ Waiting for first report | Added, but the agent hasn't connected yet |
| ✕ Revoked | Its key was revoked; it can't send events. Past events are kept. |

*(Admins)* **New key** replaces a computer's key (the old one stops working immediately, which
is useful if a key may have leaked). **Revoke** blocks the computer entirely; **New key**
re-enables it.

## Connecting a computer

You need an administrator account and **Python 3.12 or newer** on the computer being
monitored (from python.org; tick *"Add python.exe to PATH"* during setup).

1. In SentinelView, go to **Computers → Add computer**, type a name (e.g. `FRONT-DESK-PC`), and
   click **Create key**.
2. **Copy the config shown on screen.** The key is only shown once.
3. Copy SentinelView's `agent` folder onto the computer (e.g. to `C:\SentinelView\agent`).
4. In that folder, create a file called `config.json` and paste the config into it.
5. Open **PowerShell as administrator** (right-click PowerShell → *Run as administrator*).
   Windows only lets administrators read the Security log.
6. Run:
   ```powershell
   cd C:\SentinelView\agent
   python sentinel_agent.py
   ```
7. Within 30 seconds the computer shows as **Online**. The first run sends the last 24 hours of
   events.

**Keep the agent running after restarts.** Use Windows Task Scheduler: create a task that runs
*"whether user is logged on or not"* with *"highest privileges"*, triggered *At startup*, with
the action `python.exe` and argument `C:\SentinelView\agent\sentinel_agent.py`, starting in
`C:\SentinelView\agent`.

**Linux computers:** set `"source": "linux"` in `config.json` and run
`sudo python3 sentinel_agent.py` (or create a systemd service).

**HTTPS with a private certificate:** if your server uses `localhost` or a LAN name, Caddy
issues its own certificate. Copy Caddy's root certificate to the computer and set
`"ca_file"` in `config.json` to its path (see the technical documentation, *Deployment*).

## Reports

Choose a **time period**, then download:

- **Security summary (PDF)**: headline numbers, an activity chart, open alerts, alerts raised in
  the period, an event breakdown, the most-targeted accounts and attacking addresses, and the
  status of every computer. Suitable for managers, auditors, and cyber-insurance questionnaires.
- **All events (CSV)**: every event in the period, for Excel or Google Sheets.
- **Alert history (CSV)**: every alert with who handled it and their notes.

## Users

*(Admins only.)* Add people, set their role, reset passwords, disable or delete accounts.

- New users get a temporary password from you. Ask them to change it on **My account**.
- **Disable** blocks someone immediately but keeps their account; **Delete** removes it.
- You can't remove your own admin rights or delete yourself, and SentinelView always keeps at
  least one active administrator, so nobody gets locked out of the system.

## My account

See your role and change your password. Changing your password signs you out on every other
device.

Passwords must be at least 10 characters and mix letters with numbers or symbols.

## Email alerts

If your administrator configured email (see the technical documentation), SentinelView emails
each new **high-severity** alert with what happened and what to do. Open the dashboard to
investigate and resolve it.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Too many failed sign-ins" | Wait 5 minutes, or ask an admin to reset your password. |
| Agent says *"Access denied reading the Security log"* | Run PowerShell **as administrator**. |
| Agent says *"Server rejected the API key"* | The key was mistyped, replaced, or revoked. Create a **New key** and update `config.json`. |
| Agent says *"Could not reach server"* | Check `server_url` in `config.json`, the network, and that the server is running. The agent retries every 30 seconds and doesn't lose events while waiting. |
| Agent fails with a certificate error | Set `ca_file` (see *Connecting a computer*), or use a real domain with a trusted certificate. |
| A computer shows Offline | The computer is off, asleep, disconnected, or the agent was stopped. Restart the agent. |
| Too many after-hours alerts | Ask your administrator to adjust business hours or the time zone. |
| Dashboard says "Can't reach the SentinelView server" | The server is down or your network connection dropped. |
