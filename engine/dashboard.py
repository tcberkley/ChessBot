#!/usr/bin/env python3
"""
dashboard.py — Live chess bot dashboard for tombot1234
Run as: /root/lichess-bot-master/venv/bin/python3 /root/scripts/dashboard.py
Listens on 0.0.0.0:8080

Data sources:
  - /root/lichess-bot-master/game_stats.jsonl  (engine stats per move)
  - https://lichess.org/api/account/playing     (detect active game)
  - https://lichess.org/api/bot/game/stream/{}  (NDJSON move stream)
  - https://lichess.org/api/cloud-eval          (Stockfish cloud eval)
"""

import collections
import csv
import json
import os
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chess
import chess.engine
import requests

# ── Constants ─────────────────────────────────────────────────────────────────
PORT = 8080
BOT_USERNAME = "tombot1234"
STATS_PATH = "/root/lichess-bot-master/game_stats.jsonl"
LICHESS_API = "https://lichess.org"
POLL_INTERVAL = 1   # seconds between /api/account/playing polls
SF_DEPTH = 15          # depth cap for local Stockfish
SF_TIME_LIMIT = 0.15   # 150ms hard time cap
SF_FEN_CACHE_TTL = 300 # cache each FEN result for 5 min
CHALLENGE_LOG_PATH = "/root/scripts/challenge_log.csv"
DAILY_WINDOW_PATH  = "/root/lichess-bot-master/daily_window.txt"
PROFILE_CACHE_TTL  = 60   # seconds to cache /api/account response
CHALLENGE_LOG_N    = 30   # max challenge rows to display


