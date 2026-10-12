import { useState } from "react";
import { AgentStatusBadge, Card, EmptyState, ErrorBanner, Loading, Modal, PageHeader } from "../components/ui.jsx";
import { api } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { formatDateTime, timeAgo } from "../lib/format.js";
import { useApi } from "../lib/useApi.js";

function CopyBox({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="relative">
      <pre className="overflow-x-auto rounded-md border border-line bg-page p-3 pr-20 text-xs">{text}</pre>
      <button
        type="button"
        className="btn-secondary absolute right-2 top-2 px-2 py-1 text-xs"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          } catch {
            // clipboard blocked: the text is still selectable
          }
        }}
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

// Shown once after adding a computer or replacing its key.
function KeyInstructions({ result, onClose }) {
  const config = JSON.stringify(
    {
      server_url: window.location.origin,
      api_key: result.api_key,
      source: "windows",
      interval_seconds: 30,
      initial_lookback_hours: 24,
      state_file: "agent_state.json",
    },
    null,
    2,
  );
  return (
    <Modal title={`Connect ${result.agent.name}`} onClose={onClose} footer={<button className="btn-primary" onClick={onClose}>Done</button>}>
      <div className="space-y-4 text-sm">
        <div role="alert" className="rounded-md border border-serious/50 bg-serious/10 px-3 py-2">
          <strong>Copy this now.</strong> For security, the key is only shown once. If you lose it, use "New key".
        </div>
        <ol className="list-decimal space-y-3 pl-5">
          <li>Copy the <code>agent</code> folder from SentinelView onto the computer (Python 3.12+ must be installed).</li>
          <li>
            Save this as <code>agent\config.json</code>:
            <div className="mt-2"><CopyBox text={config} /></div>
            <p className="mt-1 text-xs text-muted">For a Linux computer, change <code>"source"</code> to <code>"linux"</code>.</p>
          </li>
          <li>
            Open PowerShell with <em>Run as administrator</em> in the agent folder and run:
            <div className="mt-2"><CopyBox text="python sentinel_agent.py" /></div>
          </li>
        </ol>
        <p className="text-ink-2">The computer shows as Online here within 30 seconds of the agent starting.</p>
      </div>
    </Modal>
  );
}

export default function Computers() {
  const { isAdmin } = useAuth();
  const { data: agents, error, reload } = useApi("/api/agents", { refreshMs: 30_000 });
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [keyResult, setKeyResult] = useState(null);
  const [confirm, setConfirm] = useState(null); // { agent, action }
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run(promise) {
    setBusy(true);
    setActionError(null);
    try {
      const result = await promise;
      await reload();
      return result;
    } catch (e) {
      setActionError(e);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function addComputer(e) {
    e.preventDefault();
    const result = await run(api.post("/api/agents", { name: name.trim() }));
    if (result) {
      setAdding(false);
      setName("");
      setKeyResult(result);
    }
  }

  async function confirmAction() {
    const { agent, action } = confirm;
    setConfirm(null);
    const result = await run(api.post(`/api/agents/${agent.id}/${action}`));
    if (result && action === "rotate-key") setKeyResult(result);
  }

  return (
    <>
      <PageHeader
        title="Computers"
        description="The computers SentinelView is watching. Each one runs a small agent that sends its security events here."
        actions={isAdmin && <button className="btn-primary" onClick={() => setAdding(true)}>+ Add computer</button>}
      />
      <ErrorBanner error={error || actionError} />
      <Card>
        {!agents ? (
          <Loading />
        ) : agents.length === 0 ? (
          <EmptyState title="No computers yet">
            {isAdmin ? "Click “Add computer” to connect your first one." : "Ask an administrator to add computers."}
          </EmptyState>
        ) : (
          <div className="-mx-4 overflow-x-auto sm:mx-0">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-ink-2">
                <tr className="border-b border-line">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Last report</th>
                  <th className="px-3 py-2 font-medium">System</th>
                  {isAdmin && <th className="px-3 py-2 text-right font-medium">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {agents.map((a) => (
                  <tr key={a.id} className="border-b border-line last:border-0">
                    <td className="px-3 py-3">
                      <div className="font-medium">{a.name}</div>
                      {a.hostname && a.hostname !== a.name && <div className="text-xs text-muted">{a.hostname}</div>}
                    </td>
                    <td className="px-3 py-3"><AgentStatusBadge status={a.status} /></td>
                    <td className="whitespace-nowrap px-3 py-3 text-ink-2" title={formatDateTime(a.last_seen)}>{timeAgo(a.last_seen)}</td>
                    <td className="px-3 py-3 text-ink-2">{a.os || "—"}</td>
                    {isAdmin && (
                      <td className="whitespace-nowrap px-3 py-3 text-right">
                        <button className="btn-secondary px-2 py-1 text-xs" disabled={busy} onClick={() => setConfirm({ agent: a, action: "rotate-key" })}>
                          New key
                        </button>{" "}
                        {a.status !== "revoked" && (
                          <button className="btn-danger px-2 py-1 text-xs" disabled={busy} onClick={() => setConfirm({ agent: a, action: "revoke" })}>
                            Revoke
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {adding && (
        <Modal
          title="Add a computer"
          onClose={() => setAdding(false)}
          footer={
            <>
              <button className="btn-secondary" onClick={() => setAdding(false)}>Cancel</button>
              <button className="btn-primary" form="add-computer" disabled={busy || !name.trim()}>Create key</button>
            </>
          }
        >
          <form id="add-computer" onSubmit={addComputer}>
            <label className="block text-sm">
              <span className="mb-1 block font-medium">Name</span>
              <input className="field" autoFocus maxLength={100} pattern="[A-Za-z0-9 ._\-]+" required value={name}
                onChange={(e) => setName(e.target.value)} placeholder="e.g. FRONT-DESK-PC" />
              <span className="mt-1 block text-xs text-muted">Letters, numbers, spaces, dots, dashes, and underscores.</span>
            </label>
          </form>
        </Modal>
      )}

      {confirm && (
        <Modal
          title={confirm.action === "revoke" ? `Revoke ${confirm.agent.name}?` : `New key for ${confirm.agent.name}?`}
          onClose={() => setConfirm(null)}
          footer={
            <>
              <button className="btn-secondary" onClick={() => setConfirm(null)}>Cancel</button>
              <button className={confirm.action === "revoke" ? "btn-danger" : "btn-primary"} onClick={confirmAction}>
                {confirm.action === "revoke" ? "Revoke" : "Create new key"}
              </button>
            </>
          }
        >
          <p className="text-sm">
            {confirm.action === "revoke"
              ? "This computer will no longer be able to send events. Its past events stay available. You can re-enable it later with a new key."
              : "The current key stops working immediately. You'll need to put the new key in the agent's config.json."}
          </p>
        </Modal>
      )}

      {keyResult && <KeyInstructions result={keyResult} onClose={() => setKeyResult(null)} />}
    </>
  );
}
