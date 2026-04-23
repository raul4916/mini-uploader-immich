import { QRCodeSVG } from "qrcode.react";
import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AdminConfig, Album, api } from "../api";

function ChangePassword() {
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setMsg("");
    if (next !== confirm) {
      setErr("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await api.changePassword(current, next);
      setMsg("Password updated.");
      setCurrent("");
      setNext("");
      setConfirm("");
      setOpen(false);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Password</h2>
        <button className="ghost" onClick={() => setOpen((v) => !v)}>
          {open ? "Cancel" : "Change password"}
        </button>
      </div>
      {open && (
        <form onSubmit={submit} style={{ marginTop: 12 }}>
          <label>Current password</label>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          <label>New password (min 8)</label>
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} />
          <label>Confirm new password</label>
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
          {err && <div className="error">{err}</div>}
          <button type="submit" disabled={busy}>{busy ? "…" : "Update"}</button>
        </form>
      )}
      {msg && <div className="success">{msg}</div>}
    </div>
  );
}

export default function AdminPanel() {
  const nav = useNavigate();
  const [cfg, setCfg] = useState<AdminConfig | null>(null);
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [albumId, setAlbumId] = useState("");
  const [albums, setAlbums] = useState<Album[]>([]);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.me();
        if (!me.admin) {
          nav("/admin/login", { replace: true });
          return;
        }
        const c = await api.getConfig();
        setCfg(c);
        setUrl(c.immich_url || "");
        setAlbumId(c.album_id || "");
      } catch {
        nav("/admin/login", { replace: true });
      }
    })();
  }, [nav]);

  async function loadAlbums() {
    setErr("");
    try {
      const list = await api.listAlbums(url, apiKey || undefined);
      setAlbums(list);
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function save() {
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      const selected = albums.find((a) => a.id === albumId);
      const body: any = {
        immich_url: url,
        album_id: albumId,
        album_name: selected?.albumName,
      };
      if (apiKey) body.immich_api_key = apiKey;
      const next = await api.saveConfig(body);
      setCfg(next);
      setApiKey("");
      setMsg("Saved.");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function rotate() {
    setErr("");
    setBusy(true);
    try {
      await api.rotateToken();
      setCfg(await api.getConfig());
      setMsg("Token rotated. Old QR now invalid.");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api.logout();
    nav("/admin/login", { replace: true });
  }

  if (!cfg) return <div className="container">Loading…</div>;

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Admin</h1>
        <button className="ghost" onClick={logout}>Logout</button>
      </div>

      <div className="card">
        <h2>Immich connection</h2>
        <label>Immich URL</label>
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://immich.example.com"
        />
        <label>API key {cfg.api_key_set && <span className="muted">(••• set — leave blank to keep)</span>}</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={cfg.api_key_set ? "keep existing" : "paste Immich API key"}
          autoComplete="new-password"
        />
        <div className="row" style={{ gap: 8 }}>
          <button className="ghost" onClick={loadAlbums} disabled={!url || (!apiKey && !cfg.api_key_set)}>
            Load albums
          </button>
        </div>

        {albums.length > 0 && (
          <>
            <label style={{ marginTop: 16 }}>Target album</label>
            <select value={albumId} onChange={(e) => setAlbumId(e.target.value)}>
              <option value="">— pick one —</option>
              {albums.map((a) => (
                <option key={a.id} value={a.id}>{a.albumName}</option>
              ))}
            </select>
          </>
        )}

        {cfg.album_name && albums.length === 0 && (
          <div className="muted" style={{ marginBottom: 12 }}>
            Current: <b>{cfg.album_name}</b> ({cfg.album_id})
          </div>
        )}

        <button onClick={save} disabled={busy || !url || !albumId}>
          {busy ? "…" : "Save"}
        </button>
        {err && <div className="error">{err}</div>}
        {msg && <div className="success">{msg}</div>}
      </div>

      <ChangePassword />

      <div className="card">
        <h2>Upload QR</h2>
        {cfg.upload_token && cfg.upload_url ? (
          <>
            <div className="qr-box">
              <QRCodeSVG value={cfg.upload_url} size={200} />
            </div>
            <label>Upload URL</label>
            <div className="token-display">{cfg.upload_url}</div>
            <div className="muted" style={{ marginTop: 8 }}>
              Rotated: {cfg.token_rotated_at || "—"}
            </div>
          </>
        ) : (
          <div className="muted" style={{ marginBottom: 12 }}>
            No token yet. Generate one below.
          </div>
        )}
        <div style={{ marginTop: 12 }}>
          <button className="danger" onClick={rotate} disabled={busy}>
            {cfg.upload_token ? "Rotate token" : "Generate token"}
          </button>
        </div>
      </div>
    </div>
  );
}
