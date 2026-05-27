"""NNBE Fantasy Football League History — Streamlit web app."""

from __future__ import annotations

import os
import sqlite3
import sys

# Make the fantasy_analyzer package importable regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fantasy_analyzer.analysis.history import (
    compute_playoff_results,
    compute_regular_season_records,
    get_all_seasons,
    get_all_time_standings,
    get_available_seasons,
    get_season_breakdown,
    get_standings_history,
    get_weekly_scoring_extremes,
    get_league_records,
    get_playoff_records,
    get_h2h_matrix,
    get_championship_rosters,
)
from fantasy_analyzer.analysis.rivalries import get_rivalry_pairs, get_nemesis_prey
from fantasy_analyzer.analysis.transactions import (
    get_trade_log,
    get_owner_trade_stats,
    get_trade_partner_matrix,
    get_all_traded_players,
    build_deep_trade_tree,
    get_faab_records,
    get_player_add_drop_stats,
    get_owner_waiver_activity,
    get_owner_waiver_by_season,
    TreeNode,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data", "league.db")

st.set_page_config(
    page_title="NNBE League History",
    page_icon=":football:",
    layout="wide",
)

# ---------------------------------------------------------------------------
# DB connection (cached)
# ---------------------------------------------------------------------------

@st.cache_resource
def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    return con


# ---------------------------------------------------------------------------
# Data helpers (cached per query)
# ---------------------------------------------------------------------------

@st.cache_data
def load_all_time_standings():
    con = get_db()
    return get_all_time_standings(con)


@st.cache_data
def load_season_breakdown(season: int):
    con = get_db()
    return get_season_breakdown(con, season)


@st.cache_data
def load_available_seasons():
    con = get_db()
    return get_available_seasons(con)


@st.cache_data
def load_owners() -> list[str]:
    con = get_db()
    rows = con.execute(
        "SELECT canonical_name FROM owners ORDER BY canonical_name"
    ).fetchall()
    return [r[0] for r in rows]


@st.cache_data
def load_trade_log():
    return get_trade_log(get_db())

@st.cache_data
def load_owner_trade_stats():
    return get_owner_trade_stats(get_db())

@st.cache_data
def load_trade_partner_matrix():
    return get_trade_partner_matrix(get_db())

@st.cache_data
def load_all_traded_players() -> list[str]:
    return get_all_traded_players(get_db())

@st.cache_data
def load_deep_trade_tree(player_name: str):
    return build_deep_trade_tree(get_db(), player_name)

@st.cache_data
def load_standings_history():
    return get_standings_history(get_db())

@st.cache_data
def load_weekly_scoring_extremes():
    return get_weekly_scoring_extremes(get_db())

@st.cache_data
def load_league_records(include_playoffs: bool = False):
    return get_league_records(get_db(), include_playoffs=include_playoffs)

@st.cache_data
def load_playoff_records():
    return get_playoff_records(get_db())

@st.cache_data
def load_h2h_matrix():
    return get_h2h_matrix(get_db())

@st.cache_data
def load_rivalry_pairs():
    return get_rivalry_pairs(get_db())

@st.cache_data
def load_nemesis_prey():
    return get_nemesis_prey(get_db())

@st.cache_data
def load_championship_rosters():
    return get_championship_rosters(get_db())

@st.cache_data
def load_faab_records():
    return get_faab_records(get_db())

@st.cache_data
def load_player_add_drop_stats():
    return get_player_add_drop_stats(get_db())

@st.cache_data
def load_owner_waiver_activity():
    return get_owner_waiver_activity(get_db())

@st.cache_data
def load_owner_waiver_by_season():
    return get_owner_waiver_by_season(get_db())

@st.cache_data
def load_h2h(owner1: str, owner2: str) -> pd.DataFrame:
    """Return all regular-season matchups between two owners."""
    con = get_db()
    rows = con.execute(
        """
        SELECT m1.season, m1.week, m1.points as pts1, m2.points as pts2
        FROM matchups m1
        JOIN matchups m2
          ON m1.league_id = m2.league_id
         AND m1.week = m2.week
         AND m1.matchup_id = m2.matchup_id
         AND m1.user_id != m2.user_id
        JOIN owners o1 ON m1.user_id = o1.user_id
        JOIN owners o2 ON m2.user_id = o2.user_id
        JOIN leagues l ON m1.league_id = l.league_id
        WHERE o1.canonical_name = ?
          AND o2.canonical_name = ?
          AND m1.week < l.playoff_week_start
        ORDER BY m1.season, m1.week
        """,
        (owner1, owner2),
    ).fetchall()
    return pd.DataFrame(rows, columns=["Season", "Week", f"{owner1} Pts", f"{owner2} Pts"])


# ---------------------------------------------------------------------------
# Shared style helpers
# ---------------------------------------------------------------------------

FINISH_DISPLAY = {
    1: "Champion", 2: "Runner-up", 3: "3rd", 4: "4th",
    5: "5th", 6: "6th", 7: "7th", 8: "8th",
    9: "9th", 10: "10th", 11: "11th", 12: "12th",
}

FINISH_COLOR = {
    1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32",
}


def finish_badge(finish: int | None) -> str:
    if finish is None:
        return ""
    label = FINISH_DISPLAY.get(finish, str(finish))
    color = FINISH_COLOR.get(finish, "#666")
    return f'<span style="background:{color};color:#111;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:bold">{label}</span>'


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------

def page_overview():
    st.title("NNBE League History")
    st.caption("The New New Big East — 2021 through 2025")

    tab_standings, tab_records, tab_weekly, tab_champs = st.tabs(
        ["Standings", "Records", "Weekly Scoring", "Champions"]
    )

    # ---- Standings ----
    with tab_standings:
        records = load_all_time_standings()
        rows = []
        for rank, r in enumerate(records, 1):
            rows.append({
                "Rank": rank,
                "Owner": r.canonical_name,
                "Seasons": r.seasons,
                "W-L": f"{r.reg_wins}-{r.reg_losses}" + (f"-{r.reg_ties}" if r.reg_ties else ""),
                "Win%": f"{r.win_pct:.1%}",
                "Total Pts": f"{r.total_points:,.1f}",
                "PPG": f"{r.ppg:.1f}",
                "Playoffs": f"{r.playoff_appearances}/{r.seasons}",
                "Titles": r.championships if r.championships else "",
            })
        st.dataframe(pd.DataFrame(rows).set_index("Rank"), use_container_width=True, height=460)

        st.divider()
        st.subheader("All-Time Win Percentage")
        fig = go.Figure(go.Bar(
            x=[r.canonical_name for r in records],
            y=[round(r.win_pct * 100, 1) for r in records],
            marker_color=["#FFD700" if r.championships else "#4a90d9" for r in records],
            text=[f"{r.win_pct:.1%}" for r in records],
            textposition="outside",
        ))
        fig.update_layout(
            yaxis_title="Win %", yaxis_range=[0, 100],
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20), height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---- Records ----
    with tab_records:
        scope = st.radio(
            "Scope",
            ["Regular Season", "All Games (incl. Playoffs)"],
            horizontal=True,
            key="records_scope",
        )
        include_playoffs = scope == "All Games (incl. Playoffs)"
        league_recs = load_league_records(include_playoffs=include_playoffs)
        df_recs = pd.DataFrame(league_recs).set_index("Category")
        st.dataframe(df_recs, use_container_width=True, height=560)

    # ---- Weekly Scoring ----
    with tab_weekly:
        extremes = load_weekly_scoring_extremes()

        col_top, col_bot = st.columns(2)
        with col_top:
            st.subheader("Top 10 Single-Week Scores")
            df_top = pd.DataFrame(extremes["top"]).set_index("Rank")
            df_top["Score"] = df_top["Score"].map(lambda x: f"{x:.2f}")
            st.dataframe(df_top, use_container_width=True, height=400)

        with col_bot:
            st.subheader("Bottom 10 Single-Week Scores")
            df_bot = pd.DataFrame(extremes["bottom"]).set_index("Rank")
            df_bot["Score"] = df_bot["Score"].map(lambda x: f"{x:.2f}")
            st.dataframe(df_bot, use_container_width=True, height=400)

        st.divider()
        st.subheader("Weekly High / Low Score Counts (Regular Season)")
        all_owners = sorted(set(extremes["high_counts"]) | set(extremes["low_counts"]))
        count_rows = [
            {
                "Owner": o,
                "High Score Weeks": extremes["high_counts"].get(o, 0),
                "Low Score Weeks": extremes["low_counts"].get(o, 0),
            }
            for o in sorted(all_owners, key=lambda o: -extremes["high_counts"].get(o, 0))
        ]
        st.dataframe(pd.DataFrame(count_rows).set_index("Owner"), use_container_width=True, height=460)

    # ---- Champions ----
    with tab_champs:
        champ_data = load_championship_rosters()

        for cr in reversed(champ_data):
            score_str = ""
            if cr["champ_score"] and cr["ru_score"]:
                score_str = f" ({cr['champ_score']:.2f} – {cr['ru_score']:.2f})"
            with st.expander(f"**{cr['season']} Champion: {cr['champion']}**{score_str}", expanded=True):
                st.markdown(f"Runner-up: **{cr['runner_up']}**")
                if cr["starters"]:
                    st.markdown("**Championship Starting Lineup:**")
                    pos_order = ["QB", "RB", "WR", "TE", "K", "DEF", "FLEX", "SUPER_FLEX", "BN"]
                    starters_sorted = sorted(
                        cr["starters"],
                        key=lambda p: pos_order.index(p["position"]) if p["position"] in pos_order else 99
                    )
                    starter_df = pd.DataFrame(starters_sorted).rename(
                        columns={"position": "Pos", "player": "Player"}
                    )
                    st.dataframe(starter_df.set_index("Pos"), use_container_width=True, hide_index=False)
                else:
                    st.caption("Starting lineup data not available.")


# ---------------------------------------------------------------------------
# Page: Owner Profile
# ---------------------------------------------------------------------------

def page_owner_profile():
    st.title("Owner Profile")

    owners = load_owners()
    selected = st.selectbox("Select owner", owners)
    if not selected:
        return

    con = get_db()
    seasons = load_available_seasons()

    # Gather per-season data
    season_rows = []
    total_wins = total_losses = total_ties = 0
    total_pts = total_pts_against = total_games = 0
    playoff_apps = championships = 0
    best_finish = worst_finish = None

    for season in seasons:
        data = load_season_breakdown(season)
        if not data:
            continue

        reg_map = {r.canonical_name: r for r in data["regular_season"]}
        rec = reg_map.get(selected)
        if not rec:
            continue

        pr = data["playoff"].get(
            next((uid for uid, r in
                  [(u, r) for u, r in data["playoff"].items()
                   if r.canonical_name == selected]), None)
        )
        # Find by name since we don't have user_id directly here
        playoff_entry = next(
            (r for r in data["playoff"].values() if r.canonical_name == selected),
            None,
        )

        seed = next(
            (i + 1 for i, r in enumerate(data["regular_season"]) if r.canonical_name == selected),
            None,
        )

        # Finish: championship bracket result for top 6; regular season seed for bottom 6
        if playoff_entry and playoff_entry.made_playoffs and playoff_entry.finish is not None:
            finish = playoff_entry.finish
        else:
            finish = seed  # regular season position (7–12)
        finish_label = FINISH_DISPLAY.get(finish, f"{finish}th") if finish else "-"

        season_rows.append({
            "Season": season,
            "Seed": seed,
            "W-L": f"{rec.wins}-{rec.losses}",
            "Win%": f"{rec.win_pct:.1%}",
            "Pts For": round(rec.points_for, 1),
            "Pts Against": round(rec.points_against, 1),
            "PPG": round(rec.ppg, 1),
            "Finish": finish_label,
            "_finish_int": finish,
        })

        total_wins += rec.wins
        total_losses += rec.losses
        total_ties += rec.ties
        total_pts += rec.points_for
        total_pts_against += rec.points_against
        total_games += rec.games

        if playoff_entry:
            if playoff_entry.made_playoffs:
                playoff_apps += 1
            if playoff_entry.champion:
                championships += 1
        # Track best/worst finish using the hybrid finish value (bracket for top 6, seed for bottom 6)
        if finish is not None:
            if best_finish is None or finish < best_finish:
                best_finish = finish
            if worst_finish is None or finish > worst_finish:
                worst_finish = finish

    if not season_rows:
        st.warning(f"No data found for {selected}.")
        return

    overall_win_pct = (total_wins + 0.5 * total_ties) / total_games if total_games else 0

    # --- Career summary metrics ---
    st.subheader(f"{selected} — Career Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Record", f"{total_wins}-{total_losses}" + (f"-{total_ties}" if total_ties else ""))
    c2.metric("Win %", f"{overall_win_pct:.1%}")
    c3.metric("Avg PPG", f"{total_pts / total_games:.1f}")
    c4.metric("Playoffs", f"{playoff_apps}/{len(season_rows)}")
    c5.metric("Championships", championships)

    st.divider()

    # --- Season-by-season table ---
    st.subheader("Season Breakdown")
    display_df = pd.DataFrame(season_rows).drop(columns=["_finish_int"]).set_index("Season")
    st.dataframe(display_df, use_container_width=True, height=240)

    st.divider()

    # --- Win% per season chart ---
    st.subheader("Win % by Season")
    win_pcts = [
        (row["Season"], float(row["Win%"].strip("%")) / 100)
        for row in season_rows
    ]
    fig = go.Figure(go.Scatter(
        x=[s for s, _ in win_pcts],
        y=[round(p * 100, 1) for _, p in win_pcts],
        mode="lines+markers+text",
        text=[f"{p:.0%}" for _, p in win_pcts],
        textposition="top center",
        line=dict(color="#4a90d9", width=2),
        marker=dict(size=10),
    ))
    fig.add_hline(y=50, line_dash="dot", line_color="gray", annotation_text="50%")
    fig.update_layout(
        yaxis_title="Win %",
        yaxis_range=[0, 105],
        xaxis=dict(tickmode="linear", dtick=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20),
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- Head-to-head vs all opponents ---
    st.subheader("Head-to-Head Record vs Each Opponent")

    all_records = load_all_time_standings()
    opponents = [r.canonical_name for r in all_records if r.canonical_name != selected]

    h2h_rows = []
    for opp in opponents:
        df = load_h2h(selected, opp)
        if df.empty:
            continue
        wins = (df[f"{selected} Pts"] > df[f"{opp} Pts"]).sum()
        losses = (df[f"{selected} Pts"] < df[f"{opp} Pts"]).sum()
        ties = (df[f"{selected} Pts"] == df[f"{opp} Pts"]).sum()
        games = len(df)
        avg_pts_for = df[f"{selected} Pts"].mean()
        avg_pts_against = df[f"{opp} Pts"].mean()
        w_pct = (wins + 0.5 * ties) / games if games else 0
        h2h_rows.append({
            "Opponent": opp,
            "W-L": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
            "Win%": f"{w_pct:.1%}",
            "Avg Scored": round(avg_pts_for, 1),
            "Avg Allowed": round(avg_pts_against, 1),
            "Games": games,
        })

    h2h_rows.sort(key=lambda r: float(r["Win%"].strip("%")), reverse=True)
    st.dataframe(
        pd.DataFrame(h2h_rows).set_index("Opponent"),
        use_container_width=True,
        height=420,
    )


# ---------------------------------------------------------------------------
# Page: Season View
# ---------------------------------------------------------------------------

def page_season():
    st.title("Season Standings")

    tab_detail, tab_history = st.tabs(["Season Detail", "History"])

    # ---- Season Detail ----
    with tab_detail:
        seasons = load_available_seasons()
        selected_season = st.selectbox("Select season", sorted(seasons, reverse=True))

        data = load_season_breakdown(selected_season)
        if not data:
            st.warning("No data for this season.")
        else:
            reg = data["regular_season"]
            rows = []
            for seed, rec in enumerate(reg, 1):
                playoff_entry = next(
                    (r for r in data["playoff"].values() if r.canonical_name == rec.canonical_name),
                    None,
                )
                # Finish: bracket result for championship teams; reg season seed for others
                if playoff_entry and playoff_entry.made_playoffs and playoff_entry.finish is not None:
                    finish = playoff_entry.finish
                    finish_label = FINISH_DISPLAY.get(finish, f"{finish}th")
                else:
                    finish_label = "-"
                rows.append({
                    "Seed": seed,
                    "Owner": rec.canonical_name,
                    "W-L": f"{rec.wins}-{rec.losses}",
                    "Win%": f"{rec.win_pct:.1%}",
                    "Pts For": round(rec.points_for, 1),
                    "Pts Against": round(rec.points_against, 1),
                    "PPG": round(rec.ppg, 1),
                    "Finish": finish_label,
                })

            st.dataframe(pd.DataFrame(rows).set_index("Seed"), use_container_width=True, height=460)

            st.subheader("Points Scored")
            sorted_rows = sorted(rows, key=lambda r: r["Pts For"], reverse=True)
            fig = go.Figure(go.Bar(
                x=[r["Owner"] for r in sorted_rows],
                y=[r["Pts For"] for r in sorted_rows],
                marker_color="#4a90d9",
                text=[r["Pts For"] for r in sorted_rows],
                textposition="outside",
            ))
            fig.update_layout(
                yaxis_title="Points For",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=20), height=340,
            )
            st.plotly_chart(fig, use_container_width=True)

    # ---- History grid ----
    with tab_history:
        history = load_standings_history()
        seasons_sorted = sorted(history.keys())
        all_owners_hist = sorted({name for ranks in history.values() for name in ranks.values()})

        finish_labels = {
            1: "Champion", 2: "Runner-up", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
            7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
        }

        # Build DataFrame: rows=finish rank, cols=season
        grid = {}
        for season in seasons_sorted:
            rank_to_name = history[season]
            grid[str(season)] = {finish_labels.get(rank, str(rank)): name for rank, name in rank_to_name.items()}

        df_grid = pd.DataFrame(grid)
        df_grid.index.name = "Finish"
        st.dataframe(df_grid, use_container_width=True, height=460)

        st.divider()

        # Owner view: each owner's finish by year
        st.subheader("Owner Finish by Season")
        owner_rows = []
        for owner in all_owners_hist:
            row = {"Owner": owner}
            for season in seasons_sorted:
                rank_to_name = history[season]
                finish = next((rank for rank, name in rank_to_name.items() if name == owner), None)
                row[str(season)] = finish_labels.get(finish, "—") if finish else "—"
            owner_rows.append(row)
        st.dataframe(pd.DataFrame(owner_rows).set_index("Owner"), use_container_width=True, height=460)


# ---------------------------------------------------------------------------
# Page: Head-to-Head
# ---------------------------------------------------------------------------

def page_h2h():
    st.title("Head-to-Head")

    tab_lookup, tab_playoff = st.tabs(["Matchup Lookup", "Playoff Records"])

    # ---- Matchup Lookup ----
    with tab_lookup:
        owners = load_owners()
        col1, col2 = st.columns(2)
        owner1 = col1.selectbox("Owner 1", owners, index=0, key="h2h_o1")
        owner2 = col2.selectbox("Owner 2", owners, index=1, key="h2h_o2")

        if owner1 == owner2:
            st.warning("Pick two different owners.")
        else:
            df = load_h2h(owner1, owner2)
            if df.empty:
                st.info("No head-to-head matchups found.")
            else:
                pts1_col = f"{owner1} Pts"
                pts2_col = f"{owner2} Pts"
                wins1 = (df[pts1_col] > df[pts2_col]).sum()
                wins2 = (df[pts1_col] < df[pts2_col]).sum()
                ties = (df[pts1_col] == df[pts2_col]).sum()
                games = len(df)

                c1, c2, c3 = st.columns(3)
                c1.metric(f"{owner1} Wins", wins1)
                c2.metric("Ties", ties)
                c3.metric(f"{owner2} Wins", wins2)
                st.divider()

                st.subheader("Points Each Game")
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=list(range(1, games + 1)), y=df[pts1_col].tolist(),
                    name=owner1, mode="lines+markers", line=dict(color="#4a90d9"),
                ))
                fig.add_trace(go.Scatter(
                    x=list(range(1, games + 1)), y=df[pts2_col].tolist(),
                    name=owner2, mode="lines+markers", line=dict(color="#e05a5a"),
                ))
                labels = [f"{r['Season']} Wk{r['Week']}" for _, r in df.iterrows()]
                fig.update_xaxes(tickvals=list(range(1, games + 1)), ticktext=labels, tickangle=45)
                fig.update_layout(
                    yaxis_title="Points", plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, b=80), height=380,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig, use_container_width=True)
                st.divider()

                st.subheader("All Matchups")
                log = df.copy()
                log["Winner"] = log.apply(
                    lambda r: owner1 if r[pts1_col] > r[pts2_col]
                    else (owner2 if r[pts2_col] > r[pts1_col] else "Tie"), axis=1,
                )
                st.dataframe(log.set_index("Season"), use_container_width=True, height=420)

    # ---- Playoff Records ----
    with tab_playoff:
        st.subheader("All-Time Playoff Records")
        playoff_recs = load_playoff_records()
        rows = [
            {
                "Owner": ps.canonical_name,
                "Appearances": ps.appearances,
                "Byes": ps.byes,
                "W-L": f"{ps.playoff_wins}-{ps.playoff_losses}",
                "Win%": f"{ps.win_pct:.1%}" if ps.games else "—",
                "Titles": ps.championships if ps.championships else "",
                "Runner-up": ps.runner_up if ps.runner_up else "",
            }
            for ps in playoff_recs
        ]
        st.dataframe(pd.DataFrame(rows).set_index("Owner"), use_container_width=True, height=460)


