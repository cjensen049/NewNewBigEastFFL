"""Dynasty power rankings for NNBE.

Formula:
  DynastyScore =
    0.60 × RosterValue    (z-scored; a source's own published team total when
                            it has one, else sum of matched player values —
                            taxi at 80%)
    + 0.35 × DraftCapital (z-scored; future picks you hold × the source's own
                            pick values)
    + 0.05 × AgeCurve     (z-scored; -avg age across the whole roster incl.
                            taxi; young = bonus)

All three components — and the composite — are untethered z-scores
((x - mean) / population stdev), not mapped onto a 0-100 scale. A score of
0 means league-average; positive/negative reflect how many standard
deviations above/below average a team is. This is intentionally more
sensitive to genuine outliers (e.g. a team holding most of the league's
first-round draft capital) than the old min-max normalization, which
compressed everyone else toward the bottom whenever one team was way out front.

Roster: KTC publishes its own per-team dynasty value on its league page, so we
  use that number directly for KTC rather than re-summing our own matched
  player values (it's KTC's own number, and KTC's own dynasty rankings are
  exactly what owners compare themselves against). FantasyCalc and
  DynastyProcess don't publish a per-team total, so they keep the
  computed-sum approach (active + bench + taxi squad, taxi discounted to 80%).
Draft capital: uses a source's own pick-ownership feed when it has one (KTC,
  synced from Sleeper), else reconstructs ownership from transaction history;
  covers 3 future seasons (current+1 through current+3), 3 rounds each. Pick
  value is the source's own quoted price, averaged across tiers (no per-pick
  slot prediction pre-season) and falling back to the nearest season a source
  actually prices when one of the 3 years isn't covered.
Age curve: simple (non-value-weighted) average age across the full roster —
  active and taxi squad alike, no top-N cap. Younger = higher raw score
  (we score -avg_age, then z-score it like everything else).

Returns {} when no dynasty value data has been scraped yet.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict


_TAXI_DISCOUNT   = 0.80   # taxi players counted at 80% of value
_FUTURE_YEARS    = 3      # how many future draft years to value (NNBE allows 3)
_ROUNDS          = 3      # NNBE rookie draft rounds per year

# Who currently owns a pick is a fact about the league's trade history, not
# about a valuation source's methodology -- KTC's feed is Sleeper-synced and
# authoritative, so every source borrows it when it lacks its own ownership
# feed, rather than each falling back independently to our own (incomplete)
# transaction-history reconstruction.
_AUTHORITATIVE_OWNERSHIP_SOURCE = "ktc"

_W_ROSTER  = 0.60
_W_CAPITAL = 0.35
_W_AGE     = 0.05


def _zscore(values: dict[str, float]) -> dict[str, float]:
    """Untethered z-score: (x - mean) / population stdev.

    Returns 0.0 for everyone if there's no spread (stdev == 0), since z-scoring
    a constant is undefined and 0 ("league average") is the natural neutral value.
    """
    if not values:
        return {}
    n = len(values)
    mean = sum(values.values()) / n
    variance = sum((v - mean) ** 2 for v in values.values()) / n
    stdev = variance ** 0.5
    if stdev == 0:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / stdev for k, v in values.items()}


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


def _pick_ownership_from_source(
    con: sqlite3.Connection,
    league_id: str,
    source: str,
) -> list[tuple[int, int, str]]:
    """Return [(season, round, current_user_id), ...] from a source's own
    authoritative ownership data (e.g. KTC's Sleeper-synced league page),
    if it has provided one. Empty list if the source doesn't supply this.
    """
    return con.execute(
        "SELECT season, round, user_id FROM pick_ownership WHERE source = ? AND league_id = ?",
        (source, league_id),
    ).fetchall()


def _pick_ownership_reconstructed(
    con: sqlite3.Connection,
    league_id: str,
    current_season: int,
) -> list[tuple[int, int, str]]:
    """Return [(season, round, current_user_id), ...] reconstructed from our
    own transaction history. Fallback for sources with no ownership feed.
    """
    pick_owners = _current_pick_owners(con, league_id, current_season)
    rid_to_uid = dict(
        con.execute(
            "SELECT roster_id, user_id FROM league_owners WHERE league_id = ?",
            (league_id,),
        ).fetchall()
    )
    result = []
    for (_season, _rnd, _orig_rid), current_rid in pick_owners.items():
        uid = rid_to_uid.get(current_rid)
        if uid:
            result.append((_season, _rnd, uid))
    return result


def _pick_value(con: sqlite3.Connection, source: str, season: int, rnd: int) -> float:
    """Look up a future pick's dynasty value for a given season/round.

    Tiers are averaged rather than guessed from standings — pre-season, there's
    no real basis for predicting where a team will finish. When a source's pick
    pricing doesn't cover a given season (e.g. KTC only prices ~2 draft classes
    out, but we track 3), falls back to the nearest season it does price for
    the same round rather than silently contributing zero.
    """
    rows = con.execute(
        "SELECT value FROM pick_dynasty_values WHERE source = ? AND season = ? AND round = ?",
        (source, season, rnd),
    ).fetchall()
    if not rows:
        candidates = [
            r[0] for r in con.execute(
                "SELECT DISTINCT season FROM pick_dynasty_values WHERE source = ? AND round = ?",
                (source, rnd),
            ).fetchall()
        ]
        if not candidates:
            return 0.0
        nearest_season = min(candidates, key=lambda s: abs(s - season))
        rows = con.execute(
            "SELECT value FROM pick_dynasty_values WHERE source = ? AND season = ? AND round = ?",
            (source, nearest_season, rnd),
        ).fetchall()
    return sum(r[0] for r in rows) / len(rows) if rows else 0.0


# ---------------------------------------------------------------------------
# Component computations
# ---------------------------------------------------------------------------

def _roster_values(
    con: sqlite3.Connection,
    league_id: str,
    source: str,
) -> dict[str, float]:
    """Return {user_id: raw_roster_value} using the given valuation source.

    Prefers a source's own published per-team total (currently only KTC
    provides one) over re-summing our own matched player values, since it's
    the source's own number and is what owners actually compare themselves
    against on that site. Sources with no published total fall back to the
    computed sum (active + bench + taxi squad, taxi discounted).
    """
    published = con.execute(
        "SELECT user_id, total FROM team_totals WHERE source = ? AND league_id = ?",
        (source, league_id),
    ).fetchall()
    if published:
        return {user_id: total for user_id, total in published}

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
               WHERE cr.league_id = ? AND cr.roster_id = ? AND pdv.value > 0
                 AND pdv.source = ?""",
            (league_id, roster_id, source),
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
    source: str,
) -> dict[str, float]:
    """Return {user_id: raw_draft_capital_value}.

    Ownership lookup order: (1) the source's own authoritative pick-ownership
    feed if it has one, (2) another source's authoritative feed (currently
    only KTC, synced from Sleeper) since pick ownership is a fact about the
    league, not the valuation source, (3) our own transaction-history
    reconstruction, which has known gaps for some future-pick trades. Pricing
    always uses the requested source's own pick values regardless of which
    ownership feed was used.
    """
    # Check pick value data exists for this source
    if not con.execute(
        "SELECT 1 FROM pick_dynasty_values WHERE source = ? LIMIT 1", (source,)
    ).fetchone():
        return {}

    pick_rows = _pick_ownership_from_source(con, league_id, source)
    if not pick_rows and source != _AUTHORITATIVE_OWNERSHIP_SOURCE:
        pick_rows = _pick_ownership_from_source(con, league_id, _AUTHORITATIVE_OWNERSHIP_SOURCE)
    if not pick_rows:
        pick_rows = _pick_ownership_reconstructed(con, league_id, current_season)

    capital: dict[str, float] = defaultdict(float)
    for season, rnd, uid in pick_rows:
        capital[uid] += _pick_value(con, source, season, rnd)

    return dict(capital)


