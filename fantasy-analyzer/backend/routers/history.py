"""History router — /api/history/* endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends, Query

from fantasy_analyzer.analysis.history import (
    get_all_seasons,
    get_all_time_standings,
    get_available_seasons,
    get_championship_rosters,
    get_division_order,
    get_league_records,
    get_season_breakdown,
    get_season_schedule,
    get_standings_history,
    get_weekly_scoring_extremes,
)
from fantasy_analyzer.analysis.start_sit import get_start_sit_leaderboard, get_start_sit_weeks

router = APIRouter()

# ---------------------------------------------------------------------------
# DB dependency — creates a new connection per request, closes when done
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league.db"


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a SQLite connection, close after request."""
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

FINISH_DISPLAY = {
    1: "Champion", 2: "Runner-up", 3: "3rd", 4: "4th",
    5: "5th", 6: "6th", 7: "7th", 8: "8th",
    9: "9th", 10: "10th", 11: "11th", 12: "12th",
}


@router.get("/standings")
def standings(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All-time cumulative standings for every owner."""
    records = get_all_time_standings(con)
    rows = []
    for rank, r in enumerate(records, 1):
        record_str = f"{r.reg_wins}-{r.reg_losses}"
        if r.reg_ties:
            record_str += f"-{r.reg_ties}"
        rows.append({
            "rank": rank,
            "owner": r.canonical_name,
            "seasons": r.seasons,
            "record": record_str,
            "win_pct": round(r.win_pct, 4),
            "total_pts": round(r.total_points, 1),
            "ppg": round(r.ppg, 1),
            "playoff_appearances": r.playoff_appearances,
            "championships": r.championships,
        })
    return {"standings": rows}


@router.get("/seasons")
def seasons(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """List of available season years, newest first."""
    years = sorted(get_available_seasons(con), reverse=True)
    return {"seasons": years}


@router.get("/seasons/complete")
def seasons_complete(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """List of seasons with a finished regular season + playoffs, newest first.

    Unlike /seasons (which includes the in-progress current season), this is
    for views that need the last season with real final standings — e.g.
    next year's division preview on the Schedule page.
    """
    years = sorted((s["season"] for s in get_all_seasons(con)), reverse=True)
    return {"seasons": years}


@router.get("/season/{year}")
def season_detail(year: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Regular-season standings and playoff finishes for a single season."""
    data = get_season_breakdown(con, year)
    if not data:
        return {"season": year, "standings": []}

    rows = []
    for seed, rec in enumerate(data["regular_season"], 1):
        playoff_entry = next(
            (r for r in data["playoff"].values() if r.canonical_name == rec.canonical_name),
            None,
        )
        if playoff_entry and playoff_entry.made_playoffs and playoff_entry.finish is not None:
            finish_label = FINISH_DISPLAY.get(playoff_entry.finish, f"{playoff_entry.finish}th")
        else:
            finish_label = "—"
        record_str = f"{rec.wins}-{rec.losses}"
        if rec.ties:
            record_str += f"-{rec.ties}"
        rows.append({
            "seed": seed,
            "owner": rec.canonical_name,
            "record": record_str,
            "win_pct": round(rec.win_pct, 4),
            "pts_for": round(rec.points_for, 1),
            "pts_against": round(rec.points_against, 1),
            "ppg": round(rec.ppg, 1),
            "finish": finish_label,
            "made_playoffs": playoff_entry.made_playoffs if playoff_entry else False,
        })
    return {"season": year, "standings": rows}


@router.get("/standings-history")
def standings_history(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Grid of each owner's final finish per season.
    Returns two shapes:
      rank_grid: {season → {finish_label → owner_name}}
      owner_grid: [{owner, seasons: {year → finish_label}}]
    """
    history = get_standings_history(con)
    seasons_sorted = sorted(history.keys())

    rank_grid = {}
    for season in seasons_sorted:
        rank_grid[str(season)] = {
            FINISH_DISPLAY.get(rank, str(rank)): name
            for rank, name in history[season].items()
        }

    all_owners = sorted({name for ranks in history.values() for name in ranks.values()})
    owner_grid = []
    for owner in all_owners:
        row: dict = {"owner": owner}
        for season in seasons_sorted:
            finish = next((rank for rank, name in history[season].items() if name == owner), None)
            row[str(season)] = FINISH_DISPLAY.get(finish, "—") if finish else "—"
        owner_grid.append(row)

    return {
        "seasons": [str(s) for s in seasons_sorted],
        "rank_grid": rank_grid,
        "owner_grid": owner_grid,
    }


@router.get("/finish-order/{year}")
def finish_order(year: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Return owners sorted by final finish position 1-12 for a completed season."""
    history = get_standings_history(con)
    if year not in history:
        return {"season": year, "teams": []}
    teams = [
        {"finish": rank, "owner": name}
        for rank, name in sorted(history[year].items())
    ]
    return {"season": year, "teams": teams}


@router.get("/division-order/{year}")
def division_order(year: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Next season's division order, for the Schedule page.

    Top 4 = actual playoff finish. Ranks 5-12 = pure regular-season record
    (not the toilet-bowl bracket, which can misrepresent a team's actual
    season). Names are resolved to whoever currently holds that roster, so
    a departed owner's old slot shows their replacement.
    """
    teams = get_division_order(con, year)
    return {"season": year, "teams": teams}


@router.get("/schedule/{year}")
def schedule(year: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Real per-week opponent for every owner, from Sleeper's published matchup pairings.

    Works even before any games are played — Sleeper publishes the full
    season's pairings up front, scores just default to 0 until played.
    """
    league = con.execute(
        "SELECT league_id, playoff_week_start FROM leagues WHERE season = ?",
        (year,),
    ).fetchone()
    if not league:
        return {"season": year, "weeks": 0, "schedule": {}}
    league_id, playoff_week_start = league
    sched = get_season_schedule(con, league_id, playoff_week_start)
    return {"season": year, "weeks": playoff_week_start - 1, "schedule": sched}


@router.get("/records")
def records(
    include_playoffs: bool = Query(False),
    con: sqlite3.Connection = Depends(get_db),
) -> dict:
    """League records (single-week highs, streaks, etc.)."""
    recs = get_league_records(con, include_playoffs=include_playoffs)
    return {"records": recs}


@router.get("/weekly-scoring")
def weekly_scoring(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Top/bottom single-week scores and weekly high/low count per owner."""
    data = get_weekly_scoring_extremes(con)
    high_counts = data["high_counts"]
    low_counts = data["low_counts"]
    all_owners = sorted(set(high_counts) | set(low_counts))
    count_rows = sorted(
        [
            {
                "owner": o,
                "high_weeks": high_counts.get(o, 0),
                "low_weeks": low_counts.get(o, 0),
            }
            for o in all_owners
        ],
        key=lambda r: -r["high_weeks"],
    )
    return {
        "top": data["top"],
        "bottom": data["bottom"],
        "counts": count_rows,
    }


@router.get("/start-sit")
def start_sit(
    season: int | None = Query(None, description="Omit for all-time"),
    include_playoffs: bool = Query(True),
    con: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Lineup efficiency leaderboard + per-week detail (actual vs. best-possible score).

    Best-possible score is computed from each week's full active-roster player
    pool (Sleeper never includes taxi-squad players in a week's matchup pool,
    so taxi is excluded automatically).
    """
    leaderboard = get_start_sit_leaderboard(con, season=season, include_playoffs=include_playoffs)
    weeks = get_start_sit_weeks(con, season=season, include_playoffs=include_playoffs)
    return {"season": season, "leaderboard": leaderboard, "weeks": weeks}


@router.get("/champions")
def champions(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Championship matchup details including starting lineups, newest first."""
    champ_data = get_championship_rosters(con)
    return {"champions": list(reversed(champ_data))}
