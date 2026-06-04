"""CLI entry point — argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from fantasy_analyzer.ingest import run_ingest


def load_config(path: str = "config.yaml") -> dict:
    """Load and return the YAML config."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fantasy-analyzer",
        description="NNBE Fantasy Football historical analyzer",
    )
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--log-level", default=None, help="Override log level (DEBUG, INFO, WARNING)")

    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    ingest_p = sub.add_parser("ingest", help="Pull data from Sleeper and store locally")
    ingest_p.add_argument("--league-id", default=None, help="Ingest a single league ID only")
    ingest_p.add_argument("--skip-players", action="store_true", help="Skip refreshing the player cache")

    # scrape-projections
    scrape_p = sub.add_parser(
        "scrape-projections",
        help="Scrape FantasyPros weekly projections and refresh Sleeper rosters",
    )
    scrape_p.add_argument("--season", type=int, default=None, help="Season year (default: auto-detect)")
    scrape_p.add_argument("--week",   type=int, default=None, help="NFL week to scrape (default: auto-detect)")

    # scrape-dynasty
    sub.add_parser(
        "scrape-dynasty",
        help="Fetch DynastyProcess player + pick values and refresh Sleeper rosters",
    )

    # scrape-dynasty-sources
    dynasty_src_p = sub.add_parser(
        "scrape-dynasty-sources",
        help="Fetch KTC, FantasyCalc, and Dynasty Daddy roster values concurrently",
    )
    dynasty_src_p.add_argument("--season", type=int, default=None, help="Season year (default: most recent)")

    # report
    report_p = sub.add_parser("report", help="Show analysis reports")
    report_sub = report_p.add_subparsers(dest="report_type", required=True)

    standings_p = report_sub.add_parser("standings", help="All-time or single-season standings")
    standings_p.add_argument("--season", type=int, default=None, help="Show a specific season (default: all-time)")
    standings_p.add_argument("--all-seasons", action="store_true", help="Show champion/last-place for each season")

    args = parser.parse_args()
    cfg = load_config(args.config)

    log_level = args.log_level or cfg.get("settings", {}).get("log_level", "INFO")
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    # Suppress httpx info noise for report commands
    if args.command == "report":
        logging.getLogger("httpx").setLevel(logging.WARNING)

    db_path = cfg.get("settings", {}).get("db_path", "data/league.db")

    if args.command == "ingest":
        asyncio.run(
            run_ingest(
                cfg=cfg,
                single_league_id=args.league_id,
                skip_players=args.skip_players,
            )
        )

    elif args.command == "scrape-projections":
        _run_scrape_projections(args, db_path)

    elif args.command == "scrape-dynasty":
        _run_scrape_dynasty(db_path, cfg)

    elif args.command == "scrape-dynasty-sources":
        _run_scrape_dynasty_sources(args, db_path, cfg)

    elif args.command == "report":
        con = sqlite3.connect(db_path)
        try:
            _run_report(args, con)
        finally:
            con.close()


def _run_scrape_projections(args: argparse.Namespace, db_path: str) -> None:
    """Refresh current rosters from Sleeper and scrape FantasyPros projections."""
    from fantasy_analyzer.scraping.fantasypros import run_projections_scrape, update_current_rosters

    con = sqlite3.connect(db_path)
    try:
        # Auto-detect season: prefer in_season, fall back to most recent
        season = args.season
        if not season:
            row = con.execute(
                "SELECT season FROM leagues WHERE status IN ('in_season','drafting') ORDER BY season DESC LIMIT 1"
            ).fetchone()
            if row:
                season = row[0]
            else:
                row = con.execute("SELECT MAX(season) FROM leagues").fetchone()
                season = row[0] if row and row[0] else datetime.now(timezone.utc).year

        # Auto-detect week: next week after the last completed week
        week = args.week
        if not week:
            row = con.execute(
                "SELECT MAX(week) FROM matchups WHERE season=? AND points IS NOT NULL AND points > 0",
                (season,),
            ).fetchone()
            week = (row[0] or 0) + 1

        # Get league_id for this season
        row = con.execute(
            "SELECT league_id FROM leagues WHERE season = ? ORDER BY rowid DESC LIMIT 1",
            (season,),
        ).fetchone()
        if not row:
            print(f"No league found for season {season}", file=sys.stderr)
            sys.exit(1)
        league_id = row[0]

        print(f"Season {season} — refreshing rosters and scraping week {week} projections")

        roster_count = update_current_rosters(con, league_id)
        print(f"  Rosters: {roster_count} player-roster entries updated")

        proj_count = run_projections_scrape(con, season, week)
        print(f"  Projections: {proj_count} players stored for week {week}")
    finally:
        con.close()