def _age_curve_values(
    con: sqlite3.Connection,
    league_id: str,
    source: str,
) -> dict[str, float]:
    """Return {user_id: -avg_age} — higher (less negative) is younger/better.

    Simple mean age across the entire roster, active and taxi squad alike
    (no value-weighting, no top-N cap). The negation just orients the raw
    score so a higher value means younger, ready to be z-scored upstream.
    """
    owner_rows = con.execute(
        "SELECT lo.user_id, lo.roster_id FROM league_owners lo WHERE lo.league_id = ?",
        (league_id,),
    ).fetchall()

    scores: dict[str, float] = {}

    for user_id, roster_id in owner_rows:
        rows = con.execute(
            """SELECT pdv.age
               FROM current_rosters cr
               JOIN player_dynasty_values pdv ON cr.player_id = pdv.player_id
               WHERE cr.league_id = ? AND cr.roster_id = ?
                 AND pdv.age > 0 AND pdv.source = ?""",
            (league_id, roster_id, source),
        ).fetchall()

        if not rows:
            continue

        avg_age = sum(a for (a,) in rows) / len(rows)
        scores[user_id] = -avg_age

    return scores


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_available_dynasty_sources(con: sqlite3.Connection) -> list[str]:
    """Return the distinct valuation sources that currently have data."""
    return [
        r[0] for r in con.execute(
            "SELECT DISTINCT source FROM player_dynasty_values ORDER BY source"
        ).fetchall()
    ]


