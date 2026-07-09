"""Head-to-head router — /api/h2h/* endpoints."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from backend.routers.db import get_db
from fantasy_analyzer.analysis.history import get_h2h_matrix, get_playoff_records
from fantasy_analyzer.analysis.rivalries import get_nemesis_prey, get_rivalry_pairs

router = APIRouter()


@router.get("/matchups")
def matchups(
    owner1: str = Query(...),
    owner2: str = Query(...),
    con: sqlite3.Connection = Depends(get_db),
) -> dict:
    """All regular-season matchups between two owners."""
    rows = con.execute(
        """
        SELECT m1.season, m1.week, m1.points, m2.points
        FROM matchups m1
        JOIN matchups m2
          ON m1.league_id = m2.league_id
         AND m1.week = m2.week
         AND m1.matchup_id = m2.matchup_id
         AND m1.user_id != m2.user_id
        JOIN owners o1 ON m1.user_id = o1.user_id
        JOIN owners o2 ON m2.user_id = o2.user_id
        JOIN leagues l ON m1.league_id = l.league_id
        WHERE o1.canonical_name = ?
          AND o2.canonical_name = ?
          AND m1.week < l.playoff_week_start
          AND NOT (m1.points = 0 AND m2.points = 0)
        ORDER BY m1.season, m1.week
        """,
        (owner1, owner2),
    ).fetchall()

    if not rows:
        return {"owner1": owner1, "owner2": owner2, "matchups": []}

    matchup_rows = [
        {
            "season": season,
            "week": week,
            "pts1": round(pts1, 2),
            "pts2": round(pts2, 2),
            "winner": owner1 if pts1 > pts2 else (owner2 if pts2 > pts1 else "Tie"),
        }
        for season, week, pts1, pts2 in rows
    ]

    pts1_list = [r["pts1"] for r in matchup_rows]
    pts2_list = [r["pts2"] for r in matchup_rows]
    wins1 = sum(1 for r in matchup_rows if r["winner"] == owner1)
    wins2 = sum(1 for r in matchup_rows if r["winner"] == owner2)
    ties = sum(1 for r in matchup_rows if r["winner"] == "Tie")

    return {
        "owner1": owner1,
        "owner2": owner2,
        "wins1": wins1,
        "wins2": wins2,
        "ties": ties,
        "avg_pts1": round(sum(pts1_list) / len(pts1_list), 1),
        "avg_pts2": round(sum(pts2_list) / len(pts2_list), 1),
        "matchups": matchup_rows,
    }


@router.get("/matrix")
def h2h_matrix(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Full 12×12 head-to-head win matrix.
    Returns all_owners (sorted list) and matrix (dict of {owner: {opponent: wins}}).
    """
    matrix = get_h2h_matrix(con)
    owners = sorted(
        r[0] for r in con.execute("SELECT canonical_name FROM owners").fetchall()
    )

    # Build a nested dict: matrix_out[row_owner][col_owner] = "W-L"
    matrix_out: dict[str, dict[str, str]] = {}
    for row_owner in owners:
        matrix_out[row_owner] = {}
        for col_owner in owners:
            if row_owner == col_owner:
                matrix_out[row_owner][col_owner] = "—"
            else:
                w = matrix.get((row_owner, col_owner), 0)
                l = matrix.get((col_owner, row_owner), 0)
                matrix_out[row_owner][col_owner] = f"{w}-{l}"

    return {"owners": owners, "matrix": matrix_out}


@router.get("/playoff-records")
def playoff_records(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All-time playoff records per owner."""
    recs = get_playoff_records(con)
    rows = []
    for ps in recs:
        w_pct = round(ps.win_pct, 4) if ps.games else None
        record_str = f"{ps.playoff_wins}-{ps.playoff_losses}"
        rows.append({
            "owner": ps.canonical_name,
            "appearances": ps.appearances,
            "byes": ps.byes,
            "record": record_str,
            "win_pct": w_pct,
            "championships": ps.championships,
            "runner_up": ps.runner_up,
        })
    return {"records": rows}


@router.get("/rivalries")
def rivalries(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All rivalry pairs sorted by rivalry score (most games + closest record)."""
    pairs = get_rivalry_pairs(con)
    rows = [
        {
            "owner_a": p.owner_a,
            "owner_b": p.owner_b,
            "a_wins": p.a_wins,
            "b_wins": p.b_wins,
            "total_games": p.total_games,
            "leader": p.leader() or "Tied",
            "rivalry_score": round(p.rivalry_score, 2),
        }
        for p in pairs
    ]

    lopsided = sorted(
        [r for r in rows if r["total_games"] >= 4],
        key=lambda r: (
            -abs(r["a_wins"] - r["b_wins"]) / r["total_games"],
            -r["total_games"],
        ),
    )

    return {
        "rivalries": rows[:10],
        "lopsided": lopsided[:10],
        "all_pairs": rows,
    }


@router.get("/nemesis-prey")
def nemesis_prey(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Nemesis (worst record against) and prey (best record against) for each owner."""
    data = get_nemesis_prey(con)
    return {"nemesis_prey": data}
