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
_WEEK_URL = "https://api.sleeper.app/projections/nfl/{season}/{week}?season_type=regular"


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


def fetch_bye_teams(con: sqlite3.Connection, season: int, week: int) -> list[str]:
    """Return NFL team abbreviations on a bye for one week.

    Sleeper doesn't publish a bye-week list directly, but a bye team's
    players are omitted entirely from that week's projections payload
    (not present with a null opponent) -- so this is "which of the known
    32 teams didn't show up this week" instead.
    """
    all_teams = {r[0] for r in con.execute("SELECT DISTINCT team FROM players WHERE team IS NOT NULL")}
    if not all_teams:
        return []

    try:
        resp = httpx.get(_WEEK_URL.format(season=season, week=week), timeout=30.0, verify=False)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Sleeper week %d projections fetch failed for bye detection: %s", week, e)
        return []

    teams_seen = set()
    for rec in resp.json() or []:
        # Skip fantasy-irrelevant players (O-linemen, inactive/practice-squad
        # names with no real projection) -- Sleeper sometimes carries stale
        # team tags for these that would otherwise look like a false signal.
        if (rec.get("stats") or {}).get("pts_ppr") is None:
            continue
        team = rec.get("team")
        if team:
            teams_seen.add(team)

    return sorted(all_teams - teams_seen)


def store_bye_teams(con: sqlite3.Connection, teams: list[str], season: int, week: int) -> int:
    """Upsert into nfl_byes. Returns count stored."""
    if not teams:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO nfl_byes (season, week, team) VALUES (?, ?, ?)",
        [(season, week, team) for team in teams],
    )
    con.commit()
    return len(teams)


def run_bye_week_scrape(con: sqlite3.Connection, season: int, week: int) -> int:
    """Fetch and store which NFL teams are on a bye for one week. Returns count stored."""
    log.info("Detecting bye-week teams for %d week %d", season, week)
    teams = fetch_bye_teams(con, season, week)
    stored = store_bye_teams(con, teams, season, week)
    log.info("Stored %d bye teams for %d week %d: %s", stored, season, week, teams)
    return stored
