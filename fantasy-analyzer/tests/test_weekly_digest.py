"""Tests for analysis/weekly_digest.py -- homepage weekly recap + preview."""

import json
import sqlite3

import pytest

from fantasy_analyzer.analysis.weekly_digest import get_weekly_preview, get_weekly_recap
from fantasy_analyzer.db.schema import DDL


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


def _league(con, league_id="L1", season=2026, pws=15):
    con.execute(
        "INSERT INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start) "
        "VALUES (?,?,?,?,?,?)",
        (league_id, season, "Test League", "in_season", 4, pws),
    )
    con.commit()


def _owner(con, league_id, user_id, roster_id, name):
    con.execute("INSERT OR IGNORE INTO owners (user_id, canonical_name) VALUES (?,?)", (user_id, name))
    con.execute("INSERT INTO league_owners (league_id, user_id, roster_id) VALUES (?,?,?)",
                (league_id, user_id, roster_id))
    con.commit()


_rid = 100


def _matchup(con, league_id, week, matchup_id, user_id, points, starters=None, players_points=None):
    global _rid
    _rid += 1
    con.execute(
        "INSERT INTO matchups (league_id, season, week, matchup_id, roster_id, user_id, points, "
        "is_playoff, starters_json, players_points_json) VALUES (?,?,?,?,?,?,?,0,?,?)",
        (league_id, 2026, week, matchup_id, _rid, user_id, points,
         json.dumps(starters) if starters is not None else None,
         json.dumps(players_points) if players_points is not None else None),
    )
    con.commit()


def _player(con, player_id, name, position, team=None):
    con.execute("INSERT INTO players (player_id, full_name, position, team) VALUES (?,?,?,?)",
                (player_id, name, position, team))
    con.commit()


def _roster(con, league_id, roster_id, player_ids):
    con.executemany(
        "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) VALUES (?,?,?,?,?)",
        [(league_id, roster_id, pid, "active", "2026-01-01") for pid in player_ids],
    )
    con.commit()


def _week_proj(con, season, week, projections):
    """projections: {player_id: (position, projected_pts)} -- weekly (not season-long)
    projections, since that's what the Weekly Preview panel is now sourced from."""
    con.executemany(
        "INSERT INTO player_projections (season, week, player_id, position, projected_pts, scraped_at) "
        "VALUES (?,?,?,?,?,?)",
        [(season, week, pid, pos, pts, "2026-01-01") for pid, (pos, pts) in projections.items()],
    )
    con.commit()


