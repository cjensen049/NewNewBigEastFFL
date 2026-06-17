"""FantasyCalc data fetcher — dynasty player values and pick values.

Fetches the live values feed from the FantasyCalc API. Unlike DynastyProcess,
FantasyCalc tags every player with a `sleeperId`, so no name matching is
needed. Draft picks are returned in the same list, named like "2026 Pick
1.01" — identical format to DynastyProcess, parsed via the shared
fantasy_analyzer.scraping.pick_names helper.

NumQbs=2 (SuperFlex) is hardcoded since NNBE is always superflex.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

import httpx

from fantasy_analyzer.scraping.pick_names import parse_pick_name

log = logging.getLogger(__name__)

_VALUES_URL = "https://api.fantasycalc.com/values/current"
_SOURCE = "fantasycalc"


def _fetch_values() -> list[dict]:
    """Fetch the current FantasyCalc dynasty SuperFlex values feed."""
    params = {"isDynasty": "true", "numQbs": 2, "ppr": 1, "includeAdp": "false"}
    resp = httpx.get(_VALUES_URL, params=params, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def run_fantasycalc_scrape(con: sqlite3.Connection) -> tuple[int, int]:
    """Fetch FantasyCalc values, match to Sleeper IDs, store in DB.

    Returns (players_stored, picks_stored).
    """
    log.info("Fetching FantasyCalc values...")
    items = _fetch_values()
    log.info("  values feed: %d items", len(items))

    known_player_ids = {
        r[0] for r in con.execute("SELECT player_id FROM players").fetchall()
    }

    now = datetime.now(timezone.utc).isoformat()
    player_inserts: list[tuple] = []
    pick_buckets: dict[tuple, list[float]] = {}
    unmatched = 0

    for item in items:
        player = item.get("player") or {}
        try:
            value = float(item.get("value") or 0)
        except (ValueError, TypeError):
            continue
        if value <= 0:
            continue

        if player.get("position") == "PICK":
            parsed = parse_pick_name(player.get("name") or "")
            if not parsed:
                continue
            season, rnd, tier = parsed
            pick_buckets.setdefault((season, rnd, tier), []).append(value)
            continue

        sleeper_id = player.get("sleeperId")
        if not sleeper_id or sleeper_id not in known_player_ids:
            unmatched += 1
            continue

        age = player.get("maybeAge")
        try:
            age = float(age) if age else None
        except (ValueError, TypeError):
            age = None

        player_inserts.append((sleeper_id, value, age, now))

    log.info(
        "  Player matches: %d stored, %d unmatched", len(player_inserts), unmatched
    )

    pick_inserts = [
        (season, rnd, tier, sum(vals) / len(vals), now)
        for (season, rnd, tier), vals in pick_buckets.items()
    ]
    log.info("  Pick values: %d stored", len(pick_inserts))

    # Write to DB atomically — scoped to this source so other sources'
    # rows (e.g. DynastyProcess) in the same tables are left untouched.
    con.execute("DELETE FROM player_dynasty_values WHERE source = ?", (_SOURCE,))
    con.executemany(
        """INSERT INTO player_dynasty_values (source, player_id, value, age, scraped_at)
           VALUES (?, ?, ?, ?, ?)""",
        [(_SOURCE, *row) for row in player_inserts],
    )

    con.execute("DELETE FROM pick_dynasty_values WHERE source = ?", (_SOURCE,))
    con.executemany(
        """INSERT INTO pick_dynasty_values (source, season, round, tier, value, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(_SOURCE, *row) for row in pick_inserts],
    )

    con.commit()
    return len(player_inserts), len(pick_inserts)
