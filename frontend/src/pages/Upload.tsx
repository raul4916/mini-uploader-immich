import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api, uploadFile } from "../api";

type Status = "checking" | "ready" | "invalid" | "uploading" | "done" | "error";

const MIME_OK = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/gif"];

export default function Upload() {
  const { token = "" } = useParams();
  const [status, setStatus] = useState<Status>("checking");
  const [album, setAlbum] = useState("");
  const [maxMb, setMaxMb] = useState(50);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [msg, setMsg] = useState("");
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api.checkToken(token);
        setAlbum(r.album_name || "");
        setMaxMb(r.max_mb);
        setStatus("ready");
      } catch {
        setStatus("invalid");
      }
    })();
  }, [token]);

  function pickFile(f: File | null) {
    setMsg("");
    if (!f) {
      setFile(null);
      setPreview(null);
      return;
    }
    if (!MIME_OK.includes(f.type)) {
      setMsg(`Not a supported image type: ${f.type || "unknown"}`);
      return;
    }
    if (f.size > maxMb * 1024 * 1024) {
      setMsg(`File too large (${(f.size / 1024 / 1024).toFixed(1)}MB > ${maxMb}MB)`);
      return;
    }
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    pickFile(e.dataTransfer.files?.[0] || null);
  }

  function onInput(e: ChangeEvent<HTMLInputElement>) {
    pickFile(e.target.files?.[0] || null);
  }

  async function send() {
    if (!file) return;
    setStatus("uploading");
    setProgress(0);
    setMsg("");
    try {
      await uploadFile(token, file, setProgress);
      setStatus("done");
      setMsg("Uploaded!");
    } catch (e: any) {
      setStatus("error");
      setMsg(e.message || "upload failed");
    }
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setProgress(0);
    setMsg("");
    setStatus("ready");
    if (inputRef.current) inputRef.current.value = "";
  }

  if (status === "checking") return <div className="container">Checking link…</div>;
  if (status === "invalid") {
    return (
      <div className="container">
        <div className="card">
          <h1>Link invalid or expired</h1>
          <div className="muted">Ask the admin for a new QR code.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Upload to {album || "Immich"}</h1>
        <div className="muted" style={{ marginBottom: 16 }}>
          Files scanned for malware before upload. Max {maxMb}MB. Image formats only.
        </div>

        {!file && (
          <div
            className={`dropzone ${drag ? "drag" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div>Drop image here</div>
            <div className="muted" style={{ marginTop: 6 }}>or click to choose</div>
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={onInput}
            />
          </div>
        )}

        {preview && <img src={preview} alt="preview" className="preview" />}

        {file && status !== "done" && (
          <>
            <div className="muted" style={{ marginTop: 8 }}>
              {file.name} — {(file.size / 1024 / 1024).toFixed(2)}MB
            </div>
            {status === "uploading" && (
              <div className="progress"><div className="progress-bar" style={{ width: `${progress}%` }} /></div>
            )}
            <div className="row" style={{ marginTop: 12, gap: 8 }}>
              <button onClick={send} disabled={status === "uploading"}>
                {status === "uploading" ? `Uploading ${progress}%` : "Upload"}
              </button>
              <button className="ghost" onClick={reset} disabled={status === "uploading"}>
                Cancel
              </button>
            </div>
          </>
        )}

        {status === "done" && (
          <div className="row" style={{ marginTop: 12, gap: 8 }}>
            <button onClick={reset}>Upload another</button>
          </div>
        )}

        {msg && (
          <div className={status === "error" ? "error" : "success"}>{msg}</div>
        )}
      </div>
    </div>
  );
}
