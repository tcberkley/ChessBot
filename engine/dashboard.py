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
import datetime
import json
import os
import queue
import random
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
GAMES_CACHE_TTL    = 60   # seconds to cache recent games
ACTIVITY_N         = 50   # max rows in merged activity feed
CHALLENGE_LOG_N    = 50   # read last N challenge rows

SELF_PLAY_LOG_PATH      = "/root/scripts/self_play_log.jsonl"
SELF_PLAY_LOG_SHOW      = 100
SELF_PLAY_ENGINE_DIR    = "/root/c_rewrite"
SELF_PLAY_ENGINES       = {
    "v1.11": "v24_engine",
    "v2.1":  "v26_engine",
    "v2.2":  "v27_engine",
    "v2.3":  "v28_engine",
}
SELF_PLAY_N_GAMES       = 8
SELF_PLAY_MOVETIME      = 1.0
SELF_PLAY_MOVE_PAUSE    = 2.0
SELF_PLAY_COMPUTE_SLOTS = 2
SELF_PLAY_BROADCAST_SEC = 0.5

OPENING_MOVES = [
    "e2e4", "d2d4", "c2c4", "g1f3", "b1c3",
    "f2f4", "g2g3", "b2b4", "e2e3", "d2d3",
]


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


def read_daily_counts(path: str) -> dict:
    """Return {"challenges": int|None, "games": int|None} from daily_window.txt.
    Format (newline-separated): timestamp\\nchallenge_count\\ngame_count
    """
    try:
        with open(path) as f:
            lines = [l.strip() for l in f.read().splitlines() if l.strip()]
        return {
            "challenges": int(lines[1]) if len(lines) >= 2 else None,
            "games":      int(lines[2]) if len(lines) >= 3 else None,
        }
    except Exception:
        return {"challenges": None, "games": None}


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


_games_cache: dict = {"ts": 0, "data": None}


