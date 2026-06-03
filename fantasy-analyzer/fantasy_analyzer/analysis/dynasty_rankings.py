"""Dynasty power rankings for NNBE.

Formula:
  DynastyScore =
    0.55 × RosterValue    (value_2qb for all players; taxi at 80%)
    + 0.30 × DraftCapital (future picks you hold × DynastyProcess pick values)
    + 0.15 × AgeCurve     (value-weighted avg age of top-15 players; young = bonus)

Roster includes: active players + bench + taxi squad (taxi discounted to 80%).
Draft capital: reconstructs current pick ownership from transaction history;
  covers 3 future seasons (current+1 through current+3), 3 rounds each.
Age curve: compares value-weighted average age to a dynasty-prime benchmark of 25.
  Each year above 25 costs ~5 points; normalized within league so it's relative.

Returns {} when no dynasty value data has been scraped yet.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict


_TAXI_DISCOUNT   = 0.80   # taxi players counted at 80% of value
_AGE_TOP_N       = 15     # number of top players (by value) used for age curve
_AGE_PRIME       = 25.0   # age considered peak for dynasty purposes
_AGE_COST_PER_YR = 5.0    # score penalty per year above prime
_FUTURE_YEARS    = 3      # how many future draft years to value (NNBE allows 3)
_ROUNDS          = 3      # NNBE rookie draft rounds per year

# Tier → pick slot ranges (12-team league)
_TIER_SLOTS = {"early": (1, 4), "mid": (5, 8), "late": (9, 12)}


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize to 0–100. Returns 50.0 for all if no spread."""
    if not values:
        return {}
    mn, mx = min(values.values()), max(values.values())
    if mx == mn:
        return {k: 50.0 for k in values}
    return {k: (v - mn) / (mx - mn) * 100.0 for k, v in values.items()}


# ---------------------------------------------------------------------------
# Pick ownership reconstruction
# ---------------------------------------------------------------------------

def _current_pick_owners(
    con: sqlite3.Connection,
    league_id: str,
    current_season: int,
) -> dict[tuple, int]:
    """Return {(season, round, original_roster_id): current_roster_id}.

    Considers all future picks (current_season+1 through current_season+3).
    If a pick has been traded, the most recent to_roster_id is the owner.
    Un-traded picks default to original_roster_id.
    """
    future_start = current_season + 1
    future_end   = current_season + _FUTURE_YEARS

    # All trades involving future picks for this league
    rows = con.execute(
        """SELECT tdp.season, tdp.round, tdp.original_roster_id,
                  tdp.to_roster_id, t.created_epoch
           FROM transaction_draft_picks tdp
           JOIN transactions t ON tdp.transaction_id = t.transaction_id
           WHERE t.league_id = ? AND tdp.season BETWEEN ? AND ?
           ORDER BY t.created_epoch""",
        (league_id, future_start, future_end),
    ).fetchall()

    # Keep only the most recent trade per pick
    latest: dict[tuple, tuple] = {}
    for season, rnd, orig_rid, to_rid, epoch in rows:
        key = (season, rnd, orig_rid)
        if key not in latest or (epoch or 0) > latest[key][1]:
            latest[key] = (to_rid, epoch or 0)

    current_owners = {k: v[0] for k, v in latest.items()}

    # Roster IDs for this league
    roster_ids = [
        r[0] for r in con.execute(
            "SELECT roster_id FROM league_owners WHERE league_id = ?", (league_id,)
        ).fetchall()
    ]

    # Fill un-traded picks — original owner still holds
    for future_season in range(future_start, future_end + 1):
        for rnd in range(1, _ROUNDS + 1):
            for orig_rid in roster_ids:
                key = (future_season, rnd, orig_rid)
                if key not in current_owners:
                    current_owners[key] = orig_rid

    return current_owners


