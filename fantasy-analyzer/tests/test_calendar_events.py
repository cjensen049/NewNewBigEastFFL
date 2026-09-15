"""Tests for analysis/calendar_events.py — season milestone status logic."""

import sqlite3
from datetime import date, timedelta

import pytest

import fantasy_analyzer.analysis.calendar_events as calendar_events
from fantasy_analyzer.analysis.calendar_events import get_calendar_events
from fantasy_analyzer.db.schema import DDL

SYNTH_SEASON = 9999  # fake season, not a real NFL_WEEK1 year


@pytest.fixture
def db():
    con = sqlite3.connect(":memory:")
    con.executescript(DDL)
    con.commit()
    return con


@pytest.fixture
def anchor_today(monkeypatch):
    """Anchor a synthetic season's Week 1 so `today` always falls in Week 4 of
    the regular season, regardless of when the test actually runs."""
    week1 = date.today() - timedelta(weeks=3)
    monkeypatch.setitem(calendar_events.NFL_WEEK1, SYNTH_SEASON, week1)
    return week1


def _league(con, league_id, season, status, pws=15):
    con.execute(
        "INSERT INTO leagues "
        "(league_id, season, name, status, total_rosters, playoff_week_start, last_scored_leg) "
        "VALUES (?,?,?,?,?,?,?)",
        (league_id, season, "Test League", status, 12, pws, None),
    )
    con.commit()


def _events_by_type(events, season):
    return {e["type"]: e for e in events if e["season"] == season}


class TestCalendarEventStatus:
    def test_in_progress_season_playoffs_and_championship_are_upcoming(self, db, anchor_today):
        """Regression: the league row stays 'in_season' for the whole year, so
        playoffs/championship must be judged by their own date range rather
        than that coarse flag -- otherwise they show 'active' from week 1."""
        _league(db, "L1", SYNTH_SEASON, status="in_season")

        events = _events_by_type(get_calendar_events(db), SYNTH_SEASON)
        assert events["regular_season"]["status"] == "active"
        assert events["playoffs"]["status"] == "upcoming"
        assert events["championship"]["status"] == "upcoming"

    def test_completed_season_everything_complete(self, db, anchor_today):
        _league(db, "L1", SYNTH_SEASON, status="complete")

        events = _events_by_type(get_calendar_events(db), SYNTH_SEASON)
        assert events["regular_season"]["status"] == "complete"
        assert events["playoffs"]["status"] == "complete"
        assert events["championship"]["status"] == "complete"

    def test_championship_week_is_final_week_of_season(self, db, anchor_today):
        """Championship week must be derived from playoff_week_start (final week
        of a standard 3-week bracket), not from last_scored_leg -- that field
        tracks the last week scored SO FAR and keeps climbing all season."""
        _league(db, "L1", SYNTH_SEASON, status="in_season", pws=15)

        events = _events_by_type(get_calendar_events(db), SYNTH_SEASON)
        assert events["championship"]["subtitle"] == "Week 17"
        assert events["playoffs"]["subtitle"] == "Weeks 15–16"
