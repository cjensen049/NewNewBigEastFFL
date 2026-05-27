"""Tests for analysis/history.py — core analytical functions."""

import sqlite3
import pytest

from fantasy_analyzer.analysis.history import (
    RegularSeasonRecord,
    AllTimeRecord,
    compute_regular_season_records,
    compute_playoff_results,
    compute_luck_scores,
    get_race_to_bottom,
    get_standings_history,
)
from fantasy_analyzer.db.schema import DDL


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """In-memory SQLite with the full schema."""
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


def _league(con, league_id="L1", season=2024, pws=15, last_week=17):
    con.execute(
        "INSERT INTO leagues "
        "(league_id, season, name, status, total_rosters, playoff_week_start, last_scored_leg) "
        "VALUES (?,?,?,?,?,?,?)",
        (league_id, season, "Test League", "complete", 12, pws, last_week),
    )
    con.commit()


def _owners(con, *pairs):
    """_owners(db, ('u1', 'Alice'), ('u2', 'Bob'))"""
    con.executemany("INSERT INTO owners (user_id, canonical_name) VALUES (?,?)", pairs)
    con.commit()


_rid = 0  # global roster_id counter avoids UNIQUE(league_id, week, roster_id) collisions


def _matchup(con, league_id, season, week, matchup_id, user_id, points, is_playoff=0):
    global _rid
    _rid += 1
    con.execute(
        "INSERT INTO matchups "
        "(league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (league_id, season, week, matchup_id, _rid, user_id, points, is_playoff),
    )
    con.commit()


def _season_record(con, league_id, user_id, season, wins, losses, fpts=0.0, ppts=0.0):
    con.execute(
        "INSERT INTO season_records "
        "(league_id, user_id, season, wins, losses, ties, fpts, fpts_against, ppts) "
        "VALUES (?,?,?,?,?,0,?,0,?)",
        (league_id, user_id, season, wins, losses, fpts, ppts),
    )
    con.commit()


# ---------------------------------------------------------------------------
# RegularSeasonRecord unit tests
# ---------------------------------------------------------------------------

class TestRegularSeasonRecord:
    def test_win_pct_normal(self):
        r = RegularSeasonRecord("u1", "Alice", 2024, wins=8, losses=5, ties=1)
        assert r.win_pct == pytest.approx(8.5 / 14)

    def test_win_pct_no_games(self):
        assert RegularSeasonRecord("u1", "Alice", 2024).win_pct == 0.0

    def test_ppg(self):
        r = RegularSeasonRecord("u1", "Alice", 2024, wins=5, losses=5, points_for=1400.0)
        assert r.ppg == pytest.approx(140.0)

    def test_ppg_no_games(self):
        assert RegularSeasonRecord("u1", "Alice", 2024).ppg == 0.0


# ---------------------------------------------------------------------------
# compute_regular_season_records
# ---------------------------------------------------------------------------