def compute_dynasty_rankings(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
    source: str = "dynastyprocess",
) -> dict:
    """Compute dynasty power rankings for a league using one valuation source.

    Returns: {season, data_date, rows} where rows are sorted by composite desc.
    Returns {} when no dynasty value data exists for this source.
    """
    # Check whether dynasty data exists for this source
    count = con.execute(
        "SELECT COUNT(*) FROM player_dynasty_values WHERE source = ?", (source,)
    ).fetchone()[0]
    if count == 0:
        return {"season": season, "data_date": None, "rows": []}

    data_date = (
        con.execute(
            "SELECT MAX(scraped_at) FROM player_dynasty_values WHERE source = ?", (source,)
        ).fetchone()[0]
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

    # Components — raw values per owner
    rv_raw  = _roster_values(con, league_id, source)
    dc_raw  = _draft_capital_values(con, league_id, season, source)
    age_raw = _age_curve_values(con, league_id, source)

    # Missing roster/capital data is a genuine zero (empty roster / no future
    # picks), so it's scored as-is. Missing age data (no age info for any
    # rostered player) has no real "zero" — default to the league's own mean
    # so it lands at a neutral z-score instead of skewing as fake-best/worst.
    age_mean = sum(age_raw.values()) / len(age_raw) if age_raw else 0.0

    rv_z  = _zscore({uid: rv_raw.get(uid, 0.0) for uid in uids})
    dc_z  = _zscore({uid: dc_raw.get(uid, 0.0) for uid in uids})
    age_z = _zscore({uid: age_raw.get(uid, age_mean) for uid in uids})

    # Composite — weighted sum of untethered z-scores (can be negative)
    power: dict[str, float] = {
        uid: (
            _W_ROSTER * rv_z.get(uid, 0.0)
            + _W_CAPITAL * dc_z.get(uid, 0.0)
            + _W_AGE * age_z.get(uid, 0.0)
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
            "composite":     round(power[uid], 2),
            "roster_score":  round(rv_z.get(uid, 0.0), 2),
            "capital_score": round(dc_z.get(uid, 0.0), 2),
            "age_score":     round(age_z.get(uid, 0.0), 2),
            "actual_wins":   wins_by_uid.get(uid, 0),
            "actual_losses": losses_by_uid.get(uid, 0),
            "pts_for":       pts_by_uid.get(uid, 0.0),
        })

    return {"season": season, "data_date": data_date, "rows": rows}


def compute_dynasty_rankings_overall(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
) -> dict:
    """Blend dynasty rankings across every available valuation source.

    Averages each owner's Roster/Capital/Age z-score across every source
    first, then rebuilds the composite from those blended components using
    the same 60/35/5 weights as a single-source view. Because weighted
    averaging is linear, this gives the exact same composite as averaging
    each source's own composite would — but it also yields a real per-category
    breakdown (Overall shows Roster/Capital/Age columns, same as any single
    source) instead of an opaque list of per-site totals. Each source's own
    scale/bias is stripped out before the cross-source average is taken in
    either case. Returns {} (empty rows) when no source has any data.
    """
    per_source: dict[str, dict] = {}
    for source in get_available_dynasty_sources(con):
        result = compute_dynasty_rankings(con, league_id, season, source)
        if result["rows"]:
            per_source[source] = result

    if not per_source:
        return {"season": season, "data_date": None, "rows": []}

    data_dates = [r["data_date"] for r in per_source.values() if r["data_date"]]
    data_date = max(data_dates) if data_dates else ""

    owner_components: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"roster_score": [], "capital_score": [], "age_score": []}
    )
    owner_context: dict[str, dict] = {}
    for result in per_source.values():
        for row in result["rows"]:
            comps = owner_components[row["owner"]]
            comps["roster_score"].append(row["roster_score"])
            comps["capital_score"].append(row["capital_score"])
            comps["age_score"].append(row["age_score"])
            owner_context[row["owner"]] = {
                "actual_wins":   row["actual_wins"],
                "actual_losses": row["actual_losses"],
                "pts_for":       row["pts_for"],
            }

    blended: dict[str, dict[str, float]] = {}
    for owner, comps in owner_components.items():
        roster  = sum(comps["roster_score"])  / len(comps["roster_score"])
        capital = sum(comps["capital_score"]) / len(comps["capital_score"])
        age     = sum(comps["age_score"])     / len(comps["age_score"])
        composite = _W_ROSTER * roster + _W_CAPITAL * capital + _W_AGE * age
        blended[owner] = {
            "roster_score":  round(roster, 2),
            "capital_score": round(capital, 2),
            "age_score":     round(age, 2),
            "composite":     round(composite, 2),
        }

    sorted_owners = sorted(blended, key=lambda o: -blended[o]["composite"])

    rows = []
    for rank, owner in enumerate(sorted_owners, 1):
        rows.append({
            "rank":   rank,
            "owner":  owner,
            **blended[owner],
            **owner_context[owner],
        })

    return {"season": season, "data_date": data_date, "rows": rows}