def _pick_tier(orig_rid: int, all_roster_ids: list[int]) -> str:
    """Estimate the draft pick tier for a given original_roster_id.

    Uses the roster's relative position as a proxy for expected pick slot.
    Since we don't know future standings, this is approximate.
    Returns 'early', 'mid', or 'late'.
    """
    # Sort roster IDs consistently so the mapping is stable
    sorted_ids = sorted(all_roster_ids)
    n = len(sorted_ids)
    try:
        pos = sorted_ids.index(orig_rid) + 1  # 1-indexed
    except ValueError:
        return "mid"
    pct = pos / n
    if pct <= 0.33:  return "early"
    if pct <= 0.67:  return "mid"
    return "late"


# ---------------------------------------------------------------------------
# Component computations
# ---------------------------------------------------------------------------

def _roster_values(
    con: sqlite3.Connection,
    league_id: str,
) -> dict[str, float]:
    """Return {user_id: raw_roster_value} using DynastyProcess value_2qb."""
    owner_rows = con.execute(
        "SELECT lo.user_id, lo.roster_id FROM league_owners lo WHERE lo.league_id = ?",
        (league_id,),
    ).fetchall()

    result: dict[str, float] = {}

    for user_id, roster_id in owner_rows:
        # Join current roster to dynasty values; taxi at _TAXI_DISCOUNT
        rows = con.execute(
            """SELECT pdv.value, cr.status
               FROM current_rosters cr
               JOIN player_dynasty_values pdv ON cr.player_id = pdv.player_id
               WHERE cr.league_id = ? AND cr.roster_id = ? AND pdv.value > 0""",
            (league_id, roster_id),
        ).fetchall()

        total = sum(
            val * (_TAXI_DISCOUNT if status == "taxi" else 1.0)
            for val, status in rows
        )
        result[user_id] = total

    return result


def _draft_capital_values(
    con: sqlite3.Connection,
    league_id: str,
    current_season: int,
) -> dict[str, float]:
    """Return {user_id: raw_draft_capital_value}."""
    # Check pick value data exists
    if not con.execute("SELECT 1 FROM pick_dynasty_values LIMIT 1").fetchone():
        return {}

    pick_owners = _current_pick_owners(con, league_id, current_season)

    roster_ids = [
        r[0] for r in con.execute(
            "SELECT roster_id FROM league_owners WHERE league_id = ?", (league_id,)
        ).fetchall()
    ]

    # roster_id → user_id
    rid_to_uid = dict(
        con.execute(
            "SELECT roster_id, user_id FROM league_owners WHERE league_id = ?",
            (league_id,),
        ).fetchall()
    )

    # Aggregate pick values per current owner
    capital: dict[str, float] = defaultdict(float)

    for (season, rnd, orig_rid), current_rid in pick_owners.items():
        uid = rid_to_uid.get(current_rid)
        if not uid:
            continue

        # Estimate tier from original owner (approx — future standings unknown)
        tier = _pick_tier(orig_rid, roster_ids)

        row = con.execute(
            "SELECT value FROM pick_dynasty_values WHERE season=? AND round=? AND tier=?",
            (season, rnd, tier),
        ).fetchone()

        # Fallback: try mid tier if specific tier not found
        if not row:
            row = con.execute(
                "SELECT value FROM pick_dynasty_values WHERE season=? AND round=? AND tier='mid'",
                (season, rnd),
            ).fetchone()

        if row:
            capital[uid] += row[0]

    return dict(capital)


