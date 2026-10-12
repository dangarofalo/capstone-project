import { useEffect, useRef } from "react";
import { AGENT_STATUS, ALERT_STATUS, SEVERITY, formatNumber } from "../lib/format.js";

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-2">{description}</p>}
      </div>
      {actions && <div className="no-print flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

// Color is never the only signal: every badge has an icon and a word.
function Badge({ color, icon, children }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-raised px-2 py-0.5 text-xs font-medium text-ink">
      <span aria-hidden="true" style={{ color }}>
        {icon}
      </span>
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }) {
  const s = SEVERITY[severity] || SEVERITY.info;
  return (
    <Badge color={s.color} icon={s.icon}>
      {s.label}
    </Badge>
  );
}

export function AlertStatusBadge({ status }) {
  const icon = { open: "●", acknowledged: "◐", resolved: "✓" }[status];
  const color = { open: "var(--sv-critical)", acknowledged: "var(--sv-serious)", resolved: "var(--sv-good)" }[status];
  return (
    <Badge color={color} icon={icon}>
      {ALERT_STATUS[status] || status}
    </Badge>
  );
}

export function AgentStatusBadge({ status }) {
  const s = AGENT_STATUS[status] || AGENT_STATUS.never_reported;
  return (
    <Badge color={s.color} icon={s.icon}>
      {s.label}
    </Badge>
  );
}

export function StatTile({ label, value, hint, tone }) {
  const color = tone === "critical" ? "text-critical-ink" : tone === "good" ? "text-good-ink" : "text-ink";
  return (
    <div className="card p-4">
      <div className="text-sm text-ink-2">{label}</div>
      <div className={`mt-1 text-3xl font-semibold ${color}`}>{formatNumber(value)}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={`card p-4 sm:p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="font-semibold">{title}</h2>}
            {subtitle && <p className="text-sm text-ink-2">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function ErrorBanner({ error }) {
  if (!error) return null;
  return (
    <div role="alert" className="mb-4 rounded-md border border-critical/40 bg-critical/10 px-4 py-3 text-sm text-critical-ink">
      <span aria-hidden="true">▲ </span>
      {error.message || String(error)}
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return <div className="py-10 text-center text-sm text-muted">{label}</div>;
}

export function EmptyState({ title, children }) {
  return (
    <div className="rounded-lg border border-dashed border-line-strong px-6 py-10 text-center">
      <div className="font-medium">{title}</div>
      {children && <div className="mt-1 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Pagination({ total, limit, offset, onChange }) {
  if (total <= limit) return <div className="mt-3 text-sm text-muted">{formatNumber(total)} total</div>;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="mt-3 flex items-center justify-between gap-2 text-sm">
      <span className="text-muted">
        {formatNumber(offset + 1)}–{formatNumber(Math.min(offset + limit, total))} of {formatNumber(total)}
      </span>
      <div className="flex gap-2">
        <button className="btn-secondary" disabled={page === 1} onClick={() => onChange(offset - limit)}>
          ← Newer
        </button>
        <button className="btn-secondary" disabled={page === pages} onClick={() => onChange(offset + limit)}>
          Older →
        </button>
      </div>
    </div>
  );
}

export function Modal({ title, onClose, children, footer }) {
  const dialog = useRef(null);
  useEffect(() => {
    const el = dialog.current;
    el?.showModal();
    return () => el?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40"
    >
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-lg font-semibold">{title}</h2>
      </div>
      <div className="px-5 py-4">{children}</div>
      {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
    </dialog>
  );
}

// Horizontal bars with the name and number always written out (no color-only reading).
export function BarList({ items, emptyText, onSelect }) {
  if (!items?.length) return <p className="py-4 text-sm text-muted">{emptyText}</p>;
  const max = Math.max(...items.map((i) => i.count));
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.name}>
          <button
            type="button"
            onClick={onSelect ? () => onSelect(item.name) : undefined}
            disabled={!onSelect}
            className="group w-full rounded-md px-1 py-0.5 text-left enabled:hover:bg-hover"
            title={onSelect ? `Show events for ${item.name}` : undefined}
          >
            <div className="flex justify-between gap-3 text-sm">
              <span className="truncate font-medium">{item.name}</span>
              <span className="tabular text-ink-2">{formatNumber(item.count)}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-line">
              <div
                className="h-1.5 rounded-full"
                style={{ width: `${Math.max(2, (item.count / max) * 100)}%`, background: "var(--sv-series-2)" }}
              />
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function Select({ label, value, onChange, options, className = "" }) {
  return (
    <label className={`block text-sm ${className}`}>
      <span className="mb-1 block text-ink-2">{label}</span>
      <select className="field" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}
