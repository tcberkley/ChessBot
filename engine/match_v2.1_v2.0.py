#!/usr/bin/env python3
"""
v2.1_engine vs v2.0_engine — 100-game local match (50 opening pairs × 2 colors).
Movetime: 100ms. Sends results email when done.

Usage:
  python3 match_v2.1_v2.0.py [--engine1 PATH] [--engine2 PATH] [--seed N]
"""

import argparse
import datetime
import math
import os
import random
import smtplib
import subprocess
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import chess

# ── Constants ─────────────────────────────────────────────────────────────────

MOVETIME   = 100   # ms per move
N_OPENINGS = 50    # 50 pairs × 2 colors = 100 games
MAX_MOVES  = 200   # half-moves per game before draw declared

SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
RECIPIENT  = "tcberkley@gmail.com"

# ── .env loader ───────────────────────────────────────────────────────────────

def load_dotenv():
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parent.parent / ".env",   # project root
        Path("/root/lichess-bot-master/.env"),
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())
            break

load_dotenv()

# ── Engine wrapper ────────────────────────────────────────────────────────────

class Engine:
    def __init__(self, path, name, hash_mb=8):
        self.name = name
        self.proc = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )
        self._send("uci")
        self._read_until("uciok")
        self._send(f"setoption name Hash value {hash_mb}")
        self._send("ucinewgame")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _read_until(self, token):
        while True:
            line = self.proc.stdout.readline().strip()
            if token in line:
                return

    def get_move(self, fen, movetime):
        self._send(f"position fen {fen}")
        self._send(f"go movetime {movetime}")
        while True:
            line = self.proc.stdout.readline().strip()
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2 and parts[1] not in ("(none)", "0000"):
                    return parts[1]
                return None

    def new_game(self):
        self._send("ucinewgame")
        self._send("isready")
        self._read_until("readyok")

    def quit(self):
        try:
            self._send("quit")
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


# ── Opening generation ────────────────────────────────────────────────────────

def generate_opening(rng, plies=10):
    board = chess.Board()
    for _ in range(plies):
        legal = list(board.legal_moves)
        if not legal:
            break
        move = rng.choice(legal)
        board.push(move)
        if board.is_game_over():
            board.pop()
            break
    return board.fen()


# ── Single game ───────────────────────────────────────────────────────────────

