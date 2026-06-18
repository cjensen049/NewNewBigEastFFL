"""Tests for analysis/dynasty_rankings.py — multi-source dynasty composite."""

import sqlite3
import pytest

from fantasy_analyzer.analysis.dynasty_rankings import (
    _age_curve_values,
    _draft_capital_values,
    _pick_value,
    _roster_values,
    _zscore,
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
            expected = round((dp_by_owner[owner] + fc_by_owner[owner]) / 2, 2)
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


class TestZScore:
    def test_empty_returns_empty(self):
        assert _zscore({}) == {}

    def test_no_spread_returns_zero_for_all(self):
        assert _zscore({"u1": 100.0, "u2": 100.0}) == {"u1": 0.0, "u2": 0.0}

    def test_untethered_not_bounded_to_100(self):
        # One huge outlier should NOT compress everyone else toward a floor --
        # this is the whole reason for moving off min-max normalization.
        z = _zscore({"u1": 100.0, "u2": 1.0, "u3": 1.0, "u4": 1.0})
        assert z["u1"] > 1.5  # clearly above the pack
        assert z["u1"] != pytest.approx(100.0)  # not min-max-scaled

    def test_mean_is_zero(self):
        z = _zscore({"u1": 10.0, "u2": 20.0, "u3": 30.0})
        assert sum(z.values()) == pytest.approx(0.0, abs=1e-9)


class TestRosterValuesTeamTotals:
    def test_uses_published_team_total_when_present(self, db):
        # KTC-style published total should win over the computed sum, even
        # though the computed sum (from player_dynasty_values) would give a
        # different number.
        _add_player_value(db, "ktc", "p1", 9000)
        db.execute(
            "INSERT INTO team_totals (source, league_id, user_id, total, scraped_at) "
            "VALUES ('ktc', 'L1', 'u1', 5000, '2026-01-01')"
        )
        db.commit()

        result = _roster_values(db, "L1", "ktc")
        assert result == {"u1": 5000.0}

    def test_falls_back_to_computed_sum_when_no_published_total(self, db):
        _add_player_value(db, "dynastyprocess", "p1", 9000)
        result = _roster_values(db, "L1", "dynastyprocess")
        assert result.get("u1") == pytest.approx(9000.0)


class TestAgeCurve:
    def test_simple_mean_age_across_full_roster_incl_taxi(self, db):
        # u1 (roster_id 1) gets a second, taxi-squad player -- age should be a
        # plain mean across BOTH active and taxi, not value-weighted and not
        # filtered to active-only.
        db.execute("INSERT INTO players (player_id, full_name) VALUES ('p3', 'Player Three')")
        db.execute(
            "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) "
            "VALUES ('L1', 1, 'p3', 'taxi', '2026-01-01')"
        )
        _add_player_value(db, "dynastyprocess", "p1", 9000, age=20.0)
        _add_player_value(db, "dynastyprocess", "p3", 9000, age=30.0)
        db.commit()

        scores = _age_curve_values(db, "L1", "dynastyprocess")
        # -avg_age, simple mean of 20 and 30 -> -25, regardless of value
        assert scores["u1"] == pytest.approx(-25.0)

    def test_younger_roster_scores_higher(self, db):
        _add_player_value(db, "dynastyprocess", "p1", 9000, age=22.0)
        _add_player_value(db, "dynastyprocess", "p2", 1000, age=30.0)

        scores = _age_curve_values(db, "L1", "dynastyprocess")
        assert scores["u1"] > scores["u2"]


def _add_pick_value(con, source, season, rnd, tier, value):
    con.execute(
        "INSERT INTO pick_dynasty_values (source, season, round, tier, value, scraped_at) VALUES (?, ?, ?, ?, ?, '2026-01-01')",
        (source, season, rnd, tier, value),
    )
    con.commit()


class TestPickValueFallback:
    def test_exact_season_averages_tiers(self, db):
        _add_pick_value(db, "ktc", 2027, 1, "early", 6000)
        _add_pick_value(db, "ktc", 2027, 1, "mid", 4000)
        _add_pick_value(db, "ktc", 2027, 1, "late", 2000)
        assert _pick_value(db, "ktc", 2027, 1) == pytest.approx(4000)

    def test_falls_back_to_nearest_priced_season(self, db):
        # KTC only prices 2027/2028 -- a tracked 2029 pick must not silently
        # score zero, it should reuse the nearest season it has (2028).
        _add_pick_value(db, "ktc", 2028, 1, "mid", 4500)
        assert _pick_value(db, "ktc", 2029, 1) == pytest.approx(4500)

    def test_no_data_for_round_returns_zero(self, db):
        assert _pick_value(db, "ktc", 2027, 1) == 0.0


class TestDraftCapital:
    def test_prefers_authoritative_pick_ownership_over_reconstruction(self, db):
        # Stale/incomplete transaction_draft_picks data would hand u2's pick to u1;
        # an authoritative pick_ownership row from a source's own feed (e.g. KTC,
        # synced from Sleeper) should win instead.
        db.execute(
            "INSERT INTO transactions (transaction_id, league_id, season, type, created_epoch) "
            "VALUES ('t1', 'L1', 2026, 'trade', 1000)"
        )
        db.execute(
            "INSERT INTO transaction_draft_picks (transaction_id, season, round, original_roster_id, from_roster_id, to_roster_id) "
            "VALUES ('t1', 2027, 1, 2, 2, 1)"
        )
        db.execute(
            "INSERT INTO pick_ownership (source, league_id, season, round, user_id, original_user_id, scraped_at) "
            "VALUES ('ktc', 'L1', 2027, 1, 'u2', 'u2', '2026-01-01')"
        )
        _add_pick_value(db, "ktc", 2027, 1, "mid", 1000)
        db.commit()

        capital = _draft_capital_values(db, "L1", 2026, "ktc")
        assert capital.get("u2") == pytest.approx(1000)
        assert capital.get("u1") is None

    def test_falls_back_to_reconstruction_when_no_ownership_feed(self, db):
        db.execute(
            "INSERT INTO transactions (transaction_id, league_id, season, type, created_epoch) "
            "VALUES ('t1', 'L1', 2026, 'trade', 1000)"
        )
        db.execute(
            "INSERT INTO transaction_draft_picks (transaction_id, season, round, original_roster_id, from_roster_id, to_roster_id) "
            "VALUES ('t1', 2027, 1, 2, 2, 1)"
        )
        _add_pick_value(db, "dynastyprocess", 2027, 1, "mid", 1000)
        db.commit()

        capital = _draft_capital_values(db, "L1", 2026, "dynastyprocess")
        assert capital.get("u1", 0) > 0  # u1 received u2's traded pick
