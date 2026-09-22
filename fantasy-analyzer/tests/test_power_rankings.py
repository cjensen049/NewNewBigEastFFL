"""Tests for analysis/power_rankings.py — the roster-quality prior blend and
the mathematical clinch/elimination bound check."""

import sqlite3

import pytest

from fantasy_analyzer.analysis.power_rankings import (
    _blended_mean,
    _MEAN_PRIOR_K,
    _playoff_positions,
    compute_playoff_certainty,
    compute_power_rankings,
)
from fantasy_analyzer.db.schema import DDL


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


class TestPlayoffPositions:
    def test_top4_by_wins_wildcard_by_points_among_rest(self):
        """The 2 wild-card spots go to whoever has the most points among the
        non-top-4 teams -- NOT whoever has the next-most wins. A lower-win
        team with more points must be able to leapfrog a higher-win team
        into a wild-card spot."""
        uids = ["u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8"]
        wins = {"u1": 10, "u2": 9, "u3": 8, "u4": 7, "u5": 6, "u6": 6, "u7": 5, "u8": 4}
        pts  = {"u1": 100, "u2": 100, "u3": 100, "u4": 100,
                "u5": 1000, "u6": 900, "u7": 1200, "u8": 800}

        top4, playoffs = _playoff_positions(uids, wins, pts)
        assert top4 == {"u1", "u2", "u3", "u4"}
        # u7 (5 wins, 1200 pts) and u5 (6 wins, 1000 pts) out-point u6 and u8
        # for the 2 wild-card spots, despite u7 having fewer wins than u6.
        assert playoffs == {"u1", "u2", "u3", "u4", "u5", "u7"}


class TestComputePlayoffCertainty:
    """8 synthetic teams -- _TOP_BY_RECORD/_PLAYOFF_SPOTS (4/6) don't depend
    on a real 12-team league, so a smaller set keeps these readable."""

    UIDS = ["u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8"]

    def test_season_over_matches_final_standing_exactly(self):
        """With 0 games left for everyone, nothing can change -- clinch and
        elimination must exactly match the actual final result."""
        wins = {"u1": 10, "u2": 9, "u3": 8, "u4": 7, "u5": 6, "u6": 6, "u7": 5, "u8": 4}
        pts  = {"u1": 100, "u2": 100, "u3": 100, "u4": 100,
                "u5": 1000, "u6": 900, "u7": 1200, "u8": 800}
        remaining = {u: 0 for u in self.UIDS}

        clinched_top4, clinched_playoffs, eliminated = compute_playoff_certainty(
            self.UIDS, wins, pts, remaining, ceiling=200.0,
        )
        assert clinched_top4 == {"u1", "u2", "u3", "u4"}
        assert clinched_playoffs == {"u1", "u2", "u3", "u4", "u5", "u7"}
        assert eliminated == {"u6", "u8"}

    def test_rival_can_mathematically_catch_up_blocks_clinch(self):
        """Regression: the whole point of this feature. A commanding lead
        with games still on the schedule must NOT show as clinched if a
        rival could theoretically still catch up given a maximal run."""
        uids = ["u1", "u2", "u3", "u4", "u5", "u6"]
        wins = {"u1": 5, "u2": 1, "u3": 1, "u4": 1, "u5": 1, "u6": 1}
        pts = {u: 500.0 for u in uids}
        remaining = {u: 5 for u in uids}  # u2 could reach 1+5=6 > u1's frozen 5

        clinched_top4, _, _ = compute_playoff_certainty(uids, wins, pts, remaining, ceiling=200.0)
        assert "u1" not in clinched_top4

    def test_unreachable_lead_is_clinched_even_with_games_left(self):
        uids = ["u1", "u2", "u3", "u4", "u5", "u6"]
        wins = {"u1": 20, "u2": 1, "u3": 1, "u4": 1, "u5": 1, "u6": 1}
        pts = {u: 500.0 for u in uids}
        remaining = {u: 2 for u in uids}  # best case for rivals is only 1+2=3, still << 20

        clinched_top4, clinched_playoffs, _ = compute_playoff_certainty(
            uids, wins, pts, remaining, ceiling=200.0,
        )
        assert "u1" in clinched_top4
        assert "u1" in clinched_playoffs

    def test_hopeless_record_with_one_game_left_is_eliminated(self):
        """Even winning out and scoring the ceiling every remaining week,
        this team can't reach a top-6 spot because too many rivals are
        already unreachable with zero games credited to them."""
        uids = self.UIDS
        wins = {"u1": 10, "u2": 9, "u3": 8, "u4": 7, "u5": 6, "u6": 6, "u7": 1, "u8": 0}
        pts  = {"u1": 2000, "u2": 2000, "u3": 2000, "u4": 2000,
                "u5": 1500, "u6": 1400, "u7": 500, "u8": 500}
        remaining = {u: 1 for u in uids}

        _, _, eliminated = compute_playoff_certainty(uids, wins, pts, remaining, ceiling=200.0)
        assert "u7" in eliminated
        assert "u8" in eliminated
        assert "u1" not in eliminated

    def test_still_alive_with_a_real_path_is_not_eliminated(self):
        uids = ["u1", "u2", "u3", "u4", "u5", "u6"]
        wins = {"u1": 5, "u2": 5, "u3": 5, "u4": 5, "u5": 5, "u6": 0}
        pts = {u: 500.0 for u in uids}
        remaining = {u: 10 for u in uids}  # u6 winning out reaches 10 wins, well clear

        _, _, eliminated = compute_playoff_certainty(uids, wins, pts, remaining, ceiling=200.0)
        assert "u6" not in eliminated


