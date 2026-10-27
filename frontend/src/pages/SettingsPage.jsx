import { useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import { Bell, LogOut, Monitor, Moon, Sun } from "lucide-react";
import { useAuth } from "../store/auth.js";
import { useTheme } from "../store/theme.js";
import { apiPatch, apiPost } from "../api/client.js";
import { Avatar, Button, Input, Textarea } from "../components/ui.jsx";
import StorageMeter from "../components/StorageMeter.jsx";
import { registerAndSubscribe, unsubscribe } from "../lib/push.js";
import "../styles/pages.css";
import "./settings.css";
import { useRef, useState } from "react";

const SECTIONS = [
  { id: "appearance", label: "Appearance" },
  { id: "notifications", label: "Notifications" },
  { id: "profile", label: "Profile" },
  { id: "storage", label: "Storage" },
  { id: "caldav", label: "CalDAV" },
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
        {section === "notifications" && <NotificationsSection />}
        {section === "profile" && <ProfileSection />}
        {section === "storage" && <StorageSection />}
        {section === "caldav" && <CalDAVSection />}
        {section === "account" && <AccountSection />}
      </div>
    </div>
  );
}

function AppearanceSection() {
  const { mode, accent, radiusScale, fontScale, setMode, setAccent, setRadius, setFontScale } = useTheme();
  const options = [
    { id: "light", label: "Light", icon: Sun },
    { id: "dark", label: "Dark", icon: Moon },
    { id: "system", label: "System", icon: Monitor },
  ];

  const accentColors = {
    purple: "#7c2bb4",
    blue: "#2563eb",
    indigo: "#4f46e5",
    teal: "#0d9488",
    green: "#16a34a",
    orange: "#ea580c",
    rose: "#e11d48",
    cyan: "#0891b2",
  };

  return (
    <div>
      <h1 className="page-title">Appearance</h1>

      <h2 className="settings-subtitle">Mode</h2>
      <div className="theme-options">
        {options.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`theme-option ${mode === id ? "theme-option-active" : ""}`}
            onClick={() => setMode(id)}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}
      </div>

      <h2 className="settings-subtitle">Accent color</h2>
      <div className="accent-swatches">
        {Object.entries(accentColors).map(([name, color]) => (
          <button
            key={name}
            className={`accent-swatch ${accent === name ? "accent-swatch-active" : ""}`}
            style={{ background: color }}
            title={name}
            aria-label={name}
            onClick={() => setAccent(name)}
          />
        ))}
      </div>

      <h2 className="settings-subtitle">
        Corner radius — {Math.round(radiusScale * 100)}%
      </h2>
      <input
        type="range"
        min="0.5"
        max="2"
        step="0.1"
        value={radiusScale}
        onChange={(e) => setRadius(e.target.value)}
      />

      <h2 className="settings-subtitle">
        Text size — {Math.round(fontScale * 100)}%
      </h2>
      <input
        type="range"
        min="0.85"
        max="1.4"
        step="0.05"
        value={fontScale}
        onChange={(e) => setFontScale(e.target.value)}
      />
    </div>
  );
}

function ProfileSection() {
  const { user, setUser } = useAuth();
  const queryClient = useQueryClient();
  const fileRef = useRef(null);
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

  const uploadAvatar = useMutation({
    mutationFn: (file) => {
      const fd = new FormData();
      fd.append("file", file);
      return fetch("/api/users/me/avatar", { method: "POST", credentials: "include", body: fd }).then((r) => r.json());
    },
    onSuccess: () => queryClient.invalidateQueries(),
  });

  const onAvatarPick = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) uploadAvatar.mutate(f);
  };

  return (
    <div>
      <h1 className="page-title">Profile</h1>
      <div className="settings-form">
        <div className="avatar-upload">
          <Avatar name={user?.display_name} userId={user?.id} size={56} />
          <button className="btn btn-secondary btn-sm" onClick={() => fileRef.current?.click()}>
            {uploadAvatar.isPending ? "Uploading…" : "Change photo"}
          </button>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={onAvatarPick} />
        </div>
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

function StorageSection() {
  return (
    <div>
      <h1 className="page-title">Storage</h1>
      <p className="page-subtitle">
        Each account has a 500 MB limit. Linked files (shared with you) count
        toward your quota; remove a link to free space without deleting the file.
      </p>
      <div style={{ marginTop: 16 }}>
        <StorageMeter />
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

function CalDAVSection() {
  const { user } = useAuth();
  const [creds, setCreds] = useState(null);

  const issue = useMutation({
    mutationFn: () => apiPost("/api/users/me/caldav-password", {}),
    onSuccess: (d) => setCreds(d),
  });

  const serverUrl = `${window.location.origin}/caldav/`;

  return (
    <div>
      <h1 className="page-title">CalDAV</h1>
      <p className="page-subtitle">
        Sync your Kumo calendar with an external client (Apple Calendar,
        Thunderbird, GNOME Calendar, …).
      </p>

      <div className="settings-form" style={{ marginTop: 12 }}>
        <label className="auth-label">
          Server URL
          <Input readOnly value={serverUrl} onFocus={(e) => e.target.select()} />
        </label>
        <p className="page-subtitle">
          Your password is a generated token (never used for signing in). It is
          rotated whenever you sign in, so generate a fresh one here before
          adding the account to a client.
        </p>
        <Button variant="primary" loading={issue.isPending} onClick={() => issue.mutate()} style={{ alignSelf: "flex-start" }}>
          Generate password
        </Button>
        {creds && (
          <div className="caldav-creds">
            <label className="auth-label">
              Username
              <Input readOnly value={creds.username || user?.email} onFocus={(e) => e.target.select()} />
            </label>
            <label className="auth-label">
              Password (copy now — it is only shown once)
              <Input readOnly value={creds.password} onFocus={(e) => e.target.select()} />
            </label>
          </div>
        )}
      </div>
    </div>
  );
}

function NotificationsSection() {
  const [pushOn, setPushOn] = useState(false);
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    setBusy(true);
    try {
      if (pushOn) {
        await unsubscribe();
        setPushOn(false);
      } else {
        const res = await registerAndSubscribe();
        setPushOn(res.enabled);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <h1 className="page-title">Notifications</h1>
      <div className="settings-row">
        <div>
          <div className="settings-label">Browser push notifications</div>
          <div className="settings-value">Receive notifications when Kumo is closed.</div>
        </div>
        <button className={`share-toggle ${pushOn ? "share-toggle-on" : ""}`} onClick={toggle} disabled={busy} aria-label="Toggle push notifications">
          <span className="share-toggle-knob" />
        </button>
      </div>
    </div>
  );
}

