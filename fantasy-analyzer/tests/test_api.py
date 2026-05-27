"""Tests for Pydantic API models — validates parsing and coercion logic."""

import pytest
from fantasy_analyzer.api.models import (
    League,
    Matchup,
    Roster,
    Transaction,
    DraftPick,
)


# ---------------------------------------------------------------------------
# League model
# ---------------------------------------------------------------------------

class TestLeagueModel:
    def test_basic_fields(self):
        league = League(league_id="123", name="Test", season="2024", status="complete")
        assert league.league_id == "123"
        assert int(league.season) == 2024

    def test_previous_league_id_zero_string_normalizes_to_none(self):
        league = League(league_id="1", name="L", season="2024", status="complete", previous_league_id="0")
        assert league.previous_league_id is None

    def test_previous_league_id_empty_string_normalizes_to_none(self):
        league = League(league_id="1", name="L", season="2024", status="complete", previous_league_id="")
        assert league.previous_league_id is None

    def test_previous_league_id_real_value_preserved(self):
        league = League(league_id="1", name="L", season="2024", status="complete", previous_league_id="999")
        assert league.previous_league_id == "999"

    def test_default_playoff_week_start(self):
        league = League(league_id="1", name="L", season="2024", status="complete")
        assert league.settings.playoff_week_start == 15

    def test_default_total_rosters(self):
        league = League(league_id="1", name="L", season="2024", status="complete")
        assert league.total_rosters == 12


# ---------------------------------------------------------------------------
# Matchup model
# ---------------------------------------------------------------------------

class TestMatchupModel:
    def test_points_string_coerced(self):
        m = Matchup(roster_id=1, points="123.45")
        assert m.points == pytest.approx(123.45)

    def test_points_none(self):
        assert Matchup(roster_id=1, points=None).points is None

    def test_points_invalid_string_returns_none(self):
        assert Matchup(roster_id=1, points="n/a").points is None

    def test_players_points_populated(self):
        m = Matchup(roster_id=1, players_points={"1234": 22.5, "5678": 18.0})
        assert m.players_points["1234"] == pytest.approx(22.5)
        assert m.players_points["5678"] == pytest.approx(18.0)

    def test_players_points_defaults_empty(self):
        assert Matchup(roster_id=1).players_points == {}


# ---------------------------------------------------------------------------
# Roster model
# ---------------------------------------------------------------------------

class TestRosterModel:
    def test_fpts_combines_whole_and_decimal(self):
        r = Roster(roster_id=1, league_id="L1", settings={"fpts": 1423, "fpts_decimal": 56})
        assert r.fpts == pytest.approx(1423.56)

    def test_fpts_against_combines_decimal(self):
        r = Roster(roster_id=1, league_id="L1",
                   settings={"fpts_against": 1300, "fpts_against_decimal": 75})
        assert r.fpts_against == pytest.approx(1300.75)

    def test_ppts_combines_decimal(self):
        r = Roster(roster_id=1, league_id="L1", settings={"ppts": 1800, "ppts_decimal": 25})
        assert r.ppts == pytest.approx(1800.25)

    def test_defaults_all_zero(self):
        r = Roster(roster_id=1, league_id="L1")
        assert r.wins == 0
        assert r.losses == 0
        assert r.fpts == 0.0
        assert r.ppts == 0.0

    def test_none_values_treated_as_zero(self):
        r = Roster(roster_id=1, league_id="L1",
                   settings={"fpts": None, "fpts_decimal": None})
        assert r.fpts == 0.0


# ---------------------------------------------------------------------------
# Transaction model
# ---------------------------------------------------------------------------

class TestTransactionModel:
    def test_invalid_draft_picks_filtered(self):
        """Picks missing required keys are silently dropped."""
        t = Transaction(
            transaction_id="t1",
            type="trade",
            status="complete",
            draft_picks=[
                {"season": "2025", "round": 1, "roster_id": 3, "owner_id": 5},
                {"season": "2025", "round": 2},  # missing roster_id + owner_id
            ],
        )
        assert len(t.draft_picks) == 1
        assert t.draft_picks[0].round == 1

    def test_none_draft_picks_becomes_empty_list(self):
        t = Transaction(transaction_id="t1", type="free_agent", status="complete", draft_picks=None)
        assert t.draft_picks == []

    def test_season_coerced_to_int(self):
        t = Transaction(
            transaction_id="t1",
            type="trade",
            status="complete",
            draft_picks=[{"season": "2025", "round": 1, "roster_id": 3, "owner_id": 5}],
        )
        assert t.draft_picks[0].season == 2025

    def test_adds_drops_none(self):
        t = Transaction(transaction_id="t1", type="free_agent", status="complete")
        assert t.adds is None
        assert t.drops is None
