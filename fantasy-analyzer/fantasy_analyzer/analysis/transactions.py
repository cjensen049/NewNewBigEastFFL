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


def get_all_traded_players(con: sqlite3.Connection) -> list[str]:
    """Return all player names who appear in at least one trade, sorted alphabetically."""
    rows = con.execute(
        """
        SELECT DISTINCT p.full_name
        FROM players p
        WHERE p.full_name IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM transactions t
              WHERE t.type = 'trade'
                AND (t.adds_json LIKE '%"' || p.player_id || '"%'
                     OR t.drops_json LIKE '%"' || p.player_id || '"%')
          )
        ORDER BY p.full_name
        """
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
# Waiver wire / FAAB analysis
# ---------------------------------------------------------------------------

def get_faab_records(con: sqlite3.Connection) -> dict:
    """
    Return FAAB-related records across all seasons.

    Keys:
        top_bids        — list of dicts for successful bids, desc by amount
        top_total_spent — per-player total FAAB won across all claims
        owner_totals    — per-owner all-time FAAB spent and claim counts
    """
    roster_map = _roster_to_owner(con)
    player_names_map = _player_names(con)

    rows = con.execute(
        """
        SELECT league_id, season, week, status, adds_json, roster_ids_json, waiver_bid_amount
        FROM transactions
        WHERE type = 'waiver' AND waiver_bid_amount IS NOT NULL AND waiver_bid_amount > 0
        ORDER BY waiver_bid_amount DESC
        """
    ).fetchall()

    top_bids: list[dict] = []
    player_total: dict[str, int] = {}
    owner_faab: dict[str, int] = {}
    owner_claims: dict[str, int] = {}

    for league_id, season, week, status, adds_raw, rids_raw, bid in rows:
        adds = json.loads(adds_raw) if adds_raw else {}
        rids = json.loads(rids_raw) if rids_raw else []
        owner = roster_map.get((league_id, rids[0])) if rids else None

        for pid in adds:
            name = player_names_map.get(pid, pid)
            if status == "complete":
                top_bids.append({
                    "player": name,
                    "owner": owner or "?",
                    "season": season,
                    "week": week,
                    "amount": bid,
                })
                player_total[name] = player_total.get(name, 0) + bid
                if owner:
                    owner_faab[owner] = owner_faab.get(owner, 0) + bid
                    owner_claims[owner] = owner_claims.get(owner, 0) + 1

    owner_totals = [
        {"owner": o, "faab_spent": owner_faab.get(o, 0), "claims": owner_claims.get(o, 0)}
        for o in sorted(owner_faab, key=lambda x: -owner_faab[x])
    ]

    top_total_spent = sorted(
        [{"player": p, "total_faab": v} for p, v in player_total.items()],
        key=lambda x: -x["total_faab"],
    )

    return {
        "top_bids": top_bids,
        "top_total_spent": top_total_spent,
        "owner_totals": owner_totals,
    }


def get_player_add_drop_stats(con: sqlite3.Connection) -> list[dict]:
    """
    Return per-player add/drop counts across all waiver and free-agent transactions.
    Sorted by total activity (adds + drops) descending.
    """
    player_names_map = _player_names(con)

    add_counts: dict[str, int] = {}
    drop_counts: dict[str, int] = {}

    for adds_raw, drops_raw in con.execute(
        """
        SELECT adds_json, drops_json FROM transactions
        WHERE type IN ('waiver', 'free_agent') AND status = 'complete'
        """
    ).fetchall():
        for pid in (json.loads(adds_raw) if adds_raw else {}):
            add_counts[pid] = add_counts.get(pid, 0) + 1
        for pid in (json.loads(drops_raw) if drops_raw else {}):
            drop_counts[pid] = drop_counts.get(pid, 0) + 1

    all_pids = set(add_counts) | set(drop_counts)
    rows = []
    for pid in all_pids:
        name = player_names_map.get(pid, pid)
        adds = add_counts.get(pid, 0)
        drops = drop_counts.get(pid, 0)
        rows.append({
            "player": name,
            "adds": adds,
            "drops": drops,
            "total_moves": adds + drops,
        })

    return sorted(rows, key=lambda x: -x["total_moves"])


def get_owner_waiver_activity(con: sqlite3.Connection) -> list[dict]:
    """
    Per-owner waiver wire summary: claims, FA adds, drops, FAAB spent, success rate.
    """
    roster_map = _roster_to_owner(con)

    stats: dict[str, dict] = {}

    def _s(owner: str) -> dict:
        if owner not in stats:
            stats[owner] = {
                "owner": owner,
                "waiver_claims": 0,
                "waiver_failed": 0,
                "fa_adds": 0,
                "drops": 0,
                "faab_spent": 0,
            }
        return stats[owner]

    for league_id, txn_type, status, adds_raw, drops_raw, rids_raw, bid in con.execute(
        """
        SELECT league_id, type, status, adds_json, drops_json, roster_ids_json, waiver_bid_amount
        FROM transactions
        WHERE type IN ('waiver', 'free_agent')
        """
    ).fetchall():
        rids = json.loads(rids_raw) if rids_raw else []
        owner = roster_map.get((league_id, rids[0])) if rids else None
        if not owner:
            # Try inferring from adds/drops
            adds = json.loads(adds_raw) if adds_raw else {}
            drops = json.loads(drops_raw) if drops_raw else {}
            for pid, rid in {**adds, **drops}.items():
                owner = roster_map.get((league_id, rid))
                if owner:
                    break
        if not owner:
            continue

        s = _s(owner)
        adds = json.loads(adds_raw) if adds_raw else {}
        drops = json.loads(drops_raw) if drops_raw else {}

        if txn_type == "waiver":
            if status == "complete":
                s["waiver_claims"] += 1
                if bid:
                    s["faab_spent"] += bid
            else:
                s["waiver_failed"] += 1
        else:  # free_agent
            if status == "complete":
                s["fa_adds"] += 1

        if status == "complete":
            s["drops"] += len(drops)

    result = []
    for s in stats.values():
        total_bids = s["waiver_claims"] + s["waiver_failed"]
        s["success_rate"] = s["waiver_claims"] / total_bids if total_bids else 0.0
        s["total_adds"] = s["waiver_claims"] + s["fa_adds"]
        result.append(s)

    return sorted(result, key=lambda x: -x["total_adds"])


def get_owner_waiver_by_season(con: sqlite3.Connection) -> list[dict]:
    """
    Per-owner per-season waiver wire counts: claims, FA adds, drops, FAAB spent.
    """
    roster_map = _roster_to_owner(con)

    stats: dict[tuple[str, int], dict] = {}

    def _s(owner: str, season: int) -> dict:
        key = (owner, season)
        if key not in stats:
            stats[key] = {
                "owner": owner,
                "season": season,
                "waiver_claims": 0,
                "fa_adds": 0,
                "drops": 0,
                "faab_spent": 0,
            }
        return stats[key]

    for league_id, season, txn_type, status, adds_raw, drops_raw, rids_raw, bid in con.execute(
        """
        SELECT league_id, season, type, status, adds_json, drops_json, roster_ids_json, waiver_bid_amount
        FROM transactions
        WHERE type IN ('waiver', 'free_agent') AND status = 'complete'
        """
    ).fetchall():
        rids = json.loads(rids_raw) if rids_raw else []
        owner = roster_map.get((league_id, rids[0])) if rids else None
        if not owner:
            adds = json.loads(adds_raw) if adds_raw else {}
            drops = json.loads(drops_raw) if drops_raw else {}
            for pid, rid in {**adds, **drops}.items():
                owner = roster_map.get((league_id, rid))
                if owner:
                    break
        if not owner:
            continue

        s = _s(owner, season)
        drops = json.loads(drops_raw) if drops_raw else {}

        if txn_type == "waiver":
            s["waiver_claims"] += 1
            if bid:
                s["faab_spent"] += bid
        else:
            s["fa_adds"] += 1

        s["drops"] += len(drops)

    return sorted(stats.values(), key=lambda x: (x["season"], x["owner"]))


# ---------------------------------------------------------------------------
# Per-owner waiver / FA transaction log
# ---------------------------------------------------------------------------

def get_owner_waiver_log(con: sqlite3.Connection, owner_name: str) -> list[dict]:
    """Return individual waiver and free-agent transactions for one owner.

    Each row represents one transaction: the player added, player dropped,
    transaction type, season, week, and FAAB bid if applicable.
    """
    roster_map = _roster_to_owner(con)
    owner_rosters: set[tuple[str, int]] = {
        (lid, rid) for (lid, rid), name in roster_map.items() if name == owner_name
    }
    if not owner_rosters:
        return []

    player_names = _player_names(con)

    rows = con.execute(
        """
        SELECT league_id, season, week, type, adds_json, drops_json, waiver_bid_amount
        FROM transactions
        WHERE type IN ('waiver', 'free_agent') AND status = 'complete'
        ORDER BY season DESC, COALESCE(week, 0) DESC
        """
    ).fetchall()

    results = []
    for league_id, season, week, txn_type, adds_raw, drops_raw, bid in rows:
        adds: dict[str, int] = json.loads(adds_raw) if adds_raw else {}
        drops: dict[str, int] = json.loads(drops_raw) if drops_raw else {}

        # Only include if this owner made the transaction
        is_owner = any(
            (league_id, rid) in owner_rosters
            for rid in list(adds.values()) + list(drops.values())
        )
        if not is_owner:
            continue

        added = [
            player_names.get(pid, pid)
            for pid, rid in adds.items()
            if (league_id, rid) in owner_rosters
        ]
        dropped = [
            player_names.get(pid, pid)
            for pid, rid in drops.items()
            if (league_id, rid) in owner_rosters
        ]

        results.append({
            "season": season,
            "week": week or 0,
            "type": "Waiver" if txn_type == "waiver" else "Free Agent",
            "added": ", ".join(added) if added else "—",
            "dropped": ", ".join(dropped) if dropped else "—",
            "faab_bid": bid if (txn_type == "waiver" and bid) else None,
        })

    return results


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


# ---------------------------------------------------------------------------
# Deep trade tree
# ---------------------------------------------------------------------------

@dataclass
class TreeNode:
    asset_type: str           # 'player', 'pick', or 'draft'
    asset_name: str           # display name
    player_id: str | None     # None for pick nodes
    from_owner: str
    to_owner: str
    season: int
    week: int | None          # None for draft events
    transaction_id: str | None
    children: list['TreeNode'] = field(default_factory=list)


def build_deep_trade_tree(
    con: sqlite3.Connection,
    player_name: str,
    max_depth: int = 3,
) -> tuple[str | None, list[TreeNode]]:
    """
    Trace a player's full trade history and all downstream effects.

    For each trade the player was in, we also follow every counter-asset
    (players and picks) received in return. Picks are linked to whoever
    was eventually drafted with that pick slot, and that player's subsequent
    trades are followed recursively up to max_depth.

    Returns (canonical_player_name, spine_nodes) where each spine node
    represents one trade of the focal player and its children are the
    counter-assets (with their own downstream children).
    """
    roster_map = _roster_to_owner(con)
    player_names_map = _player_names(con)

    matches = con.execute(
        "SELECT player_id, full_name FROM players WHERE LOWER(full_name) LIKE LOWER(?)",
        (f"%{player_name}%",),
    ).fetchall()
    if not matches:
        return None, []
    exact = [m for m in matches if m[1].lower() == player_name.lower()]
    player_id, player_full_name = (exact or matches)[0]

    # {(season, round, draft_slot): (player_id, player_name)}
    # draft_slot is the original pick slot number (= original_roster_id in trade pick records).
    # This gives a 1:1 mapping: each traded pick slot resolves to exactly one drafted player.
    pick_drafted: dict[tuple, list] = {}
    for r in con.execute(
        "SELECT season, round, draft_slot, player_id, player_name FROM draft_picks "
        "WHERE player_id IS NOT NULL AND draft_slot IS NOT NULL ORDER BY pick_no"
    ).fetchall():
        key = (int(r[0]), int(r[1]), int(r[2]))
        pick_drafted.setdefault(key, []).append((r[3], r[4]))

    visited_txns: set[str] = set()

    def _follow(pid: str, depth: int) -> list[TreeNode]:
        if depth > max_depth:
            return []
        rows = con.execute(
            """
            SELECT transaction_id, league_id, season, week, adds_json, drops_json
            FROM transactions
            WHERE type = 'trade'
              AND (adds_json LIKE ? OR drops_json LIKE ?)
            ORDER BY season, week
            """,
            (f'%"{pid}"%', f'%"{pid}"%'),
        ).fetchall()

        nodes: list[TreeNode] = []
        for txn_id, league_id, season, week, adds_raw, drops_raw in rows:
            if txn_id in visited_txns:
                continue
            visited_txns.add(txn_id)

            adds = json.loads(adds_raw) if adds_raw else {}
            drops = json.loads(drops_raw) if drops_raw else {}

            recv_rid = adds.get(pid)
            send_rid = drops.get(pid)
            to_owner = roster_map.get((league_id, recv_rid), f"Roster {recv_rid}") if recv_rid else "?"
            from_owner = roster_map.get((league_id, send_rid), f"Roster {send_rid}") if send_rid else "?"

            node = TreeNode(
                asset_type="player",
                asset_name=player_names_map.get(pid, pid),
                player_id=pid,
                from_owner=from_owner,
                to_owner=to_owner,
                season=season,
                week=week,
                transaction_id=txn_id,
            )

            # Counter-players: everything else that moved in this trade
            for other_pid, other_recv_rid in adds.items():
                if other_pid == pid:
                    continue
                other_send_rid = drops.get(other_pid)
                other_to = roster_map.get((league_id, other_recv_rid), f"Roster {other_recv_rid}")
                other_from = roster_map.get((league_id, other_send_rid), "?") if other_send_rid else "?"
                other_name = player_names_map.get(other_pid, other_pid)

                counter = TreeNode(
                    asset_type="player",
                    asset_name=other_name,
                    player_id=other_pid,
                    from_owner=other_from,
                    to_owner=other_to,
                    season=season,
                    week=week,
                    transaction_id=txn_id,
                )
                counter.children = _follow(other_pid, depth + 1)
                node.children.append(counter)

            # Draft picks in this trade
            pick_rows = con.execute(
                """
                SELECT season, round, original_roster_id, from_roster_id, to_roster_id
                FROM transaction_draft_picks WHERE transaction_id = ?
                """,
                (txn_id,),
            ).fetchall()

            for pick_season, round_, orig_rid, from_rid, to_rid in pick_rows:
                orig_owner = roster_map.get((league_id, orig_rid), f"Roster {orig_rid}")
                pick_from = roster_map.get((league_id, from_rid), f"Roster {from_rid}")
                pick_to = roster_map.get((league_id, to_rid), f"Roster {to_rid}")
                pick_label = f"{pick_season} R{round_} ({orig_owner})"

                pick_node = TreeNode(
                    asset_type="pick",
                    asset_name=pick_label,
                    player_id=None,
                    from_owner=pick_from,
                    to_owner=pick_to,
                    season=season,
                    week=week,
                    transaction_id=txn_id,
                )
                # draft_slot == original_roster_id: each pick slot maps to exactly one player.
                candidates = pick_drafted.get((int(pick_season), int(round_), int(orig_rid)), [])
                for drafted_pid, drafted_name in candidates:
                    draft_node = TreeNode(
                        asset_type="draft",
                        asset_name=drafted_name,
                        player_id=drafted_pid,
                        from_owner="Draft",
                        to_owner=pick_to,
                        season=int(pick_season),
                        week=None,
                        transaction_id=None,
                    )
                    draft_node.children = _follow(drafted_pid, depth + 1)
                    pick_node.children.append(draft_node)
                node.children.append(pick_node)

            nodes.append(node)

        return nodes

    return player_full_name, _follow(player_id, depth=0)
