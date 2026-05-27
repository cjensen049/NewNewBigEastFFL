"""Season records, standings, and playoff result analysis."""

from __future__ import annotations

import json
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
                # Only track best/worst finish for championship bracket (1–6)
                if pr.finish is not None and pr.finish <= 6:
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


# ---------------------------------------------------------------------------
# Standings history grid
# ---------------------------------------------------------------------------

def get_standings_history(con: sqlite3.Connection) -> dict[int, dict[int, str]]:
    """Return {season: {finish_rank: owner_name}} for all complete seasons.

    Ranks 1–6 come from the championship bracket playoff results.
    Ranks 7–12 come from regular-season seeding (toilet bowl is ignored).
    """
    seasons = get_all_seasons(con)
    history: dict[int, dict[int, str]] = {}
    for s in seasons:
        reg = compute_regular_season_records(
            con, s["league_id"], s["season"], s["playoff_week_start"]
        )
        playoff = compute_playoff_results(
            con, s["league_id"], s["season"],
            s["playoff_week_start"], s["last_week"]
        )

        rank_to_name: dict[int, str] = {}
        # Championship bracket finishes (1–6)
        for pr in playoff:
            if pr.made_playoffs and pr.finish is not None and pr.finish <= 6:
                rank_to_name[pr.finish] = pr.canonical_name

        # Non-playoff teams ranked by regular-season record (7th–12th)
        playoff_names = {pr.canonical_name for pr in playoff if pr.made_playoffs}
        non_playoff = [r for r in reg if r.canonical_name not in playoff_names]
        for i, r in enumerate(non_playoff):
            rank_to_name[7 + i] = r.canonical_name

        history[s["season"]] = rank_to_name
    return history


# ---------------------------------------------------------------------------
# Weekly scoring extremes
# ---------------------------------------------------------------------------

def get_weekly_scoring_extremes(
    con: sqlite3.Connection, top_n: int = 10
) -> dict:
    """Return top/bottom weekly scores and high/low score week counts per owner."""
    rows = con.execute(
        """
        SELECT m.season, m.week, o.canonical_name, m.points
        FROM matchups m
        JOIN owners o ON m.user_id = o.user_id
        WHERE m.is_playoff = 0 AND m.points IS NOT NULL AND m.points > 0
        ORDER BY m.points DESC
        """
    ).fetchall()

    top = [{"Rank": i + 1, "Owner": r[2], "Score": r[3], "Season": r[0], "Week": r[1]}
           for i, r in enumerate(rows[:top_n])]
    bottom = [{"Rank": i + 1, "Owner": r[2], "Score": r[3], "Season": r[0], "Week": r[1]}
              for i, r in enumerate(reversed(rows[-top_n:]))]

    # High/low score of the week counts
    week_scores: dict[tuple, list] = {}
    for season, week, name, pts in rows:
        week_scores.setdefault((season, week), []).append((name, pts))

    high_counts: dict[str, int] = {}
    low_counts: dict[str, int] = {}
    for (season, week), team_scores in week_scores.items():
        if not team_scores:
            continue
        max_pts = max(p for _, p in team_scores)
        min_pts = min(p for _, p in team_scores)
        for name, pts in team_scores:
            if pts == max_pts:
                high_counts[name] = high_counts.get(name, 0) + 1
            if pts == min_pts:
                low_counts[name] = low_counts.get(name, 0) + 1

    return {"top": top, "bottom": bottom, "high_counts": high_counts, "low_counts": low_counts}


# ---------------------------------------------------------------------------
# League records
# ---------------------------------------------------------------------------

def _compute_win_loss_streaks(con: sqlite3.Connection) -> dict[str, dict[str, int]]:
    """Compute max win and loss streaks per owner across all regular-season weeks."""
    rows = con.execute(
        """
        SELECT m1.season, m1.week, m1.user_id,
               CASE WHEN m1.points > m2.points THEN 1 ELSE 0 END as won
        FROM matchups m1
        JOIN matchups m2
          ON m1.league_id = m2.league_id
         AND m1.week      = m2.week
         AND m1.matchup_id = m2.matchup_id
         AND m1.user_id   != m2.user_id
        WHERE m1.is_playoff = 0
          AND m1.points IS NOT NULL
          AND m2.points IS NOT NULL
        ORDER BY m1.season, m1.week
        """
    ).fetchall()

    results_by_owner: dict[str, list[int]] = {}
    for _, _, uid, won in rows:
        results_by_owner.setdefault(uid, []).append(won)

    streaks: dict[str, dict[str, int]] = {}
    for uid, outcomes in results_by_owner.items():
        max_win = max_loss = cur_win = cur_loss = 0
        for won in outcomes:
            if won:
                cur_win += 1
                cur_loss = 0
            else:
                cur_loss += 1
                cur_win = 0
            max_win = max(max_win, cur_win)
            max_loss = max(max_loss, cur_loss)
        streaks[uid] = {"max_win": max_win, "max_loss": max_loss}
    return streaks


