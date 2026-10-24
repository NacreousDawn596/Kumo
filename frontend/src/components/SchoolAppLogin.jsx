import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Dialog, Button, Input } from "./ui.jsx";
import { api } from "../api/client.js";
import { useAuth } from "../store/auth.js";

const WORKER_URL = import.meta.env.VITE_SCHOOLAPP_WORKER_URL || "";

export default function SchoolAppLogin({ open, onClose }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const { setUser } = useAuth();
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError(null);

    if (!WORKER_URL) {
      setError("SchoolApp sign-in is not configured yet.");
      return;
    }

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
      onClose();
      navigate("/", { replace: true });
    } catch (err) {
      setError(err.message || "SchoolApp sign-in failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Continue with SchoolApp"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" type="submit" form="schoolapp-form" loading={loading}>
            Continue
          </Button>
        </>
      }
    >
      <p className="sa-note">
        Verify your SchoolApp identity to sign in to Kumo. Your password is used
        once to verify and is never stored.
      </p>
      <form id="schoolapp-form" onSubmit={submit} className="auth-form">
        <label className="auth-label">
          SchoolApp email
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@schoolapp" required autoFocus />
        </label>
        <label className="auth-label">
          SchoolApp password
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
        </label>
        {error && <p className="auth-error">{error}</p>}
      </form>
    </Dialog>
  );
}
