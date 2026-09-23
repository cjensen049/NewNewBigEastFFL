"""Tests for scraping/nfl_schedule.py -- kickoff-time slot bucketing.

No test hits the real ESPN API; _slot_for is a pure function of a UTC
timestamp and is tested directly.
"""

import pytest

from fantasy_analyzer.scraping.nfl_schedule import _slot_for


class TestSlotFor:
    def test_thursday_night(self):
        # 2026-09-25T00:15Z -> Thu Sep 24, 8:15pm ET
        assert _slot_for("2026-09-25T00:15Z") == "Thursday Night"

    def test_monday_night(self):
        # 2026-10-19T23:15Z -> Mon Oct 19, 7:15pm ET
        assert _slot_for("2026-10-19T23:15Z") == "Monday Night"

    def test_sunday_early(self):
        # 2026-09-27T17:00Z -> Sun Sep 27, 1:00pm ET
        assert _slot_for("2026-09-27T17:00Z") == "Sunday Early"

    def test_sunday_late(self):
        # 2026-09-27T20:05Z -> Sun Sep 27, 4:05pm ET
        assert _slot_for("2026-09-27T20:05Z") == "Sunday Late"

    def test_sunday_night(self):
        # 2026-09-28T00:20Z -> Sun Sep 27, 8:20pm ET
        assert _slot_for("2026-09-28T00:20Z") == "Sunday Night"

    def test_friday_falls_back_to_other(self):
        # 2026-11-27T18:00Z -> Fri Nov 27, 1:00pm ET (e.g. a Black Friday game)
        assert _slot_for("2026-11-27T18:00Z") == "Other"
