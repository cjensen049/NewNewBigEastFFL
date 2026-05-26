"""Season records, standings, and playoff result analysis."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


@dataclass
class RegularSeasonRecord:
    user_id: str
    canonical_name: str
    season: int
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float = 0.0
    points_against: float = 0.0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.ties

    @property
    def win_pct(self) -> float:
        return (self.wins + 0.5 * self.ties) / self.games if self.games else 0.0

    @property
    def ppg(self) -> float:
        return self.points_for / self.games if self.games else 0.0


@dataclass
class PlayoffResult:
    user_id: str
    canonical_name: str
    season: int
    made_playoffs: bool = False
    finish: int | None = None   # 1=champion, 2=runner-up, ... 12=last
    champion: bool = False
    last_place: bool = False


@dataclass
class AllTimeRecord:
    user_id: str
    canonical_name: str
    seasons: int = 0
    reg_wins: int = 0
    reg_losses: int = 0
    reg_ties: int = 0
    total_points: float = 0.0
    total_points_against: float = 0.0
    total_games: int = 0
    playoff_appearances: int = 0
    championships: int = 0
    last_place_finishes: int = 0
    best_finish: int | None = None
    worst_finish: int | None = None

    @property
    def win_pct(self) -> float:
        return (self.reg_wins + 0.5 * self.reg_ties) / self.total_games if self.total_games else 0.0

    @property
    def ppg(self) -> float:
        return self.total_points / self.total_games if self.total_games else 0.0


def compute_regular_season_records(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
    playoff_week_start: int,
) -> list[RegularSeasonRecord]:
    """Compute W/L/T and points from weekly matchup results for the regular season only."""
    cur = con.cursor()

    # Fetch all regular season matchup rows
    rows = cur.execute(
        """
        SELECT m.week, m.matchup_id, m.user_id, m.points, o.canonical_name
        FROM matchups m
        JOIN owners o ON m.user_id = o.user_id
        WHERE m.league_id = ? AND m.week < ?
        ORDER BY m.week, m.matchup_id
        """,
        (league_id, playoff_week_start),
    ).fetchall()

    # Group into matchups: (week, matchup_id) -> list of (user_id, points, name)
    from collections import defaultdict
    matchup_groups: dict[tuple, list] = defaultdict(list)
    for week, mid, uid, pts, name in rows:
        matchup_groups[(week, mid)].append((uid, pts or 0.0, name))

    # Accumulate per-owner records
    records: dict[str, RegularSeasonRecord] = {}

    for (week, mid), teams in matchup_groups.items():
        if len(teams) != 2:
            continue
        (uid_a, pts_a, name_a), (uid_b, pts_b, name_b) = teams

        if uid_a not in records:
            records[uid_a] = RegularSeasonRecord(uid_a, name_a, season)
        if uid_b not in records:
            records[uid_b] = RegularSeasonRecord(uid_b, name_b, season)

        rec_a, rec_b = records[uid_a], records[uid_b]
        rec_a.points_for += pts_a
        rec_a.points_against += pts_b
        rec_b.points_for += pts_b
        rec_b.points_against += pts_a

        if pts_a > pts_b:
            rec_a.wins += 1
            rec_b.losses += 1
        elif pts_b > pts_a:
            rec_b.wins += 1
            rec_a.losses += 1
        else:
            rec_a.ties += 1
            rec_b.ties += 1

    return sorted(records.values(), key=lambda r: (-r.win_pct, -r.points_for))


def compute_playoff_results(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
    playoff_week_start: int,
    last_week: int,
) -> list[PlayoffResult]:
    """
    Determine playoff finishes from matchup data.

    Bracket structure (12-team, consistent across all NNBE seasons):
    - matchup_id <= 3: championship bracket (top 6 seeds = "made playoffs")
    - matchup_id >= 4: toilet bowl bracket (bottom 6 seeds)
    - Champion: winner of matchup_id=1 in the final week
    - Last place: loser of the highest matchup_id in the final week
    """
    cur = con.cursor()

    rows = cur.execute(
        """
        SELECT m.week, m.matchup_id, m.user_id, m.points, o.canonical_name
        FROM matchups m
        JOIN owners o ON m.user_id = o.user_id
        WHERE m.league_id = ? AND m.week >= ?
        ORDER BY m.week, m.matchup_id
        """,
        (league_id, playoff_week_start),
    ).fetchall()

    from collections import defaultdict
    # Track which bracket each owner appeared in
    owner_info: dict[str, str] = {}  # user_id -> canonical_name
    owner_min_matchup_id: dict[str, int] = {}  # lowest matchup_id seen (determines bracket)

    matchup_groups: dict[tuple, list] = defaultdict(list)
    for week, mid, uid, pts, name in rows:
        matchup_groups[(week, mid)].append((uid, pts or 0.0))
        owner_info[uid] = name
        if uid not in owner_min_matchup_id or mid < owner_min_matchup_id[uid]:
            owner_min_matchup_id[uid] = mid

    results: dict[str, PlayoffResult] = {
        uid: PlayoffResult(
            user_id=uid,
            canonical_name=name,
            season=season,
            made_playoffs=(owner_min_matchup_id.get(uid, 99) <= 3),
        )
        for uid, name in owner_info.items()
    }

    # Final week results determine champion and last place
    final_week_matchups = {
        mid: teams
        for (week, mid), teams in matchup_groups.items()
        if week == last_week
    }

    if 1 in final_week_matchups and len(final_week_matchups[1]) == 2:
        teams = sorted(final_week_matchups[1], key=lambda x: -x[1])
        champion_id, runner_up_id = teams[0][0], teams[1][0]
        results[champion_id].finish = 1
        results[champion_id].champion = True
        results[runner_up_id].finish = 2

    if 2 in final_week_matchups and len(final_week_matchups[2]) == 2:
        teams = sorted(final_week_matchups[2], key=lambda x: -x[1])
        results[teams[0][0]].finish = 3
        results[teams[1][0]].finish = 4

    # 5th/6th: matchup_id=3 only appears in the middle playoff week
    middle_week = playoff_week_start + 1
    mid3_key = (middle_week, 3)
    if mid3_key in matchup_groups and len(matchup_groups[mid3_key]) == 2:
        teams = sorted(matchup_groups[mid3_key], key=lambda x: -x[1])
        results[teams[0][0]].finish = 5
        results[teams[1][0]].finish = 6

    # 7th/8th: matchup_id=4 in final week (toilet bowl bracket winners side)
    if 4 in final_week_matchups and len(final_week_matchups[4]) == 2:
        teams = sorted(final_week_matchups[4], key=lambda x: -x[1])
        results[teams[0][0]].finish = 7
        results[teams[1][0]].finish = 8

    # 9th/10th: matchup_id=6 only appears in middle week (toilet bowl consolation)
    mid6_key = (middle_week, 6)
    if mid6_key in matchup_groups and len(matchup_groups[mid6_key]) == 2:
        teams = sorted(matchup_groups[mid6_key], key=lambda x: -x[1])
        results[teams[0][0]].finish = 9
        results[teams[1][0]].finish = 10

    # 11th/12th: highest matchup_id in final week (last place game)
    max_mid = max(final_week_matchups.keys()) if final_week_matchups else None
    if max_mid and max_mid >= 4 and len(final_week_matchups[max_mid]) == 2:
        teams = sorted(final_week_matchups[max_mid], key=lambda x: -x[1])
        results[teams[0][0]].finish = 11
        last_place_id = teams[1][0]
        results[last_place_id].finish = 12
        results[last_place_id].last_place = True

    return list(results.values())


def get_all_seasons(con: sqlite3.Connection) -> list[dict]:
    """Return all complete seasons with their settings."""
    return [
        {"league_id": r[0], "season": r[1], "playoff_week_start": r[2], "last_week": r[3]}
        for r in con.execute(
            """
            SELECT league_id, season, playoff_week_start,
                   COALESCE(last_scored_leg, playoff_week_start + 2) as last_week
            FROM leagues
            WHERE status = 'complete'
            ORDER BY season
            """
        ).fetchall()
    ]


def get_all_time_standings(con: sqlite3.Connection) -> list[AllTimeRecord]:
    """Compute cumulative all-time standings across all complete seasons."""
    seasons = get_all_seasons(con)
    all_records: dict[str, AllTimeRecord] = {}

    for s in seasons:
        reg_records = compute_regular_season_records(
            con, s["league_id"], s["season"], s["playoff_week_start"]
        )
        playoff_results = compute_playoff_results(
            con, s["league_id"], s["season"],
            s["playoff_week_start"], s["last_week"]
        )
        playoff_map = {p.user_id: p for p in playoff_results}

        for rec in reg_records:
            if rec.user_id not in all_records:
                all_records[rec.user_id] = AllTimeRecord(rec.user_id, rec.canonical_name)
            at = all_records[rec.user_id]
            at.seasons += 1
            at.reg_wins += rec.wins
            at.reg_losses += rec.losses
            at.reg_ties += rec.ties
            at.total_points += rec.points_for
            at.total_points_against += rec.points_against
            at.total_games += rec.games

            pr = playoff_map.get(rec.user_id)
            if pr:
                if pr.made_playoffs:
                    at.playoff_appearances += 1
                if pr.champion:
                    at.championships += 1
                if pr.last_place:
                    at.last_place_finishes += 1
                if pr.finish is not None:
                    if at.best_finish is None or pr.finish < at.best_finish:
                        at.best_finish = pr.finish
                    if at.worst_finish is None or pr.finish > at.worst_finish:
                        at.worst_finish = pr.finish

    return sorted(
        all_records.values(),
        key=lambda r: (-r.win_pct, -r.ppg),
    )


def get_season_breakdown(con: sqlite3.Connection, season: int) -> dict:
    """Return regular season records and playoff results for one season."""
    row = con.execute(
        """
        SELECT league_id, playoff_week_start,
               COALESCE(last_scored_leg, playoff_week_start + 2)
        FROM leagues WHERE season = ?
        """,
        (season,),
    ).fetchone()
    if not row:
        return {}
    league_id, pws, last_week = row

    reg = compute_regular_season_records(con, league_id, season, pws)
    playoff = compute_playoff_results(con, league_id, season, pws, last_week)
    playoff_map = {p.user_id: p for p in playoff}

    return {
        "season": season,
        "regular_season": reg,
        "playoff": playoff_map,
    }


def get_available_seasons(con: sqlite3.Connection) -> list[int]:
    """Return list of seasons that have matchup data."""
    return [
        r[0] for r in con.execute(
            "SELECT DISTINCT season FROM matchups ORDER BY season"
        ).fetchall()
    ]
