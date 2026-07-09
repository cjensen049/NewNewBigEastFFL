"""Calendar router — /api/calendar/* endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from backend.routers.db import get_db
from fantasy_analyzer.analysis.calendar_events import get_calendar_events

router = APIRouter()


@router.get("/events")
def calendar_events(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All league calendar events — drafts, regular seasons, playoffs, championships."""
    return {"events": get_calendar_events(con)}
