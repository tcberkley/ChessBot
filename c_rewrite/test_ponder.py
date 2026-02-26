#!/usr/bin/env python3
"""
test_ponder.py — Automated UCI ponder tests for v21_engine

Verifies that pondering produces legal moves and the ponder cycle works.

Suite 1: Every ponder move in "bestmove X ponder Y" is legal after X.
Suite 2: Full go-ponder → ponderhit cycle yields a valid bestmove.
Suite 3: Full go-ponder → stop cycle yields a valid bestmove.
Suite 4: TT collision stress — same positions run repeatedly without clearing
         TT, verifying no illegal moves appear even under heavy hash reuse.

Usage:
    python3 c_rewrite/test_ponder.py [path/to/v21_engine]

Exit code: 0 if all tests pass, 1 if any failure.
"""

import os
import queue
import subprocess
import sys
import threading
import time

import chess

ENGINE_PATH = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.path.join(os.path.dirname(os.path.abspath(__file__)), "v21_engine")
)

# ── Positions ─────────────────────────────────────────────────────────────────
# 30 diverse positions: openings, middlegames, endgames.
POSITIONS = [
    # Openings
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",           # startpos
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",        # 1.e4
    "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",     # 1.e4 e5
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2",     # Sicilian
    "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",      # French
    "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3",  # Italian
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",  # Ruy Lopez
    "rnbqkb1r/ppp1pppp/3p4/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq d3 0 3",     # Pirc
    "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq d6 0 2",     # Closed
    "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2",      # 1.d4 Nf6
    # Middlegames
    "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 7",
    "r1bqk2r/pp2bppp/2n1pn2/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R w KQkq d6 0 6",
    "r1bqr1k1/pp3ppp/2n2n2/2ppP3/3P4/2P2N2/PP3PPP/R1BQ1RK1 w - - 0 10",
    "r2q1rk1/pb1nbppp/1p2pn2/2pp4/3P1B2/2NBPN2/PPP2PPP/R2Q1RK1 w - - 0 9",
    "3r1rk1/pp2qppp/2n1pn2/2b5/2B5/2N1PN2/PPQ2PPP/3R1RK1 w - - 0 13",
    "r4rk1/pp1qppbp/2np1np1/8/3NP3/2N1BP2/PPP3PP/R2QR1K1 b - - 0 11",
    "r1bq1rk1/pp3ppp/2n1pn2/3p4/1bPP4/2NBPN2/PP3PPP/R1BQK2R b KQkq - 0 7",
    "2rqr1k1/pb1nbppp/1p1ppn2/8/2PP4/1PN1PN2/PBQ1BPPP/3R1RK1 w - - 2 12",
    "r1b2rk1/pp1nqppp/2p1pn2/3p4/2PP4/2N1PN2/PPQ2PPP/R1B2RK1 w - - 0 10",
    "r2q1rk1/1pp2ppp/p1nb1n2/4p3/2P1P3/2NP1N2/PP3PPP/R1BQ1RK1 b - - 0 9",
    # Tactical
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r2q1rk1/pp1bppbp/3p1np1/n7/3NP3/2N1BP2/PPPQ2PP/R3KB1R w KQ - 4 10",
    "r1b1k2r/pppp1ppp/2n2q2/2b5/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 0 7",
    # Endgames (all have both kings)
    "8/8/4k3/4p3/4P3/4K3/8/8 w - - 0 1",
    "8/8/3k4/8/3K4/8/5P2/8 w - - 0 1",
    "8/8/k7/8/K7/8/8/1R6 w - - 0 1",
    "4k3/8/8/8/8/8/8/4K2R w K - 0 1",
    "5k2/8/5K2/8/5P2/8/8/8 w - - 0 1",
    "3k4/3p4/8/8/8/8/3P4/3K4 w - - 0 1",
    "8/8/3k4/8/3K4/8/4P3/8 w - - 0 1",
]

