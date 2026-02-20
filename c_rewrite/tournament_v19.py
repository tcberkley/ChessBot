#!/usr/bin/env python3
"""
Tournament: v19_engine vs v18_engine
Plays N games with alternating colors using go movetime UCI protocol.
Uses python-chess for move validation and game-end detection.
"""

import subprocess
import chess
import sys
import time

ENGINE_DIR = "/Users/tomberkley/Desktop/CodeProjects/Chess/c_rewrite"

MOVETIME_MS = 100   # ms per move
MAX_MOVES   = 200   # cap game length (draw)

OPENINGS = [
    [],                                         # 1. (start)
    ["e2e4", "e7e5"],                           # 2. Open game
    ["d2d4", "d7d5"],                           # 3. Closed game
    ["e2e4", "c7c5"],                           # 4. Sicilian
    ["e2e4", "e7e6"],                           # 5. French
    ["d2d4", "g8f6", "c2c4", "g7g6"],           # 6. King's Indian
    ["e2e4", "e7e5", "g1f3", "b8c6"],           # 7. Ruy Lopez
    ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],  # 8. Italian
    ["d2d4", "d7d5", "c2c4"],                   # 9. Queen's Gambit
    ["e2e4", "c7c6"],                           # 10. Caro-Kann
    ["g1f3", "d7d5", "g2g3"],                   # 11. King's Fianchetto
    ["c2c4"],                                   # 12. English
    ["e2e4", "g7g6"],                           # 13. Modern
    ["d2d4", "f7f5"],                           # 14. Dutch
    ["e2e4", "d7d6"],                           # 15. Pirc
]


def start_engine(name):
    path = f"{ENGINE_DIR}/{name}"
    p = subprocess.Popen(
        [path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    # Init UCI
    p.stdin.write("uci\n")
    p.stdin.flush()
    for _ in range(50):
        line = p.stdout.readline()
        if "uciok" in line:
            break
    p.stdin.write("isready\n")
    p.stdin.flush()
    for _ in range(50):
        line = p.stdout.readline()
        if "readyok" in line:
            break
    return p


def get_best_move(engine, fen, movetime_ms):
    engine.stdin.write(f"position fen {fen}\n")
    engine.stdin.flush()
    engine.stdin.write(f"go movetime {movetime_ms}\n")
    engine.stdin.flush()
    for _ in range(500):
        line = engine.stdout.readline()
        if line.startswith("bestmove"):
            parts = line.strip().split()
            if len(parts) >= 2 and parts[1] != "(none)" and parts[1] != "0000":
                return parts[1]
            return None
    return None


def play_game(engine_white, engine_black, opening_moves):
    """Returns 'white', 'black', or 'draw'."""
    board = chess.Board()
    for m in opening_moves:
        try:
            board.push_uci(m)
        except Exception:
            break

    for move_num in range(MAX_MOVES):
        if board.is_game_over():
            break

        engine = engine_white if board.turn == chess.WHITE else engine_black
        fen = board.fen()
        move_str = get_best_move(engine, fen, MOVETIME_MS)

        if move_str is None:
            # Engine failed to return a move — opponent wins
            return "black" if board.turn == chess.WHITE else "white"

        try:
            move = chess.Move.from_uci(move_str)
            if move not in board.legal_moves:
                return "black" if board.turn == chess.WHITE else "white"
            board.push(move)
        except Exception:
            return "black" if board.turn == chess.WHITE else "white"

    result = board.result()
    if result == "1-0":
        return "white"
    elif result == "0-1":
        return "black"
    else:
        return "draw"


def main():
    n_games = 30
    print(f"Tournament: v19_engine vs v18_engine")
    print(f"Games: {n_games} | Movetime: {MOVETIME_MS}ms/move | Max moves: {MAX_MOVES}")
    print("-" * 60)

    v19_wins = 0
    v18_wins = 0
    draws = 0

    pairs = n_games // 2  # 15 pairs → 30 games

    start_total = time.time()

    for pair_idx in range(pairs):
        opening = OPENINGS[pair_idx % len(OPENINGS)]

        for v19_is_white in [True, False]:
            # Fresh engines each game to avoid state leakage
            e19 = start_engine("v19_engine")
            e18 = start_engine("v18_engine")

            if v19_is_white:
                result = play_game(e19, e18, opening)
                if result == "white":
                    winner = "v19"
                elif result == "black":
                    winner = "v18"
                else:
                    winner = "draw"
            else:
                result = play_game(e18, e19, opening)
                if result == "black":
                    winner = "v19"
                elif result == "white":
                    winner = "v18"
                else:
                    winner = "draw"

            try:
                e19.stdin.write("quit\n"); e19.stdin.flush()
                e18.stdin.write("quit\n"); e18.stdin.flush()
                e19.wait(timeout=2)
                e18.wait(timeout=2)
            except Exception:
                pass

            game_num = pair_idx * 2 + (1 if v19_is_white else 2)
            color_str = "v19=W" if v19_is_white else "v19=B"

            if winner == "v19":
                v19_wins += 1
                outcome = "v19 wins"
            elif winner == "v18":
                v18_wins += 1
                outcome = "v18 wins"
            else:
                draws += 1
                outcome = "Draw"

            print(f"Game {game_num:3d}/{n_games} [{color_str}] opening={pair_idx % len(OPENINGS):2d}: {outcome}")
            sys.stdout.flush()

    elapsed = time.time() - start_total
    total_games = v19_wins + v18_wins + draws

    print("\n" + "=" * 60)
    print(f"RESULTS after {total_games} games ({elapsed:.1f}s)")
    print(f"  v19 wins:  {v19_wins:3d}  ({100*v19_wins/total_games:.1f}%)")
    print(f"  v18 wins:  {v18_wins:3d}  ({100*v18_wins/total_games:.1f}%)")
    print(f"  Draws:     {draws:3d}  ({100*draws/total_games:.1f}%)")
    score = (v19_wins + 0.5 * draws) / total_games
    print(f"  v19 score: {score:.3f}  ({score*100:.1f}%)")

    if score > 0 and score < 1:
        import math
        elo_diff = -400 * math.log10(1/score - 1)
        print(f"  Est. Elo diff: {elo_diff:+.0f} Elo (v19 vs v18)")
    print("=" * 60)


if __name__ == "__main__":
    main()
