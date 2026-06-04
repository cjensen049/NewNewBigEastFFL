"""Dynasty ranking data sources for NNBE.

Fetches per-owner roster values from KTC, FantasyCalc, and Dynasty Daddy.
Each source returns a standardised dict:

    {
        "source":       "ktc" | "fantasycalc" | "dynasty_daddy",
        "fetched_at":   ISO-8601 UTC string,
        "owner_values": {user_id: total_roster_value, ...},
        "owner_ranks":  {user_id: rank_1_to_12, ...},
    }

Entry point: fetch_all_sources(league_id, season, db_path, players_cache_path)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from fantasy_analyzer.api.sleeper import SleeperClient
from fantasy_analyzer.rankings.player_matching import (
    build_name_index,
    fuzzy_match,
    load_aliases,
)

log = logging.getLogger(__name__)

_KTC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://keeptradecut.com/dynasty-rankings",
}

# ---------------------------------------------------------------------------
# Roster context — loaded once, shared by all source fetchers
# ---------------------------------------------------------------------------

@dataclass
class RosterContext:
    """Shared lookup tables loaded before fetching any source."""
    rosters: dict[int, list[str]] = field(default_factory=dict)       # roster_id -> [player_ids]
    roster_to_user: dict[int, str] = field(default_factory=dict)      # roster_id -> user_id
    user_to_name: dict[str, str] = field(default_factory=dict)        # user_id -> canonical_name
    name_index: dict[str, str] = field(default_factory=dict)          # normalized_name -> sleeper_id
    aliases: dict[str, str] = field(default_factory=dict)             # normalized_alias -> sleeper_id
    is_superflex: bool = True                                          # NNBE always superflex


async def _load_roster_context(
    league_id: str,
    db_path: Path,
    players_cache_path: Path,
    aliases_path: Path,
) -> RosterContext:
    """Fetch current Sleeper rosters and load owner/player lookup tables."""
    client = SleeperClient()
    sl_rosters = await client.get_rosters(league_id)
    rosters = {r.roster_id: r.players for r in sl_rosters}

    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT lo.roster_id, lo.user_id, o.canonical_name
            FROM league_owners lo
            JOIN owners o ON lo.user_id = o.user_id
            WHERE lo.league_id = ?
            """,
            (league_id,),
        ).fetchall()
    finally:
        con.close()

    roster_to_user = {r[0]: r[1] for r in rows}
    user_to_name = {r[1]: r[2] for r in rows}

    return RosterContext(
        rosters=rosters,
        roster_to_user=roster_to_user,
        user_to_name=user_to_name,
        name_index=build_name_index(players_cache_path),
        aliases=load_aliases(aliases_path),
        is_superflex=True,
    )


# ---------------------------------------------------------------------------
# Shared ranking helper
# ---------------------------------------------------------------------------

def compute_owner_ranks(
    player_values: dict[str, float],
    ctx: RosterContext,
    source: str,
) -> dict:
    """Sum player values per owner roster and return the standard result dict."""
    owner_values: dict[str, float] = {}
    for roster_id, player_ids in ctx.rosters.items():
        user_id = ctx.roster_to_user.get(roster_id)
        if not user_id:
            continue
        owner_values[user_id] = sum(player_values.get(pid, 0.0) for pid in player_ids)

    sorted_owners = sorted(owner_values.items(), key=lambda x: -x[1])
    owner_ranks = {uid: rank + 1 for rank, (uid, _) in enumerate(sorted_owners)}

    return {
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner_values": owner_values,
        "owner_ranks": owner_ranks,
    }


# ---------------------------------------------------------------------------
# Error logging
# ---------------------------------------------------------------------------

