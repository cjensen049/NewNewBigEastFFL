"""Tests for analysis/history.py::get_league_records — tie handling.

A record value tied by 2 or fewer owners lists every tied owner. A value
tied by more than 2 shows only the most recent occurrence as Holder, with
a Notes field recording the total count (so a value that's easy to hit,
e.g. a perfect lineup-efficiency week, isn't attributed to whoever happened
to do it first).
"""

import sqlite3

import pytest

from fantasy_analyzer.analysis.history import get_league_records
from fantasy_analyzer.db.schema import DDL


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


def _season_record(con, league_id, user_id, season, wins=0, losses=0, fpts=0.0, fpts_against=0.0, ppts=0.0):
    con.execute(
        "INSERT INTO season_records "
        "(league_id, user_id, season, wins, losses, ties, fpts, fpts_against, ppts) "
        "VALUES (?,?,?,?,?,0,?,?,?)",
        (league_id, user_id, season, wins, losses, fpts, fpts_against, ppts),
    )
    con.commit()


_rid = 0


def _matchup(con, league_id, season, week, matchup_id, user_id, points, is_playoff=0):
    global _rid
    _rid += 1
    con.execute(
        "INSERT INTO matchups (league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (league_id, season, week, matchup_id, _rid, user_id, points, is_playoff),
    )
    con.commit()


def _by_category(records, category):
    return next(r for r in records if r["Category"] == category)


# ---------------------------------------------------------------------------
# Event-style records (single week / single season — have a time axis)
# ---------------------------------------------------------------------------

class TestEventRecordTies:
    def test_no_tie_holder_unaffected(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _season_record(db, "L1", "u1", 2024, wins=10)
        _season_record(db, "L1", "u2", 2024, wins=5)

        rec = _by_category(get_league_records(db), "Most Wins, Single Season")
        assert rec["Holder"] == "Alice"
        assert rec["Notes"] == ""

    def test_two_way_tie_lists_both_owners_chronologically(self, db):
        _league(db, league_id="L1", season=2024)
        _league(db, league_id="L2", season=2025)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _season_record(db, "L1", "u1", 2024, wins=14)
        _season_record(db, "L2", "u2", 2025, wins=14)

        rec = _by_category(get_league_records(db), "Most Wins, Single Season")
        assert rec["Holder"] == "Alice, Bob"
        assert rec["Season"] == "2024, 2025"
        assert rec["Notes"] == ""

    def test_three_way_tie_shows_most_recent_owner_and_count(self, db):
        _league(db, league_id="L1", season=2024)
        _league(db, league_id="L2", season=2025)
        _league(db, league_id="L3", season=2026)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol"))
        _season_record(db, "L1", "u1", 2024, wins=14)
        _season_record(db, "L2", "u2", 2025, wins=14)
        _season_record(db, "L3", "u3", 2026, wins=14)

        rec = _by_category(get_league_records(db), "Most Wins, Single Season")
        assert rec["Holder"] == "Carol"  # most recent (2026), not Alice who did it first
        assert rec["Season"] == "2026"
        assert rec["Notes"] == "Achieved 3×"

    def test_most_recent_occurrence_itself_tied_lists_both(self, db):
        """If the *most recent* occurrence is shared by two owners, both are shown."""
        _league(db, league_id="L1", season=2024)
        _league(db, league_id="L2", season=2025)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol"))
        _season_record(db, "L1", "u1", 2024, wins=14)
        _season_record(db, "L2", "u2", 2025, wins=14)
        _season_record(db, "L2", "u3", 2025, wins=14)

        rec = _by_category(get_league_records(db), "Most Wins, Single Season")
        assert rec["Holder"] == "Bob, Carol"
        assert rec["Season"] == "2025"
        assert rec["Notes"] == "Achieved 3×"

    def test_weekly_points_tie_includes_week_in_context(self, db):
        _league(db, season=2024)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 50.0)
        _matchup(db, "L1", 2024, 3, 2, "u2", 50.0)

        rec = _by_category(get_league_records(db), "Fewest Points, Single Week")
        assert rec["Holder"] == "Alice, Bob"
        assert rec["Season"] == "2024 Wk1, 2024 Wk3"


# ---------------------------------------------------------------------------
# All-Time aggregate records (career sums/streaks/counts — no time axis)
# ---------------------------------------------------------------------------

class TestAllTimeRecordTies:
    def test_two_way_tie_no_notes(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _season_record(db, "L1", "u1", 2024, wins=10)
        _season_record(db, "L1", "u2", 2024, wins=10)

        rec = _by_category(get_league_records(db), "Most Wins, All-Time")
        assert rec["Holder"] == "Alice, Bob"
        assert rec["Season"] == "All-Time"
        assert rec["Notes"] == ""

    def test_three_way_tie_notes_owner_count_not_achieved_count(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol"))
        _season_record(db, "L1", "u1", 2024, wins=10)
        _season_record(db, "L1", "u2", 2024, wins=10)
        _season_record(db, "L1", "u3", 2024, wins=10)

        rec = _by_category(get_league_records(db), "Most Wins, All-Time")
        # All-Time records have no "most recent" — every tied owner is listed,
        # and Notes describes owner count rather than an "achieved N times" event.
        assert rec["Holder"] == "Alice, Bob, Carol"
        assert rec["Notes"] == "3 owners tied"