# ── Token loading ─────────────────────────────────────────────────────────────
def load_token() -> str:
    token = os.environ.get("LICHESS_BOT_TOKEN", "")
    if not token:
        env_path = Path("/root/lichess-bot-master/.env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, val = line.partition("=")
                        if key.strip() == "LICHESS_BOT_TOKEN":
                            token = val.strip()
                            break
    return token


# ── Challenge log / daily window / profile helpers ───────────────────────────
def read_challenge_log(path: str, n: int = CHALLENGE_LOG_N) -> list:
    """Return the last n rows from challenge_log.csv as list of dicts (newest first)."""
    try:
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            rows = collections.deque(reader, maxlen=n)
        return list(reversed(rows))
    except FileNotFoundError:
        return []
    except Exception:
        return []


def read_daily_sent(path: str) -> "int | None":
    """Read challenges-sent-today count from daily_window.txt.
    Format: 'timestamp,challenge_count,game_count'
    """
    try:
        with open(path) as f:
            content = f.read().strip()
        parts = content.split(",")
        return int(parts[1]) if len(parts) >= 2 else None
    except Exception:
        return None


_profile_cache: dict = {"ts": 0, "data": None}


def fetch_bot_profile(token: str) -> "dict | None":
    """GET /api/account — returns rating/stats dict, cached PROFILE_CACHE_TTL seconds."""
    now = time.time()
    if now - _profile_cache["ts"] < PROFILE_CACHE_TTL and _profile_cache["data"]:
        return _profile_cache["data"]
    try:
        resp = requests.get(
            f"{LICHESS_API}/api/account",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            perfs = data.get("perfs", {})
            result = {
                "bullet_rating":  perfs.get("bullet",  {}).get("rating"),
                "blitz_rating":   perfs.get("blitz",   {}).get("rating"),
                "rapid_rating":   perfs.get("rapid",   {}).get("rating"),
                "bullet_games":   perfs.get("bullet",  {}).get("games"),
                "blitz_games":    perfs.get("blitz",   {}).get("games"),
                "rapid_games":    perfs.get("rapid",   {}).get("games"),
                "nb_games":       data.get("count", {}).get("all"),
                "nb_wins":        data.get("count", {}).get("win"),
                "nb_losses":      data.get("count", {}).get("loss"),
                "nb_draws":       data.get("count", {}).get("draw"),
            }
            _profile_cache["ts"]   = now
            _profile_cache["data"] = result
            return result
    except Exception:
        pass
    return _profile_cache["data"]  # return stale on error


# ── SharedState ───────────────────────────────────────────────────────────────
class SharedState:
    def __init__(self):
        self._lock = threading.Lock()
        self.state = {"type": "idle"}
        self._clients: list[queue.Queue] = []

    def update(self, new_state: dict):
        with self._lock:
            self.state = new_state
            payload = f"data: {json.dumps(new_state)}\n\n"
            dead = []
            for q in self._clients:
                try:
                    q.put_nowait(payload)
                except Exception:
                    dead.append(q)
            for q in dead:
                self._clients.remove(q)

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=20)
        with self._lock:
            self._clients.append(q)
            # Send current state immediately to new subscriber
            q.put_nowait(f"data: {json.dumps(self.state)}\n\n")
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            try:
                self._clients.remove(q)
            except ValueError:
                pass

    def get(self) -> dict:
        with self._lock:
            return dict(self.state)


# ── FEN reconstruction helpers ────────────────────────────────────────────────
def build_board_from_moves(initial_fen: str, moves_str: str):
    """Return (board, last_move_uci) after replaying all UCI moves."""
    if initial_fen and initial_fen != "startpos":
        board = chess.Board(initial_fen)
    else:
        board = chess.Board()
    last_move = None
    if moves_str:
        for uci in moves_str.split():
            try:
                m = chess.Move.from_uci(uci)
                board.push(m)
                last_move = uci
            except Exception:
                pass
    return board, last_move


def parse_game_full(event: dict, game_id: str) -> dict:
    white = event.get("white", {})
    black = event.get("black", {})
    bot_color = "white" if white.get("id", "").lower() == BOT_USERNAME.lower() else "black"

    initial_fen = event.get("initialFen") or "startpos"
    state = event.get("state", {})
    moves_str = state.get("moves", "")
    board, last_move = build_board_from_moves(initial_fen, moves_str)

    turn = "white" if board.turn == chess.WHITE else "black"
    clock = event.get("clock", {})

    return {
        "type": "update",
        "game": {
            "id": game_id,
            "white": {"name": white.get("name", white.get("id", "?")), "rating": white.get("rating")},
            "black": {"name": black.get("name", black.get("id", "?")), "rating": black.get("rating")},
            "speed": event.get("speed", ""),
            "rated": event.get("rated", False),
            "clock_initial": clock.get("initial", 0),
            "clock_increment": clock.get("increment", 0),
            "url": f"https://lichess.org/{game_id}",
        },
        "bot_color": bot_color,
        "position": {"fen": board.fen(), "last_move": last_move},
        "clock": {
            "wtime_ms": state.get("wtime", 0),
            "btime_ms": state.get("btime", 0),
            "turn": turn,
        },
        "engine": None,
        "sf": None,
    }


def apply_game_state(current: dict, event: dict) -> dict:
    moves_str = event.get("moves", "")
    board, last_move = build_board_from_moves("startpos", moves_str)
    turn = "white" if board.turn == chess.WHITE else "black"
    status = event.get("status", "started")

    updated = dict(current)
    updated["position"] = {"fen": board.fen(), "last_move": last_move}
    updated["clock"] = {
        "wtime_ms": event.get("wtime", 0),
        "btime_ms": event.get("btime", 0),
        "turn": turn,
    }
    if status not in ("started", "created"):
        updated["type"] = "idle"
    return updated


# ── Game stream thread ────────────────────────────────────────────────────────
def stream_game(shared: SharedState, token: str, game_id: str, stop_event: threading.Event):
    url = f"{LICHESS_API}/api/bot/game/stream/{game_id}"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            timeout=(10, None),  # connect timeout=10s, read=unlimited
        )
        for raw_line in resp.iter_lines():
            if stop_event.is_set():
                break
            if not raw_line:
                continue  # Lichess sends empty lines as keepalives
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            t = event.get("type")
            if t == "gameFull":
                state = parse_game_full(event, game_id)
                shared.update(state)
            elif t == "gameState":
                current = shared.get()
                if current.get("type") == "update":
                    updated = apply_game_state(current, event)
                    shared.update(updated)
                    # If game ended, go idle
                    if updated.get("type") == "idle":
                        break
            elif t in ("gameFinish",):
                shared.update({"type": "idle"})
                break
    except Exception:
        pass  # GameMonitor will detect missing game_id on next poll


# ── Efficient file tail ────────────────────────────────────────────────────────
def tail_stats(path: str, file_pos: int, game_id: str):
    """Read only new lines since last call. Returns (new_pos, latest_entry | None)."""
    latest = None
    try:
        with open(path, "r") as f:
            f.seek(file_pos)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("game_id") == game_id:
                        latest = entry
                except json.JSONDecodeError:
                    pass
            new_pos = f.tell()
        return new_pos, latest
    except FileNotFoundError:
        return 0, None