def log_error(source: str, message: str, errors_path: Path = Path("errors.md")) -> None:
    """Append a timestamped error to errors.md and Python logging."""
    log.error("[%s] %s", source, message)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = f"\n## {timestamp} [{source}]\n{message}\n"
    try:
        with open(errors_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except OSError:
        pass  # Don't crash if errors.md can't be written


# ---------------------------------------------------------------------------
# Source 1: KeepTradeCut
# ---------------------------------------------------------------------------

async def fetch_ktc(league_id: str, season: int, ctx: RosterContext) -> dict:
    """Fetch KTC dynasty values. Tries three approaches in order."""
    # 1. KTC league power rankings (Sleeper-integrated, no per-player work needed)
    try:
        result = await _ktc_league_endpoint(league_id, ctx)
        if result:
            log.info("KTC: used league endpoint")
            return result
    except Exception as e:
        log.warning("KTC league endpoint failed: %s", e)

    # 2. Scrape dynasty rankings page with httpx
    try:
        result = await _ktc_scrape_httpx(ctx)
        log.info("KTC: used httpx scrape")
        return result
    except Exception as e:
        log.warning("KTC httpx scrape failed: %s — trying Playwright", e)

    # 3. Playwright headless browser fallback
    return await _ktc_scrape_playwright(ctx)


async def _ktc_league_endpoint(league_id: str, ctx: RosterContext) -> dict | None:
    """Try KTC's Sleeper-integrated league power rankings endpoint."""
    url = "https://keeptradecut.com/dynasty/power-rankings/teams"
    params = {"leagueId": league_id, "platform": "Sleeper"}

    async with httpx.AsyncClient(timeout=30, headers=_KTC_HEADERS, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    # Try JSON first
    try:
        data = resp.json()
        result = _parse_ktc_team_data(data, ctx)
        if result:
            return result
    except Exception:
        pass

    # Try embedded JS variable in HTML
    for var in ("teamData", "powerRankingsData", "rankingsData"):
        match = re.search(rf"var\s+{var}\s*=\s*(\[.+?\]);", resp.text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                result = _parse_ktc_team_data(data, ctx)
                if result:
                    return result
            except Exception:
                continue

    return None


def _parse_ktc_team_data(data: object, ctx: RosterContext) -> dict | None:
    """Parse a KTC team-level response into the standard result structure."""
    if not isinstance(data, list) or not data:
        return None

    first = data[0]
    uid_key = next(
        (k for k in first if "user" in k.lower() or "sleeper" in k.lower()), None
    )
    val_key = next(
        (k for k in first if "value" in k.lower() or "total" in k.lower() or "power" in k.lower()),
        None,
    )
    if not uid_key or not val_key:
        return None

    owner_values: dict[str, float] = {}
    for team in data:
        user_id = str(team.get(uid_key, ""))
        value = float(team.get(val_key, 0) or 0)
        if user_id in ctx.user_to_name:
            owner_values[user_id] = value

    if not owner_values:
        return None

    sorted_owners = sorted(owner_values.items(), key=lambda x: -x[1])
    return {
        "source": "ktc",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner_values": owner_values,
        "owner_ranks": {uid: i + 1 for i, (uid, _) in enumerate(sorted_owners)},
    }


async def _ktc_scrape_httpx(ctx: RosterContext) -> dict:
    """Scrape KTC dynasty rankings page and parse the embedded playerData JS variable."""
    url = "https://keeptradecut.com/dynasty-rankings"
    params = {"filters": "QB|WR|RB|TE|RDP", "format": "2"}

    async with httpx.AsyncClient(timeout=30, headers=_KTC_HEADERS, follow_redirects=True) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()

    players = _parse_ktc_player_data(resp.text)
    if not players:
        raise ValueError(
            "No playerData variable found in KTC response — page likely requires JavaScript rendering"
        )

    return _ktc_players_to_ranks(players, ctx)


def _parse_ktc_player_data(html: str) -> list | None:
    """Extract var playerData = [...] from KTC page HTML."""
    match = re.search(r"var\s+playerData\s*=\s*(\[.+?\]);", html, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _ktc_players_to_ranks(players: list, ctx: RosterContext) -> dict:
    """Map KTC player list to owner totals via fuzzy name matching."""
    player_values: dict[str, float] = {}
    unmatched = 0
    for p in players:
        name = p.get("playerName") or p.get("name") or ""
        value = float(p.get("value", 0) or 0)
        if not name or value == 0:
            continue
        sleeper_id = fuzzy_match(name, ctx.name_index, ctx.aliases)
        if sleeper_id:
            if player_values.get(sleeper_id, 0) < value:
                player_values[sleeper_id] = value
        else:
            unmatched += 1

    if unmatched:
        log.debug("KTC: %d players unmatched (low value or unknown)", unmatched)

    return compute_owner_ranks(player_values, ctx, "ktc")


async def _ktc_scrape_playwright(ctx: RosterContext) -> dict:
    """Playwright headless browser fallback for KTC (requires playwright install)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise ImportError(
            "Playwright required for KTC headless scrape: "
            "pip install playwright && playwright install chromium"
        )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(
            "https://keeptradecut.com/dynasty-rankings?filters=QB|WR|RB|TE|RDP&format=2",
            wait_until="networkidle",
        )
        await page.wait_for_function("typeof playerData !== 'undefined'", timeout=15000)
        html = await page.content()
        await browser.close()

    players = _parse_ktc_player_data(html)
    if not players:
        raise ValueError("No playerData found after Playwright render")

    log.info("KTC: used Playwright fallback")
    return _ktc_players_to_ranks(players, ctx)


# ---------------------------------------------------------------------------
# Source 2: FantasyCalc
# ---------------------------------------------------------------------------

async def fetch_fantasycalc(league_id: str, season: int, ctx: RosterContext) -> dict:
    """Fetch FantasyCalc dynasty values. Uses sleeperId for direct mapping — no fuzzy match needed."""
    num_qbs = 2 if ctx.is_superflex else 1
    params = {
        "isDynasty": "true",
        "numQbs": num_qbs,
        "ppr": 1,
        "includeAdp": "false",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://api.fantasycalc.com/values/current", params=params
        )
        resp.raise_for_status()
        data = resp.json()

    player_values: dict[str, float] = {}
    for item in data:
        sleeper_id = (item.get("player") or {}).get("sleeperId")
        value = float(item.get("value", 0) or 0)
        if sleeper_id and value > 0:
            player_values[str(sleeper_id)] = value

    return compute_owner_ranks(player_values, ctx, "fantasycalc")


# ---------------------------------------------------------------------------
# Source 3: Dynasty Daddy
# ---------------------------------------------------------------------------

async def fetch_dynasty_daddy(league_id: str, season: int, ctx: RosterContext) -> dict:
    """Fetch Dynasty Daddy values. Tries league endpoint first, falls back to player list."""
    try:
        result = await _dynasty_daddy_league(league_id, ctx)
        if result:
            log.info("Dynasty Daddy: used league endpoint")
            return result
    except Exception as e:
        log.warning("Dynasty Daddy league endpoint failed: %s", e)

    log.info("Dynasty Daddy: falling back to player-by-player")
    return await _dynasty_daddy_players(ctx)


async def _dynasty_daddy_league(league_id: str, ctx: RosterContext) -> dict | None:
    """Try Dynasty Daddy's Sleeper-integrated league power rankings endpoint."""
    url = f"https://dynasty-daddy.com/api/v1/league/{league_id}/power_rankings"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()

    if not isinstance(data, list) or not data:
        return None

    # Field names vary across DD API versions — try known candidates
    first = data[0]
    uid_key = next(
        (k for k in first if "user" in k.lower() or "sleeper" in k.lower()), None
    )
    val_key = next(
        (k for k in first if "value" in k.lower() or "total" in k.lower() or "sf" in k.lower()),
        None,
    )
    if not uid_key or not val_key:
        return None

    owner_values: dict[str, float] = {}
    for team in data:
        user_id = str(team.get(uid_key, ""))
        value = float(team.get(val_key, 0) or 0)
        if user_id in ctx.user_to_name:
            owner_values[user_id] = value

    if not owner_values:
        return None

    sorted_owners = sorted(owner_values.items(), key=lambda x: -x[1])
    return {
        "source": "dynasty_daddy",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner_values": owner_values,
        "owner_ranks": {uid: i + 1 for i, (uid, _) in enumerate(sorted_owners)},
    }


async def _dynasty_daddy_players(ctx: RosterContext) -> dict:
    """Fetch Dynasty Daddy's full player values list and match by name."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get("https://dynasty-daddy.com/api/v1/player/values")
        resp.raise_for_status()
        data = resp.json()

    value_key = "sf_trade_value" if ctx.is_superflex else "trade_value"

    player_values: dict[str, float] = {}
    unmatched = 0
    for player in data:
        name = player.get("full_name") or player.get("name") or ""
        value = float(player.get(value_key) or 0)
        if not name or value == 0:
            continue
        sleeper_id = fuzzy_match(name, ctx.name_index, ctx.aliases)
        if sleeper_id:
            if player_values.get(sleeper_id, 0) < value:
                player_values[sleeper_id] = value
        else:
            unmatched += 1

    if unmatched:
        log.debug("Dynasty Daddy: %d players unmatched", unmatched)

    return compute_owner_ranks(player_values, ctx, "dynasty_daddy")


# ---------------------------------------------------------------------------
# Master entry point
# ---------------------------------------------------------------------------

async def fetch_all_sources(
    league_id: str,
    season: int,
    db_path: Path | str = "data/league.db",
    players_cache_path: Path | str = "data/players.json",
    aliases_path: Path | str | None = None,
) -> list[dict]:
    """
    Fetch dynasty values from all three sources concurrently.
    Returns only successful results; failed sources are logged and skipped.
    """
    if aliases_path is None:
        aliases_path = Path(__file__).parent / "player_aliases.json"

    ctx = await _load_roster_context(
        league_id,
        Path(db_path),
        Path(players_cache_path),
        Path(aliases_path),
    )

    source_names = ["ktc", "fantasycalc", "dynasty_daddy"]
    tasks = [
        fetch_ktc(league_id, season, ctx),
        fetch_fantasycalc(league_id, season, ctx),
        fetch_dynasty_daddy(league_id, season, ctx),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    good: list[dict] = []
    for name, result in zip(source_names, results):
        if isinstance(result, dict):
            good.append(result)
        else:
            log_error(name, f"{type(result).__name__}: {result}")

    log.info("Dynasty sources: %d/%d succeeded", len(good), len(tasks))
    return good
