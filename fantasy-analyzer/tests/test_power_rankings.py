"""Tests for analysis/power_rankings.py — the roster-quality prior blend."""

import pytest

from fantasy_analyzer.analysis.power_rankings import _blended_mean, _MEAN_PRIOR_K


class TestBlendedMean:
    def test_no_prior_returns_empirical_unchanged(self):
        assert _blended_mean(110.0, games_played=1, prior=None) == 110.0

    def test_zero_games_is_pure_prior(self):
        """n=0 -> empirical_weight = 0/(0+k) = 0, so the prior fully applies
        (a team on a bye or with no games yet has no empirical signal)."""
        assert _blended_mean(0.0, games_played=0, prior=140.0) == pytest.approx(140.0)

    def test_weight_at_k_games_is_even(self):
        """At n == k, empirical and prior are weighted equally (the defining
        property of credibility weighting -- this is what k means)."""
        empirical, prior = 100.0, 140.0
        blended = _blended_mean(empirical, games_played=int(_MEAN_PRIOR_K), prior=prior)
        assert blended == pytest.approx((empirical + prior) / 2)

    def test_weight_shifts_toward_empirical_as_games_accumulate(self):
        """More games played -> the blend should move closer to the empirical
        mean and further from the prior (regression: a real bad week must
        matter less than a bad roster projection, but matter MORE over time,
        not stay pinned to the prior all season)."""
        empirical, prior = 90.0, 150.0
        early = _blended_mean(empirical, games_played=1, prior=prior)
        late = _blended_mean(empirical, games_played=12, prior=prior)
        assert prior > early > late > empirical

    def test_bad_week_does_not_zero_out_a_strong_roster(self):
        """The scenario this whole fix exists for: one bad week against a
        strong roster projection should land well above the raw empirical
        score, not get overridden entirely by it."""
        bad_week_score, strong_roster = 90.0, 150.0
        blended = _blended_mean(bad_week_score, games_played=1, prior=strong_roster)
        assert blended > 130.0  # much closer to the roster prior than to the raw score
