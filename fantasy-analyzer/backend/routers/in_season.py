"""In-Season router — /api/in-season/* endpoints."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends

from fantasy_analyzer.analysis.history import (
    compute_luck_scores,
    get_all_seasons,
    get_all_time_luck,
    get_available_seasons,
    get_race_to_bottom,
    get_rtb_history,
    get_standings_snapshot,
)
from fantasy_analyzer.analysis.power_rankings import compute_power_rankings
from fantasy_analyzer.analysis.dynasty_rankings import compute_dynasty_rankings

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league.db"


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a SQLite connection, close after request."""
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


def _luck_verdict(diff: float) -> str:
    """Convert a luck diff value to a human-readable verdict."""
    if diff >= 1.5:   return "Very Lucky"
    if diff >= 0.5:   return "Lucky"
    if diff >= -0.5:  return "Average"
    if diff >= -1.5:  return "Unlucky"
    return "Very Unlucky"


@router.get("/seasons")
def luck_seasons(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """List of available seasons for in-season tools."""
    seasons = sorted(get_available_seasons(con), reverse=True)
    return {"seasons": seasons}


@router.get("/snapshot/{season}")
def standings_snapshot(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Standings snapshot: luck scores + next opponent + remaining SoS for the home page."""
    row = con.execute(
        "SELECT league_id, playoff_week_start FROM leagues WHERE season = ?", (season,)
    ).fetchone()
    if not row:
        return {"season": season, "current_week": 0, "next_week": None, "rows": []}
    result = get_standings_snapshot(con, row[0], season, row[1])
    return result if result else {"season": season, "current_week": 0, "next_week": None, "rows": []}


@router.get("/luck/all-time")
def luck_all_time(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Aggregated luck scores across all seasons per owner."""
    all_luck = get_all_time_luck(con)

    agg: dict[str, dict] = defaultdict(lambda: {
        "luck": 0.0, "seasons": 0,
        "aw": 0, "al": 0, "at": 0,
        "sw": 0, "sl": 0, "st": 0,
    })
    for r in all_luck:
        o = r["owner"]
        agg[o]["luck"] += r["luck_diff"]
        agg[o]["seasons"] += 1
        agg[o]["aw"] += r["actual_wins"]
        agg[o]["al"] += r["actual_losses"]
        agg[o]["at"] += r["actual_ties"]
        agg[o]["sw"] += r["sim_wins"]
        agg[o]["sl"] += r["sim_losses"]
        agg[o]["st"] += r["sim_ties"]

    out = []
    for owner, d in sorted(agg.items(), key=lambda x: -x[1]["luck"]):
        ag = d["aw"] + d["al"] + d["at"]
        sg = d["sw"] + d["sl"] + d["st"]
        actual_wp = (d["aw"] + 0.5 * d["at"]) / ag if ag else 0.0
        sim_wp = (d["sw"] + 0.5 * d["st"]) / sg if sg else 0.0
        out.append({
            "owner": owner,
            "actual_record": f"{d['aw']}-{d['al']}",
            "actual_win_pct": round(actual_wp, 4),
            "sim_record": f"{d['sw']}-{d['sl']}",
            "sim_win_pct": round(sim_wp, 4),
            "win_pct_diff": round(actual_wp - sim_wp, 4),
            "total_luck": round(d["luck"], 2),
            "verdict": _luck_verdict(d["luck"] / d["seasons"] if d["seasons"] else 0),
        })
    return {"rows": out}


@router.get("/luck/{season}")
def luck_by_season(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Luck-o-Meter scores for a single season."""
    row = con.execute(
        "SELECT league_id, playoff_week_start FROM leagues WHERE season = ?", (season,)
    ).fetchone()
    if not row:
        return {"season": season, "rows": []}

    luck_rows = compute_luck_scores(con, row[0], season, row[1])
    out = []
    for r in luck_rows:
        actual_win_pct = r["actual_win_pct"]
        sim_win_pct = r["sim_win_pct"]
        out.append({
            "owner": r["owner"],
            "actual_wins": r["actual_wins"],
            "actual_losses": r["actual_losses"],
            "actual_win_pct": round(actual_win_pct, 4),
            "sim_wins": r["sim_wins"],
            "sim_losses": r["sim_losses"],
            "sim_win_pct": round(sim_win_pct, 4),
            "win_pct_diff": round(actual_win_pct - sim_win_pct, 4),
            "luck_diff": round(r["luck_diff"], 2),
            "verdict": _luck_verdict(r["luck_diff"]),
        })
    return {"season": season, "rows": out}


@router.get("/dynasty-rankings/{season}")
def dynasty_rankings(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Dynasty power rankings: roster value + draft capital + age curve."""
    row = con.execute(
        "SELECT league_id FROM leagues WHERE season = ?", (season,)
    ).fetchone()
    if not row:
        return {"season": season, "data_date": None, "rows": []}
    return compute_dynasty_rankings(con, row[0], season)


@router.get("/power-rankings/{season}")
def power_rankings(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Power rankings for the current season with playoff odds via Monte Carlo."""
    row = con.execute(
        "SELECT league_id, playoff_week_start FROM leagues WHERE season = ?", (season,)
    ).fetchone()
    if not row:
        return {"season": season, "current_week": 0, "rows": []}
    return compute_power_rankings(con, row[0], season, row[1])


@router.get("/rtb/{season}")
def rtb_by_season(season: int, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Race to the Bottom standings for a single season."""
    rows = get_race_to_bottom(con, season)
    return {"season": season, "rows": rows}


@router.get("/rtb/history")
def rtb_history(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Historical Race to the Bottom results across all seasons."""
    all_rtb = get_rtb_history(con)
    if not all_rtb:
        return {"rows": [], "seasons": [], "owner_grid": []}

    # Build owner-level summary
    owner_data: dict[str, dict] = defaultdict(lambda: {"seasons": [], "picks": [], "optimal_pts": []})
    for r in all_rtb:
        owner_data[r["owner"]]["seasons"].append(r["season"])
        owner_data[r["owner"]]["picks"].append(r["draft_pick"])
        owner_data[r["owner"]]["optimal_pts"].append(r["optimal_pts"])

    summary = []
    for owner, d in owner_data.items():
        picks = d["picks"]
        summary.append({
            "owner": owner,
            "appearances": len(d["seasons"]),
            "best_pick": f"#{min(picks)}",
            "avg_pick": f"#{sum(picks) / len(picks):.1f}",
            "seasons": ", ".join(str(s) for s in sorted(d["seasons"])),
        })
    summary.sort(key=lambda r: -r["appearances"])

    # Build season-by-season pick grid
    seasons_sorted = sorted({r["season"] for r in all_rtb})
    owners_sorted = sorted(owner_data.keys())
    owner_grid = []
    for owner in owners_sorted:
        row: dict = {"owner": owner}
        pick_by_season = dict(zip(owner_data[owner]["seasons"], owner_data[owner]["picks"]))
        for s in seasons_sorted:
            row[str(s)] = f"#{pick_by_season[s]}" if s in pick_by_season else "—"
        owner_grid.append(row)

    return {
        "rows": all_rtb,
        "seasons": [str(s) for s in seasons_sorted],
        "summary": summary,
        "owner_grid": owner_grid,
    }
