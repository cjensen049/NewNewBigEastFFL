"""Tests for scraping/narratives.py -- AI-generated weekly recap/preview text.

No test calls the real Claude API. _call_claude's own network path is
mocked; everything else (facts building, storage/upsert) is tested directly
against real data shapes.
"""

import json
import sqlite3

import pytest

from fantasy_analyzer.scraping.narratives import (
    _build_preview_facts,
    _build_recap_facts,
    _call_claude,
    _store_narratives,
    _strip_code_fence,
    run_preview_narratives,
    run_recap_narratives,
)
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
        (league_id, season, "Test League", "in_season", 2, pws),
    )
    con.commit()


def _owner(con, league_id, user_id, roster_id, name):
    con.execute("INSERT OR IGNORE INTO owners (user_id, canonical_name) VALUES (?,?)", (user_id, name))
    con.execute("INSERT INTO league_owners (league_id, user_id, roster_id) VALUES (?,?,?)",
                (league_id, user_id, roster_id))
    con.commit()


_rid = 200


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


def _season_proj(con, season, projections):
    con.executemany(
        "INSERT INTO player_season_projections (season, player_id, position, projected_pts, scraped_at) "
        "VALUES (?,?,?,?,?)",
        [(season, pid, pos, pts, "2026-01-01") for pid, (pos, pts) in projections.items()],
    )
    con.commit()


def _slot(con, season, week, team, slot):
    con.execute("INSERT INTO game_slots (season, week, team, slot) VALUES (?,?,?,?)", (season, week, team, slot))
    con.commit()


