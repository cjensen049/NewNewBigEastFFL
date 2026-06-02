"""Draft analysis — per-season draft boards and owner draft history."""

from __future__ import annotations

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
