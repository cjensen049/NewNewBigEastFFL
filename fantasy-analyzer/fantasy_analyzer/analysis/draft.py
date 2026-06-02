"""Draft analysis — per-season draft boards and owner draft history."""

from __future__ import annotations

import json
import sqlite3


def get_draft_seasons(con: sqlite3.Connection) -> list[int]:
    """List of seasons with draft data, newest first."""
    rows = con.execute(
        "SELECT DISTINCT season FROM draft_picks ORDER BY season DESC"
    ).fetchall()
    return [r[0] for r in rows]


def get_draft_board(con: sqlite3.Connection, season: int) -> dict:
    """All picks for one season, structured for grid display.

    Returns picks as a flat list plus slot→owner mapping so the frontend can
    render a draft board (rows = rounds, columns = draft slots).
    """
    rows = con.execute(
        """
        SELECT
            dp.round,
            dp.pick_no,
            dp.draft_slot,
            COALESCE(o.canonical_name, dp.user_id, 'Unknown') AS owner,
            COALESCE(dp.player_name, '—') AS player_name,
            COALESCE(pl.position, '') AS position,
            d.type AS draft_type
        FROM draft_picks dp
        JOIN drafts d ON d.draft_id = dp.draft_id
        LEFT JOIN owners o ON o.user_id = dp.user_id
        LEFT JOIN players pl ON pl.player_id = dp.player_id
        WHERE dp.season = ?
        ORDER BY dp.round, dp.pick_no
        """,
        (season,),
    ).fetchall()

    if not rows:
        return {"season": season, "draft_type": None, "num_rounds": 0, "num_teams": 12, "slot_owners": {}, "picks": []}

    draft_type = rows[0][6] or "snake"

    # Infer team count from how many picks are in round 1.
    round1 = [r for r in rows if r[0] == 1]
    num_teams = len(round1) if round1 else 12

    picks = []
    for r in rows:
        round_num, pick_no, draft_slot, owner, player_name, position, _ = r

        # Compute draft_slot when missing from the DB (migration added it later).
        if draft_slot is None:
            pos = (pick_no - 1) % num_teams  # 0-indexed position within the round
            if draft_type == "linear" or round_num % 2 == 1:
                draft_slot = pos + 1
            else:
                draft_slot = num_teams - pos  # even rounds run in reverse (snake)

        picks.append({
            "round": round_num,
            "pick_no": pick_no,
            "draft_slot": draft_slot,
            "owner": owner,
            "player_name": player_name,
            "position": position,
        })

    num_rounds = max(p["round"] for p in picks)

    # Map each draft slot to the owner who holds it (stable across rounds).
    slot_owners: dict[int, str] = {}
    for p in picks:
        slot = p["draft_slot"]
        if slot not in slot_owners:
            slot_owners[slot] = p["owner"]

    return {
        "season": season,
        "draft_type": draft_type,
        "num_rounds": num_rounds,
        "num_teams": num_teams,
        "slot_owners": slot_owners,
        "picks": picks,
    }


def get_owners_with_picks(con: sqlite3.Connection) -> list[dict]:
    """Owners who have at least one draft pick, for the selector."""
    rows = con.execute(
        """
        SELECT DISTINCT
            COALESCE(o.canonical_name, dp.user_id) AS owner,
            dp.user_id
        FROM draft_picks dp
        LEFT JOIN owners o ON o.user_id = dp.user_id
        WHERE dp.user_id IS NOT NULL
        ORDER BY owner
        """
    ).fetchall()
    return [{"owner": r[0], "user_id": r[1]} for r in rows]


def get_owner_picks(con: sqlite3.Connection, user_id: str) -> list[dict]:
    """All picks by one owner across all seasons, ordered by season then pick."""
    rows = con.execute(
        """
        SELECT
            dp.season,
            d.type AS draft_type,
            dp.round,
            dp.pick_no,
            COALESCE(dp.player_name, '—') AS player_name,
            COALESCE(pl.position, '') AS position
        FROM draft_picks dp
        JOIN drafts d ON d.draft_id = dp.draft_id
        LEFT JOIN players pl ON pl.player_id = dp.player_id
        WHERE dp.user_id = ?
        ORDER BY dp.season, dp.round, dp.pick_no
        """,
        (user_id,),
    ).fetchall()

    return [
        {
            "season": r[0],
            "draft_type": r[1],
            "round": r[2],
            "pick_no": r[3],
            "player_name": r[4],
            "position": r[5],
        }
        for r in rows
    ]


