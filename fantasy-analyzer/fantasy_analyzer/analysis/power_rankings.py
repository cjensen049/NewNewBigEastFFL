"""In-season power rankings for NNBE.

Formula (weights shift by season phase):
  PowerScore = w_scoring * ScoringComponent   (EWA of weekly scores, recent weeks weighted more)
             + w_record  * RecordComponent    (luck-adjusted sim win%)
             + w_sos     * SoSComponent       (inverse remaining schedule strength)

Phase weights:
  Early  (wks 1–4):   scoring=0.25, record=0.20, sos=0.55
  Mid    (wks 5–10):  scoring=0.45, record=0.40, sos=0.15
  Late   (wks 11–14): scoring=0.55, record=0.40, sos=0.05

Playoff odds via Monte Carlo simulation (10,000 runs) using NNBE rules:
  - Top 4 by W-L record (ties broken by total pts)
  - Next 2 by total pts (not already in top 4)
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict

import numpy as np

# ---------------------------------------------------------------------------
# Phase configuration
# ---------------------------------------------------------------------------

# Weights when roster quality data IS available (FantasyPros projections scraped)
PHASES: dict[str, dict] = {
    "early": {
        "label": "Early Season",
        "weights": {"scoring": 0.15, "record": 0.10, "sos": 0.25, "roster": 0.50},
    },
    "mid": {
        "label": "Mid Season",
        "weights": {"scoring": 0.35, "record": 0.30, "sos": 0.10, "roster": 0.25},
    },
    "late": {
        "label": "Late Season",
        "weights": {"scoring": 0.45, "record": 0.35, "sos": 0.05, "roster": 0.15},
    },
}

# Fallback weights when no roster quality data is available
PHASES_NO_ROSTER: dict[str, dict] = {
    "early": {
        "label": "Early Season",
        "weights": {"scoring": 0.25, "record": 0.20, "sos": 0.55, "roster": 0.0},
    },
    "mid": {
        "label": "Mid Season",
        "weights": {"scoring": 0.45, "record": 0.40, "sos": 0.15, "roster": 0.0},
    },
    "late": {
        "label": "Late Season",
        "weights": {"scoring": 0.55, "record": 0.40, "sos": 0.05, "roster": 0.0},
    },
}

_PLAYOFF_SPOTS   = 6
_TOP_BY_RECORD   = 4
_N_SIMS_DEFAULT  = 10_000
_EWA_DECAY       = 0.85


def _phase(week: int) -> str:
    """Return 'early', 'mid', or 'late' based on current week."""
    if week <= 4:   return "early"
    if week <= 10:  return "mid"
    return "late"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _weekly_scores(
    con: sqlite3.Connection,
    league_id: str,
    pws: int,
    max_week: int,
) -> dict[str, list[float]]:
    """Return {user_id: [score_wk1, score_wk2, ...]} through max_week."""
    rows = con.execute(
        """SELECT user_id, week, points
           FROM matchups
           WHERE league_id=? AND week < ? AND week <= ?
             AND points IS NOT NULL AND points > 0
           ORDER BY user_id, week""",
        (league_id, pws, max_week),
    ).fetchall()
    scores: dict[str, list[float]] = defaultdict(list)
    for uid, _, pts in rows:
        scores[uid].append(float(pts))
    return dict(scores)


def _ewa(scores: list[float], decay: float = _EWA_DECAY) -> float:
    """Exponentially weighted average — most recent week gets weight 1, prior weeks decay."""
    if not scores:
        return 0.0
    n = len(scores)
    weights = [decay ** (n - 1 - i) for i in range(n)]
    total_w = sum(weights)
    return sum(w * s for w, s in zip(weights, scores)) / total_w


def _sim_win_pcts(
    con: sqlite3.Connection,
    league_id: str,
    pws: int,
    max_week: int,
) -> dict[str, float]:
    """Luck-adjusted sim win%: each team vs every other team each week, through max_week."""
    rows = con.execute(
        """SELECT week, user_id, points
           FROM matchups
           WHERE league_id=? AND week < ? AND week <= ?
             AND points IS NOT NULL AND points > 0
           ORDER BY week""",
        (league_id, pws, max_week),
    ).fetchall()

    week_scores: dict[int, list[tuple[str, float]]] = defaultdict(list)
    for week, uid, pts in rows:
        week_scores[week].append((uid, float(pts)))

    sim_wins:  dict[str, int] = defaultdict(int)
    sim_games: dict[str, int] = defaultdict(int)

    for scores in week_scores.values():
        if len(scores) < 2:
            continue
        for uid_i, pts_i in scores:
            for uid_j, pts_j in scores:
                if uid_j == uid_i:
                    continue
                sim_games[uid_i] += 1
                if pts_i > pts_j:
                    sim_wins[uid_i] += 1

    all_uids = {uid for scores in week_scores.values() for uid, _ in scores}
    return {
        uid: sim_wins[uid] / sim_games[uid] if sim_games[uid] else 0.0
        for uid in all_uids
    }


def _remaining_sos(
    con: sqlite3.Connection,
    league_id: str,
    current_week: int,
    pws: int,
    win_pct_by_uid: dict[str, float],
) -> dict[str, float | None]:
    """Remaining schedule SoS: average current win% of future opponents per user."""
    rows = con.execute(
        """SELECT week, matchup_id, user_id
           FROM matchups
           WHERE league_id=? AND week > ? AND week < ?
           ORDER BY week, matchup_id""",
        (league_id, current_week, pws),
    ).fetchall()

    pairs: dict[tuple, list[str]] = defaultdict(list)
    for week, mid, uid in rows:
        pairs[(week, mid)].append(uid)

    opp_wps: dict[str, list[float]] = defaultdict(list)
    for users in pairs.values():
        if len(users) == 2:
            uid_a, uid_b = users
            if uid_b in win_pct_by_uid:
                opp_wps[uid_a].append(win_pct_by_uid[uid_b])
            if uid_a in win_pct_by_uid:
                opp_wps[uid_b].append(win_pct_by_uid[uid_a])

    return {uid: sum(wps) / len(wps) if wps else None for uid, wps in opp_wps.items()}


def _remaining_schedule(
    con: sqlite3.Connection,
    league_id: str,
    current_week: int,
    pws: int,
) -> list[list[tuple[str, str]]]:
    """Return [[( uid_a, uid_b ), ...], ...] for each remaining regular-season week."""
    rows = con.execute(
        """SELECT week, matchup_id, user_id
           FROM matchups
           WHERE league_id=? AND week > ? AND week < ?
           ORDER BY week, matchup_id""",
        (league_id, current_week, pws),
    ).fetchall()

    by_week: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for week, mid, uid in rows:
        by_week[week][mid].append(uid)

    schedule = []
    for week in sorted(by_week):
        pairs = [(uids[0], uids[1]) for uids in by_week[week].values() if len(uids) == 2]
        if pairs:
            schedule.append(pairs)
    return schedule


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Min-max normalize to 0–100. Returns 50.0 for all if no spread."""
    if not values:
        return {}
    mn, mx = min(values.values()), max(values.values())
    if mx == mn:
        return {k: 50.0 for k in values}
    return {k: (v - mn) / (mx - mn) * 100.0 for k, v in values.items()}


