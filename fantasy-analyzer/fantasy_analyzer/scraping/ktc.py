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

The same page also embeds a `leagueTeams` array with each team's current
draft-pick holdings (`teamId` is literally our Sleeper user_id, no matching
needed). This is KTC's own Sleeper-synced ownership record, including
trades, and is stored in `pick_ownership` for use by the draft-capital
component of dynasty rankings in place of our own trade-history
reconstruction.
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

    try:
        league_teams = _extract_js_array(html, "leagueTeams")
    except ValueError:
        log.warning("  leagueTeams not found — skipping pick ownership sync")
        league_teams = []

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

    # leagueTeams[].teamId is the same value as our own Sleeper user_id (confirmed
    # 12-for-12 against league_owners), so this needs no fuzzy matching at all —
    # it's KTC's authoritative, Sleeper-synced record of which owner currently
    # holds each future pick, including trades our own reconstruction may miss.
    name_to_user_id = {t.get("name"): t.get("teamId") for t in league_teams if t.get("teamId")}
    ownership_inserts = []
    for team in league_teams:
        current_user_id = team.get("teamId")
        if not current_user_id:
            continue
        for pick in team.get("draftPicks") or []:
            try:
                season = int(pick["year"])
                rnd = int(pick["round"])
            except (KeyError, TypeError, ValueError):
                continue
            original_user_id = name_to_user_id.get(pick.get("franchiseName"), current_user_id)
            ownership_inserts.append((season, rnd, current_user_id, original_user_id, now))
    log.info("  Pick ownership: %d entries", len(ownership_inserts))

    # KTC's own published roster total per team -- used directly for the roster
    # component of dynasty rankings instead of re-summing our matched player
    # values, since it's KTC's own number and KTC's own dynasty rankings are
    # exactly what owners compare themselves against.
    team_total_inserts = [
        (team["teamId"], float(team["total"]), now)
        for team in league_teams
        if team.get("teamId") and team.get("total") is not None
    ]
    log.info("  Team totals: %d entries", len(team_total_inserts))

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

    con.execute("DELETE FROM pick_ownership WHERE source = ? AND league_id = ?", (_SOURCE, league_id))
    con.executemany(
        """INSERT INTO pick_ownership (source, league_id, season, round, user_id, original_user_id, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(_SOURCE, league_id, *row) for row in ownership_inserts],
    )

    con.execute("DELETE FROM team_totals WHERE source = ? AND league_id = ?", (_SOURCE, league_id))
    con.executemany(
        """INSERT INTO team_totals (source, league_id, user_id, total, scraped_at)
           VALUES (?, ?, ?, ?, ?)""",
        [(_SOURCE, league_id, *row) for row in team_total_inserts],
    )

    con.commit()
    return len(player_inserts), len(pick_inserts)
