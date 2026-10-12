// Plain-English labels and formatting shared by every page.

export const EVENT_TYPES = {
  login_success: { label: "Successful login", help: "Someone signed in to the computer." },
  login_failure: {
    label: "Failed login",
    help: "Someone tried to sign in with a wrong password. A few are normal typos; many in a row can mean password guessing.",
  },
  account_lockout: {
    label: "Account locked out",
    help: "Windows locked an account after too many wrong passwords.",
  },
  account_created: { label: "Account created", help: "A new user account was added to the computer." },
  admin_group_added: {
    label: "Admin rights granted",
    help: "An account was given administrator (full control) access.",
  },
};

export const RULES = {
  brute_force: "Password-guessing attack",
  admin_added: "New administrator",
  off_hours_login: "After-hours login",
  agent_offline: "Computer stopped reporting",
};

// Severity uses the reserved status colors, and is always shown with an icon + word.
export const SEVERITY = {
  high: { label: "High", color: "var(--sv-critical)", icon: "▲" },
  medium: { label: "Medium", color: "var(--sv-serious)", icon: "◆" },
  low: { label: "Low", color: "var(--sv-warning)", icon: "●" },
  info: { label: "Info", color: "var(--sv-neutral)", icon: "○" },
};

export const ALERT_STATUS = {
  open: "Open",
  acknowledged: "Investigating",
  resolved: "Resolved",
};

export const AGENT_STATUS = {
  online: { label: "Online", color: "var(--sv-good)", icon: "●" },
  offline: { label: "Offline", color: "var(--sv-critical)", icon: "▲" },
  never_reported: { label: "Waiting for first report", color: "var(--sv-neutral)", icon: "○" },
  revoked: { label: "Revoked", color: "var(--sv-neutral)", icon: "✕" },
};

const LOGON_TYPES = {
  2: "At the keyboard",
  3: "Over the network",
  7: "Unlocked screen",
  10: "Remote Desktop",
  11: "Cached credentials",
  ssh: "SSH",
};

export function logonLabel(type) {
  if (!type) return "";
  return LOGON_TYPES[type] || `Type ${type}`;
}

export function eventLabel(type) {
  return EVENT_TYPES[type]?.label || type;
}

export function ruleLabel(rule) {
  return RULES[rule] || rule;
}

export function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function timeAgo(value, now = Date.now()) {
  if (!value) return "never";
  const seconds = Math.round((now - new Date(value).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (minutes < 60 * 24) return `${hours} hr ago`;
  const days = Math.floor(minutes / 60 / 24); // 38 hours is "1 day ago", not 2
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return formatDateTime(value);
}

export function formatNumber(n) {
  return (n ?? 0).toLocaleString();
}

export const RANGES = [
  { hours: 24, label: "Last 24 hours" },
  { hours: 24 * 7, label: "Last 7 days" },
  { hours: 24 * 30, label: "Last 30 days" },
  { hours: 24 * 90, label: "Last 90 days" },
];

// Short axis label for a chart bucket: "3 PM" for hourly buckets, "Oct 12" for daily.
export function bucketLabel(value, bucket) {
  const d = new Date(value);
  return bucket === "hour"
    ? d.toLocaleTimeString(undefined, { hour: "numeric" })
    : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Turn a filter object into a query string, dropping empty values.
export function toQuery(params) {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value !== null && value !== undefined && value !== false) qs.set(key, value);
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// <input type="datetime-local"> gives local time without a zone; send it as UTC.
export function localInputToIso(value) {
  return value ? new Date(value).toISOString() : "";
}
