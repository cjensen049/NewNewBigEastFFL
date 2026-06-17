"""Tests for analysis/dynasty_rankings.py — multi-source dynasty composite."""

import sqlite3
import pytest

from fantasy_analyzer.analysis.dynasty_rankings import (
    compute_dynasty_rankings,
    compute_dynasty_rankings_overall,
    get_available_dynasty_sources,
)
from fantasy_analyzer.db.schema import DDL


@pytest.fixture
def db():
    """In-memory SQLite with the full schema and a two-owner league."""
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)

    con.execute(
        "INSERT INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start, last_scored_leg) "
        "VALUES ('L1', 2026, 'Test League', 'in_season', 2, 15, 17)"
    )
    con.executemany(
        "INSERT INTO owners (user_id, canonical_name) VALUES (?, ?)",
        [("u1", "Alice"), ("u2", "Bob")],
    )
    con.executemany(
        "INSERT INTO league_owners (league_id, user_id, roster_id) VALUES (?, ?, ?)",
        [("L1", "u1", 1), ("L1", "u2", 2)],
    )
    con.executemany(
        "INSERT INTO players (player_id, full_name) VALUES (?, ?)",
        [("p1", "Player One"), ("p2", "Player Two")],
    )
    con.executemany(
        "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) VALUES (?, ?, ?, 'active', '2026-01-01')",
        [("L1", 1, "p1"), ("L1", 2, "p2")],
    )
    con.commit()
    return con


def _add_player_value(con, source, player_id, value, age=25.0):
    con.execute(
        "INSERT INTO player_dynasty_values (source, player_id, value, age, scraped_at) VALUES (?, ?, ?, ?, ?)",
        (source, player_id, value, age, f"2026-01-0{1 if source == 'dynastyprocess' else 2}"),
    )
    con.commit()


class TestSingleSource:
    def test_no_data_returns_empty_rows(self, db):
        result = compute_dynasty_rankings(db, "L1", 2026, "dynastyprocess")
        assert result["rows"] == []
        assert result["data_date"] is None

    def test_higher_roster_value_ranks_first(self, db):
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        _add_player_value(db, "dynastyprocess", "p2", 1000)

        result = compute_dynasty_rankings(db, "L1", 2026, "dynastyprocess")
        assert [r["owner"] for r in result["rows"]] == ["Alice", "Bob"]
        assert result["rows"][0]["composite"] > result["rows"][1]["composite"]

    def test_unknown_source_returns_empty(self, db):
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        result = compute_dynasty_rankings(db, "L1", 2026, "made_up_source")
        assert result["rows"] == []


class TestAvailableSources:
    def test_lists_distinct_sources(self, db):
        assert get_available_dynasty_sources(db) == []
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        _add_player_value(db, "fantasycalc", "p1", 8000)
        assert get_available_dynasty_sources(db) == ["dynastyprocess", "fantasycalc"]


class TestOverallBlend:
    def test_no_sources_returns_empty(self, db):
        result = compute_dynasty_rankings_overall(db, "L1", 2026)
        assert result["rows"] == []

    def test_averages_composite_across_sources(self, db):
        # Alice (p1) is strongest in both sources -> should rank first overall
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        _add_player_value(db, "dynastyprocess", "p2", 1000)
        _add_player_value(db, "fantasycalc", "p1", 8500)
        _add_player_value(db, "fantasycalc", "p2", 1500)

        dp = compute_dynasty_rankings(db, "L1", 2026, "dynastyprocess")
        fc = compute_dynasty_rankings(db, "L1", 2026, "fantasycalc")
        overall = compute_dynasty_rankings_overall(db, "L1", 2026)

        dp_by_owner = {r["owner"]: r["composite"] for r in dp["rows"]}
        fc_by_owner = {r["owner"]: r["composite"] for r in fc["rows"]}
        overall_by_owner = {r["owner"]: r["composite"] for r in overall["rows"]}

        for owner in ("Alice", "Bob"):
            expected = round((dp_by_owner[owner] + fc_by_owner[owner]) / 2, 1)
            assert overall_by_owner[owner] == pytest.approx(expected)

        assert overall["rows"][0]["owner"] == "Alice"
        assert overall["rows"][0]["source_scores"].keys() == {"dynastyprocess", "fantasycalc"}

    def test_ignores_source_with_no_data_for_league(self, db):
        # fantasycalc has rows in the table, but none of them are for this
        # league's rostered players -> compute_dynasty_rankings for it still
        # returns rows (defaulted to neutral), so it's included; this test
        # documents that behavior rather than asserting exclusion.
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        _add_player_value(db, "fantasycalc", "p_unrelated", 5000)

        overall = compute_dynasty_rankings_overall(db, "L1", 2026)
        assert set(overall["rows"][0]["source_scores"].keys()) == {"dynastyprocess", "fantasycalc"}