class TestGetWeeklyRecap:
    def test_no_completed_week_returns_none(self, db):
        _league(db)
        assert get_weekly_recap(db, "L1") is None

    def test_finds_closest_and_blowout(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _owner(db, "L1", "u3", 3, "Carl")
        _owner(db, "L1", "u4", 4, "Dana")
        # Matchup 1: close game (2.0 margin). Matchup 2: blowout (100 margin).
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 98.0)
        _matchup(db, "L1", 1, 2, "u3", 150.0)
        _matchup(db, "L1", 1, 2, "u4", 50.0)

        recap = get_weekly_recap(db, "L1")
        assert recap["week"] == 1
        assert recap["closest"]["margin"] == pytest.approx(2.0)
        assert recap["blowout"]["margin"] == pytest.approx(100.0)
        assert recap["blowout"]["winner"] == "Carl"

    def test_top_player_only_counts_starters(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _player(db, "bench_star", "Bench Guy", "WR")
        _player(db, "starter", "Starter Guy", "WR")
        _matchup(
            db, "L1", 1, 1, "u1", 100.0,
            starters=["starter"],
            players_points={"starter": 30.0, "bench_star": 99.0},  # bench_star scored more but didn't start
        )
        _matchup(db, "L1", 1, 1, "u2", 90.0, starters=[], players_points={})

        recap = get_weekly_recap(db, "L1")
        assert recap["top_player"]["name"] == "Starter Guy"
        assert recap["top_player"]["points"] == pytest.approx(30.0)
        assert recap["top_player"]["owner"] == "Alice"


class TestGetWeeklyPreview:
    def test_no_upcoming_matchups_returns_none(self, db):
        _league(db)
        assert get_weekly_preview(db, "L1", 2026, 15) is None

    def test_returns_none_once_regular_season_is_over(self, db):
        _league(db, pws=2)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        # last completed week (1) + 1 == pws (2) -> playoffs, not a regular preview week
        assert get_weekly_preview(db, "L1", 2026, 2) is None

    def test_projected_gap_and_closest_match(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _owner(db, "L1", "u3", 3, "Carl")
        _owner(db, "L1", "u4", 4, "Dana")
        # Week 1 already played so week 2 is the upcoming preview week
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        _matchup(db, "L1", 2, 1, "u1", 0.0)
        _matchup(db, "L1", 2, 1, "u2", 0.0)
        _matchup(db, "L1", 2, 2, "u3", 0.0)
        _matchup(db, "L1", 2, 2, "u4", 0.0)

        players = {
            "u1": [("qb1", "QB", 20.0), ("rb1", "RB", 15.0), ("wr1", "WR", 12.0), ("wr2", "WR", 10.0), ("te1", "TE", 8.0)],
            "u2": [("qb2", "QB", 19.0), ("rb2", "RB", 14.0), ("wr3", "WR", 11.0), ("wr4", "WR", 9.0), ("te2", "TE", 7.0)],
            "u3": [("qb3", "QB", 5.0), ("rb3", "RB", 5.0), ("wr5", "WR", 5.0), ("wr6", "WR", 5.0), ("te3", "TE", 5.0)],
        }
        for uid, roster in players.items():
            roster_id = {"u1": 1, "u2": 2, "u3": 3}[uid]
            for pid, pos, _ in roster:
                _player(db, pid, pid, pos)
            _roster(db, "L1", roster_id, [pid for pid, _, _ in roster])
            _week_proj(db, 2026, 2, {pid: (pos, pts) for pid, pos, pts in roster})
        # u4 (Dana) intentionally left with no projections at all -> null projected total

        preview = get_weekly_preview(db, "L1", 2026, 15)
        assert preview["week"] == 2
        by_owner = {}
        for m in preview["matchups"]:
            by_owner[m["a"]["owner"]] = m["a"]
            by_owner[m["b"]["owner"]] = m["b"]

        assert by_owner["Alice"]["projected"] == pytest.approx(65.0)   # 20+15+12+10+8
        assert by_owner["Bob"]["projected"] == pytest.approx(60.0)     # 19+14+11+9+7
        assert by_owner["Dana"]["projected"] is None                   # no data at all

        alice_bob = next(m for m in preview["matchups"] if {"Alice", "Bob"} == {m["a"]["owner"], m["b"]["owner"]})
        assert alice_bob["proj_gap"] == pytest.approx(5.0)

        carl_dana = next(m for m in preview["matchups"] if {"Carl", "Dana"} == {m["a"]["owner"], m["b"]["owner"]})
        assert carl_dana["proj_gap"] is None  # Dana has no projection at all

        # Alice/Bob (5.0 gap) is closer than Carl (0 gap would be self, but here proj_gap
        # is None for Carl/Dana), so Alice/Bob must be the closest known projected matchup
        assert preview["closest_projected"]["proj_gap"] == pytest.approx(5.0)

    def test_too_few_matched_players_gives_null_projection(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        _matchup(db, "L1", 2, 1, "u1", 0.0)
        _matchup(db, "L1", 2, 1, "u2", 0.0)

        _player(db, "p1", "P1", "QB")
        _player(db, "p2", "P2", "RB")
        _roster(db, "L1", 1, ["p1", "p2"])  # only 2 players matched -- below the minimum
        _week_proj(db, 2026, 2, {"p1": ("QB", 20.0), "p2": ("RB", 15.0)})

        preview = get_weekly_preview(db, "L1", 2026, 15)
        alice = next(s for m in preview["matchups"] for s in (m["a"], m["b"]) if s["owner"] == "Alice")
        assert alice["projected"] is None

    def test_bye_count_reflects_nfl_byes_table(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        _matchup(db, "L1", 2, 1, "u1", 0.0)
        _matchup(db, "L1", 2, 1, "u2", 0.0)

        _player(db, "p1", "P1", "QB", team="BUF")
        _player(db, "p2", "P2", "RB", team="MIA")
        _roster(db, "L1", 1, ["p1", "p2"])
        db.execute("INSERT INTO nfl_byes (season, week, team) VALUES (2026, 2, 'BUF')")
        db.commit()

        preview = get_weekly_preview(db, "L1", 2026, 15)
        alice = next(s for m in preview["matchups"] for s in (m["a"], m["b"]) if s["owner"] == "Alice")
        assert alice["bye_count"] == 1