def get_league_records(con: sqlite3.Connection, include_playoffs: bool = False) -> list[dict]:
    """Return notable league records as a list of {Category, Holder, Value, Season}."""
    owner_names = {r[0]: r[1] for r in con.execute("SELECT user_id, canonical_name FROM owners")}
    records = []

    def _add(category: str, holder: str, value: str, season: str) -> None:
        records.append({"Category": category, "Holder": holder, "Value": value, "Season": season})

    def _q1(sql: str, params: tuple = ()) -> tuple | None:
        return con.execute(sql, params).fetchone()

    # Single-season win/loss records (use season_records from Sleeper roster endpoint)
    r = _q1("SELECT o.canonical_name, sr.wins, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id ORDER BY sr.wins DESC LIMIT 1")
    if r: _add("Most Wins, Single Season", r[0], str(r[1]), str(r[2]))

    r = _q1("SELECT o.canonical_name, sr.losses, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id ORDER BY sr.losses DESC LIMIT 1")
    if r: _add("Most Losses, Single Season", r[0], str(r[1]), str(r[2]))

    # All-time regular season
    r = _q1("SELECT o.canonical_name, SUM(sr.wins) as w FROM season_records sr JOIN owners o ON sr.user_id=o.user_id GROUP BY sr.user_id ORDER BY w DESC LIMIT 1")
    if r: _add("Most Wins, All-Time", r[0], str(int(r[1])), "All-Time")

    r = _q1("SELECT o.canonical_name, SUM(sr.losses) as l FROM season_records sr JOIN owners o ON sr.user_id=o.user_id GROUP BY sr.user_id ORDER BY l DESC LIMIT 1")
    if r: _add("Most Losses, All-Time", r[0], str(int(r[1])), "All-Time")

    # Weekly scoring
    playoff_filter = "" if include_playoffs else "AND m.is_playoff = 0 "
    r = _q1(f"SELECT o.canonical_name, m.points, m.season, m.week FROM matchups m JOIN owners o ON m.user_id=o.user_id WHERE m.points IS NOT NULL {playoff_filter}ORDER BY m.points DESC LIMIT 1")
    if r: _add("Most Points, Single Week", r[0], f"{r[1]:,.2f}", f"{r[2]} Wk{r[3]}")

    r = _q1(f"SELECT o.canonical_name, m.points, m.season, m.week FROM matchups m JOIN owners o ON m.user_id=o.user_id WHERE m.points IS NOT NULL AND m.points > 0 {playoff_filter}ORDER BY m.points ASC LIMIT 1")
    if r: _add("Fewest Points, Single Week", r[0], f"{r[1]:,.2f}", f"{r[2]} Wk{r[3]}")

    # Season points
    r = _q1("SELECT o.canonical_name, sr.fpts, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id ORDER BY sr.fpts DESC LIMIT 1")
    if r: _add("Most Points For, Single Season", r[0], f"{r[1]:,.2f}", str(r[2]))

    r = _q1("SELECT o.canonical_name, sr.fpts, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id WHERE sr.wins+sr.losses+sr.ties > 0 ORDER BY sr.fpts ASC LIMIT 1")
    if r: _add("Fewest Points For, Single Season", r[0], f"{r[1]:,.2f}", str(r[2]))

    r = _q1("SELECT o.canonical_name, SUM(sr.fpts) as t FROM season_records sr JOIN owners o ON sr.user_id=o.user_id GROUP BY sr.user_id HAVING SUM(sr.wins)+SUM(sr.losses) > 0 ORDER BY t DESC LIMIT 1")
    if r: _add("Most Points For, All-Time", r[0], f"{r[1]:,.2f}", "All-Time")

    r = _q1("SELECT o.canonical_name, SUM(sr.fpts) as t FROM season_records sr JOIN owners o ON sr.user_id=o.user_id GROUP BY sr.user_id HAVING SUM(sr.wins)+SUM(sr.losses) > 0 ORDER BY t ASC LIMIT 1")
    if r: _add("Fewest Points For, All-Time", r[0], f"{r[1]:,.2f}", "All-Time")

    r = _q1("SELECT o.canonical_name, sr.fpts_against, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id ORDER BY sr.fpts_against DESC LIMIT 1")
    if r: _add("Most Points Against, Single Season", r[0], f"{r[1]:,.2f}", str(r[2]))

    r = _q1("SELECT o.canonical_name, sr.fpts_against, sr.season FROM season_records sr JOIN owners o ON sr.user_id=o.user_id WHERE sr.wins+sr.losses+sr.ties > 0 ORDER BY sr.fpts_against ASC LIMIT 1")
    if r: _add("Fewest Points Against, Single Season", r[0], f"{r[1]:,.2f}", str(r[2]))

    # Streaks
    streaks = _compute_win_loss_streaks(con)
    if streaks:
        best_win = max(streaks.items(), key=lambda x: x[1]["max_win"])
        _add("Longest Win Streak", owner_names.get(best_win[0], best_win[0]), str(best_win[1]["max_win"]), "All-Time")
        worst_loss = max(streaks.items(), key=lambda x: x[1]["max_loss"])
        _add("Longest Losing Streak", owner_names.get(worst_loss[0], worst_loss[0]), str(worst_loss[1]["max_loss"]), "All-Time")

    # Weekly high score king (most weeks with the single highest score)
    extremes = get_weekly_scoring_extremes(con)
    high_counts = extremes["high_counts"]
    if high_counts:
        top_owner = max(high_counts, key=lambda k: high_counts[k])
        _add("Most Weekly High Scores, All-Time", top_owner, str(high_counts[top_owner]), "All-Time")
    low_counts = extremes["low_counts"]
    if low_counts:
        top_owner = max(low_counts, key=lambda k: low_counts[k])
        _add("Most Weekly Low Scores, All-Time", top_owner, str(low_counts[top_owner]), "All-Time")

    # Championships
    seasons = get_all_seasons(con)
    champ_counts: dict[str, int] = {}
    for s in seasons:
        results = compute_playoff_results(con, s["league_id"], s["season"], s["playoff_week_start"], s["last_week"])
        for pr in results:
            if pr.champion:
                champ_counts[pr.canonical_name] = champ_counts.get(pr.canonical_name, 0) + 1
    if champ_counts:
        top = max(champ_counts, key=lambda k: champ_counts[k])
        _add("Most Championships", top, str(champ_counts[top]), "All-Time")

    return records


