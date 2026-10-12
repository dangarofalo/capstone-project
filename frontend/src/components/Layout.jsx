import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth.jsx";

const NAV = [
  { to: "/", label: "Overview", icon: "▦", end: true },
  { to: "/alerts", label: "Alerts", icon: "⚑" },
  { to: "/events", label: "Events", icon: "☰" },
  { to: "/computers", label: "Computers", icon: "▭" },
  { to: "/reports", label: "Reports", icon: "⎙" },
  { to: "/users", label: "Users", icon: "◉", adminOnly: true },
];

function Logo() {
  return (
    <div className="flex items-center gap-2 font-semibold">
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden="true">
        <path d="M16 2 4 7v8c0 7.5 5.1 13.4 12 15 6.9-1.6 12-7.5 12-15V7z" fill="currentColor" />
        <path d="m11 16 3.5 3.5L21.5 12" fill="none" stroke="var(--sv-brand)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      SentinelView
    </div>
  );
}

export default function Layout() {
  const { user, isAdmin, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const links = NAV.filter((n) => !n.adminOnly || isAdmin);

  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {links.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.end}
          onClick={() => setMenuOpen(false)}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${
              isActive ? "bg-white/15 font-medium text-white" : "text-white/80 hover:bg-white/10 hover:text-white"
            }`
          }
        >
          <span aria-hidden="true" className="w-4 text-center">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );

  const account = (
    <div className="border-t border-white/15 pt-4 text-sm text-white/80">
      <NavLink to="/account" onClick={() => setMenuOpen(false)} className="block rounded-md px-3 py-2 hover:bg-white/10 hover:text-white">
        <div className="font-medium text-white">{user.username}</div>
        <div className="text-xs">{isAdmin ? "Administrator" : "Viewer (read-only)"} · My account</div>
      </NavLink>
      <button type="button" onClick={logout} className="mt-1 w-full rounded-md px-3 py-2 text-left hover:bg-white/10 hover:text-white">
        Sign out
      </button>
    </div>
  );

  return (
    <div className="min-h-screen lg:flex">
      {/* Desktop sidebar */}
      <aside className="no-print hidden w-60 shrink-0 flex-col justify-between bg-brand p-4 text-white lg:sticky lg:top-0 lg:flex lg:h-screen">
        <div>
          <div className="mb-6 px-2 text-white"><Logo /></div>
          {nav}
        </div>
        {account}
      </aside>

      {/* Mobile top bar */}
      <header className="no-print sticky top-0 z-10 flex items-center justify-between bg-brand px-4 py-3 text-white lg:hidden">
        <Logo />
        <button type="button" className="rounded-md px-2 py-1 hover:bg-white/10" aria-expanded={menuOpen} onClick={() => setMenuOpen((o) => !o)}>
          {menuOpen ? "Close" : "Menu"}
        </button>
      </header>
      {menuOpen && (
        <div className="no-print space-y-4 bg-brand px-4 pb-4 lg:hidden">
          {nav}
          {account}
        </div>
      )}

      <main className="min-w-0 flex-1 px-4 py-6 sm:px-8 lg:py-8">
        <div className="mx-auto max-w-7xl">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