# Positions for TT collision stress — complex tactical positions run without
# clearing TT between repeats to maximise hash collision probability.
BUG_POSITIONS = [
    # Complex middlegames with many pieces — lots of TT entries, collision-prone
    "r1bqkb1r/pp3ppp/2np1n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 0 6",
    "r2qk2r/ppp1bppp/2npbn2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQK2R w KQkq - 2 7",
    "r1bq1rk1/ppp2ppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 b - - 2 7",
    "r1b2rk1/ppp1qppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQR1K1 w - - 4 9",
    "r1bqr1k1/ppp2ppp/2np1n2/4p3/2B1P3/2NP1N2/PPP2PPP/R1BQ1RK1 w - - 0 9",
]


# ── Engine wrapper ─────────────────────────────────────────────────────────────

class Engine:
    """Thin subprocess wrapper for raw UCI communication.

    A background reader thread pushes stdout lines into a queue so we can do
    non-blocking reads — necessary during ponder cycles where we send commands
    while the engine is also producing output.
    """

    def __init__(self, path):
        self.proc = subprocess.Popen(
            [path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._q = queue.Queue()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        for line in self.proc.stdout:
            self._q.put(line.rstrip())
        self._q.put(None)  # EOF sentinel

    def send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def readline(self, timeout=8.0):
        """Return the next output line, or None on timeout/EOF."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_bestmove(self, timeout=10.0):
        """Read lines until 'bestmove', return (bm_uci, ponder_uci_or_None).

        Returns (None, None) on timeout, crash, or if the engine sends 0000/(none).
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.readline(timeout=max(0.1, deadline - time.time()))
            if line is None:
                break
            if line.startswith("bestmove"):
                parts = line.split()
                bm = parts[1] if len(parts) > 1 else None
                if bm in ("(none)", "0000", None):
                    return None, None
                pm = parts[3] if len(parts) >= 4 and parts[2] == "ponder" else None
                return bm, pm
        return None, None

    def uci_init(self):
        """Send UCI handshake; wait for readyok."""
        self.send("uci")
        self._wait_for("uciok", timeout=5.0)
        self.send("isready")
        self._wait_for("readyok", timeout=5.0)

    def new_game(self):
        """Send ucinewgame + isready and wait for readyok."""
        self.send("ucinewgame")
        self.send("isready")
        self._wait_for("readyok", timeout=5.0)

    def _wait_for(self, token, timeout=5.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.readline(timeout=max(0.1, deadline - time.time()))
            if line and token in line:
                return
        # Not a fatal error — engine may already have sent it

    def close(self):
        try:
            self.send("quit")
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_bestmove(eng, fen, movetime_ms=200):
    """Send position + go movetime, return (bm_uci, ponder_uci_or_None)."""
    eng.send(f"position fen {fen}")
    eng.send(f"go movetime {movetime_ms}")
    return eng.wait_bestmove(timeout=movetime_ms / 1000.0 + 6.0)


def is_legal(board, uci):
    """Return True if uci is a legal move on board."""
    try:
        move = chess.Move.from_uci(uci)
        return move in board.legal_moves
    except Exception:
        return False


# ── Suite 1: Ponder move legality ─────────────────────────────────────────────

def suite1_ponder_legality(eng, positions):
    """Every 'bestmove X ponder Y' must have Y legal in the position after X."""
    passed = skipped = 0
    failures = []

    print("Suite 1 — Ponder move legality:")
    for i, fen in enumerate(positions):
        eng.new_game()
        bm, pm = get_bestmove(eng, fen, movetime_ms=300)

        if bm is None:
            failures.append((fen, "No bestmove returned"))
            print(f"  pos {i+1:2d}: FAIL — no bestmove returned")
            continue

        board = chess.Board(fen)
        if not is_legal(board, bm):
            failures.append((fen, f"bestmove {bm!r} is illegal"))
            print(f"  pos {i+1:2d}: FAIL — bestmove {bm!r} is illegal")
            continue

        if pm is None:
            # Acceptable: engine chose not to output a ponder move (short PV)
            skipped += 1
            passed += 1
            print(f"  pos {i+1:2d}: bm={bm} (no ponder) [ok]")
            continue

        board.push(chess.Move.from_uci(bm))
        if not is_legal(board, pm):
            failures.append((fen, f"ponder {pm!r} illegal after bestmove {bm!r}"))
            print(f"  pos {i+1:2d}: FAIL — ponder {pm!r} illegal after {bm!r}")
            continue

        passed += 1
        print(f"  pos {i+1:2d}: bm={bm} ponder={pm} [ok]")

    suffix = f"  ({skipped} with no ponder move)" if skipped else ""
    print(f"  Result: {passed}/{len(positions)} passed{suffix}")
    return passed, len(positions), failures


# ── Suite 2: Ponder cycle — ponderhit ─────────────────────────────────────────

def suite2_ponder_hit(eng, positions):
    """go ponder → ponderhit must yield a legal bestmove in the ponder position."""
    passed = skipped = 0
    failures = []

    print("Suite 2 — Ponder cycle (ponderhit):")
    for i, fen in enumerate(positions):
        # First get a predicted ponder move
        eng.new_game()
        bm, pm = get_bestmove(eng, fen, movetime_ms=200)

        if bm is None:
            failures.append((fen, "Initial search returned no bestmove"))
            print(f"  pos {i+1:2d}: FAIL — no initial bestmove")
            continue

        if pm is None:
            skipped += 1
            passed += 1
            print(f"  pos {i+1:2d}: SKIP — no ponder move from initial search")
            continue

        board = chess.Board(fen)
        if not is_legal(board, bm):
            failures.append((fen, f"Initial bestmove {bm!r} illegal — can't set up cycle"))
            skipped += 1
            continue

        # Set up ponder position and start pondering
        eng.send(f"position fen {fen} moves {bm}")
        eng.send("go ponder")
        time.sleep(0.4)    # let ponder search run briefly
        eng.send("ponderhit")

        # Engine outputs bestmove from the ponder search (ponder position)
        bm2, pm2 = eng.wait_bestmove(timeout=8.0)

        if bm2 is None:
            failures.append((fen, f"No bestmove after ponderhit (initial: {bm} / {pm})"))
            print(f"  pos {i+1:2d}: FAIL — no bestmove after ponderhit")
            continue

        # bm2 must be legal in the ponder position (after bm was played)
        ponder_board = chess.Board(fen)
        ponder_board.push(chess.Move.from_uci(bm))
        if not is_legal(ponder_board, bm2):
            failures.append((fen, f"After ponderhit, bestmove {bm2!r} illegal in ponder pos"))
            print(f"  pos {i+1:2d}: FAIL — {bm2!r} illegal after ponderhit")
            continue

        # If a new ponder move returned, check it too
        if pm2 is not None:
            ponder_board.push(chess.Move.from_uci(bm2))
            if not is_legal(ponder_board, pm2):
                failures.append((fen, f"After ponderhit, ponder {pm2!r} illegal after {bm2!r}"))
                print(f"  pos {i+1:2d}: FAIL — ponder {pm2!r} illegal after ponderhit+{bm2!r}")
                continue

        passed += 1
        print(f"  pos {i+1:2d}: {bm} → ponder → hit → {bm2} [ok]")

    suffix = f"  ({skipped} skipped, no ponder move)" if skipped else ""
    print(f"  Result: {passed}/{len(positions)} passed{suffix}")
    return passed, len(positions), failures


# ── Suite 3: Ponder cycle — stop ──────────────────────────────────────────────

def suite3_ponder_stop(eng, positions):
    """go ponder → stop must yield a legal bestmove and not hang."""
    passed = skipped = 0
    failures = []

    print("Suite 3 — Ponder cycle (stop):")
    for i, fen in enumerate(positions):
        eng.new_game()
        bm, pm = get_bestmove(eng, fen, movetime_ms=200)

        if bm is None:
            failures.append((fen, "Initial search returned no bestmove"))
            print(f"  pos {i+1:2d}: FAIL — no initial bestmove")
            continue

        if pm is None:
            skipped += 1
            passed += 1
            print(f"  pos {i+1:2d}: SKIP — no ponder move from initial search")
            continue

        board = chess.Board(fen)
        if not is_legal(board, bm):
            failures.append((fen, f"Initial bestmove {bm!r} illegal"))
            skipped += 1
            continue

        eng.send(f"position fen {fen} moves {bm}")
        eng.send("go ponder")
        time.sleep(0.4)
        eng.send("stop")

        bm2, pm2 = eng.wait_bestmove(timeout=8.0)

        if bm2 is None:
            failures.append((fen, f"No bestmove after stop (initial: {bm} / {pm})"))
            print(f"  pos {i+1:2d}: FAIL — no bestmove after stop")
            continue

        ponder_board = chess.Board(fen)
        ponder_board.push(chess.Move.from_uci(bm))
        if not is_legal(ponder_board, bm2):
            failures.append((fen, f"After stop, bestmove {bm2!r} illegal in ponder pos"))
            print(f"  pos {i+1:2d}: FAIL — {bm2!r} illegal after stop")
            continue

        passed += 1
        print(f"  pos {i+1:2d}: {bm} → ponder → stop → {bm2} [ok]")

    suffix = f"  ({skipped} skipped)" if skipped else ""
    print(f"  Result: {passed}/{len(positions)} passed{suffix}")
    return passed, len(positions), failures


# ── Suite 4: TT collision stress ───────────────────────────────────────────────

def suite4_tt_stress(eng, bug_positions, repeats=4):
    """Run positions repeatedly without clearing TT to maximise hash collision.

    Any illegal move appearing here indicates a TT-collision bug that
    is_tt_move_valid() should have caught.
    """
    passed = 0
    failures = []

    print("Suite 4 — TT collision stress:")
    for i, fen in enumerate(bug_positions):
        board_start = chess.Board(fen)
        for r in range(repeats):
            # Intentionally skip new_game() to keep TT hot between repeats
            bm, pm = get_bestmove(eng, fen, movetime_ms=150)

            label = f"pos {i+1} rep {r+1}"

            if bm is None:
                failures.append((fen, f"repeat {r+1}: no bestmove"))
                print(f"  {label}: FAIL — no bestmove")
                continue

            if not is_legal(board_start, bm):
                failures.append((fen, f"repeat {r+1}: bestmove {bm!r} is illegal"))
                print(f"  {label}: FAIL — bestmove {bm!r} is illegal")
                continue

            ponder_ok = True
            if pm is not None:
                board2 = chess.Board(fen)
                board2.push(chess.Move.from_uci(bm))
                if not is_legal(board2, pm):
                    failures.append((fen, f"repeat {r+1}: ponder {pm!r} illegal after {bm!r}"))
                    print(f"  {label}: FAIL — ponder {pm!r} illegal after {bm!r}")
                    ponder_ok = False

            if ponder_ok:
                passed += 1
                extra = f" ponder={pm}" if pm else ""
                print(f"  {label}: bm={bm}{extra} [ok]")

    total = len(bug_positions) * repeats
    print(f"  Result: {passed}/{total} passed")
    return passed, total, failures


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.isfile(ENGINE_PATH):
        print(f"ERROR: Engine not found at {ENGINE_PATH}")
        print("Build with: cd c_rewrite && make v21_engine")
        sys.exit(1)

    print(f"Engine: {ENGINE_PATH}")
    print(f"python-chess: {chess.__version__}")
    print()

    eng = Engine(ENGINE_PATH)
    eng.uci_init()

    total_passed = 0
    total_tests = 0
    all_failures = []

    print()
    p, t, f = suite1_ponder_legality(eng, POSITIONS)
    total_passed += p; total_tests += t; all_failures += f

    print()
    p, t, f = suite2_ponder_hit(eng, POSITIONS[:10])
    total_passed += p; total_tests += t; all_failures += f

    print()
    p, t, f = suite3_ponder_stop(eng, POSITIONS[:5])
    total_passed += p; total_tests += t; all_failures += f

    print()
    # Don't clear TT before stress suite — that's the point
    p, t, f = suite4_tt_stress(eng, BUG_POSITIONS, repeats=4)
    total_passed += p; total_tests += t; all_failures += f

    eng.close()

    print()
    print("=" * 55)
    if all_failures:
        print(f"FAILURES ({len(all_failures)}):")
        for fen, reason in all_failures:
            print(f"  FEN:    {fen}")
            print(f"  Reason: {reason}")
        print()

    print(f"TOTAL: {total_passed}/{total_tests} passed")
    if all_failures:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