# ── Local Stockfish eval ──────────────────────────────────────────────────────
class SFEngine:
    """Persistent local Stockfish wrapper. Thread-safe via a lock."""
    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self._cache: dict = {}  # fen -> (timestamp, result)

    def _open(self):
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci("stockfish")
            self._engine.configure({"Threads": 1, "Hash": 16})
        except Exception:
            self._engine = None

    def analyse(self, fen: str):
        now = time.time()
        with self._lock:
            if fen in self._cache:
                ts, result = self._cache[fen]
                if now - ts < SF_FEN_CACHE_TTL:
                    return result
            try:
                if self._engine is None:
                    self._open()
                if self._engine is None:
                    return None
                board = chess.Board(fen)
                info = self._engine.analyse(
                    board,
                    chess.engine.Limit(depth=SF_DEPTH, time=SF_TIME_LIMIT)
                )
                score = info.get("score")
                if score:
                    pov = score.white()  # always from white's perspective
                    result = {
                        "cp":    pov.score(mate_score=10000),
                        "mate":  pov.mate(),
                        "depth": info.get("depth"),
                    }
                    # Clamp cp to ±2000 if not mate
                    if result["mate"] is None and result["cp"] is not None:
                        result["cp"] = max(-2000, min(2000, result["cp"]))
                else:
                    result = None
            except Exception:
                self._engine = None  # restart next call
                result = None
            self._cache[fen] = (now, result)
            return result

    def clear_cache(self):
        with self._lock:
            self._cache.clear()

    def quit(self):
        with self._lock:
            if self._engine:
                try:
                    self._engine.quit()
                except Exception:
                    pass
                self._engine = None