# ---------------------------------------------------------------------------
# Trade tree DOT renderer
# ---------------------------------------------------------------------------

def _trade_tree_dot(player_name: str, nodes: list[TreeNode]) -> str:
    """Generate a Graphviz DOT string from trade tree nodes."""
    _counter = [0]

    def _id() -> str:
        _counter[0] += 1
        return f"n{_counter[0]}"

    def _esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    lines = [
        "digraph {",
        "  rankdir=LR;",
        '  graph [bgcolor=transparent, fontname="Helvetica"];',
        '  node [fontname="Helvetica", fontsize=10, margin="0.18,0.1"];',
        '  edge [color="#666666", arrowsize=0.75];',
    ]

    root_id = _id()
    lines.append(
        f'  {root_id} [label="{_esc(player_name)}", shape=box, '
        'style="filled,rounded", fillcolor="#1a472a", fontcolor=white, penwidth=2];'
    )

    def _render(node: TreeNode, parent_id: str) -> None:
        nid = _id()
        name = _esc(node.asset_name)
        fr = _esc(node.from_owner)
        to = _esc(node.to_owner)

        if node.asset_type == "player":
            label = f"S{node.season} Wk{node.week}\\n{fr} -> {to}\\n{name}"
            fill = "#154360"
        elif node.asset_type == "pick":
            n_drafted = len(node.children)
            label = f"{name}\\n{fr} -> {to}"
            if n_drafted:
                label += f"\\n({n_drafted} player(s) drafted)"
            else:
                label += "\\n(future / no data)"
            fill = "#6e2c00"
        else:  # draft
            label = f"Drafted: {name}\\n{to} ({node.season})"
            fill = "#7d5a00"

        lines.append(
            f'  {nid} [label="{label}", shape=box, style="filled,rounded", '
            f'fillcolor="{fill}", fontcolor=white];'
        )
        lines.append(f"  {parent_id} -> {nid};")
        for child in node.children:
            _render(child, nid)

    for node in nodes:
        _render(node, root_id)

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Page: Trades
# ---------------------------------------------------------------------------

