"""NNBE Fantasy Football — FastAPI application entry point."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import history, owner, h2h, transactions, in_season

# Resolve paths relative to the project root (fantasy-analyzer/)
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "league.db"

app = FastAPI(title="NNBE Fantasy Football API", version="1.0.0")

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

# Register all API routers
app.include_router(history.router, prefix="/api/history")
app.include_router(owner.router, prefix="/api/owners")
app.include_router(h2h.router, prefix="/api/h2h")
app.include_router(transactions.router, prefix="/api/transactions")
app.include_router(in_season.router, prefix="/api/in-season")

# In production, serve the built React app as static files.
# This mount must come LAST — it catches everything not matched by the API routes.
_frontend_dist = BASE_DIR / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")


def get_db() -> sqlite3.Connection:
    """Open and return a SQLite connection to the league database."""
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)
