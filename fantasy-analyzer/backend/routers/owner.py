"""Owner router — /api/owners/* endpoints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

import httpx
from fastapi import APIRouter, Depends, Query

# Simple in-memory avatar cache so we don't call Sleeper on every request
_avatar_cache: dict[str, str] = {}  # canonical_name -> avatar_url

from fantasy_analyzer.analysis.history import (
    get_all_time_standings,
    get_available_seasons,
    get_season_breakdown,
    get_owner_top_players,
)
from fantasy_analyzer.analysis.transactions import (
    get_trade_log,
    get_owner_waiver_log,
)

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "league.db"

FINISH_DISPLAY = {
    1: "Champion", 2: "Runner-up", 3: "3rd", 4: "4th",
    5: "5th", 6: "6th", 7: "7th", 8: "8th",
    9: "9th", 10: "10th", 11: "11th", 12: "12th",
}


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency: yield a SQLite connection, close after request."""
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    try:
        yield con
    finally:
        con.close()


@router.get("/")
def list_owners(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Return all owner canonical names, sorted alphabetically."""
    rows = con.execute(
        "SELECT canonical_name FROM owners ORDER BY canonical_name"
    ).fetchall()
    return {"owners": [r[0] for r in rows]}


@router.get("/avatars")
def owner_avatars(con: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Return Sleeper avatar URLs for all owners.
    Results are cached in memory after the first call.
    Avatar URL format: https://sleepercdn.com/avatars/thumbs/{avatar_id}
    """
    global _avatar_cache
    if _avatar_cache:
        return {"avatars": _avatar_cache}

    owners = con.execute("SELECT user_id, canonical_name FROM owners").fetchall()
    result: dict[str, str] = {}
    for user_id, name in owners:
        try:
            resp = httpx.get(
                f"https://api.sleeper.app/v1/user/{user_id}",
                timeout=5,
                verify=False,
            )
            resp.raise_for_status()
            avatar = resp.json().get("avatar")
            if avatar:
                result[name] = f"https://sleepercdn.com/avatars/thumbs/{avatar}"
        except Exception:
            pass  # skip if Sleeper is unreachable

    _avatar_cache = result
    return {"avatars": result}


@router.get("/{name}")
def owner_profile(name: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """
    Career summary + per-season breakdown for a single owner.
    Returns career metrics (record, win%, PPG, championships, etc.)
    and a list of season rows.
    """
    seasons = get_available_seasons(con)

    # Load owner's active range from DB
    owner_meta = con.execute(
        "SELECT joined_season, departed_after FROM owners WHERE canonical_name = ?", (name,)
    ).fetchone()
    joined_season = owner_meta[0] if owner_meta else None
    departed_after = owner_meta[1] if owner_meta else None

    season_rows = []
    total_wins = total_losses = total_ties = total_games = 0
    total_pts = total_pts_against = 0.0
    playoff_apps = championships = 0
    best_finish = worst_finish = None

    for season in sorted(seasons):
        # Skip seasons outside the owner's active window
        if joined_season is not None and season < joined_season:
            continue
        if departed_after is not None and season > departed_after:
            continue

        data = get_season_breakdown(con, season)
        if not data:
            continue

        rec = next((r for r in data["regular_season"] if r.canonical_name == name), None)
        if not rec:
            continue

        # Skip pre-season placeholder rows (no games played, no points scored)
        if rec.wins == 0 and rec.losses == 0 and rec.points_for == 0:
            continue

        seed = next(
            (i + 1 for i, r in enumerate(data["regular_season"]) if r.canonical_name == name),
            None,
        )
        playoff_entry = next(
            (r for r in data["playoff"].values() if r.canonical_name == name), None
        )

        if playoff_entry and playoff_entry.made_playoffs and playoff_entry.finish is not None:
            finish = playoff_entry.finish
            finish_label = FINISH_DISPLAY.get(finish, f"{finish}th")
        else:
            finish = seed
            finish_label = "—"

        record_str = f"{rec.wins}-{rec.losses}"
        if rec.ties:
            record_str += f"-{rec.ties}"

        season_rows.append({
            "season": season,
            "seed": seed,
            "record": record_str,
            "win_pct": round(rec.win_pct, 4),
            "pts_for": round(rec.points_for, 1),
            "pts_against": round(rec.points_against, 1),
            "ppg": round(rec.ppg, 1),
            "finish": finish_label,
        })

        total_wins += rec.wins
        total_losses += rec.losses
        total_ties += rec.ties
        total_pts += rec.points_for
        total_pts_against += rec.points_against
        total_games += rec.games

        if playoff_entry:
            if playoff_entry.made_playoffs:
                playoff_apps += 1
            if playoff_entry.champion:
                championships += 1
        if finish is not None:
            if best_finish is None or finish < best_finish:
                best_finish = finish
            if worst_finish is None or finish > worst_finish:
                worst_finish = finish

    if not season_rows:
        return {"error": f"No data found for '{name}'"}

    overall_win_pct = (total_wins + 0.5 * total_ties) / total_games if total_games else 0.0

    all_trades = get_trade_log(con)
    total_trades = sum(1 for t in all_trades if name in t.owners)

    top_players = get_owner_top_players(con, name)
    top_player_str = (
        f"{top_players[0]['player']} ({top_players[0]['total_pts']} pts)"
        if top_players
        else "—"
    )

    record_str = f"{total_wins}-{total_losses}"
    if total_ties:
        record_str += f"-{total_ties}"

    career = {
        "record": record_str,
        "win_pct": round(overall_win_pct, 4),
        "avg_ppg": round(total_pts / total_games, 1) if total_games else 0.0,
        "playoff_appearances": playoff_apps,
        "total_seasons": len(season_rows),
        "championships": championships,
        "total_trades": total_trades,
        "top_scorer": top_player_str,
        "best_finish": FINISH_DISPLAY.get(best_finish, str(best_finish)) if best_finish else "—",
    }

    return {
        "owner": name,
        "joined_season": joined_season,
        "departed_after": departed_after,
        "career": career,
        "seasons": season_rows,
    }


@router.get("/{name}/h2h")
def owner_h2h(name: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Head-to-head record for one owner vs every opponent."""
    all_owners = [
        r[0] for r in con.execute(
            "SELECT canonical_name FROM owners WHERE canonical_name != ? ORDER BY canonical_name",
            (name,),
        ).fetchall()
    ]

    h2h_rows = []
    for opp in all_owners:
        rows = con.execute(
            """
            SELECT m1.points, m2.points
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
            """,
            (name, opp),
        ).fetchall()
        if not rows:
            continue
        wins = sum(1 for p1, p2 in rows if p1 > p2)
        losses = sum(1 for p1, p2 in rows if p1 < p2)
        ties = sum(1 for p1, p2 in rows if p1 == p2)
        games = len(rows)
        avg_for = round(sum(p1 for p1, _ in rows) / games, 1)
        avg_against = round(sum(p2 for _, p2 in rows) / games, 1)
        w_pct = (wins + 0.5 * ties) / games
        record_str = f"{wins}-{losses}"
        if ties:
            record_str += f"-{ties}"
        h2h_rows.append({
            "opponent": opp,
            "record": record_str,
            "win_pct": round(w_pct, 4),
            "avg_for": avg_for,
            "avg_against": avg_against,
            "games": games,
        })

    h2h_rows.sort(key=lambda r: -r["win_pct"])
    return {"owner": name, "h2h": h2h_rows}


@router.get("/{name}/top-players")
def owner_top_players(
    name: str,
    season: int | None = Query(None),
    con: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Top-scoring starters for an owner (all-time or filtered to one season)."""
    players = get_owner_top_players(con, name, season=season)
    return {"owner": name, "season": season, "players": players}


@router.get("/{name}/trades")
def owner_trades(name: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Trade history for an owner, newest first."""
    all_trades = get_trade_log(con)
    owner_trades = [t for t in all_trades if name in t.owners]
    rows = []
    for t in sorted(owner_trades, key=lambda x: (x.season, x.week), reverse=True):
        received = [a.asset_name for a in t.assets if a.to_owner == name]
        sent = [a.asset_name for a in t.assets if a.from_owner == name]
        partners = [o for o in t.owners if o != name]
        rows.append({
            "season": t.season,
            "week": t.week,
            "partners": partners,
            "received": received,
            "sent": sent,
        })
    return {"owner": name, "trades": rows}


@router.get("/{name}/waivers")
def owner_waivers(name: str, con: sqlite3.Connection = Depends(get_db)) -> dict:
    """Waiver and free-agent activity for an owner."""
    log = get_owner_waiver_log(con, name)
    total_claims = sum(1 for r in log if r["type"] == "Waiver")
    total_fa = sum(1 for r in log if r["type"] == "Free Agent")
    total_faab = sum(r["faab_bid"] or 0 for r in log)
    return {
        "owner": name,
        "summary": {
            "waiver_claims": total_claims,
            "fa_adds": total_fa,
            "faab_spent": total_faab,
        },
        "log": log,
    }
