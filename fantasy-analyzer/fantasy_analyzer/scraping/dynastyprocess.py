"""DynastyProcess data fetcher — dynasty player values and pick values.

Fetches two public CSVs from the DynastyProcess GitHub repository:

  values.csv       — player + pick dynasty values; value_2qb column used
                     (SuperFlex leagues like NNBE favour the 2QB valuation)
  db_playerids.csv — cross-reference of player IDs across 20+ platforms,
                     including sleeper_id, which bridges our DB to DP values

No HTML scraping. Pure HTTPS GET to GitHub raw content.
DynastyProcess refreshes these files daily.
"""

from __future__ import annotations

import csv
import io
import logging
import sqlite3
from datetime import datetime, timezone

import httpx

from fantasy_analyzer.scraping.pick_names import parse_pick_name

log = logging.getLogger(__name__)

_VALUES_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/values.csv"
)
_IDS_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
)

# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def _fetch_csv(url: str) -> list[dict]:
    """Fetch a CSV URL and return rows as dicts."""
    resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    return list(reader)


# ---------------------------------------------------------------------------
# Main fetch + store
# ---------------------------------------------------------------------------

_SOURCE = "dynastyprocess"


def run_dynasty_scrape(con: sqlite3.Connection) -> tuple[int, int]:
    """Fetch DynastyProcess CSVs, match to Sleeper IDs, store in DB.

    Returns (players_stored, picks_stored).
    """
    log.info("Fetching DynastyProcess values.csv...")
    all_rows = _fetch_csv(_VALUES_URL)

    player_rows = [r for r in all_rows if r.get("pos", "").upper() != "PICK" and r.get("value_2qb")]
    pick_rows   = [r for r in all_rows if r.get("pos", "").upper() == "PICK"]

    log.info(
        "  values.csv: %d player rows, %d pick rows", len(player_rows), len(pick_rows)
    )

    log.info("Fetching DynastyProcess db_playerids.csv...")
    id_rows = _fetch_csv(_IDS_URL)

    # sleeper_id → dp_name lookup
    sleeper_to_dp: dict[str, str] = {}
    for r in id_rows:
        sid = (r.get("sleeper_id") or "").strip()
        nm  = (r.get("name") or "").strip()
        if sid and nm:
            sleeper_to_dp[sid] = nm

    # dp_name → (value, age) lookup
    dp_val: dict[str, float] = {}
    dp_age: dict[str, float] = {}
    for r in player_rows:
        nm = (r.get("player") or "").strip()
        if not nm:
            continue
        try:
            dp_val[nm] = float(r["value_2qb"])
        except (ValueError, TypeError):
            pass
        try:
            age = float(r.get("age") or 0)
            if age > 0:
                dp_age[nm] = age
        except (ValueError, TypeError):
            pass

    # Match our DB players → dynasty value + age
    db_players = con.execute(
        "SELECT player_id, full_name FROM players WHERE full_name IS NOT NULL"
    ).fetchall()

    now = datetime.now(timezone.utc).isoformat()
    player_inserts: list[tuple] = []
    unmatched = 0

    for player_id, full_name in db_players:
        # Prefer sleeper_id → dp canonical name route
        dp_name = sleeper_to_dp.get(player_id)
        val = dp_val.get(dp_name) if dp_name else None

        # Fallback: try direct name match
        if val is None:
            val = dp_val.get(full_name)
            dp_name = full_name if val is not None else dp_name

        if val is None or val <= 0:
            unmatched += 1
            continue

        age = dp_age.get(dp_name) if dp_name else None
        player_inserts.append((player_id, val, age, now))

    log.info(
        "  Player matches: %d stored, %d unmatched", len(player_inserts), unmatched
    )

    # Store pick values — average duplicates that share (season, round, tier)
    pick_buckets: dict[tuple, list[float]] = {}
    for r in pick_rows:
        nm = (r.get("player") or "").strip()
        parsed = parse_pick_name(nm)
        if not parsed:
            continue
        season, rnd, tier = parsed
        try:
            val = float(r.get("value_2qb") or 0)
        except (ValueError, TypeError):
            continue
        if val <= 0:
            continue
        key = (season, rnd, tier)
        pick_buckets.setdefault(key, []).append(val)

    pick_inserts = [
        (season, rnd, tier, sum(vals) / len(vals), now)
        for (season, rnd, tier), vals in pick_buckets.items()
    ]

    log.info("  Pick values: %d stored", len(pick_inserts))

    # Write to DB atomically — scoped to this source so other sources'
    # rows (e.g. FantasyCalc) in the same tables are left untouched.
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
