"""Tests for analysis/start_sit.py — lineup efficiency (start/sit) analysis."""

import json
import sqlite3

import pytest

from fantasy_analyzer.analysis.start_sit import (
    get_start_sit_leaderboard,
    get_start_sit_weeks,
    optimal_lineup_pts,
)
from fantasy_analyzer.db.schema import DDL


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


def _league(con, league_id="L1", season=2024, pws=15, last_week=17):
    con.execute(
        "INSERT INTO leagues "
        "(league_id, season, name, status, total_rosters, playoff_week_start, last_scored_leg) "
        "VALUES (?,?,?,?,?,?,?)",
        (league_id, season, "Test League", "complete", 12, pws, last_week),
    )
    con.commit()


def _owners(con, *pairs):
    con.executemany("INSERT INTO owners (user_id, canonical_name) VALUES (?,?)", pairs)
    con.commit()


def _players(con, *rows):
    """_players(db, ('p1', 'QB'), ('p2', 'RB'))"""
    con.executemany(
        "INSERT INTO players (player_id, full_name, position) VALUES (?,?,?)",
        [(pid, pid, pos) for pid, pos in rows],
    )
    con.commit()


_rid = 0


def _matchup(con, league_id, season, week, matchup_id, user_id, points, players_points, is_playoff=0):
    global _rid
    _rid += 1
    con.execute(
        "INSERT INTO matchups "
        "(league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff, players_points_json) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (league_id, season, week, matchup_id, _rid, user_id, points, is_playoff, json.dumps(players_points)),
    )
    con.commit()


# ---------------------------------------------------------------------------
# optimal_lineup_pts
# ---------------------------------------------------------------------------

class TestOptimalLineupPts:
    def test_fills_locked_slots_with_best_available(self):
        players = [
            {"position": "QB", "points": 20.0},
            {"position": "QB", "points": 10.0},
            {"position": "RB", "points": 15.0},
            {"position": "WR", "points": 12.0},
            {"position": "WR", "points": 8.0},
            {"position": "TE", "points": 5.0},
        ]
        # Locked QB/RB/WR/WR/TE = 20+15+12+8+5 = 60. The backup QB (10) has no other
        # competition for the 4 open flex slots, so it fills one: 60 + 10 = 70.
        assert optimal_lineup_pts(players, num_flex=4) == pytest.approx(70.0)

    def test_flex_pool_takes_best_remaining_non_qb(self):
        players = [
            {"position": "QB", "points": 20.0},
            {"position": "RB", "points": 15.0},
            {"position": "RB", "points": 14.0},  # flex candidate
            {"position": "WR", "points": 12.0},
            {"position": "WR", "points": 8.0},
            {"position": "WR", "points": 6.0},  # flex candidate
            {"position": "TE", "points": 5.0},
            {"position": "TE", "points": 4.0},  # flex candidate
        ]
        # Locked: 20+15+12+8+5 = 60. Flex (num_flex=4) from remaining {14,6,4}: all three = 24.
        assert optimal_lineup_pts(players, num_flex=4) == pytest.approx(84.0)

    def test_second_qb_only_used_in_flex_when_it_beats_worst_flex_candidate(self):
        players = [
            {"position": "QB", "points": 20.0},
            {"position": "QB", "points": 30.0},  # better than the locked QB — still only 1 locked QB slot
            {"position": "RB", "points": 15.0},
            {"position": "WR", "points": 12.0},
            {"position": "WR", "points": 1.0},
            {"position": "TE", "points": 5.0},
        ]
        # Locked QB takes the best QB (30), RB/WR/WR/TE = 15+12+1+5.
        # Remaining QB (20) competes for 1 flex slot against the leftover pool (empty) — wins by default.
        assert optimal_lineup_pts(players, num_flex=4) == pytest.approx(30.0 + 15.0 + 12.0 + 1.0 + 5.0 + 20.0)

    def test_flex_qb_excluded_when_worse_than_non_qb_alternatives(self):
        players = [
            {"position": "QB", "points": 20.0},
            {"position": "QB", "points": 2.0},  # weak 2nd QB, shouldn't make the flex cut
            {"position": "RB", "points": 15.0},
            {"position": "RB", "points": 10.0},
            {"position": "RB", "points": 9.0},
            {"position": "RB", "points": 8.0},
            {"position": "RB", "points": 7.0},
            {"position": "WR", "points": 12.0},
            {"position": "WR", "points": 7.0},
            {"position": "TE", "points": 5.0},
        ]
        # Locked: QB(20) + RB(15) + WR(12)+WR(7) + TE(5) = 59
        # Flex pool (non-QB remaining): RB 10,9,8,7 fills all 4 flex slots = 34.
        # 2nd QB (2.0) doesn't beat the worst of those (7), so it's excluded entirely.
        assert optimal_lineup_pts(players, num_flex=4) == pytest.approx(59.0 + 34.0)

    def test_empty_pool_returns_zero(self):
        assert optimal_lineup_pts([], num_flex=4) == 0.0

    def test_respects_num_flex_for_pre_sflex_seasons(self):
        players = [
            {"position": "QB", "points": 20.0},
            {"position": "RB", "points": 15.0},
            {"position": "RB", "points": 14.0},
            {"position": "WR", "points": 12.0},
            {"position": "WR", "points": 8.0},
            {"position": "WR", "points": 6.0},
            {"position": "TE", "points": 5.0},
        ]
        # Locked: 20+15+12+8+5=60. Remaining non-qb: {14, 6}.
        # num_flex=3 (pre-2023) takes top 3 of {14, 6} = 20.
        assert optimal_lineup_pts(players, num_flex=3) == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# get_start_sit_weeks
