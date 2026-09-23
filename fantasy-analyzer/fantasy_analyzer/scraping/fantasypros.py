"""Sleeper current-roster refresh.

FantasyPros used to be scraped here too, but its free weekly projections
page only exposes the top 10 players per position (the rest requires their
paid MVP tier) -- replaced by Sleeper's own per-week and season-long
projections (see sleeper_projections.py), which have no such cap.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

_SLEEPER_ROSTERS_URL = "https://api.sleeper.app/v1/league/{league_id}/rosters"


def fetch_current_rosters(league_id: str) -> list[dict]:
    """Pull current roster player lists from the Sleeper API."""
    url = _SLEEPER_ROSTERS_URL.format(league_id=league_id)
    try:
        # verify=False: public read-only Sleeper API (Windows SSL cert issue)
        resp = httpx.get(url, timeout=30.0, verify=False)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.error("Failed to fetch rosters from Sleeper: %s", e)
        return []

    entries: list[dict] = []
    for roster in resp.json() or []:
        roster_id = roster.get("roster_id")
        if not roster_id:
            continue

        all_players = set(roster.get("players") or [])
        taxi      = set(roster.get("taxi")    or [])
        reserve   = set(roster.get("reserve") or [])

        for player_id in all_players:
            if player_id in taxi:
                status = "taxi"
            elif player_id in reserve:
                status = "reserve"
            else:
                status = "active"
            entries.append(
                {"roster_id": roster_id, "player_id": player_id, "status": status}
            )

    return entries


def update_current_rosters(con: sqlite3.Connection, league_id: str) -> int:
    """Replace current_rosters for this league with fresh Sleeper data.

    Returns number of player-roster records written.
    """
    entries = fetch_current_rosters(league_id)
    if not entries:
        log.warning("No roster data returned for league %s", league_id)
        return 0

    now = datetime.now(timezone.utc).isoformat()

    con.execute("DELETE FROM current_rosters WHERE league_id = ?", (league_id,))
    con.executemany(
        """INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        [(league_id, e["roster_id"], e["player_id"], e["status"], now) for e in entries],
    )
    con.commit()

    log.info("Updated %d roster entries for league %s", len(entries), league_id)
    return len(entries)
