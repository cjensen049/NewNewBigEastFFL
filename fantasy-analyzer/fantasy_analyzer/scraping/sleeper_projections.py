"""Sleeper's undocumented player projections -- season-long and per-week.

FantasyPros' free weekly projections page only exposes the top 10 players
per position (the rest requires their paid MVP tier), which can't cover a
full ~25-man dynasty roster. Sleeper's own projections -- the same data
their app shows -- have no such cap and already cover essentially every
rostered player, with no extra scraping/auth needed.

Season-long (rest-of-season, divided to a per-game rate) is used as the
roster-quality prior in power rankings -- a stable long-run team-strength
signal. Per-week is used for anything that needs THIS week's reality (an
injured/doubtful player has no `pts_ppr` at all that week, rather than a
healthy season average) -- the Weekly Preview panel's projected matchup
totals and bye-week detection.

Every projected point total stored here is rebuilt from Sleeper's projected STAT
LINE (yards, TDs, receptions, ...) under the league's own scoring_settings, never
Sleeper's ready-made `pts_ppr`. For quarterbacks in its older weekly feeds, `pts_ppr`
includes ~2 points a game of pass-first-down credit that NNBE (and the actual
scores) never award, which made every QB read as an under-performer.
`pts_ppr` is only used as the marker that a real projection exists: retired or
released players have a record with no projected stats at all.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

_URL = "https://api.sleeper.app/projections/nfl/{season}?season_type=regular"
_WEEK_URL = "https://api.sleeper.app/projections/nfl/{season}/{week}?season_type=regular"
_LEAGUE_URL = "https://api.sleeper.app/v1/league/{league_id}"

# NNBE's scoring (identical in every season 2021-2026). Only used if the league's settings
# can't be fetched, so a Sleeper hiccup can't quietly change how projections are scored.
DEFAULT_SCORING: dict[str, float] = {
    "pass_yd": 0.04, "pass_td": 4.0, "pass_int": -1.0, "pass_2pt": 2.0,
    "rush_yd": 0.1, "rush_td": 6.0, "rush_2pt": 2.0,
    "rec": 1.0, "rec_yd": 0.1, "rec_td": 6.0, "rec_2pt": 2.0,
    "fum_lost": -2.0, "fum_rec_td": 6.0, "st_td": 6.0,
}


def fetch_scoring_settings(league_id: str) -> dict[str, float]:
    """The league's scoring rules ({stat: points}, non-zero only), from Sleeper.

    Falls back to DEFAULT_SCORING (with a warning) if the league can't be fetched.
    """
    try:
        resp = httpx.get(_LEAGUE_URL.format(league_id=league_id), timeout=30.0, verify=False)
        resp.raise_for_status()
        settings = resp.json().get("scoring_settings") or {}
    except (httpx.HTTPError, ValueError) as e:
        log.warning("Couldn't fetch scoring settings for league %s (%s); using NNBE defaults", league_id, e)
        return dict(DEFAULT_SCORING)
    scoring = {k: round(float(v), 4) for k, v in settings.items() if isinstance(v, (int, float)) and v}
    return scoring or dict(DEFAULT_SCORING)


def score_stats(stats: dict, scoring: dict[str, float]) -> float:
    """Fantasy points for a (projected) stat line under the given scoring rules."""
    return sum(float(stats.get(stat) or 0.0) * pts for stat, pts in scoring.items())


def fetch_season_projections(season: int, scoring: dict[str, float]) -> list[dict]:
    """Return [{player_id, position, projected_pts}] for every projected player,
    scored under `scoring` (see score_stats)."""
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
            "projected_pts": score_stats(stats, scoring) / float(gp),
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


def run_season_projections_scrape(con: sqlite3.Connection, season: int, scoring: dict[str, float]) -> int:
    """Fetch and store Sleeper's rest-of-season projections. Returns count stored."""
    log.info("Fetching Sleeper season-long projections for %d", season)
    projections = fetch_season_projections(season, scoring)
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


def fetch_week_projections(season: int, week: int, scoring: dict[str, float]) -> list[dict]:
    """Return [{player_id, position, projected_pts}] for this specific week, scored under
    `scoring` (see score_stats).

    Unlike the season-long projection, this reflects THIS week's reality --
    a player ruled out or doubtful with an injury has no `pts_ppr` at all
    (rather than a healthy season average), so hurt players correctly drop
    out of a "who's projected to start" or "projected matchup total" view.
    """
    try:
        resp = httpx.get(_WEEK_URL.format(season=season, week=week), timeout=30.0, verify=False)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Sleeper week %d projections fetch failed for %d: %s", week, season, e)
        return []

    results = []
    for rec in resp.json() or []:
        pid = rec.get("player_id")
        stats = rec.get("stats") or {}
        position = (rec.get("player") or {}).get("position")
        if not pid or stats.get("pts_ppr") is None or not position:
            continue   # no projected stat line (injured/out, or retired and since dropped)
        results.append({
            "player_id": pid,
            "position": position,
            "projected_pts": score_stats(stats, scoring),
        })
    return results


def store_week_projections(con: sqlite3.Connection, projections: list[dict], season: int, week: int) -> int:
    """Upsert into player_projections. Returns count stored.

    Only ever adds or updates rows, never deletes: the stored weeks are the permanent
    record. Sleeper's feed later drops players who retire or get released (that's how
    Tom Brady's 2021 ended up with no projections), so a week must be saved while
    its players are still listed, and a later re-fetch must not remove what we saved.
    """
    if not projections:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        """INSERT INTO player_projections (season, week, player_id, position, projected_pts, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(season, week, player_id) DO UPDATE SET
               position      = excluded.position,
               projected_pts = excluded.projected_pts,
               scraped_at    = excluded.scraped_at""",
        [(season, week, p["player_id"], p["position"], p["projected_pts"], now) for p in projections],
    )
    con.commit()
    return len(projections)


def run_week_projections_scrape(con: sqlite3.Connection, season: int, week: int, scoring: dict[str, float]) -> int:
    """Fetch and store Sleeper's this-week projections. Returns count stored."""
    log.info("Fetching Sleeper week %d projections for %d", week, season)
    projections = fetch_week_projections(season, week, scoring)
    stored = store_week_projections(con, projections, season, week)
    log.info("Stored %d week %d projections for %d", stored, week, season)
    return stored
