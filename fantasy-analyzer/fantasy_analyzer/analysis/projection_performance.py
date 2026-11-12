"""Players vs. projection, per owner per week and over the season.

For each team-week: actual score vs. the sum of that week's Sleeper projections
for the players the owner actually started. +20 means the starters collectively
outscored their projections by 20. This is purely about how the players
performed against Sleeper's expectations; it says nothing about whether the
owner picked a good lineup.

Lineup efficiency (actual score as a % of the best lineup in hindsight, from
analysis.start_sit) is reported alongside but as a separate measure -- it is the
manager's start/sit quality, not the players' over/under-performance.

Sleeper projections only, scored with NNBE's own rules: the scraper rebuilds each
projected point total from Sleeper's projected stat line (see scraping.sleeper_projections),
because Sleeper's ready-made total for older QB feeds carries ~2 pts/game of first-down
credit that NNBE never awards. Sleeper drops players who later retire or get released
from its old weekly feeds (Tom Brady's 2021 has none), and counting those as "0
projected" made their whole season read as over-performance. So a starter with no
weekly projection who scored gets his season-long per-game rate as a stand-in
(marked estimated); one with neither, or who scored nothing (inactive), is left
out of the comparison and reported as unprojected. Regular season only.

Sleeper's projections run high or low for the whole league in some seasons (e.g.
every team ~9 pts/week under in 2021/2022/2025, ~even in 2023/2024), so raw
over/under isn't comparable across seasons. Each week's league-wide average
over/under is also subtracted ("vs league"), which centers every week on zero.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict

from fantasy_analyzer.analysis.start_sit import get_start_sit_weeks
from fantasy_analyzer.analysis.weekly_digest import team_actual_vs_projected

_RECENT_WEEKS = 3

def _avg(values: list[float]) -> float | None:
    """Mean rounded to 1 decimal, or None for an empty list."""
    return round(sum(values) / len(values), 1) if values else None


def projection_luck_verdict(avg_vs_league: float | None) -> str | None:
    """Very Lucky ... Very Unlucky from an owner's average weekly over/under vs. the league.

    avg_vs_league is points per week above (+) or below (-) the league-wide average
    over/under (an owner's season total vs. league divided by weeks played). Fixed
    cutoffs, same boundary style as the schedule-luck verdict: +10 or more is Very
    Lucky, +2.5 up to +10 Lucky, -2.5 up to +2.5 Average, -10 up to -2.5 Unlucky, and
    below -10 Very Unlucky.
    """
    if avg_vs_league is None:
        return None
    if avg_vs_league >= 10:
        return "Very Lucky"
    if avg_vs_league >= 2.5:
        return "Lucky"
    if avg_vs_league >= -2.5:
        return "Average"
    if avg_vs_league >= -10:
        return "Unlucky"
    return "Very Unlucky"


def get_projection_performance(con: sqlite3.Connection, league_id: str, season: int) -> dict:
    """Per-owner weekly and season over/under vs. Sleeper projections, plus lineup efficiency.

    Returns {season, weeks, league_avg_diff, rows, ...}; rows are sorted by season
    total over/under (best first). league_avg_diff is the mean over/under per
    team-week across the whole league. Each row: owner, total_diff,
    total_vs_league (season total after subtracting each week's league average),
    avg_vs_league, luck_verdict (projection luck, see projection_luck_verdict),
    avg_diff, recent_avg_diff (last 3 weeks), total_actual, total_projected,
    estimated_n (starter-weeks using a season-average stand-in), efficiency_pct,
    pts_left_on_bench, and weeks: [{week, actual, projected, diff, diff_vs_league,
    estimated_n, unprojected_pts, unprojected_n, efficiency_pct, pts_left_on_bench}].
    A team-week with no projection data is left out of that owner's weeks.
    excluded_pts / excluded_starters count starters left out of the comparison
    for having no projection at all; estimated_starters counts the stand-ins.
    """
    weeks = [
        r[0] for r in con.execute(
            "SELECT DISTINCT week FROM matchups WHERE league_id=? AND is_playoff=0 "
            "AND points IS NOT NULL AND points > 0 ORDER BY week",
            (league_id,),
        )
    ]
    if not weeks:
        return {
            "season": season, "weeks": [], "league_avg_diff": None,
            "excluded_pts": 0.0, "excluded_starters": 0, "estimated_starters": 0, "rows": [],
        }

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
                "estimated_n": perf["estimated_n"],
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
        vs_league = [w["diff_vs_league"] for w in wks]
        with_eff = [w for w in wks if w["_optimal"]]
        total_actual = sum(w["actual"] for w in with_eff)
        total_optimal = sum(w["_optimal"] for w in with_eff)
        rows.append({
            "owner": owner,
            "total_diff": round(sum(diffs), 1),
            "total_vs_league": round(sum(vs_league), 1),
            "avg_vs_league": _avg(vs_league),
            "luck_verdict": projection_luck_verdict(sum(vs_league) / len(vs_league)),
            "avg_diff": _avg(diffs),
            "recent_avg_diff": _avg(diffs[-_RECENT_WEEKS:]),
            "total_actual": round(sum(w["actual"] for w in wks), 1),
            "total_projected": round(sum(w["projected"] for w in wks), 1),
            "estimated_n": sum(w["estimated_n"] for w in wks),
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
        "estimated_starters": sum(w["estimated_n"] for w in all_weeks),
        "rows": rows,
    }


def _role_totals(entries: list[dict]) -> dict:
    """Totals for a list of player-week entries.

    games and actual cover every entry. projected, diff and avg_diff cover only the
    entries with a projection (compared_games of them, estimated_games of which use a
    season-average stand-in), and are None when there were none.
    """
    compared = [e for e in entries if e["projected"] is not None]
    projected = sum(e["projected"] for e in compared)
    diff = sum(e["actual"] - e["projected"] for e in compared)
    return {
        "games": len(entries),
        "compared_games": len(compared),
        "estimated_games": sum(1 for e in compared if e["estimated"]),
        "actual": round(sum(e["actual"] for e in entries), 1),
        "projected": round(projected, 1) if compared else None,
        "diff": round(diff, 1) if compared else None,
        "avg_diff": round(diff / len(compared), 1) if compared else None,
    }


def get_owner_player_performance(con: sqlite3.Connection, owner_name: str, season: int) -> dict:
    """Every player an owner rostered in a season: actual vs. Sleeper projection, by week.

    One row per player with a `weeks` list ({week, actual, projected, diff, role,
    estimated}; role is "starter" or "bench") and `totals` for each of "all",
    "starter" and "bench" so the page can toggle without recomputing. Regular season only.

    A started player always appears, even with no projection and 0 points (he
    held a lineup slot). A bench player appears only if he was projected or
    scored, so inactive/bye players don't pad his games with zeros. A starter with
    no weekly projection who scored gets his season-long per-game rate as an
    estimated projection (as in team_actual_vs_projected). Any other week with no
    projection has projected/diff None and is left out of the over/under, so the
    starter diffs add up to that owner's team-level over/under.
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
    season_rate = dict(con.execute(
        "SELECT player_id, projected_pts FROM player_season_projections WHERE season=?", (season,)
    ).fetchall())
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
            estimated = False
            if role == "starter" and projected is None and actual != 0 and pid in season_rate:
                projected, estimated = season_rate[pid], True
            by_player[pid].append({
                "week": week,
                "actual": round(actual, 1),
                "projected": round(projected, 1) if projected is not None else None,
                "diff": round(actual - projected, 1) if projected is not None else None,
                "role": role,
                "estimated": estimated,
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


# ---------------------------------------------------------------------------
# League-wide player leaderboards and records (History page)
# ---------------------------------------------------------------------------

def _starter_events(con: sqlite3.Connection) -> list[dict]:
    """Every regular-season starter-week that has a REAL weekly Sleeper projection, all seasons.

    Estimated stand-ins are left out on purpose: leaderboards and records shouldn't be
    decided by a season-average guess.
    """
    owner_names = {r[0]: r[1] for r in con.execute("SELECT user_id, canonical_name FROM owners")}
    info = {pid: (name, pos) for pid, name, pos in con.execute("SELECT player_id, full_name, position FROM players")}
    projections = {
        (s, w, pid): p for s, w, pid, p in con.execute(
            "SELECT season, week, player_id, projected_pts FROM player_projections"
        )
    }
    events = []
    for user_id, season, week, starters_raw, pp_raw in con.execute(
        """SELECT m.user_id, l.season, m.week, m.starters_json, m.players_points_json
           FROM matchups m JOIN leagues l ON l.league_id = m.league_id
           WHERE m.is_playoff=0 AND m.points IS NOT NULL AND m.points > 0
             AND m.starters_json IS NOT NULL AND m.players_points_json IS NOT NULL
           ORDER BY l.season, m.week"""
    ):
        pp = json.loads(pp_raw)
        for pid in json.loads(starters_raw):
            projected = projections.get((season, week, pid))
            if projected is None:
                continue
            actual = float(pp.get(pid) or 0.0)
            name, pos = info.get(pid, (pid, None))
            events.append({
                "owner": owner_names.get(user_id, user_id), "season": season, "week": week,
                "player_id": pid, "player": name or pid, "position": pos,
                "actual": round(actual, 1), "projected": round(projected, 1),
                "diff": round(actual - projected, 1),
            })
    return events


def get_projection_leaders(con: sqlite3.Connection, top_n: int = 10) -> dict:
    """All-time top players over and under Sleeper's projection while in a starting lineup.

    Returns {over, under, over_adj, under_adj}, each a list of up to top_n rows: player,
    position, owners, starts, projected, actual, diff (total over/under), avg_diff (per
    start), adj_diff / avg_adj_diff and seasons (e.g. "2021-2024"). owners lists everyone
    who started him, most starts first, with the start count when there's more than one
    (e.g. "Casey (40), Jensen (28)"). Regular season, any owner, real projections only.

    over/under rank by raw diff. over_adj/under_adj rank by adj_diff instead: each
    start's diff minus the average diff of all starters at that position in that
    season, i.e. how a player did against other starters at his own position (useful
    when a position group ran over or under as a whole, as QBs did in 2021-22).
    """
    events = _starter_events(con)
    pos_season: dict[tuple, list[float]] = defaultdict(list)
    for e in events:
        pos_season[(e["position"], e["season"])].append(e["diff"])
    pos_avg = {k: sum(v) / len(v) for k, v in pos_season.items()}

    agg: dict[str, dict] = {}
    for e in events:
        a = agg.setdefault(e["player_id"], {
            "player_id": e["player_id"], "player": e["player"], "position": e["position"],
            "starts": 0, "projected": 0.0, "actual": 0.0, "adj": 0.0, "seasons": set(), "owners": Counter(),
        })
        a["starts"] += 1
        a["owners"][e["owner"]] += 1
        a["projected"] += e["projected"]
        a["actual"] += e["actual"]
        a["adj"] += e["diff"] - pos_avg[(e["position"], e["season"])]
        a["seasons"].add(e["season"])

    rows = []
    for a in agg.values():
        diff = a["actual"] - a["projected"]
        lo, hi = min(a["seasons"]), max(a["seasons"])
        ranked = sorted(a["owners"].items(), key=lambda kv: (-kv[1], kv[0]))
        owners = ranked[0][0] if len(ranked) == 1 else ", ".join(f"{o} ({n})" for o, n in ranked)
        rows.append({
            "player_id": a["player_id"], "player": a["player"], "position": a["position"],
            "owners": owners, "starts": a["starts"], "projected": round(a["projected"], 1), "actual": round(a["actual"], 1),
            "diff": round(diff, 1), "avg_diff": round(diff / a["starts"], 1),
            "adj_diff": round(a["adj"], 1), "avg_adj_diff": round(a["adj"] / a["starts"], 1),
            "seasons": str(lo) if lo == hi else f"{lo}-{hi}",
        })
    return {
        "over": sorted(rows, key=lambda r: -r["diff"])[:top_n],
        "under": sorted(rows, key=lambda r: r["diff"])[:top_n],
        "over_adj": sorted(rows, key=lambda r: -r["adj_diff"])[:top_n],
        "under_adj": sorted(rows, key=lambda r: r["adj_diff"])[:top_n],
    }


def get_projection_record_rows(con: sqlite3.Connection) -> list[tuple[str, str, list[tuple[str, int, int | None]]]]:
    """The four single-week / single-season player-vs-projection records.

    Returns [(category, value, [(holder, season, week_or_None), ...])] -- the shape
    history._add_event_record takes, with every tied holder listed. A season record is
    one player's total while starting for one owner in one season.
    """
    events = _starter_events(con)
    if not events:
        return []

    out = []

    def holder(e: dict) -> str:
        return f"{e['player']} ({e['owner']})"

    best = max(e["diff"] for e in events)
    worst = min(e["diff"] for e in events)
    for category, target in (("Player Most Over Projection, Single Week", best),
                             ("Player Most Under Projection, Single Week", worst)):
        tied = [e for e in events if e["diff"] == target]
        first = tied[0]
        out.append((category, f"{target:+.1f} ({first['actual']:.1f} vs {first['projected']:.1f} proj)",
                    [(holder(e), e["season"], e["week"]) for e in tied]))

    seasons: dict[tuple, dict] = {}
    for e in events:
        s = seasons.setdefault((e["owner"], e["player_id"], e["season"]), {"e": e, "diff": 0.0, "starts": 0})
        s["diff"] += e["diff"]
        s["starts"] += 1
    totals = [{**v, "diff": round(v["diff"], 1)} for v in seasons.values()]
    best_s = max(t["diff"] for t in totals)
    worst_s = min(t["diff"] for t in totals)
    for category, target in (("Player Most Over Projection, Single Season", best_s),
                             ("Player Most Under Projection, Single Season", worst_s)):
        tied = [t for t in totals if t["diff"] == target]
        out.append((category, f"{target:+.1f} over {tied[0]['starts']} starts",
                    [(holder(t["e"]), t["e"]["season"], None) for t in tied]))
    return out
