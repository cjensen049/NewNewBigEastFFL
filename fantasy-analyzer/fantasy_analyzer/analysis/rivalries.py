"""Rivalry, nemesis, and head-to-head dominance analysis."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class RivalryPair:
    owner_a: str
    owner_b: str
    a_wins: int
    b_wins: int

    @property
    def total_games(self) -> int:
        return self.a_wins + self.b_wins

    @property
    def balance(self) -> float:
        """0.0 = perfectly even, 1.0 = complete domination."""
        if self.total_games == 0:
            return 0.0
        return abs(self.a_wins - self.b_wins) / self.total_games

    @property
    def rivalry_score(self) -> float:
        """Higher = more games AND closer record — the truest rivalries."""
        return self.total_games * (1.0 - self.balance)

    def record_for(self, owner: str) -> str:
        if owner == self.owner_a:
            return f"{self.a_wins}-{self.b_wins}"
        return f"{self.b_wins}-{self.a_wins}"

    def win_pct_for(self, owner: str) -> float:
        wins = self.a_wins if owner == self.owner_a else self.b_wins
        return wins / self.total_games if self.total_games else 0.0

    def opponent_of(self, owner: str) -> str:
        return self.owner_b if owner == self.owner_a else self.owner_a

    def leader(self) -> str:
        """Owner with the better record, or empty string if tied."""
        if self.a_wins > self.b_wins:
            return self.owner_a
        if self.b_wins > self.a_wins:
            return self.owner_b
        return ""


def get_rivalry_pairs(con: sqlite3.Connection) -> list[RivalryPair]:
    """
    Return all owner pairs with their regular-season head-to-head records,
    sorted by rivalry_score descending (most games + closest record first).
    """
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

    pair_wins: dict[tuple[str, str], list[int]] = {}
    for uid1, uid2, pts1, pts2 in rows:
        n1 = owner_names.get(uid1)
        n2 = owner_names.get(uid2)
        if not n1 or not n2:
            continue
        # Keep alphabetical order so (A, B) is canonical regardless of uid order
        a, b = (n1, n2) if n1 < n2 else (n2, n1)
        key = (a, b)
        if key not in pair_wins:
            pair_wins[key] = [0, 0]
        if pts1 > pts2:
            winner = n1
        elif pts2 > pts1:
            winner = n2
        else:
            continue  # tie — skip
        if winner == a:
            pair_wins[key][0] += 1
        else:
            pair_wins[key][1] += 1

    return sorted(
        [RivalryPair(a, b, w[0], w[1]) for (a, b), w in pair_wins.items()],
        key=lambda p: -p.rivalry_score,
    )


def get_nemesis_prey(con: sqlite3.Connection) -> list[dict]:
    """
    For each owner return their nemesis (worst record against, min 2 games)
    and prey (best record against, min 2 games), sorted by owner name.
    """
    pairs = get_rivalry_pairs(con)
    all_owners = sorted({p.owner_a for p in pairs} | {p.owner_b for p in pairs})

    rows = []
    for owner in all_owners:
        eligible = [p for p in pairs if owner in (p.owner_a, p.owner_b) and p.total_games >= 2]
        if not eligible:
            continue

        nemesis_pair = min(eligible, key=lambda p: p.win_pct_for(owner))
        prey_pair    = max(eligible, key=lambda p: p.win_pct_for(owner))

        rows.append({
            "owner":            owner,
            "nemesis":          nemesis_pair.opponent_of(owner),
            "nemesis_record":   nemesis_pair.record_for(owner),
            "nemesis_win_pct":  nemesis_pair.win_pct_for(owner),
            "prey":             prey_pair.opponent_of(owner),
            "prey_record":      prey_pair.record_for(owner),
            "prey_win_pct":     prey_pair.win_pct_for(owner),
        })

    return rows
