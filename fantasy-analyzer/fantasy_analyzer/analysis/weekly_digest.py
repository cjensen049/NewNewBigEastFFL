"""Weekly recap + look-ahead digest for the homepage.

Recap covers the most recently completed week (final scores, closest game,
biggest blowout, top-scoring player league-wide). Preview covers the
upcoming week (naive projected totals from each roster's optimal lineup
at Sleeper's season-long per-game rate, the closest projected matchup,
and bye-week flags).
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from fantasy_analyzer.analysis.roster_quality import optimal_lineup_pts

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


def get_weekly_recap(con: sqlite3.Connection, league_id: str) -> dict | None:
    """Final scores, closest game, biggest blowout, and top performer for the
    most recently completed regular-season week. None if no week is complete yet."""
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
    for mid, name, pts in rows:
        by_matchup[mid].append({"owner": name, "points": round(pts, 1)})

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

    return {
        "week": week,
        "matchups": matchups,
        "closest": matchups[0] if matchups else None,
        "blowout": matchups[-1] if matchups else None,
        "top_player": top_player,
    }


def _projected_lineup_total(con: sqlite3.Connection, league_id: str, roster_id: int, season: int) -> float | None:
    """A roster's optimal-lineup total at Sleeper's season-long per-game rate.
    None if too few of its players matched a projection to trust the result."""
    players = con.execute(
        """SELECT sp.position, sp.projected_pts
           FROM current_rosters cr
           JOIN player_season_projections sp ON sp.player_id = cr.player_id AND sp.season = ?
           WHERE cr.league_id=? AND cr.roster_id=? AND sp.projected_pts > 0""",
        (season, league_id, roster_id),
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
    for mid, name, roster_id in rows:
        by_matchup[mid].append({
            "owner": name,
            "projected": _projected_lineup_total(con, league_id, roster_id, season),
            "bye_count": _bye_player_count(con, league_id, roster_id, season, week),
        })

    matchups = []
    for mid, sides in by_matchup.items():
        if len(sides) != 2:
            continue
        a, b = sides
        proj_gap = (
            round(abs(a["projected"] - b["projected"]), 1)
            if a["projected"] is not None and b["projected"] is not None
            else None
        )
        matchups.append({"matchup_id": mid, "a": a, "b": b, "proj_gap": proj_gap})
    matchups.sort(key=lambda m: (m["proj_gap"] is None, m["proj_gap"]))

    closest_projected = next((m for m in matchups if m["proj_gap"] is not None), None)

    return {
        "week": week,
        "matchups": matchups,
        "closest_projected": closest_projected,
    }
