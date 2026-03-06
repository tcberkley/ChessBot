"""Bot analytics dashboard — run with: streamlit run dashboard/app.py"""
import datetime
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from data import (
    fetch_games, fetch_profile, fetch_game_stats,
    rating_history, today_summary
)

st.set_page_config(page_title="tombot1234 Analytics", layout="wide")
st.title("tombot1234 — Bot Analytics Dashboard")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    if st.button("Refresh data"):
        st.cache_data.clear()
    speeds = st.multiselect("Time controls", ["bullet", "blitz", "rapid", "classical"],
                            default=["bullet", "blitz", "rapid"])
    days_back = st.slider("Show last N days", 7, 90, 30)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
with st.spinner("Loading data..."):
    games_all = fetch_games()
    profile = fetch_profile()
    stats_df = fetch_game_stats()

cutoff = datetime.datetime.now() - datetime.timedelta(days=days_back)
games = games_all[games_all["ts"] >= cutoff] if not games_all.empty else games_all
if speeds:
    games = games[games["speed"].isin(speeds)]

# Attach speed to stats and filter
stats = pd.DataFrame()
if not stats_df.empty:
    stats = stats_df[stats_df["ts"] >= cutoff].copy()
    if not games_all.empty and "game_id" in games_all.columns:
        speed_map = games_all.set_index("game_id")["speed"].to_dict()
        stats["speed"] = stats["game_id"].map(speed_map)
        if speeds:
            stats = stats[stats["speed"].isin(speeds)]

# ---------------------------------------------------------------------------
# Row 1: KPI strip
# ---------------------------------------------------------------------------
today = today_summary(games_all)
perfs = profile.get("perfs", {})

avg_depth = stats["depth"].dropna().mean() if not stats.empty else None
avg_nodes = stats["nodes"].dropna().mean() if not stats.empty else None
avg_nps = stats["nps"].dropna().mean() if not stats.empty else None

blitz_perf = perfs.get("blitz", {})
blitz_rating = blitz_perf.get("rating", None)
blitz_prog = blitz_perf.get("prog", None)

k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Today W / D / L", f"{today['W']} / {today['D']} / {today['L']}")
k2.metric("Rating Δ today", f"{today['rating_change']:+d}")
k3.metric("Blitz rating", blitz_rating if blitz_rating else "—",
          f"{blitz_prog:+d}" if blitz_prog is not None else None)
k4.metric("Avg depth", f"{avg_depth:.1f}" if avg_depth is not None else "—")
k5.metric("Avg nodes/move", f"{avg_nodes/1e6:.2f}M" if avg_nodes is not None else "—")
k6.metric("Avg NPS", f"{avg_nps/1e6:.2f}M/s" if avg_nps is not None else "—")

st.divider()

# ---------------------------------------------------------------------------
# Row 2: Rating history | W/D/L pie | Win rate by opponent rating
# ---------------------------------------------------------------------------
rc1, rc2, rc3 = st.columns([5, 3, 4])

with rc1:
    rh = rating_history(games_all)
    if not rh.empty:
        filtered_rh = rh[rh["speed"].isin(speeds)] if speeds else rh
        fig_rating = px.line(filtered_rh, x="ts", y="my_rating", color="speed",
                             labels={"ts": "Date", "my_rating": "Rating", "speed": "Speed"},
                             title="Rating history")
        fig_rating.update_layout(height=280)
        st.plotly_chart(fig_rating, use_container_width=True)
    else:
        st.info("No rating history yet.")

with rc2:
    if not games.empty:
        result_counts = games["result"].value_counts()
        fig_pie = px.pie(values=result_counts.values, names=result_counts.index,
                         color=result_counts.index,
                         color_discrete_map={"win": "#2ecc71", "draw": "#95a5a6", "loss": "#e74c3c"},
                         title="W / D / L")
        fig_pie.update_layout(height=280)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No game data for selected filters.")

with rc3:
    games_rated = games[games["opp_rating"] > 0].copy() if not games.empty else pd.DataFrame()
    if not games_rated.empty:
        bins = [0, 1600, 1800, 2000, 2200, 2400, 9999]
        labels = ["<1600", "1600–1800", "1800–2000", "2000–2200", "2200–2400", "2400+"]
        games_rated["rating_bucket"] = pd.cut(games_rated["opp_rating"], bins=bins, labels=labels)
        bucket_wins = games_rated.groupby("rating_bucket", observed=True).apply(
            lambda g: pd.Series({
                "games": len(g),
                "win_pct": (g["result"] == "win").mean() * 100,
            })
        ).reset_index()
        fig_bucket = px.bar(bucket_wins, x="rating_bucket", y="win_pct",
                            hover_data=["games"],
                            title="Win rate by opponent rating",
                            labels={"rating_bucket": "Opponent rating", "win_pct": "Win %"},
                            color_discrete_sequence=["#3498db"])
        fig_bucket.update_layout(height=280)
        st.plotly_chart(fig_bucket, use_container_width=True)
    else:
        st.info("No rated game data.")

st.divider()

# ---------------------------------------------------------------------------
# Row 3: Engine performance charts
# ---------------------------------------------------------------------------
ec1, ec2 = st.columns(2)

with ec1:
    if not stats.empty and "depth" in stats.columns:
        fig_hist = px.histogram(stats.dropna(subset=["depth"]), x="depth",
                                title="Depth distribution", nbins=20,
                                color_discrete_sequence=["#3498db"],
                                labels={"depth": "Search depth"})
        fig_hist.update_layout(height=300)
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No engine stats for selected filters.")

with ec2:
    if not stats.empty and "speed" in stats.columns:
        grp = stats.groupby("speed", observed=True).agg(
            avg_depth=("depth", "mean"),
            avg_nps=("nps", "mean"),
        ).reset_index().dropna()

        if not grp.empty:
            fig_grouped = go.Figure()
            fig_grouped.add_bar(x=grp["speed"], y=grp["avg_depth"],
                                name="Avg depth", marker_color="#3498db",
                                yaxis="y")
            fig_grouped.add_bar(x=grp["speed"], y=grp["avg_nps"] / 1e6,
                                name="Avg NPS (M)", marker_color="#e67e22",
                                yaxis="y2")
            fig_grouped.update_layout(
                title="Avg depth & NPS by time control",
                height=300,
                barmode="group",
                yaxis=dict(title="Avg depth"),
                yaxis2=dict(title="Avg NPS (M/s)", overlaying="y", side="right"),
                legend=dict(orientation="h", y=1.1),
            )
            st.plotly_chart(fig_grouped, use_container_width=True)
        else:
            st.info("Not enough data to group by time control.")
    else:
        st.info("No engine stats for selected filters.")
