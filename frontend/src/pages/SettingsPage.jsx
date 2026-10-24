import { useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { LogOut, Monitor, Moon, Sun } from "lucide-react";
import { useAuth } from "../store/auth.js";
import { useTheme } from "../store/theme.js";
import { apiPatch } from "../api/client.js";
import { Button, Input, Textarea } from "../components/ui.jsx";
import "../styles/pages.css";
import "./settings.css";
import { useState } from "react";

const SECTIONS = [
  { id: "appearance", label: "Appearance" },
  { id: "profile", label: "Profile" },
  { id: "account", label: "Account" },
];

export default function SettingsPage() {
  const { section = "appearance" } = useParams();

  return (
    <div className="page settings-layout">
      <div className="settings-nav">
        {SECTIONS.map((s) => (
          <NavLink
            key={s.id}
            to={`/settings/${s.id}`}
            className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}
          >
            {s.label}
          </NavLink>
        ))}
      </div>
      <div className="settings-body">
        {section === "appearance" && <AppearanceSection />}
        {section === "profile" && <ProfileSection />}
        {section === "account" && <AccountSection />}
      </div>
    </div>
  );
}

function AppearanceSection() {
  const { preference, apply } = useTheme();
  const options = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
    { id: "system", label: "System", icon: Monitor },
  ];

  return (
    <div>
      <h1 className="page-title">Appearance</h1>
      <p className="page-subtitle">Theme</p>
      <div className="theme-options">
        {options.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`theme-option ${preference === id ? "theme-option-active" : ""}`}
            onClick={() => apply(id)}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    display_name: user?.display_name || "",
    bio: user?.bio || "",
    timezone: user?.timezone || "UTC",
  });

  const save = useMutation({
    mutationFn: () => apiPatch("/api/users/me", form),
    onSuccess: (u) => {
      setUser(u);
      queryClient.invalidateQueries();
    },
  });

  return (
    <div>
      <h1 className="page-title">Profile</h1>
      <div className="settings-form">
        <label className="auth-label">
          Display name
          <Input value={form.display_name} onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))} />
        </label>
        <label className="auth-label">
          Bio
          <Textarea value={form.bio} onChange={(e) => setForm((f) => ({ ...f, bio: e.target.value }))} rows={3} />
        </label>
        <label className="auth-label">
          Time zone
          <Input value={form.timezone} onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))} />
        </label>
        <Button variant="primary" loading={save.isPending} onClick={() => save.mutate()} style={{ alignSelf: "flex-start" }}>
          Save
        </Button>
      </div>
    </div>
  );
}

function AccountSection() {
  const { user, logout } = useAuth();
  return (
    <div>
      <h1 className="page-title">Account</h1>
      <div className="settings-row">
        <div>
          <div className="settings-label">Signed in as</div>
          <div className="settings-value">{user?.email}</div>
        </div>
        <Button variant="secondary" icon={LogOut} onClick={logout}>
          Sign out
        </Button>
      </div>
    </div>
  );
}

