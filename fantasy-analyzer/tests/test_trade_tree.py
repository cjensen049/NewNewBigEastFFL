"""Tests for analysis/transactions.py — build_deep_trade_tree pick resolution.

Regression coverage for a real bug: a traded pick's original_roster_id was being
used directly as the draft_slot, but draft_slot is a separate per-season column
position (from Sleeper's slot_to_roster_id lottery), not the roster_id itself.
"""

import json
import sqlite3

import pytest

from fantasy_analyzer.analysis.transactions import build_deep_trade_tree
from fantasy_analyzer.db.schema import DDL


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


def _league(con, league_id="L1", season=2024):
    con.execute(
        "INSERT INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start) "
        "VALUES (?,?,?,?,?,?)",
        (league_id, season, "Test League", "complete", 2, 15),
    )
    con.commit()


def _owners_and_rosters(con, league_id, *pairs):
    """_owners_and_rosters(db, 'L1', ('u1', 'RosterOne', 1), ('u2', 'RosterTwo', 2))"""
    con.executemany("INSERT INTO owners (user_id, canonical_name) VALUES (?,?)", [(u, n) for u, n, _ in pairs])
    con.executemany(
        "INSERT INTO league_owners (league_id, user_id, roster_id) VALUES (?,?,?)",
        [(league_id, u, r) for u, _, r in pairs],
    )
    con.commit()


def _player(con, player_id, full_name):
    con.execute("INSERT INTO players (player_id, full_name) VALUES (?,?)", (player_id, full_name))
    con.commit()


class TestPickToPlayerResolution:
    """The exact Trey McBride / Turo / Marvin Harrison Jr. scenario, genericized."""

    def test_traded_pick_resolves_via_slot_to_roster_id_not_roster_id(self, db):
        _league(db, "L1", 2024)
        _owners_and_rosters(db, "L1", ("u1", "RosterOne", 1), ("u2", "RosterTwo", 2))
        _player(db, "focal", "Focal Player")
        _player(db, "wrong", "Wrong Player")
        _player(db, "right", "Right Player")

        # Trade: RosterOne sends Focal Player + their own 2025 1st to RosterTwo.
        db.execute(
            "INSERT INTO transactions (transaction_id, league_id, season, week, type, adds_json, drops_json) "
            "VALUES (?,?,?,?,?,?,?)",
            ("t1", "L1", 2024, 1, "trade", json.dumps({"focal": 2}), json.dumps({"focal": 1})),
        )
        db.execute(
            "INSERT INTO transaction_draft_picks "
            "(transaction_id, season, round, original_roster_id, from_roster_id, to_roster_id) "
            "VALUES (?,?,?,?,?,?)",
            ("t1", 2025, 1, 1, 1, 2),
        )

        # 2025 draft: slot_to_roster_id deliberately does NOT match roster_id 1:1 —
        # roster 1's own pick (original_roster_id=1) actually sits in draft_slot=2.
        db.execute(
            "INSERT INTO drafts (draft_id, league_id, season, type, status, slot_to_roster_id_json) "
            "VALUES (?,?,?,?,?,?)",
            ("d1", "L1", 2025, "linear", "complete", json.dumps({"1": 2, "2": 1})),
        )
        db.execute(
            "INSERT INTO draft_picks (draft_id, league_id, season, round, pick_no, roster_id, player_id, player_name, draft_slot) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("d1", "L1", 2025, 1, 1, 2, "wrong", "Wrong Player", 1),
        )
        db.execute(
            "INSERT INTO draft_picks (draft_id, league_id, season, round, pick_no, roster_id, player_id, player_name, draft_slot) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("d1", "L1", 2025, 1, 2, 1, "right", "Right Player", 2),
        )
        db.commit()

        _, nodes = build_deep_trade_tree(db, "Focal Player")
        assert len(nodes) == 1
        pick_node = next(c for c in nodes[0].children if c.asset_type == "pick")
        assert len(pick_node.children) == 1
        draft_node = pick_node.children[0]
        assert draft_node.asset_type == "draft"
        assert draft_node.asset_name == "Right Player"


class TestVisitedTransactionsScoping:
    """visited must be scoped per-branch, not a single global mutation, so a legitimate
    sibling branch can't be silently dropped just because another branch reached the
    same transaction first."""

    def test_sibling_branches_do_not_suppress_each_other(self, db):
        _league(db, "L1", 2024)
        _owners_and_rosters(db, "L1", ("u1", "RosterOne", 1), ("u2", "RosterTwo", 2))
        _player(db, "focal", "Focal Player")
        _player(db, "sideA", "Side A")

        db.execute(
            "INSERT INTO transactions (transaction_id, league_id, season, week, type, adds_json, drops_json) "
            "VALUES (?,?,?,?,?,?,?)",
            ("t1", "L1", 2024, 1, "trade",
             json.dumps({"focal": 2, "sideA": 2}), json.dumps({"focal": 1, "sideA": 1})),
        )
        db.commit()

        _, nodes = build_deep_trade_tree(db, "Focal Player")
        assert len(nodes) == 1
        # sideA should appear as a counter-asset even though its own _follow() call
        # would re-hit the very same transaction t1 that produced it.
        names = {c.asset_name for c in nodes[0].children}
        assert "Side A" in names
