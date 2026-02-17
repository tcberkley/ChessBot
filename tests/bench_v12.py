"""Benchmark v11 vs v12."""
import sys, os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import chess

# Test on a middlegame position
board = chess.Board()
moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6", "e1g1", "f8e7"]
for m in moves:
    board.push(chess.Move.from_uci(m))

print(f"FEN: {board.fen()}")

# V11
from bots import time_managed_v11 as v11
print("\n--- V11 ---")
for d in [5, 6, 7]:
    v11.transposition_table.clear()
    v11.killer_moves.clear()
    v11.history_table.clear()
    start = time.time()
    move = v11.get_best_move(board.copy(), depth=d)
    elapsed = time.time() - start
    print(f"  Depth {d}: {move} in {elapsed:.2f}s ({v11._node_count} nodes)")

# V12
from bots import v12
print("\n--- V12 ---")
for d in [5, 6, 7]:
    v12.transposition_table.clear()
    v12.killer_moves.clear()
    v12.history_table.clear()
    start = time.time()
    move = v12.get_best_move(board.copy(), depth=d)
    elapsed = time.time() - start
    print(f"  Depth {d}: {move} in {elapsed:.2f}s ({v12._node_count} nodes)")

# Test on a tactical position (mate in 2)
print("\n--- Tactical position (mate threats) ---")
board2 = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4")
print(f"FEN: {board2.fen()}")
v12.transposition_table.clear()
start = time.time()
move = v12.get_best_move(board2.copy(), depth=5)
elapsed = time.time() - start
print(f"  V12 d5: {move} in {elapsed:.2f}s (should find Qxf7#)")

# Test stalemate detection
print("\n--- Stalemate detection ---")
board3 = chess.Board("k7/8/1K6/8/8/8/8/1Q6 w - - 0 1")
print(f"FEN: {board3.fen()}")
v12.transposition_table.clear()
start = time.time()
move = v12.get_best_move(board3.copy(), depth=5)
elapsed = time.time() - start
print(f"  V12 d5: {move} in {elapsed:.2f}s (should NOT play Qa2 stalemate)")