def _run_scrape_dynasty(db_path: str, cfg: dict) -> None:
    """Fetch DynastyProcess values and refresh Sleeper rosters."""
    from fantasy_analyzer.scraping.dynastyprocess import run_dynasty_scrape
    from fantasy_analyzer.scraping.fantasypros import update_current_rosters

    con = sqlite3.connect(db_path)
    try:
        # Get the active/most recent league_id to refresh rosters
        row = con.execute(
            "SELECT league_id FROM leagues ORDER BY season DESC LIMIT 1"
        ).fetchone()
        if row:
            roster_count = update_current_rosters(con, row[0])
            print(f"  Rosters: {roster_count} player-roster entries updated")

        players_stored, picks_stored = run_dynasty_scrape(con)
        print(f"  Dynasty values: {players_stored} players, {picks_stored} picks stored")
    finally:
        con.close()


def _run_scrape_dynasty_sources(args: argparse.Namespace, db_path: str, cfg: dict) -> None:
    """Fetch KTC, FantasyCalc, and Dynasty Daddy roster values concurrently."""
    from fantasy_analyzer.rankings.dynasty_sources import fetch_all_sources

    con = sqlite3.connect(db_path)
    try:
        season = getattr(args, "season", None)
        if not season:
            row = con.execute("SELECT MAX(season) FROM leagues").fetchone()
            season = row[0] if row and row[0] else datetime.now(timezone.utc).year

        row = con.execute(
            "SELECT league_id FROM leagues WHERE season = ? ORDER BY rowid DESC LIMIT 1",
            (season,),
        ).fetchone()
        if not row:
            print(f"No league found for season {season}", file=sys.stderr)
            sys.exit(1)
        league_id = row[0]
    finally:
        con.close()

    players_cache = cfg.get("settings", {}).get("player_cache_path", "data/players.json")
    print(f"Fetching dynasty sources for season {season} (league {league_id})…")

    results = asyncio.run(
        fetch_all_sources(
            league_id=league_id,
            season=season,
            db_path=db_path,
            players_cache_path=players_cache,
        )
    )

    if not results:
        print("All sources failed — check errors.md for details", file=sys.stderr)
        sys.exit(1)

    for r in results:
        print(f"\n  [{r['source']}] fetched at {r['fetched_at']}")
        ranked = sorted(r["owner_ranks"].items(), key=lambda x: x[1])
        con2 = sqlite3.connect(db_path)
        try:
            name_map = dict(con2.execute("SELECT user_id, canonical_name FROM owners").fetchall())
        finally:
            con2.close()
        for uid, rank in ranked:
            name = name_map.get(uid, uid)
            value = r["owner_values"].get(uid, 0)
            print(f"    {rank:2}. {name:<12} {value:,.0f}")


def _run_report(args: argparse.Namespace, con: sqlite3.Connection) -> None:
    """Dispatch to the appropriate report function."""
    from fantasy_analyzer.reports.terminal import (
        show_all_time_standings,
        show_season_standings,
        show_all_seasons_summary,
    )
    from fantasy_analyzer.analysis.history import get_available_seasons

    if args.report_type == "standings":
        if args.all_seasons:
            show_all_seasons_summary(con)
        elif args.season is not None:
            available = get_available_seasons(con)
            if args.season not in available:
                print(f"No data for season {args.season}. Available: {available}")
                sys.exit(1)
            show_season_standings(con, args.season)
        else:
            show_all_time_standings(con)


if __name__ == "__main__":
    main()
