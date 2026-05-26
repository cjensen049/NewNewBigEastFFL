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
)
from fantasy_analyzer.analysis.transactions import (
    get_trade_log,
    get_player_trade_history,
    get_owner_trade_stats,
    get_trade_partner_matrix,
    search_player_names,
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
    9: "9th", 10: "10th", 11: "11th", 12: "Last Place",
}

FINISH_COLOR = {
    1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32",
    12: "#FF4444",
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

    records = load_all_time_standings()
    seasons = load_available_seasons()

    # --- All-time standings table ---
    st.subheader("All-Time Standings")

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
            "Lasts": r.last_place_finishes if r.last_place_finishes else "",
        })

    df = pd.DataFrame(rows).set_index("Rank")
    st.dataframe(df, use_container_width=True, height=460)

    st.divider()

    # --- Season champions grid ---
    st.subheader("Season-by-Season Results")

    con = get_db()
    all_seasons_data = get_all_seasons(con)

    champ_rows = []
    for s in all_seasons_data:
        results = compute_playoff_results(
            con, s["league_id"], s["season"],
            s["playoff_week_start"], s["last_week"]
        )
        fmap = {r.finish: r.canonical_name for r in results if r.finish}
        champ_rows.append({
            "Season": s["season"],
            "Champion": fmap.get(1, "-"),
            "Runner-up": fmap.get(2, "-"),
            "3rd Place": fmap.get(3, "-"),
            "Last Place": fmap.get(12, "-"),
        })

    st.dataframe(
        pd.DataFrame(champ_rows).set_index("Season"),
        use_container_width=True,
        height=220,
    )

    st.divider()

    # --- Win% bar chart ---
    st.subheader("All-Time Win Percentage")
    fig = go.Figure(go.Bar(
        x=[r.canonical_name for r in records],
        y=[round(r.win_pct * 100, 1) for r in records],
        marker_color=["#FFD700" if r.championships else "#4a90d9" for r in records],
        text=[f"{r.win_pct:.1%}" for r in records],
        textposition="outside",
    ))
    fig.update_layout(
        yaxis_title="Win %",
        yaxis_range=[0, 100],
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20),
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


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
    playoff_apps = championships = last_places = 0
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

        finish = playoff_entry.finish if playoff_entry else None
        finish_label = FINISH_DISPLAY.get(finish, "-") if finish else "-"

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
            if playoff_entry.last_place:
                last_places += 1
            if finish:
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
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Record", f"{total_wins}-{total_losses}" + (f"-{total_ties}" if total_ties else ""))
    c2.metric("Win %", f"{overall_win_pct:.1%}")
    c3.metric("Avg PPG", f"{total_pts / total_games:.1f}")
    c4.metric("Playoffs", f"{playoff_apps}/{len(season_rows)}")
    c5.metric("Championships", championships)
    c6.metric("Last Places", last_places)

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

    seasons = load_available_seasons()
    selected_season = st.selectbox("Select season", sorted(seasons, reverse=True))

    data = load_season_breakdown(selected_season)
    if not data:
        st.warning("No data for this season.")
        return

    reg = data["regular_season"]

    rows = []
    for seed, rec in enumerate(reg, 1):
        playoff_entry = next(
            (r for r in data["playoff"].values() if r.canonical_name == rec.canonical_name),
            None,
        )
        finish = playoff_entry.finish if playoff_entry else None
        rows.append({
            "Seed": seed,
            "Owner": rec.canonical_name,
            "W-L": f"{rec.wins}-{rec.losses}",
            "Win%": f"{rec.win_pct:.1%}",
            "Pts For": round(rec.points_for, 1),
            "Pts Against": round(rec.points_against, 1),
            "PPG": round(rec.ppg, 1),
            "Finish": FINISH_DISPLAY.get(finish, "-") if finish else "-",
        })

    st.dataframe(
        pd.DataFrame(rows).set_index("Seed"),
        use_container_width=True,
        height=460,
    )

    # Points scored bar chart
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
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=20),
        height=340,
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Head-to-Head
# ---------------------------------------------------------------------------

