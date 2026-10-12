import { useState } from "react";
import { Card, ErrorBanner, PageHeader } from "../components/ui.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { formatDateTime } from "../lib/format.js";

export default function Account() {
  const { user, isAdmin, replaceSession } = useAuth();
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setSaved(false);
    if (form.next !== form.confirm) {
      setError(new Error("The new passwords don't match."));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await api.post("/api/auth/change-password", {
        current_password: form.current,
        new_password: form.next,
      });
      replaceSession(response);
      setForm({ current: "", next: "", confirm: "" });
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const field = (key, label, autoComplete) => (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <input className="field" type="password" required autoComplete={autoComplete} value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
    </label>
  );

  return (
    <>
      <PageHeader title="My account" />
      <div className="grid max-w-3xl gap-6 md:grid-cols-2">
        <Card title="Profile">
          <dl className="space-y-3 text-sm">
            <div><dt className="text-muted">Username</dt><dd className="font-medium">{user.username}</dd></div>
            <div><dt className="text-muted">Role</dt><dd>{isAdmin ? "Administrator" : "Viewer (read-only)"}</dd></div>
            <div><dt className="text-muted">Member since</dt><dd>{formatDateTime(user.created_at)}</dd></div>
          </dl>
        </Card>
        <Card title="Change password">
          <form className="space-y-4" onSubmit={submit}>
            <ErrorBanner error={error} />
            {saved && (
              <div role="status" className="rounded-md border border-good/40 bg-good/10 px-3 py-2 text-sm text-good-ink">
                ✓ Password changed. Other devices have been signed out.
              </div>
            )}
            {field("current", "Current password", "current-password")}
            {field("next", "New password", "new-password")}
            {field("confirm", "Repeat new password", "new-password")}
            <p className="text-xs text-muted">At least 10 characters, mixing letters with numbers or symbols.</p>
            <button className="btn-primary" disabled={busy}>Change password</button>
          </form>
        </Card>
      </div>
    </>
  );
}