# ---------------------------------------------------------------------------
# Monte Carlo simulation
# ---------------------------------------------------------------------------

def _monte_carlo(
    uids: list[str],
    base_wins: dict[str, int],
    base_pts:  dict[str, float],
    means:     dict[str, float],
    stds:      dict[str, float],
    schedule:  list[list[tuple[str, str]]],
    n_sims:    int = _N_SIMS_DEFAULT,
) -> dict[str, float]:
    """Simulate remaining schedule n_sims times; return {uid: playoff_pct}.

    Uses fully-vectorised numpy: all sims run in parallel per remaining week.
    """
    rng = np.random.default_rng()
    uid_idx = {uid: i for i, uid in enumerate(uids)}
    n = len(uids)

    mu_arr  = np.array([means.get(uid, 120.0) for uid in uids])
    sig_arr = np.array([stds.get(uid, 20.0)   for uid in uids])

    # Accumulate across remaining weeks (vectorised per week)
    sim_wins = np.tile([float(base_wins.get(u, 0)) for u in uids], (n_sims, 1))
    sim_pts  = np.tile([float(base_pts.get(u, 0.0)) for u in uids], (n_sims, 1))

    for week_pairs in schedule:
        ia = np.array([uid_idx[a] for a, b in week_pairs if a in uid_idx and b in uid_idx])
        ib = np.array([uid_idx[b] for a, b in week_pairs if a in uid_idx and b in uid_idx])
        if len(ia) == 0:
            continue

        # Draw scores for every team this week: (n_sims, n_teams)
        week_scores = np.maximum(rng.normal(mu_arr, sig_arr, size=(n_sims, n)), 0.0)

        for g in range(len(ia)):
            a_won = week_scores[:, ia[g]] > week_scores[:, ib[g]]
            sim_wins[:, ia[g]] += a_won.astype(np.float64)
            sim_wins[:, ib[g]] += (~a_won).astype(np.float64)
            sim_pts[:, ia[g]] += week_scores[:, ia[g]]
            sim_pts[:, ib[g]] += week_scores[:, ib[g]]

    # Determine playoff teams per sim using NNBE rules (vectorised)
    # Sort by (-wins, -pts): lexsort sorts ascending, so negate
    sort_keys = -(sim_wins * 1e9 + sim_pts)
    order = np.argsort(sort_keys, axis=1)                # (n_sims, n_teams)

    top4      = order[:, :_TOP_BY_RECORD]               # (n_sims, 4)
    remainder = order[:, _TOP_BY_RECORD:]               # (n_sims, 8)

    # Among remainder, sort by pts desc for wild-card spots
    rem_pts  = sim_pts[np.arange(n_sims)[:, None], remainder]
    rem_ord  = np.argsort(-rem_pts, axis=1)
    wild2    = remainder[np.arange(n_sims)[:, None], rem_ord[:, :(_PLAYOFF_SPOTS - _TOP_BY_RECORD)]]

    in_playoffs = np.zeros((n_sims, n), dtype=bool)
    np.put_along_axis(in_playoffs, top4,  True, axis=1)
    np.put_along_axis(in_playoffs, wild2, True, axis=1)

    counts = in_playoffs.sum(axis=0)
    return {uid: round(float(counts[uid_idx[uid]]) / n_sims * 100, 1) for uid in uids}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compute_power_rankings(
    con: sqlite3.Connection,
    league_id: str,
    season: int,
    pws: int,
    n_sims: int = _N_SIMS_DEFAULT,
) -> dict:
    """Compute in-season power rankings.

    Returns: {season, current_week, phase, phase_label, weights, rows}
    Rows sorted by power_score descending.
    """
    # ── Current week ──────────────────────────────────────────────────────────
    row = con.execute(
        "SELECT MAX(week) FROM matchups WHERE league_id=? AND is_playoff=0 AND points IS NOT NULL AND points > 0",
        (league_id,),
    ).fetchone()
    current_week: int = row[0] or 0

    if current_week == 0:
        phase_key = "early"
        return {
            "season": season,
            "current_week": 0,
            "phase": phase_key,
            "phase_label": PHASES_NO_ROSTER[phase_key]["label"],
            "weights": PHASES_NO_ROSTER[phase_key]["weights"],
            "rows": [],
        }

    # For trend: use max(current_week - 1, 1) so week 1 shows neutral trends
    prev_week = max(current_week - 1, 1)
    phase_key = _phase(current_week)

    # Choose phase table based on whether roster quality data exists
    from fantasy_analyzer.analysis.roster_quality import compute_roster_quality
    roster_quality_raw = compute_roster_quality(con, league_id, season)
    has_roster_data = bool(roster_quality_raw)
    phase_table = PHASES if has_roster_data else PHASES_NO_ROSTER
    weights = phase_table[phase_key]["weights"]

    # ── Owner list ────────────────────────────────────────────────────────────
    user_rows = con.execute(
        """SELECT lo.user_id, o.canonical_name
           FROM league_owners lo
           JOIN owners o ON lo.user_id = o.user_id
           WHERE lo.league_id = ?""",
        (league_id,),
    ).fetchall()
    user_to_name: dict[str, str] = {r[0]: r[1] for r in user_rows}
    uids = list(user_to_name.keys())

    if not uids:
        return {"season": season, "current_week": current_week, "phase": phase_key,
                "phase_label": PHASES[phase_key]["label"], "weights": weights, "rows": []}

    # ── Scoring component ─────────────────────────────────────────────────────
    sc_curr = _weekly_scores(con, league_id, pws, current_week)
    sc_prev = _weekly_scores(con, league_id, pws, prev_week)

    ewa_curr = {uid: _ewa(sc_curr.get(uid, [])) for uid in uids}
    ewa_prev = {uid: _ewa(sc_prev.get(uid, [])) for uid in uids}

    scoring_norm_curr = _normalize(ewa_curr)
    scoring_norm_prev = _normalize(ewa_prev)

    # ── Record component (sim win%) ───────────────────────────────────────────
    swp_curr = _sim_win_pcts(con, league_id, pws, current_week)
    swp_prev = _sim_win_pcts(con, league_id, pws, prev_week)

    record_norm_curr = _normalize(swp_curr)
    record_norm_prev = _normalize(swp_prev)

    # ── SoS component (remaining schedule, inverted) ──────────────────────────
    win_pct_by_uid = {uid: swp_curr.get(uid, 0.5) for uid in uids}
    sos_raw  = _remaining_sos(con, league_id, current_week, pws, win_pct_by_uid)
    sos_inv  = {uid: 1.0 - v for uid, v in sos_raw.items() if v is not None}
    sos_norm = _normalize(sos_inv) if sos_inv else {}
    sos_norm_full = {uid: sos_norm.get(uid, 50.0) for uid in uids}

    # ── Roster quality component ──────────────────────────────────────────────
    # Normalize raw projected pts; fall back to 50.0 per team if no data
    rq_values = {uid: v for uid, v in roster_quality_raw.items() if v is not None}
    rq_norm_map = _normalize(rq_values) if rq_values else {}
    rq_norm = {uid: rq_norm_map.get(uid, 50.0) for uid in uids}

    # ── Composite power score (current and previous week for trend) ───────────
    def _composite(sc_norm: dict, rc_norm: dict) -> dict[str, float]:
        return {
            uid: (
                weights["scoring"] * sc_norm.get(uid, 50.0)
                + weights["record"]  * rc_norm.get(uid, 50.0)
                + weights["sos"]     * sos_norm_full.get(uid, 50.0)
                + weights["roster"]  * rq_norm.get(uid, 50.0)
            )
            for uid in uids
        }

    power_curr = _composite(scoring_norm_curr, record_norm_curr)
    power_prev = _composite(scoring_norm_prev, record_norm_prev)

    rank_curr = {uid: r for r, uid in enumerate(sorted(uids, key=lambda u: -power_curr[u]), 1)}
    rank_prev = {uid: r for r, uid in enumerate(sorted(uids, key=lambda u: -power_prev[u]), 1)}

    # ── Actual standings for display ──────────────────────────────────────────
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
           WHERE m1.league_id=? AND m1.is_playoff=0
             AND m1.week < ? AND m1.week <= ?
             AND m1.points IS NOT NULL AND m1.points > 0
           GROUP BY m1.user_id""",
        (league_id, pws, current_week),
    ).fetchall()

    wins_by_uid:   dict[str, int]   = {r[0]: r[1] for r in standings}
    losses_by_uid: dict[str, int]   = {r[0]: r[2] for r in standings}
    pts_by_uid:    dict[str, float] = {r[0]: float(r[3]) for r in standings}

    # ── Score distribution for Monte Carlo ────────────────────────────────────
    score_means: dict[str, float] = {}
    score_stds:  dict[str, float] = {}
    for uid in uids:
        s = sc_curr.get(uid, [])
        if s:
            mu = sum(s) / len(s)
            score_means[uid] = mu
            score_stds[uid]  = max(math.sqrt(sum((x - mu) ** 2 for x in s) / len(s)), 10.0) if len(s) >= 2 else 20.0
        else:
            score_means[uid] = 120.0
            score_stds[uid]  = 20.0

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    sched = _remaining_schedule(con, league_id, current_week, pws)
    playoff_pcts = _monte_carlo(
        uids, wins_by_uid, pts_by_uid,
        score_means, score_stds, sched, n_sims=n_sims,
    )

    # ── Build output ──────────────────────────────────────────────────────────
    sorted_uids = sorted(uids, key=lambda u: -power_curr[u])
    rows = []
    for rank, uid in enumerate(sorted_uids, 1):
        prev = rank_prev.get(uid, rank)
        rows.append({
            "rank":          rank,
            "prev_rank":     prev,
            "trend":         prev - rank,        # positive = moved up
            "owner":         user_to_name[uid],
            "power_score":   round(power_curr[uid], 1),
            "playoff_pct":   playoff_pcts.get(uid, 0.0),
            "actual_wins":   wins_by_uid.get(uid, 0),
            "actual_losses": losses_by_uid.get(uid, 0),
            "pts_for":       pts_by_uid.get(uid, 0.0),
            "scoring_score": round(scoring_norm_curr.get(uid, 0.0), 1),
            "record_score":  round(record_norm_curr.get(uid, 0.0), 1),
            "sos_score":     round(sos_norm_full.get(uid, 0.0), 1),
            "roster_score":  round(rq_norm.get(uid, 0.0), 1) if has_roster_data else None,
        })

    return {
        "season":           season,
        "current_week":     current_week,
        "phase":            phase_key,
        "phase_label":      phase_table[phase_key]["label"],
        "weights":          weights,
        "has_roster_data":  has_roster_data,
        "rows":             rows,
    }
