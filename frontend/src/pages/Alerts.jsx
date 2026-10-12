import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { AlertStatusBadge, Card, EmptyState, ErrorBanner, Loading, PageHeader, Pagination, Select, SeverityBadge } from "../components/ui.jsx";
import { download } from "../lib/api.js";
import { RULES, timeAgo, toQuery } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

const LIMIT = 25;

export default function Alerts() {
  const [params, setParams] = useSearchParams();
  const view = params.get("view") || "active";
  const severity = params.get("severity") || "";
  const rule = params.get("rule") || "";
  const offset = Number(params.get("offset") || 0);
  const [downloadError, setDownloadError] = useState(null);

  const filters = {
    active: view === "active",
    status: view === "resolved" ? "resolved" : "",
    severity,
    rule,
  };
  const { data, error, loading } = useApi(`/api/alerts${toQuery({ ...filters, limit: LIMIT, offset })}`, { refreshMs: 30_000 });

  const update = (changes) => {
    const next = { view, severity, rule, offset: 0, ...changes };
    setParams(toQuery(next).slice(1));
  };

  async function exportCsv() {
    setDownloadError(null);
    try {
      await download(`/api/alerts/export.csv${toQuery(filters)}`);
    } catch (e) {
      setDownloadError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Suspicious activity SentinelView found. Open an alert to see what happened and what to do about it."
        actions={<button className="btn-secondary" onClick={exportCsv}>Export CSV</button>}
      />
      <ErrorBanner error={error || downloadError} />
      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Select
            label="Show"
            value={view}
            onChange={(v) => update({ view: v })}
            options={[["active", "Open & investigating"], ["resolved", "Resolved"], ["all", "All alerts"]]}
          />
          <Select
            label="Severity"
            value={severity}
            onChange={(v) => update({ severity: v })}
            options={[["", "Any severity"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]]}
          />
          <Select
            label="Type"
            value={rule}
            onChange={(v) => update({ rule: v })}
            options={[["", "Any type"], ...Object.entries(RULES)]}
          />
        </div>

        {loading && !data ? (
          <Loading />
        ) : data?.items.length === 0 ? (
          <EmptyState title={view === "active" ? "No open alerts" : "No alerts match these filters"}>
            {view === "active" && "Nothing needs your attention right now."}
          </EmptyState>
        ) : (
          <>
            <div className="-mx-4 overflow-x-auto sm:mx-0">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-left text-ink-2">
                  <tr className="border-b border-line">
                    <th className="px-3 py-2 font-medium">Severity</th>
                    <th className="px-3 py-2 font-medium">Alert</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 text-right font-medium">Events</th>
                    <th className="px-3 py-2 font-medium">Last activity</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((a) => (
                    <tr key={a.id} className="border-b border-line last:border-0 hover:bg-hover">
                      <td className="px-3 py-3"><SeverityBadge severity={a.severity} /></td>
                      <td className="px-3 py-3">
                        <Link to={`/alerts/${a.id}`} className="font-medium hover:underline">{a.title}</Link>
                        <div className="text-xs text-muted">{RULES[a.rule]}</div>
                      </td>
                      <td className="px-3 py-3"><AlertStatusBadge status={a.status} /></td>
                      <td className="tabular px-3 py-3 text-right">{a.event_count}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-ink-2" title={new Date(a.last_seen).toLocaleString()}>{timeAgo(a.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={(o) => update({ offset: o })} />
          </>
        )}
      </Card>
    </>
  );
}
