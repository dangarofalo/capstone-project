import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout.jsx";
import { AuthProvider, useAuth } from "./lib/auth.jsx";
import Account from "./pages/Account.jsx";
import AlertDetail from "./pages/AlertDetail.jsx";
import Alerts from "./pages/Alerts.jsx";
import Computers from "./pages/Computers.jsx";
import Events from "./pages/Events.jsx";
import Login from "./pages/Login.jsx";
import Overview from "./pages/Overview.jsx";
import Reports from "./pages/Reports.jsx";
import Users from "./pages/Users.jsx";

function RequireAuth({ children }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  return children;
}

function RequireAdmin({ children }) {
  const { isAdmin } = useAuth();
  return isAdmin ? children : <Navigate to="/" replace />;
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Overview />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="alerts/:id" element={<AlertDetail />} />
            <Route path="events" element={<Events />} />
            <Route path="computers" element={<Computers />} />
            <Route path="reports" element={<Reports />} />
            <Route path="account" element={<Account />} />
            <Route path="users" element={<RequireAdmin><Users /></RequireAdmin>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </StrictMode>,
);
