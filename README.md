# mini-uploader

A tiny website where a friend scans a QR code, drops in a photo, and it lands
in one specific album of your Immich photo server. Every file is scanned for
viruses before it's accepted.

You log in (with a password you pick the first time you open the app) to
choose which Immich album photos go into, and to generate the QR code.

---

## If you're not technical: the 5-minute setup

### What you need before you start

1. **A computer that stays on.** This is where the uploader runs. Your laptop
   is fine for testing; a home server (Synology, Unraid, Mac mini, Raspberry Pi,
   an old PC — anything) is better for real use.
2. **Docker Desktop installed** on that computer. It's free.
   - Mac: <https://www.docker.com/products/docker-desktop>
   - Windows: same link
   - Linux: your package manager (`docker` and `docker compose`)
3. **Your Immich server's web address** (for example `https://photos.mydomain.com`).
4. **An Immich API key.** In Immich: click your profile picture (top right) →
   *Account Settings* → *API Keys* → *New API Key*. Copy the long string it
   shows — you'll paste it later.

That's it. You will **not** need to type any passwords into config files or run
any scary-looking commands to generate keys.

### Step 1 — Get the code

Download this folder to your computer. If you were given a zip file, unzip it.
If you know how to use `git`, you can `git clone` it instead.

### Step 2 — Open a terminal in the folder

- **Mac:** right-click the folder in Finder → *New Terminal at Folder*.
- **Windows:** open the folder in File Explorer, click the address bar, type
  `cmd`, press Enter.
- **Linux:** you know what to do.

### Step 3 — Start it

In that terminal, type:

```bash
docker compose up -d --build
```

Press Enter. The first time, this takes a few minutes. Docker is downloading
two things:

- The uploader itself.
- ClamAV, the virus scanner, which also downloads its virus definitions
  (about 200 MB, one-time).

When you get your terminal prompt back, the app is running.

> Tip: if you see `docker: command not found` or similar, Docker Desktop
> isn't running yet. Open the Docker Desktop app first, wait for it to say
> "Docker Desktop is running", then try again.

### Step 4 — Open it in your browser

Go to: <http://localhost:8000>

**First thing you'll see: a setup page.**

Pick a username (default `admin` is fine) and a password at least 8 characters
long. **Write the password down somewhere safe.** There's no "forgot password"
— if you lose it, you'll have to reset the admin account manually (see the
troubleshooting section).

Click **Create admin**. You're in.

### Step 5 — Connect your Immich server

You'll land on the admin page. Fill in:

- **Immich URL** — the web address of your Immich server, like
  `https://photos.mydomain.com`. No trailing slash.
- **API key** — paste the long string you copied from Immich earlier.

Click **Load albums**. A dropdown appears with all your albums. Pick the one
you want uploads to land in.

Click **Save**.

If anything's wrong (typo in the URL, bad API key, Immich offline) the page
tells you and nothing gets saved.

### Step 6 — Generate the QR code

Scroll down to the **Upload QR** card and click **Generate token**.

You'll see:

- A QR code (black-and-white square).
- A URL underneath it, like `http://localhost:8000/u/abc123…`.

**Important:** right now that URL uses `localhost`, which only works *on your
own computer*. For your friend's phone to use the QR code, it needs a URL that
reaches your computer from the outside. There are a few ways:

- **Easiest for testing** (same Wi-Fi network): find your computer's local IP
  address (Mac: System Settings → Wi-Fi → Details; Windows: `ipconfig`; looks
  like `192.168.1.42`). Then edit the `PUBLIC_BASE_URL` setting — see the next
  section.
- **Real use** (anyone, anywhere): point a domain name at your home/server
  with something like Cloudflare Tunnel, Tailscale Funnel, or a real hosted
  server, with HTTPS. If this sentence is gibberish, ask a friend who runs
  their own Immich server — they've done this dance before.

### Step 7 — Print or share the QR

- Right-click the QR → *Save image as* → print it, email it, tape it to a
  fridge, whatever.
- Your friend scans it with their phone camera.
- They land on a page that says "Upload to \[your album name\]". They pick a
  photo, tap Upload. It gets virus-scanned and dropped straight into Immich.

Done.

### Changing the public URL (Step 6 follow-up)

If the default `http://localhost:8000` in the QR isn't reachable from phones:

1. In the same folder, make a copy of `.env.example` and call it `.env`.
2. Open `.env` in any text editor (TextEdit, Notepad, VS Code — any).
3. Change this line:

   ```ini
   PUBLIC_BASE_URL=http://localhost:8000
   ```

   to your actual URL, for example:

   ```ini
   PUBLIC_BASE_URL=http://192.168.1.42:8000
   ```

   or

   ```ini
   PUBLIC_BASE_URL=https://uploader.mydomain.com
   ```