def page_h2h():
    st.title("Head-to-Head")

    owners = load_owners()
    col1, col2 = st.columns(2)
    owner1 = col1.selectbox("Owner 1", owners, index=0)
    owner2 = col2.selectbox("Owner 2", owners, index=1)

    if owner1 == owner2:
        st.warning("Pick two different owners.")
        return

    df = load_h2h(owner1, owner2)
    if df.empty:
        st.info("No head-to-head matchups found.")
        return

    pts1_col = f"{owner1} Pts"
    pts2_col = f"{owner2} Pts"

    wins1 = (df[pts1_col] > df[pts2_col]).sum()
    wins2 = (df[pts1_col] < df[pts2_col]).sum()
    ties = (df[pts1_col] == df[pts2_col]).sum()
    games = len(df)

    # Summary metrics
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{owner1} Wins", wins1)
    c2.metric("Ties", ties)
    c3.metric(f"{owner2} Wins", wins2)

    st.divider()

    # Matchup history chart
    st.subheader("Points Each Game")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(1, games + 1)),
        y=df[pts1_col].tolist(),
        name=owner1,
        mode="lines+markers",
        line=dict(color="#4a90d9"),
    ))
    fig.add_trace(go.Scatter(
        x=list(range(1, games + 1)),
        y=df[pts2_col].tolist(),
        name=owner2,
        mode="lines+markers",
        line=dict(color="#e05a5a"),
    ))
    # Shade wins
    labels = [f"{r['Season']} Wk{r['Week']}" for _, r in df.iterrows()]
    fig.update_xaxes(tickvals=list(range(1, games + 1)), ticktext=labels, tickangle=45)
    fig.update_layout(
        yaxis_title="Points",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=80),
        height=380,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Full matchup log
    st.subheader("All Matchups")
    log = df.copy()
    log["Winner"] = log.apply(
        lambda r: owner1 if r[pts1_col] > r[pts2_col]
        else (owner2 if r[pts2_col] > r[pts1_col] else "Tie"),
        axis=1,
    )
    st.dataframe(log.set_index("Season"), use_container_width=True, height=420)


# ---------------------------------------------------------------------------
# Page: Trades
# ---------------------------------------------------------------------------

def page_trades():
    st.title("Trades")

    tab1, tab2, tab3 = st.tabs(["Trade Log", "Player Trade Tree", "Owner Tendencies"])

    # ---- Tab 1: Trade Log ----
    with tab1:
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

    # ---- Tab 2: Player Trade Tree ----
    with tab2:
        st.markdown("Search for a player to see every team they passed through.")
        query = st.text_input("Player name", placeholder="e.g. Davante Adams")

        if query and len(query) >= 2:
            suggestions = search_player_names(get_db(), query)
            if not suggestions:
                st.warning("No traded players found matching that name.")
            else:
                selected_player = st.selectbox("Select player", suggestions)
                if selected_player:
                    full_name, stops = get_player_trade_history(get_db(), selected_player)

                    if not stops:
                        st.info(f"{full_name} has no recorded trades.")
                    else:
                        st.subheader(f"{full_name} — Trade History")
                        st.caption(f"Traded {len(stops)} time(s)")

                        # Timeline visualization
                        fig = go.Figure()
                        for i, stop in enumerate(stops):
                            label = f"{stop.season} Wk{stop.week}"
                            fig.add_annotation(
                                x=i, y=0.5,
                                text=f"<b>{stop.to_owner}</b><br><sub>{label}</sub>",
                                showarrow=False,
                                font=dict(size=13),
                                bgcolor="#1a3a5c",
                                bordercolor="#4a90d9",
                                borderwidth=1,
                                borderpad=6,
                            )
                            if i > 0:
                                fig.add_annotation(
                                    x=i - 0.5, y=0.5,
                                    text=f"<sub>{stop.from_owner} →</sub>",
                                    showarrow=False,
                                    font=dict(size=10, color="#aaa"),
                                )
                        fig.update_layout(
                            xaxis=dict(visible=False, range=[-0.5, len(stops) - 0.5]),
                            yaxis=dict(visible=False, range=[0, 1]),
                            height=160,
                            margin=dict(l=20, r=20, t=20, b=20),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig, use_container_width=True)

                        # Detail table
                        detail_rows = [
                            {
                                "Season": s.season,
                                "Week": s.week,
                                "From": s.from_owner,
                                "To": s.to_owner,
                            }
                            for s in stops
                        ]
                        st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

    # ---- Tab 3: Owner Tendencies ----
    with tab3:
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
# Navigation
# ---------------------------------------------------------------------------

PAGES = {
    "League Overview": page_overview,
    "Owner Profile": page_owner_profile,
    "Season Standings": page_season,
    "Head-to-Head": page_h2h,
    "Trades": page_trades,
}

with st.sidebar:
    st.markdown("## NNBE History")
    st.markdown("The New New Big East")
    st.divider()
    page = st.radio("Navigate", list(PAGES.keys()))

PAGES[page]()
