"""Sleeper API client with rate limiting, retry, and player caching."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from fantasy_analyzer.api.models import (
    Draft,
    DraftSlot,
    League,
    Matchup,
    NFLPlayer,
    Roster,
    Transaction,
    User,
)

BASE_URL = "https://api.sleeper.app/v1"
log = logging.getLogger(__name__)

VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


class SleeperClient:
    """Async Sleeper API client."""

    def __init__(self, delay: float = 0.5, retries: int = 3) -> None:
        self._delay = delay
        self._retries = retries
        self._last_call: float = 0.0

    async def _get(self, path: str) -> Any:
        """GET with rate limiting and exponential backoff retry."""
        url = f"{BASE_URL}{path}"
        # verify=False: public read-only API, no credentials transmitted
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            for attempt in range(self._retries):
                elapsed = time.monotonic() - self._last_call
                if elapsed < self._delay:
                    await asyncio.sleep(self._delay - elapsed)
                try:
                    resp = await client.get(url)
                    self._last_call = time.monotonic()
                    resp.raise_for_status()
                    return resp.json()
                except httpx.HTTPStatusError as e:
                    log.warning("HTTP %s for %s (attempt %d)", e.response.status_code, url, attempt + 1)
                    if attempt == self._retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
                except httpx.RequestError as e:
                    log.warning("Request error for %s: %s (attempt %d)", url, e, attempt + 1)
                    if attempt == self._retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

    # --- League ---

    async def get_league(self, league_id: str) -> League:
        """Fetch league metadata."""
        data = await self._get(f"/league/{league_id}")
        return League.model_validate(data)

    async def get_league_chain(self, current_league_id: str) -> list[League]:
        """Walk previous_league_id links to collect all seasons, newest first."""
        chain: list[League] = []
        league_id: str | None = current_league_id
        while league_id:
            log.info("Fetching league %s", league_id)
            league = await self.get_league(league_id)
            chain.append(league)
            league_id = league.previous_league_id
        return chain

    # --- Rosters / Users ---

    async def get_rosters(self, league_id: str) -> list[Roster]:
        """Fetch all rosters for a league."""
        data = await self._get(f"/league/{league_id}/rosters")
        return [Roster.model_validate({**r, "league_id": league_id}) for r in (data or [])]

    async def get_users(self, league_id: str) -> list[User]:
        """Fetch all users for a league."""
        data = await self._get(f"/league/{league_id}/users")
        return [User.model_validate(u) for u in (data or [])]

    # --- Matchups ---

    async def get_matchups(self, league_id: str, week: int) -> list[Matchup]:
        """Fetch matchups for a single week."""
        data = await self._get(f"/league/{league_id}/matchups/{week}")
        if not data:
            return []
        return [Matchup.model_validate(m) for m in data]

    async def get_all_matchups(self, league: League) -> dict[int, list[Matchup]]:
        """Fetch matchups for all weeks in a league."""
        last_week = (league.settings.last_scored_leg or
                     league.settings.playoff_week_start + 3)
        results: dict[int, list[Matchup]] = {}
        for week in range(1, last_week + 1):
            matchups = await self.get_matchups(league.league_id, week)
            if matchups:
                results[week] = matchups
        return results

    # --- Transactions ---

    async def get_transactions(self, league_id: str, week: int) -> list[Transaction]:
        """Fetch transactions for a single week."""
        data = await self._get(f"/league/{league_id}/transactions/{week}")
        if not data:
            return []
        result = []
        for t in data:
            if t.get("type") == "commissioner":
                continue
            try:
                result.append(Transaction.model_validate({**t, "leg": week}))
            except Exception as e:
                log.warning("Skipping malformed transaction %s: %s", t.get("transaction_id"), e)
        return result

    async def get_all_transactions(self, league: League) -> list[Transaction]:
        """Fetch all transactions across all weeks."""
        last_week = (league.settings.last_scored_leg or
                     league.settings.playoff_week_start + 3)
        all_txns: list[Transaction] = []
        for week in range(1, last_week + 1):
            txns = await self.get_transactions(league.league_id, week)
            all_txns.extend(txns)
        return all_txns

    # --- Drafts ---

    async def get_drafts(self, league_id: str) -> list[Draft]:
        """Fetch drafts linked to a league."""
        data = await self._get(f"/league/{league_id}/drafts")
        return [Draft.model_validate(d) for d in (data or [])]

    async def get_draft_picks(self, draft_id: str) -> list[DraftSlot]:
        """Fetch all picks in a completed draft."""
        data = await self._get(f"/draft/{draft_id}/picks")
        return [DraftSlot.model_validate({**p, "draft_id": draft_id}) for p in (data or [])]

    # --- Players ---

    async def get_players(
        self,
        cache_path: Path,
        ttl_days: int = 7,
    ) -> dict[str, NFLPlayer]:
        """Return NFL players, using a local cache refreshed at most weekly."""
        cache_path = Path(cache_path)
        if cache_path.exists():
            age_days = (time.time() - cache_path.stat().st_mtime) / 86400
            if age_days < ttl_days:
                log.info("Loading players from cache (%s)", cache_path)
                raw = json.loads(cache_path.read_text(encoding="utf-8"))
                return _parse_players(raw)

        log.info("Fetching full player list from Sleeper (this may take a moment)...")
        raw = await self._get("/players/nfl")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(raw), encoding="utf-8")
        log.info("Player cache written to %s", cache_path)
        return _parse_players(raw)


def _parse_players(raw: dict) -> dict[str, NFLPlayer]:
    """Filter raw player dict to NFL skill positions only."""
    players: dict[str, NFLPlayer] = {}
    for pid, pdata in raw.items():
        if not isinstance(pdata, dict):
            continue
        if pdata.get("sport") != "nfl":
            continue
        if pdata.get("position") not in VALID_POSITIONS:
            continue
        try:
            players[pid] = NFLPlayer.model_validate({"player_id": pid, **pdata})
        except Exception:
            pass
    return players
