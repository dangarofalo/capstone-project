import { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth.jsx";

export default function Login() {
  const { user, login } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={location.state?.from || "/"} replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(err.message);
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <svg viewBox="0 0 32 32" className="mb-3 h-12 w-12" aria-hidden="true">
            <path d="M16 2 4 7v8c0 7.5 5.1 13.4 12 15 6.9-1.6 12-7.5 12-15V7z" fill="var(--sv-brand)" />
            <path d="m11 16 3.5 3.5L21.5 12" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <h1 className="text-2xl font-semibold">SentinelView</h1>
          <p className="mt-1 text-sm text-ink-2">Security monitoring for your organization</p>
        </div>
        <form onSubmit={submit} className="card space-y-4 p-6">
          {error && (
            <div role="alert" className="rounded-md border border-critical/40 bg-critical/10 px-3 py-2 text-sm text-critical-ink">
              {error}
            </div>
          )}
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Username</span>
            <input className="field" autoComplete="username" autoFocus required value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block font-medium">Password</span>
            <input className="field" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          <button className="btn-primary w-full" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-center text-xs text-muted">
          Forgot your password? Ask your SentinelView administrator to reset it.
        </p>
      </div>
    </div>
  );
}
