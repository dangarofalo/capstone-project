"""Printable PDF security summary for managers, auditors, or cyber-insurance."""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..detection import ACTIVE_STATUSES, local_time
from ..models import Agent, Alert, User, utcnow
from ..security import get_current_user
from .agents import agent_status
from .stats import overview

router = APIRouter(prefix="/api/reports", tags=["reports"])

NAVY = (31, 56, 100)
GREY = (110, 110, 110)
SERIES_COLORS = [(42, 120, 214), (235, 104, 52), (27, 175, 122)]  # same as the dashboard chart
SEVERITY_COLORS = {"high": (192, 57, 43), "medium": (211, 132, 0), "low": (41, 128, 185), "info": (127, 140, 141)}
TYPE_LABELS = {
    "login_success": "Successful logins",
    "login_failure": "Failed logins",
    "account_lockout": "Account lockouts",
    "account_created": "Accounts created",
    "admin_group_added": "Admin rights granted",
}
RULE_LABELS = {
    "brute_force": "Password-guessing attacks",
    "admin_added": "New administrators",
    "off_hours_login": "After-hours logins",
    "agent_offline": "Computers stopped reporting",
}


def _t(text) -> str:
    """The PDF's built-in fonts only cover Latin-1; replace anything else."""
    return str(text if text is not None else "-").encode("latin-1", "replace").decode("latin-1")


def _when(value: datetime | None) -> str:
    return local_time(value).strftime("%b %d, %Y %I:%M %p") if value else "never"


