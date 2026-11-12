"""Tests for scraping/sleeper_projections.py -- stored weekly projections are a permanent record."""

import sqlite3

import pytest

from fantasy_analyzer.db.schema import DDL
from fantasy_analyzer.scraping.sleeper_projections import store_week_projections


def _proj(pid, pts):
    return {"player_id": pid, "position": "QB", "projected_pts": pts}


class TestStoreWeekProjections:
    def test_refetch_never_removes_a_player_sleeper_no_longer_lists(self):
        """Regression: Sleeper's feed drops players who retire or get released (Tom Brady's 2021
        had no projections). A later re-fetch that no longer includes a player must leave his
        stored projection alone, or retirements would punch holes in saved weeks."""
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)

        store_week_projections(con, [_proj("brady", 18.0), _proj("mahomes", 22.0)], 2026, 5)
        store_week_projections(con, [_proj("mahomes", 23.5)], 2026, 5)   # Brady has since retired

        stored = dict(con.execute("SELECT player_id, projected_pts FROM player_projections WHERE season=2026 AND week=5"))
        assert stored == {"brady": 18.0, "mahomes": 23.5}   # Brady kept, still-listed player updated


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _record(pid, pos, stats):
    return {"player_id": pid, "player": {"position": pos}, "stats": stats}


class TestScoringProjectionsUnderOurRules:
    """Projected points are rebuilt from the projected stat line under NNBE's scoring,
    not taken from Sleeper's pts_ppr (which for older QB feeds includes first-down credit)."""

    # 250 pass yds, 2 TD, 1 INT, 20 rush yds = 10 + 8 - 1 + 2 = 19.0 under NNBE scoring
    QB_STATS = {"pass_yd": 250, "pass_td": 2, "pass_int": 1, "rush_yd": 20, "pass_fd": 22, "pts_ppr": 21.2}

    def test_score_stats_applies_the_league_rules_and_ignores_unscored_stats(self):
        from fantasy_analyzer.scraping.sleeper_projections import DEFAULT_SCORING, score_stats
        assert score_stats(self.QB_STATS, DEFAULT_SCORING) == pytest.approx(19.0)   # pass_fd earns nothing
        assert score_stats({"rec": 6, "rec_yd": 70, "rec_td": 1}, DEFAULT_SCORING) == pytest.approx(19.0)  # 6 + 7 + 6

    def test_weekly_projection_uses_rebuilt_points_not_pts_ppr(self, monkeypatch):
        """Regression: Sleeper's QB pts_ppr was ~2 points per game above what the stat line is worth,
        so every QB looked like he under-performed."""
        from fantasy_analyzer.scraping import sleeper_projections as sp
        payload = [
            _record("qb1", "QB", self.QB_STATS),
            _record("wr1", "WR", {"rec": 6, "rec_yd": 70, "rec_td": 1, "pts_ppr": 19.0}),
            _record("brady", "QB", {"adp_dd_ppr": 1000.0}),   # retired: a record, but no projected stats
        ]
        monkeypatch.setattr(sp.httpx, "get", lambda *a, **k: _FakeResponse(payload))
        by_id = {p["player_id"]: p for p in sp.fetch_week_projections(2021, 5, sp.DEFAULT_SCORING)}
        assert by_id["qb1"]["projected_pts"] == pytest.approx(19.0)    # not 21.2
        assert by_id["wr1"]["projected_pts"] == pytest.approx(19.0)
        assert "brady" not in by_id

    def test_season_projection_is_rebuilt_points_per_game(self, monkeypatch):
        from fantasy_analyzer.scraping import sleeper_projections as sp
        stats = {**self.QB_STATS, "pass_yd": 250 * 17, "pass_td": 2 * 17, "pass_int": 17, "rush_yd": 20 * 17, "pts_ppr": 999, "gp": 17}
        monkeypatch.setattr(sp.httpx, "get", lambda *a, **k: _FakeResponse([_record("qb1", "QB", stats)]))
        [row] = sp.fetch_season_projections(2026, sp.DEFAULT_SCORING)
        assert row["projected_pts"] == pytest.approx(19.0)

    def test_scoring_settings_come_from_the_league_and_drop_zero_rules(self, monkeypatch):
        from fantasy_analyzer.scraping import sleeper_projections as sp
        settings = {"scoring_settings": {"pass_yd": 0.03999999910593033, "pass_td": 6.0, "rec": 0.0, "note": "x"}}
        monkeypatch.setattr(sp.httpx, "get", lambda *a, **k: _FakeResponse(settings))
        assert sp.fetch_scoring_settings("L1") == {"pass_yd": 0.04, "pass_td": 6.0}

    def test_scoring_settings_fall_back_to_nnbe_defaults_if_sleeper_is_down(self, monkeypatch):
        from fantasy_analyzer.scraping import sleeper_projections as sp

        def boom(*a, **k):
            raise sp.httpx.ConnectError("down")

        monkeypatch.setattr(sp.httpx, "get", boom)
        assert sp.fetch_scoring_settings("L1") == sp.DEFAULT_SCORING