class TestBuildRecapFacts:
    def test_standout_and_bust_selected_by_diff_from_projection(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _player(db, "hot", "Hot Guy", "WR", team="BUF")
        _player(db, "cold", "Cold Guy", "RB", team="MIA")
        _season_proj(db, 2026, {"hot": ("WR", 10.0), "cold": ("RB", 15.0)})
        _slot(db, 2026, 1, "BUF", "Monday Night")

        _matchup(
            db, "L1", 1, 1, "u1", 100.0,
            starters=["hot", "cold"],
            players_points={"hot": 35.0, "cold": 2.0},
        )
        _matchup(db, "L1", 1, 1, "u2", 90.0, starters=[], players_points={})

        week, facts = _build_recap_facts(db, "L1", 2026)
        assert week == 1
        alice = facts[0]["a"] if facts[0]["a"]["owner"] == "Alice" else facts[0]["b"]
        assert alice["standout"]["name"] == "Hot Guy"
        assert alice["standout"]["diff"] == pytest.approx(25.0)
        assert alice["standout"]["slot"] == "Monday Night"
        assert alice["bust"]["name"] == "Cold Guy"
        assert alice["bust"]["diff"] == pytest.approx(-13.0)

    def test_no_completed_week_returns_none(self, db):
        _league(db)
        assert _build_recap_facts(db, "L1", 2026) is None


class TestBuildPreviewFacts:
    def test_key_players_and_bye_players_populated(self, db):
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        _matchup(db, "L1", 2, 1, "u1", 0.0)
        _matchup(db, "L1", 2, 1, "u2", 0.0)

        _player(db, "star", "Star Guy", "QB", team="KC")
        _player(db, "byeguy", "Bye Guy", "WR", team="DAL")
        db.execute(
            "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) "
            "VALUES ('L1', 1, 'star', 'active', '2026-01-01')"
        )
        db.execute(
            "INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at) "
            "VALUES ('L1', 1, 'byeguy', 'active', '2026-01-01')"
        )
        db.commit()
        _season_proj(db, 2026, {"star": ("QB", 22.0)})
        _slot(db, 2026, 2, "KC", "Sunday Night")
        db.execute("INSERT INTO nfl_byes (season, week, team) VALUES (2026, 2, 'DAL')")
        db.commit()

        week, facts = _build_preview_facts(db, "L1", 2026, 15)
        assert week == 2
        alice = facts[0]["a"] if facts[0]["a"]["owner"] == "Alice" else facts[0]["b"]
        assert alice["key_players"][0]["name"] == "Star Guy"
        assert alice["key_players"][0]["slot"] == "Sunday Night"
        assert alice["bye_players"] == [{"name": "Bye Guy", "position": "WR"}]

    def test_no_upcoming_week_returns_none(self, db):
        _league(db)
        assert _build_preview_facts(db, "L1", 2026, 15) is None


class TestStoreNarratives:
    def test_upsert_overwrites_on_regenerate(self, db):
        _league(db)
        n = _store_narratives(db, "L1", 2026, 1, "recap", {1: "First version"})
        assert n == 1
        _store_narratives(db, "L1", 2026, 1, "recap", {1: "Updated version"})
        row = db.execute(
            "SELECT text FROM weekly_narratives WHERE league_id='L1' AND season=2026 AND week=1 AND kind='recap' AND matchup_id=1"
        ).fetchone()
        assert row[0] == "Updated version"


class TestGracefulDegradation:
    def test_missing_api_key_skips_generation(self, db, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert _call_claude("system prompt", [{"matchup_id": 1}]) == {}

    def test_run_recap_narratives_returns_zero_without_key(self, db, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        assert run_recap_narratives(db, "L1", 2026) == 0

    def test_run_preview_narratives_returns_zero_without_key(self, db, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        _league(db)
        _owner(db, "L1", "u1", 1, "Alice")
        _owner(db, "L1", "u2", 2, "Bob")
        _matchup(db, "L1", 1, 1, "u1", 100.0)
        _matchup(db, "L1", 1, 1, "u2", 90.0)
        _matchup(db, "L1", 2, 1, "u1", 0.0)
        _matchup(db, "L1", 2, 1, "u2", 0.0)
        assert run_preview_narratives(db, "L1", 2026, 15) == 0


class TestCallClaudeParsing:
    def test_parses_json_array_response_into_dict(self, db, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

        class FakeContent:
            # _call_claude prefills the assistant turn with "[", so a real completion
            # continues from there rather than repeating the opening bracket.
            full_array = json.dumps([{"matchup_id": 5, "text": "Great game."}, {"matchup_id": 7, "text": "Blowout."}])
            text = full_array[1:]

        class FakeResponse:
            content = [FakeContent()]

        class FakeMessages:
            def create(self, **kwargs):
                return FakeResponse()

        class FakeClient:
            def __init__(self, api_key):
                self.messages = FakeMessages()

        # _call_claude does `import anthropic` locally, so patch the real module's class
        import anthropic
        monkeypatch.setattr(anthropic, "Anthropic", FakeClient)

        result = _call_claude("system", [{"matchup_id": 5}, {"matchup_id": 7}])
        assert result == {5: "Great game.", 7: "Blowout."}

    def test_recovers_from_trailing_code_fence(self, db, monkeypatch):
        """Regression: Claude sometimes appends a closing ``` even when the
        assistant turn is prefilled with '[', which used to break json.loads
        outright and silently drop every narrative for the week."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-for-test")

        class FakeContent:
            full_array = json.dumps([{"matchup_id": 1, "text": "Close one."}])
            text = full_array[1:] + "\n```"

        class FakeResponse:
            content = [FakeContent()]

        class FakeMessages:
            def create(self, **kwargs):
                return FakeResponse()

        class FakeClient:
            def __init__(self, api_key):
                self.messages = FakeMessages()

        import anthropic
        monkeypatch.setattr(anthropic, "Anthropic", FakeClient)

        result = _call_claude("system", [{"matchup_id": 1}])
        assert result == {1: "Close one."}


class TestStripCodeFence:
    def test_strips_trailing_fence(self):
        assert _strip_code_fence('[{"a": 1}]\n```') == '[{"a": 1}]'

    def test_leaves_unfenced_text_unchanged(self):
        assert _strip_code_fence('[{"a": 1}]') == '[{"a": 1}]'
