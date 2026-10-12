import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertStatusBadge, Card, ErrorBanner, Loading, Modal, PageHeader, SeverityBadge } from "../components/ui.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { RULES, eventLabel, formatDateTime, logonLabel } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

function Fact({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 text-sm">{children || "—"}</dd>
    </div>
  );
}

export default function AlertDetail() {
  const { id } = useParams();
  const { isAdmin } = useAuth();
  const { data: alert, error, reload } = useApi(`/api/alerts/${id}`);
  const [resolving, setResolving] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);

  async function act(path, body) {
    setBusy(true);
    setActionError(null);
    try {
      await api.post(`/api/alerts/${id}/${path}`, body);
      setResolving(false);
      setNote("");
      await reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorBanner error={error} />;
  if (!alert) return <Loading />;
  const active = alert.status !== "resolved";

  return (
    <>
      <Link to="/alerts" className="no-print mb-3 inline-block text-sm text-accent hover:underline">← All alerts</Link>
      <PageHeader
        title={alert.title}
        actions={
          isAdmin && active && (
            <>
              {alert.status === "open" && (
                <button className="btn-secondary" disabled={busy} onClick={() => act("acknowledge")}>
                  I'm investigating
                </button>
              )}
              <button className="btn-primary" disabled={busy} onClick={() => setResolving(true)}>
                Mark resolved
              </button>
            </>
          )
        }
      />
      <ErrorBanner error={actionError} />
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <SeverityBadge severity={alert.severity} />
        <AlertStatusBadge status={alert.status} />
        <span className="text-sm text-muted">{RULES[alert.rule]}</span>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="What happened">
            <p className="leading-relaxed">{alert.description}</p>
          </Card>
          <div className="card border-l-4 p-5" style={{ borderLeftColor: "var(--sv-accent)" }}>
            <h2 className="mb-2 font-semibold">What to do</h2>
            <p className="leading-relaxed">{alert.recommendation}</p>
          </div>
          {alert.events.length > 0 && (
            <Card
              title="Events behind this alert"
              subtitle={alert.event_count > alert.events.length ? `Latest ${alert.events.length} of ${alert.event_count}` : undefined}
            >
              <div className="-mx-4 overflow-x-auto sm:mx-0">
                <table className="w-full min-w-[560px] text-sm">
                  <thead className="text-left text-ink-2">
                    <tr className="border-b border-line">
                      <th className="px-3 py-2 font-medium">Time</th>
                      <th className="px-3 py-2 font-medium">Event</th>
                      <th className="px-3 py-2 font-medium">Account</th>
                      <th className="px-3 py-2 font-medium">From</th>
                    </tr>
                  </thead>
                  <tbody>
                    {alert.events.map((e) => (
                      <tr key={e.id} className="border-b border-line last:border-0">
                        <td className="tabular whitespace-nowrap px-3 py-2">{formatDateTime(e.event_time)}</td>
                        <td className="px-3 py-2">
                          {eventLabel(e.event_type)}
                          {e.logon_type && <div className="text-xs text-muted">{logonLabel(e.logon_type)}</div>}
                        </td>
                        <td className="px-3 py-2">{e.username || "—"}</td>
                        <td className="tabular px-3 py-2">{e.source_ip || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>

        <Card title="Details">
          <dl className="space-y-3">
            <Fact label="Computer">
              {alert.host && <Link className="text-accent hover:underline" to={`/events?host=${encodeURIComponent(alert.host)}`}>{alert.host}</Link>}
            </Fact>
            <Fact label="Account">{alert.username}</Fact>
            <Fact label="Source IP">
              {alert.source_ip && <Link className="text-accent hover:underline" to={`/events?source_ip=${encodeURIComponent(alert.source_ip)}`}>{alert.source_ip}</Link>}
            </Fact>
            <Fact label="First seen">{formatDateTime(alert.first_seen)}</Fact>
            <Fact label="Last seen">{formatDateTime(alert.last_seen)}</Fact>
            <Fact label="Related events">{String(alert.event_count)}</Fact>
            {alert.acknowledged_at && (
              <Fact label="Investigation started">
                {formatDateTime(alert.acknowledged_at)}{alert.acknowledged_by && ` by ${alert.acknowledged_by}`}
              </Fact>
            )}
            {alert.resolved_at && (
              <Fact label="Resolved">
                {formatDateTime(alert.resolved_at)}{alert.resolved_by && ` by ${alert.resolved_by}`}
              </Fact>
            )}
            {alert.resolution_note && <Fact label="Resolution note">{alert.resolution_note}</Fact>}
          </dl>
          {!isAdmin && active && (
            <p className="mt-4 text-xs text-muted">Only administrators can mark alerts as investigating or resolved.</p>
          )}
        </Card>
      </div>

      {resolving && (
        <Modal
          title="Mark alert resolved"
          onClose={() => setResolving(false)}
          footer={
            <>
              <button className="btn-secondary" onClick={() => setResolving(false)}>Cancel</button>
              <button className="btn-primary" disabled={busy} onClick={() => act("resolve", { note: note.trim() || null })}>
                Resolve alert
              </button>
            </>
          }
        >
          <label className="block text-sm">
            <span className="mb-1 block font-medium">What did you find or do? (optional)</span>
            <textarea
              className="field min-h-24"
              maxLength={1000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Blocked the IP at the firewall and reset the password."
            />
          </label>
          <p className="mt-2 text-xs text-muted">The note is saved with the alert for future reference.</p>
        </Modal>
      )}
    </>
  );
}
