"""Roster quality scoring for NNBE power rankings.

Computes each owner's optimal projected lineup score using Sleeper's
rest-of-season projections (player_season_projections) and the current
roster snapshot in current_rosters.

NNBE lineup: QB  RB  WR  WR  TE  FLEX  FLEX  FLEX  SFLEX  (9 starters)
  FLEX  eligible: RB, WR, TE
  SFLEX eligible: QB, RB, WR, TE  (at most 1 QB in the flex pool)
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict


# ---------------------------------------------------------------------------
# Optimal lineup calculator
# ---------------------------------------------------------------------------

def optimal_lineup_pts(players: list[dict]) -> float:
    """Return the maximum projected points achievable from a player pool.

    Args:
        players: list of {"position": str, "projected_pts": float}

    Slots filled: QB(1), RB(1), WR(2), TE(1), FLEX×3, SFLEX×1 = 9 total.
    """
    by_pos: dict[str, list[float]] = defaultdict(list)
    for p in players:
        by_pos[p["position"]].append(p["projected_pts"])
    for pos in by_pos:
        by_pos[pos].sort(reverse=True)

    total = 0.0
    used: dict[str, int] = defaultdict(int)

    # ── Locked single-position slots ─────────────────────────────────────────
    locked = [("QB", 1), ("RB", 1), ("WR", 2), ("TE", 1)]
    for pos, count in locked:
        pool = by_pos.get(pos, [])
        for i in range(count):
            if i < len(pool):
                total += pool[i]
                used[pos] += 1

    # ── Flex pool: 4 remaining slots (FLEX×3 + SFLEX) ─────────────────────
    # Build pool of remaining players.
    non_qb: list[float] = []
    for pos in ("RB", "WR", "TE"):
        non_qb.extend(by_pos.get(pos, [])[used[pos]:])
    non_qb.sort(reverse=True)

    # Best remaining QB (if any) — can only fill SFLEX (at most 1 QB in pool)
    qb_pool = by_pos.get("QB", [])[used["QB"]:]
    best_qb = qb_pool[0] if qb_pool else None

    # Determine whether the best QB earns a spot over the 4th-best non-QB
    top4_non_qb = non_qb[:4]

    if best_qb is not None:
        # Include QB if it beats the worst of the top-4 non-QB (or fills an empty slot)
        if len(top4_non_qb) < 4 or best_qb > top4_non_qb[-1]:
            cutoff_idx = 3 if len(top4_non_qb) >= 4 else len(top4_non_qb)
            flex_pts = sum(top4_non_qb[:cutoff_idx]) + best_qb
        else:
            flex_pts = sum(top4_non_qb)
    else:
        flex_pts = sum(top4_non_qb)

    total += flex_pts
    return total


# ---------------------------------------------------------------------------
# Per-owner roster quality
# ---------------------------------------------------------------------------

# Below this many matched players, there isn't enough real data to fill even
# the locked slots (QB, RB, WR×2, TE) -- treat it as no data rather than let
# a handful of stray matches masquerade as a real "worst roster" signal.
_MIN_MATCHED_PLAYERS = 5


def compute_roster_quality(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
) -> dict[str, float | None]:
    """Return {user_id: optimal_projected_pts} using season-long projections.

    Returns {} if no projection data exists at all.
    Returns None for a specific owner if too few of their rostered players
    matched a projection to trust the result (see _MIN_MATCHED_PLAYERS).
    """
    has_data = con.execute(
        "SELECT 1 FROM player_season_projections WHERE season = ? LIMIT 1",
        (season,),
    ).fetchone()
    if not has_data:
        return {}

    # Owner → roster_id mapping for this league
    owner_rows = con.execute(
        """SELECT lo.user_id, lo.roster_id
           FROM league_owners lo
           WHERE lo.league_id = ?""",
        (league_id,),
    ).fetchall()

    if not owner_rows:
        return {}

    result: dict[str, float | None] = {}

    for user_id, roster_id in owner_rows:
        players = con.execute(
            """SELECT sp.position, sp.projected_pts
               FROM current_rosters cr
               JOIN player_season_projections sp
                 ON cr.player_id = sp.player_id
                AND sp.season    = ?
               WHERE cr.league_id = ?
                 AND cr.roster_id = ?
                 AND sp.projected_pts > 0""",
            (season, league_id, roster_id),
        ).fetchall()

        if len(players) < _MIN_MATCHED_PLAYERS:
            result[user_id] = None
            continue

        player_dicts = [{"position": pos, "projected_pts": float(pts)} for pos, pts in players]
        result[user_id] = optimal_lineup_pts(player_dicts)

    return result