def play_game(white_eng, black_eng, start_fen, movetime, max_moves=MAX_MOVES):
    board = chess.Board(start_fen)
    for _ in range(max_moves):
        if board.is_game_over(claim_draw=True):
            break
        engine = white_eng if board.turn == chess.WHITE else black_eng
        move_uci = engine.get_move(board.fen(), movetime)
        if move_uci is None:
            break
        try:
            move = chess.Move.from_uci(move_uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        board.push(move)
    result = board.result(claim_draw=True)
    if result == "1-0":
        return 1.0
    elif result == "0-1":
        return 0.0
    else:
        return 0.5


# ── Email ─────────────────────────────────────────────────────────────────────

def build_html(e1_name, e2_name, wins, draws, losses, score, total,
               elapsed, game_log):
    pct = 100.0 * score / total if total > 0 else 0.0
    if 0 < score < total:
        elo_diff = 400.0 * math.log10(score / (total - score))
        elo_str = f"{elo_diff:+.1f}"
    else:
        elo_str = "±∞" if score == total else "−∞"

    lines = ['<html><body style="font-family:monospace;font-size:13px;">']
    lines.append(f'<h2>{e1_name} vs {e2_name} — 100-Game Match</h2>')
    lines.append('<table style="margin-bottom:16px;border-spacing:6px">')
    lines.append(f'<tr><td><b>Result:</b></td>'
                 f'<td>{e1_name}: {wins}W / {draws}D / {losses}L'
                 f' = {score:.1f}/{total} ({pct:.1f}%)</td></tr>')
    lines.append(f'<tr><td><b>Elo diff:</b></td><td>{elo_str} cp (vs {e2_name})</td></tr>')
    lines.append(f'<tr><td><b>Movetime:</b></td><td>{MOVETIME}ms</td></tr>')
    lines.append(f'<tr><td><b>Openings:</b></td><td>{N_OPENINGS} × 2 colors</td></tr>')
    lines.append(f'<tr><td><b>Duration:</b></td><td>{elapsed/3600:.2f}h</td></tr>')
    lines.append('</table>')

    lines.append('<h3>Per-Game Log</h3>')
    lines.append('<pre style="font-size:12px">')
    lines.append(f"{'Game':>5}  {'Open':>5}  {'Color':>5}  {'Result':>6}  "
                 f"{e1_name+' Score':>10}  {'W':>4} {'D':>4} {'L':>4}  "
                 f"{'Elapsed':>8}  {'ETA':>8}")
    lines.append("-" * 75)
    for row in game_log:
        lines.append(row)
    lines.append('</pre>')
    lines.append('</body></html>')
    return "\n".join(lines)


def send_email(subject, html_body):
    sender   = os.environ.get("SUMMARY_EMAIL_SENDER", "")
    password = os.environ.get("SUMMARY_EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        print("Email skipped — SUMMARY_EMAIL_SENDER / SUMMARY_EMAIL_APP_PASSWORD not set.",
              flush=True)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, RECIPIENT, msg.as_string())
        print(f"Email sent: {subject}", flush=True)
    except Exception as e:
        print(f"Email failed: {e}", flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="v2.1 vs v2.0 — 100-game match")
    parser.add_argument("--engine1", default="./v2.1_engine",
                        help="Path to engine 1 / new (default: ./v2.1_engine)")
    parser.add_argument("--engine2", default="./v2.0_engine",
                        help="Path to engine 2 / baseline (default: ./v2.0_engine)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    e1_path = args.engine1
    e2_path = args.engine2

    for path in (e1_path, e2_path):
        if not os.path.isfile(path):
            print(f"ERROR: engine not found: {path}", flush=True)
            sys.exit(1)

    e1_name = Path(e1_path).name.replace("_engine", "")
    e2_name = Path(e2_path).name.replace("_engine", "")

    print(f"Starting engines...", flush=True)
    try:
        eng1 = Engine(e1_path, e1_name)
        eng2 = Engine(e2_path, e2_name)
    except Exception as ex:
        print(f"ERROR starting engine: {ex}", flush=True)
        sys.exit(1)
    print(f"  {e1_name}: {e1_path}", flush=True)
    print(f"  {e2_name}: {e2_path}", flush=True)
    print(f"  Movetime: {MOVETIME}ms  Openings: {N_OPENINGS}  Total games: {N_OPENINGS*2}",
          flush=True)

    rng = random.Random(args.seed)
    openings = [generate_opening(rng, plies=10) for _ in range(N_OPENINGS)]

    score  = 0.0
    wins   = draws = losses = 0
    game_num = 0
    game_log = []
    start_time = time.time()
    total_games = N_OPENINGS * 2

    header = (f"{'Game':>5}  {'Open':>5}  {'Color':>5}  {'Result':>6}  "
              f"{e1_name+' Score':>10}  {'W':>4} {'D':>4} {'L':>4}  "
              f"{'Elapsed':>8}  {'ETA':>8}")
    sep = "-" * 75
    print(f"\n{'='*75}", flush=True)
    print(f"  {e1_name} vs {e2_name} — {N_OPENINGS} openings × 2 colors = {total_games} games",
          flush=True)
    print(f"{'='*75}", flush=True)
    print(header, flush=True)
    print(sep, flush=True)

    try:
        for i, fen in enumerate(openings):
            for eng1_is_white in [True, False]:
                game_num += 1
                if eng1_is_white:
                    white_e, black_e = eng1, eng2
                    color_str = "White"
                else:
                    white_e, black_e = eng2, eng1
                    color_str = "Black"

                result_white = play_game(white_e, black_e, fen, MOVETIME)

                eng1_result = result_white if eng1_is_white else (1.0 - result_white)
                score += eng1_result

                if eng1_result == 1.0:
                    wins += 1;   res_str = "Win"
                elif eng1_result == 0.5:
                    draws += 1;  res_str = "Draw"
                else:
                    losses += 1; res_str = "Loss"

                elapsed = time.time() - start_time
                eta = elapsed / game_num * (total_games - game_num) if game_num > 0 else 0

                row = (f"{game_num:>5}  {i+1:>5}  {color_str:>5}  {res_str:>6}  "
                       f"{score:>10.1f}  {wins:>4} {draws:>4} {losses:>4}  "
                       f"{elapsed/3600:>6.2f}h  {eta/3600:>6.2f}h")
                print(row, flush=True)
                game_log.append(row)

                eng1.new_game()
                eng2.new_game()

    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)

    # Final summary
    elapsed = time.time() - start_time
    total = game_num
    pct = 100.0 * score / total if total > 0 else 0.0
    if 0 < score < total:
        elo_diff = 400.0 * math.log10(score / (total - score))
        elo_str = f"{elo_diff:+.1f}"
    else:
        elo_str = "±∞"

    print(f"\n{'='*75}", flush=True)
    print(f"  FINAL: {e1_name} vs {e2_name}  ({total} games)", flush=True)
    print(f"  {e1_name}: {wins}W / {draws}D / {losses}L  =  {score:.1f}/{total}  ({pct:.1f}%)",
          flush=True)
    print(f"  Elo diff: {elo_str} (vs {e2_name})", flush=True)
    print(f"  Elapsed: {elapsed/3600:.2f}h", flush=True)
    print(f"{'='*75}", flush=True)

    eng1.quit()
    eng2.quit()

    # Send email
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    subject = f"{e1_name} vs {e2_name} — 100 games complete ({date_str})"
    html = build_html(e1_name, e2_name, wins, draws, losses, score, total,
                      elapsed, game_log)
    send_email(subject, html)


if __name__ == "__main__":
    main()
