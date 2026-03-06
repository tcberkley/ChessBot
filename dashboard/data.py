"""Data fetching and parsing for the bot analytics dashboard."""
import json
import subprocess
import datetime
import pandas as pd
import requests
import streamlit as st

SERVER = "root@178.156.243.29"
USERNAME = "tombot1234"
LICHESS_API = "https://lichess.org/api"


# ---------------------------------------------------------------------------
# Lichess API
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def fetch_games() -> pd.DataFrame:
    """Fetch all bot games from Lichess API. Returns one row per game."""
    url = f"{LICHESS_API}/games/user/{USERNAME}"
    params = {
        "pgnInJson": "false",
        "clocks": "false",
        "opening": "true",
        "moves": "false",
        "rated": "true",
        "max": 5000,
    }
    headers = {"Accept": "application/x-ndjson"}
    resp = requests.get(url, params=params, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()

    rows = []
    for line in resp.iter_lines():
        if not line:
            continue
        game = json.loads(line)
        white = game["players"]["white"]
        black = game["players"]["black"]
        is_white = white.get("user", {}).get("name", "").lower() == USERNAME.lower()
        my = white if is_white else black
        opp = black if is_white else white

        winner = game.get("winner")  # "white", "black", or absent (draw)
        if winner is None:
            result = "draw"
        elif (winner == "white") == is_white:
            result = "win"
        else:
            result = "loss"

        opp_user = opp.get("user", {})
        rows.append({
            "game_id": game["id"],
            "ts": datetime.datetime.fromtimestamp(game["createdAt"] / 1000),
            "speed": game.get("speed", ""),
            "color": "white" if is_white else "black",
            "result": result,
            "status": game.get("status", ""),
            "my_rating": my.get("rating", 0),
            "my_rating_diff": my.get("ratingDiff", 0),
            "opp_name": opp_user.get("name", opp_user.get("id", "?")),
            "opp_rating": opp.get("rating", 0),
            "opp_rating_diff": opp.get("ratingDiff", 0),
            "opp_is_bot": opp.get("aiLevel") is not None or opp_user.get("title", "") == "BOT",
            "opening_eco": game.get("opening", {}).get("eco", ""),
            "opening_name": game.get("opening", {}).get("name", ""),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date
    return df.sort_values("ts").reset_index(drop=True)


@st.cache_data(ttl=300)
def fetch_profile() -> dict:
    """Fetch bot profile (current ratings)."""
    resp = requests.get(f"{LICHESS_API}/user/{USERNAME}", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Server file sync
# ---------------------------------------------------------------------------

def _scp(remote_path: str, local_path: str) -> bool:
    result = subprocess.run(
        ["scp", "-q", f"{SERVER}:{remote_path}", local_path],
        capture_output=True
    )
    return result.returncode == 0


@st.cache_data(ttl=120)
def fetch_game_stats() -> pd.DataFrame:
    """Sync game_stats.jsonl from server and parse into a DataFrame."""
    local = "/tmp/game_stats.jsonl"
    if not _scp("/root/lichess-bot-master/game_stats.jsonl", local):
        return pd.DataFrame()
    rows = []
    try:
        with open(local) as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    except FileNotFoundError:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.date
    return df


@st.cache_data(ttl=120)
def fetch_challenge_log() -> pd.DataFrame:
    """Sync challenge_log.csv from server and parse into a DataFrame."""
    local = "/tmp/challenge_log.csv"
    if not _scp("/root/scripts/challenge_log.csv", local):
        return pd.DataFrame()
    try:
        df = pd.read_csv(local)
    except Exception:
        return pd.DataFrame()
    if "timestamp_utc" in df.columns:
        df["ts"] = pd.to_datetime(df["timestamp_utc"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
        df["date"] = df["ts"].dt.date
    return df


# ---------------------------------------------------------------------------
# Derived helpers
# ---------------------------------------------------------------------------

def rating_history(games: pd.DataFrame) -> pd.DataFrame:
    """Return a DataFrame with cumulative rating per game, per speed."""
    if games.empty:
        return pd.DataFrame()
    df = games[["ts", "speed", "my_rating"]].copy()
    df = df[df["speed"].isin(["bullet", "blitz", "rapid", "classical"])]
    return df.sort_values("ts")


def win_type(row: pd.Series) -> str:
    """Classify win/loss method from status field."""
    status = row["status"]
    result = row["result"]
    if result == "draw":
        return status  # threefoldRepetition, stalemate, draw, etc.
    if result == "win":
        return status  # mate, resign, outoftime
    return status  # lose by mate, resign, outoftime


def today_summary(games: pd.DataFrame) -> dict:
    """W/L/D for today (Eastern Time)."""
    today = datetime.datetime.now().date()
    today_games = games[games["date"] == today] if not games.empty else pd.DataFrame()
    counts = today_games["result"].value_counts().to_dict() if not today_games.empty else {}
    return {
        "W": counts.get("win", 0),
        "L": counts.get("loss", 0),
        "D": counts.get("draw", 0),
        "games": len(today_games),
        "rating_change": int(today_games["my_rating_diff"].sum()) if not today_games.empty else 0,
    }
