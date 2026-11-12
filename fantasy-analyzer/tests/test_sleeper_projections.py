"""Tests for scraping/sleeper_projections.py -- stored weekly projections are a permanent record."""

import sqlite3

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