def page_trades():
    st.title("Trades")

    tab1, tab2, tab3 = st.tabs(["Player Trade Tree", "Owner Tendencies", "Trade Log"])

    # ---- Tab 3: Trade Log ----
    with tab3:
        trades = load_trade_log()
        owners = load_owners()

        col1, col2 = st.columns([2, 1])
        season_filter = col1.multiselect(
            "Filter by season", sorted({t.season for t in trades}), default=[]
        )
        owner_filter = col2.multiselect("Filter by owner", owners, default=[])

        filtered = trades
        if season_filter:
            filtered = [t for t in filtered if t.season in season_filter]
        if owner_filter:
            filtered = [t for t in filtered if any(o in t.owners for o in owner_filter)]

        rows = []
        for trade in filtered:
            players = [a for a in trade.assets if a.asset_type == "player"]
            picks = [a for a in trade.assets if a.asset_type == "pick"]
            rows.append({
                "Season": trade.season,
                "Week": trade.week,
                "Teams": " & ".join(trade.owners),
                "Players": ", ".join(f"{a.asset_name} ({a.from_owner} → {a.to_owner})" for a in players),
                "Picks": ", ".join(f"{a.asset_name} ({a.from_owner} → {a.to_owner})" for a in picks),
            })

        if rows:
            df = pd.DataFrame(rows)
            st.caption(f"{len(rows)} trades")
            st.dataframe(df, use_container_width=True, height=520)
        else:
            st.info("No trades match the selected filters.")

    # ---- Tab 1: Player Trade Tree ----
    with tab1:
        st.markdown(
            "Select a player to trace their full trade history — including every asset "
            "exchanged in return, what picks were used to draft, and where those players ended up."
        )
        all_traded = load_all_traded_players()
        selected_player = st.selectbox(
            "Player", [""] + all_traded, format_func=lambda x: "Select a player..." if x == "" else x
        )

        if selected_player:
            full_name, trade_nodes = load_deep_trade_tree(selected_player)

            if not trade_nodes:
                st.info(f"{full_name} has no recorded trades.")
            else:
                st.subheader(f"{full_name} — Trade Tree")
                st.caption(f"{len(trade_nodes)} trade(s) in league history.")

                # Trade selector — pick one trade to visualize at a time
                trade_labels = [
                    f"Season {n.season}, Week {n.week}: {n.from_owner} → {n.to_owner}"
                    for n in trade_nodes
                ]
                if len(trade_nodes) == 1:
                    node = trade_nodes[0]
                else:
                    idx = st.radio(
                        "Select trade to visualize",
                        range(len(trade_labels)),
                        format_func=lambda i: trade_labels[i],
                        horizontal=False,
                    )
                    node = trade_nodes[idx]

                dot = _trade_tree_dot(full_name, [node])
                st.graphviz_chart(dot, use_container_width=True)

                st.divider()
                st.subheader("Trade Details")

                header = (
                    f"Season {node.season}, Week {node.week}: "
                    f"{node.from_owner} traded {full_name} to {node.to_owner}"
                )
                with st.expander(header, expanded=True):
                    if not node.children:
                        st.markdown("_(no counter-assets recorded)_")
                    else:
                        st.markdown("**Received in return:**")
                        for c in node.children:
                            if c.asset_type == "player":
                                line = f"- **{c.asset_name}** ({c.from_owner} to {c.to_owner})"
                                if c.children:
                                    next_trade = c.children[0]
                                    line += (
                                        f" — later traded S{next_trade.season} "
                                        f"Wk{next_trade.week}: "
                                        f"{next_trade.from_owner} to {next_trade.to_owner}"
                                    )
                                st.markdown(line)
                            elif c.asset_type == "pick":
                                drafted_names = [gc.asset_name for gc in c.children if gc.asset_type == "draft"]
                                if drafted_names:
                                    drafted_str = ", ".join(f"**{n}**" for n in drafted_names)
                                    line = (
                                        f"- **{c.asset_name}** ({c.from_owner} to {c.to_owner})"
                                        f" — {c.to_owner} drafted: {drafted_str}"
                                    )
                                    for gc in c.children:
                                        if gc.asset_type == "draft" and gc.children:
                                            follow = gc.children[0]
                                            line += (
                                                f" ({gc.asset_name} later traded "
                                                f"S{follow.season} Wk{follow.week})"
                                            )
                                else:
                                    line = (
                                        f"- **{c.asset_name}** ({c.from_owner} to {c.to_owner})"
                                        f" — future pick / no draft data"
                                    )
                                st.markdown(line)

    # ---- Tab 2: Owner Tendencies ----
    with tab2:
        stats = load_owner_trade_stats()

        st.subheader("Trade Activity by Owner")
        rows = [
            {
                "Owner": s.canonical_name,
                "Trades": s.total_trades,
                "Players In": s.players_acquired,
                "Players Out": s.players_sent,
                "Picks In": s.picks_acquired,
                "Picks Out": s.picks_sent,
                "Waiver Claims": s.total_waiver_claims,
                "FA Adds": s.total_fa_adds,
                "FAAB Spent": s.total_faab_spent,
            }
            for s in stats
        ]
        st.dataframe(pd.DataFrame(rows).set_index("Owner"), use_container_width=True, height=460)

        st.divider()

        # Trade partner heatmap
        st.subheader("Trade Partner Frequency")
        matrix = load_trade_partner_matrix()
        all_owners = sorted(load_owners())

        heatmap_z = []
        for o1 in all_owners:
            row = []
            for o2 in all_owners:
                if o1 == o2:
                    row.append(0)
                else:
                    pair = tuple(sorted([o1, o2]))
                    row.append(matrix.get(pair, 0))
            heatmap_z.append(row)

        fig = go.Figure(go.Heatmap(
            z=heatmap_z,
            x=all_owners,
            y=all_owners,
            colorscale="Blues",
            text=heatmap_z,
            texttemplate="%{text}",
            showscale=True,
        ))
        fig.update_layout(
            height=480,
            margin=dict(t=20, b=20),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Rivalries
# ---------------------------------------------------------------------------

def _cell_color(val: str) -> str:
    """Return CSS background+text color for a W-L cell string."""
    if val == "—" or not val:
        return ""
    try:
        w, l = map(int, val.split("-"))
        total = w + l
        if total == 0:
            return ""
        pct = w / total
        if pct == 1.0:
            return "background-color: #1b5e20; color: white; font-weight: bold"
        if pct >= 0.70:
            return "background-color: #388e3c; color: white"
        if pct >= 0.55:
            return "background-color: #81c784; color: black"
        if pct == 0.50:
            return "background-color: #fff9c4; color: black"
        if pct >= 0.35:
            return "background-color: #e57373; color: white"
        if pct > 0.0:
            return "background-color: #c62828; color: white"
        return "background-color: #7f0000; color: white; font-weight: bold"
    except Exception:
        return ""


def _matrix_df():
    """Build the styled 12x12 W-L matrix."""
    matrix = load_h2h_matrix()
    owners = sorted(load_owners())
    grid = {}
    for row in owners:
        grid[row] = {}
        for col in owners:
            if row == col:
                grid[row][col] = "—"
            else:
                w = matrix.get((row, col), 0)
                l = matrix.get((col, row), 0)
                grid[row][col] = f"{w}-{l}"
    df = pd.DataFrame(grid).T
    df.index.name = "Owner \\ Opp"
    try:
        return df.style.map(_cell_color)
    except AttributeError:
        return df.style.applymap(_cell_color)  # pandas < 2.1


def page_rivalries():
    st.title("Rivalries")

    tab_overview, tab_nemesis, tab_matrix = st.tabs(["Overview", "Nemesis & Prey", "Full Matrix"])

    # ---- Overview ----
    with tab_overview:
        pairs = load_rivalry_pairs()
        total_games = sum(p.total_games for p in pairs)
        st.caption(f"{total_games} regular-season matchups across {len(pairs)} unique pairings")

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Top Rivalries")
            st.caption("Most games played with the closest records.")
            rivalry_rows = [
                {
                    "Matchup": f"{p.owner_a} vs {p.owner_b}",
                    "Record": f"{p.a_wins}-{p.b_wins}",
                    "Games": p.total_games,
                    "Leader": p.leader() or "Tied",
                }
                for p in pairs[:10]
            ]
            st.dataframe(pd.DataFrame(rivalry_rows).set_index("Matchup"), use_container_width=True, height=400)

        with col_right:
            st.subheader("Most Lopsided")
            st.caption("Biggest mismatches (min 4 games).")
            lopsided = sorted(
                [p for p in pairs if p.total_games >= 4],
                key=lambda p: (-p.balance, -p.total_games),
            )
            lopsided_rows = []
            for p in lopsided[:10]:
                ldr = p.leader()
                opp = p.opponent_of(ldr) if ldr else p.owner_b
                lopsided_rows.append({
                    "Matchup": f"{p.owner_a} vs {p.owner_b}",
                    "Record": f"{p.a_wins}-{p.b_wins}",
                    "Games": p.total_games,
                    "Dominant": ldr or "—",
                })
            st.dataframe(pd.DataFrame(lopsided_rows).set_index("Matchup"), use_container_width=True, height=400)

    # ---- Nemesis & Prey ----
    with tab_nemesis:
        nemesis_data = load_nemesis_prey()

        st.subheader("League-Wide Nemesis & Prey")
        st.caption("Nemesis = opponent with your worst record (min 2 games). Prey = opponent with your best record.")
        summary_rows = [
            {
                "Owner": r["owner"],
                "Nemesis": r["nemesis"],
                "vs Nemesis": r["nemesis_record"],
                "Prey": r["prey"],
                "vs Prey": r["prey_record"],
            }
            for r in nemesis_data
        ]
        st.dataframe(pd.DataFrame(summary_rows).set_index("Owner"), use_container_width=True, height=460)

        st.divider()

        st.subheader("Owner Deep Dive")
        selected = st.selectbox(
            "Select owner", [r["owner"] for r in nemesis_data], key="rivalry_owner"
        )
        if selected:
            pairs = load_rivalry_pairs()
            owner_pairs = [p for p in pairs if selected in (p.owner_a, p.owner_b)]
            detail_rows = sorted(
                [
                    {
                        "Opponent": p.opponent_of(selected),
                        "Record": p.record_for(selected),
                        "Win%": f"{p.win_pct_for(selected):.1%}",
                        "Games": p.total_games,
                    }
                    for p in owner_pairs
                ],
                key=lambda r: float(r["Win%"].strip("%")),
            )
            st.dataframe(pd.DataFrame(detail_rows).set_index("Opponent"), use_container_width=True, height=460)

    # ---- Full Matrix ----
    with tab_matrix:
        st.subheader("All-Time Regular Season Head-to-Head (W-L)")
        st.caption("Read row vs column: row owner's record against column opponent.")
        st.dataframe(_matrix_df(), use_container_width=True, height=460)


# ---------------------------------------------------------------------------
# Page: Waivers
# ---------------------------------------------------------------------------

def page_waivers() -> None:
    st.title("Waiver Wire & FAAB")
    tab_faab, tab_players, tab_owners = st.tabs(["FAAB Records", "Player Activity", "Owner Activity"])

    # ---- FAAB Records ----
    with tab_faab:
        rec = load_faab_records()

        st.subheader("Biggest Single Waiver Claims")
        st.caption("Top successful FAAB bids of all time. Each row is one winning claim.")

        top_bids = rec["top_bids"]
        if top_bids:
            # Find max amount and show all ties at the top
            max_bid = top_bids[0]["amount"]
            top_n = 20
            bid_rows = [
                {
                    "Player": b["player"],
                    "Owner": b["owner"],
                    "Season": b["season"],
                    "Week": b["week"],
                    "FAAB": f"${b['amount']}",
                }
                for b in top_bids[:top_n]
            ]
            st.dataframe(pd.DataFrame(bid_rows).set_index("Player"), use_container_width=True, height=400)

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Most Total FAAB Won Per Player")
            st.caption("Sum of all successful waiver bid amounts for each player across all owners and seasons.")
            total_rows = [
                {"Player": p["player"], "Total FAAB": f"${p['total_faab']}"}
                for p in rec["top_total_spent"][:15]
            ]
            st.dataframe(pd.DataFrame(total_rows).set_index("Player"), use_container_width=True, height=430)

        with col_right:
            st.subheader("All-Time FAAB Spent by Owner")
            st.caption("Total successful waiver bid dollars across all seasons.")
            owner_rows = [
                {
                    "Owner": o["owner"],
                    "FAAB Spent": f"${o['faab_spent']}",
                    "Claims": o["claims"],
                    "Avg Bid": f"${o['faab_spent'] // o['claims'] if o['claims'] else 0}",
                }
                for o in rec["owner_totals"]
            ]
            st.dataframe(pd.DataFrame(owner_rows).set_index("Owner"), use_container_width=True, height=430)

    # ---- Player Activity ----
    with tab_players:
        add_drop_stats = load_player_add_drop_stats()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Revolving Door Players")
            st.caption("Players with the most combined adds + drops — highest churn on the wire.")
            revolving_rows = [
                {
                    "Player": p["player"],
                    "Adds": p["adds"],
                    "Drops": p["drops"],
                    "Total Moves": p["total_moves"],
                }
                for p in add_drop_stats[:20]
            ]
            st.dataframe(pd.DataFrame(revolving_rows).set_index("Player"), use_container_width=True, height=580)

        with col_right:
            st.subheader("Most Added Players")
            st.caption("Players claimed off waivers or added as free agents most often.")
            most_added = sorted(add_drop_stats, key=lambda x: -x["adds"])
            added_rows = [
                {"Player": p["player"], "Adds": p["adds"], "Drops": p["drops"]}
                for p in most_added[:20]
            ]
            st.dataframe(pd.DataFrame(added_rows).set_index("Player"), use_container_width=True, height=580)

    # ---- Owner Activity ----
    with tab_owners:
        activity = load_owner_waiver_activity()

        st.subheader("All-Time Waiver Wire Activity")
        st.caption("Includes both FAAB waiver claims and free-agent (no-bid) adds.")

        # Filter out John (placeholder) with no real activity
        activity = [o for o in activity if o["total_adds"] > 0 and o["owner"] != "John"]

        all_time_rows = [
            {
                "Owner": o["owner"],
                "Total Adds": o["total_adds"],
                "Waiver Claims": o["waiver_claims"],
                "FA Adds": o["fa_adds"],
                "Drops": o["drops"],
                "FAAB Spent": f"${o['faab_spent']}",
                "Failed Bids": o["waiver_failed"],
                "Bid Win%": f"{o['success_rate']:.1%}",
            }
            for o in activity
        ]
        st.dataframe(pd.DataFrame(all_time_rows).set_index("Owner"), use_container_width=True, height=460)

        st.divider()

        st.subheader("Activity by Season")
        seasons = sorted({r["season"] for r in load_owner_waiver_by_season()}, reverse=True)
        selected_season = st.selectbox("Season", seasons, key="waiver_season")

        season_data = [r for r in load_owner_waiver_by_season() if r["season"] == selected_season]
        season_rows = [
            {
                "Owner": r["owner"],
                "Waiver Claims": r["waiver_claims"],
                "FA Adds": r["fa_adds"],
                "Total Adds": r["waiver_claims"] + r["fa_adds"],
                "Drops": r["drops"],
                "FAAB Spent": f"${r['faab_spent']}",
            }
            for r in sorted(season_data, key=lambda x: -(x["waiver_claims"] + x["fa_adds"]))
        ]
        st.dataframe(pd.DataFrame(season_rows).set_index("Owner"), use_container_width=True, height=460)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "League Overview": page_overview,
    "Owner Profile": page_owner_profile,
    "Season Standings": page_season,
    "Head-to-Head": page_h2h,
    "Rivalries": page_rivalries,
    "Trades": page_trades,
    "Waivers": page_waivers,
}

with st.sidebar:
    st.markdown("## NNBE History")
    st.markdown("The New New Big East")
    st.divider()
    page = st.radio("Navigate", list(PAGES.keys()))

PAGES[page]()
