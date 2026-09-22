"""Sleeper's undocumented rest-of-season player projections.

Used as the roster-quality prior in power rankings. FantasyPros' free
weekly projections page only exposes the top 10 players per position (the
rest requires their paid MVP tier), which can't cover a full ~25-man
dynasty roster. Sleeper's own season-long projection -- the same data
their app shows -- has no such cap and already covers essentially every
rostered player, with no extra scraping/auth needed.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

_URL = "https://api.sleeper.app/projections/nfl/{season}?season_type=regular"


def fetch_season_projections(season: int) -> list[dict]:
    """Return [{player_id, position, projected_pts}] for every projected player."""
    try:
        # verify=False: public read-only API (Windows SSL cert issue), same as fantasypros.py
        resp = httpx.get(_URL.format(season=season), timeout=30.0, verify=False)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Sleeper season projections fetch failed for %d: %s", season, e)
        return []

    results = []
    for rec in resp.json() or []:
        pid = rec.get("player_id")
        stats = rec.get("stats") or {}
        pts = stats.get("pts_ppr")
        gp = stats.get("gp")
        if not pid or pts is None or not gp:
            continue
        results.append({
            "player_id": pid,
            "position": (rec.get("player") or {}).get("position"),
            # Sleeper's number here is a season total (rest-of-season, ~18 games) --
            # divide down to a per-game rate so it's on the same scale as a team's
            # weekly scoring average, which is what this gets blended against.
            "projected_pts": float(pts) / float(gp),
        })
    return results


def store_season_projections(con: sqlite3.Connection, projections: list[dict], season: int) -> int:
    """Upsert into player_season_projections. Returns count stored."""
    if not projections:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        """INSERT INTO player_season_projections (season, player_id, position, projected_pts, scraped_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(season, player_id) DO UPDATE SET
               position      = excluded.position,
               projected_pts = excluded.projected_pts,
               scraped_at    = excluded.scraped_at""",
        [(season, p["player_id"], p["position"], p["projected_pts"], now) for p in projections],
    )
    con.commit()
    return len(projections)


def run_season_projections_scrape(con: sqlite3.Connection, season: int) -> int:
    """Fetch and store Sleeper's rest-of-season projections. Returns count stored."""
    log.info("Fetching Sleeper season-long projections for %d", season)
    projections = fetch_season_projections(season)
    stored = store_season_projections(con, projections, season)
    log.info("Stored %d season-long projections for %d", stored, season)
    return stored
