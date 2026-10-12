import { useState } from "react";
import { Card, ErrorBanner, PageHeader, Select } from "../components/ui.jsx";
import { download } from "../lib/api.js";
import { RANGES, toQuery } from "../lib/format.js";

function DownloadButton({ path, children }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  return (
    <div>
      <ErrorBanner error={error} />
      <button
        className="btn-primary"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setError(null);
          try {
            await download(path);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Preparing…" : children}
      </button>
    </div>
  );
}

export default function Reports() {
  const [hours, setHours] = useState(String(24 * 7));
  const since = new Date(Date.now() - Number(hours) * 3600 * 1000).toISOString();
  const rangeOptions = RANGES.map((r) => [String(r.hours), r.label]);

  return (
    <>
      <PageHeader title="Reports" description="Download summaries to share with managers, auditors, or your cyber-insurance provider." />
      <div className="mb-6 max-w-xs">
        <Select label="Time period" value={hours} onChange={setHours} options={rangeOptions} />
      </div>
      <div className="grid gap-6 md:grid-cols-3">
        <Card title="Security summary (PDF)" subtitle="A printable overview anyone can read.">
          <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-ink-2">
            <li>Headline numbers and an activity chart</li>
            <li>Open alerts and alerts raised in the period</li>
            <li>Most-targeted accounts and attacking addresses</li>
            <li>Status of every monitored computer</li>
          </ul>
          <DownloadButton path={`/api/reports/summary.pdf?hours=${hours}`}>Download PDF</DownloadButton>
        </Card>
        <Card title="All events (CSV)" subtitle="Every event in the period, for Excel or Google Sheets.">
          <p className="mb-4 text-sm text-ink-2">
            To export only certain events, filter them on the Events page and use its Export button.
          </p>
          <DownloadButton path={`/api/events/export.csv${toQuery({ start: since })}`}>Download CSV</DownloadButton>
        </Card>
        <Card title="Alert history (CSV)" subtitle="Every alert, including who resolved it and their notes.">
          <p className="mb-4 text-sm text-ink-2">Useful as an audit trail of how each security issue was handled.</p>
          <DownloadButton path="/api/alerts/export.csv">Download CSV</DownloadButton>
        </Card>
      </div>
    </>
  );
}
