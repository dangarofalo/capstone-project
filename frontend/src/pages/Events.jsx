import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, EmptyState, ErrorBanner, Loading, PageHeader, Pagination, Select, SeverityBadge } from "../components/ui.jsx";
import { download } from "../lib/api.js";
import { EVENT_TYPES, formatDateTime, localInputToIso, logonLabel, toQuery } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

const LIMIT = 50;
const FILTER_KEYS = ["q", "event_type", "severity", "host", "username", "source_ip", "start", "end"];

function readFilters(params) {
  return Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) || ""]));
}

// Filters as the API wants them: date inputs are local time, the API expects UTC.
function apiFilters(f) {
  return { ...f, start: localInputToIso(f.start), end: localInputToIso(f.end) };
}

export default function Events() {
  const [params, setParams] = useSearchParams();
  const applied = readFilters(params);
  const offset = Number(params.get("offset") || 0);
  const [draft, setDraft] = useState(applied);
  const [showHelp, setShowHelp] = useState(false);
  const [downloadError, setDownloadError] = useState(null);
  const { data: agents } = useApi("/api/agents");

  // Keep the form in sync when filters change from a link (e.g. clicking an IP on the overview).
  const paramString = params.toString();
  useEffect(() => setDraft(readFilters(new URLSearchParams(paramString))), [paramString]);

  const { data, error, loading } = useApi(`/api/events${toQuery({ ...apiFilters(applied), limit: LIMIT, offset })}`);
  const activeCount = FILTER_KEYS.filter((k) => applied[k]).length;

  const apply = (filters, newOffset = 0) => setParams(toQuery({ ...filters, offset: newOffset || "" }).slice(1));
  const set = (key) => (value) => setDraft((d) => ({ ...d, [key]: value }));

  async function exportCsv() {
    setDownloadError(null);
    try {
      await download(`/api/events/export.csv${toQuery(apiFilters(applied))}`);
    } catch (e) {
      setDownloadError(e);
    }
  }

  return (
    <>
      <PageHeader
        title="Events"
        description="Every security event collected from your computers. Search and filter to investigate."
        actions={
          <>
            <button className="btn-secondary" onClick={() => setShowHelp((v) => !v)}>
              {showHelp ? "Hide" : "What do these mean?"}
            </button>
            <button className="btn-secondary" onClick={exportCsv}>Export CSV</button>
          </>
        }
      />
      <ErrorBanner error={error || downloadError} />

      {showHelp && (
        <Card title="Event types explained" className="mb-6">
          <dl className="grid gap-4 sm:grid-cols-2">
            {Object.entries(EVENT_TYPES).map(([key, t]) => (
              <div key={key}>
                <dt className="font-medium">{t.label}</dt>
                <dd className="text-sm text-ink-2">{t.help}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      <Card className="mb-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            apply(draft);
          }}
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <label className="block text-sm sm:col-span-2">
              <span className="mb-1 block text-ink-2">Search</span>
              <input className="field" type="search" placeholder="Username, IP address, computer, or message" value={draft.q} onChange={(e) => set("q")(e.target.value)} />
            </label>
            <Select label="Event type" value={draft.event_type} onChange={set("event_type")}
              options={[["", "Any type"], ...Object.entries(EVENT_TYPES).map(([k, t]) => [k, t.label])]} />
            <Select label="Severity" value={draft.severity} onChange={set("severity")}
              options={[["", "Any severity"], ["high", "High"], ["medium", "Medium"], ["low", "Low"], ["info", "Info"]]} />
            <Select label="Computer" value={draft.host} onChange={set("host")}
              options={[["", "All computers"], ...[...new Set((agents || []).map((a) => a.hostname).filter(Boolean))].map((h) => [h, h]),
                ...(draft.host && !(agents || []).some((a) => a.hostname === draft.host) ? [[draft.host, draft.host]] : [])]} />
            <label className="block text-sm">
              <span className="mb-1 block text-ink-2">Exact username</span>
              <input className="field" value={draft.username} onChange={(e) => set("username")(e.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-2">From (date & time)</span>
              <input className="field" type="datetime-local" value={draft.start} onChange={(e) => set("start")(e.target.value)} />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-ink-2">To (date & time)</span>
              <input className="field" type="datetime-local" value={draft.end} onChange={(e) => set("end")(e.target.value)} />
            </label>
          </div>
          {draft.source_ip && (
            <div className="mt-3 text-sm text-ink-2">
              Source IP: <span className="font-medium text-ink">{draft.source_ip}</span>{" "}
              <button type="button" className="text-accent hover:underline" onClick={() => set("source_ip")("")}>remove</button>
            </div>
          )}
          <div className="mt-4 flex gap-2">
            <button className="btn-primary">Apply filters</button>
            {activeCount > 0 && (
              <button type="button" className="btn-secondary" onClick={() => apply({})}>
                Clear {activeCount} filter{activeCount === 1 ? "" : "s"}
              </button>
            )}
          </div>
        </form>
      </Card>

      <Card>
        {loading && !data ? (
          <Loading />
        ) : data?.items.length === 0 ? (
          <EmptyState title="No events found">
            {activeCount ? "Try removing some filters." : "Events appear here once a computer's agent starts reporting."}
          </EmptyState>
        ) : (
          <>
            <div className="-mx-4 overflow-x-auto sm:mx-0">
              <table className="w-full min-w-[800px] text-sm">
                <thead className="text-left text-ink-2">
                  <tr className="border-b border-line">
                    <th className="px-3 py-2 font-medium">Time</th>
                    <th className="px-3 py-2 font-medium">Event</th>
                    <th className="px-3 py-2 font-medium">Severity</th>
                    <th className="px-3 py-2 font-medium">Computer</th>
                    <th className="px-3 py-2 font-medium">Account</th>
                    <th className="px-3 py-2 font-medium">Source IP</th>
                    <th className="px-3 py-2 font-medium">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((e) => (
                    <tr key={e.id} className="border-b border-line align-top last:border-0 hover:bg-hover">
                      <td className="tabular whitespace-nowrap px-3 py-2">{formatDateTime(e.event_time)}</td>
                      <td className="px-3 py-2">
                        {EVENT_TYPES[e.event_type]?.label || e.event_type}
                        {e.logon_type && <div className="text-xs text-muted">{logonLabel(e.logon_type)}</div>}
                      </td>
                      <td className="px-3 py-2"><SeverityBadge severity={e.severity} /></td>
                      <td className="px-3 py-2">{e.host}</td>
                      <td className="px-3 py-2">{e.username || "—"}</td>
                      <td className="tabular px-3 py-2">{e.source_ip || "—"}</td>
                      <td className="max-w-xs px-3 py-2 text-ink-2">{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={(o) => apply(applied, o)} />
          </>
        )}
      </Card>
    </>
  );
}