def _age_curve_values(
    con: sqlite3.Connection,
    league_id: str,
) -> dict[str, float]:
    """Return {user_id: age_score} where younger rosters score higher.

    Computes value-weighted average age of each roster's top-N players
    then converts to 0-100 via: 100 - max(0, (avg_age - AGE_PRIME) * AGE_COST).
    """
    owner_rows = con.execute(
        "SELECT lo.user_id, lo.roster_id FROM league_owners lo WHERE lo.league_id = ?",
        (league_id,),
    ).fetchall()

    scores: dict[str, float] = {}

    for user_id, roster_id in owner_rows:
        rows = con.execute(
            """SELECT pdv.value, pdv.age
               FROM current_rosters cr
               JOIN player_dynasty_values pdv ON cr.player_id = pdv.player_id
               WHERE cr.league_id = ? AND cr.roster_id = ?
                 AND pdv.value > 0 AND pdv.age > 0
               ORDER BY pdv.value DESC
               LIMIT ?""",
            (league_id, roster_id, _AGE_TOP_N),
        ).fetchall()

        if not rows:
            continue

        total_val = sum(v for v, _ in rows)
        if total_val == 0:
            continue

        weighted_age = sum(v * a for v, a in rows) / total_val
        raw_score = 100.0 - max(0.0, (weighted_age - _AGE_PRIME) * _AGE_COST_PER_YR)
        scores[user_id] = raw_score

    return scores


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_dynasty_rankings(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
) -> dict:
    """Compute dynasty power rankings for a league.

    Returns: {season, data_date, rows} where rows are sorted by composite desc.
    Returns {} when no dynasty value data exists.
    """
    # Check whether dynasty data exists
    count = con.execute("SELECT COUNT(*) FROM player_dynasty_values").fetchone()[0]
    if count == 0:
        return {"season": season, "data_date": None, "rows": []}

    data_date = (
        con.execute("SELECT MAX(scraped_at) FROM player_dynasty_values").fetchone()[0]
        or ""
    )[:10]  # ISO date prefix

    # User list
    user_rows = con.execute(
        """SELECT lo.user_id, o.canonical_name
           FROM league_owners lo
           JOIN owners o ON lo.user_id = o.user_id
           WHERE lo.league_id = ?""",
        (league_id,),
    ).fetchall()
    user_to_name = {r[0]: r[1] for r in user_rows}
    uids = list(user_to_name.keys())

    if not uids:
        return {"season": season, "data_date": data_date, "rows": []}

    # Components
    rv_raw  = _roster_values(con, league_id)
    dc_raw  = _draft_capital_values(con, league_id, season)
    age_raw = _age_curve_values(con, league_id)

    rv_norm  = _normalize({uid: rv_raw.get(uid, 0.0) for uid in uids})
    dc_norm  = _normalize({uid: dc_raw.get(uid, 0.0) for uid in uids})
    age_norm = _normalize({uid: age_raw.get(uid, 50.0) for uid in uids})

    # Composite
    power: dict[str, float] = {
        uid: (
            0.55 * rv_norm.get(uid, 50.0)
            + 0.30 * dc_norm.get(uid, 50.0)
            + 0.15 * age_norm.get(uid, 50.0)
        )
        for uid in uids
    }

    # Current season standings for display context
    standings = con.execute(
        """SELECT m1.user_id,
                  SUM(CASE WHEN m1.points > m2.points THEN 1 ELSE 0 END) AS wins,
                  SUM(CASE WHEN m1.points < m2.points THEN 1 ELSE 0 END) AS losses,
                  ROUND(SUM(m1.points), 1) AS pts_for
           FROM matchups m1
           JOIN matchups m2
             ON m1.league_id  = m2.league_id
            AND m1.week       = m2.week
            AND m1.matchup_id = m2.matchup_id
            AND m1.user_id   != m2.user_id
           WHERE m1.league_id = ?
             AND m1.is_playoff = 0
             AND m1.points IS NOT NULL AND m1.points > 0
           GROUP BY m1.user_id""",
        (league_id,),
    ).fetchall()
    wins_by_uid   = {r[0]: r[1] for r in standings}
    losses_by_uid = {r[0]: r[2] for r in standings}
    pts_by_uid    = {r[0]: float(r[3]) for r in standings}

    sorted_uids = sorted(uids, key=lambda u: -power[u])
    rows = []
    for rank, uid in enumerate(sorted_uids, 1):
        rows.append({
            "rank":          rank,
            "owner":         user_to_name[uid],
            "composite":     round(power[uid], 1),
            "roster_score":  round(rv_norm.get(uid, 0.0), 1),
            "capital_score": round(dc_norm.get(uid, 0.0), 1),
            "age_score":     round(age_norm.get(uid, 0.0), 1),
            "actual_wins":   wins_by_uid.get(uid, 0),
            "actual_losses": losses_by_uid.get(uid, 0),
            "pts_for":       pts_by_uid.get(uid, 0.0),
        })

    return {"season": season, "data_date": data_date, "rows": rows}
