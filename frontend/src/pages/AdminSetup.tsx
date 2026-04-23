import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function AdminSetup() {
  const nav = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    if (password !== confirm) {
      setErr("Passwords don't match.");
      return;
    }
    if (password.length < 8) {
      setErr("Use at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await api.setup(username, password);
      nav("/admin", { replace: true });
    } catch (e: any) {
      setErr(e.message || "setup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Welcome — let's set up your admin account</h1>
        <p className="muted" style={{ marginTop: -8, marginBottom: 16 }}>
          This one-time form creates the login you'll use to manage this uploader.
          Pick a username and a strong password. Write the password down somewhere
          safe — it's not recoverable.
        </p>
        <form onSubmit={onSubmit}>
          <label>Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
          <label>Password (min 8 characters)</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
            minLength={8}
          />
          <label>Confirm password</label>
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            required
            minLength={8}
          />
          {err && <div className="error">{err}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create admin"}
          </button>
        </form>
      </div>
    </div>
  );
}