class Report(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*GREY)
        self.cell(0, 6, "SentinelView Security Report", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="C")

    def section(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*NAVY)
        self.cell(0, 8, _t(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(200, 200, 200)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 10)

    def kpis(self, items: list[tuple[str, int, tuple]]):
        width = (self.w - self.l_margin - self.r_margin - 3 * (len(items) - 1)) / len(items)
        y = self.get_y()
        for i, (label, value, color) in enumerate(items):
            x = self.l_margin + i * (width + 3)
            self.set_fill_color(244, 246, 250)
            self.rect(x, y, width, 20, style="F")
            self.set_xy(x, y + 2)
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*color)
            self.cell(width, 9, f"{value:,}", align="C")
            self.set_xy(x, y + 11)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*GREY)
            self.cell(width, 6, _t(label), align="C")
        self.set_text_color(0, 0, 0)
        self.set_xy(self.l_margin, y + 23)

    def bar_chart(self, labels: list[str], success: list[int], failure: list[int], other: list[int]):
        """Stacked bars in the dashboard's colorblind-safe palette (blue, orange, aqua)."""
        left, top, height = self.l_margin + 8, self.get_y() + 2, 45
        width = self.w - self.r_margin - left
        totals = [s + f + o for s, f, o in zip(success, failure, other)]
        peak = max(totals + [1])
        bar_w = width / max(len(totals), 1)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*GREY)
        self.set_xy(self.l_margin, top - 2)
        self.cell(8, 4, str(peak))
        self.set_xy(self.l_margin, top + height - 3)
        self.cell(8, 4, "0")
        for i, parts in enumerate(zip(success, failure, other)):
            y = top + height
            for count, color in zip(parts, SERIES_COLORS):
                if count:
                    h = height * count / peak
                    y -= h
                    self.set_fill_color(*color)
                    self.rect(left + i * bar_w + bar_w * 0.15, y, bar_w * 0.7, h, style="F")
        step = max(1, len(labels) // 8)
        for i in range(0, len(labels), step):
            self.set_xy(left + i * bar_w - 6, top + height + 1)
            self.cell(bar_w + 12, 4, _t(labels[i]), align="C")
        self.set_text_color(0, 0, 0)
        self.set_y(top + height + 7)
        self.set_font("Helvetica", "", 8)
        for text, color in zip(["Successful logins", "Failed logins", "Account changes & lockouts"], SERIES_COLORS):
            self.set_fill_color(*color)
            self.rect(self.get_x(), self.get_y() + 1.2, 3, 3, style="F")
            self.set_x(self.get_x() + 4)
            self.cell(self.get_string_width(text) + 6, 5, text)
        self.ln(7)
        self.set_font("Helvetica", "", 10)

    def simple_table(self, header: list[str], rows: list[list[str]], widths: tuple, empty: str):
        if not rows:
            self.set_text_color(*GREY)
            self.cell(0, 6, _t(empty), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(0, 0, 0)
            return
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(255, 255, 255)  # the chart legend leaves its color behind
        heading_style = FontFace(emphasis="BOLD", color=NAVY, fill_color=(234, 238, 245))
        with self.table(col_widths=widths, line_height=5.5, headings_style=heading_style,
                        borders_layout="HORIZONTAL_LINES", text_align="LEFT",
                        cell_fill_color=(248, 249, 251), cell_fill_mode="ROWS") as table:
            heading = table.row()
            for h in header:
                heading.cell(_t(h))
            for r in rows:
                row = table.row()
                for value in r:
                    row.cell(_t(value))
        self.set_font("Helvetica", "", 10)


@router.get("/summary.pdf")
def summary_pdf(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24 * 7,
) -> Response:
    stats = overview(db=db, hours=hours)
    period = f"{hours} hours" if hours < 48 else f"{hours // 24} days"

    pdf = Report(format="Letter")
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 10, "Security Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*GREY)
    pdf.cell(0, 5, _t(f"Last {period}: {_when(stats.start)} to {_when(stats.end)} (local time)"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5, _t(f"Generated by {user.username} on {_when(utcnow())}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    t, a = stats.totals, stats.agents
    pdf.kpis([
        ("Security events", t["events"], NAVY),
        ("Failed logins", t["failed_logins"], SEVERITY_COLORS["high"] if t["failed_logins"] else NAVY),
        ("Active alerts", t["active_alerts"], SEVERITY_COLORS["high"] if t["high_alerts"] else NAVY),
        ("Computers online", a["online"], NAVY),
    ])
    pdf.set_font("Helvetica", "", 10)
    verdict = (
        f"{t['high_alerts']} high-severity alert(s) need attention." if t["high_alerts"]
        else "No high-severity alerts are currently open."
    )
    offline = f" {a['offline']} computer(s) are not reporting." if a["offline"] else ""
    pdf.multi_cell(0, 5, _t(f"{verdict}{offline} {a['online']} of {a['total']} monitored computers are online."))

    pdf.section("Activity over time")
    fmt = "%I %p" if stats.timeline.bucket == "hour" else "%b %d"
    labels = [local_time(x).strftime(fmt).lstrip("0") for x in stats.timeline.labels]
    series = stats.timeline.series
    other = [sum(v) for v in zip(*(series[k] for k in series if k not in ("login_success", "login_failure")))]
    pdf.bar_chart(labels, series["login_success"], series["login_failure"], other)

    pdf.section("Open alerts")
    active = db.scalars(
        select(Alert).where(Alert.status.in_(ACTIVE_STATUSES)).order_by(Alert.last_seen.desc()).limit(30)
    ).all()
    pdf.simple_table(
        ["Severity", "Alert", "Computer", "Status", "Last seen"],
        [[x.severity.upper(), x.title, x.host, x.status, _when(x.last_seen)] for x in active],
        (16, 74, 30, 24, 36),
        "No open alerts.",
    )

    pdf.section(f"Alerts raised in the last {period}")
    raised = db.scalars(select(Alert.rule).where(Alert.created_at >= stats.start)).all()
    pdf.simple_table(
        ["Type", "Count"],
        [[RULE_LABELS.get(rule, rule), str(raised.count(rule))] for rule in RULE_LABELS if raised.count(rule)],
        (120, 60),
        "No new alerts in this period.",
    )

    pdf.section("Event breakdown")
    pdf.simple_table(
        ["Event type", "Count"],
        [[TYPE_LABELS.get(k, k), f"{v:,}"] for k, v in sorted(stats.event_type_counts.items(), key=lambda kv: -kv[1])],
        (120, 60),
        "No events in this period.",
    )

    pdf.section("Most-targeted accounts and sources of failed logins")
    rows = []
    for i in range(max(len(stats.top_failed_users), len(stats.top_failed_ips))):
        u = stats.top_failed_users[i] if i < len(stats.top_failed_users) else None
        ip = stats.top_failed_ips[i] if i < len(stats.top_failed_ips) else None
        rows.append([u.name if u else "", str(u.count) if u else "", ip.name if ip else "", str(ip.count) if ip else ""])
    pdf.simple_table(["Account", "Failures", "Source IP", "Failures"], rows, (60, 30, 60, 30), "No failed logins.")

    pdf.section("Monitored computers")
    now = utcnow()
    agents = db.scalars(select(Agent).order_by(Agent.name)).all()
    status_text = {"online": "Online", "offline": "OFFLINE", "never_reported": "Never reported", "revoked": "Revoked"}
    pdf.simple_table(
        ["Name", "Computer", "Status", "Last report"],
        [[x.name, x.hostname or "-", status_text[agent_status(x, now)], _when(x.last_seen)] for x in agents],
        (45, 45, 35, 55),
        "No computers registered yet.",
    )

    filename = f"sentinelview-report-{now:%Y-%m-%d}.pdf"
    return Response(
        bytes(pdf.output()),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
