#!/usr/bin/env python3
"""
Round-robin all-versions tournament (v1.0–v2.1).

Usage:
  python3 round_robin.py [options]

  --engine-dir DIR   Directory with v*_engine binaries (default: ~/c_rewrite)
  --movetime MS      ms per move (default: 100)
  --end-time HH:MM   Local time to stop and send email (default: 08:00)
  --log PATH         JSONL output path (default: /tmp/rr_allversions.jsonl)
  --hash MB          TT size per engine in MB (default: 8)
  --seed N           RNG seed (default: 42)
  --test-email       Send a test email with dummy data and exit
  --report PATH      Print current standings from JSONL and exit
"""

import argparse
import base64
import datetime
import json
import os
import random
import smtplib
import subprocess
import sys
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import chess

# ── Constants ─────────────────────────────────────────────────────────────────

VERSIONS = ["1.0","1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8","1.9","1.10","1.11","2.0","2.1"]
V20_ELO_ANCHOR = 2225
V20_IDX = VERSIONS.index("2.0")    # index of v2.0 in VERSIONS list

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
RECIPIENT = "tcberkley@gmail.com"

# ── .env loader ───────────────────────────────────────────────────────────────

def load_dotenv():
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent / ".env",
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

def play_game(white_eng, black_eng, start_fen, movetime, max_moves=200):
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


# ── JSONL logging ─────────────────────────────────────────────────────────────

def append_game(log_path, white_name, black_name, result, opening_fen):
    record = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "white": white_name,
        "black": black_name,
        "result": result,
        "opening_fen": opening_fen,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_games(log_path):
    games = []
    if not os.path.isfile(log_path):
        return games
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return games


# ── Elo computation (MLE) ─────────────────────────────────────────────────────

def compute_elo(games):
    """
    MLE Elo ratings for all versions. Fixes v2.0 = V20_ELO_ANCHOR as anchor.
    Returns dict {version: (elo, ci_95)} or None if scipy unavailable.
    """
    try:
        from scipy.optimize import minimize
        import numpy as np
    except ImportError:
        return None

    n = len(VERSIONS)
    name_to_idx = {f"v{v}": i for i, v in enumerate(VERSIONS)}

    game_list = []
    for g in games:
        wi = name_to_idx.get(g["white"])
        bi = name_to_idx.get(g["black"])
        if wi is None or bi is None:
            continue
        game_list.append((wi, bi, float(g["result"])))

    if not game_list:
        return {v: (V20_ELO_ANCHOR if v == "2.0" else 1500, None) for v in VERSIONS}

    # Optimize 13 free parameters (all except v2.0, which is fixed = 0 offset)
    free_indices = [i for i in range(n) if i != V20_IDX]

    def full_theta(theta_free):
        theta = np.zeros(n)
        for k, fi in enumerate(free_indices):
            theta[fi] = theta_free[k]
        return theta

    def neg_ll(theta_free):
        theta = full_theta(theta_free)
        ll = 0.0
        eps = 1e-9
        for (i, j, r) in game_list:
            e = 1.0 / (1.0 + 10.0 ** ((theta[j] - theta[i]) / 400.0))
            ll += r * np.log(e + eps) + (1.0 - r) * np.log(1.0 - e + eps)
        return -ll

    x0 = np.zeros(n - 1)
    res = minimize(neg_ll, x0, method="BFGS", options={"maxiter": 10000, "gtol": 1e-8})
    theta_opt = full_theta(res.x)

    # 95% CI from BFGS inverse Hessian diagonal
    ci_full = np.zeros(n)
    if hasattr(res, "hess_inv") and res.hess_inv is not None:
        hess_inv = np.array(res.hess_inv)
        se_free = np.sqrt(np.maximum(np.diag(hess_inv), 0))
        for k, fi in enumerate(free_indices):
            ci_full[fi] = 1.96 * se_free[k]

    elo_dict = {}
    for i, v in enumerate(VERSIONS):
        elo_dict[v] = (theta_opt[i] + V20_ELO_ANCHOR, ci_full[i] if ci_full[i] > 0 else None)
    return elo_dict


# ── Per-engine stats ──────────────────────────────────────────────────────────