4. Save the file.
5. Back in the terminal: `docker compose up -d` (no `--build` needed).
6. Reload the admin page and click **Rotate token** — the QR regenerates with
   the new URL.

### Daily operation

- **See if it's running:** `docker compose ps`.
- **See what it's doing:** `docker compose logs -f app`. Press `Ctrl+C` to stop
  watching (the app keeps running).
- **Stop it:** `docker compose stop`.
- **Start it again:** `docker compose start`.
- **Turn off + delete containers but keep photos/settings:** `docker compose down`.
- **Kill EVERYTHING including your settings (nuclear):** `docker compose down -v`.

Your uploaded photos live in Immich, not here — the uploader only keeps its
own admin password and which-album-to-use settings. Those live in a Docker
volume called `app_data` and survive restarts and upgrades.

### Revoking access

Someone shared the QR with the wrong person? On the admin page click
**Rotate token**. The old QR stops working instantly. Print a new one.

### Troubleshooting

#### "I forgot the admin password."

```bash
docker compose exec app python -c "from app import db; db.delete('admin_user'); db.delete('admin_pass_hash'); print('admin reset — reload the page')"
```

Reload the page and go through Setup again. Your Immich connection and token
are preserved.

**"The QR page says 'Link invalid or expired'."** The token was rotated. Get
a fresh QR from the admin page.

**"Uploads fail with 'scanner unavailable'."** ClamAV is still downloading
virus definitions (check `docker compose logs clamav` — wait for "SelfCheck:
Database status OK"), or it crashed. `docker compose restart clamav`.

**"Uploads fail with 'immich: 401'."** Your Immich API key was revoked or
expired. Generate a new one in Immich and paste it into the admin page.

**"I want to move to a different computer."** Stop the app, copy the whole
folder, run `docker compose up -d --build` on the new computer. (To also keep
your admin login and album settings, also copy the Docker volume — ask
someone technical for this; easier to just set it up fresh.)

---

## For the tech-savvy: architecture

- **Backend**: FastAPI (Python 3.11+). SQLite for config. Session cookie
  admin auth. Admin credentials and the app's encryption key are created on
  first launch and live in `/data` inside the container.
- **Frontend**: React + Vite + TypeScript. Served by FastAPI in prod, Vite dev
  server in dev.
- **Scanner**: ClamAV via `clamd` (TCP). Falls back to VirusTotal API if
  `VT_API_KEY` is set and clamd is unreachable.
- **Access control**: one shared rotatable token at `/u/<token>`.

### Secrets model

On first run, if `data/secret.key` doesn't exist, the app generates a Fernet
key and writes it there (600 perms). That key is used to:

- sign admin session cookies,
- encrypt the stored Immich API key at rest.

`APP_SECRET` env var overrides the file — set it if you want to rotate keys
or keep the secret out of the volume. Admin credentials themselves are stored
bcrypt-hashed in the SQLite `config` table, created via the setup UI.

Deleting the `app_data` volume wipes both the secret file and the DB —
functionally equivalent to a factory reset.

### Bare-metal dev (no Docker)

Prereqs: Python 3.11+, Node 20+, `libmagic` (`brew install libmagic`), optional
ClamAV (`brew install clamav`, configure for TCP 3310).

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env    # optional
uvicorn app.main:app --reload --port 8000
```

```bash
# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173/admin> — the setup page is gated on having no
admin in the DB, so the first visit lands you on `/admin/setup`.

### Endpoints

- `GET  /api/admin/setup/needed` → `{setup_needed: bool}`
- `POST /api/admin/setup` — `{username, password}` (only if no admin yet)
- `POST /api/admin/login` — `{username, password}`
- `POST /api/admin/logout`
- `GET  /api/admin/me`
- `GET  /api/admin/config`
- `PUT  /api/admin/config` — `{immich_url, immich_api_key?, album_id, album_name?}`
- `POST /api/admin/albums` — `{immich_url, immich_api_key?}` → `[{id, albumName}]`
- `POST /api/admin/token/rotate`
- `POST /api/admin/password` — `{current, new}`
- `GET  /api/upload/status/{token}` — pre-flight album info
- `POST /api/upload` — multipart `file` + form `token`

### Testing

- Upload a clean image → appears in the target Immich album.
- Upload the [EICAR test file](https://www.eicar.org/download-anti-malware-testfile/)
  renamed to `.png` → **422 malware detected**.
- Visit `/u/<wrong-token>` → "Link invalid".
- Rotate token → the old URL stops working.

### Production notes

- Put behind HTTPS. Then flip `https_only=True` on the session cookie in
  `app/main.py`.
- `MAX_UPLOAD_MB` and rate-limit (10/min/IP) are tunable in `app/main.py` /
  `config.py`.
- SVG is rejected — it can carry script payloads that Immich's viewer would
  execute. Don't loosen the MIME allowlist without thinking about this.
