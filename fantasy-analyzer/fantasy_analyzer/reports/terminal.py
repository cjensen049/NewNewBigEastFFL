"""Rich-based terminal tables and panels for all reports."""

from __future__ import annotations

import sqlite3

from rich.console import Console
from rich.table import Table
from rich import box
from rich.text import Text
from rich.panel import Panel

from fantasy_analyzer.analysis.history import (
    AllTimeRecord,
    RegularSeasonRecord,
    PlayoffResult,
    get_all_time_standings,
    get_season_breakdown,
    get_available_seasons,
)

console = Console(width=120)

FINISH_LABELS = {
    1: "[bold gold1]Champion[/bold gold1]",
    2: "[bold]Runner-up[/bold]",
    3: "[green]3rd[/green]",
    4: "[green]4th[/green]",
    5: "5th",
    6: "6th",
    7: "7th",
    8: "8th",
    9: "9th",
    10: "10th",
    11: "11th",
    12: "[bold red]Last Place[/bold red]",
}


def _pct(v: float) -> str:
    return f"{v:.1%}"


def _pts(v: float) -> str:
    return f"{v:,.1f}"


def show_all_time_standings(con: sqlite3.Connection) -> None:
    """Render all-time standings table."""
    records = get_all_time_standings(con)

    table = Table(
        title="NNBE All-Time Standings",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Owner", style="bold", min_width=8)
    table.add_column("Seasons", justify="right", min_width=7)
    table.add_column("Reg W-L", justify="center", min_width=8)
    table.add_column("Win%", justify="right", min_width=5)
    table.add_column("Total Pts", justify="right", min_width=9)
    table.add_column("Pts/Gm", justify="right", min_width=6)
    table.add_column("Playoffs", justify="right", min_width=8)
    table.add_column("Titles", justify="center", min_width=6)
    table.add_column("Lasts", justify="center", min_width=5)

    for rank, r in enumerate(records, 1):
        titles = str(r.championships) if r.championships else "-"
        lasts = str(r.last_place_finishes) if r.last_place_finishes else "-"
        name = Text(r.canonical_name)
        if r.championships:
            name.stylize("gold1")

        table.add_row(
            str(rank),
            name,
            str(r.seasons),
            f"{r.reg_wins}-{r.reg_losses}" + (f"-{r.reg_ties}" if r.reg_ties else ""),
            _pct(r.win_pct),
            _pts(r.total_points),
            f"{r.ppg:.1f}",
            f"{r.playoff_appearances}/{r.seasons}",
            titles,
            lasts,
        )

    console.print()
    console.print(table)
    console.print()


def show_season_standings(con: sqlite3.Connection, season: int) -> None:
    """Render standings for a single season."""
    data = get_season_breakdown(con, season)
    if not data:
        console.print(f"[red]No data for season {season}[/red]")
        return

    reg: list[RegularSeasonRecord] = data["regular_season"]
    playoff_map: dict[str, PlayoffResult] = data["playoff"]

    table = Table(
        title=f"NNBE {season} Season",
        box=box.SIMPLE_HEAD,
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("Seed", justify="right", style="dim", width=4)
    table.add_column("Owner", style="bold")
    table.add_column("W-L", justify="center")
    table.add_column("Win%", justify="right")
    table.add_column("Pts For", justify="right")
    table.add_column("Pts Agnst", justify="right")
    table.add_column("PPG", justify="right")
    table.add_column("Finish", justify="left")

    for seed, rec in enumerate(reg, 1):
        pr = playoff_map.get(rec.user_id)
        finish_str = ""
        if pr and pr.finish is not None:
            finish_str = FINISH_LABELS.get(pr.finish, str(pr.finish))
        elif pr and pr.made_playoffs:
            finish_str = "Playoffs"

        row_style = ""
        if pr and pr.champion:
            row_style = "bold"

        table.add_row(
            str(seed),
            rec.canonical_name,
            f"{rec.wins}-{rec.losses}" + (f"-{rec.ties}" if rec.ties else ""),
            _pct(rec.win_pct),
            _pts(rec.points_for),
            _pts(rec.points_against),
            f"{rec.ppg:.1f}",
            finish_str,
            style=row_style,
        )

    console.print()
    console.print(table)
    console.print()


def show_all_seasons_summary(con: sqlite3.Connection) -> None:
    """Show champions and last-place finishers for every completed season."""
    from fantasy_analyzer.analysis.history import get_all_seasons, compute_playoff_results

    seasons = get_all_seasons(con)

    table = Table(
        title="NNBE Season-by-Season Results",
        box=box.SIMPLE_HEAD,
        padding=(0, 1),
    )
    table.add_column("Season", justify="right")
    table.add_column("Champion", style="gold1 bold")
    table.add_column("Runner-up", style="bright_white")
    table.add_column("3rd Place")
    table.add_column("Last Place", style="red")

    for s in seasons:
        results = compute_playoff_results(
            con, s["league_id"], s["season"],
            s["playoff_week_start"], s["last_week"]
        )
        finish_map: dict[int, str] = {}
        for r in results:
            if r.finish is not None:
                finish_map[r.finish] = r.canonical_name

        table.add_row(
            str(s["season"]),
            finish_map.get(1, "-"),
            finish_map.get(2, "-"),
            finish_map.get(3, "-"),
            finish_map.get(12, "-"),
        )

    console.print()
    console.print(table)
    console.print()