# ── Game monitor thread ───────────────────────────────────────────────────────
def game_monitor_loop(shared: SharedState, token: str):
    current_game_id = None
    stream_thread = None
    stream_stop_event = None
    file_pos = 0
    sf_engine = SFEngine()
    last_engine_stats = None  # persist last valid (non-null) engine stats
    last_sf_fen = None  # track last FEN we ran SF on

    while True:
        try:
            resp = requests.get(
                f"{LICHESS_API}/api/account/playing",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            data = resp.json()
            games = data.get("nowPlaying", [])
            game_id = games[0]["gameId"] if games else None

            if game_id != current_game_id:
                # Stop old stream thread
                if stream_stop_event is not None:
                    stream_stop_event.set()

                current_game_id = game_id
                file_pos = 0  # reset tail position for new game
                sf_engine.clear_cache()
                last_engine_stats = None  # clear stats for new game
                last_sf_fen = None

                if game_id is None:
                    challenges = read_challenge_log(CHALLENGE_LOG_PATH)
                    daily_sent = read_daily_sent(DAILY_WINDOW_PATH)
                    profile    = fetch_bot_profile(token)
                    shared.update({
                        "type":       "idle",
                        "challenges": challenges,
                        "daily_sent": daily_sent,
                        "profile":    profile,
                    })
                    stream_stop_event = None
                    stream_thread = None
                else:
                    stop_ev = threading.Event()
                    stream_stop_event = stop_ev
                    stream_thread = threading.Thread(
                        target=stream_game,
                        args=(shared, token, game_id, stop_ev),
                        daemon=True,
                        name=f"Stream-{game_id}",
                    )
                    stream_thread.start()

            # Refresh idle state every poll cycle (challenge feed + profile)
            if game_id is None:
                challenges = read_challenge_log(CHALLENGE_LOG_PATH)
                daily_sent = read_daily_sent(DAILY_WINDOW_PATH)
                profile    = fetch_bot_profile(token)
                shared.update({
                    "type":       "idle",
                    "challenges": challenges,
                    "daily_sent": daily_sent,
                    "profile":    profile,
                })

            # Tail game_stats.jsonl for engine stats
            if game_id:
                file_pos, latest_stats = tail_stats(STATS_PATH, file_pos, game_id)
                # Only promote to last_engine_stats if at least one key field is non-null
                if latest_stats and any(
                    latest_stats.get(k) is not None
                    for k in ("depth", "nodes", "nps", "cp", "mate")
                ):
                    last_engine_stats = latest_stats

                # Always re-push last known stats every poll cycle to self-correct race conditions
                if last_engine_stats:
                    current = shared.get()
                    if current.get("type") == "update":
                        fen = current.get("position", {}).get("fen", "")
                        # Only run SF eval when a new bot move has occurred
                        if fen and fen != last_sf_fen:
                            last_sf_fen = fen
                            sf = sf_engine.analyse(fen)
                            current["sf"] = sf
                        current["engine"] = last_engine_stats
                        shared.update(current)

        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


# ── Frontend HTML ─────────────────────────────────────────────────────────────
HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>tombot1234 — Live Dashboard</title>
<link rel="stylesheet"
  href="https://cdn.jsdelivr.net/npm/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #1a1a2e;
  color: #e0e0e0;
  font-family: 'Segoe UI', system-ui, sans-serif;
  min-height: 100vh;
}
.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 16px;
}
header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 20px;
  border-bottom: 1px solid #2d2d44;
  margin-bottom: 20px;
}
header h1 { font-size: 1.4rem; font-weight: 600; color: #e8e8f0; }
.status-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #444; transition: background 0.4s;
  flex-shrink: 0;
}
.status-dot.live { background: #2ecc71; box-shadow: 0 0 8px #2ecc71; }
.main-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 20px;
  align-items: start;
}
.board-col { position: relative; padding-left: 20px; }
#board { width: 380px; }
.eval-bar-wrap {
  position: absolute;
  left: 0; top: 28px;
  width: 10px;
  height: 380px;
  background: #333;
  border-radius: 4px;
  overflow: hidden;
}
.board-player-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #c0c0d8;
  height: 28px;
  display: flex;
  align-items: center;
}
.captures {
  font-size: 0.75rem;
  margin-left: 6px;
  opacity: 0.85;
  letter-spacing: -1px;
}
.eval-bar-white {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  background: #ddd;
  transition: height 0.5s ease;
}
.info-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}
.card {
  background: #16213e;
  border: 1px solid #2d2d54;
  border-radius: 8px;
  padding: 14px 16px;
}
.card-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6878a8;
  margin-bottom: 10px;
  font-weight: 600;
}
.game-players {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
}
.player-name { font-weight: 600; color: #c8d0f0; }
.player-rating { color: #8898c8; font-size: 0.85rem; margin-left: 4px; }
.vs-badge {
  font-size: 0.75rem; color: #556; background: #0f1630;
  padding: 2px 8px; border-radius: 3px; flex-shrink: 0;
}
.game-meta { margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
.meta-chip {
  font-size: 0.75rem; background: #0f1630;
  padding: 2px 10px; border-radius: 12px; color: #8898c8;
  text-transform: capitalize;
}
.meta-chip.rated { color: #f39c12; }
.game-link { margin-top: 8px; font-size: 0.8rem; }
.game-link a { color: #3498db; text-decoration: none; }
.game-link a:hover { text-decoration: underline; }
.clocks {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.clock-box {
  background: #0f1630;
  border-radius: 6px;
  padding: 12px;
  text-align: center;
  border: 2px solid transparent;
  transition: border-color 0.3s, opacity 0.3s;
}
.clock-box.active { border-color: #3498db; }
.clock-box.low-time { border-color: #e74c3c !important; }
.clock-label {
  font-size: 0.7rem; color: #6878a8;
  text-transform: uppercase; margin-bottom: 4px;
}
.clock-time {
  font-size: 1.8rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #e8e8f0;
  letter-spacing: 0.02em;
}
.clock-box.low-time .clock-time { color: #e74c3c; }
.eval-display { display: flex; gap: 20px; }
.eval-item { flex: 1; }
.eval-label {
  font-size: 0.7rem; color: #6878a8;
  text-transform: uppercase; margin-bottom: 4px;
}
.eval-value {
  font-size: 1.4rem; font-weight: 700;
  font-variant-numeric: tabular-nums; color: #e8e8f0;
}
.eval-value.positive { color: #2ecc71; }
.eval-value.negative { color: #e74c3c; }
.stats-table { width: 100%; border-collapse: collapse; }
.stats-table th {
  text-align: left; font-size: 0.7rem; color: #6878a8;
  text-transform: uppercase; padding: 4px 6px;
  border-bottom: 1px solid #2d2d44;
}
.stats-table td {
  font-size: 0.85rem; padding: 6px 6px;
  font-variant-numeric: tabular-nums;
  color: #c8d0f0;
}
#idle-screen { display: none; }
#idle-stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 4px;
}
.idle-stat-card {
  background: #16213e;
  border: 1px solid #2d2d54;
  border-radius: 8px;
  padding: 12px 16px;
  text-align: center;
}
.idle-stat-label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6878a8;
  margin-bottom: 6px;
}
.idle-stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #e8e8f0;
  font-variant-numeric: tabular-nums;
}
.idle-stat-sub {
  font-size: 0.75rem;
  color: #6878a8;
  margin-top: 2px;
}
.challenge-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.challenge-table th {
  text-align: left;
  font-size: 0.68rem;
  color: #6878a8;
  text-transform: uppercase;
  padding: 4px 6px;
  border-bottom: 1px solid #2d2d44;
}
.challenge-table td {
  padding: 5px 6px;
  color: #c8d0f0;
  font-variant-numeric: tabular-nums;
  border-bottom: 1px solid #1a1a30;
}
.ch-out-sent     { color: #3498db; }
.ch-out-declined { color: #e67e22; }
.ch-in-accepted  { color: #2ecc71; }
.ch-in-declined  { color: #888;    }
.ch-dir-out { font-weight:600; color:#3498db; }
.ch-dir-in  { font-weight:600; color:#2ecc71; }
@media (max-width: 720px) {
  .main-grid { grid-template-columns: 1fr; }
  #board { width: 100%; max-width: 340px; margin: 0 auto; }
  .board-col { padding-left: 0; }
  .eval-bar-wrap { display: none; }
}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="status-dot" id="status-dot"></div>
    <h1>tombot1234 — Live Dashboard</h1>
  </header>

  <div id="game-view" style="display:none">
    <div class="main-grid">
      <div class="board-col">
        <div class="eval-bar-wrap">
          <div class="eval-bar-white" id="eval-bar" style="height:50%"></div>
        </div>
        <div id="opponent-label" class="board-player-label">
          <span id="opponent-name-text">—</span>
          <span id="opp-captures" class="captures"></span>
        </div>
        <div id="board"></div>
        <div id="bot-label" class="board-player-label">
          <span id="bot-name-text">—</span>
          <span id="bot-captures" class="captures"></span>
        </div>
      </div>
      <div class="info-col">

        <div class="card">
          <div class="card-title">Game</div>
          <div class="game-players">
            <span>
              <span class="player-name" id="white-name">—</span>
              <span class="player-rating" id="white-rating"></span>
            </span>
            <span class="vs-badge">vs</span>
            <span>
              <span class="player-name" id="black-name">—</span>
              <span class="player-rating" id="black-rating"></span>
            </span>
          </div>
          <div class="game-meta">
            <span class="meta-chip" id="speed-chip"></span>
            <span class="meta-chip" id="rated-chip"></span>
            <span class="meta-chip" id="tc-chip"></span>
          </div>
          <div class="game-link"><a id="game-url" href="#" target="_blank">View on Lichess →</a></div>
        </div>

        <div class="card">
          <div class="card-title">Clock</div>
          <div class="clocks">
            <div class="clock-box" id="white-clock-box">
              <div class="clock-label">White</div>
              <div class="clock-time" id="white-clock">0:00</div>
            </div>
            <div class="clock-box" id="black-clock-box">
              <div class="clock-label">Black</div>
              <div class="clock-time" id="black-clock">0:00</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Evaluation</div>
          <div class="eval-display">
            <div class="eval-item">
              <div class="eval-label">Bot (v2.1)</div>
              <div class="eval-value" id="bot-eval">—</div>
            </div>
            <div class="eval-item">
              <div class="eval-label">Stockfish Local</div>
              <div class="eval-value" id="sf-eval">—</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Engine Stats</div>
          <table class="stats-table">
            <thead>
              <tr>
                <th>Depth</th><th>Nodes</th><th>NPS</th><th>Time</th><th>TB Hits</th><th>Source</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td id="st-depth">—</td>
                <td id="st-nodes">—</td>
                <td id="st-nps">—</td>
                <td id="st-time">—</td>
                <td id="st-tbhits">—</td>
                <td id="st-source">—</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </div>
  </div>

  <div id="idle-screen">
    <!-- Top row: bot stats cards -->
    <div id="idle-stats-row"></div>
    <!-- Challenge feed -->
    <div class="card" style="margin-top:14px">
      <div class="card-title">Challenge Activity</div>
      <table class="challenge-table" id="challenge-table">
        <thead>
          <tr>
            <th>Time</th><th>Dir</th><th>Event</th>
            <th>Opponent</th><th>Rating</th><th>TC</th><th>Reason</th>
          </tr>
        </thead>
        <tbody id="challenge-tbody"></tbody>
      </table>
      <div id="challenge-empty" style="display:none;color:#445;font-size:0.85rem;padding:16px 0;text-align:center">
        No challenge activity yet
      </div>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
<script>
// Inject highlight style
const _hs = document.createElement("style");
_hs.textContent = ".sq-highlight { background: rgba(52,152,219,0.45) !important; }";
document.head.appendChild(_hs);

// ── State ───────────────────────────────────────────────────────────────────
let board = null;
let clockInterval = null;
let wtime_ms = 0, btime_ms = 0;
let currentTurn = "white";
let clockTickAt = null;
let lastClockWtime = -1, lastClockBtime = -1, lastClockTurn = null;

// ── Helpers ─────────────────────────────────────────────────────────────────
function fmtMs(ms) {
  if (ms == null || ms < 0) ms = 0;
  const s = Math.floor(ms / 1000);
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}
function fmtNum(n, div, suffix) {
  if (n == null) return "—";
  if (n >= div) return (n / div).toFixed(2) + suffix;
  return String(n);
}
function fmtNodes(n) {
  if (n == null) return "—";
  if (n >= 1e9) return (n/1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n/1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n/1e3).toFixed(1) + "K";
  return String(n);
}
function fmtNps(n) {
  if (n == null) return "—";
  if (n >= 1e6) return (n/1e6).toFixed(2) + "M/s";
  if (n >= 1e3) return (n/1e3).toFixed(0) + "K/s";
  return n + "/s";
}
function fmtCp(cp, mate) {
  if (mate != null) return (mate > 0 ? "+" : "") + "#" + mate;
  if (cp == null) return "—";
  const v = (cp / 100).toFixed(2);
  return cp >= 0 ? "+" + v : v;
}
function cpClass(cp, mate) {
  if (cp == null && mate == null) return "";
  if (mate != null) return mate > 0 ? "positive" : "negative";
  return cp >= 0 ? "positive" : "negative";
}
function evalToPercent(cp, mate) {
  if (mate != null) return mate > 0 ? 98 : 2;
  if (cp == null) return 50;
  return Math.min(98, Math.max(2, 50 + 50 * Math.tanh(cp / 400)));
}

// ── Clock ticker ─────────────────────────────────────────────────────────────
function startClock() {
  stopClock();
  clockTickAt = Date.now();
  clockInterval = setInterval(() => {
    const elapsed = Date.now() - clockTickAt;
    const w = currentTurn === "white" ? Math.max(0, wtime_ms - elapsed) : wtime_ms;
    const b = currentTurn === "black" ? Math.max(0, btime_ms - elapsed) : btime_ms;
    document.getElementById("white-clock").textContent = fmtMs(w);
    document.getElementById("black-clock").textContent = fmtMs(b);
    const wBox = document.getElementById("white-clock-box");
    const bBox = document.getElementById("black-clock-box");
    wBox.classList.toggle("active", currentTurn === "white");
    bBox.classList.toggle("active", currentTurn === "black");
    wBox.classList.toggle("low-time", currentTurn === "white" && w < 10000);
    bBox.classList.toggle("low-time", currentTurn === "black" && b < 10000);
  }, 500);
}
function stopClock() {
  if (clockInterval) { clearInterval(clockInterval); clockInterval = null; }
}

// ── Board ────────────────────────────────────────────────────────────────────
function initBoard(orientation) {
  if (board) { try { board.destroy(); } catch(e) {} }
  board = Chessboard("board", {
    position: "start",
    orientation: orientation,
    pieceTheme: "/img/{piece}.png",
    draggable: false,
  });
}
function setPosition(fen, lastMove) {
  if (!board) return;
  board.position(fen, false);
  $(".square-55d63").removeClass("sq-highlight");
  if (lastMove && lastMove.length >= 4) {
    const from = lastMove.slice(0, 2);
    const to   = lastMove.slice(2, 4);
    $("[data-square='" + from + "']").addClass("sq-highlight");
    $("[data-square='" + to   + "']").addClass("sq-highlight");
  }
}

// ── Material captured ────────────────────────────────────────────────────────
const PIECE_SYMBOLS = {
  wQ: '\u2655', wR: '\u2656', wB: '\u2657', wN: '\u2658', wP: '\u2659',
  bQ: '\u265b', bR: '\u265c', bB: '\u265d', bN: '\u265e', bP: '\u265f',
};
const INITIAL_COUNTS = {Q:1, R:2, B:2, N:2, P:8};

const PIECE_VALUES = {Q:9, R:5, B:3, N:3, P:1};

function computeCaptures(fen) {
  const g = new Chess(fen);
  const cnt = {w:{Q:0,R:0,B:0,N:0,P:0}, b:{Q:0,R:0,B:0,N:0,P:0}};
  ['a','b','c','d','e','f','g','h'].forEach(function(f) {
    for (let r = 1; r <= 8; r++) {
      const p = g.get(f + r);
      if (p) cnt[p.color][p.type.toUpperCase()]++;
    }
  });
  const captured = {w:'', b:'', advantage: 0};
  let wLostVal = 0, bLostVal = 0;
  ['Q','R','B','N','P'].forEach(function(pt) {
    const wLost = INITIAL_COUNTS[pt] - cnt.w[pt];
    const bLost = INITIAL_COUNTS[pt] - cnt.b[pt];
    for (let i = 0; i < wLost; i++) captured.w += PIECE_SYMBOLS['w' + pt];
    for (let i = 0; i < bLost; i++) captured.b += PIECE_SYMBOLS['b' + pt];
    wLostVal += wLost * PIECE_VALUES[pt];
    bLostVal += bLost * PIECE_VALUES[pt];
  });
  // positive = white ahead (black lost more material)
  captured.advantage = bLostVal - wLostVal;
  return captured; // captured.w = white pieces taken, captured.b = black pieces taken
}

// ── Render ───────────────────────────────────────────────────────────────────
function statCard(label, value, sub) {
  const val = value != null ? String(value) : "—";
  const subHtml = sub != null ? "<div class='idle-stat-sub'>" + sub + "</div>" : "";
  return "<div class='idle-stat-card'>"
       + "<div class='idle-stat-label'>" + label + "</div>"
       + "<div class='idle-stat-value'>" + val + "</div>"
       + subHtml + "</div>";
}

function renderIdle(s) {
  stopClock();
  lastClockWtime = -1; lastClockBtime = -1; lastClockTurn = null;
  document.getElementById("game-view").style.display = "none";
  document.getElementById("idle-screen").style.display = "block";
  document.getElementById("status-dot").classList.remove("live");
  document.getElementById("bot-name-text").textContent = "—";
  document.getElementById("opponent-name-text").textContent = "—";
  document.getElementById("bot-captures").textContent = "";
  document.getElementById("opp-captures").textContent = "";

  // Profile stats
  const p = s && s.profile;
  const daily = s && s.daily_sent;
  const statsRow = document.getElementById("idle-stats-row");
  statsRow.innerHTML = [
    statCard("Bullet",  p && p.bullet_rating,  p ? p.bullet_games + " games" : null),
    statCard("Blitz",   p && p.blitz_rating,   p ? p.blitz_games  + " games" : null),
    statCard("Rapid",   p && p.rapid_rating,   p ? p.rapid_games  + " games" : null),
    statCard("Total Games", p && p.nb_games,
             p ? p.nb_wins + "W / " + p.nb_draws + "D / " + p.nb_losses + "L" : null),
    statCard("Challenges Today", daily != null ? daily + " / 250" : null, "daily limit"),
  ].join("");

  // Challenge feed
  const rows = s && s.challenges;
  const tbody = document.getElementById("challenge-tbody");
  const empty = document.getElementById("challenge-empty");
  if (!rows || rows.length === 0) {
    tbody.innerHTML = "";
    empty.style.display = "block";
  } else {
    empty.style.display = "none";
    tbody.innerHTML = rows.map(function(r) {
      const dir    = r.direction === "outgoing" ? "outgoing" : "incoming";
      const evt    = r.event || "";
      const cls    = "ch-" + dir.slice(0,3) + "-" + evt;
      const dirEl  = "<span class='ch-dir-" + dir.slice(0,3) + "'>"
                   + (dir === "outgoing" ? "\u2192" : "\u2190") + "</span>";
      const ts     = r.timestamp_utc ? r.timestamp_utc.slice(11,19) : "";
      const tc     = r.time_control  || "—";
      const opp    = r.opponent      || "—";
      const rat    = r.opponent_rating || "—";
      const reason = r.decline_reason || "";
      const evtEl  = "<span class='" + cls + "'>" + evt + "</span>";
      return "<tr><td>" + ts + "</td><td>" + dirEl + "</td><td>" + evtEl
           + "</td><td>" + opp + "</td><td>" + rat + "</td><td>" + tc
           + "</td><td>" + reason + "</td></tr>";
    }).join("");
  }
}

function renderUpdate(s) {
  document.getElementById("game-view").style.display = "block";
  document.getElementById("idle-screen").style.display = "none";
  document.getElementById("status-dot").classList.add("live");

  const g = s.game, pos = s.position, clk = s.clock, eng = s.engine, sf = s.sf;

  // Game info
  document.getElementById("white-name").textContent   = g.white.name;
  document.getElementById("white-rating").textContent = g.white.rating ? "(" + g.white.rating + ")" : "";
  document.getElementById("black-name").textContent   = g.black.name;
  document.getElementById("black-rating").textContent = g.black.rating ? "(" + g.black.rating + ")" : "";
  document.getElementById("speed-chip").textContent   = g.speed || "—";
  const ratedEl = document.getElementById("rated-chip");
  ratedEl.textContent = g.rated ? "Rated" : "Casual";
  ratedEl.classList.toggle("rated", !!g.rated);
  const init = g.clock_initial, inc = g.clock_increment;
  document.getElementById("tc-chip").textContent = init ? Math.floor(init / 60000) + "+" + Math.round(inc / 1000) : "—";
  const link = document.getElementById("game-url");
  link.href = g.url;
  link.textContent = "lichess.org/" + g.id + " \u2192";

  // Board
  if (!board || board.orientation() !== s.bot_color) initBoard(s.bot_color);
  setPosition(pos.fen, pos.last_move);
  const botPlayer = s.bot_color === "white" ? g.white : g.black;
  const oppPlayer = s.bot_color === "white" ? g.black : g.white;
  document.getElementById("bot-name-text").textContent =
    botPlayer.name + (botPlayer.rating ? " (" + botPlayer.rating + ")" : "");
  document.getElementById("opponent-name-text").textContent =
    oppPlayer.name + (oppPlayer.rating ? " (" + oppPlayer.rating + ")" : "");

  // Material captured
  try {
    const caps = computeCaptures(pos.fen);
    // bot-captures: pieces bot captured = opponent color pieces gone
    const botIsWhite = s.bot_color === "white";
    const botCaps = botIsWhite ? caps.b : caps.w;
    const oppCaps = botIsWhite ? caps.w : caps.b;
    // advantage: positive = white ahead; convert to bot's perspective
    const botAdv = botIsWhite ? caps.advantage : -caps.advantage;
    document.getElementById("bot-captures").textContent =
      botCaps + (botAdv > 0 ? " +" + botAdv : "");
    document.getElementById("opp-captures").textContent =
      oppCaps + (botAdv < 0 ? " +" + (-botAdv) : "");
  } catch(e) {}

  // Clocks — only restart ticker if values changed (avoids reset on engine-stats-only SSE pushes)
  if (clk.wtime_ms !== lastClockWtime || clk.btime_ms !== lastClockBtime || clk.turn !== lastClockTurn) {
    wtime_ms = clk.wtime_ms;
    btime_ms = clk.btime_ms;
    currentTurn = clk.turn;
    lastClockWtime = clk.wtime_ms;
    lastClockBtime = clk.btime_ms;
    lastClockTurn = clk.turn;
    document.getElementById("white-clock").textContent = fmtMs(wtime_ms);
    document.getElementById("black-clock").textContent = fmtMs(btime_ms);
    startClock();
  }

  // Bot eval
  const botCp = eng ? eng.cp : null, botMate = eng ? eng.mate : null;
  const botEl = document.getElementById("bot-eval");
  botEl.textContent = fmtCp(botCp, botMate);
  botEl.className   = "eval-value " + cpClass(botCp, botMate);

  // SF eval
  const sfEl = document.getElementById("sf-eval");
  sfEl.textContent = sf ? fmtCp(sf.cp, sf.mate) : "—";
  sfEl.className   = "eval-value " + (sf ? cpClass(sf.cp, sf.mate) : "");

  // Eval bar — botCp is from bot's perspective (positive = bot winning)
  // bar fills from bottom = bot's side; use directly without negation
  document.getElementById("eval-bar").style.height = evalToPercent(botCp, botMate) + "%";

  // Engine stats
  document.getElementById("st-depth").textContent  = eng && eng.depth  != null ? eng.depth  : "—";
  document.getElementById("st-nodes").textContent  = eng ? fmtNodes(eng.nodes)  : "—";
  const derivedNps = (eng && eng.nps != null) ? eng.nps
    : (eng && eng.nodes && eng.time_ms ? Math.round(eng.nodes / eng.time_ms) : null);
  document.getElementById("st-nps").textContent    = fmtNps(derivedNps);
  document.getElementById("st-time").textContent   = eng && eng.time_ms != null ? eng.time_ms.toFixed(2) + "s" : "—";
  document.getElementById("st-tbhits").textContent = eng ? fmtNodes(eng.tbhits) : "—";
  document.getElementById("st-source").textContent = eng && eng.source  ? eng.source  : "—";
}

// ── SSE connection ───────────────────────────────────────────────────────────
function connect() {
  const es = new EventSource("/events");
  es.onmessage = function(e) {
    try {
      const s = JSON.parse(e.data);
      if (s.type === "idle") renderIdle(s);
      else if (s.type === "update") renderUpdate(s);
    } catch(err) {}
  };
  es.onerror = function() {
    es.close();
    document.getElementById("status-dot").classList.remove("live");
    setTimeout(connect, 5000);
  };
}

renderIdle(null);
connect();
</script>
</body>
</html>"""


# ── HTTP Handler ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    shared: SharedState  # set as class attr before server starts

    def log_message(self, fmt, *args):
        pass  # suppress default access log noise

    def do_GET(self):
        if self.path == "/":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            q = self.shared.subscribe()
            try:
                while True:
                    try:
                        chunk = q.get(timeout=25)
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # SSE comment as keepalive — prevents proxy/browser timeout
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                self.shared.unsubscribe(q)

        elif self.path.startswith("/img/") and self.path.endswith(".png"):
            img_path = Path("/root/scripts") / self.path.lstrip("/")
            if img_path.exists():
                body = img_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        else:
            self.send_error(404)


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    token = load_token()
    if not token:
        raise RuntimeError("LICHESS_BOT_TOKEN not found in env or /root/lichess-bot-master/.env")

    shared = SharedState()
    Handler.shared = shared

    monitor = threading.Thread(
        target=game_monitor_loop,
        args=(shared, token),
        daemon=True,
        name="GameMonitor",
    )
    monitor.start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Dashboard running at http://0.0.0.0:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
