"""Trade log, trade trees, and waiver wire analysis."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TradeAsset:
    asset_type: str          # 'player' or 'pick'
    asset_id: str            # player_id or pick descriptor e.g. "2023 R2 (Chase)"
    asset_name: str          # display name
    from_owner: str
    to_owner: str


@dataclass
class Trade:
    transaction_id: str
    season: int
    week: int
    owners: list[str]
    assets: list[TradeAsset] = field(default_factory=list)


@dataclass
class PlayerTradeStop:
    season: int
    week: int
    transaction_id: str
    from_owner: str
    to_owner: str


@dataclass
class OwnerTradeStats:
    canonical_name: str
    total_trades: int = 0
    players_acquired: int = 0
    players_sent: int = 0
    picks_acquired: int = 0
    picks_sent: int = 0
    total_faab_spent: int = 0
    total_waiver_claims: int = 0
    total_fa_adds: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _roster_to_owner(con: sqlite3.Connection) -> dict[tuple[str, int], str]:
    """Return {(league_id, roster_id): canonical_name}."""
    rows = con.execute(
        """
        SELECT lo.league_id, lo.roster_id, o.canonical_name
        FROM league_owners lo
        JOIN owners o ON lo.user_id = o.user_id
        """
    ).fetchall()
    return {(r[0], r[1]): r[2] for r in rows}


def _player_names(con: sqlite3.Connection) -> dict[str, str]:
    """Return {player_id: full_name}."""
    rows = con.execute("SELECT player_id, full_name FROM players").fetchall()
    return {r[0]: r[1] or r[0] for r in rows}


def _original_pick_owner(con: sqlite3.Connection, league_id: str, roster_map: dict) -> dict[int, str]:
    """Return {roster_id: canonical_name} for original pick owners in a league."""
    rows = con.execute(
        "SELECT roster_id FROM league_owners WHERE league_id = ?", (league_id,)
    ).fetchall()
    return {r[0]: roster_map.get((league_id, r[0]), f"Roster {r[0]}") for r in rows}


# ---------------------------------------------------------------------------
# Trade log
# ---------------------------------------------------------------------------

def get_trade_log(con: sqlite3.Connection) -> list[Trade]:
    """Return all trades enriched with player and pick assets."""
    roster_map = _roster_to_owner(con)
    player_names = _player_names(con)

    rows = con.execute(
        """
        SELECT transaction_id, league_id, season, week,
               adds_json, drops_json, roster_ids_json
        FROM transactions
        WHERE type = 'trade'
        ORDER BY season, week, transaction_id
        """
    ).fetchall()

    # Picks keyed by transaction_id
    pick_rows = con.execute(
        """
        SELECT transaction_id, season, round,
               original_roster_id, from_roster_id, to_roster_id
        FROM transaction_draft_picks
        """
    ).fetchall()
    picks_by_txn: dict[str, list] = {}
    for pr in pick_rows:
        picks_by_txn.setdefault(pr[0], []).append(pr[1:])

    trades: list[Trade] = []

    for txn_id, league_id, season, week, adds_raw, drops_raw, rids_raw in rows:
        adds = json.loads(adds_raw) if adds_raw else {}
        drops = json.loads(drops_raw) if drops_raw else {}
        roster_ids = json.loads(rids_raw) if rids_raw else []

        owners = [
            roster_map.get((league_id, rid), f"Roster {rid}")
            for rid in roster_ids
        ]

        trade = Trade(
            transaction_id=txn_id,
            season=season,
            week=week,
            owners=owners,
        )

        # Player assets — derive direction from adds/drops
        for pid, recv_rid in adds.items():
            send_rid = drops.get(pid)
            from_owner = roster_map.get((league_id, send_rid), "?") if send_rid else "?"
            to_owner = roster_map.get((league_id, recv_rid), f"Roster {recv_rid}")
            name = player_names.get(pid, f"Player {pid}")
            trade.assets.append(TradeAsset("player", pid, name, from_owner, to_owner))

        # Pick assets
        for pick_season, round_, orig_rid, from_rid, to_rid in picks_by_txn.get(txn_id, []):
            orig_owner = roster_map.get((league_id, orig_rid), f"Roster {orig_rid}")
            from_owner = roster_map.get((league_id, from_rid), f"Roster {from_rid}")
            to_owner = roster_map.get((league_id, to_rid), f"Roster {to_rid}")
            label = f"{pick_season} R{round_} ({orig_owner}'s pick)"
            trade.assets.append(TradeAsset("pick", f"{pick_season}_{round_}_{orig_rid}", label, from_owner, to_owner))

        trades.append(trade)

    return trades


# ---------------------------------------------------------------------------
# Player trade history / trade tree
# ---------------------------------------------------------------------------

def get_player_trade_history(
    con: sqlite3.Connection, player_name: str
) -> tuple[str | None, list[PlayerTradeStop]]:
    """
    Find all trades involving a player by name (case-insensitive substring).
    Returns (canonical_player_name, list of trade stops).
    """
    roster_map = _roster_to_owner(con)

    # Resolve player_id from name
    matches = con.execute(
        "SELECT player_id, full_name FROM players WHERE LOWER(full_name) LIKE LOWER(?)",
        (f"%{player_name}%",),
    ).fetchall()

    if not matches:
        return None, []

    # If multiple matches, prefer exact
    exact = [m for m in matches if m[1].lower() == player_name.lower()]
    player_id, player_full_name = (exact or matches)[0]

    rows = con.execute(
        """
        SELECT transaction_id, league_id, season, week, adds_json, drops_json
        FROM transactions
        WHERE type = 'trade'
          AND (adds_json LIKE ? OR drops_json LIKE ?)
        ORDER BY season, week
        """,
        (f'%"{player_id}"%', f'%"{player_id}"%'),
    ).fetchall()

    stops: list[PlayerTradeStop] = []
    for txn_id, league_id, season, week, adds_raw, drops_raw in rows:
        adds = json.loads(adds_raw) if adds_raw else {}
        drops = json.loads(drops_raw) if drops_raw else {}

        if player_id in adds:
            recv_rid = adds[player_id]
            send_rid = drops.get(player_id)
            from_owner = roster_map.get((league_id, send_rid), "?") if send_rid else "?"
            to_owner = roster_map.get((league_id, recv_rid), f"Roster {recv_rid}")
            stops.append(PlayerTradeStop(season, week, txn_id, from_owner, to_owner))

    return player_full_name, stops


def search_player_names(con: sqlite3.Connection, query: str) -> list[str]:
    """Return player full names matching a substring, limited to traded players."""
    rows = con.execute(
        """
        SELECT DISTINCT p.full_name
        FROM players p
        WHERE LOWER(p.full_name) LIKE LOWER(?)
          AND EXISTS (
              SELECT 1 FROM transactions t
              WHERE t.type = 'trade'
                AND (t.adds_json LIKE '%"' || p.player_id || '"%'
                     OR t.drops_json LIKE '%"' || p.player_id || '"%')
          )
        ORDER BY p.full_name
        LIMIT 20
        """,
        (f"%{query}%",),
    ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Owner trade tendencies
# ---------------------------------------------------------------------------

def get_owner_trade_stats(con: sqlite3.Connection) -> list[OwnerTradeStats]:
    """Compute per-owner trade and waiver stats."""
    roster_map = _roster_to_owner(con)
    player_names = _player_names(con)

    stats: dict[str, OwnerTradeStats] = {}

    def _get(name: str) -> OwnerTradeStats:
        if name not in stats:
            stats[name] = OwnerTradeStats(name)
        return stats[name]

    # Trades
    trade_rows = con.execute(
        """
        SELECT transaction_id, league_id, season, week,
               adds_json, drops_json, roster_ids_json
        FROM transactions
        WHERE type = 'trade'
        """
    ).fetchall()

    pick_rows = con.execute(
        """
        SELECT transaction_id, from_roster_id, to_roster_id,
               (SELECT league_id FROM transactions t WHERE t.transaction_id = transaction_draft_picks.transaction_id)
        FROM transaction_draft_picks
        """
    ).fetchall()

    picks_by_txn: dict[str, list] = {}
    for pr in pick_rows:
        picks_by_txn.setdefault(pr[0], []).append(pr[1:])

    seen_txn_per_owner: dict[tuple[str, str], bool] = {}

    for txn_id, league_id, season, week, adds_raw, drops_raw, rids_raw in trade_rows:
        adds = json.loads(adds_raw) if adds_raw else {}
        drops = json.loads(drops_raw) if drops_raw else {}
        roster_ids = json.loads(rids_raw) if rids_raw else []

        # Count trade participation per owner
        for rid in roster_ids:
            owner = roster_map.get((league_id, rid))
            if not owner:
                continue
            key = (owner, txn_id)
            if key not in seen_txn_per_owner:
                seen_txn_per_owner[key] = True
                _get(owner).total_trades += 1

        # Player movement
        for pid, recv_rid in adds.items():
            to_owner = roster_map.get((league_id, recv_rid))
            if to_owner:
                _get(to_owner).players_acquired += 1
            send_rid = drops.get(pid)
            if send_rid:
                from_owner = roster_map.get((league_id, send_rid))
                if from_owner:
                    _get(from_owner).players_sent += 1

        # Pick movement
        for from_rid, to_rid, pick_league_id in picks_by_txn.get(txn_id, []):
            from_owner = roster_map.get((league_id, from_rid))
            to_owner = roster_map.get((league_id, to_rid))
            if from_owner and from_owner != to_owner:
                _get(from_owner).picks_sent += 1
            if to_owner and from_owner != to_owner:
                _get(to_owner).picks_acquired += 1

    # Waivers / free agents
    wire_rows = con.execute(
        """
        SELECT league_id, type, adds_json, waiver_budget_json
        FROM transactions
        WHERE type IN ('waiver', 'free_agent')
        """
    ).fetchall()

    for league_id, txn_type, adds_raw, budget_raw in wire_rows:
        adds = json.loads(adds_raw) if adds_raw else {}
        for pid, recv_rid in adds.items():
            owner = roster_map.get((league_id, recv_rid))
            if not owner:
                continue
            st = _get(owner)
            if txn_type == 'waiver':
                st.total_waiver_claims += 1
                if budget_raw:
                    for entry in json.loads(budget_raw):
                        if entry.get("roster_id") == recv_rid:
                            st.total_faab_spent += entry.get("amount", 0)
            else:
                st.total_fa_adds += 1

    return sorted(stats.values(), key=lambda s: s.total_trades, reverse=True)


# ---------------------------------------------------------------------------
# Trade partner matrix
# ---------------------------------------------------------------------------

def get_trade_partner_matrix(con: sqlite3.Connection) -> dict[tuple[str, str], int]:
    """Return {(owner_a, owner_b): trade_count} for all pairs."""
    roster_map = _roster_to_owner(con)

    rows = con.execute(
        "SELECT league_id, roster_ids_json FROM transactions WHERE type = 'trade'"
    ).fetchall()

    matrix: dict[tuple[str, str], int] = {}
    for league_id, rids_raw in rows:
        rids = json.loads(rids_raw) if rids_raw else []
        owners = sorted(set(
            roster_map.get((league_id, rid))
            for rid in rids
            if roster_map.get((league_id, rid))
        ))
        if len(owners) >= 2:
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    pair = (owners[i], owners[j])
                    matrix[pair] = matrix.get(pair, 0) + 1

    return matrix
