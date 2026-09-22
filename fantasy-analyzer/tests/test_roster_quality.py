"""Tests for analysis/roster_quality.py -- the roster-quality prior used in
power rankings.

Regression coverage for a real bug: FantasyPros' free weekly projections page
only exposes the top 10 players per position (the rest requires their paid
MVP tier), which starved most rosters of matched players and made whoever
got unlucky look like the league's worst roster. Switched the data source to
Sleeper's own season-long projections (full coverage, no paywall) and added
a minimum-matched-players guard so a still-sparse result is treated as no
data rather than as a real signal.
"""

import sqlite3

import pytest

from fantasy_analyzer.analysis.roster_quality import compute_roster_quality
from fantasy_analyzer.db.schema import DDL


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


def _league_owner(con, league_id, user_id, roster_id, canonical_name):
    con.execute(
        "INSERT OR IGNORE INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start) "
        "VALUES (?,?,?,?,?,?)",
        (league_id, 2026, "Test League", "in_season", 12, 15),
    )
    con.execute("INSERT OR IGNORE INTO owners (user_id, canonical_name) VALUES (?,?)", (user_id, canonical_name))
    con.execute(
        "INSERT INTO league_owners (league_id, user_id, roster_id) VALUES (?,?,?)",
        (league_id, user_id, roster_id),
    )
    con.commit()


def _roster(con, league_id, roster_id, player_ids):
    con.executemany(
        "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) VALUES (?,?,?,?,?)",
        [(league_id, roster_id, pid, "active", "2026-01-01") for pid in player_ids],
    )
    con.commit()


def _season_projections(con, season, projections):
    """projections: {player_id: (position, projected_pts)}"""
    con.executemany(
        "INSERT INTO player_season_projections (season, player_id, position, projected_pts, scraped_at) "
        "VALUES (?,?,?,?,?)",
        [(season, pid, pos, pts, "2026-01-01") for pid, (pos, pts) in projections.items()],
    )
    con.commit()


class TestComputeRosterQuality:
    def test_no_projection_data_returns_empty(self, db):
        _league_owner(db, "L1", "u1", 1, "Alice")
        assert compute_roster_quality(db, "L1", 2026) == {}

    def test_too_few_matched_players_returns_none(self, db):
        """A roster that only matched a couple of players shouldn't be treated
        as a real 'worst roster in the league' signal -- it's just missing data."""
        _league_owner(db, "L1", "u1", 1, "Alice")
        _roster(db, "L1", 1, ["p1", "p2", "p3", "p4", "p5", "p6"])
        _season_projections(db, 2026, {"p1": ("QB", 20.0), "p2": ("RB", 15.0)})  # only 2 of 6 matched

        result = compute_roster_quality(db, "L1", 2026)
        assert result["u1"] is None

    def test_enough_matched_players_computes_optimal_lineup(self, db):
        _league_owner(db, "L1", "u1", 1, "Alice")
        _roster(db, "L1", 1, ["qb", "rb", "wr1", "wr2", "te", "extra"])
        _season_projections(db, 2026, {
            "qb": ("QB", 20.0), "rb": ("RB", 15.0), "wr1": ("WR", 12.0),
            "wr2": ("WR", 10.0), "te": ("TE", 8.0), "extra": ("RB", 5.0),
        })

        result = compute_roster_quality(db, "L1", 2026)
        assert result["u1"] == pytest.approx(20.0 + 15.0 + 12.0 + 10.0 + 8.0 + 5.0)

    def test_zero_point_projections_are_excluded(self, db):
        _league_owner(db, "L1", "u1", 1, "Alice")
        _roster(db, "L1", 1, ["qb", "rb", "wr1", "wr2", "te", "bench"])
        _season_projections(db, 2026, {
            "qb": ("QB", 20.0), "rb": ("RB", 15.0), "wr1": ("WR", 12.0),
            "wr2": ("WR", 10.0), "te": ("TE", 8.0), "bench": ("WR", 0.0),
        })

        result = compute_roster_quality(db, "L1", 2026)
        # "bench" (0.0 pts) doesn't count toward the 5-player minimum or the total
        assert result["u1"] == pytest.approx(20.0 + 15.0 + 12.0 + 10.0 + 8.0)

    def test_only_pulls_the_requested_season(self, db):
        _league_owner(db, "L1", "u1", 1, "Alice")
        _roster(db, "L1", 1, ["p1", "p2", "p3", "p4", "p5"])
        _season_projections(db, 2025, {
            "p1": ("QB", 20.0), "p2": ("RB", 15.0), "p3": ("WR", 12.0),
            "p4": ("WR", 10.0), "p5": ("TE", 8.0),
        })

        assert compute_roster_quality(db, "L1", 2026) == {}
