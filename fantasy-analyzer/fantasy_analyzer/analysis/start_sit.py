"""Start/Sit (lineup efficiency) analysis.

For every team-week, compares the actual score to the best possible score
achievable from that week's full rostered player pool (the same pool Sleeper
uses for `players_points` — active roster only, never taxi squad, since taxi
players aren't part of a week's matchup player pool in Sleeper's data model).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

# NNBE's locked-slot count and flex-slot count, by season. Sleeper doesn't
# store historical roster_positions in our DB, so this is reconstructed
# empirically from real starters_json data (filtered to weeks where every
# slot was filled, i.e. no bye/empty-slot "0" placeholders): every season
# from 2022 on locks QB1/RB1/WR2/TE1, but 2021 ran with only WR1 locked
# (one extra flex slot in its place) — confirmed by real lineups that
# season starting just 1 WR despite having bench WRs with points to spare,
# which is only possible if that slot was a true FLEX, not a locked WR2.
_DEFAULT_LOCKED = {"QB": 1, "RB": 1, "WR": 2, "TE": 1}
_LINEUP_SHAPE_OVERRIDES: dict[int, tuple[dict[str, int], int]] = {
    2021: ({"QB": 1, "RB": 1, "WR": 1, "TE": 1}, 4),
    2022: (_DEFAULT_LOCKED, 3),
}


def _lineup_shape(season: int) -> tuple[dict[str, int], int]:
    """Return (locked_slot_counts, num_flex_slots) for a given season."""
    return _LINEUP_SHAPE_OVERRIDES.get(season, (_DEFAULT_LOCKED, 4))


def optimal_lineup_pts(
    players: list[dict],
    num_flex: int = 4,
    locked: dict[str, int] | None = None,
) -> float:
    """Return the maximum achievable score from a player pool.

    Args:
        players: list of {"position": str, "points": float}
        num_flex: number of flexible slots beyond the locked starters. Flex
            slots draw from RB/WR/TE, plus at most 1 QB (mirrors NNBE's
            SUPER_FLEX rule).
        locked: locked single-position slot counts, e.g. {"QB":1,"RB":1,
            "WR":2,"TE":1} (the modern NNBE default — see `_lineup_shape`
            for historical exceptions).
    """
    if locked is None:
        locked = _DEFAULT_LOCKED

    by_pos: dict[str, list[float]] = defaultdict(list)
    for p in players:
        by_pos[p["position"]].append(p["points"])
    for pos in by_pos:
        by_pos[pos].sort(reverse=True)

    total = 0.0
    used: dict[str, int] = defaultdict(int)

    for pos, count in locked.items():
        pool = by_pos.get(pos, [])
        for i in range(count):
            if i < len(pool):
                total += pool[i]
                used[pos] += 1

    non_qb: list[float] = []
    for pos in ("RB", "WR", "TE"):
        non_qb.extend(by_pos.get(pos, [])[used[pos]:])
    non_qb.sort(reverse=True)

    qb_pool = by_pos.get("QB", [])[used["QB"]:]
    best_qb = qb_pool[0] if qb_pool else None
    top_flex = non_qb[:num_flex]

    if best_qb is not None and (len(top_flex) < num_flex or best_qb > top_flex[-1]):
        cutoff = num_flex - 1 if len(top_flex) >= num_flex else len(top_flex)
        flex_pts = sum(top_flex[:cutoff]) + best_qb
    else:
        flex_pts = sum(top_flex)

    return total + flex_pts


def get_start_sit_weeks(
    con: sqlite3.Connection,
    season: int | None = None,
    include_playoffs: bool = True,
) -> list[dict]:
    """Per-team-week actual vs. optimal lineup score.

    Returns one row per team-week: user_id, owner, season, week, is_playoff,
    actual_pts, optimal_pts, pct (actual/optimal*100), pts_left_on_bench.
    Weeks where the optimal pool can't be computed (no usable position data)
    are skipped.
    """
    positions = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT player_id, position FROM players WHERE position IN ('QB','RB','WR','TE')"
        )
    }
    owner_names = {r[0]: r[1] for r in con.execute("SELECT user_id, canonical_name FROM owners")}

    filters = ["m.players_points_json IS NOT NULL", "m.points IS NOT NULL"]
    params: list = []
    if season is not None:
        filters.append("m.season = ?")
        params.append(season)
    if not include_playoffs:
        filters.append("m.is_playoff = 0")

    rows = con.execute(
        f"""
        SELECT m.user_id, m.season, m.week, m.is_playoff, m.points, m.players_points_json
        FROM matchups m
        WHERE {' AND '.join(filters)}
        ORDER BY m.season, m.week
        """,
        params,
    ).fetchall()

    results = []
    for user_id, szn, week, is_playoff, points, pp_json in rows:
        pp: dict[str, float] = json.loads(pp_json)
        pool = [
            {"position": positions[pid], "points": float(pts or 0)}
            for pid, pts in pp.items()
            if pid in positions
        ]
        if not pool:
            continue
        locked, num_flex = _lineup_shape(szn)
        optimal = optimal_lineup_pts(pool, num_flex=num_flex, locked=locked)
        if optimal <= 0:
            continue
        actual = float(points or 0)
        # The actual lineup a team started is itself a feasible lineup, so it's
        # a real lower bound on the true optimal — clamp against it as a
        # safety net for any lineup-shape quirk not captured by `_lineup_shape`.
        optimal = max(optimal, actual)
        results.append({
            "user_id": user_id,
            "owner": owner_names.get(user_id, user_id),
            "season": szn,
            "week": week,
            "is_playoff": bool(is_playoff),
            "actual_pts": round(actual, 2),
            "optimal_pts": round(optimal, 2),
            "pct": round(actual / optimal * 100, 1),
            "pts_left_on_bench": round(max(optimal - actual, 0), 2),
        })

    return results


def get_start_sit_leaderboard(
    con: sqlite3.Connection,
    season: int | None = None,
    include_playoffs: bool = True,
) -> list[dict]:
    """Per-owner lineup-efficiency aggregate for one season, or all-time when season is None."""
    weeks = get_start_sit_weeks(con, season=season, include_playoffs=include_playoffs)

    by_owner: dict[str, list[dict]] = defaultdict(list)
    for w in weeks:
        by_owner[w["user_id"]].append(w)

    leaderboard = []
    for user_id, wks in by_owner.items():
        total_actual = sum(w["actual_pts"] for w in wks)
        total_optimal = sum(w["optimal_pts"] for w in wks)
        best = max(wks, key=lambda w: w["pct"])
        worst = min(wks, key=lambda w: w["pct"])
        leaderboard.append({
            "user_id": user_id,
            "owner": wks[0]["owner"],
            "weeks": len(wks),
            "avg_pct": round(sum(w["pct"] for w in wks) / len(wks), 1),
            "total_actual": round(total_actual, 2),
            "total_optimal": round(total_optimal, 2),
            "total_left_on_bench": round(total_optimal - total_actual, 2),
            "best_week": {"season": best["season"], "week": best["week"], "pct": best["pct"]},
            "worst_week": {"season": worst["season"], "week": worst["week"], "pct": worst["pct"]},
        })

    leaderboard.sort(key=lambda r: -r["avg_pct"])
    return leaderboard
