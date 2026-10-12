// Talks to the SentinelView API, adding the sign-in token to every request.

const TOKEN_KEY = "sentinelview.session";

export function loadSession() {
  try {
    const session = JSON.parse(localStorage.getItem(TOKEN_KEY));
    if (session && session.expiresAt > Date.now()) return session;
  } catch {
    // storage unavailable or corrupted: treat as signed out
  }
  return null;
}

export function saveSession(tokenResponse) {
  const session = {
    token: tokenResponse.access_token,
    user: tokenResponse.user,
    expiresAt: Date.now() + tokenResponse.expires_in * 1000,
  };
  try {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
  } catch {
    // private browsing: the session still works until the tab closes
  }
  return session;
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // ignore
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

async function request(path, { method = "GET", body, raw = false } = {}) {
  const headers = {};
  const session = loadSession();
  if (session) headers.Authorization = `Bearer ${session.token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError(0, "Can't reach the SentinelView server. Check that it is running.");
  }

  if (response.status === 401 && !path.startsWith("/api/auth/login")) {
    clearSession();
    onUnauthorized();
  }
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d) => d.msg).join("; ");
    } catch {
      // not JSON
    }
    throw new ApiError(response.status, message);
  }
  if (raw) return response;
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: "POST", body }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  delete: (path) => request(path, { method: "DELETE" }),
};

// Downloads need the token too, so fetch the file and hand it to the browser.
export async function download(path) {
  const response = await request(path, { raw: true });
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] || "download";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
