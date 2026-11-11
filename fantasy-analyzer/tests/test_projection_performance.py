"""Tests for analysis/projection_performance.py -- starters' actual vs. Sleeper
projections per owner per week, summed over the season."""

import json
import sqlite3

import pytest

from fantasy_analyzer.analysis.projection_performance import get_projection_performance
from fantasy_analyzer.db.schema import DDL


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.execute(
        "INSERT INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start) "
        "VALUES ('L1', 2026, 'Test', 'in_season', 2, 15)"
    )
    for i, (uid, name) in enumerate([("u1", "Alice"), ("u2", "Bob")], 1):
        con.execute("INSERT INTO owners (user_id, canonical_name) VALUES (?,?)", (uid, name))
        con.execute("INSERT INTO league_owners (league_id, user_id, roster_id) VALUES ('L1', ?, ?)", (uid, i))
    for pid, pos in [("a1", "RB"), ("a2", "WR"), ("b1", "RB"), ("b2", "WR"), ("bench", "WR")]:
        con.execute("INSERT INTO players (player_id, full_name, position) VALUES (?,?,?)", (pid, pid, pos))
    con.commit()
    return con


def _week(con, week, scores, projections, pool=None):
    """scores: {uid: points}; projections: {player_id: proj}; pool: {uid: {pid: pts}} for efficiency."""
    starters = {"u1": ["a1", "a2"], "u2": ["b1", "b2"]}
    for rid, uid in enumerate(["u1", "u2"], 1):
        con.execute(
            "INSERT INTO matchups (league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff, "
            "starters_json, players_points_json) VALUES ('L1', 2026, ?, 1, ?, ?, ?, 0, ?, ?)",
            (week, rid, uid, scores[uid], json.dumps(starters[uid]),
             json.dumps(pool[uid]) if pool else None),
        )
    for pid, p in projections.items():
        con.execute(
            "INSERT INTO player_projections (season, week, player_id, position, projected_pts, scraped_at) "
            "VALUES (2026, ?, ?, 'RB', ?, 'x')", (week, pid, p))
    con.commit()


class TestProjectionPerformance:
    def test_no_played_weeks_returns_empty(self, db):
        assert get_projection_performance(db, "L1", 2026) == {"season": 2026, "weeks": [], "rows": []}

    def test_weekly_diff_is_actual_minus_projected_of_started_players(self, db):
        # Alice projected 60+50=110, scored 130 -> +20. Bob projected 45+45=90, scored 80 -> -10.
        _week(db, 1, {"u1": 130.0, "u2": 80.0}, {"a1": 60, "a2": 50, "b1": 45, "b2": 45})
        rows = {r["owner"]: r for r in get_projection_performance(db, "L1", 2026)["rows"]}
        assert rows["Alice"]["weeks"][0] == {
            "week": 1, "actual": 130.0, "projected": 110.0, "diff": 20.0,
            "efficiency_pct": None, "pts_left_on_bench": None,
        }
        assert rows["Bob"]["weeks"][0]["diff"] == -10.0

    def test_season_totals_and_ordering_and_recent_average(self, db):
        _week(db, 1, {"u1": 130.0, "u2": 80.0}, {"a1": 60, "a2": 50, "b1": 45, "b2": 45})   # +20 / -10
        _week(db, 2, {"u1": 100.0, "u2": 100.0}, {"a1": 55, "a2": 55, "b1": 40, "b2": 50})  # -10 / +10
        _week(db, 3, {"u1": 90.0, "u2": 110.0}, {"a1": 40, "a2": 40, "b1": 50, "b2": 50})   # +10 / +10
        _week(db, 4, {"u1": 100.0, "u2": 70.0}, {"a1": 50, "a2": 50, "b1": 50, "b2": 50})   # 0 / -30
        result = get_projection_performance(db, "L1", 2026)
        assert result["weeks"] == [1, 2, 3, 4]
        alice, bob = result["rows"]
        assert (alice["owner"], bob["owner"]) == ("Alice", "Bob")  # +20 beats -20 -> Alice first
        assert alice["total_diff"] == 20.0 and bob["total_diff"] == -20.0
        assert alice["avg_diff"] == 5.0
        assert alice["recent_avg_diff"] == 0.0   # last 3 weeks: -10, +10, 0
        assert bob["recent_avg_diff"] == -3.3    # last 3 weeks: +10, +10, -30

    def test_starter_without_a_projection_counts_as_zero_projected(self, db):
        # a2 has no Sleeper projection (out/inactive): projected is just a1's 60.
        _week(db, 1, {"u1": 100.0, "u2": 80.0}, {"a1": 60, "b1": 45, "b2": 45})
        alice = next(r for r in get_projection_performance(db, "L1", 2026)["rows"] if r["owner"] == "Alice")
        assert alice["weeks"][0]["projected"] == 60.0 and alice["weeks"][0]["diff"] == 40.0

    def test_team_week_with_no_projection_data_is_skipped(self, db):
        _week(db, 1, {"u1": 100.0, "u2": 90.0}, {"a1": 50, "a2": 50})   # only Alice's starters projected
        rows = {r["owner"]: r for r in get_projection_performance(db, "L1", 2026)["rows"]}
        assert "Bob" not in rows and rows["Alice"]["total_diff"] == 0.0

    def test_efficiency_reported_separately_from_over_under(self, db):
        # Alice started a1 (30) + a2 (20) = 50 but left "bench" (45) on the bench: optimal is higher.
        pool = {"u1": {"a1": 30.0, "a2": 20.0, "bench": 45.0}, "u2": {"b1": 40.0, "b2": 40.0}}
        _week(db, 1, {"u1": 50.0, "u2": 80.0}, {"a1": 25, "a2": 25, "b1": 40, "b2": 40}, pool)
        rows = {r["owner"]: r for r in get_projection_performance(db, "L1", 2026)["rows"]}
        a, b = rows["Alice"], rows["Bob"]
        assert a["total_diff"] == 0.0                      # played exactly to projection...
        assert a["efficiency_pct"] < 100 and a["pts_left_on_bench"] > 0   # ...but started the wrong guys
        assert b["efficiency_pct"] == 100.0 and b["pts_left_on_bench"] == 0.0
