"""Quick benchmark: CPython vs PyPy on v11 search."""
import sys, os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chess
from bots.time_managed_v11 import get_best_move, get_game_phase

board = chess.Board()
# Play a few moves to get a middlegame position
moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6", "e1g1", "f8e7"]
for m in moves:
    board.push(chess.Move.from_uci(m))

print(f"Python: {sys.implementation.name} {sys.version}")
print(f"FEN: {board.fen()}")
print(f"Phase: {get_game_phase(board):.2f}")

for d in [5, 6, 7]:
    start = time.time()
    move = get_best_move(board, depth=d)
    elapsed = time.time() - start
    print(f"Depth {d}: {move} in {elapsed:.2f}s")