def build_stats(games):
    stats = {v: {"w": 0, "d": 0, "l": 0, "score": 0.0, "games": 0} for v in VERSIONS}
    for g in games:
        try:
            wv = g["white"].lstrip("v")
            bv = g["black"].lstrip("v")
        except (ValueError, AttributeError):
            continue
        r = float(g["result"])
        for v, score in [(wv, r), (bv, 1.0 - r)]:
            if v not in stats:
                continue
            stats[v]["games"] += 1
            stats[v]["score"] += score
            if score == 1.0:   stats[v]["w"] += 1
            elif score == 0.5: stats[v]["d"] += 1
            else:              stats[v]["l"] += 1
    return stats


# ── Elo plot ──────────────────────────────────────────────────────────────────

def generate_elo_plot(elo_dict, path="/tmp/elo_progression.png"):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        versions = sorted(elo_dict.keys())
        elos = [elo_dict[v][0] for v in versions]
        cis  = [elo_dict[v][1] if elo_dict[v][1] is not None else 0.0 for v in versions]

        fig, ax = plt.subplots(figsize=(13, 6))
        ax.errorbar(versions, elos, yerr=cis, fmt="o-", color="#1976d2",
                    ecolor="#90caf9", capsize=5, linewidth=1.8, markersize=7)
        ax.axhline(V20_ELO_ANCHOR, color="green", linestyle="--", linewidth=1,
                   label=f"v2.0 anchor = {V20_ELO_ANCHOR}")
        for v, e in zip(versions, elos):
            ax.annotate(f"{e:.0f}", (v, e), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8)
        ax.set_xlabel("Engine Version", fontsize=11)
        ax.set_ylabel("Elo", fontsize=11)
        ax.set_title("Chess Engine Round-Robin — Elo Progression (v1.0–v2.1)", fontsize=13)
        ax.set_xticks(versions)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(path, dpi=100)
        plt.close(fig)
        return path
    except Exception as e:
        print(f"Plot failed: {e}", flush=True)
        return None


# ── Email ─────────────────────────────────────────────────────────────────────

