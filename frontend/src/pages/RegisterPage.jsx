import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../store/auth.js";
import { Button, Input } from "../components/ui.jsx";
import "./auth.css";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ display_name: "", username: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(form);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "Sign up failed");
    } finally {
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
        <h1 className="auth-title">Create your account</h1>
        <p className="auth-subtitle">Organize your academic life.</p>

        <button className="auth-sso">
          <span className="auth-sso-dot" />
          Continue with SchoolApp
        </button>

        <div className="auth-divider">
          <span>or sign up with email</span>
        </div>

        <form onSubmit={submit} className="auth-form">
          <label className="auth-label">
            Display name
            <Input value={form.display_name} onChange={set("display_name")} placeholder="Ada Lovelace" required />
          </label>
          <label className="auth-label">
            Username
            <Input value={form.username} onChange={set("username")} placeholder="ada" pattern="[a-z0-9_\-]+" required />
          </label>
          <label className="auth-label">
            Email
            <Input type="email" value={form.email} onChange={set("email")} placeholder="you@university.edu" required />
          </label>
          <label className="auth-label">
            Password
            <Input
              type="password"
              value={form.password}
              onChange={set("password")}
              placeholder="At least 8 characters"
              minLength={8}
              required
            />
          </label>
          {error && <p className="auth-error">{error}</p>}
          <Button type="submit" variant="primary" size="lg" loading={loading}>
            Create account
          </Button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
