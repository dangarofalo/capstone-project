import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearSession, loadSession, saveSession, setUnauthorizedHandler } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => loadSession());

  useEffect(() => {
    // Any 401 from the API (expired or revoked session) signs the user out.
    setUnauthorizedHandler(() => setSession(null));
  }, []);

  const login = useCallback(async (username, password) => {
    const response = await api.post("/api/auth/login", { username, password });
    setSession(saveSession(response));
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  const replaceSession = useCallback((tokenResponse) => setSession(saveSession(tokenResponse)), []);

  const value = useMemo(
    () => ({
      user: session?.user ?? null,
      isAdmin: session?.user?.role === "admin",
      login,
      logout,
      replaceSession,
    }),
    [session, login, logout, replaceSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
