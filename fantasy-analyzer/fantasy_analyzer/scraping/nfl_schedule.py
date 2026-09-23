"""NFL game schedule + kickoff time slots, from ESPN's public scoreboard API.

Used to add game-time context to weekly recap/preview narratives (e.g. "3 of
your starters play in the Monday night finale"). Sleeper's own projections
data only has day-level precision, not kickoff time.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

log = logging.getLogger(__name__)

_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
_ET = ZoneInfo("America/New_York")

# ESPN's team abbreviation differs from Sleeper/our players.team in one case.
_TEAM_REMAP = {"WSH": "WAS"}


def _slot_for(iso_utc: str) -> str:
    """Bucket a game's kickoff time into a human slot label (Eastern time)."""
    dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(_ET)
    weekday = dt.weekday()  # Mon=0 ... Sun=6
    if weekday == 3:
        return "Thursday Night"
    if weekday == 0:
        return "Monday Night"
    if weekday == 6:
        hour = dt.hour + dt.minute / 60
        if hour < 15.5:
            return "Sunday Early"
        if hour < 18.5:
            return "Sunday Late"
        return "Sunday Night"
    return "Other"  # Friday/Saturday international or holiday games


def fetch_week_schedule(season: int, week: int) -> dict[str, str]:
    """Return {team_abbr: slot_label} for every team playing this week."""
    try:
        resp = httpx.get(
            _URL, params={"week": week, "seasontype": 2, "year": season}, timeout=30.0, verify=False
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("ESPN scoreboard fetch failed for %d week %d: %s", season, week, e)
        return {}

    slots: dict[str, str] = {}
    for event in resp.json().get("events", []):
        if not event.get("date"):
            continue
        slot = _slot_for(event["date"])
        comp = (event.get("competitions") or [{}])[0]
        for c in comp.get("competitors", []):
            abbr = (c.get("team") or {}).get("abbreviation")
            if abbr:
                slots[_TEAM_REMAP.get(abbr, abbr)] = slot
    return slots


def store_week_schedule(con: sqlite3.Connection, slots: dict[str, str], season: int, week: int) -> int:
    """Upsert into game_slots. Returns count stored."""
    if not slots:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO game_slots (season, week, team, slot) VALUES (?, ?, ?, ?)",
        [(season, week, team, slot) for team, slot in slots.items()],
    )
    con.commit()
    return len(slots)


def run_schedule_scrape(con: sqlite3.Connection, season: int, week: int) -> int:
    """Fetch and store this week's kickoff-time slot per NFL team. Returns count stored."""
    log.info("Fetching NFL schedule slots for %d week %d", season, week)
    slots = fetch_week_schedule(season, week)
    stored = store_week_schedule(con, slots, season, week)
    log.info("Stored %d team schedule slots for %d week %d", stored, season, week)
    return stored
