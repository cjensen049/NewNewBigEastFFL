"""Draft router — /api/draft/* endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.routers.db import get_db
from fantasy_analyzer.analysis.draft import (
    get_draft_board,
    get_draft_seasons,
    get_owner_picks_with_points,
    get_owners_with_picks,
)

router = APIRouter()


@router.get("/seasons")
def draft_seasons(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """List of seasons that have draft data."""
    return {"seasons": get_draft_seasons(con)}


@router.get("/board/{season}")
def draft_board(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All picks for one season, with slot→owner mapping for grid display."""
    data = get_draft_board(con, season)
    if not data["picks"]:
        raise HTTPException(status_code=404, detail=f"No draft data for season {season}")
    return data


@router.get("/owners")
def draft_owners(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Owners who have at least one draft pick."""
    return {"owners": get_owners_with_picks(con)}


@router.get("/owner/{user_id}")
def owner_draft(user_id: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All picks by one owner with fantasy points scored while on their roster."""
    return {"user_id": user_id, "picks": get_owner_picks_with_points(con, user_id)}
