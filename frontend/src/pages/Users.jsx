import { useState } from "react";
import { Card, ErrorBanner, Loading, Modal, PageHeader, Select } from "../components/ui.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { timeAgo } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

const ROLE_HELP = {
  admin: "Administrator: can resolve alerts and manage computers and users.",
  viewer: "Viewer: can see dashboards, events, alerts, and reports, but can't change anything.",
};

function PasswordField({ value, onChange, label = "Password" }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium">{label}</span>
      <input className="field" type="password" autoComplete="new-password" required minLength={10} value={value} onChange={(e) => onChange(e.target.value)} />
      <span className="mt-1 block text-xs text-muted">At least 10 characters, mixing letters with numbers or symbols.</span>
    </label>
  );
}

export default function Users() {
  const { user: me } = useAuth();
  const { data: users, error, reload } = useApi("/api/users");
  const [modal, setModal] = useState(null); // {type: "add"|"reset"|"delete", user?}
  const [form, setForm] = useState({ username: "", password: "", role: "viewer" });
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(promise, close = true) {
    setBusy(true);
    setActionError(null);
    try {
      await promise;
      if (close) setModal(null);
      await reload();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  }

  const open = (type, user) => {
    setActionError(null);
    setForm({ username: "", password: "", role: "viewer" });
    setModal({ type, user });
  };

  return (
    <>
      <PageHeader
        title="Users"
        description="People who can sign in to SentinelView."
        actions={<button className="btn-primary" onClick={() => open("add")}>+ Add user</button>}
      />
      <ErrorBanner error={error || (!modal && actionError)} />
      <Card>
        {!users ? (
          <Loading />
        ) : (
          <div className="-mx-4 overflow-x-auto sm:mx-0">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-ink-2">
                <tr className="border-b border-line">
                  <th className="px-3 py-2 font-medium">Username</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Last sign-in</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isMe = u.id === me.id;
                  return (
                    <tr key={u.id} className="border-b border-line last:border-0">
                      <td className="px-3 py-3">
                        <span className="font-medium">{u.username}</span>
                        {isMe && <span className="ml-2 text-xs text-muted">(you)</span>}
                        {!u.is_active && <span className="ml-2 rounded bg-hover px-1.5 py-0.5 text-xs text-ink-2">Disabled</span>}
                      </td>
                      <td className="px-3 py-3">
                        <select
                          className="field w-auto py-1"
                          value={u.role}
                          disabled={isMe || busy}
                          title={isMe ? "You can't change your own role" : undefined}
                          onChange={(e) => run(api.patch(`/api/users/${u.id}`, { role: e.target.value }), false)}
                          aria-label={`Role for ${u.username}`}
                        >
                          <option value="admin">Administrator</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </td>
                      <td className="px-3 py-3 text-ink-2">{timeAgo(u.last_login)}</td>
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <button className="btn-secondary px-2 py-1 text-xs" onClick={() => open("reset", u)}>Reset password</button>{" "}
                        {!isMe && (
                          <>
                            <button className="btn-secondary px-2 py-1 text-xs" disabled={busy}
                              onClick={() => run(api.patch(`/api/users/${u.id}`, { is_active: !u.is_active }), false)}>
                              {u.is_active ? "Disable" : "Enable"}
                            </button>{" "}
                            <button className="btn-danger px-2 py-1 text-xs" onClick={() => open("delete", u)}>Delete</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Roles" className="mt-6">
        <ul className="space-y-1 text-sm text-ink-2">
          <li>{ROLE_HELP.admin}</li>
          <li>{ROLE_HELP.viewer}</li>
        </ul>
      </Card>

      {modal?.type === "add" && (
        <Modal title="Add user" onClose={() => setModal(null)}
          footer={<><button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn-primary" form="user-form" disabled={busy}>Add user</button></>}>
          <form id="user-form" className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(api.post("/api/users", form)); }}>
            <ErrorBanner error={actionError} />
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Username</span>
              <input className="field" autoFocus required minLength={3} maxLength={50} pattern="[A-Za-z0-9._\-]+" value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </label>
            <PasswordField value={form.password} onChange={(password) => setForm({ ...form, password })} label="Temporary password" />
            <Select label="Role" value={form.role} onChange={(role) => setForm({ ...form, role })}
              options={[["viewer", "Viewer (read-only)"], ["admin", "Administrator"]]} />
            <p className="text-xs text-muted">{ROLE_HELP[form.role]} Ask them to change their password after signing in.</p>
          </form>
        </Modal>
      )}

      {modal?.type === "reset" && (
        <Modal title={`Reset password for ${modal.user.username}`} onClose={() => setModal(null)}
          footer={<><button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn-primary" form="reset-form" disabled={busy}>Set password</button></>}>
          <form id="reset-form" className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(api.patch(`/api/users/${modal.user.id}`, { password: form.password })); }}>
            <ErrorBanner error={actionError} />
            <PasswordField value={form.password} onChange={(password) => setForm({ ...form, password })} label="New password" />
            <p className="text-xs text-muted">They will be signed out everywhere and must use the new password.</p>
          </form>
        </Modal>
      )}

      {modal?.type === "delete" && (
        <Modal title={`Delete ${modal.user.username}?`} onClose={() => setModal(null)}
          footer={<><button className="btn-secondary" onClick={() => setModal(null)}>Cancel</button>
            <button className="btn-danger" disabled={busy} onClick={() => run(api.delete(`/api/users/${modal.user.id}`))}>Delete user</button></>}>
          <ErrorBanner error={actionError} />
          <p className="text-sm">They will no longer be able to sign in. To keep the account but block access temporarily, use “Disable” instead.</p>
        </Modal>
      )}
    </>
  );
}
