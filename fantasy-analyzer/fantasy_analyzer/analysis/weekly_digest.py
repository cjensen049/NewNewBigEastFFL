"""Weekly recap + look-ahead digest for the homepage.

Recap covers the most recently completed week: final scores, closest game,
biggest blowout, top-scoring player league-wide, and superlatives (highest/
lowest score, most efficient lineup, biggest over/underachiever vs. that
week's own projection). Preview covers the upcoming week: each roster's
optimal-lineup projected total at Sleeper's per-week projection, bye-week
flags, the week's highest projected team, "matchup of the week" (closest
game among the highest-projected matchups), and the lowest-combined
"pillow fight" matchup.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from fantasy_analyzer.analysis.roster_quality import optimal_lineup_pts
from fantasy_analyzer.analysis.start_sit import get_start_sit_weeks

# Below this many matched players, a projected total isn't trustworthy
# enough to show -- same threshold roster_quality.py uses for the same reason.
_MIN_MATCHED_PLAYERS = 5


def last_completed_week(con: sqlite3.Connection, league_id: str) -> int:
    row = con.execute(
        "SELECT MAX(week) FROM matchups WHERE league_id=? AND is_playoff=0 "
        "AND points IS NOT NULL AND points > 0",
        (league_id,),
    ).fetchone()
    return row[0] or 0


def _team_actual_vs_projected(con: sqlite3.Connection, league_id: str, season: int, week: int) -> dict[str, dict]:
    """Return {owner: {actual, projected, diff}} -- each team's real score vs.
    the sum of their actual starters' own pre-game weekly projections. A team
    with no projection data for any starter is omitted (diff would be meaningless)."""
    rows = con.execute(
        """SELECT o.canonical_name, m.points, m.starters_json
           FROM matchups m JOIN owners o ON o.user_id = m.user_id
           WHERE m.league_id=? AND m.week=? AND m.is_playoff=0 AND m.starters_json IS NOT NULL""",
        (league_id, week),
    ).fetchall()

    result: dict[str, dict] = {}
    for name, points, starters_raw in rows:
        starters = json.loads(starters_raw)
        if not starters:
            continue
        placeholders = ",".join("?" * len(starters))
        proj_rows = con.execute(
            f"SELECT projected_pts FROM player_projections WHERE season=? AND week=? AND player_id IN ({placeholders})",
            (season, week, *starters),
        ).fetchall()
        if not proj_rows:
            continue
        team_projected = sum(r[0] for r in proj_rows)
        result[name] = {
            "actual": round(points, 1),
            "projected": round(team_projected, 1),
            "diff": round(points - team_projected, 1),
        }
    return result


def get_weekly_recap(con: sqlite3.Connection, league_id: str, season: int) -> dict | None:
    """Final scores, closest game, biggest blowout, top performer, and
    superlatives (highest/lowest score, most efficient lineup, biggest
    over/underachiever vs. that week's own projection) for the most recently
    completed regular-season week. None if no week is complete yet."""
    week = last_completed_week(con, league_id)
    if week == 0:
        return None

    rows = con.execute(
        """SELECT m.matchup_id, o.canonical_name, m.points
           FROM matchups m JOIN owners o ON o.user_id = m.user_id
           WHERE m.league_id=? AND m.week=? AND m.is_playoff=0
           ORDER BY m.matchup_id""",
        (league_id, week),
    ).fetchall()

    by_matchup: dict[int, list] = defaultdict(list)
    all_scores: list[dict] = []
    for mid, name, pts in rows:
        entry = {"owner": name, "points": round(pts, 1)}
        by_matchup[mid].append(entry)
        all_scores.append(entry)

    matchups = []
    for mid, sides in by_matchup.items():
        if len(sides) != 2:
            continue
        a, b = sides
        winner = a["owner"] if a["points"] > b["points"] else b["owner"]
        margin = round(abs(a["points"] - b["points"]), 1)
        matchups.append({"matchup_id": mid, "a": a, "b": b, "winner": winner, "margin": margin})
    matchups.sort(key=lambda m: m["margin"])

    # Top-scoring player league-wide this week (from actual starters only)
    top_player = None
    pp_rows = con.execute(
        """SELECT m.user_id, m.starters_json, m.players_points_json
           FROM matchups m
           WHERE m.league_id=? AND m.week=? AND m.is_playoff=0
             AND m.starters_json IS NOT NULL AND m.players_points_json IS NOT NULL""",
        (league_id, week),
    ).fetchall()
    if pp_rows:
        owner_by_uid = {
            r[0]: r[1] for r in con.execute(
                "SELECT lo.user_id, o.canonical_name FROM league_owners lo "
                "JOIN owners o ON o.user_id = lo.user_id WHERE lo.league_id=?",
                (league_id,),
            )
        }
        best_pid, best_pts, best_uid = None, -1.0, None
        for uid, starters_raw, pp_raw in pp_rows:
            pp = json.loads(pp_raw)
            for pid in json.loads(starters_raw):
                pts = pp.get(pid) or 0.0
                if pts > best_pts:
                    best_pid, best_pts, best_uid = pid, pts, uid
        if best_pid:
            row = con.execute(
                "SELECT full_name, position FROM players WHERE player_id=?", (best_pid,)
            ).fetchone()
            name, pos = row if row else (best_pid, None)
            top_player = {
                "name": name, "position": pos, "points": round(best_pts, 1),
                "owner": owner_by_uid.get(best_uid, "?"),
            }

    highest_score = max(all_scores, key=lambda s: s["points"]) if all_scores else None
    lowest_score = min(all_scores, key=lambda s: s["points"]) if all_scores else None

    most_efficient = None
    week_efficiency = [r for r in get_start_sit_weeks(con, season=season, include_playoffs=False) if r["week"] == week]
    if week_efficiency:
        best = max(week_efficiency, key=lambda r: r["pct"])
        most_efficient = {"owner": best["owner"], "pct": best["pct"]}

    overachiever = None
    underachiever = None
    team_perf = _team_actual_vs_projected(con, league_id, season, week)
    if team_perf:
        best_name = max(team_perf, key=lambda n: team_perf[n]["diff"])
        worst_name = min(team_perf, key=lambda n: team_perf[n]["diff"])
        overachiever = {"owner": best_name, **team_perf[best_name]}
        underachiever = {"owner": worst_name, **team_perf[worst_name]}

    return {
        "week": week,
        "matchups": matchups,
        "closest": matchups[0] if matchups else None,
        "blowout": matchups[-1] if matchups else None,
        "top_player": top_player,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "most_efficient": most_efficient,
        "overachiever": overachiever,
        "underachiever": underachiever,
    }


def _projected_lineup_total(con: sqlite3.Connection, league_id: str, roster_id: int, season: int, week: int) -> float | None:
    """A roster's optimal-lineup total at Sleeper's this-week projections (so an
    injured/doubtful player correctly drops out instead of showing a healthy
    season average). None if too few of its players matched a projection."""
    players = con.execute(
        """SELECT wp.position, wp.projected_pts
           FROM current_rosters cr
           JOIN player_projections wp ON wp.player_id = cr.player_id AND wp.season = ? AND wp.week = ?
           WHERE cr.league_id=? AND cr.roster_id=? AND wp.projected_pts > 0""",
        (season, week, league_id, roster_id),
    ).fetchall()
    if len(players) < _MIN_MATCHED_PLAYERS:
        return None
    return round(optimal_lineup_pts([{"position": p, "projected_pts": pts} for p, pts in players]), 1)


def _bye_player_count(con: sqlite3.Connection, league_id: str, roster_id: int, season: int, week: int) -> int:
    bye_teams = {r[0] for r in con.execute("SELECT team FROM nfl_byes WHERE season=? AND week=?", (season, week))}
    if not bye_teams:
        return 0
    rows = con.execute(
        """SELECT p.team FROM current_rosters cr JOIN players p ON p.player_id = cr.player_id
           WHERE cr.league_id=? AND cr.roster_id=?""",
        (league_id, roster_id),
    ).fetchall()
    return sum(1 for (team,) in rows if team in bye_teams)


def get_weekly_preview(con: sqlite3.Connection, league_id: str, season: int, pws: int) -> dict | None:
    """Upcoming week's matchups with naive projected totals and bye-week flags.
    None once the regular season is over (playoffs have a different structure)."""
    week = last_completed_week(con, league_id) + 1
    if week >= pws:
        return None

    rows = con.execute(
        """SELECT m.matchup_id, o.canonical_name, lo.roster_id
           FROM matchups m
           JOIN owners o ON o.user_id = m.user_id
           JOIN league_owners lo ON lo.league_id = m.league_id AND lo.user_id = m.user_id
           WHERE m.league_id=? AND m.week=?
           ORDER BY m.matchup_id""",
        (league_id, week),
    ).fetchall()
    if not rows:
        return None

    by_matchup: dict[int, list] = defaultdict(list)
    all_projected: list[dict] = []
    for mid, name, roster_id in rows:
        entry = {
            "owner": name,
            "projected": _projected_lineup_total(con, league_id, roster_id, season, week),
            "bye_count": _bye_player_count(con, league_id, roster_id, season, week),
        }
        by_matchup[mid].append(entry)
        if entry["projected"] is not None:
            all_projected.append(entry)

    matchups = []
    for mid, sides in by_matchup.items():
        if len(sides) != 2:
            continue
        a, b = sides
        has_both = a["projected"] is not None and b["projected"] is not None
        proj_gap = round(abs(a["projected"] - b["projected"]), 1) if has_both else None
        combined = round(a["projected"] + b["projected"], 1) if has_both else None
        matchups.append({"matchup_id": mid, "a": a, "b": b, "proj_gap": proj_gap, "combined": combined})
    matchups.sort(key=lambda m: (m["proj_gap"] is None, m["proj_gap"]))

    # "Matchup of the week": the closest game AMONG the highest-projected
    # matchups, so a 140-150 nail-biter gets featured over a 92-97 pillow
    # fight that's technically closer in raw gap but far lower-scoring.
    ranked = [m for m in matchups if m["combined"] is not None]
    ranked.sort(key=lambda m: -m["combined"])
    top_half = ranked[: max(1, -(-len(ranked) // 2))]  # ceil(n/2), at least 1
    matchup_of_the_week = min(top_half, key=lambda m: m["proj_gap"]) if top_half else None
    lowest_combined_matchup = min(ranked, key=lambda m: m["combined"]) if ranked else None
    highest_projected = max(all_projected, key=lambda s: s["projected"]) if all_projected else None

    return {
        "week": week,
        "matchups": matchups,
        "matchup_of_the_week": matchup_of_the_week,
        "lowest_combined_matchup": lowest_combined_matchup,
        "highest_projected": highest_projected,
    }
