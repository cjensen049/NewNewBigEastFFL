"""League calendar — compute season milestones and draft events from the DB."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

# Approximate NFL Week 1 kickoff dates (Thursday of Week 1 each season).
# Fantasy weeks align with NFL weeks, so we use these as anchors.
NFL_WEEK1: dict[int, date] = {
    2021: date(2021, 9, 9),
    2022: date(2022, 9, 8),
    2023: date(2023, 9, 7),
    2024: date(2024, 9, 5),
    2025: date(2025, 9, 4),
    2026: date(2026, 9, 3),  # approximate
}

# Approximate months when rookie/startup drafts are held each year.
DRAFT_MONTHS: dict[int, str] = {
    2021: "Aug 2021",   # startup draft before first season
    2022: "May 2022",
    2023: "May 2023",
    2024: "May 2024",
    2025: "May 2025",
    2026: "Jun 2026",   # currently in progress
}


def _week_range(season: int, week: int) -> tuple[str, str] | tuple[None, None]:
    """Return (start_iso, end_iso) for a fantasy week, or (None, None) if unknown."""
    base = NFL_WEEK1.get(season)
    if base is None:
        return None, None
    start = base + timedelta(weeks=week - 1)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _fmt(iso: str | None) -> str:
    """Format an ISO date string as 'Mon D, YYYY'."""
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return d.strftime("%b %-d, %Y")


def get_calendar_events(con: sqlite3.Connection) -> list[dict]:
    """Return all calendar events sorted newest season first, then by week within season."""
    leagues = con.execute(
        "SELECT league_id, season, status, playoff_week_start, last_scored_leg FROM leagues ORDER BY season DESC"
    ).fetchall()

    drafts_by_season: dict[int, dict] = {
        r[2]: {"type": r[3], "status": r[4]}
        for r in con.execute("SELECT draft_id, league_id, season, type, status FROM drafts").fetchall()
    }

    events: list[dict] = []

    for league_id, season, status, playoff_week_start, last_scored_leg in leagues:
        reg_end_week = (playoff_week_start or 15) - 1  # last regular-season week
        playoff_start_week = playoff_week_start or 15
        champ_week = last_scored_leg or 17

        # ── Draft ────────────────────────────────────────────────────────────
        draft = drafts_by_season.get(season, {})
        draft_type = draft.get("type", "linear")
        draft_status = draft.get("status", "unknown")
        draft_label = "Startup Draft" if draft_type == "snake" else "Rookie Draft"
        events.append({
            "season": season,
            "sort_key": 0,
            "type": "draft",
            "status": draft_status,
            "title": f"{season} {draft_label}",
            "subtitle": DRAFT_MONTHS.get(season, f"Offseason {season}"),
            "date_start": None,
            "date_end": None,
        })

        # ── Regular season ───────────────────────────────────────────────────
        rs_start, _ = _week_range(season, 1)
        _, rs_end = _week_range(season, reg_end_week)
        events.append({
            "season": season,
            "sort_key": 1,
            "type": "regular_season",
            "status": "complete" if status == "complete" else ("active" if status == "in_season" else "upcoming"),
            "title": f"{season} Regular Season",
            "subtitle": f"Weeks 1–{reg_end_week}",
            "date_start": rs_start,
            "date_end": rs_end,
        })

        # ── Playoffs ─────────────────────────────────────────────────────────
        pl_start, _ = _week_range(season, playoff_start_week)
        _, pl_end = _week_range(season, champ_week - 1)
        events.append({
            "season": season,
            "sort_key": 2,
            "type": "playoffs",
            "status": "complete" if status == "complete" else ("active" if status == "in_season" else "upcoming"),
            "title": f"{season} Playoffs",
            "subtitle": f"Weeks {playoff_start_week}–{champ_week - 1}",
            "date_start": pl_start,
            "date_end": pl_end,
        })

        # ── Championship ─────────────────────────────────────────────────────
        champ_start, champ_end = _week_range(season, champ_week)
        events.append({
            "season": season,
            "sort_key": 3,
            "type": "championship",
            "status": "complete" if status == "complete" else ("active" if status == "in_season" else "upcoming"),
            "title": f"{season} Championship",
            "subtitle": f"Week {champ_week}",
            "date_start": champ_start,
            "date_end": champ_end,
        })

    # Sort: newest season first, then by sort_key (draft → reg → playoffs → champ)
    events.sort(key=lambda e: (-e["season"], e["sort_key"]))

    # Format dates for display
    for e in events:
        e["date_start_fmt"] = _fmt(e["date_start"])
        e["date_end_fmt"] = _fmt(e["date_end"])

    return events
