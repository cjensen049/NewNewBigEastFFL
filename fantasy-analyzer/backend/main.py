"""NNBE Fantasy Football — FastAPI application entry point."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.routers import history, owner, h2h, transactions, in_season, draft, calendar
from fantasy_analyzer.db.schema import apply_migrations

# Resolve paths relative to the project root (fantasy-analyzer/)
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "league.db"

app = FastAPI(title="NNBE Fantasy Football API", version="1.0.0")


@app.on_event("startup")
async def run_migrations() -> None:
    """Apply any pending DB schema migrations on every server start."""
    await apply_migrations(str(DB_PATH))

# Allow the Vite dev server (port 5173) to call the API during development.
# In production, React is served by FastAPI itself so CORS is not needed,
# but we keep the dev origin here so both environments work.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict:
    """Railway health check endpoint."""
    return {"status": "ok"}


# Register all API routers
app.include_router(history.router, prefix="/api/history")
app.include_router(owner.router, prefix="/api/owners")
app.include_router(h2h.router, prefix="/api/h2h")
app.include_router(transactions.router, prefix="/api/transactions")
app.include_router(in_season.router, prefix="/api/in-season")
app.include_router(draft.router, prefix="/api/draft")
app.include_router(calendar.router, prefix="/api/calendar")

_frontend_dist = BASE_DIR / "frontend" / "dist"


@app.get("/{full_path:path}")
async def serve_react(full_path: str) -> FileResponse:
    """Serve the React SPA for all non-API paths (enables client-side routing).

    Serves actual static assets when they exist; falls back to index.html so
    React Router can handle the path on the client side.
    """
    static_file = _frontend_dist / full_path
    if static_file.is_file():
        return FileResponse(str(static_file))
    index = _frontend_dist / "index.html"
    if index.is_file():
        return FileResponse(str(index))
    return FileResponse(str(static_file))  # let OS raise the 404


# StaticFiles mount kept as a fallback for HEAD/OPTIONS and cache-header support.
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


def get_db() -> sqlite3.Connection:
    """Open and return a SQLite connection to the league database."""
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)
