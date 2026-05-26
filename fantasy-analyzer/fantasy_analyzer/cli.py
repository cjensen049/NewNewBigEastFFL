"""CLI entry point — argument parsing and command dispatch."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sqlite3
import sys
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

    elif args.command == "report":
        con = sqlite3.connect(db_path)
        try:
            _run_report(args, con)
        finally:
            con.close()


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
