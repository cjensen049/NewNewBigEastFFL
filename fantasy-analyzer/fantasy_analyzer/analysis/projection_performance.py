"""Players vs. projection, per owner per week and over the season.

For each team-week: actual score vs. the sum of that week's Sleeper projections
for the players the owner actually started. +20 means the starters collectively
outscored their projections by 20. This is purely about how the players
performed against Sleeper's expectations; it says nothing about whether the
owner picked a good lineup.

Lineup efficiency (actual score as a % of the best lineup in hindsight, from
analysis.start_sit) is reported alongside but as a separate measure -- it is the
manager's start/sit quality, not the players' over/under-performance.

Sleeper projections only. A starter with no Sleeper projection that week is left
out of the comparison (neither his points nor a projection count). That covers
inactive players (scored 0 anyway) and players Sleeper no longer lists, such as
players retired since 2021 -- counting those as "0 projected" made their whole
season read as over-performance. The excluded points are reported separately.
Regular season only.

Sleeper's projections run high or low for the whole league in some seasons (e.g.
every team ~9 pts/week under in 2021/2022/2025, ~even in 2023/2024), so raw
over/under isn't comparable across seasons. Each week's league-wide average
over/under is also subtracted ("vs league"), which centers every week on zero.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from fantasy_analyzer.analysis.start_sit import get_start_sit_weeks
from fantasy_analyzer.analysis.weekly_digest import team_actual_vs_projected

_RECENT_WEEKS = 3


def _avg(values: list[float]) -> float | None:
    """Mean rounded to 1 decimal, or None for an empty list."""
    return round(sum(values) / len(values), 1) if values else None


def get_projection_performance(con: sqlite3.Connection, league_id: str, season: int) -> dict:
    """Per-owner weekly and season over/under vs. Sleeper projections, plus lineup efficiency.

    Returns {season, weeks, league_avg_diff, rows}; rows are sorted by season
    total over/under (best first). league_avg_diff is the mean over/under per
    team-week across the whole league. Each row: owner, total_diff,
    total_vs_league (season total after subtracting each week's league average),
    avg_diff, recent_avg_diff (last 3 weeks), total_actual, total_projected,
    efficiency_pct, pts_left_on_bench, and weeks: [{week, actual, projected, diff,
    diff_vs_league, unprojected_pts, unprojected_n, efficiency_pct, pts_left_on_bench}].
    A team-week with no projection data is left out of that owner's weeks.
    excluded_pts / excluded_starters count starters left out of the comparison
    for having no Sleeper projection.
    """
    weeks = [
        r[0] for r in con.execute(
            "SELECT DISTINCT week FROM matchups WHERE league_id=? AND is_playoff=0 "
            "AND points IS NOT NULL AND points > 0 ORDER BY week",
            (league_id,),
        )
    ]
    if not weeks:
        return {"season": season, "weeks": [], "league_avg_diff": None, "excluded_pts": 0.0, "excluded_starters": 0, "rows": []}

    efficiency = {
        (r["owner"], r["week"]): r
        for r in get_start_sit_weeks(con, season=season, include_playoffs=False)
    }

    by_owner: dict[str, list[dict]] = defaultdict(list)
    for week in weeks:
        for owner, perf in team_actual_vs_projected(con, league_id, season, week).items():
            eff = efficiency.get((owner, week))
            by_owner[owner].append({
                "week": week,
                "actual": perf["actual"],
                "projected": perf["projected"],
                "diff": perf["diff"],
                "unprojected_pts": perf["unprojected_pts"],
                "unprojected_n": perf["unprojected_n"],
                "efficiency_pct": eff["pct"] if eff else None,
                "pts_left_on_bench": eff["pts_left_on_bench"] if eff else None,
                "_optimal": eff["optimal_pts"] if eff else None,
            })

    all_diffs = [w["diff"] for wks in by_owner.values() for w in wks]
    week_avg: dict[int, float] = {}
    for week in weeks:
        d = [w["diff"] for wks in by_owner.values() for w in wks if w["week"] == week]
        if d:
            week_avg[week] = sum(d) / len(d)
    for wks in by_owner.values():
        for w in wks:
            w["diff_vs_league"] = round(w["diff"] - week_avg[w["week"]], 1)

    rows = []
    for owner, wks in by_owner.items():
        diffs = [w["diff"] for w in wks]
        with_eff = [w for w in wks if w["_optimal"]]
        total_actual = sum(w["actual"] for w in with_eff)
        total_optimal = sum(w["_optimal"] for w in with_eff)
        rows.append({
            "owner": owner,
            "total_diff": round(sum(diffs), 1),
            "total_vs_league": round(sum(w["diff_vs_league"] for w in wks), 1),
            "avg_diff": _avg(diffs),
            "recent_avg_diff": _avg(diffs[-_RECENT_WEEKS:]),
            "total_actual": round(sum(w["actual"] for w in wks), 1),
            "total_projected": round(sum(w["projected"] for w in wks), 1),
            "efficiency_pct": round(total_actual / total_optimal * 100, 1) if total_optimal else None,
            "pts_left_on_bench": round(sum(w["pts_left_on_bench"] for w in with_eff), 1),
            "weeks": [{k: v for k, v in w.items() if k != "_optimal"} for w in wks],
        })
    rows.sort(key=lambda r: -r["total_diff"])
    all_weeks = [w for wks in by_owner.values() for w in wks]
    return {
        "season": season,
        "weeks": weeks,
        "league_avg_diff": _avg(all_diffs),
        "excluded_pts": round(sum(w["unprojected_pts"] for w in all_weeks), 1),
        "excluded_starters": sum(w["unprojected_n"] for w in all_weeks),
        "rows": rows,
    }


def _role_totals(entries: list[dict]) -> dict:
    """Totals for a list of player-week entries.

    games and actual cover every entry. projected, diff and avg_diff cover only the
    entries Sleeper projected (compared_games of them), and are None when none were.
    """
    compared = [e for e in entries if e["projected"] is not None]
    projected = sum(e["projected"] for e in compared)
    diff = sum(e["actual"] - e["projected"] for e in compared)
    return {
        "games": len(entries),
        "compared_games": len(compared),
        "actual": round(sum(e["actual"] for e in entries), 1),
        "projected": round(projected, 1) if compared else None,
        "diff": round(diff, 1) if compared else None,
        "avg_diff": round(diff / len(compared), 1) if compared else None,
    }


def get_owner_player_performance(con: sqlite3.Connection, owner_name: str, season: int) -> dict:
    """Every player an owner rostered in a season: actual vs. Sleeper projection, by week.

    One row per player with a `weeks` list ({week, actual, projected, diff, role},
    role is "starter" or "bench") and `totals` for each of "all", "starter" and
    "bench" so the page can toggle without recomputing. Regular season only.

    A started player always appears, even with no projection and 0 points (he
    held a lineup slot). A bench player appears only if he was projected or
    scored, so inactive/bye players don't pad his games with zeros. A week with no
    Sleeper projection has projected/diff None and is left out of the over/under
    (as in get_projection_performance), so the starter diffs add up to that owner's
    team-level over/under.
    """
    row = con.execute("SELECT user_id FROM owners WHERE canonical_name = ?", (owner_name,)).fetchone()
    empty = {"owner": owner_name, "season": season, "weeks": [], "rows": []}
    if not row:
        return empty

    matchups = con.execute(
        """SELECT week, starters_json, players_points_json FROM matchups
           WHERE user_id=? AND season=? AND is_playoff=0 AND points IS NOT NULL AND points > 0
             AND starters_json IS NOT NULL AND players_points_json IS NOT NULL
           ORDER BY week""",
        (row[0], season),
    ).fetchall()
    if not matchups:
        return empty

    projections = {
        (w, pid): p for w, pid, p in con.execute(
            "SELECT week, player_id, projected_pts FROM player_projections WHERE season=?", (season,)
        )
    }
    info = {pid: (name, pos) for pid, name, pos in con.execute("SELECT player_id, full_name, position FROM players")}

    by_player: dict[str, list[dict]] = defaultdict(list)
    for week, starters_raw, pp_raw in matchups:
        starters = set(json.loads(starters_raw))
        for pid, pts in json.loads(pp_raw).items():
            actual = float(pts or 0.0)
            projected = projections.get((week, pid))
            role = "starter" if pid in starters else "bench"
            if role == "bench" and projected is None and actual == 0:
                continue
            by_player[pid].append({
                "week": week,
                "actual": round(actual, 1),
                "projected": round(projected, 1) if projected is not None else None,
                "diff": round(actual - projected, 1) if projected is not None else None,
                "role": role,
            })

    rows = []
    for pid, entries in by_player.items():
        name, pos = info.get(pid, (pid, None))
        rows.append({
            "player_id": pid,
            "player": name or pid,
            "position": pos,
            "weeks": entries,
            "totals": {
                "all": _role_totals(entries),
                "starter": _role_totals([e for e in entries if e["role"] == "starter"]),
                "bench": _role_totals([e for e in entries if e["role"] == "bench"]),
            },
        })
    rows.sort(key=lambda r: -(r["totals"]["all"]["diff"] or 0.0))
    return {"owner": owner_name, "season": season, "weeks": [m[0] for m in matchups], "rows": rows}
