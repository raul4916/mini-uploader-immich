from pathlib import Path

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import db
from .config import load_or_create_secret
from .routers import admin, upload

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    db.init_db()
    app_secret = load_or_create_secret()

    app = FastAPI(title="mini-uploader")

    _ip_hits: dict[str, deque[float]] = defaultdict(deque)
    _ip_lock = Lock()
    LIMIT = 10  # requests
    WINDOW = 60  # seconds

    @app.middleware("http")
    async def _rate_limit_upload(request: Request, call_next):
        if request.url.path == "/api/upload" and request.method == "POST":
            ip = request.client.host if request.client else "unknown"
            now = time.time()
            with _ip_lock:
                dq = _ip_hits[ip]
                while dq and now - dq[0] > WINDOW:
                    dq.popleft()
                if len(dq) >= LIMIT:
                    return JSONResponse({"detail": "rate limit"}, status_code=429)
                dq.append(now)
        return await call_next(request)

    app.add_middleware(
        SessionMiddleware,
        secret_key=app_secret,
        session_cookie="mu_sess",
        https_only=False,  # flip True behind HTTPS
        same_site="lax",
        max_age=60 * 60 * 24 * 7,
    )

    # Dev CORS for Vite on :5173
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin.router)
    app.include_router(upload.router)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/u/{token}")
    def upload_page(token: str, request: Request):
        stored = db.get("upload_token")
        if not stored or stored != token:
            raise HTTPException(status_code=404, detail="not found")
        return _spa_response()

    if STATIC_DIR.is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

        @app.get("/")
        def root():
            return _spa_response()

        @app.get("/admin")
        @app.get("/admin/{sub:path}")
        def admin_spa(sub: str | None = None):
            return _spa_response()

    return app


def _spa_response() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=500, detail="frontend not built — run: cd frontend && npm run build")
    return FileResponse(index)


app = create_app()