# ---------------------------------------------------------------------------
# Playoff records per owner
# ---------------------------------------------------------------------------

@dataclass
class PlayoffSummary:
    canonical_name: str
    appearances: int = 0
    byes: int = 0
    playoff_wins: int = 0
    playoff_losses: int = 0
    championships: int = 0
    runner_up: int = 0

    @property
    def games(self) -> int:
        return self.playoff_wins + self.playoff_losses

    @property
    def win_pct(self) -> float:
        return self.playoff_wins / self.games if self.games else 0.0


def get_playoff_records(con: sqlite3.Connection) -> list[PlayoffSummary]:
    """Compute cumulative playoff stats per owner across all complete seasons."""
    seasons = get_all_seasons(con)
    summaries: dict[str, PlayoffSummary] = {}

    for s in seasons:
        pws = s["playoff_week_start"]
        last_week = s["last_week"]
        league_id = s["league_id"]

        # Determine who had byes (played in championship bracket but NOT in the first playoff week)
        first_week_players = {
            r[0] for r in con.execute(
                "SELECT user_id FROM matchups WHERE league_id=? AND week=? AND is_playoff=1 AND matchup_id<=3",
                (league_id, pws),
            ).fetchall()
        }
        all_playoff_players = {
            r[0] for r in con.execute(
                "SELECT DISTINCT user_id FROM matchups WHERE league_id=? AND is_playoff=1 AND matchup_id<=3",
                (league_id,),
            ).fetchall()
        }
        bye_recipients = all_playoff_players - first_week_players

        results = compute_playoff_results(con, league_id, s["season"], pws, last_week)

        for pr in results:
            if not pr.made_playoffs:
                continue
            if pr.canonical_name not in summaries:
                summaries[pr.canonical_name] = PlayoffSummary(pr.canonical_name)
            ps = summaries[pr.canonical_name]
            ps.appearances += 1
            if pr.user_id in bye_recipients:
                ps.byes += 1
            if pr.champion:
                ps.championships += 1
            if pr.finish == 2:
                ps.runner_up += 1

        # Compute playoff W-L from matchup results within the championship bracket
        playoff_rows = con.execute(
            """
            SELECT m1.user_id, m2.user_id,
                   CASE WHEN m1.points > m2.points THEN 1 ELSE 0 END as m1_won
            FROM matchups m1
            JOIN matchups m2
              ON m1.league_id = m2.league_id AND m1.week = m2.week
             AND m1.matchup_id = m2.matchup_id AND m1.user_id < m2.user_id
            WHERE m1.league_id = ? AND m1.is_playoff = 1
              AND m1.matchup_id <= 3
              AND m1.points IS NOT NULL AND m2.points IS NOT NULL
            """,
            (league_id,),
        ).fetchall()

        owner_names = {r[0]: r[1] for r in con.execute("SELECT user_id, canonical_name FROM owners")}
        for uid1, uid2, m1_won in playoff_rows:
            for uid, won in [(uid1, m1_won), (uid2, 1 - m1_won)]:
                name = owner_names.get(uid)
                if name and name in summaries:
                    if won:
                        summaries[name].playoff_wins += 1
                    else:
                        summaries[name].playoff_losses += 1

    return sorted(summaries.values(), key=lambda s: (-s.appearances, -s.win_pct))


