#!/usr/bin/env python3
"""
Tournament: v17_engine vs v16_engine
Plays N games with alternating colors using go movetime UCI protocol.
Uses python-chess for move validation and game-end detection.
"""

import subprocess
import chess
import sys
import time

ENGINE_DIR = "/Users/tomberkley/Desktop/CodeProjects/Chess/c_rewrite"

MOVETIME_MS = 100   # ms per move — fast for 50 games
MAX_MOVES   = 200   # cap game length (draw)

OPENINGS = [
    # Start from a variety of positions for diversity
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
    ["e2e4", "e7e5", "f2f4"],                   # 16. King's Gambit
    ["d2d4", "d7d5", "c2c4", "e7e6"],           # 17. QGD
    ["e2e4", "e7e5", "g1f3", "b8c6", "b1c3"],  # 18. Three Knights
    ["e2e4", "e7e5", "g1f3", "g8f6"],           # 19. Petrov
    ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4"],  # 20. Scotch
    ["e2e4", "e7e5", "g1f3", "b8c6",
     "f1b5", "a7a6", "b5a4"],                  # 21. Ruy Lopez main
    ["e2e4", "c7c5", "g1f3", "d7d6"],           # 22. Sicilian Najdorf setup
    ["e2e4", "c7c5", "b1c3"],                   # 23. Sicilian closed
    ["d2d4", "g8f6", "c2c4", "e7e6",
     "g1f3", "d7d5"],                           # 24. QGD
    ["e2e4", "e7e5", "f1c4", "f8c5"],           # 25. Giuoco Piano
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
    # UCI handshake
    p.stdin.write("uci\n")
    p.stdin.flush()
    while True:
        line = p.stdout.readline().strip()
        if line == "uciok":
            break
    p.stdin.write("isready\n")
    p.stdin.flush()
    while True:
        line = p.stdout.readline().strip()
        if line == "readyok":
            break
    return p


def get_best_move(engine, fen, movetime_ms):
    engine.stdin.write(f"position fen {fen}\n")
    engine.stdin.write(f"go movetime {movetime_ms}\n")
    engine.stdin.flush()
    while True:
        line = engine.stdout.readline().strip()
        if line.startswith("bestmove"):
            parts = line.split()
            mv = parts[1] if len(parts) > 1 else None
            return mv if mv != "(none)" else None


def play_game(white_engine, black_engine, opening_moves):
    board = chess.Board()

    # Apply opening moves
    for uci in opening_moves:
        try:
            move = chess.Move.from_uci(uci)
            if move in board.legal_moves:
                board.push(move)
            else:
                break
        except Exception:
            break

    for _ in range(MAX_MOVES):
        if board.is_game_over():
            break

        engine = white_engine if board.turn == chess.WHITE else black_engine
        fen = board.fen()
        uci_move = get_best_move(engine, fen, MOVETIME_MS)

        if uci_move is None:
            # Engine resigned or no move
            break

        try:
            move = chess.Move.from_uci(uci_move)
            if move not in board.legal_moves:
                # Illegal move — count as loss for that engine
                return "white" if board.turn == chess.BLACK else "black"
            board.push(move)
        except Exception:
            break

    if board.is_checkmate():
        return "black" if board.turn == chess.WHITE else "white"
    elif board.is_stalemate() or board.is_insufficient_material() or \
         board.is_fifty_moves() or board.is_repetition(3):
        return "draw"
    else:
        return "draw"  # max moves reached


def main():
    n_games = 50
    print(f"Tournament: v17_engine vs v16_engine")
    print(f"Games: {n_games} | Movetime: {MOVETIME_MS}ms/move | Max moves: {MAX_MOVES}")
    print("-" * 60)

    v17_wins = 0
    v16_wins = 0
    draws = 0

    # We play pairs: v17 as white, v16 as black; then swap
    # Total pairs = n_games // 2, each opening repeated once per color
    pairs = n_games // 2  # 25 pairs → 50 games

    start_total = time.time()

    for pair_idx in range(pairs):
        opening = OPENINGS[pair_idx % len(OPENINGS)]

        for v17_color in [chess.WHITE, chess.BLACK]:
            # Start fresh engines for each game (avoids state leakage)
            e17 = start_engine("v17_engine")
            e16 = start_engine("v16_engine")

            if v17_color == chess.WHITE:
                result = play_game(e17, e16, opening)
                winner = "v17" if result == "white" else ("v16" if result == "black" else "draw")
            else:
                result = play_game(e16, e17, opening)
                winner = "v17" if result == "black" else ("v16" if result == "white" else "draw")

            e17.stdin.write("quit\n"); e17.stdin.flush()
            e16.stdin.write("quit\n"); e16.stdin.flush()
            e17.wait(timeout=2)
            e16.wait(timeout=2)

            game_num = pair_idx * 2 + (0 if v17_color == chess.WHITE else 1) + 1
            color_str = "v17=W" if v17_color == chess.WHITE else "v17=B"

            if winner == "v17":
                v17_wins += 1
                outcome = "v17 wins"
            elif winner == "v16":
                v16_wins += 1
                outcome = "v16 wins"
            else:
                draws += 1
                outcome = "Draw"

            print(f"Game {game_num:3d}/{n_games} [{color_str}] opening={pair_idx % len(OPENINGS):2d}: {outcome}")
            sys.stdout.flush()

    elapsed = time.time() - start_total
    total_games = v17_wins + v16_wins + draws

    print("\n" + "=" * 60)
    print(f"RESULTS after {total_games} games ({elapsed:.1f}s)")
    print(f"  v17 wins:  {v17_wins:3d}  ({100*v17_wins/total_games:.1f}%)")
    print(f"  v16 wins:  {v16_wins:3d}  ({100*v16_wins/total_games:.1f}%)")
    print(f"  Draws:     {draws:3d}  ({100*draws/total_games:.1f}%)")
    score = (v17_wins + 0.5 * draws) / total_games
    print(f"  v17 score: {score:.3f}  ({score*100:.1f}%)")

    # Rough Elo estimate using logistic model
    if score > 0 and score < 1:
        import math
        elo_diff = -400 * math.log10(1/score - 1)
        print(f"  Est. Elo diff: {elo_diff:+.0f} cp (v17 vs v16)")
    print("=" * 60)


if __name__ == "__main__":
    main()
