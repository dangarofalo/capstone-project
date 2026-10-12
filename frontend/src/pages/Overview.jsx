import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import EventsChart from "../components/EventsChart.jsx";
import { BarList, Card, EmptyState, ErrorBanner, Loading, PageHeader, SeverityBadge, StatTile } from "../components/ui.jsx";
import { RANGES, timeAgo } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

const REFRESH_MS = 30_000;

export default function Overview() {
  const [hours, setHours] = useState(24);
  const navigate = useNavigate();
  const stats = useApi(`/api/stats/overview?hours=${hours}`, { refreshMs: REFRESH_MS });
  const alerts = useApi("/api/alerts?active=true&limit=6", { refreshMs: REFRESH_MS });
  const s = stats.data;
  const rangeLabel = RANGES.find((r) => r.hours === hours)?.label.toLowerCase();

  // Clicking a name in a top-5 list opens the Events page already filtered to it.
  const showEvents = (filter) => navigate(`/events?event_type=login_failure&${filter}`);

  return (
    <>
      <PageHeader
        title="Security overview"
        description="What has happened on your monitored computers. Updates every 30 seconds."
        actions={
          <div className="flex rounded-md border border-line-strong bg-raised p-0.5" role="group" aria-label="Time range">
            {RANGES.slice(0, 3).map((r) => (
              <button
                key={r.hours}
                type="button"
                onClick={() => setHours(r.hours)}
                aria-pressed={hours === r.hours}
                className={`rounded px-3 py-1.5 text-sm ${hours === r.hours ? "bg-brand text-brand-ink" : "text-ink-2 hover:bg-hover"}`}
              >
                {r.label.replace("Last ", "")}
              </button>
            ))}
          </div>
        }
      />
      <ErrorBanner error={stats.error} />
      {!s ? (
        <Loading />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile
              label="Open alerts"
              value={s.totals.active_alerts}
              tone={s.totals.high_alerts ? "critical" : s.totals.active_alerts ? undefined : "good"}
              hint={s.totals.high_alerts ? `${s.totals.high_alerts} high severity` : "No high-severity alerts"}
            />
            <StatTile label="Failed logins" value={s.totals.failed_logins} hint={rangeLabel} />
            <StatTile label="Security events" value={s.totals.events} hint={rangeLabel} />
            <StatTile
              label="Computers online"
              value={s.agents.online}
              tone={s.agents.offline ? "critical" : undefined}
              hint={s.agents.offline ? `${s.agents.offline} not reporting` : `of ${s.agents.total} monitored`}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card title="Activity over time" subtitle={`Security events, ${rangeLabel}`} className="xl:col-span-2">
              <EventsChart timeline={s.timeline} />
            </Card>

            <Card
              title="Needs attention"
              subtitle="Open and in-progress alerts"
              actions={<Link to="/alerts" className="text-sm text-accent hover:underline">All alerts →</Link>}
            >
              <ErrorBanner error={alerts.error} />
              {alerts.data?.items.length === 0 && (
                <EmptyState title="All clear">No open alerts right now.</EmptyState>
              )}
              <ul className="-mx-2 divide-y divide-line">
                {alerts.data?.items.map((a) => (
                  <li key={a.id}>
                    <Link to={`/alerts/${a.id}`} className="block rounded-md px-2 py-2.5 hover:bg-hover">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-medium leading-snug">{a.title}</span>
                        <SeverityBadge severity={a.severity} />
                      </div>
                      <div className="mt-0.5 text-xs text-muted">{timeAgo(a.last_seen)}</div>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <Card title="Most-targeted accounts" subtitle="Failed logins by username">
              <BarList items={s.top_failed_users} emptyText="No failed logins." onSelect={(name) => showEvents(`username=${encodeURIComponent(name)}`)} />
            </Card>
            <Card title="Top sources of failed logins" subtitle="By IP address">
              <BarList items={s.top_failed_ips} emptyText="No failed logins from a known address." onSelect={(ip) => showEvents(`source_ip=${encodeURIComponent(ip)}`)} />
            </Card>
            <Card title="Busiest computers" subtitle="Security events by computer">
              <BarList items={s.top_hosts} emptyText="No events yet." onSelect={(host) => navigate(`/events?host=${encodeURIComponent(host)}`)} />
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
