"""Ingestion pipeline — pulls all Sleeper data and writes to SQLite."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from fantasy_analyzer.api.sleeper import SleeperClient
from fantasy_analyzer.db.schema import init_db
from fantasy_analyzer.db import store

log = logging.getLogger(__name__)
console = Console()


async def run_ingest(
    cfg: dict,
    single_league_id: str | None = None,
    skip_players: bool = False,
) -> None:
    """Top-level ingestion entry point."""
    settings = cfg.get("settings", {})
    db_path = settings.get("db_path", "data/league.db")
    player_cache = settings.get("player_cache_path", "data/players.json")
    ttl_days = settings.get("player_cache_ttl_days", 7)
    api_delay = settings.get("api_delay_seconds", 0.5)
    owners_cfg = cfg.get("owners", [])
    leagues_cfg = cfg.get("leagues", [])

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    console.print("[bold cyan]Initializing database...[/bold cyan]")
    await init_db(db_path)

    client = SleeperClient(delay=api_delay)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        # Write canonical owners from config
        await store.upsert_owners(db, owners_cfg)
        await db.commit()
        console.print(f"[green]Owners registered:[/green] {len(owners_cfg)}")

        # Resolve which leagues to ingest
        if single_league_id:
            target_ids = {single_league_id}
        else:
            target_ids = {l["id"] for l in leagues_cfg}

        # Player cache (shared across all seasons)
        players = {}
        if not skip_players:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Fetching player metadata...", total=None)
                players = await client.get_players(Path(player_cache), ttl_days)
            console.print(f"[green]Players loaded:[/green] {len(players):,}")
            await store.upsert_players(db, players)
            await db.commit()

        # Ingest each league
        for league_cfg in sorted(leagues_cfg, key=lambda l: l["season"]):
            lid = league_cfg["id"]
            if lid not in target_ids:
                continue
            await _ingest_league(db, client, lid, players, console)

    console.print("\n[bold green]Ingestion complete.[/bold green]")


async def _ingest_league(
    db: aiosqlite.Connection,
    client: SleeperClient,
    league_id: str,
    players: dict,
    console: Console,
) -> None:
    """Ingest a single league — metadata, rosters, matchups, transactions, drafts."""
    console.rule(f"[bold]League {league_id}[/bold]")

    # --- League metadata ---
    league = await client.get_league(league_id)
    await store.upsert_league(db, league)
    await db.commit()
    console.print(f"  [cyan]Season:[/cyan] {league.season}  [cyan]Name:[/cyan] {league.name}")

    # --- Users + Rosters ---
    users = await client.get_users(league_id)
    rosters = await client.get_rosters(league_id)
    await store.upsert_league_owners(db, league_id, rosters, users)
    await store.upsert_season_records(db, league, rosters)
    await db.commit()

    roster_to_user = await store.build_roster_to_user(db, league_id)
    console.print(f"  [cyan]Owners ingested:[/cyan] {len(users)}")

    # --- Matchups ---
    playoff_start = league.settings.playoff_week_start
    last_week = league.settings.last_scored_leg or (playoff_start + 3)

    console.print(f"  Fetching matchups weeks 1–{last_week}...")
    matchup_count = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("  [progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Matchups", total=last_week)
        for week in range(1, last_week + 1):
            matchups = await client.get_matchups(league_id, week)
            if matchups:
                await store.upsert_matchups(
                    db, league, week, matchups, roster_to_user, playoff_start
                )
                await db.commit()
                matchup_count += len(matchups)
            progress.advance(task)

    console.print(f"  [cyan]Matchup slots stored:[/cyan] {matchup_count}")

    # --- Transactions ---
    console.print(f"  Fetching transactions weeks 1–{last_week}...")
    all_txns = []
    with Progress(
        SpinnerColumn(),
        TextColumn("  [progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Transactions", total=last_week)
        for week in range(1, last_week + 1):
            txns = await client.get_transactions(league_id, week)
            all_txns.extend(txns)
            progress.advance(task)

    await store.upsert_transactions(db, league, all_txns)
    await db.commit()
    trades = sum(1 for t in all_txns if t.type == "trade")
    console.print(f"  [cyan]Transactions stored:[/cyan] {len(all_txns)} ({trades} trades)")

    # --- Drafts ---
    drafts = await client.get_drafts(league_id)
    for draft in drafts:
        await store.upsert_draft(db, draft)
        await db.commit()
        if draft.status == "complete":
            picks = await client.get_draft_picks(draft.draft_id)
            await store.upsert_draft_picks(
                    db,
                    league_id,
                    int(league.season),
                    picks,
                    roster_to_user,
                    players,
                )
            await db.commit()
            console.print(f"  [cyan]Draft picks stored:[/cyan] {len(picks)} (draft {draft.draft_id})")
        else:
            console.print(f"  [yellow]Draft {draft.draft_id} status:[/yellow] {draft.status} — skipping picks")
