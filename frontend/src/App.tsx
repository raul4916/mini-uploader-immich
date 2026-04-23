import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import AdminLogin from "./pages/AdminLogin";
import AdminPanel from "./pages/AdminPanel";
import AdminSetup from "./pages/AdminSetup";
import Upload from "./pages/Upload";

function AdminGate() {
  const nav = useNavigate();
  const [state, setState] = useState<"checking" | "ready">("checking");

  useEffect(() => {
    (async () => {
      try {
        const s = await api.setupNeeded();
        if (s.setup_needed) {
          nav("/admin/setup", { replace: true });
          return;
        }
      } catch {
        // fall through — AdminPanel handles failure
      }
      setState("ready");
    })();
  }, [nav]);

  if (state === "checking") return <div className="container">Loading…</div>;
  return <AdminPanel />;
}

function SetupGate() {
  const nav = useNavigate();
  const [state, setState] = useState<"checking" | "ready">("checking");

  useEffect(() => {
    (async () => {
      try {
        const s = await api.setupNeeded();
        if (!s.setup_needed) {
          nav("/admin/login", { replace: true });
          return;
        }
      } catch {}
      setState("ready");
    })();
  }, [nav]);

  if (state === "checking") return <div className="container">Loading…</div>;
  return <AdminSetup />;
}

function LoginGate() {
  const nav = useNavigate();
  const [state, setState] = useState<"checking" | "ready">("checking");

  useEffect(() => {
    (async () => {
      try {
        const s = await api.setupNeeded();
        if (s.setup_needed) {
          nav("/admin/setup", { replace: true });
          return;
        }
      } catch {}
      setState("ready");
    })();
  }, [nav]);

  if (state === "checking") return <div className="container">Loading…</div>;
  return <AdminLogin />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/admin" replace />} />
      <Route path="/admin/setup" element={<SetupGate />} />
      <Route path="/admin/login" element={<LoginGate />} />
      <Route path="/admin" element={<AdminGate />} />
      <Route path="/u/:token" element={<Upload />} />
      <Route path="*" element={<div className="container"><h1>404</h1></div>} />
    </Routes>
  );
}
