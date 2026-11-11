"""Players vs. projection, per owner per week and over the season.

For each team-week: actual score vs. the sum of that week's Sleeper projections
for the players the owner actually started. +20 means the starters collectively
outscored their projections by 20. This is purely about how the players
performed against Sleeper's expectations; it says nothing about whether the
owner picked a good lineup.

Lineup efficiency (actual score as a % of the best lineup in hindsight, from
analysis.start_sit) is reported alongside but as a separate measure -- it is the
manager's start/sit quality, not the players' over/under-performance.

Sleeper projections only. A starter with no Sleeper projection that week (out,
inactive) counts as 0 projected, same as Sleeper's own app shows. Regular
season only.

Sleeper's projections run high or low for the whole league in some seasons (e.g.
every team ~9 pts/week under in 2021/2022/2025, ~even in 2023/2024), so raw
over/under isn't comparable across seasons. Each week's league-wide average
over/under is also subtracted ("vs league"), which centers every week on zero.
"""

from __future__ import annotations

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
    diff_vs_league, efficiency_pct, pts_left_on_bench}]. A team-week with no
    projection data is left out of that owner's weeks.
    """
    weeks = [
        r[0] for r in con.execute(
            "SELECT DISTINCT week FROM matchups WHERE league_id=? AND is_playoff=0 "
            "AND points IS NOT NULL AND points > 0 ORDER BY week",
            (league_id,),
        )
    ]
    if not weeks:
        return {"season": season, "weeks": [], "league_avg_diff": None, "rows": []}

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
    return {"season": season, "weeks": weeks, "league_avg_diff": _avg(all_diffs), "rows": rows}