def _resolve_current_owners(
    con: sqlite3.Connection,
    player_ids: set[str],
    drafter_user_id: str,
) -> dict[str, str]:
    """Walk transactions newest-to-oldest to find the current NNBE owner of each player.

    - A player last seen in adds_json → current owner is the receiving team.
    - A player last seen in drops_json (but not in the same transaction's adds) → Free Agent.
    - A player with no transaction history → still with the original drafter.
    """
    if not player_ids:
        return {}

    user_to_name: dict[str, str] = dict(
        con.execute("SELECT user_id, canonical_name FROM owners").fetchall()
    )

    # Build (league_id, roster_id) → user_id for all seasons so trade-era roster_ids resolve.
    lo_rows = con.execute("SELECT league_id, roster_id, user_id FROM league_owners").fetchall()
    league_roster_to_user: dict[tuple, str] = {
        (r[0], int(r[1])): r[2] for r in lo_rows
    }

    tx_rows = con.execute(
        """
        SELECT league_id, adds_json, drops_json
        FROM transactions
        WHERE adds_json IS NOT NULL OR drops_json IS NOT NULL
        ORDER BY season DESC, week DESC, created_epoch DESC
        """
    ).fetchall()

    current_owners: dict[str, str] = {}
    remaining = set(player_ids)

    for league_id, adds_str, drops_str in tx_rows:
        if not remaining:
            break

        # Adds must be checked first: in a trade the same player appears in both
        # adds and drops; the add reflects the new owner.
        if adds_str:
            try:
                for pid, roster_id in json.loads(adds_str).items():
                    if pid in remaining:
                        uid = league_roster_to_user.get((league_id, int(roster_id)))
                        if uid:
                            current_owners[pid] = user_to_name.get(uid, uid)
                            remaining.discard(pid)
            except (ValueError, TypeError):
                pass

        # Drops with no matching add in this transaction = player was released.
        if drops_str:
            try:
                for pid in json.loads(drops_str):
                    if pid in remaining:
                        current_owners[pid] = "Free Agent"
                        remaining.discard(pid)
            except (ValueError, TypeError):
                pass

    # Players with no transactions are still on the original drafter's roster.
    drafter_name = user_to_name.get(drafter_user_id, drafter_user_id)
    for pid in remaining:
        current_owners[pid] = drafter_name

    return current_owners


def get_owner_picks_with_points(con: sqlite3.Connection, user_id: str) -> list[dict]:
    """All picks by one owner with points on roster, total league points, and current NNBE owner.

    - points_on_team: fantasy points scored while on THIS owner's roster (trade-aware)
    - total_points:   fantasy points scored across ALL matchups in the league
    - current_owner:  which NNBE owner currently holds the player ("Free Agent" if unclaimed)
    """
    picks_rows = con.execute(
        """
        SELECT
            dp.season,
            d.type AS draft_type,
            dp.round,
            dp.pick_no,
            dp.player_id,
            COALESCE(dp.player_name, '—') AS player_name,
            COALESCE(pl.position, '') AS position
        FROM draft_picks dp
        JOIN drafts d ON d.draft_id = dp.draft_id
        LEFT JOIN players pl ON pl.player_id = dp.player_id
        WHERE dp.user_id = ?
        ORDER BY dp.season, dp.round, dp.pick_no
        """,
        (user_id,),
    ).fetchall()

    picks = [
        {
            "season": r[0],
            "draft_type": r[1],
            "round": r[2],
            "pick_no": r[3],
            "player_id": r[4],
            "player_name": r[5],
            "position": r[6],
        }
        for r in picks_rows
    ]

    # One pass through ALL matchup rows: compute both owner-specific and league-wide totals.
    all_matchup_rows = con.execute(
        "SELECT user_id, players_points_json FROM matchups WHERE players_points_json IS NOT NULL"
    ).fetchall()

    owner_totals: dict[str, float] = {}
    league_totals: dict[str, float] = {}

    for row_user_id, json_str in all_matchup_rows:
        try:
            week_pts = json.loads(json_str)
            for pid, pts in week_pts.items():
                if pts:
                    pts_f = float(pts)
                    league_totals[pid] = league_totals.get(pid, 0.0) + pts_f
                    if row_user_id == user_id:
                        owner_totals[pid] = owner_totals.get(pid, 0.0) + pts_f
        except (ValueError, TypeError):
            pass

    # Resolve current NNBE owner for each drafted player.
    player_ids = {p["player_id"] for p in picks if p["player_id"]}
    current_owners = _resolve_current_owners(con, player_ids, user_id)

    for pick in picks:
        pid = pick["player_id"] or ""
        pick["points_on_team"] = round(owner_totals.get(pid, 0.0), 1)
        pick["total_points"] = round(league_totals.get(pid, 0.0), 1)
        pick["current_owner"] = current_owners.get(pid, "Free Agent")

    return picks
