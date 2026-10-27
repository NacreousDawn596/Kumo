import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Calendar,
  FileText,
  Folder,
  Home,
  Inbox,
  ListTodo,
  Network,
  Plus,
  Search,
  Settings,
  Users,
  Video,
  Bell,
  Command,
  Menu as MenuIcon,
  X,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import { useAuth } from "../store/auth.js";
import { useTheme } from "../store/theme.js";
import { useCommandPalette } from "../store/commandPalette.js";
import { Avatar, IconButton, Menu } from "../components/ui.jsx";
import CommandPalette from "../components/CommandPalette.jsx";
import QuickCapture from "../components/QuickCapture.jsx";
import "./shell.css";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/calendar", label: "Calendar", icon: Calendar },
  { to: "/tasks", label: "Tasks", icon: ListTodo },
  { to: "/notes", label: "Notes", icon: FileText },
  { to: "/knowledge", label: "Knowledge", icon: Network },
  { to: "/vault", label: "Vault", icon: Folder },
];

const NAV_SECONDARY = [
  { to: "/sessions", label: "Study Rooms", icon: Video },
  { to: "/groups", label: "Groups", icon: Users },
];

export default function AppShell() {
  const { user, logout } = useAuth();
  const { preference, apply } = useTheme();
  const openPalette = useCommandPalette((s) => s.openPalette);
  const [quickCapture, setQuickCapture] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();

  const ThemeIcon = preference === "dark" ? Moon : preference === "light" ? Sun : Monitor;

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openPalette]);

  const sidebar = (
    <div className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          <span className="brand-mark-core" />
        </span>
        <span className="brand-name">Kumo</span>
      </div>

      <button className="quick-capture-btn" onClick={() => setQuickCapture(true)}>
        <Plus size={15} strokeWidth={2.2} />
        <span>Quick capture</span>
        <kbd className="kbd">/</kbd>
      </button>

      <nav className="sidebar-nav">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
          >
            <Icon size={16} strokeWidth={1.8} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-section-gap" />

      <nav className="sidebar-nav">
        {NAV_SECONDARY.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
          >
            <Icon size={16} strokeWidth={1.8} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <NavLink
          to="/settings"
          onClick={() => setMobileOpen(false)}
          className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
        >
          <Settings size={16} strokeWidth={1.8} />
          <span>Settings</span>
        </NavLink>
        <div className="sidebar-user">
          <Avatar name={user?.display_name} size={26} />
          <span className="sidebar-user-name">{user?.display_name}</span>
          <Menu
            align="right"
            trigger={<IconButton icon={MenuIcon} label="Account" size="sm" />}
            items={[
              { label: "Settings", onClick: () => navigate("/settings") },
              { divider: true },
              { label: "Sign out", danger: true, onClick: () => logout().then(() => navigate("/login")) },
            ]}
          />
        </div>
      </div>
    </div>
  );

  return (
    <div className="shell">
      <aside className="sidebar-desktop">{sidebar}</aside>

      {mobileOpen && (
        <div className="mobile-drawer-overlay" onClick={() => setMobileOpen(false)}>
          <aside className="mobile-drawer" onClick={(e) => e.stopPropagation()}>
            <div className="mobile-drawer-head">
              <span className="brand-name">Kumo</span>
              <IconButton icon={X} label="Close" onClick={() => setMobileOpen(false)} />
            </div>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="shell-main">
        <header className="topbar">
          <button className="topbar-menu" onClick={() => setMobileOpen(true)}>
            <MenuIcon size={18} />
          </button>
          <button className="search-trigger" onClick={openPalette}>
            <Search size={15} />
            <span>Search or jump to…</span>
            <kbd className="kbd">⌘K</kbd>
          </button>
          <div className="topbar-actions">
            <IconButton icon={Command} label="Command palette" onClick={openPalette} />
            <button
              className="theme-toggle"
              onClick={() =>
                apply(preference === "dark" ? "light" : preference === "light" ? "system" : "dark")
              }
              aria-label="Toggle theme"
            >
              <ThemeIcon size={16} />
            </button>
            <IconButton icon={Bell} label="Notifications" onClick={() => navigate("/inbox")} />
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>

      <CommandPalette />
      <QuickCapture open={quickCapture} onClose={() => setQuickCapture(false)} />
    </div>
  );
}
