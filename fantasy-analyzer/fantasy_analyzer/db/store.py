"""CRUD helpers — all writes use transactions, operations are idempotent."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

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

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Owners
# ---------------------------------------------------------------------------

async def upsert_owners(db: aiosqlite.Connection, owners_cfg: list[dict]) -> None:
    """Write canonical owner records from config."""
    await db.executemany(
        """
        INSERT INTO owners (user_id, canonical_name, sleeper_username)
        VALUES (:user_id, :canonical_name, :sleeper_username)
        ON CONFLICT(user_id) DO UPDATE SET
            canonical_name   = excluded.canonical_name,
            sleeper_username = excluded.sleeper_username
        """,
        [
            {
                "user_id": o["user_id"],
                "canonical_name": o["canonical_name"],
                "sleeper_username": o.get("sleeper_username"),
            }
            for o in owners_cfg
        ],
    )


# ---------------------------------------------------------------------------
# Leagues
# ---------------------------------------------------------------------------

async def upsert_league(db: aiosqlite.Connection, league: League) -> None:
    """Write league metadata."""
    await db.execute(
        """
        INSERT INTO leagues
            (league_id, season, name, status, total_rosters, playoff_week_start, last_scored_leg)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id) DO UPDATE SET
            status             = excluded.status,
            last_scored_leg    = excluded.last_scored_leg
        """,
        (
            league.league_id,
            int(league.season),
            league.name,
            league.status,
            league.total_rosters,
            league.settings.playoff_week_start,
            league.settings.last_scored_leg,
        ),
    )


# ---------------------------------------------------------------------------
# League owners (roster_id ↔ user_id mapping per season)
# ---------------------------------------------------------------------------

async def upsert_league_owners(
    db: aiosqlite.Connection,
    league_id: str,
    rosters: list[Roster],
    users: list[User],
) -> None:
    """Map roster_id → user_id for a league and store team names."""
    user_map = {u.user_id: u for u in users}
    roster_map = {r.roster_id: r for r in rosters}

    rows = []
    for roster in rosters:
        if not roster.owner_id:
            continue
        user = user_map.get(roster.owner_id)
        team_name = user.metadata.team_name if user else None
        rows.append((league_id, roster.owner_id, roster.roster_id, team_name))

    await db.executemany(
        """
        INSERT INTO league_owners (league_id, user_id, roster_id, team_name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(league_id, user_id) DO UPDATE SET
            roster_id = excluded.roster_id,
            team_name = excluded.team_name
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# Season records (from final roster standings)
# ---------------------------------------------------------------------------

async def upsert_season_records(
    db: aiosqlite.Connection,
    league: League,
    rosters: list[Roster],
) -> None:
    """Write end-of-season win/loss/points records from roster settings."""
    rows = []
    for r in rosters:
        if not r.owner_id:
            continue
        rows.append((
            league.league_id,
            r.owner_id,
            int(league.season),
            r.wins,
            r.losses,
            r.ties,
            r.fpts,
            r.fpts_against,
        ))

    await db.executemany(
        """
        INSERT INTO season_records
            (league_id, user_id, season, wins, losses, ties, fpts, fpts_against)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id, user_id) DO UPDATE SET
            wins         = excluded.wins,
            losses       = excluded.losses,
            ties         = excluded.ties,
            fpts         = excluded.fpts,
            fpts_against = excluded.fpts_against
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# Matchups
# ---------------------------------------------------------------------------

async def upsert_matchups(
    db: aiosqlite.Connection,
    league: League,
    week: int,
    matchups: list[Matchup],
    roster_to_user: dict[int, str],
    playoff_week_start: int,
) -> None:
    """Write matchup rows for one week."""
    is_playoff = 1 if week >= playoff_week_start else 0
    rows = []
    for m in matchups:
        if m.matchup_id is None:
            continue
        rows.append((
            league.league_id,
            int(league.season),
            week,
            m.matchup_id,
            m.roster_id,
            roster_to_user.get(m.roster_id),
            m.points,
            is_playoff,
            json.dumps(m.starters) if m.starters else None,
            json.dumps(m.players_points) if m.players_points else None,
        ))

    await db.executemany(
        """
        INSERT INTO matchups
            (league_id, season, week, matchup_id, roster_id, user_id, points, is_playoff,
             starters_json, players_points_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(league_id, week, roster_id) DO UPDATE SET
            points              = excluded.points,
            matchup_id          = excluded.matchup_id,
            user_id             = excluded.user_id,
            starters_json       = COALESCE(excluded.starters_json, starters_json),
            players_points_json = COALESCE(excluded.players_points_json, players_points_json)
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

async def upsert_transactions(
    db: aiosqlite.Connection,
    league: League,
    transactions: list[Transaction],
) -> None:
    """Write transaction and associated draft pick rows."""
    txn_rows = []
    pick_rows = []

    for t in transactions:
        txn_rows.append((
            t.transaction_id,
            league.league_id,
            int(league.season),
            t.leg,
            t.type,
            t.status,
            t.created,
            json.dumps(t.adds) if t.adds else None,
            json.dumps(t.drops) if t.drops else None,
            json.dumps(t.roster_ids),
            json.dumps(t.waiver_budget) if t.waiver_budget else None,
            t.settings.get("waiver_bid") if t.settings else None,
        ))

        for pick in t.draft_picks:
            # Use Sleeper's own direction fields: owner_id = receiver, previous_owner_id = sender.
            # If previous_owner_id is absent (pick going out for the first time), infer the
            # sender as whichever trade partner is not the receiver.
            to_rid = pick.owner_id
            if pick.previous_owner_id:
                from_rid = pick.previous_owner_id
            else:
                others = [r for r in t.roster_ids if r != to_rid]
                from_rid = others[0] if others else 0
            pick_rows.append((
                t.transaction_id,
                pick.season,
                pick.round,
                pick.roster_id,
                from_rid,
                to_rid,
            ))

    await db.executemany(
        """
        INSERT INTO transactions
            (transaction_id, league_id, season, week, type, status,
             created_epoch, adds_json, drops_json, roster_ids_json,
             waiver_budget_json, waiver_bid_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(transaction_id) DO UPDATE SET
            status            = excluded.status,
            waiver_bid_amount = COALESCE(excluded.waiver_bid_amount, waiver_bid_amount)
        """,
        txn_rows,
    )

    if pick_rows:
        await db.executemany(
            """
            INSERT OR IGNORE INTO transaction_draft_picks
                (transaction_id, season, round, original_roster_id, from_roster_id, to_roster_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            pick_rows,
        )


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

async def upsert_draft(db: aiosqlite.Connection, draft: Draft) -> None:
    """Write draft metadata."""
    await db.execute(
        """
        INSERT INTO drafts (draft_id, league_id, season, type, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(draft_id) DO UPDATE SET status = excluded.status
        """,
        (draft.draft_id, draft.league_id, int(draft.season), draft.type, draft.status),
    )


async def upsert_draft_picks(
    db: aiosqlite.Connection,
    league_id: str,
    season: int,
    picks: list[DraftSlot],
    roster_to_user: dict[int, str],
    players: dict[str, NFLPlayer],
) -> None:
    """Write draft pick rows."""
    rows = []
    for p in picks:
        player = players.get(p.player_id or "") if p.player_id else None
        user_id = roster_to_user.get(p.roster_id or 0) if p.roster_id else None
        # picked_by is a user_id on the draft slot itself
        if p.picked_by and not user_id:
            user_id = p.picked_by
        rows.append((
            p.draft_id,
            league_id,
            season,
            p.round,
            p.pick_no,
            p.roster_id,
            user_id,
            p.player_id,
            player.full_name if player else None,
            p.draft_slot,
        ))

    await db.executemany(
        """
        INSERT INTO draft_picks
            (draft_id, league_id, season, round, pick_no, roster_id, user_id, player_id, player_name, draft_slot)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(draft_id, pick_no) DO UPDATE SET
            player_id   = COALESCE(excluded.player_id, player_id),
            player_name = COALESCE(excluded.player_name, player_name),
            user_id     = COALESCE(excluded.user_id, user_id),
            draft_slot  = COALESCE(excluded.draft_slot, draft_slot)
        """,
        rows,
    )


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

async def upsert_players(
    db: aiosqlite.Connection,
    players: dict[str, NFLPlayer],
) -> None:
    """Write NFL player metadata."""
    await db.executemany(
        """
        INSERT INTO players (player_id, full_name, position, team)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            full_name = excluded.full_name,
            position  = excluded.position,
            team      = excluded.team
        """,
        [(p.player_id, p.full_name, p.position, p.team) for p in players.values()],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def build_roster_to_user(
    db: aiosqlite.Connection, league_id: str
) -> dict[int, str]:
    """Return {roster_id: user_id} for a league from the DB."""
    async with db.execute(
        "SELECT roster_id, user_id FROM league_owners WHERE league_id = ?", (league_id,)
    ) as cur:
        return {row[0]: row[1] async for row in cur}
