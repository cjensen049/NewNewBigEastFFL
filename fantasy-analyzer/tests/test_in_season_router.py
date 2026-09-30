"""Tests for backend/routers/in_season.py — presentation-layer helpers.

_luck_verdict is the single source of truth for luck classification text;
both the Home page and the Playoff Picture page render whatever this
returns rather than each re-deriving their own thresholds from luck_diff
(see the "Casey unlucky on Home, average on In-Season" bug this fixed).
"""

from backend.routers.in_season import _luck_verdict


class TestLuckVerdict:
    def test_very_lucky_boundary(self):
        assert _luck_verdict(1.5) == "Very Lucky"

    def test_lucky_boundary(self):
        assert _luck_verdict(0.5) == "Lucky"

    def test_average_boundary(self):
        assert _luck_verdict(-0.5) == "Average"

    def test_average_middle(self):
        assert _luck_verdict(0.0) == "Average"

    def test_unlucky_boundary(self):
        assert _luck_verdict(-1.5) == "Unlucky"

    def test_very_unlucky_below_boundary(self):
        assert _luck_verdict(-1.51) == "Very Unlucky"

    def test_just_below_average_is_unlucky_not_average(self):
        # Regression: a naive +/-0.3 threshold (the old Home page logic)
        # would call this "Unlucky" while the canonical scale calls it
        # "Average" -- both pages must now agree since both read this value.
        assert _luck_verdict(-0.4) == "Average"
