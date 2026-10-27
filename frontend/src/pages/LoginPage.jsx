import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth.js";
import { api } from "../api/client.js";
import { Button, Input } from "../components/ui.jsx";
import "./auth.css";

const WORKER_URL = import.meta.env.VITE_SCHOOLAPP_WORKER_URL || "";

export default function LoginPage() {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // 1. Verify SchoolApp credentials and obtain a short-lived assertion.
      const res = await fetch(`${WORKER_URL}/verify`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.error || "SchoolApp sign-in failed.");
        setLoading(false);
        return;
      }

      // 2. Exchange the assertion for a Kumo session.
      const user = await api("/api/auth/schoolapp/assert", {
        method: "POST",
        body: { assertion: data.assertion },
      });
      setUser(user);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "SchoolApp sign-in failed.");
      setLoading(false);
    }
  };

  return (
    <div className="auth">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark">
            <span className="brand-mark-core" />
          </span>
          <span className="brand-name">Kumo</span>
        </div>
        <h1 className="auth-title">Sign in with SchoolApp</h1>
        <p className="auth-subtitle">Use your SchoolApp account to continue.</p>

        <form onSubmit={submit} className="auth-form">
          <label className="auth-label">
            SchoolApp email
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@schoolapp"
              autoComplete="email"
              required
              autoFocus
            />
          </label>
          <label className="auth-label">
            SchoolApp password
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <Button type="submit" variant="primary" size="lg" loading={loading}>
            Sign in
          </Button>
        </form>

        <p className="auth-footer">
          Your password is used once to verify and is never stored.
        </p>
      </div>
    </div>
  );
}