def fetch_recent_games(token: str, n: int = ACTIVITY_N) -> list:
    """GET /api/games/user/{bot} — returns list of game dicts, cached GAMES_CACHE_TTL seconds."""
    now = time.time()
    if now - _games_cache["ts"] < GAMES_CACHE_TTL and _games_cache["data"] is not None:
        return _games_cache["data"]
    try:
        resp = requests.get(
            f"{LICHESS_API}/api/games/user/{BOT_USERNAME}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/x-ndjson",
            },
            params={"max": n, "moves": "false", "clocks": "false", "pgnInJson": "false"},
            timeout=10,
        )
        games = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                g = json.loads(line)
                players = g.get("players", {})
                bot_color = (
                    "white"
                    if players.get("white", {}).get("user", {}).get("name", "").lower()
                       == BOT_USERNAME.lower()
                    else "black"
                )
                opp_color = "black" if bot_color == "white" else "white"
                opp       = players.get(opp_color, {})
                bot_p     = players.get(bot_color, {})
                opp_name  = opp.get("user", {}).get("name", "?")
                opp_rating = opp.get("rating")
                rating_diff = bot_p.get("ratingDiff")

                winner = g.get("winner")
                if winner is None:
                    result = "draw"
                elif winner == bot_color:
                    result = "win"
                else:
                    result = "loss"

                clock = g.get("clock", {})
                initial   = clock.get("initial", 0)
                increment = clock.get("increment", 0)
                def _fmt_tc_mins(secs):
                    if secs == 0: return "0"
                    if secs < 60:
                        return {15: "¼", 30: "½", 45: "¾"}.get(secs, f"{secs}s")
                    return str(secs // 60)
                tc = f"{_fmt_tc_mins(initial)}+{increment}" if clock else "—"

                created_ms = g.get("createdAt", 0)
                ts_utc = datetime.datetime.utcfromtimestamp(created_ms / 1000).strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
                games.append({
                    "row_type":        "game",
                    "timestamp_utc":   ts_utc,
                    "event":           result,
                    "opponent":        opp_name,
                    "opponent_rating": opp_rating,
                    "time_control":    tc,
                    "rating_diff":     rating_diff,
                    "bot_rating":      bot_p.get("rating"),
                    "game_id":         g.get("id"),
                })
            except Exception:
                pass
        _games_cache["ts"]   = now
        _games_cache["data"] = games
        return games
    except Exception:
        return _games_cache["data"] or []


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
        updated["last_result"] = {
            "winner": event.get("winner"),
            "status": status,
        }
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
            self._engine = chess.engine.SimpleEngine.popen_uci("/usr/games/stockfish")
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


# ── Self-play arena ───────────────────────────────────────────────────────────
class SelfPlayGame:
    def __init__(self, idx: int):
        self.idx          = idx
        self.board        = chess.Board()
        self.last_move    = None
        self.result       = None
        self.status       = "starting"
        self.move_count   = 0
        self.white_label  = ""
        self.black_label  = ""
        self.white_engine = None
        self.black_engine = None
        self.white_wins   = 0
        self.black_wins   = 0
        self.draws        = 0

    def _open_engines(self, white_label: str, black_label: str) -> bool:
        try:
            wp = os.path.join(SELF_PLAY_ENGINE_DIR, SELF_PLAY_ENGINES[white_label])
            bp = os.path.join(SELF_PLAY_ENGINE_DIR, SELF_PLAY_ENGINES[black_label])
            self.white_engine = chess.engine.SimpleEngine.popen_uci(wp)
            self.black_engine = chess.engine.SimpleEngine.popen_uci(bp)
            self.white_engine.configure({"Threads": 1})
            self.black_engine.configure({"Threads": 1})
            return True
        except Exception:
            return False

    def start_engines(self) -> bool:
        labels = random.sample(list(SELF_PLAY_ENGINES.keys()), 2)
        self.white_label, self.black_label = labels
        return self._open_engines(self.white_label, self.black_label)

    def new_game(self):
        self.board      = chess.Board()
        self.last_move  = None
        self.result     = None
        self.status     = "playing"
        self.move_count = 0
        labels = random.sample(list(SELF_PLAY_ENGINES.keys()), 2)
        self.white_label, self.black_label = labels
        for eng in (self.white_engine, self.black_engine):
            if eng:
                try: eng.quit()
                except: pass
        self.white_engine = self.black_engine = None
        if not self._open_engines(self.white_label, self.black_label):
            self.status = "error"
            return
        opening = random.choice(OPENING_MOVES)
        try:
            move = chess.Move.from_uci(opening)
            if move in self.board.legal_moves:
                self.board.push(move)
                self.last_move = opening
        except Exception:
            pass

    def make_move(self) -> bool:
        if self.board.is_game_over():
            self._record_result(); return False
        engine = self.white_engine if self.board.turn == chess.WHITE else self.black_engine
        if engine is None:
            self.status = "error"; return False
        try:
            r = engine.play(self.board, chess.engine.Limit(time=SELF_PLAY_MOVETIME))
            self.board.push(r.move)
            self.last_move  = r.move.uci()
            self.move_count += 1
            if self.board.is_game_over():
                self._record_result(); return False
        except Exception:
            self.status = "error"; return False
        return True

    def _record_result(self):
        self.status = "finished"
        out = self.board.outcome()
        if out is None:
            self.result = "½-½"; self.draws += 1
        elif out.winner == chess.WHITE:
            self.result = "1-0"; self.white_wins += 1
        elif out.winner == chess.BLACK:
            self.result = "0-1"; self.black_wins += 1
        else:
            self.result = "½-½"; self.draws += 1
        entry = {
            "ts":     datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "white":  self.white_label,
            "black":  self.black_label,
            "result": self.result,
            "moves":  self.move_count,
        }
        try:
            with open(SELF_PLAY_LOG_PATH, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def to_state(self) -> dict:
        return {
            "idx":         self.idx,
            "fen":         self.board.fen(),
            "last_move":   self.last_move,
            "result":      self.result,
            "status":      self.status,
            "move_count":  self.move_count,
            "white_label": self.white_label,
            "black_label": self.black_label,
            "white_wins":  self.white_wins,
            "black_wins":  self.black_wins,
            "draws":       self.draws,
            "turn":        "w" if self.board.turn == chess.WHITE else "b",
        }

    def stop(self):
        for eng in (self.white_engine, self.black_engine):
            if eng:
                try: eng.quit()
                except: pass
        self.white_engine = self.black_engine = None


class SelfPlayManager:
    def __init__(self, shared: "SharedState"):
        self.shared     = shared
        self.games      = [SelfPlayGame(i) for i in range(SELF_PLAY_N_GAMES)]
        self.stop_event = threading.Event()
        self._move_q: queue.Queue = queue.Queue()
        self._extra: dict = {}

    def start(self):
        self.stop_event.clear()
        for _ in range(SELF_PLAY_COMPUTE_SLOTS):
            threading.Thread(target=self._worker, daemon=True).start()
        # Stagger game launches to avoid CPU spike from simultaneous engine init
        for i, game in enumerate(self.games):
            def _launch(g=game, delay=i * 0.8):
                time.sleep(delay)
                if not self.stop_event.is_set():
                    if g.start_engines():
                        g.new_game()
            threading.Thread(target=_launch, daemon=True).start()
            threading.Thread(target=self._game_loop, args=(game,), daemon=True).start()
        threading.Thread(target=self._broadcast_loop, daemon=True).start()

    def stop(self):
        self.stop_event.set()
        while not self._move_q.empty():
            try:
                _, done = self._move_q.get_nowait()
                done.set()
            except Exception:
                pass
        for game in self.games:
            game.stop()

    def _worker(self):
        while not self.stop_event.is_set():
            try:
                game, done = self._move_q.get(timeout=1)
                if not self.stop_event.is_set():
                    game.make_move()
                done.set()
            except queue.Empty:
                pass

    def _game_loop(self, game: SelfPlayGame):
        while not self.stop_event.is_set():
            if game.status == "playing":
                done = threading.Event()
                self._move_q.put((game, done))
                done.wait(timeout=60)
                if not self.stop_event.is_set():
                    time.sleep(SELF_PLAY_MOVE_PAUSE)
            elif game.status in ("finished", "error"):
                time.sleep(2.5)
                if not self.stop_event.is_set():
                    game.new_game()
            else:
                time.sleep(0.2)

    @staticmethod
    def _load_log() -> list:
        try:
            with open(SELF_PLAY_LOG_PATH) as f:
                lines = f.readlines()
            entries = []
            for line in lines[-SELF_PLAY_LOG_SHOW:]:
                try: entries.append(json.loads(line))
                except: pass
            entries.reverse()
            return entries
        except Exception:
            return []

    @staticmethod
    def _log_totals():
        total_games, total_moves = 0, 0
        try:
            with open(SELF_PLAY_LOG_PATH) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        total_games += 1
                        total_moves += e.get("moves", 0)
                    except:
                        pass
        except Exception:
            pass
        return total_games, total_moves

    def set_extra(self, extra: dict):
        self._extra = extra

    def _broadcast_loop(self):
        while not self.stop_event.is_set():
            total_games, total_moves = self._log_totals()
            self.shared.update({
                "type":        "self_play",
                "games":       [g.to_state() for g in self.games],
                "history":     self._load_log(),
                "total_games": total_games,
                "total_moves": total_moves,
                **self._extra,
            })
            time.sleep(SELF_PLAY_BROADCAST_SEC)


# ── Game monitor thread ───────────────────────────────────────────────────────
def game_monitor_loop(shared: SharedState, token: str):
    current_game_id   = None
    stream_thread     = None
    stream_stop_event = None
    file_pos          = 0
    sf_engine         = SFEngine()
    last_engine_stats = None
    last_sf_fen       = None
    self_play         = SelfPlayManager(shared)
    self_play_running = False

    while True:
        try:
            resp = requests.get(
                f"{LICHESS_API}/api/account/playing",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            data = resp.json()
            nowPlaying = data.get("nowPlaying", [])
            game_id = nowPlaying[0]["gameId"] if nowPlaying else None

            # Collect activity/profile every cycle (cached 60s)
            challenges  = [dict(r, row_type="challenge") for r in read_challenge_log(CHALLENGE_LOG_PATH)]
            games_data  = fetch_recent_games(token)
            activity    = sorted(challenges + games_data, key=lambda r: r.get("timestamp_utc", ""), reverse=True)[:ACTIVITY_N]
            daily_counts = read_daily_counts(DAILY_WINDOW_PATH)
            profile      = fetch_bot_profile(token)
            extra        = {"activity": activity, "challenges": challenges, "daily_counts": daily_counts, "profile": profile}

            if game_id != current_game_id:
                # Stop self-play only when a real game is STARTING (not when it ends)
                if self_play_running and game_id is not None:
                    self_play.stop()
                    self_play         = SelfPlayManager(shared)
                    self_play_running = False

                # Stop old stream thread
                if stream_stop_event is not None:
                    stream_stop_event.set()

                current_game_id = game_id
                file_pos = 0
                sf_engine.clear_cache()
                last_engine_stats = None
                last_sf_fen = None

                if game_id is None:
                    shared.update({"type": "idle", **extra})
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

            # Start self-play when idle
            if game_id is None and not self_play_running:
                self_play.start()
                self_play_running = True

            # Push extra (activity/profile) every cycle — used by self_play broadcasts too
            if game_id is None:
                if self_play_running:
                    self_play.set_extra(extra)
                else:
                    shared.update({"type": "idle", **extra})

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
                        current.update(extra)
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
#eval-bar.flipped { bottom: auto; top: 0; }
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
.stats-table { width: 100%; border-collapse: collapse; overflow: visible; table-layout: fixed; }
.stats-table th {
  text-align: left; font-size: 0.7rem; color: #6878a8;
  text-transform: uppercase; padding: 4px 6px;
  border-bottom: 1px solid #2d2d44; overflow: visible; position: relative;
}
.stats-table td {
  font-size: 0.85rem; padding: 6px 6px;
  font-variant-numeric: tabular-nums;
  color: #c8d0f0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.stats-table th:nth-child(1), .stats-table td:nth-child(1) { width: 14%; }
.stats-table th:nth-child(2), .stats-table td:nth-child(2) { width: 17%; }
.stats-table th:nth-child(3), .stats-table td:nth-child(3) { width: 17%; }
.stats-table th:nth-child(4), .stats-table td:nth-child(4) { width: 14%; }
.stats-table th:nth-child(5), .stats-table td:nth-child(5) { width: 14%; }
.stats-table th:nth-child(6), .stats-table td:nth-child(6) { width: 24%; }
#idle-screen { display: none; }
#idle-stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px;
  margin-bottom: 10px;
  align-items: stretch;
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
.view-tabs { display:flex; gap:6px; }
.view-tab {
  padding: 6px 20px;
  border-radius: 6px;
  border: 1px solid #2d2d54;
  background: #0f1630;
  color: #6878a8;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  font-family: inherit;
  transition: all 0.15s;
}
.view-tab:hover { color: #c8d0f0; border-color: #4a4a74; }
.view-tab.active { background: #16213e; color: #e8e8f0; border-color: #3498db; }
.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 0;
}
@media (max-width: 720px) { .stats-grid { grid-template-columns: 1fr; } }
#card-rating-trend { grid-column: 1 / -1; }
.sparkline-tc-btn {
  padding: 3px 10px;
  border-radius: 4px;
  border: 1px solid #2d2d54;
  background: #0f1630;
  color: #6878a8;
  cursor: pointer;
  font-size: 0.75rem;
  font-family: inherit;
}
.sparkline-tc-btn.active { color: #e8e8f0; border-color: #3498db; background: #16213e; }
.record-bar {
  height: 22px; border-radius: 4px; overflow: hidden;
  display: flex; margin: 10px 0 6px;
}
.record-bar-w { background: #2ecc71; }
.record-bar-d { background: #555; }
.record-bar-l { background: #e74c3c; }
.record-legend { display:flex; gap:16px; font-size:0.8rem; }
.record-legend span { display:flex; align-items:center; gap:5px; }
.legend-dot { width:10px; height:10px; border-radius:50%; flex-shrink:0; }
.by-tc-table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.by-tc-table th { text-align:left; font-size:0.68rem; color:#6878a8; text-transform:uppercase;
  padding:4px 6px; border-bottom:1px solid #2d2d44; }
.by-tc-table td { padding:5px 6px; color:#c8d0f0; font-variant-numeric:tabular-nums;
  border-bottom:1px solid #1a1a30; }
.top-opp-table { width:100%; border-collapse:collapse; font-size:0.82rem; }
.top-opp-table th { text-align:left; font-size:0.68rem; color:#6878a8; text-transform:uppercase;
  padding:4px 6px; border-bottom:1px solid #2d2d44; }
.top-opp-table td { padding:5px 6px; color:#c8d0f0; font-variant-numeric:tabular-nums;
  border-bottom:1px solid #1a1a30; }
.ch-out-sent     { color: #3498db; }
.ch-out-declined { color: #e67e22; }
.ch-in-accepted  { color: #2ecc71; }
.ch-in-declined  { color: #888;    }
.ch-dir-out  { font-weight:600; color:#3498db; }
.ch-dir-in   { font-weight:600; color:#2ecc71; }
.ch-dir-game { font-weight:600; color:#9b59b6; }
.ch-game-win  { color: #2ecc71; font-weight:600; }
.ch-game-loss { color: #e74c3c; font-weight:600; }
.ch-game-draw { color: #888;    font-weight:600; }
.ch-rating-pos { color: #2ecc71; font-size:0.78rem; }
.ch-rating-neg { color: #e74c3c; font-size:0.78rem; }
.activity-link { color: #c8d0f0; text-decoration: none; }
.activity-link:hover { text-decoration: underline; }
.dir-badge { font-size:0.65rem; font-weight:700; padding:2px 6px; border-radius:3px; letter-spacing:0.05em; }
.dir-out   { background:#1a3a5c; color:#3498db; }
.dir-in    { background:#1a3a1a; color:#2ecc71; }
.bot-badge { font-size:0.6rem; font-weight:700; color:#9b59b6; background:#1e1030;
             padding:1px 4px; border-radius:2px; margin-left:4px; vertical-align:middle; }
@media (max-width: 720px) {
  .main-grid { grid-template-columns: 1fr; }
  #board { width: 100%; max-width: 340px; margin: 0 auto; }
  .board-col { padding-left: 0; }
  .eval-bar-wrap { display: none; }
}
.info-btn {
  width: 28px; height: 28px; border-radius: 50%;
  border: 1px solid #2d2d54; background: #0f1630;
  color: #6878a8; cursor: pointer; font-size: 0.85rem;
  font-weight: 700; font-family: inherit; flex-shrink: 0;
  transition: all 0.15s; margin-left: 8px;
}
.info-btn:hover { color: #c8d0f0; border-color: #4a4a74; }
.stat-th-tip {
  display: inline-block; width: 14px; height: 14px; border-radius: 50%;
  background: #2d2d54; color: #6878a8; font-size: 0.65rem; font-weight: 700;
  line-height: 14px; text-align: center; cursor: default;
  position: relative; margin-left: 4px; vertical-align: middle;
}
#stat-tooltip {
  display: none; position: fixed;
  background: #1a2040; color: #c8d0f0; font-size: 0.7rem; font-weight: 400;
  padding: 5px 9px; border-radius: 4px; border: 1px solid #2d2d54;
  white-space: nowrap; z-index: 9999; pointer-events: none;
  box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  transform: translateX(-50%);
}
.info-modal-backdrop {
  display: none; position: fixed; inset: 0;
  background: rgba(0,0,0,0.6); z-index: 100;
  align-items: center; justify-content: center;
}
.info-modal-backdrop.open { display: flex; }
.info-modal {
  background: #16213e; border: 1px solid #2d2d54;
  border-radius: 10px; padding: 24px 28px; min-width: 280px;
  max-width: 380px; width: 90%; position: relative;
}
.info-modal h2 {
  font-size: 1rem; font-weight: 700; color: #e8e8f0;
  margin-bottom: 18px;
}
.info-modal-close {
  position: absolute; top: 12px; right: 14px;
  background: none; border: none; color: #6878a8;
  font-size: 1.2rem; cursor: pointer; line-height: 1;
}
.info-modal-close:hover { color: #e8e8f0; }
.info-link-row {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 0; border-bottom: 1px solid #2d2d44;
  text-decoration: none; color: #c8d0f0;
  font-size: 0.9rem; transition: color 0.15s;
}
.info-link-row:last-child { border-bottom: none; }
.info-link-row:hover { color: #3498db; }
.info-link-icon { font-size: 1.1rem; width: 22px; text-align: center; flex-shrink: 0; }
.table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.table-scroll table { white-space: nowrap; }
#result-overlay {
  display: none; position: fixed; inset: 0; z-index: 50;
  align-items: center; justify-content: center;
  background: rgba(5,8,22,0.82); backdrop-filter: blur(4px);
  cursor: pointer;
}
#result-card {
  background: #16213e; border: 1px solid #2d2d54; border-radius: 14px;
  padding: 36px 44px; text-align: center; min-width: 280px; max-width: 360px;
  cursor: default; position: relative;
}
#result-icon { font-size: 3.2rem; line-height: 1; margin-bottom: 14px; }
#result-heading { font-size: 2rem; font-weight: 700; margin-bottom: 6px; }
#result-opponent { font-size: 0.95rem; color: #8898c8; margin-bottom: 3px; }
#result-method { font-size: 0.85rem; color: #4a5070; margin-bottom: 24px; text-transform: capitalize; }
#result-game-link {
  display: inline-block; padding: 7px 18px; border: 1px solid #2d2d54;
  border-radius: 6px; color: #6878a8; font-size: 0.85rem; text-decoration: none;
  transition: all 0.15s; margin-bottom: 22px;
}
#result-game-link:hover { color: #c8d0f0; border-color: #4a4a74; }
#result-dismiss-bar { height: 3px; background: #1a2030; border-radius: 2px; overflow: hidden; }
#result-dismiss-fill { height: 100%; background: #3498db; width: 100%; }
@media (max-width: 600px) {
  .container { padding: 10px; }
  header { flex-wrap: wrap; padding-bottom: 14px; }
  header h1 { font-size: 1.05rem; flex: 1; }
  #header-tabs { order: 3; flex: 0 0 100%; justify-content: center; margin-left: 0 !important; }
  .info-btn { margin-left: 0; }
  .card { padding: 10px 12px; }
  .view-tab { padding: 5px 14px; font-size: 0.8rem; }
  .idle-stat-value { font-size: 1.3rem; }
  .player-name { overflow-wrap: break-word; word-break: break-all; }
}
@keyframes ponder-pulse { 0%,100%{opacity:1} 50%{opacity:0.45} }
.pondering { animation: ponder-pulse 1.8s ease-in-out infinite; color: #8898c8 !important; }
#board-mate-sweep {
  position: absolute; inset: 0; pointer-events: none; overflow: hidden; z-index: 10;
}
#board-mate-sweep::after {
  content: ''; position: absolute; top: 0; bottom: 0; left: -60%; width: 60%;
  background: linear-gradient(90deg, transparent, rgba(46,204,113,0.55), transparent);
}
#board-mate-sweep.sweeping::after {
  animation: board-mate-sweep 0.9s ease-in-out forwards;
}
@keyframes board-mate-sweep { 0% { left: -60%; } 100% { left: 100%; } }
/* ── Self-play arena ──────────────────────────────────────────────────────── */
#self-play-screen { display: none; }
#sp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
#sp-header-title {
  font-size: 0.85rem;
  color: #6878a8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
#sp-idle-notice {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 0.72rem;
  color: #6878a8;
  margin-bottom: 12px;
  background: #16213e;
  border: 1px solid #2d2d54;
  border-radius: 20px;
  padding: 4px 12px 4px 10px;
}
.sp-idle-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #4a5a8a; flex-shrink: 0;
}
#sp-idle-notice a {
  color: #7c9ee8;
  text-decoration: none;
  font-weight: 600;
}
#sp-idle-notice a:hover { text-decoration: underline; }
.sp-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  align-items: start;
}
@media (max-width: 700px) { .sp-grid { grid-template-columns: repeat(2, 1fr); } }
.sp-card {
  background: #16213e;
  border: 1px solid #2d2d54;
  border-radius: 8px;
  padding: 5px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sp-side-label {
  font-size: 0.58rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sp-top-label    { color: #7888b8; }
.sp-bottom-label { color: #9aa8cc; }
.sp-result-badge {
  font-size: 0.6rem; font-weight: 700; padding: 1px 4px; border-radius: 3px;
}
.sp-result-badge.white-wins { background: #e8e8e8; color: #1a1a2e; }
.sp-result-badge.black-wins { background: #2a2a3a; color: #c0c0d8; border: 1px solid #444; }
.sp-result-badge.draw       { background: #4a4a6a; color: #c0c0d8; }
.mini-board-wrap {
  position: relative;
  width: 100%;
  padding-bottom: 100%;
  flex-shrink: 0;
  overflow: hidden;
}
.mini-board-wrap::after {
  content: '';
  position: absolute;
  inset: 0;
  background: #0d1020;
  transform: translateX(-101%);
  pointer-events: none;
  z-index: 2;
}
.mini-board-wrap.wiping::after {
  animation: sp-curtain 0.7s ease-in-out forwards;
}
@keyframes sp-curtain {
  0%   { transform: translateX(-101%); }
  38%  { transform: translateX(0%); }
  62%  { transform: translateX(0%); }
  100% { transform: translateX(101%); }
}
.mini-board {
  position: absolute;
  inset: 0;
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  grid-template-rows: repeat(8, 1fr);
  border: 1px solid #2d2d54;
  border-radius: 2px;
  overflow: hidden;
}
.mini-sq {
  display: flex; align-items: center; justify-content: center;
  user-select: none;
}
.mini-piece {
  width: 82%; height: 82%; object-fit: contain;
  display: block; pointer-events: none;
  filter: drop-shadow(0 0 1px rgba(0,0,0,0.55));
}
.mini-sq.light { background: #f0d9b5; }
.mini-sq.dark  { background: #b58863; }
.mini-sq.hi    { background: #cdd26a; }
.mini-sq.dark.hi { background: #aaa23a; }
.sp-score-row {
  display: flex; justify-content: space-between;
  font-size: 0.65rem; color: #6878a8;
}
.sp-score-row .sp-score-val { color: #a0a8c8; font-weight: 600; }
#sp-history {
  margin-top: 20px; border: 1px solid #2d2d54;
  border-radius: 8px; overflow: hidden;
}
#sp-history-title {
  padding: 8px 14px; background: #16213e;
  font-size: 0.75rem; color: #6878a8;
  text-transform: uppercase; letter-spacing: 0.06em;
  border-bottom: 1px solid #2d2d54;
}
#sp-history table { width: 100%; border-collapse: collapse; font-size: 0.75rem; }
#sp-history th {
  padding: 6px 12px; text-align: left; color: #6878a8;
  font-weight: 500; background: #131226; border-bottom: 1px solid #2d2d54;
}
#sp-history td { padding: 5px 12px; color: #c0c0d8; border-bottom: 1px solid #1e1e38; }
#sp-history tr:last-child td { border-bottom: none; }
#sp-history tr:hover td { background: #1a1a36; }
.sp-res-w { color: #e0e0e0; font-weight: 600; }
.sp-res-b { color: #a0a0b8; font-weight: 600; }
.sp-res-d { color: #6878a8; font-weight: 600; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="status-dot" id="status-dot"></div>
    <h1>tombot1234 — Live Dashboard</h1>
    <div class="view-tabs" id="header-tabs" style="margin-left:auto">
      <button class="view-tab active" id="tab-game"     onclick="switchTab('game')">Game</button>
      <button class="view-tab"        id="tab-activity" onclick="switchTab('activity')">Activity</button>
      <button class="view-tab"        id="tab-stats"    onclick="switchTab('stats')">Stats</button>
    </div>
    <button class="info-btn" onclick="document.getElementById('info-modal-backdrop').classList.add('open')" title="Links">&#9432;</button>
  </header>

  <div class="info-modal-backdrop" id="info-modal-backdrop" onclick="if(event.target===this)this.classList.remove('open')">
    <div class="info-modal">
      <button class="info-modal-close" onclick="document.getElementById('info-modal-backdrop').classList.remove('open')">&times;</button>
      <h2>tombot1234</h2>
      <a class="info-link-row" href="https://lichess.org/@/tombot1234/tv" target="_blank">
        <span class="info-link-icon">&#128249;</span> Watch live on Lichess
      </a>
      <a class="info-link-row" href="https://lichess.org/?user=tombot1234#friend" target="_blank">
        <span class="info-link-icon">&#9822;</span> Send a challenge
      </a>
      <a class="info-link-row" href="https://github.com/tcberkley/ChessBot" target="_blank">
        <span class="info-link-icon">&#128025;</span> GitHub source
      </a>
    </div>
  </div>

  <div id="game-view" style="display:none">
    <div id="no-game-msg" style="display:none;min-height:320px;align-items:center;justify-content:center;flex-direction:column;gap:0">
      <div style="font-size:5rem;line-height:1;opacity:0.15;user-select:none">&#9822;</div>
      <div style="font-size:1.25rem;font-weight:600;color:#c8d0f0;margin-top:20px;letter-spacing:0.01em">Waiting for a game</div>
      <div style="font-size:0.88rem;color:#4a5070;margin-top:6px">tombot1234 is online and ready</div>
      <a href="https://lichess.org/?user=tombot1234#friend" target="_blank" rel="noopener"
         style="display:inline-flex;align-items:center;gap:8px;margin-top:28px;padding:11px 28px;background:#1a2744;border:1px solid #3498db;border-radius:8px;color:#3498db;font-size:0.95rem;font-weight:600;text-decoration:none;transition:all 0.18s;letter-spacing:0.01em"
         onmouseover="this.style.background='#1e3060';this.style.color='#5ab4f0';this.style.borderColor='#5ab4f0'"
         onmouseout="this.style.background='#1a2744';this.style.color='#3498db';this.style.borderColor='#3498db'">
        &#9878;&nbsp; Challenge on Lichess
      </a>
    </div>
    <div id="game-content">
    <div class="main-grid">
      <div class="board-col">
        <div class="eval-bar-wrap">
          <div class="eval-bar-white" id="eval-bar" style="height:50%"></div>
        </div>
        <div id="opponent-label" class="board-player-label">
          <span id="opponent-name-text">—</span>
          <span id="opp-captures" class="captures"></span>
        </div>
        <div id="board-wrap" style="position:relative;display:inline-block">
          <div id="board"></div>
          <div id="board-mate-sweep"></div>
        </div>
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
              <div class="eval-label">Bot (v2.2)</div>
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
          <div class="table-scroll">
          <table class="stats-table">
            <thead>
              <tr>
                <th>Depth <span class="stat-th-tip" data-tip="Search depth in iterative deepening">i</span></th>
                <th>Nodes <span class="stat-th-tip" data-tip="Total positions evaluated this move">i</span></th>
                <th>NPS <span class="stat-th-tip" data-tip="Nodes per second (nodes ÷ search time)">i</span></th>
                <th>Time <span class="stat-th-tip" data-tip="Total search time for this move (seconds)">i</span></th>
                <th>TB Hits <span class="stat-th-tip" data-tip="Syzygy tablebase probes that resolved a position (endgame only)">i</span></th>
                <th>Source <span class="stat-th-tip" data-tip="engine = normal search · tb = tablebase win · book = opening">i</span></th>
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
    </div>
  </div>

  <div id="idle-screen">
    <!-- Stat cards row (always visible) -->
    <div id="idle-stats-row"></div>

    <!-- Activity panel -->
    <div id="panel-activity">
      <div class="card">
        <div class="card-title">Activity</div>
        <div id="activity-filter-bar" style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap">
          <button class="view-tab active" id="af-games"    onclick="setActivityFilter('games')">Games</button>
          <button class="view-tab"        id="af-outgoing" onclick="setActivityFilter('outgoing')">Outgoing</button>
          <button class="view-tab"        id="af-incoming" onclick="setActivityFilter('incoming')">Incoming</button>
        </div>
        <div class="table-scroll">
        <table class="challenge-table" id="challenge-table">
          <thead>
            <tr>
              <th>Time</th><th>Dir</th><th>Event</th>
              <th>Opponent</th><th>Rating</th><th>TC</th><th>Info</th>
            </tr>
          </thead>
          <tbody id="challenge-tbody"></tbody>
        </table>
        </div>
        <div id="challenge-empty" style="display:none;color:#445;font-size:0.85rem;padding:16px 0;text-align:center">
          No activity yet
        </div>
      </div>
    </div>

    <!-- Stats panel -->
    <div id="panel-stats" style="display:none">
      <div class="stats-grid">
        <div class="card" id="card-rating-trend">
          <div class="card-title">Rating Trend</div>
          <div id="sparkline-wrap"></div>
          <div id="sparkline-tc-buttons" style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap"></div>
        </div>
        <div class="card" id="card-record">
          <div class="card-title">Overall Record</div>
          <div id="record-bar-wrap"></div>
        </div>
        <div class="card" id="card-by-tc">
          <div class="card-title">By Time Control</div>
          <div id="by-tc-wrap"></div>
        </div>
        <div class="card" id="card-top-opp">
          <div class="card-title">Top Opponents</div>
          <div id="top-opp-wrap"></div>
        </div>
      </div>
    </div>
  </div>

  <div id="self-play-screen">
    <div id="sp-header">
      <span id="sp-header-title">Self-Play Arena</span>
      <span id="sp-move-ticker" style="font-size:0.7rem;color:#6878a8;"></span>
    </div>
    <div id="sp-idle-notice">
      <span class="sp-idle-dot"></span>
      tombot1234 is not currently in a game &mdash;
      <a href="https://lichess.org/?user=tombot1234#friend" target="_blank" rel="noopener">send a challenge ↗</a>
    </div>
    <div id="sp-grid" class="sp-grid"></div>
  </div>
</div>

<div id="result-overlay" onclick="dismissResultOverlay()">
  <div id="result-card" onclick="event.stopPropagation()">
    <div id="result-icon"></div>
    <div id="result-heading"></div>
    <div id="result-opponent"></div>
    <div id="result-method"></div>
    <a id="result-game-link" href="#" target="_blank" rel="noopener">View on Lichess &rarr;</a>
    <div id="result-dismiss-bar"><div id="result-dismiss-fill"></div></div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
<script>
// Inject highlight style
const _hs = document.createElement("style");
_hs.textContent = ".sq-highlight { background: rgba(52,152,219,0.45) !important; } .sq-check { background: rgba(231,76,60,0.55) !important; }";
document.head.appendChild(_hs);

// ── State ───────────────────────────────────────────────────────────────────
let board = null;
let gameState = "idle";
let prevGameState = "idle";
let activeTab = "game";
let selfPlayActive = false;
let lastIdleState = null;
let sparklineTC = "all";
let activityFilter = "games";
let clockInterval = null;
let wtime_ms = 0, btime_ms = 0;
let currentTurn = "white";
let mateSweptThisGame = false;
let lastBoardFen = null;
let clockTickAt = null;
let lastClockWtime = -1, lastClockBtime = -1, lastClockTurn = null;
let resultDismissTimer = null;

// ── Helpers ─────────────────────────────────────────────────────────────────
function tcSortKey(tc) {
  if (!tc || tc === "—" || tc === "?") return [Infinity, Infinity];
  var parts = tc.split("+");
  function parseMins(s) {
    if (s === "¼") return 0.25; if (s === "½") return 0.5; if (s === "¾") return 0.75;
    if (s && s.endsWith("s")) return parseInt(s) / 60;
    return parseFloat(s) || 0;
  }
  return [parseMins(parts[0] || "0"), parseFloat(parts[1] || "0")];
}
function cmpTC(a, b) {
  var ka = tcSortKey(a), kb = tcSortKey(b);
  return ka[0] !== kb[0] ? ka[0] - kb[0] : ka[1] - kb[1];
}
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
  if (Math.abs(cp) >= 9000) return cp > 0 ? "TB+" : "TB-";
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
    moveSpeed: 120,
  });
  lastBoardFen = null;
}
function setPosition(fen, lastMove) {
  if (!board) return;
  if (fen !== lastBoardFen) {
    board.position(fen, true);
    lastBoardFen = fen;
  }
  $(".square-55d63").removeClass("sq-highlight");
  if (lastMove && lastMove.length >= 4) {
    const from = lastMove.slice(0, 2);
    const to   = lastMove.slice(2, 4);
    $("[data-square='" + from + "']").addClass("sq-highlight");
    $("[data-square='" + to   + "']").addClass("sq-highlight");
  }
  $(".square-55d63").removeClass("sq-check");
  try {
    const ch = new Chess(fen);
    if (ch.in_check()) {
      const turn = ch.turn();
      const bd = ch.board();
      for (let r = 0; r < 8; r++) for (let c = 0; c < 8; c++) {
        if (bd[r][c] && bd[r][c].type === 'k' && bd[r][c].color === turn) {
          const file = 'abcdefgh'[c];
          const rank = 8 - r;
          $("[data-square='" + file + rank + "']").addClass("sq-check");
        }
      }
    }
  } catch(e) {}
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

// ── Tab switching ────────────────────────────────────────────────────────────
function applyTabView() {
  const isGame     = activeTab === "game";
  const isActivity = activeTab === "activity";
  const isStats    = activeTab === "stats";

  const showSelfPlay = isGame && selfPlayActive;
  document.getElementById("self-play-screen").style.display = showSelfPlay ? "block" : "none";
  document.getElementById("game-view").style.display   = isGame && !showSelfPlay ? "block" : "none";
  document.getElementById("idle-screen").style.display = isGame ? "none"  : "block";

  document.getElementById("no-game-msg").style.display  = (isGame && gameState === "idle" && !showSelfPlay) ? "flex" : "none";
  document.getElementById("game-content").style.display = (isGame && gameState === "active") ? "block" : "none";

  if (!isGame) {
    document.getElementById("panel-activity").style.display = isActivity ? "block" : "none";
    document.getElementById("panel-stats").style.display    = isStats    ? "block" : "none";
    if (isStats && lastIdleState) renderStats(lastIdleState);
  }
}

function switchTab(tab) {
  activeTab = tab;
  ["game", "activity", "stats"].forEach(function(t) {
    document.getElementById("tab-" + t).classList.toggle("active", t === tab);
  });
  applyTabView();
}

// ── Activity filter ──────────────────────────────────────────────────────────
function setActivityFilter(f) {
  activityFilter = f;
  ["games","outgoing","incoming"].forEach(function(k) {
    document.getElementById("af-" + k).classList.toggle("active", k === f);
  });
  if (lastIdleState) updateIdleContent(lastIdleState);
}

// ── Streak helper ─────────────────────────────────────────────────────────────
function computeStreak(games) {
  if (!games || games.length === 0) return {count: 0, type: null};
  let count = 1, type = games[0].event;
  for (let i = 1; i < games.length; i++) {
    if (games[i].event === type) count++;
    else break;
  }
  return {count: count, type: type};
}

// ── Stats panel ──────────────────────────────────────────────────────────────
function renderSparkline(games, tc) {
  const filtered = tc === "all" ? games : games.filter(function(g) { return g.time_control === tc; });
  const chrono   = filtered.slice().reverse();
  const pts      = chrono.map(function(g) { return g.bot_rating; }).filter(function(r) { return r != null; });
  if (pts.length < 2) {
    return "<div style='color:#445;font-size:0.85rem;padding:20px 0;text-align:center'>Not enough data</div>";
  }
  const W = 600, H = 90, PX = 12, PY = 10;
  const lo = Math.min.apply(null, pts) - 5;
  const hi = Math.max.apply(null, pts) + 5;
  const range = hi - lo || 1;
  const coords = pts.map(function(r, i) {
    const x = PX + (i / (pts.length - 1)) * (W - 2 * PX);
    const y = PY + (1 - (r - lo) / range) * (H - 2 * PY);
    return [x.toFixed(1), y.toFixed(1)];
  });
  const polyline = coords.map(function(c) { return c[0] + "," + c[1]; }).join(" ");
  const lx = coords[coords.length - 1][0];
  const ly = coords[coords.length - 1][1];
  const first = pts[0], last = pts[pts.length - 1];
  const delta = last - first;
  const deltaStr = (delta >= 0 ? "+" : "") + delta;
  const deltaCol = delta >= 0 ? "#2ecc71" : "#e74c3c";
  return "<div style='display:flex;align-items:baseline;gap:10px;margin-bottom:4px'>"
       + "<span style='font-size:1.3rem;font-weight:700;color:#e8e8f0'>" + last + "</span>"
       + "<span style='font-size:0.85rem;color:" + deltaCol + "'>" + deltaStr + " over " + pts.length + " games</span>"
       + "</div>"
       + "<svg viewBox='0 0 " + W + " " + H + "' style='width:100%;height:80px'>"
       + "<polyline points='" + polyline + "' fill='none' stroke='#3498db' stroke-width='2'/>"
       + "<circle cx='" + lx + "' cy='" + ly + "' r='3.5' fill='#3498db'/>"
       + "</svg>";
}

function renderStats(s) {
  const games = (s.activity || []).filter(function(r) { return r.row_type === "game"; });
  if (games.length === 0) {
    ["sparkline-wrap","record-bar-wrap","by-tc-wrap","top-opp-wrap"].forEach(function(id) {
      document.getElementById(id).innerHTML =
        "<div style='color:#445;font-size:0.85rem;padding:12px 0'>No game data</div>";
    });
    return;
  }

  // Sparkline
  const tcs = Array.from(new Set(games.map(function(g) { return g.time_control; }))).sort(cmpTC);
  const tcBtns = [["all","All"]].concat(tcs.map(function(t) { return [t, t]; }));
  document.getElementById("sparkline-tc-buttons").innerHTML = tcBtns.map(function(b) {
    return "<button class='sparkline-tc-btn" + (sparklineTC === b[0] ? " active" : "")
         + "' onclick='setSparklineTC(&quot;" + b[0] + "&quot;)'>" + b[1] + "</button>";
  }).join("");
  document.getElementById("sparkline-wrap").innerHTML = renderSparkline(games, sparklineTC);

  // Overall record
  let W = 0, D = 0, L = 0;
  games.forEach(function(g) {
    if (g.event === "win") W++;
    else if (g.event === "draw") D++;
    else L++;
  });
  const total = W + D + L;
  const score = ((W + D * 0.5) / total * 100).toFixed(1);
  const wp = (W/total*100).toFixed(1), dp = (D/total*100).toFixed(1), lp = (L/total*100).toFixed(1);
  document.getElementById("record-bar-wrap").innerHTML =
    "<div class='record-bar'>"
    + "<div class='record-bar-w' style='width:" + wp + "%'></div>"
    + "<div class='record-bar-d' style='width:" + dp + "%'></div>"
    + "<div class='record-bar-l' style='width:" + lp + "%'></div>"
    + "</div>"
    + "<div class='record-legend'>"
    + "<span><div class='legend-dot' style='background:#2ecc71'></div>" + W + "W (" + wp + "%)</span>"
    + "<span><div class='legend-dot' style='background:#555'></div>" + D + "D (" + dp + "%)</span>"
    + "<span><div class='legend-dot' style='background:#e74c3c'></div>" + L + "L (" + lp + "%)</span>"
    + "</div>"
    + "<div style='margin-top:8px;font-size:0.8rem;color:#6878a8'>Score: <span style='color:#e8e8f0;font-weight:700'>" + score + "%</span>"
    + " &nbsp;|&nbsp; " + total + " games</div>";

  // Streak
  const sk = computeStreak(games);
  const streakCol = sk.type === "win" ? "#2ecc71" : sk.type === "loss" ? "#e74c3c" : "#888";
  const skPlural  = sk.type === "loss" ? "losses" : (sk.type + "s");
  const skLabel   = sk.count > 1 ? skPlural : sk.type;
  document.getElementById("record-bar-wrap").innerHTML +=
    "<div style='margin-top:6px;font-size:0.8rem;color:#6878a8'>Current streak: "
    + "<span style='color:" + streakCol + ";font-weight:700'>" + sk.count + " " + skLabel + "</span></div>";

  // By time control
  const byTC = {};
  games.forEach(function(g) {
    const t = g.time_control || "?";
    if (!byTC[t]) byTC[t] = {w:0,d:0,l:0};
    if (g.event === "win") byTC[t].w++;
    else if (g.event === "draw") byTC[t].d++;
    else byTC[t].l++;
  });
  const tcRows = Object.keys(byTC).sort(cmpTC).map(function(t) {
    const b = byTC[t];
    const n = b.w + b.d + b.l;
    const sc = ((b.w + b.d * 0.5) / n * 100).toFixed(0);
    return "<tr><td>" + t + "</td><td style='color:#2ecc71'>" + b.w + "</td>"
         + "<td style='color:#888'>" + b.d + "</td><td style='color:#e74c3c'>" + b.l + "</td>"
         + "<td style='color:#e8e8f0;font-weight:600'>" + sc + "%</td></tr>";
  }).join("");
  document.getElementById("by-tc-wrap").innerHTML =
    "<table class='by-tc-table'><thead><tr><th>TC</th><th>W</th><th>D</th><th>L</th><th>Score</th></tr></thead>"
    + "<tbody>" + tcRows + "</tbody></table>";

  // Top opponents (by games played)
  const oppMap = {};
  games.forEach(function(g) {
    const n = g.opponent || "?";
    if (!oppMap[n]) oppMap[n] = {w:0,d:0,l:0,rating:g.opponent_rating};
    if (g.event === "win") oppMap[n].w++;
    else if (g.event === "draw") oppMap[n].d++;
    else oppMap[n].l++;
  });
  const topOpps = Object.keys(oppMap)
    .map(function(n) { const b = oppMap[n]; return {name:n, total:b.w+b.d+b.l, w:b.w, d:b.d, l:b.l, rating:b.rating}; })
    .sort(function(a,b) { return b.total - a.total; })
    .slice(0, 8);
  const oppRows = topOpps.map(function(o) {
    const score = ((o.w + o.d * 0.5) / o.total * 100).toFixed(0);
    return "<tr><td>" + o.name + "</td><td style='color:#8898c8'>" + (o.rating || "—") + "</td>"
         + "<td>" + o.total + "</td><td style='font-weight:600;color:"
         + (parseFloat(score) >= 50 ? "#2ecc71" : "#e74c3c") + "'>" + score + "%</td></tr>";
  }).join("");
  document.getElementById("top-opp-wrap").innerHTML =
    "<table class='top-opp-table'><thead><tr><th>Opponent</th><th>Rating</th><th>Games</th><th>Score</th></tr></thead>"
    + "<tbody>" + oppRows + "</tbody></table>";
}

function setSparklineTC(tc) {
  sparklineTC = tc;
  if (lastIdleState) renderStats(lastIdleState);
}

// ── Render ───────────────────────────────────────────────────────────────────
function statCard(label, value, sub, valueColor) {
  const val = value != null ? String(value) : "—";
  const style = valueColor ? " style='color:" + valueColor + "'" : "";
  const subHtml = sub != null ? "<div class='idle-stat-sub'>" + sub + "</div>" : "";
  return "<div class='idle-stat-card'>"
       + "<div class='idle-stat-label'>" + label + "</div>"
       + "<div class='idle-stat-value'" + style + ">" + val + "</div>"
       + subHtml + "</div>";
}

function updateIdleContent(s) {
  // Profile stats
  const p = s && s.profile;
  const dc = s && s.daily_counts;
  const games_all = (s && s.activity || []).filter(function(r) { return r.row_type === "game"; });
  const sk = computeStreak(games_all);
  const streakPlural = sk.type === "loss" ? "losses" : (sk.type + "s");
  const streakVal = sk.count > 0 ? sk.count + " " + (sk.count > 1 ? streakPlural : sk.type) : "—";
  const streakColor = sk.type === "win" ? "#2ecc71" : sk.type === "loss" ? "#e74c3c" : null;
  const statsRow = document.getElementById("idle-stats-row");
  statsRow.innerHTML = [
    statCard("Bullet",  p && p.bullet_rating,  p ? p.bullet_games + " games" : null),
    statCard("Blitz",   p && p.blitz_rating,   p ? p.blitz_games  + " games" : null),
    statCard("Rapid",   p && p.rapid_rating,   p ? p.rapid_games  + " games" : null),
    statCard("Total Games", p && p.nb_games,
             p ? p.nb_wins + "W " + p.nb_draws + "D " + p.nb_losses + "L" : null),
    statCard("Challenges", dc && dc.challenges != null ? dc.challenges : null, "of 250 today"),
    statCard("Games Today", dc && dc.games != null ? dc.games : null, null),
    statCard("Streak", sk.count > 0 ? streakVal : "—", null, streakColor),
  ].join("");

  // Activity feed — use full challenges list for direction filters so games don't crowd them out
  let rows;
  if (activityFilter === "outgoing") {
    rows = (s && s.challenges || []).filter(function(r) { return r.direction === "outgoing"; });
  } else if (activityFilter === "incoming") {
    rows = (s && s.challenges || []).filter(function(r) { return r.direction === "incoming"; });
  } else if (activityFilter === "games") {
    rows = (s && s.activity || []).filter(function(r) { return r.row_type === "game"; });
  } else {
    rows = s && s.activity;
  }
  const tbody = document.getElementById("challenge-tbody");
  const empty = document.getElementById("challenge-empty");
  if (!rows || rows.length === 0) {
    tbody.innerHTML = "";
    empty.style.display = "block";
  } else {
    empty.style.display = "none";
    tbody.innerHTML = rows.map(function(r) {
      const ts  = r.timestamp_utc ? (function(s) {
        try {
          return new Date(s.replace(" ","T") + "Z").toLocaleTimeString("en-US",
            {timeZone:"America/New_York", hour:"numeric", minute:"2-digit", hour12:true});
        } catch(e) { return s.slice(11,16); }
      })(r.timestamp_utc) : "";
      const tc  = r.time_control  || "—";
      const rat = r.opponent_rating != null ? r.opponent_rating : "—";

      if (r.row_type === "game") {
        const url    = "https://lichess.org/" + r.game_id;
        const dirEl  = "<span class='ch-dir-game'>\u265f</span>";
        const evtEl  = "<span class='ch-game-" + r.event + "'>" + r.event + "</span>";
        const oppEl  = "<a href='" + url + "' target='_blank' class='activity-link'>"
                     + (r.opponent || "—") + "</a>";
        const diff   = r.rating_diff;
        const infoEl = diff != null
          ? "<span class='" + (diff >= 0 ? "ch-rating-pos" : "ch-rating-neg") + "'>"
            + (diff >= 0 ? "+" : "") + diff + "</span>"
          : "";
        return "<tr><td>" + ts + "</td><td>" + dirEl + "</td><td>" + evtEl
             + "</td><td>" + oppEl + "</td><td>" + rat + "</td><td>" + tc
             + "</td><td>" + infoEl + "</td></tr>";
      } else {
        const dir    = r.direction === "outgoing" ? "outgoing" : "incoming";
        const evt    = r.event || "";
        const cls    = "ch-" + dir.slice(0,3) + "-" + evt;
        const dirEl  = dir === "outgoing"
          ? "<span class='dir-badge dir-out'>OUT</span>"
          : "<span class='dir-badge dir-in'>IN</span>";
        const evtEl  = "<span class='" + cls + "'>" + evt + "</span>";
        const isBot  = r.opponent_is_bot === "True" || r.opponent_is_bot === true;
        const botBadge = isBot ? "<span class='bot-badge'>BOT</span>" : "";
        const opp    = (r.opponent || "—") + botBadge;
        const reason = r.decline_reason || "";
        return "<tr><td>" + ts + "</td><td>" + dirEl + "</td><td>" + evtEl
             + "</td><td>" + opp + "</td><td>" + rat + "</td><td>" + tc
             + "</td><td>" + reason + "</td></tr>";
      }
    }).join("");
  }

  if (activeTab === "stats" && s) renderStats(s);
}

function updateGameContent(s) {
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
  (function() {
    if (!init && !inc) { document.getElementById("tc-chip").textContent = "—"; return; }
    const initS = Math.round((init||0) / 1000);
    const incS  = Math.round((inc||0) / 1000);
    const fracs = {15:"¼", 30:"½", 45:"¾"};
    const minStr = initS >= 60 ? Math.floor(initS/60) : (fracs[initS] || initS+"s");
    document.getElementById("tc-chip").textContent = minStr + "+" + incS;
  })();
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
    const botIsWhite = s.bot_color === "white";
    const botCaps = botIsWhite ? caps.b : caps.w;
    const oppCaps = botIsWhite ? caps.w : caps.b;
    const botAdv = botIsWhite ? caps.advantage : -caps.advantage;
    document.getElementById("bot-captures").textContent =
      botCaps + (botAdv > 0 ? " +" + botAdv : "");
    document.getElementById("opp-captures").textContent =
      oppCaps + (botAdv < 0 ? " +" + (-botAdv) : "");
  } catch(e) {}

  // Clocks — only restart ticker if values changed
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
  if (!mateSweptThisGame && botMate != null && botMate > 0) {
    mateSweptThisGame = true;
    const sweep = document.getElementById("board-mate-sweep");
    sweep.classList.remove("sweeping");
    void sweep.offsetWidth;
    sweep.classList.add("sweeping");
  }

  // SF eval (stored from white's POV — flip sign for color when bot is black)
  const sfEl = document.getElementById("sf-eval");
  const sfCpBot   = sf && s.bot_color === "black" ? (sf.cp != null ? -sf.cp : null) : (sf ? sf.cp : null);
  const sfMateBot = sf && s.bot_color === "black" ? (sf.mate != null ? -sf.mate : null) : (sf ? sf.mate : null);
  sfEl.textContent = sf ? fmtCp(sfCpBot, sfMateBot) : "—";
  sfEl.className  = "eval-value " + (sf ? cpClass(sfCpBot, sfMateBot) : "");

  // Eval bar — eng.cp is from side-to-move's POV; convert to white's POV for the bar
  const barCp   = (botCp   != null && s.bot_color === "black") ? -botCp   : botCp;
  const barMate = (botMate != null && s.bot_color === "black") ? -botMate : botMate;
  document.getElementById("eval-bar").classList.toggle("flipped", s.bot_color === "black");
  document.getElementById("eval-bar").style.height = evalToPercent(barCp, barMate) + "%";

  // Engine stats
  const isOpponentTurn = s.clock && s.clock.turn !== s.bot_color;
  document.getElementById("st-depth").textContent  = eng && eng.depth  != null ? eng.depth  : "—";
  document.getElementById("st-nodes").textContent  = eng ? fmtNodes(eng.nodes)  : "—";
  const derivedNps = (eng && eng.nps != null) ? eng.nps
    : (eng && eng.nodes && eng.time_ms ? Math.round(eng.nodes / eng.time_ms) : null);
  document.getElementById("st-nps").textContent    = fmtNps(derivedNps);
  document.getElementById("st-time").textContent   =
    isOpponentTurn ? "—" : (eng && eng.time_ms != null ? eng.time_ms.toFixed(2) + "s" : "—");
  document.getElementById("st-tbhits").textContent = eng ? fmtNodes(eng.tbhits) : "—";
  const srcEl = document.getElementById("st-source");
  if (isOpponentTurn) {
    const pmove = eng && eng.ponder_move ? " " + eng.ponder_move : "";
    srcEl.textContent = "Pondering" + pmove;
    srcEl.classList.add("pondering");
  } else {
    srcEl.textContent = eng && eng.source ? eng.source : "—";
    srcEl.classList.remove("pondering");
  }
}

// ── Game result overlay ──────────────────────────────────────────────────────
const RESULT_METHOD = {
  resign: "by resignation", mate: "by checkmate", stalemate: "draw by stalemate",
  draw: "by agreement", timeout: "on time", outoftime: "on time",
  cheat: "by cheat detection", variantEnd: "variant end",
};
function showResultOverlay(s) {
  const lr = s.last_result, botColor = s.bot_color, game = s.game;
  const winner = lr.winner;
  let heading, icon, color;
  if (!winner || lr.status === "draw" || lr.status === "stalemate") {
    heading = "Draw"; icon = "½"; color = "#8898c8";
  } else if (winner === botColor) {
    heading = "Victory!"; icon = "♛"; color = "#2ecc71";
  } else {
    heading = "Defeat"; icon = "♟"; color = "#e74c3c";
  }
  const oppColor = botColor === "white" ? "black" : "white";
  const opp = game[oppColor];
  document.getElementById("result-icon").textContent = icon;
  document.getElementById("result-heading").textContent = heading;
  document.getElementById("result-heading").style.color = color;
  document.getElementById("result-opponent").textContent = "vs " + opp.name + (opp.rating ? " (" + opp.rating + ")" : "");
  document.getElementById("result-method").textContent = RESULT_METHOD[lr.status] || lr.status || "";
  document.getElementById("result-game-link").href = game.url;
  const overlay = document.getElementById("result-overlay");
  overlay.style.display = "flex";
  const fill = document.getElementById("result-dismiss-fill");
  fill.style.transition = "none";
  fill.style.width = "100%";
  setTimeout(function() { fill.style.transition = "width 6s linear"; fill.style.width = "0%"; }, 30);
  clearTimeout(resultDismissTimer);
  resultDismissTimer = setTimeout(dismissResultOverlay, 6000);
}
function dismissResultOverlay() {
  clearTimeout(resultDismissTimer);
  document.getElementById("result-overlay").style.display = "none";
}

// ── Self-play state tracking ──────────────────────────────────────────────────
var spPrevStatus = {};

// ── Mini-board renderer ───────────────────────────────────────────────────────
const FEN_TO_IMG = {
  K:'wK', Q:'wQ', R:'wR', B:'wB', N:'wN', P:'wP',
  k:'bK', q:'bQ', r:'bR', b:'bB', n:'bN', p:'bP'
};

function buildMiniBoard(fen, lastMove) {
  const rows = fen.split(" ")[0].split("/");
  const hi   = new Set(lastMove && lastMove.length >= 4
    ? [lastMove.slice(0,2), lastMove.slice(2,4)] : []);
  var html = "";
  for (var r = 0; r < 8; r++) {
    var f = 0;
    for (var ci = 0; ci < rows[r].length; ci++) {
      var ch = rows[r][ci];
      if (ch >= "1" && ch <= "8") {
        for (var e = 0; e < +ch; e++, f++) {
          var sq   = "abcdefgh"[f] + (8 - r);
          var lite = (f + r) % 2 === 0;
          var hlit = hi.has(sq);
          html += '<div class="mini-sq ' + (lite?"light":"dark") + (hlit?" hi":"") + '"></div>';
        }
      } else {
        var sq   = "abcdefgh"[f] + (8 - r);
        var lite = (f + r) % 2 === 0;
        var hlit = hi.has(sq);
        var img = FEN_TO_IMG[ch] ? '<img src="/img/' + FEN_TO_IMG[ch] + '.png" class="mini-piece">' : '';
        html += '<div class="mini-sq ' + (lite?"light":"dark") + (hlit?" hi":"") + '">' + img + "</div>";
        f++;
      }
    }
  }
  return html;
}

function renderSelfPlay(s) {
  document.getElementById("status-dot").classList.remove("live");
  gameState = "idle";
  prevGameState = "idle";
  selfPlayActive = true;
  stopClock();
  if (s.activity || s.profile) {
    lastIdleState = s;
    updateIdleContent(s);
  }
  applyTabView();

  var grid = document.getElementById("sp-grid");
  if (!grid) return;

  function fmtNum(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 10e6 ? 1 : 2).replace(/\.?0+$/, '') + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(n >= 10e3 ? 1 : 2).replace(/\.?0+$/, '') + 'K';
    return String(n);
  }
  var totalGames = s.total_games || 0;
  var totalMoves = s.total_moves || 0;
  document.getElementById("sp-move-ticker").textContent = fmtNum(totalGames) + " games · " + fmtNum(totalMoves) + " moves";

  s.games.forEach(function(g) {
    var card = document.getElementById("sp-card-" + g.idx);
    if (!card) {
      card = document.createElement("div");
      card.className = "sp-card";
      card.id = "sp-card-" + g.idx;
      grid.appendChild(card);
    }

    var badge = "";
    if (g.status === "finished" && g.result) {
      var winner = g.result === "1-0" ? g.white_label
                 : g.result === "0-1" ? g.black_label : null;
      var cls    = g.result === "1-0" ? "white-wins"
                 : g.result === "0-1" ? "black-wins" : "draw";
      badge = '<span class="sp-result-badge ' + cls + '">' + (winner ? winner + " wins" : "Draw") + '</span>';
    }

    var prevSt = spPrevStatus[g.idx];
    spPrevStatus[g.idx] = g.status;

    card.innerHTML =
      '<div class="sp-side-label sp-top-label">' + g.black_label + '</div>'
      + '<div class="mini-board-wrap"><div class="mini-board">' + buildMiniBoard(g.fen, g.last_move) + '</div></div>'
      + '<div class="sp-side-label sp-bottom-label">' + (badge || g.white_label) + '</div>';

    if (prevSt === 'finished' && g.status === 'playing') {
      var wrap = card.querySelector('.mini-board-wrap');
      if (wrap) {
        wrap.classList.add('wiping');
        wrap.addEventListener('animationend', function() {
          wrap.classList.remove('wiping');
        }, { once: true });
      }
    }
  });

}

function renderIdle(s) {
  document.getElementById("status-dot").classList.remove("live");
  gameState = "idle";
  selfPlayActive = false;
  const wasActive = prevGameState === "active";
  prevGameState = "idle";

  if (wasActive && s && s.last_result && s.last_result.status !== "aborted") {
    showResultOverlay(s);
  }

  stopClock();
  lastClockWtime = -1; lastClockBtime = -1; lastClockTurn = null;

  document.getElementById("bot-name-text").textContent = "—";
  document.getElementById("opponent-name-text").textContent = "—";
  document.getElementById("bot-captures").textContent = "";
  document.getElementById("opp-captures").textContent = "";

  lastIdleState = s;
  updateIdleContent(s);
  applyTabView();
}

function renderUpdate(s) {
  document.getElementById("status-dot").classList.add("live");
  selfPlayActive = false;
  gameState = "active";

  // Auto-switch to game tab when game starts
  if (prevGameState === "idle") {
    activeTab = "game";
    ["game","activity","stats"].forEach(function(t) {
      document.getElementById("tab-" + t).classList.toggle("active", t === "game");
    });
    mateSweptThisGame = false;
  }
  prevGameState = "active";

  lastIdleState = s;
  updateIdleContent(s);
  applyTabView();        // make #game-content visible before initBoard reads offsetWidth
  updateGameContent(s);
}

// ── SSE connection ───────────────────────────────────────────────────────────
function connect() {
  const es = new EventSource("/events");
  es.onmessage = function(e) {
    try {
      const s = JSON.parse(e.data);
      if      (s.type === "idle")      renderIdle(s);
      else if (s.type === "update")    renderUpdate(s);
      else if (s.type === "self_play") renderSelfPlay(s);
    } catch(err) { console.error("SSE render error:", err); }
  };
  es.onerror = function() {
    es.close();
    document.getElementById("status-dot").classList.remove("live");
    setTimeout(connect, 5000);
  };
}

renderIdle(null);
connect();

// Global floating tooltip — immune to table overflow clipping
(function() {
  var tt = document.createElement('div');
  tt.id = 'stat-tooltip';
  document.body.appendChild(tt);
  document.querySelectorAll('.stat-th-tip').forEach(function(el) {
    el.addEventListener('mouseenter', function() {
      tt.textContent = el.dataset.tip || '';
      var rect = el.getBoundingClientRect();
      tt.style.top  = (rect.top - 38 + window.scrollY) + 'px';
      tt.style.left = (rect.left + rect.width / 2) + 'px';
      tt.style.display = 'block';
    });
    el.addEventListener('mouseleave', function() {
      tt.style.display = 'none';
    });
  });
})();
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
