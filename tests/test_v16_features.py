#!/usr/bin/env python3
"""
Feature verification tests for v16_engine.

Each test targets one specific v16 feature by comparing eval scores between
positions that differ only in that feature, or by checking search behavior
via UCI output.

Usage:
    python tests/test_v16_features.py
"""

import subprocess
import sys
import os

ENGINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "c_rewrite", "v16_engine",
)


def uci_session(commands: list, timeout: float = 10.0) -> list:
    """Send UCI commands to engine, return all output lines."""
    proc = subprocess.Popen(
        [ENGINE_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    input_str = "\n".join(commands) + "\nquit\n"
    try:
        stdout, _ = proc.communicate(input=input_str, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()
    return stdout.strip().split("\n") if stdout.strip() else []


def get_eval(fen: str) -> int:
    """Get static eval for a position via the 'eval' UCI command."""
    lines = uci_session(["uci", "isready", f"position fen {fen}", "eval"])
    for line in lines:
        if line.startswith("eval:"):
            return int(line.split(":")[1].strip())
    raise ValueError(f"No eval output.\nFEN: {fen}\nOutput: {lines}")


def get_search_score(fen: str, depth: int) -> int:
    """Run a fixed-depth search and return the final score in centipawns."""
    lines = uci_session(
        ["uci", "isready", f"position fen {fen}", f"go depth {depth}"],
        timeout=30.0,
    )
    # Use the last info line with a score (deepest completed depth)
    for line in reversed(lines):
        if "score cp" in line:
            parts = line.split()
            idx = parts.index("cp")
            return int(parts[idx + 1])
        if "score mate" in line:
            return 30000
    raise ValueError(f"No score in output.\nFEN: {fen}\nOutput: {lines}")


def get_info_lines(fen: str, depth: int) -> list:
    """Return all 'info score ...' lines from a search.
    Engine format: 'info score cp X depth Y nodes Z time W pv ...'
    """
    lines = uci_session(
        ["uci", "isready", f"position fen {fen}", f"go depth {depth}"],
        timeout=30.0,
    )
    return [l for l in lines if l.startswith("info score")]


def run_test(name: str, fn) -> bool:
    """Run a single test, printing pass/fail."""
    sys.stdout.write(f"  {name:<50s} ... ")
    sys.stdout.flush()
    try:
        fn()
        print("PASS")
        return True
    except AssertionError as e:
        print(f"FAIL  ({e})")
        return False
    except Exception as e:
        print(f"ERROR ({type(e).__name__}: {e})")
        return False


# ---------------------------------------------------------------------------
# Tests: Insufficient Material
# ---------------------------------------------------------------------------

def test_kk_is_draw():
    """KK → evaluate() must return 0."""
    score = get_eval("4k3/8/8/8/8/8/8/4K3 w - - 0 1")
    assert score == 0, f"KK eval={score}, expected 0"


def test_knk_is_draw():
    """KNK → evaluate() must return 0."""
    score = get_eval("4k3/8/8/8/8/8/8/4KN2 w - - 0 1")
    assert score == 0, f"KNK eval={score}, expected 0"


def test_kbk_is_draw():
    """KBK → evaluate() must return 0."""
    score = get_eval("4k3/8/8/8/8/8/8/3BK3 w - - 0 1")
    assert score == 0, f"KBK eval={score}, expected 0"


def test_krk_not_draw():
    """KRK must NOT eval to 0 (rook can force mate)."""
    score = get_eval("4k3/8/8/8/8/8/8/4KR2 w - - 0 1")
    assert score != 0, f"KRK eval={score}, expected non-zero"


# ---------------------------------------------------------------------------
# Tests: 50-Move Rule  (needs search, not eval — check is in negamax at ply>0)
# ---------------------------------------------------------------------------

def test_50_move_triggers():
    """
    KRK with halfmove clock=99: after any quiet move clock hits 100.
    All children return draw (0) → root score must be 0.
    """
    # No pawns so ALL moves are quiet.
    score = get_search_score("8/8/4k3/8/8/8/8/R3K3 w - - 99 1", depth=1)
    assert score == 0, f"50-move rule not detected: score={score}, expected 0"


def test_50_move_no_false_trigger():
    """Same KRK position with clock=0: must show a winning score for white."""
    score = get_search_score("8/8/4k3/8/8/8/8/R3K3 w - - 0 1", depth=1)
    assert score > 100, f"KRK with clock=0 score={score}, expected >100"


# ---------------------------------------------------------------------------
# Tests: Rook Behind Passed Pawn  (+20 bonus)
# ---------------------------------------------------------------------------

def test_rook_behind_passer_bonus():
    """
    Rook on a1 behind passed pawn on a7 should score higher than
    rook on a8 (ahead of the same pawn).
    Both positions have phase=2 (one rook), so endgame mode,
    but the bonus fires unconditionally in the rook loop.
    """
    # Rook behind: Ra1 (BBC sq56, rank7) vs pawn a7 (BBC sq8, rank1) → rank7 > rank1 ✓
    behind = get_eval("6k1/P7/8/8/8/8/8/R5K1 w - - 0 1")
    # Rook ahead:  Ra8 (BBC sq0,  rank0) vs pawn a7 (BBC sq8, rank1) → rank0 < rank1 ✗
    ahead  = get_eval("R5k1/P7/8/8/8/8/8/6K1 w - - 0 1")
    assert behind > ahead, (
        f"Rook behind passer ({behind} cp) should outscore rook ahead ({ahead} cp)"
    )


# ---------------------------------------------------------------------------
# Tests: Connected Rooks  (+15 bonus when same rank/file with clear path)
# ---------------------------------------------------------------------------

def test_connected_rooks_bonus():
    """
    Two rooks on the same rank with no pieces between them should score
    higher than two rooks on different ranks/files.
    """
    # Connected: Ra1 and Re1 — same BBC rank 7, clear path b1-d1
    connected    = get_eval("6k1/8/8/8/8/8/8/R3R1K1 w - - 0 1")
    # Disconnected: Ra1 and Re2 — different rank AND file
    disconnected = get_eval("6k1/8/8/8/8/8/4R3/R5K1 w - - 0 1")
    assert connected > disconnected, (
        f"Connected rooks ({connected} cp) should outscore disconnected ({disconnected} cp)"
    )


# ---------------------------------------------------------------------------
# Tests: Pawn Shield Quality  (middlegame only: needs phase >= 7)
# ---------------------------------------------------------------------------
#
# Add one queen per side (phase += 4+4 = 8 >= 7) so the shield check fires.
# Queens on d1/d8 (symmetric, far from g-file king), pawns on the g-side.

def test_shield_rank1_beats_rank2():
    """
    Pawns directly in front of king (rank_dist=1, +15 each) should score
    higher than pawns one step advanced (rank_dist=2, +8 each).
    Shield difference: 3×15=45 vs 3×8=24 → Δ≈21 cp.
    Queens added per side for phase=8 (middlegame).
    """
    # rank_dist=1: pawns f2,g2,h2 in front of Kg1
    close = get_eval("3q2k1/8/8/8/8/8/5PPP/3Q2K1 w - - 0 1")
    # rank_dist=2: pawns f3,g3,h3
    far   = get_eval("3q2k1/8/8/8/8/5PPP/8/3Q2K1 w - - 0 1")
    assert close > far, (
        f"Close shield ({close} cp) should score > advanced shield ({far} cp)"
    )


def test_shield_beats_no_shield():
    """Any pawn shield should score higher than no shield at all."""
    # rank_dist=1 shield
    shielded   = get_eval("3q2k1/8/8/8/8/8/5PPP/3Q2K1 w - - 0 1")
    # No pawns in front of king
    unshielded = get_eval("3q2k1/8/8/8/8/8/8/3Q2K1 w - - 0 1")
    assert shielded > unshielded, (
        f"Shielded king ({shielded} cp) should score > unshielded ({unshielded} cp)"
    )


# ---------------------------------------------------------------------------
# Tests: Pawn Islands  (-8 cp per island beyond the first)
# ---------------------------------------------------------------------------

def test_pawn_islands_penalty():
    """More pawn islands → lower score. Penalty: (islands-1)*8 cp."""
    # 1 island: 8 connected pawns (all on rank 2)
    one  = get_eval("6k1/8/8/8/8/8/PPPPPPPP/6K1 w - - 0 1")
    # 2 islands: gap in the middle (PPP..PPP)
    two  = get_eval("6k1/8/8/8/8/8/PPP2PPP/6K1 w - - 0 1")
    # 4 islands: P.P.P.PP
    four = get_eval("6k1/8/8/8/8/8/P1P1P1PP/6K1 w - - 0 1")
    assert one >= two,  f"1 island ({one} cp) should score >= 2 islands ({two} cp)"
    assert two >= four, f"2 islands ({two} cp) should score >= 4 islands ({four} cp)"
    assert one > four,  f"1 island ({one} cp) should score > 4 islands ({four} cp)"


# ---------------------------------------------------------------------------
# Tests: King Mobility in Endgame  (+3 cp per safe move, endgame only)
# ---------------------------------------------------------------------------
#
# Use K+P vs K so phase=0 (end_game=true) and eval is non-zero.

def test_king_mobility_endgame():
    """
    King in the centre (up to 8 moves) should score higher than
    king in the corner (3 moves) in endgame.
    Both positions have same pawn to keep eval non-zero.
    """
    # King on e4 (BBC sq28): centralized, high mobility
    central = get_eval("4k3/8/8/8/4K3/8/P7/8 w - - 0 1")
    # King on h1 (BBC sq63): corner, low mobility
    corner  = get_eval("4k3/8/8/8/8/8/P7/7K w - - 0 1")
    assert central > corner, (
        f"Central king ({central} cp) should score > corner king ({corner} cp) in endgame"
    )


# ---------------------------------------------------------------------------
# Tests: Sanity / Search Features
# ---------------------------------------------------------------------------

def test_search_returns_valid_move():
    """Engine must return a valid bestmove from the start position."""
    lines = uci_session(["uci", "isready", "position startpos", "go depth 5"],
                        timeout=15.0)
    bestmove_lines = [l for l in lines if l.startswith("bestmove")]
    assert len(bestmove_lines) == 1, f"Expected 1 bestmove line, got: {bestmove_lines}"
    move = bestmove_lines[0].split()[1]
    assert move != "0000", f"Engine returned null move from startpos"
    assert len(move) >= 4, f"Move '{move}' too short to be valid"


def test_aspiration_no_crash():
    """
    Aspiration gradual widening must not crash or hang on a
    sharp tactical position.
    """
    # Italian Game — lots of tactics
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    lines = uci_session(["uci", "isready", f"position fen {fen}", "go depth 8"],
                        timeout=20.0)
    info = [l for l in lines if l.startswith("info score")]
    assert len(info) >= 5, f"Expected at least 5 depth levels, got {len(info)}"
    bestmove = [l for l in lines if l.startswith("bestmove")]
    assert len(bestmove) == 1 and bestmove[0].split()[1] != "0000", \
        f"Invalid bestmove output: {bestmove}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TESTS = [
    # Insufficient material
    ("Insufficient material: KK → 0",              test_kk_is_draw),
    ("Insufficient material: KNK → 0",             test_knk_is_draw),
    ("Insufficient material: KBK → 0",             test_kbk_is_draw),
    ("Insufficient material: KRK ≠ 0",             test_krk_not_draw),
    # 50-move rule
    ("50-move rule: clock=99 → draw score",         test_50_move_triggers),
    ("50-move rule: clock=0 → no false draw",       test_50_move_no_false_trigger),
    # Eval features
    ("Rook behind passer > rook ahead",             test_rook_behind_passer_bonus),
    ("Connected rooks > disconnected",              test_connected_rooks_bonus),
    ("Pawn shield rank_dist=1 > rank_dist=2",       test_shield_rank1_beats_rank2),
    ("Pawn shield > no shield (middlegame)",        test_shield_beats_no_shield),
    ("Pawn islands penalty (1 < 2 < 4 islands)",   test_pawn_islands_penalty),
    ("King mobility: central > corner (endgame)",  test_king_mobility_endgame),
    # Search sanity
    ("Search: valid bestmove from startpos",        test_search_returns_valid_move),
    ("Aspiration: no crash on tactical position",  test_aspiration_no_crash),
]


def main():
    print(f"\nv16 Engine Feature Tests")
    print(f"Engine: {ENGINE_PATH}")
    print("=" * 70)

    if not os.path.isfile(ENGINE_PATH):
        print(f"ERROR: engine not found — run: cd c_rewrite && make v16_engine")
        sys.exit(1)

    passed = failed = 0
    for name, fn in TESTS:
        if run_test(name, fn):
            passed += 1
        else:
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed  ({passed + failed} total)")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