def build_email_html(games, elo_dict, stats, config_summary, plot_path=None):
    rows_sorted = sorted(elo_dict.keys(), key=lambda v: elo_dict[v][0], reverse=True)

    plot_img_tag = ""
    if plot_path and os.path.isfile(plot_path):
        with open(plot_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        plot_img_tag = (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="max-width:100%;margin:16px 0;" alt="Elo Progression">'
        )

    lines = ['<html><body style="font-family:monospace;font-size:13px;">']
    lines.append('<h2 style="margin-bottom:6px">Chess Engine Round-Robin — Final Results</h2>')

    # Config table
    lines.append('<table style="margin-bottom:16px;border-spacing:6px">')
    for k, v in config_summary.items():
        lines.append(f'<tr><td><b>{k}:</b></td><td>{v}</td></tr>')
    lines.append('</table>')

    # Rankings table
    lines.append('''
<h3>Elo Rankings</h3>
<table border="1" cellpadding="5" cellspacing="0"
       style="border-collapse:collapse;margin-bottom:16px">
  <tr style="background:#e0e0e0">
    <th>Rank</th><th>Engine</th><th>Elo</th><th>±95% CI</th>
    <th>Games</th><th>W</th><th>D</th><th>L</th><th>Score%</th>
  </tr>''')

    for rank, v in enumerate(rows_sorted, 1):
        elo, ci = elo_dict[v]
        s = stats.get(v, {})
        g = s.get("games", 0)
        w = s.get("w", 0)
        d = s.get("d", 0)
        l = s.get("l", 0)
        sc = s.get("score", 0.0)
        pct = f"{100*sc/g:.1f}%" if g > 0 else "—"
        ci_str = f"±{ci:.0f}" if ci is not None else "—"
        bg = "#f5f5f5" if rank % 2 == 0 else "#ffffff"
        anchor = " ⚓" if v == "2.0" else ""
        lines.append(
            f'  <tr style="background:{bg}">'
            f'<td style="text-align:right">{rank}</td>'
            f'<td><b>v{v}{anchor}</b></td>'
            f'<td style="text-align:right">{elo:.0f}</td>'
            f'<td style="text-align:right">{ci_str}</td>'
            f'<td style="text-align:right">{g}</td>'
            f'<td style="text-align:right">{w}</td>'
            f'<td style="text-align:right">{d}</td>'
            f'<td style="text-align:right">{l}</td>'
            f'<td style="text-align:right">{pct}</td></tr>'
        )
    lines.append('</table>')

    if plot_img_tag:
        lines.append('<h3>Elo Progression</h3>')
        lines.append(plot_img_tag)

    lines.append('</body></html>')
    return "\n".join(lines)


def send_results_email(games, elo_dict, stats, config_summary, plot_path):
    sender   = os.environ.get("SUMMARY_EMAIL_SENDER", "")
    password = os.environ.get("SUMMARY_EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        print("WARNING: email credentials not set — skipping email.", flush=True)
        return

    n = len(games)
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    subject = f"Chess Engine Round-Robin — {n} games, {date_str}"
    html_body = build_email_html(games, elo_dict, stats, config_summary, plot_path)

    outer = MIMEMultipart("mixed")
    outer["Subject"] = subject
    outer["From"] = sender
    outer["To"] = RECIPIENT
    outer.attach(MIMEText(html_body, "html"))

    if plot_path and os.path.isfile(plot_path):
        with open(plot_path, "rb") as f:
            img = MIMEImage(f.read(), name="elo_progression.png")
        img.add_header("Content-Disposition", "attachment", filename="elo_progression.png")
        outer.attach(img)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, RECIPIENT, outer.as_string())
        print(f"Email sent: {subject}", flush=True)
    except Exception as e:
        print(f"Email failed: {e}", flush=True)


# ── Report mode ───────────────────────────────────────────────────────────────

def print_report(log_path):
    games = load_games(log_path)
    if not games:
        print(f"No games found in {log_path}", flush=True)
        return
    elo_dict = compute_elo(games)
    stats = build_stats(games)
    if elo_dict is None:
        print("scipy not available — cannot compute Elo", flush=True)
        return
    rows = sorted(elo_dict.keys(), key=lambda v: elo_dict[v][0], reverse=True)
    print(f"\n{'='*70}")
    print(f"  Round-Robin Standings — {len(games)} games")
    print(f"{'='*70}")
    print(f"{'Rank':>4}  {'Engine':>8}  {'Elo':>6}  {'±CI':>6}  "
          f"{'Games':>6}  {'W':>5}  {'D':>5}  {'L':>5}  {'Score%':>7}")
    print(f"{'-'*70}")
    for rank, v in enumerate(rows, 1):
        elo, ci = elo_dict[v]
        s = stats.get(v, {})
        g = s.get("games", 0)
        w = s.get("w", 0)
        d = s.get("d", 0)
        l = s.get("l", 0)
        sc = s.get("score", 0.0)
        pct = f"{100*sc/g:.1f}%" if g > 0 else "—"
        ci_str = f"±{ci:.0f}" if ci is not None else "—"
        anchor = " *" if v == "2.0" else ""
        print(f"{rank:>4}  v{v:<7}{anchor}  {elo:>6.0f}  {ci_str:>6}  "
              f"{g:>6}  {w:>5}  {d:>5}  {l:>5}  {pct:>7}")
    print(f"{'='*70}")
    print(f"  * v2.0 Elo anchored at {V20_ELO_ANCHOR}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Round-robin all-versions tournament")
    parser.add_argument("--engine-dir", default=os.path.expanduser("~/c_rewrite"),
                        dest="engine_dir")
    parser.add_argument("--movetime",   type=int, default=100)
    parser.add_argument("--end-time",   default="08:00", dest="end_time")
    parser.add_argument("--log",        default="/tmp/rr_allversions.jsonl")
    parser.add_argument("--hash",       type=int, default=8)
    parser.add_argument("--seed",       type=int, default=42)
    parser.add_argument("--test-email", action="store_true", dest="test_email")
    parser.add_argument("--report",     type=str, default=None,
                        help="Print standings from JSONL and exit")
    args = parser.parse_args()

    if args.report:
        print_report(args.report)
        return

    if args.test_email:
        print("Generating dummy data for test email...", flush=True)
        rng_d = random.Random(99)
        dummy_elo = {}
        for i, v in enumerate(VERSIONS):
            if v == "2.0":
                dummy_elo[v] = (float(V20_ELO_ANCHOR), 0.0)
            else:
                base = 800 + i * 110 + rng_d.randint(-20, 20)
                dummy_elo[v] = (float(base), float(rng_d.randint(8, 15)))
        dummy_stats = {
            v: {"w": 80, "d": 30, "l": 80, "score": 95.0, "games": 190}
            for v in VERSIONS
        }
        config = {
            "Engines": f"v{VERSIONS[0]}–v{VERSIONS[-1]} ({len(VERSIONS)} engines)",
            "TC": "movetime 100ms",
            "Total games": "TEST MODE",
            "Duration": "TEST",
            "v2.0 Elo anchor": V20_ELO_ANCHOR,
        }
        plot_path = generate_elo_plot(dummy_elo, "/tmp/elo_test.png")
        send_results_email([], dummy_elo, dummy_stats, config, plot_path)
        return

    # Parse end time (local)
    now = datetime.datetime.now()
    hh, mm = map(int, args.end_time.split(":"))
    end_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if end_dt <= now:
        end_dt += datetime.timedelta(days=1)
    print(f"Tournament will run until {end_dt.strftime('%Y-%m-%d %H:%M')} (local)", flush=True)

    # Verify binaries
    engine_paths = [os.path.join(args.engine_dir, f"v{v}_engine") for v in VERSIONS]
    missing = [p for p in engine_paths if not os.path.isfile(p)]
    if missing:
        print("ERROR: Missing engine binaries:", flush=True)
        for p in missing:
            print(f"  {p}", flush=True)
        sys.exit(1)

    # Start all engines
    print(f"Starting {len(VERSIONS)} engines (Hash={args.hash}MB each)...", flush=True)
    engines = []
    for path, v in zip(engine_paths, VERSIONS):
        name = f"v{v}"
        try:
            e = Engine(path, name, hash_mb=args.hash)
            engines.append(e)
            print(f"  {name}: OK", flush=True)
        except Exception as ex:
            print(f"  ERROR starting {name}: {ex}", flush=True)
            for started in engines:
                started.quit()
            sys.exit(1)

    rng = random.Random(args.seed)
    log_path = args.log
    start_time = time.time()

    # Resume support: count existing games
    existing = load_games(log_path)
    game_count = len(existing)
    if game_count:
        print(f"Resuming: {game_count} existing games found in {log_path}", flush=True)

    print(f"\nTournament started — JSONL: {log_path}", flush=True)
    print(f"{'Game':>6}  {'White':>6}  {'Black':>6}  {'Result':>9}  "
          f"{'Elapsed':>8}  {'Rate':>9}", flush=True)
    print("-" * 60, flush=True)

    try:
        while datetime.datetime.now() < end_dt:
            i, j = rng.sample(range(len(VERSIONS)), 2)
            fen = generate_opening(rng, plies=10)

            for w_idx, b_idx in [(i, j), (j, i)]:
                if datetime.datetime.now() >= end_dt:
                    break

                white_e = engines[w_idx]
                black_e = engines[b_idx]

                result = play_game(white_e, black_e, fen, args.movetime)
                append_game(log_path, white_e.name, black_e.name, result, fen)
                game_count += 1

                white_e.new_game()
                black_e.new_game()

                elapsed = time.time() - start_time
                rate = game_count / elapsed * 3600 if elapsed > 0 else 0
                result_str = {1.0: "1-0", 0.5: "1/2-1/2", 0.0: "0-1"}.get(result, "?")
                print(f"{game_count:>6}  {white_e.name:>6}  {black_e.name:>6}  "
                      f"{result_str:>9}  {elapsed/3600:>6.2f}h  {rate:>7.0f}/hr",
                      flush=True)

    except KeyboardInterrupt:
        print("\nInterrupted by user.", flush=True)

    # Final results
    print(f"\nTournament ended. Total games: {game_count}", flush=True)
    all_games = load_games(log_path)
    elo_dict = compute_elo(all_games)
    stats = build_stats(all_games)

    if elo_dict:
        print_report(log_path)
        plot_path = generate_elo_plot(elo_dict, "/tmp/elo_progression.png")
        elapsed_total = time.time() - start_time
        config = {
            "Engines": f"v{VERSIONS[0]}–v{VERSIONS[-1]} ({len(VERSIONS)} engines)",
            "TC": f"movetime {args.movetime}ms",
            "Total games": game_count,
            "Duration": f"{elapsed_total/3600:.2f}h",
            "JSONL": log_path,
            "v2.0 Elo anchor": V20_ELO_ANCHOR,
        }
        send_results_email(all_games, elo_dict, stats, config, plot_path)
    else:
        print("Could not compute Elo (scipy unavailable or no games).", flush=True)

    for e in engines:
        e.quit()
    print("Done.", flush=True)


if __name__ == "__main__":
    main()
