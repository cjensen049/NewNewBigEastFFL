"""KeepTradeCut data fetcher — dynasty player values and pick values.

KTC's general dynasty-rankings page now requires JavaScript rendering (the
embedded playerData variable was removed in a site redesign), but its
Sleeper-synced league power-rankings page is still server-rendered: it embeds
a full player list (var playersArray = [...]) directly in the HTML, scoped to
our actual league via the same numeric ID Sleeper uses. Picks are included in
that same array as entries with position "RDP", named like "2026 Early 1st" —
a format fantasy_analyzer.scraping.pick_names already parses.

KTC doesn't tag players with a sleeperId, so player rows are matched to our
DB by fuzzy name (fantasy_analyzer.rankings.player_matching), same approach
already used for Dynasty Daddy in rankings/dynasty_sources.py.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fantasy_analyzer.rankings.player_matching import build_name_index, fuzzy_match, load_aliases
from fantasy_analyzer.scraping.pick_names import parse_pick_name

log = logging.getLogger(__name__)

_OVERVIEW_URL = "https://keeptradecut.com/dynasty/power-rankings/league-overview"
_SOURCE = "ktc"
_DEFAULT_ALIASES_PATH = Path(__file__).parent.parent / "rankings" / "player_aliases.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


def _fetch_html(league_id: str) -> str:
    """Fetch the Sleeper-synced league power-rankings overview page."""
    params = {"leagueId": league_id, "platform": 2, "viewMode": 0, "viewSort": 0}
    resp = httpx.get(_OVERVIEW_URL, params=params, headers=_HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _extract_js_array(html: str, var_name: str) -> list:
    """Pull a `var <var_name> = [...]` JSON array out of inline page HTML.

    KTC's league pages embed full JSON directly in a <script> block rather
    than via a JS API, so this is plain bracket-matching, not JS execution.
    """
    marker = f"var {var_name} = "
    start = html.find(marker)
    if start == -1:
        raise ValueError(f"{var_name} not found in KTC page — page layout may have changed")

    pos = start + len(marker)
    depth = 0
    in_string = False
    escape = False
    i = pos
    while i < len(html):
        c = html[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(html[pos:i + 1])
        i += 1
    raise ValueError(f"{var_name} array in KTC page was never closed")


def run_ktc_scrape(
    con: sqlite3.Connection,
    league_id: str,
    players_cache_path: str = "data/players.json",
    aliases_path: str | Path = _DEFAULT_ALIASES_PATH,
) -> tuple[int, int]:
    """Fetch KTC's league-synced player values, match to Sleeper IDs, store in DB.

    Returns (players_stored, picks_stored).
    """
    log.info("Fetching KTC league-overview page for league %s...", league_id)
    html = _fetch_html(league_id)
    players_raw = _extract_js_array(html, "playersArray")
    log.info("  playersArray: %d entries", len(players_raw))

    name_index = build_name_index(players_cache_path)
    aliases = load_aliases(aliases_path)

    known_player_ids = {
        r[0] for r in con.execute("SELECT player_id FROM players").fetchall()
    }

    now = datetime.now(timezone.utc).isoformat()
    player_values: dict[str, tuple[float, float | None]] = {}
    pick_buckets: dict[tuple, list[float]] = {}
    unmatched = 0

    for p in players_raw:
        sf_values = p.get("superflexValues") or {}
        try:
            value = float(sf_values.get("value") or 0)
        except (ValueError, TypeError):
            continue
        if value <= 0:
            continue

        if p.get("position") == "RDP":
            parsed = parse_pick_name(p.get("playerName") or "")
            if not parsed:
                continue
            season, rnd, tier = parsed
            pick_buckets.setdefault((season, rnd, tier), []).append(value)
            continue

        sleeper_id = fuzzy_match(p.get("playerName") or "", name_index, aliases)
        if not sleeper_id or sleeper_id not in known_player_ids:
            unmatched += 1
            continue

        age = p.get("age")
        try:
            age = float(age) if age else None
        except (ValueError, TypeError):
            age = None

        # Keep the higher value if KTC lists a name twice (e.g. position changes)
        existing = player_values.get(sleeper_id)
        if existing is None or value > existing[0]:
            player_values[sleeper_id] = (value, age)

    player_inserts = [
        (sleeper_id, value, age, now)
        for sleeper_id, (value, age) in player_values.items()
    ]
    log.info(
        "  Player matches: %d stored, %d unmatched", len(player_inserts), unmatched
    )

    pick_inserts = [
        (season, rnd, tier, sum(vals) / len(vals), now)
        for (season, rnd, tier), vals in pick_buckets.items()
    ]
    log.info("  Pick values: %d stored", len(pick_inserts))

    # Write to DB atomically — scoped to this source so other sources'
    # rows (DynastyProcess, FantasyCalc) in the same tables are left untouched.
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