class TestComputeRegularSeasonRecords:
    def test_basic_win_loss(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 120.0)
        _matchup(db, "L1", 2024, 1, 1, "u2", 100.0)

        records = compute_regular_season_records(db, "L1", 2024, 15)
        by_name = {r.canonical_name: r for r in records}

        assert by_name["Alice"].wins == 1 and by_name["Alice"].losses == 0
        assert by_name["Bob"].wins == 0 and by_name["Bob"].losses == 1

    def test_tie(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 100.0)
        _matchup(db, "L1", 2024, 1, 1, "u2", 100.0)

        records = compute_regular_season_records(db, "L1", 2024, 15)
        by_name = {r.canonical_name: r for r in records}
        assert by_name["Alice"].ties == 1 and by_name["Alice"].wins == 0
        assert by_name["Bob"].ties == 1

    def test_points_accumulation(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _matchup(db, "L1", 2024, 1, 1, "u1", 120.0)
        _matchup(db, "L1", 2024, 1, 1, "u2", 100.0)
        _matchup(db, "L1", 2024, 2, 1, "u1", 80.0)
        _matchup(db, "L1", 2024, 2, 1, "u2", 90.0)

        by_name = {r.canonical_name: r for r in compute_regular_season_records(db, "L1", 2024, 15)}
        assert by_name["Alice"].points_for == pytest.approx(200.0)
        assert by_name["Alice"].points_against == pytest.approx(190.0)

    def test_playoff_weeks_excluded(self, db):
        """Weeks >= playoff_week_start must not be counted."""
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"))
        _matchup(db, "L1", 2024, 14, 1, "u1", 120.0)
        _matchup(db, "L1", 2024, 14, 1, "u2", 100.0)
        # Playoff week — should be ignored by compute_regular_season_records
        _matchup(db, "L1", 2024, 15, 1, "u1", 200.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 1, "u2", 50.0, is_playoff=1)

        by_name = {r.canonical_name: r for r in compute_regular_season_records(db, "L1", 2024, 15)}
        assert by_name["Alice"].games == 1

    def test_sorted_by_win_pct_then_points(self, db):
        _league(db)
        _owners(db, ("u1", "Alice"), ("u2", "Bob"), ("u3", "Carol"))
        # Alice beats Bob
        _matchup(db, "L1", 2024, 1, 1, "u1", 120.0)
        _matchup(db, "L1", 2024, 1, 1, "u2", 100.0)
        # Carol beats Bob (Bob gets second loss)
        _matchup(db, "L1", 2024, 2, 2, "u3", 110.0)
        _matchup(db, "L1", 2024, 2, 2, "u2", 90.0)

        records = compute_regular_season_records(db, "L1", 2024, 15)
        assert records[-1].canonical_name == "Bob"

    def test_empty_returns_empty(self, db):
        _league(db)
        assert compute_regular_season_records(db, "L1", 2024, 15) == []


# ---------------------------------------------------------------------------
# compute_playoff_results
# ---------------------------------------------------------------------------

class TestComputePlayoffResults:
    @pytest.fixture(autouse=True)
    def _seed(self, db):
        """4-team championship bracket: Champ/RU/Third/Fourth + last-place game."""
        _league(db, pws=15, last_week=17)
        _owners(db,
                ("c1", "Champ"), ("ru1", "RunnerUp"),
                ("t3", "Third"), ("t4", "Fourth"),
                ("lp1", "LastPlus"), ("lp2", "LastPlace"))

        # Week 15: matchup 1 (Champ vs RunnerUp), matchup 2 (Third vs Fourth)
        _matchup(db, "L1", 2024, 15, 1, "c1", 130.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 1, "ru1", 120.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 2, "t3", 110.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 2, "t4", 90.0, is_playoff=1)

        # Week 16 (middle): matchup 3 decides 5th/6th — not used in this 4-team test

        # Week 17 (last): championship + consolation + last-place
        _matchup(db, "L1", 2024, 17, 1, "c1", 140.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 1, "ru1", 125.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 2, "t3", 115.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 2, "t4", 95.0, is_playoff=1)
        # Toilet bowl last-place game (matchup_id=5)
        _matchup(db, "L1", 2024, 17, 5, "lp1", 80.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 5, "lp2", 70.0, is_playoff=1)

        self.db = db

    def test_champion(self):
        results = compute_playoff_results(self.db, "L1", 2024, 15, 17)
        champ = next(r for r in results if r.canonical_name == "Champ")
        assert champ.finish == 1
        assert champ.champion is True

    def test_runner_up(self):
        results = compute_playoff_results(self.db, "L1", 2024, 15, 17)
        ru = next(r for r in results if r.canonical_name == "RunnerUp")
        assert ru.finish == 2
        assert ru.champion is False

    def test_third_and_fourth(self):
        results = compute_playoff_results(self.db, "L1", 2024, 15, 17)
        by_name = {r.canonical_name: r for r in results}
        assert by_name["Third"].finish == 3
        assert by_name["Fourth"].finish == 4

    def test_made_playoffs_flag(self):
        results = compute_playoff_results(self.db, "L1", 2024, 15, 17)
        by_name = {r.canonical_name: r for r in results}
        assert by_name["Champ"].made_playoffs is True
        assert by_name["RunnerUp"].made_playoffs is True
        # Toilet bowl participants had min matchup_id >= 4 so made_playoffs=False
        assert by_name["LastPlace"].made_playoffs is False

    def test_last_place(self):
        results = compute_playoff_results(self.db, "L1", 2024, 15, 17)
        lp = next(r for r in results if r.canonical_name == "LastPlace")
        assert lp.finish == 12
        assert lp.last_place is True

    def test_no_data_returns_empty(self, db):
        _league(db, league_id="L99", season=2023)
        results = compute_playoff_results(db, "L99", 2023, 15, 17)
        assert results == []


# ---------------------------------------------------------------------------
# compute_luck_scores
# ---------------------------------------------------------------------------

class TestComputeLuckScores:
    @pytest.fixture(autouse=True)
    def _seed(self, db):
        """4 teams, 1 week. Scores: Alpha=120, Beta=100, Gamma=80, Delta=90.
        Matchups: Alpha vs Beta (Alpha wins), Gamma vs Delta (Delta wins).
        """
        _league(db)
        _owners(db, ("ua", "Alpha"), ("ub", "Beta"), ("uc", "Gamma"), ("ud", "Delta"))
        _matchup(db, "L1", 2024, 1, 1, "ua", 120.0)
        _matchup(db, "L1", 2024, 1, 1, "ub", 100.0)
        _matchup(db, "L1", 2024, 1, 2, "uc", 80.0)
        _matchup(db, "L1", 2024, 1, 2, "ud", 90.0)
        self.db = db

    def _by_name(self):
        return {r["owner"]: r for r in compute_luck_scores(self.db, "L1", 2024, 15)}

    def test_actual_wins_correct(self):
        bn = self._by_name()
        assert bn["Alpha"]["actual_wins"] == 1
        assert bn["Beta"]["actual_wins"] == 0
        assert bn["Delta"]["actual_wins"] == 1
        assert bn["Gamma"]["actual_wins"] == 0

    def test_sim_wins_correct(self):
        # Alpha(120) beats everyone: 3 sim wins
        # Beta(100) beats Gamma(80) and Delta(90): 2 sim wins
        # Delta(90) beats Gamma(80): 1 sim win
        # Gamma(80) beats nobody: 0 sim wins
        bn = self._by_name()
        assert bn["Alpha"]["sim_wins"] == 3
        assert bn["Beta"]["sim_wins"] == 2
        assert bn["Delta"]["sim_wins"] == 1
        assert bn["Gamma"]["sim_wins"] == 0

    def test_delta_is_lucky(self):
        """Delta wins actual (beat Gamma) but sim win% is only 1/3 — lucky schedule."""
        bn = self._by_name()
        assert bn["Delta"]["luck_diff"] > 0

    def test_beta_is_unlucky(self):
        """Beta loses actual (to Alpha) but sim win% is 2/3 — unlucky schedule."""
        bn = self._by_name()
        assert bn["Beta"]["luck_diff"] < 0

    def test_sorted_desc_by_luck(self):
        results = compute_luck_scores(self.db, "L1", 2024, 15)
        lucks = [r["luck_diff"] for r in results]
        assert lucks == sorted(lucks, reverse=True)

    def test_empty_season_returns_empty(self, db):
        _league(db, league_id="L2", season=2023)
        assert compute_luck_scores(db, "L2", 2023, 15) == []


# ---------------------------------------------------------------------------
# get_race_to_bottom
# ---------------------------------------------------------------------------

class TestGetRaceToBottom:
    @pytest.fixture(autouse=True)
    def _seed(self, db):
        _league(db, pws=15, last_week=17)
        _owners(db,
                ("p1", "Playoff1"), ("p2", "Playoff2"),
                ("np1", "Bottom1"), ("np2", "Bottom2"),
                ("np3", "Bottom3"), ("np4", "Bottom4"))

        # Playoff bracket game (marks p1 and p2 as playoff teams)
        _matchup(db, "L1", 2024, 15, 1, "p1", 120.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 1, "p2", 100.0, is_playoff=1)

        # Season records — non-playoff teams have different ppts
        _season_record(db, "L1", "p1",  2024, 9, 5, fpts=1500.0, ppts=1800.0)
        _season_record(db, "L1", "p2",  2024, 8, 6, fpts=1400.0, ppts=1700.0)
        _season_record(db, "L1", "np1", 2024, 5, 9, fpts=1200.0, ppts=1600.0)
        _season_record(db, "L1", "np2", 2024, 4, 10, fpts=1100.0, ppts=1500.0)
        _season_record(db, "L1", "np3", 2024, 3, 11, fpts=1000.0, ppts=1300.0)
        _season_record(db, "L1", "np4", 2024, 2, 12, fpts=900.0,  ppts=1100.0)
        self.db = db

    def test_playoff_teams_excluded(self):
        names = [r["owner"] for r in get_race_to_bottom(self.db, 2024)]
        assert "Playoff1" not in names
        assert "Playoff2" not in names

    def test_ranked_ascending_by_ppts(self):
        results = get_race_to_bottom(self.db, 2024)
        ppts = [r["optimal_pts"] for r in results]
        assert ppts == sorted(ppts)

    def test_lowest_ppts_gets_pick_1(self):
        results = get_race_to_bottom(self.db, 2024)
        assert results[0]["owner"] == "Bottom4"  # ppts=1100 is lowest
        assert results[0]["draft_pick"] == 1

    def test_draft_picks_sequential(self):
        results = get_race_to_bottom(self.db, 2024)
        picks = [r["draft_pick"] for r in results]
        assert picks == list(range(1, len(picks) + 1))

    def test_lineup_pct_calculated(self):
        results = get_race_to_bottom(self.db, 2024)
        for r in results:
            expected = round(r["actual_pts"] / r["optimal_pts"] * 100, 1)
            assert r["lineup_pct"] == pytest.approx(expected)

    def test_unknown_season_returns_empty(self, db):
        assert get_race_to_bottom(db, 9999) == []


# ---------------------------------------------------------------------------
# get_standings_history (hybrid ranking)
# ---------------------------------------------------------------------------

class TestGetStandingsHistory:
    def test_champion_is_rank_1(self, db):
        _league(db, pws=15, last_week=17)
        _owners(db, ("c1", "Champ"), ("ru1", "RunnerUp"))

        # Championship matchup
        _matchup(db, "L1", 2024, 15, 1, "c1", 130.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 1, "ru1", 120.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 1, "c1", 140.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 1, "ru1", 125.0, is_playoff=1)

        history = get_standings_history(db)
        assert history[2024][1] == "Champ"
        assert history[2024][2] == "RunnerUp"

    def test_non_playoff_team_not_in_top_6(self, db):
        _league(db, pws=15, last_week=17)
        # Four owners: two in championship bracket, two non-playoff
        _owners(db, ("c1", "Champ"), ("ru1", "RunnerUp"),
                ("np1", "Nonplayoff1"), ("np2", "Nonplayoff2"))

        # Championship bracket games
        _matchup(db, "L1", 2024, 15, 1, "c1", 130.0, is_playoff=1)
        _matchup(db, "L1", 2024, 15, 1, "ru1", 120.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 1, "c1", 140.0, is_playoff=1)
        _matchup(db, "L1", 2024, 17, 1, "ru1", 125.0, is_playoff=1)

        # Regular season game between the two non-playoff teams (need a pair to register)
        _matchup(db, "L1", 2024, 1, 2, "np1", 100.0)
        _matchup(db, "L1", 2024, 1, 2, "np2", 90.0)

        history = get_standings_history(db)
        top_6 = [history[2024].get(i) for i in range(1, 7)]
        assert "Nonplayoff1" not in top_6
        assert "Nonplayoff2" not in top_6
        # Both should appear at rank 7+
        assert "Nonplayoff1" in history[2024].values()
        assert "Nonplayoff2" in history[2024].values()