# ---------------------------------------------------------------------------

class TestGetStartSitWeeks:
    def test_actual_vs_optimal_basic(self, db):
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"))
        _players(db, ("qb1", "QB"), ("rb1", "RB"), ("rb2", "RB"), ("wr1", "WR"), ("wr2", "WR"), ("te1", "TE"))
        # Alice started rb1 (8 pts) but rb2 (18 pts) was on her bench — suboptimal.
        players_points = {"qb1": 20.0, "rb1": 8.0, "rb2": 18.0, "wr1": 10.0, "wr2": 9.0, "te1": 5.0}
        # actual score = sum of what she actually started (not derivable from this fixture alone,
        # so we set m.points directly as the team's real total for the week).
        _matchup(db, "L1", 2024, 1, 1, "u1", 52.0, players_points)

        weeks = get_start_sit_weeks(db, season=2024)
        assert len(weeks) == 1
        w = weeks[0]
        assert w["owner"] == "Alice"
        assert w["actual_pts"] == 52.0
        # Optimal: locked QB(20)+RB(18)+WR(10)+WR(9)+TE(5)=62, plus the leftover
        # RB (rb1, 8 pts) fills one of the open flex slots = 70.
        assert w["optimal_pts"] == pytest.approx(70.0)
        assert w["pct"] == pytest.approx(52.0 / 70.0 * 100, abs=0.1)
        assert w["pts_left_on_bench"] == pytest.approx(18.0)

    def test_unknown_player_positions_are_ignored(self, db):
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"))
        _players(db, ("qb1", "QB"))
        players_points = {"qb1": 20.0, "ghost": 99.0}  # "ghost" has no row in players table
        _matchup(db, "L1", 2024, 1, 1, "u1", 20.0, players_points)

        weeks = get_start_sit_weeks(db, season=2024)
        assert weeks[0]["optimal_pts"] == pytest.approx(20.0)

    def test_playoff_weeks_excluded_when_requested(self, db):
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"))
        _players(db, ("qb1", "QB"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 20.0, {"qb1": 20.0}, is_playoff=0)
        _matchup(db, "L1", 2024, 15, 1, "u1", 25.0, {"qb1": 25.0}, is_playoff=1)

        all_weeks = get_start_sit_weeks(db, season=2024, include_playoffs=True)
        reg_only = get_start_sit_weeks(db, season=2024, include_playoffs=False)
        assert len(all_weeks) == 2
        assert len(reg_only) == 1
        assert reg_only[0]["week"] == 1

    def test_season_filter(self, db):
        _league(db, league_id="L1", season=2024)
        _league(db, league_id="L2", season=2025)
        _owners(db, ("u1", "Alice"))
        _players(db, ("qb1", "QB"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 20.0, {"qb1": 20.0})
        _matchup(db, "L2", 2025, 1, 1, "u1", 25.0, {"qb1": 25.0})

        weeks_2024 = get_start_sit_weeks(db, season=2024)
        assert len(weeks_2024) == 1
        assert weeks_2024[0]["season"] == 2024

        all_weeks = get_start_sit_weeks(db, season=None)
        assert len(all_weeks) == 2

    def test_zero_optimal_skipped(self, db):
        """A week with no usable positional data (optimal == 0) shouldn't appear."""
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 0.0, {})
        assert get_start_sit_weeks(db, season=2024) == []


# ---------------------------------------------------------------------------
# get_start_sit_leaderboard
# ---------------------------------------------------------------------------

class TestGetStartSitLeaderboard:
    @pytest.fixture(autouse=True)
    def _seed(self, db):
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"))
        _players(db, ("qb1", "QB"))
        # Week 1: perfect lineup (100%). Week 2: left points on the bench.
        _matchup(db, "L1", 2024, 1, 1, "u1", 20.0, {"qb1": 20.0})
        _matchup(db, "L1", 2024, 2, 1, "u1", 10.0, {"qb1": 20.0})
        self.db = db

    def test_aggregates_per_owner(self):
        board = get_start_sit_leaderboard(self.db, season=2024)
        assert len(board) == 1
        row = board[0]
        assert row["owner"] == "Alice"
        assert row["weeks"] == 2
        assert row["total_actual"] == pytest.approx(30.0)
        assert row["total_optimal"] == pytest.approx(40.0)
        assert row["total_left_on_bench"] == pytest.approx(10.0)
        assert row["avg_pct"] == pytest.approx((100.0 + 50.0) / 2, abs=0.1)

    def test_best_and_worst_week(self):
        row = get_start_sit_leaderboard(self.db, season=2024)[0]
        assert row["best_week"]["week"] == 1
        assert row["best_week"]["pct"] == pytest.approx(100.0)
        assert row["worst_week"]["week"] == 2
        assert row["worst_week"]["pct"] == pytest.approx(50.0)

    def test_sorted_by_avg_pct_desc(self, db):
        _owners(db, ("u2", "Bob"))
        _players(db, ("rb1", "RB"))
        # Bob always starts his only player optimally -> 100% avg, should rank above Alice (75% avg).
        _matchup(db, "L1", 2024, 1, 2, "u2", 15.0, {"rb1": 15.0})
        _matchup(db, "L1", 2024, 2, 2, "u2", 15.0, {"rb1": 15.0})

        board = get_start_sit_leaderboard(db, season=2024)
        assert board[0]["owner"] == "Bob"
        assert board[1]["owner"] == "Alice"

    def test_empty_when_no_data(self):
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)
        assert get_start_sit_leaderboard(con) == []