# ---------------------------------------------------------------------------
# Head-to-head matrix
# ---------------------------------------------------------------------------

def get_h2h_matrix(con: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Return {(winner_name, loser_name): count} for regular-season matchups."""
    owner_names = {r[0]: r[1] for r in con.execute("SELECT user_id, canonical_name FROM owners")}

    rows = con.execute(
        """
        SELECT m1.user_id, m2.user_id, m1.points, m2.points
        FROM matchups m1
        JOIN matchups m2
          ON m1.league_id  = m2.league_id
         AND m1.week       = m2.week
         AND m1.matchup_id = m2.matchup_id
         AND m1.user_id    < m2.user_id
        WHERE m1.is_playoff = 0
          AND m1.points IS NOT NULL
          AND m2.points IS NOT NULL
        """
    ).fetchall()

    matrix = {}
    for uid1, uid2, pts1, pts2 in rows:
        n1 = owner_names.get(uid1)
        n2 = owner_names.get(uid2)
        if not n1 or not n2:
            continue
        if pts1 > pts2:
            matrix[(n1, n2)] = matrix.get((n1, n2), 0) + 1
        elif pts2 > pts1:
            matrix[(n2, n1)] = matrix.get((n2, n1), 0) + 1

    return matrix


# ---------------------------------------------------------------------------
# Championship rosters
# ---------------------------------------------------------------------------

def get_championship_rosters(con: sqlite3.Connection) -> list[dict]:
    """Return champion, runner-up, score, and starting lineup for each season."""
    seasons = get_all_seasons(con)
    player_names = {r[0]: (r[1], r[2]) for r in con.execute("SELECT player_id, full_name, position FROM players")}
    results_out = []

    for s in seasons:
        results = compute_playoff_results(
            con, s["league_id"], s["season"], s["playoff_week_start"], s["last_week"]
        )
        finish_map = {r.finish: r for r in results}
        champion = finish_map.get(1)
        runner_up = finish_map.get(2)
        if not champion:
            continue

        # Championship game scores and lineups
        champ_row = con.execute(
            "SELECT points, starters_json, players_points_json FROM matchups "
            "WHERE league_id=? AND week=? AND user_id=? AND matchup_id=1",
            (s["league_id"], s["last_week"], champion.user_id),
        ).fetchone()
        ru_row = con.execute(
            "SELECT points, starters_json, players_points_json FROM matchups "
            "WHERE league_id=? AND week=? AND user_id=? AND matchup_id=1",
            (s["league_id"], s["last_week"], runner_up.user_id if runner_up else None),
        ).fetchone() if runner_up else None

        def _build_lineup(row: tuple | None) -> list[dict]:
            if not row or not row[1]:
                return []
            starters_list = json.loads(row[1])
            pts_map: dict[str, float] = json.loads(row[2]) if row[2] else {}
            lineup = []
            for pid in starters_list:
                name, pos = player_names.get(pid, (pid, "?"))
                lineup.append({
                    "position": pos or "?",
                    "player": name or pid,
                    "points": pts_map.get(pid),
                })
            return lineup

        results_out.append({
            "season": s["season"],
            "champion": champion.canonical_name,
            "runner_up": runner_up.canonical_name if runner_up else "—",
            "champ_score": champ_row[0] if champ_row else None,
            "ru_score": ru_row[0] if ru_row else None,
            "champ_starters": _build_lineup(champ_row),
            "ru_starters": _build_lineup(ru_row),
        })

    return results_out


# ---------------------------------------------------------------------------
# Luck-o-Meter
# ---------------------------------------------------------------------------

def compute_luck_scores(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
    playoff_week_start: int,
) -> list[dict]:
    """Compute luck scores for one regular season.

    Expected wins per week = (teams beaten + 0.5 * teams tied) / (n_teams - 1).
    Luck diff = actual_wins - sum(expected_wins_per_week).
    Positive = lucky schedule, negative = unlucky.
    """
    from collections import defaultdict

    rows = con.execute(
        """
        SELECT m.week, m.matchup_id, m.user_id, o.canonical_name, m.points
        FROM matchups m
        JOIN owners o ON m.user_id = o.user_id
        WHERE m.league_id = ? AND m.week < ?
          AND m.points IS NOT NULL
        ORDER BY m.week
        """,
        (league_id, playoff_week_start),
    ).fetchall()

    if not rows:
        return []

    # Actual W/L from head-to-head matchup pairs
    owner_names: dict[str, str] = {}
    actual_wins: dict[str, int] = defaultdict(int)
    actual_losses: dict[str, int] = defaultdict(int)
    actual_ties: dict[str, int] = defaultdict(int)
    matchup_pairs: dict[tuple, list] = defaultdict(list)
    week_all_scores: dict[int, list] = defaultdict(list)

    for week, mid, uid, name, pts in rows:
        owner_names[uid] = name
        matchup_pairs[(week, mid)].append((uid, pts or 0.0))
        week_all_scores[week].append((uid, pts or 0.0))

    for (week, mid), teams in matchup_pairs.items():
        if len(teams) != 2:
            continue
        (uid_a, pts_a), (uid_b, pts_b) = teams
        if pts_a > pts_b:
            actual_wins[uid_a] += 1
            actual_losses[uid_b] += 1
        elif pts_b > pts_a:
            actual_wins[uid_b] += 1
            actual_losses[uid_a] += 1
        else:
            actual_ties[uid_a] += 1
            actual_ties[uid_b] += 1

    # Simulate each team vs every opponent each week (integer counts)
    sim_wins: dict[str, int] = defaultdict(int)
    sim_losses: dict[str, int] = defaultdict(int)
    sim_ties: dict[str, int] = defaultdict(int)
    for week, teams in week_all_scores.items():
        if len(teams) < 2:
            continue
        for uid, my_pts in teams:
            for other, opp_pts in teams:
                if other == uid:
                    continue
                if my_pts > opp_pts:
                    sim_wins[uid] += 1
                elif my_pts < opp_pts:
                    sim_losses[uid] += 1
                else:
                    sim_ties[uid] += 1

    results = []
    for uid, name in owner_names.items():
        aw = actual_wins.get(uid, 0)
        al = actual_losses.get(uid, 0)
        at = actual_ties.get(uid, 0)
        actual_games = aw + al + at
        actual_win_pct = (aw + 0.5 * at) / actual_games if actual_games else 0.0

        sw = sim_wins.get(uid, 0)
        sl = sim_losses.get(uid, 0)
        st_ = sim_ties.get(uid, 0)
        sim_games = sw + sl + st_
        sim_win_pct = (sw + 0.5 * st_) / sim_games if sim_games else 0.0

        # luck_diff in equivalent wins (same scale as actual W/L) for verdict thresholds
        luck_diff = round((actual_win_pct - sim_win_pct) * actual_games, 2)

        results.append({
            "user_id": uid,
            "owner": name,
            "season": season,
            "actual_wins": aw,
            "actual_losses": al,
            "actual_ties": at,
            "actual_win_pct": round(actual_win_pct, 4),
            "sim_wins": sw,
            "sim_losses": sl,
            "sim_ties": st_,
            "sim_win_pct": round(sim_win_pct, 4),
            "luck_diff": luck_diff,
        })

    return sorted(results, key=lambda r: -r["luck_diff"])


def get_all_time_luck(con: sqlite3.Connection) -> list[dict]:
    """Aggregate luck scores across all complete regular seasons."""
    seasons = get_all_seasons(con)
    all_rows: list[dict] = []
    for s in seasons:
        rows = compute_luck_scores(
            con, s["league_id"], s["season"], s["playoff_week_start"]
        )
        all_rows.extend(rows)
    return all_rows


# ---------------------------------------------------------------------------
# Race to the Bottom
# ---------------------------------------------------------------------------

def get_race_to_bottom(con: sqlite3.Connection, season: int) -> list[dict]:
    """Return non-playoff teams ranked by optimal PF (ppts) ascending.

    Lowest ppts = 1st rookie draft pick. Rewards weakest overall roster
    rather than rewarding owners who bench players to lose.
    """
    row = con.execute(
        """
        SELECT league_id, playoff_week_start,
               COALESCE(last_scored_leg, playoff_week_start + 2)
        FROM leagues WHERE season = ?
        """,
        (season,),
    ).fetchone()
    if not row:
        return []
    league_id, pws, last_week = row

    playoff_results = compute_playoff_results(con, league_id, season, pws, last_week)
    playoff_uids = {pr.user_id for pr in playoff_results if pr.made_playoffs}

    rows = con.execute(
        """
        SELECT sr.user_id, o.canonical_name, sr.wins, sr.losses, sr.fpts, sr.ppts
        FROM season_records sr
        JOIN owners o ON sr.user_id = o.user_id
        WHERE sr.league_id = ?
        """,
        (league_id,),
    ).fetchall()

    non_playoff = []
    for uid, name, wins, losses, fpts, ppts in rows:
        if uid in playoff_uids or ppts == 0:
            continue
        non_playoff.append({
            "user_id": uid,
            "owner": name,
            "season": season,
            "wins": wins,
            "losses": losses,
            "actual_pts": round(fpts, 2),
            "optimal_pts": round(ppts, 2),
            "lineup_pct": round(fpts / ppts * 100, 1) if ppts else 0.0,
        })

    non_playoff.sort(key=lambda r: r["optimal_pts"])
    for i, r in enumerate(non_playoff):
        r["draft_pick"] = i + 1

    return non_playoff


def get_rtb_history(con: sqlite3.Connection) -> list[dict]:
    """Return Race to the Bottom results for all complete seasons."""
    seasons = get_all_seasons(con)
    all_rows: list[dict] = []
    for s in seasons:
        rows = get_race_to_bottom(con, s["season"])
        all_rows.extend(rows)
    return all_rows


# ---------------------------------------------------------------------------
# Owner top scoring players
# ---------------------------------------------------------------------------

def get_owner_top_players(
    con: sqlite3.Connection,
    owner_name: str,
    season: int | None = None,
    top_n: int = 10,
) -> list[dict]:
    """Return the top N players by total regular-season points started for an owner.

    Only weeks where both starters_json and players_points_json are populated
    are counted — this covers all seasons where the full ingest has run.
    """
    row = con.execute(
        "SELECT user_id FROM owners WHERE canonical_name = ?", (owner_name,)
    ).fetchone()
    if not row:
        return []
    user_id = row[0]

    season_filter = "AND m.season = ?" if season is not None else ""
    params: tuple = (user_id,) + ((season,) if season is not None else ())

    rows = con.execute(
        f"""
        SELECT m.starters_json, m.players_points_json
        FROM matchups m
        WHERE m.user_id = ?
          {season_filter}
          AND m.starters_json IS NOT NULL
          AND m.players_points_json IS NOT NULL
          AND m.is_playoff = 0
        """,
        params,
    ).fetchall()

    totals: dict[str, float] = {}
    weeks_started: dict[str, int] = {}

    for starters_raw, pp_raw in rows:
        starters = set(json.loads(starters_raw))
        pp: dict[str, float] = json.loads(pp_raw)
        for pid in starters:
            pts = pp.get(pid, 0.0)
            totals[pid] = totals.get(pid, 0.0) + pts
            weeks_started[pid] = weeks_started.get(pid, 0) + 1

    player_info = {
        r[0]: (r[1], r[2])
        for r in con.execute("SELECT player_id, full_name, position FROM players")
    }

    results = []
    for pid, total_pts in sorted(totals.items(), key=lambda x: -x[1])[:top_n]:
        name, pos = player_info.get(pid, (pid, "?"))
        wk = weeks_started[pid]
        results.append({
            "player": name or pid,
            "position": pos or "?",
            "total_pts": round(total_pts, 1),
            "weeks_started": wk,
            "avg_pts": round(total_pts / wk, 1) if wk else 0.0,
        })

    return results