class TestRecordScoreIsTrueAllPlayPercentage:
    """Regression: the all-play win% is already a real 0-100% number, so the
    league's best team must show its true win%, never a min-max-stretched
    100 just for being relatively best among the other 11 teams."""

    @pytest.fixture
    def db(self):
        con = sqlite3.connect(":memory:")
        con.executescript(DDL)
        con.commit()
        return con

    def _setup(self, con):
        con.execute(
            "INSERT INTO leagues (league_id, season, name, status, total_rosters, playoff_week_start) "
            "VALUES ('L1', 2026, 'Test', 'in_season', 3, 15)"
        )
        for uid, name in [("u1", "Alice"), ("u2", "Bob"), ("u3", "Carl")]:
            con.execute("INSERT INTO owners (user_id, canonical_name) VALUES (?,?)", (uid, name))
            con.execute("INSERT INTO league_owners (league_id, user_id, roster_id) VALUES ('L1', ?, ?)",
                        (uid, int(uid[1])))

        # Week 1: Alice 100, Bob 90, Carl 80 -- Alice sweeps all-play (2-0), Bob 1-1, Carl 0-2
        # Week 2: Bob 90, Alice 85, Carl 70 -- Bob sweeps (2-0), Alice 1-1, Carl 0-2
        # Totals: Alice 3/4 = 75%, Bob 3/4 = 75% (tied best), Carl 0/4 = 0%
        weeks = {1: {"u1": 100.0, "u2": 90.0, "u3": 80.0}, 2: {"u1": 85.0, "u2": 90.0, "u3": 70.0}}
        rid = 1
        for week, scores in weeks.items():
            for uid, pts in scores.items():
                con.execute(
                    "INSERT INTO matchups (league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff) "
                    "VALUES ('L1', 2026, ?, ?, ?, ?, ?, 0)",
                    (week, rid, rid, uid, pts),
                )
                rid += 1
        con.commit()

    def test_tied_leaders_show_true_win_pct_not_100(self, db):
        self._setup(db)
        result = compute_power_rankings(db, "L1", 2026, pws=15)
        by_owner = {r["owner"]: r for r in result["rows"]}

        assert by_owner["Alice"]["record_score"] == pytest.approx(75.0)
        assert by_owner["Bob"]["record_score"] == pytest.approx(75.0)
        assert by_owner["Carl"]["record_score"] == pytest.approx(0.0)
