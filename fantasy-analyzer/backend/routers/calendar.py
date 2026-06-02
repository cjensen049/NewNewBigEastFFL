"""Calendar router — /api/calendar/* endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends

from fantasy_analyzer.analysis.calendar_events import get_calendar_events

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league.db"


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a SQLite connection, close after request."""
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


@router.get("/events")
def calendar_events(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All league calendar events — drafts, regular seasons, playoffs, championships."""
    return {"events": get_calendar_events(con)}
