"""Tests for analysis/projection_performance.py -- starters' actual vs. Sleeper
projections per owner per week, summed over the season."""

import json
import sqlite3

import pytest

from fantasy_analyzer.analysis.projection_performance import (
    get_owner_player_performance,
    get_projection_performance,
)
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
        assert get_projection_performance(db, "L1", 2026) == {
            "season": 2026, "weeks": [], "league_avg_diff": None, "rows": [],
        }

    def test_weekly_diff_is_actual_minus_projected_of_started_players(self, db):
        # Alice projected 60+50=110, scored 130 -> +20. Bob projected 45+45=90, scored 80 -> -10.
        _week(db, 1, {"u1": 130.0, "u2": 80.0}, {"a1": 60, "a2": 50, "b1": 45, "b2": 45})
        rows = {r["owner"]: r for r in get_projection_performance(db, "L1", 2026)["rows"]}
        assert rows["Alice"]["weeks"][0] == {
            "week": 1, "actual": 130.0, "projected": 110.0, "diff": 20.0, "diff_vs_league": 15.0,
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


class TestVsLeagueAverage:
    def test_each_week_is_centered_on_the_league_average(self, db):
        # Week 1: Alice +20, Bob -10 -> league avg +5, so +15 / -15.
        # Week 2: Alice -10, Bob -30 -> league avg -20, so +10 / -10.
        _week(db, 1, {"u1": 130.0, "u2": 80.0}, {"a1": 60, "a2": 50, "b1": 45, "b2": 45})
        _week(db, 2, {"u1": 90.0, "u2": 60.0}, {"a1": 50, "a2": 50, "b1": 45, "b2": 45})
        result = get_projection_performance(db, "L1", 2026)
        rows = {r["owner"]: r for r in result["rows"]}
        assert result["league_avg_diff"] == -7.5                 # (20 - 10 - 10 - 30) / 4
        assert rows["Alice"]["total_vs_league"] == 25.0          # 15 + 10
        assert rows["Bob"]["total_vs_league"] == -25.0
        assert rows["Alice"]["total_vs_league"] + rows["Bob"]["total_vs_league"] == 0
        assert rows["Alice"]["total_diff"] == 10.0               # raw over/under is unchanged


class TestOwnerPlayerPerformance:
    def _games(self, db):
        """Alice's roster: a1, a2 start both weeks; `bench` sits; `ghost` is on the bench but never plays."""
        for week, pts, pool in [
            (1, 50.0, {"a1": 30.0, "a2": 20.0, "bench": 25.0, "ghost": 0.0}),   # team points = the starters' points
            (2, 50.0, {"a1": 10.0, "a2": 40.0, "bench": 0.0, "ghost": 0.0}),
        ]:
            db.execute(
                "INSERT INTO matchups (league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff, "
                "starters_json, players_points_json) VALUES ('L1', 2026, ?, 1, 1, 'u1', ?, 0, ?, ?)",
                (week, pts, json.dumps(["a1", "a2"]), json.dumps(pool)),
            )
        for week, pid, p in [(1, "a1", 20), (1, "a2", 25), (1, "bench", 15), (2, "a1", 25), (2, "a2", 30), (2, "bench", 12)]:
            db.execute("INSERT INTO player_projections (season, week, player_id, position, projected_pts, scraped_at) "
                       "VALUES (2026, ?, ?, 'RB', ?, 'x')", (week, pid, p))
        db.commit()

    def test_unknown_owner_or_no_games_returns_empty(self, db):
        assert get_owner_player_performance(db, "Nobody", 2026)["rows"] == []
        assert get_owner_player_performance(db, "Alice", 2026)["rows"] == []

    def test_weekly_entries_and_totals_split_by_starter_and_bench(self, db):
        self._games(db)
        rows = {r["player"]: r for r in get_owner_player_performance(db, "Alice", 2026)["rows"]}
        a1 = rows["a1"]
        assert [(w["week"], w["actual"], w["projected"], w["diff"], w["role"]) for w in a1["weeks"]] == [
            (1, 30.0, 20.0, 10.0, "starter"), (2, 10.0, 25.0, -15.0, "starter"),
        ]
        assert a1["totals"]["starter"] == {"games": 2, "actual": 40.0, "projected": 45.0, "diff": -5.0, "avg_diff": -2.5}
        assert a1["totals"]["bench"]["games"] == 0 and a1["totals"]["bench"]["avg_diff"] is None

        bench = rows["bench"]   # sat both weeks: scored 25 vs 15 projected, then 0 vs 12 projected
        assert bench["totals"]["bench"]["diff"] == -2.0 and bench["totals"]["starter"]["games"] == 0
        assert bench["totals"]["all"]["games"] == 2

    def test_inactive_bench_player_is_left_out_but_a_started_one_is_kept(self, db):
        self._games(db)
        names = {r["player"] for r in get_owner_player_performance(db, "Alice", 2026)["rows"]}
        assert "ghost" not in names   # bench, no projection, 0 points both weeks

        # Start the same unprojected 0-point player in week 1: he held a lineup slot, so he shows up.
        db.execute("UPDATE matchups SET starters_json=? WHERE week=1", (json.dumps(["a1", "ghost"]),))
        db.commit()
        ghost = next(r for r in get_owner_player_performance(db, "Alice", 2026)["rows"] if r["player"] == "ghost")
        assert ghost["weeks"] == [{"week": 1, "actual": 0.0, "projected": None, "diff": 0.0, "role": "starter"}]

    def test_unprojected_player_who_scores_counts_as_zero_projected(self, db):
        self._games(db)
        db.execute("UPDATE matchups SET players_points_json=? WHERE week=1",
                   (json.dumps({"a1": 30.0, "a2": 20.0, "surprise": 14.0}),))
        db.commit()
        surprise = next(r for r in get_owner_player_performance(db, "Alice", 2026)["rows"] if r["player"] == "surprise")
        assert surprise["weeks"][0]["projected"] is None and surprise["weeks"][0]["diff"] == 14.0

    def test_starter_diffs_add_up_to_the_team_level_over_under(self, db):
        self._games(db)
        # a1, a2 are Alice's only starters; every starter has a projection here, so the two views must agree.
        team = next(r for r in get_projection_performance(db, "L1", 2026)["rows"] if r["owner"] == "Alice")
        player_sum = sum(r["totals"]["starter"]["diff"] for r in get_owner_player_performance(db, "Alice", 2026)["rows"])
        assert player_sum == pytest.approx(team["total_diff"])
