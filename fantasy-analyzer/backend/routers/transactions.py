"""Transactions router — /api/transactions/* endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends, Query

from fantasy_analyzer.analysis.transactions import (
    build_deep_trade_tree,
    get_all_traded_players,
    get_faab_records,
    get_owner_trade_stats,
    get_owner_waiver_activity,
    get_owner_waiver_by_season,
    get_player_add_drop_stats,
    get_trade_log,
    get_trade_partner_matrix,
    TreeNode,
)

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league.db"


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a SQLite connection, close after request."""
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


def _serialize_tree_node(node: TreeNode) -> dict:
    """Recursively convert a TreeNode into a JSON-serializable dict."""
    return {
        "asset_name": node.asset_name,
        "asset_type": node.asset_type,
        "from_owner": node.from_owner,
        "to_owner": node.to_owner,
        "season": node.season,
        "week": node.week,
        "children": [_serialize_tree_node(c) for c in node.children],
    }


@router.get("/trades")
def trade_log(
    season: int | None = Query(None),
    owner: str | None = Query(None),
    con: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Full trade log with optional season and/or owner filter."""
    trades = get_trade_log(con)
    if season is not None:
        trades = [t for t in trades if t.season == season]
    if owner:
        trades = [t for t in trades if owner in t.owners]

    rows = []
    for t in trades:
        players = [
            {
                "name": a.asset_name,
                "from_owner": a.from_owner,
                "to_owner": a.to_owner,
            }
            for a in t.assets if a.asset_type == "player"
        ]
        picks = [
            {
                "name": a.asset_name,
                "from_owner": a.from_owner,
                "to_owner": a.to_owner,
            }
            for a in t.assets if a.asset_type == "pick"
        ]
        rows.append({
            "season": t.season,
            "week": t.week,
            "owners": t.owners,
            "players": players,
            "picks": picks,
        })
    return {"trades": rows}


@router.get("/trade-stats")
def trade_stats(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Per-owner trade statistics and the trade-partner frequency matrix."""
    stats = get_owner_trade_stats(con)
    matrix = get_trade_partner_matrix(con)
    owners = sorted(
        r[0] for r in con.execute("SELECT canonical_name FROM owners").fetchall()
    )

    stats_rows = [
        {
            "owner": s.canonical_name,
            "total_trades": s.total_trades,
            "players_in": s.players_acquired,
            "players_out": s.players_sent,
            "picks_in": s.picks_acquired,
            "picks_out": s.picks_sent,
            "waiver_claims": s.total_waiver_claims,
            "fa_adds": s.total_fa_adds,
            "faab_spent": s.total_faab_spent,
        }
        for s in stats
    ]

    # Build the heatmap matrix as a 2D array
    heatmap = []
    for o1 in owners:
        row = []
        for o2 in owners:
            if o1 == o2:
                row.append(0)
            else:
                pair = tuple(sorted([o1, o2]))
                row.append(matrix.get(pair, 0))
        heatmap.append(row)

    return {"stats": stats_rows, "owners": owners, "heatmap": heatmap}


@router.get("/traded-players")
def traded_players(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Alphabetical list of all player names that have appeared in trades."""
    players = get_all_traded_players(con)
    return {"players": players}


@router.get("/trade-tree/{player_name}")
def trade_tree(player_name: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Deep trade tree for a player — follows the asset through all subsequent trades
    and draft picks. Returns the canonical player name and a list of root trade nodes.
    """
    full_name, nodes = build_deep_trade_tree(con, player_name)
    return {
        "player": full_name,
        "trades": [_serialize_tree_node(n) for n in nodes],
    }


@router.get("/waivers/faab")
def faab_records(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """FAAB records: top bids, most total FAAB per player, owner totals."""
    return get_faab_records(con)


@router.get("/waivers/players")
def waiver_players(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Player add/drop stats (most added, most dropped, revolving door)."""
    stats = get_player_add_drop_stats(con)
    return {"players": stats}


@router.get("/waivers/activity")
def waiver_activity(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """All-time waiver wire activity summary per owner."""
    activity = get_owner_waiver_activity(con)
    # Filter out placeholder owners with no activity
    activity = [o for o in activity if o["total_adds"] > 0 and o["owner"] != "John"]
    return {"activity": activity}


@router.get("/waivers/by-season")
def waiver_by_season(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Per-owner waiver activity broken out by season."""
    data = get_owner_waiver_by_season(con)
    seasons = sorted({r["season"] for r in data}, reverse=True)
    return {"by_season": data, "seasons": seasons}
