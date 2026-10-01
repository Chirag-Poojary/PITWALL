"""PITWALL — FastAPI application entry point.

Serves the JSON API under /api and the built React app (frontend/dist) for every
other path, so one process runs the whole project.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import auth, db, ml
from .data import get_data
from .routes_admin import router as admin_router
from .routes_fan import router as fan_router

DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    auth.seed_admin()
    yield


app = FastAPI(title="PITWALL F1 API", version="1.0.0", lifespan=lifespan)

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins_env == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(auth.router)
app.include_router(fan_router)
app.include_router(admin_router)


@app.get("/api/health")
def health():
    return {"ok": True, "models": ml.status()["status"]}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
def api_404(path: str):
    return JSONResponse({"detail": "Not found"}, status_code=404)


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"])
    def spa(path: str):
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        if path.startswith("media/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return FileResponse(DIST / "index.html")
