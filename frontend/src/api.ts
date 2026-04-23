async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      detail = body.detail || JSON.stringify(body);
    } catch {}
    throw new Error(detail);
  }
  return r.json() as Promise<T>;
}

export interface AdminConfig {
  immich_url: string | null;
  album_id: string | null;
  album_name: string | null;
  api_key_set: boolean;
  upload_token: string | null;
  upload_url: string | null;
  token_rotated_at: string | null;
}

export interface Album {
  id: string;
  albumName: string;
}

export const api = {
  me: () => req<{ admin: boolean }>("/api/admin/me"),
  setupNeeded: () => req<{ setup_needed: boolean }>("/api/admin/setup/needed"),
  setup: (username: string, password: string) =>
    req<{ ok: boolean }>("/api/admin/setup", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  login: (username: string, password: string) =>
    req<{ ok: boolean }>("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => req<{ ok: boolean }>("/api/admin/logout", { method: "POST" }),
  changePassword: (current: string, newPw: string) =>
    req<{ ok: boolean }>("/api/admin/password", {
      method: "POST",
      body: JSON.stringify({ current, new: newPw }),
    }),
  getConfig: () => req<AdminConfig>("/api/admin/config"),
  saveConfig: (body: {
    immich_url: string;
    immich_api_key?: string;
    album_id: string;
    album_name?: string;
  }) =>
    req<AdminConfig>("/api/admin/config", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  listAlbums: (immich_url: string, immich_api_key?: string) =>
    req<Album[]>("/api/admin/albums", {
      method: "POST",
      body: JSON.stringify({ immich_url, immich_api_key }),
    }),
  rotateToken: () =>
    req<{ upload_token: string; upload_url: string; token_rotated_at: string }>(
      "/api/admin/token/rotate",
      { method: "POST" }
    ),
  checkToken: (token: string) =>
    req<{ ok: boolean; album_name: string; max_mb: number }>(
      `/api/upload/status/${encodeURIComponent(token)}`
    ),
};

export function uploadFile(
  token: string,
  file: File,
  onProgress: (pct: number) => void
): Promise<{ ok: boolean; assetId: string }> {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("token", token);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error(body.detail || `${xhr.status}`));
      } catch {
        reject(new Error(`${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("network error"));
    xhr.send(fd);
  });
}
