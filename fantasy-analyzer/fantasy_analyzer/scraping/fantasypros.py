"""FantasyPros projection scraper and Sleeper roster updater.

Scrapes weekly PPR projected points for QB/RB/WR/TE from FantasyPros,
matches players to Sleeper player_ids via name normalisation, and stores
results in the player_projections table.

Also pulls current rosters from the Sleeper API and stores them in
current_rosters so power rankings can compute optimal lineup scores.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from difflib import get_close_matches

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Positions to scrape — no K or DST for NNBE
_POSITIONS = ["qb", "rb", "wr", "te"]

_FP_URL = "https://www.fantasypros.com/nfl/projections/{pos}.php"
_SLEEPER_ROSTERS_URL = "https://api.sleeper.app/v1/league/{league_id}/rosters"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"\b(jr\.?|sr\.?|ii|iii|iv)\s*$", re.IGNORECASE)


def _norm(name: str) -> str:
    """Normalise a player name for fuzzy matching."""
    name = name.lower().strip()
    name = _SUFFIX_RE.sub("", name).strip()
    name = name.replace(".", "").replace("'", "").replace("’", "")
    name = name.replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# FantasyPros scraper
# ---------------------------------------------------------------------------

def _scrape_position(pos: str, week: int) -> list[dict]:
    """Scrape one position page and return [{name, position, projected_pts}]."""
    url = f"{_FP_URL.format(pos=pos)}?week={week}&scoring=PPR"
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("FantasyPros fetch failed for %s wk%s: %s", pos.upper(), week, e)
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="data")
    if not table:
        log.warning("No #data table found for %s wk%s", pos.upper(), week)
        return []

    tbody = table.find("tbody")
    if not tbody:
        return []

    players = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # Player name is in the first cell inside an <a> tag
        name_tag = cells[0].find("a")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)

        # FPTS is the last numeric cell
        try:
            fpts = float(cells[-1].get_text(strip=True).replace(",", ""))
        except ValueError:
            continue

        if fpts <= 0:
            continue

        players.append({"name": name, "position": pos.upper(), "projected_pts": fpts})

    log.info("Scraped %d %s projections for week %d", len(players), pos.upper(), week)
    return players


def scrape_week_projections(week: int) -> list[dict]:
    """Scrape all relevant positions for a given NFL week."""
    results = []
    for pos in _POSITIONS:
        results.extend(_scrape_position(pos, week))
    return results


# ---------------------------------------------------------------------------
# Player name matching
# ---------------------------------------------------------------------------

def _build_name_index(con: sqlite3.Connection) -> dict[str, str]:
    """Return {normalised_name: player_id} from the players table."""
    rows = con.execute(
        "SELECT player_id, full_name FROM players WHERE full_name IS NOT NULL"
    ).fetchall()
    index: dict[str, str] = {}
    for player_id, full_name in rows:
        key = _norm(full_name)
        index[key] = player_id
    return index


def match_to_sleeper(
    fp_players: list[dict],
    con: sqlite3.Connection,
) -> list[dict]:
    """Match FantasyPros names to Sleeper player_ids. Logs unmatched players."""
    index = _build_name_index(con)
    norm_keys = list(index.keys())

    matched: list[dict] = []
    unmatched: list[str] = []

    for p in fp_players:
        key = _norm(p["name"])
        player_id = index.get(key)

        if not player_id:
            # Fuzzy fallback — require high similarity (0.88) to avoid false matches
            hits = get_close_matches(key, norm_keys, n=1, cutoff=0.88)
            if hits:
                player_id = index[hits[0]]
                log.debug("Fuzzy match: '%s' → '%s'", p["name"], hits[0])
            else:
                unmatched.append(p["name"])
                continue

        matched.append({**p, "player_id": player_id})

    if unmatched:
        log.warning(
            "%d unmatched FantasyPros players: %s",
            len(unmatched),
            ", ".join(unmatched[:20]),
        )

    return matched


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

def store_projections(
    con: sqlite3.Connection,
    matched: list[dict],
    season: int,
    week: int,
) -> int:
    """Upsert matched projections into player_projections. Returns count stored."""
    if not matched:
        return 0

    now = datetime.now(timezone.utc).isoformat()
    con.executemany(
        """INSERT OR REPLACE INTO player_projections
               (season, week, player_id, position, projected_pts, scraped_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (season, week, p["player_id"], p["position"], p["projected_pts"], now)
            for p in matched
        ],
    )
    con.commit()
    return len(matched)


def run_projections_scrape(
    con: sqlite3.Connection,
    season: int,
    week: int,
) -> int:
    """Scrape FantasyPros projections, match to Sleeper IDs, store in DB.

    Returns the number of players stored.
    """
    log.info("Scraping FantasyPros projections — season %d, week %d", season, week)
    fp_players = scrape_week_projections(week)

    if not fp_players:
        log.warning("No projection data scraped — check FantasyPros page structure")
        return 0

    matched = match_to_sleeper(fp_players, con)
    stored = store_projections(con, matched, season, week)
    log.info("Stored %d / %d player projections", stored, len(fp_players))
    return stored


# ---------------------------------------------------------------------------
# Sleeper roster refresh
# ---------------------------------------------------------------------------

def fetch_current_rosters(league_id: str) -> list[dict]:
    """Pull current roster player lists from the Sleeper API."""
    url = _SLEEPER_ROSTERS_URL.format(league_id=league_id)
    try:
        # verify=False: public read-only Sleeper API (Windows SSL cert issue)
        resp = httpx.get(url, timeout=30.0, verify=False)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.error("Failed to fetch rosters from Sleeper: %s", e)
        return []

    entries: list[dict] = []
    for roster in resp.json() or []:
        roster_id = roster.get("roster_id")
        if not roster_id:
            continue

        all_players = set(roster.get("players") or [])
        taxi      = set(roster.get("taxi")    or [])
        reserve   = set(roster.get("reserve") or [])

        for player_id in all_players:
            if player_id in taxi:
                status = "taxi"
            elif player_id in reserve:
                status = "reserve"
            else:
                status = "active"
            entries.append(
                {"roster_id": roster_id, "player_id": player_id, "status": status}
            )

    return entries


def update_current_rosters(con: sqlite3.Connection, league_id: str) -> int:
    """Replace current_rosters for this league with fresh Sleeper data.

    Returns number of player-roster records written.
    """
    entries = fetch_current_rosters(league_id)
    if not entries:
        log.warning("No roster data returned for league %s", league_id)
        return 0

    now = datetime.now(timezone.utc).isoformat()

    con.execute("DELETE FROM current_rosters WHERE league_id = ?", (league_id,))
    con.executemany(
        """INSERT INTO current_rosters (league_id, roster_id, player_id, status, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        [(league_id, e["roster_id"], e["player_id"], e["status"], now) for e in entries],
    )
    con.commit()

    log.info("Updated %d roster entries for league %s", len(entries), league_id)
    return len(entries)
