"""
Methodical comparison between v13_engine and v14_engine.

Tests:
  1. Perft — verify move generation is identical (count must match known values)
  2. Eval  — compare depth-1 scores on many positions
  3. Search — run depth 1-12 on tactical positions, find first divergence
  4. Bestmove — compare final bestmove on a large position set

Usage:
    python tests/engine_diff.py
"""
import subprocess, sys, os, time

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT        = os.path.dirname(SCRIPT_DIR)
V13         = os.path.join(ROOT, "c_rewrite", "v13_engine")
V14         = os.path.join(ROOT, "c_rewrite", "v14_engine")

# ── Known-correct perft values (source: chessprogramming.org) ──────────────
PERFT_POSITIONS = [
    ("startpos",
     "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
     {1: 20, 2: 400, 3: 8902, 4: 197281, 5: 4865609}),
    ("kiwipete",
     "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     {1: 48, 2: 2039, 3: 97862, 4: 4085603}),
    ("pos3",
     "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
     {1: 14, 2: 191, 3: 2812, 4: 43238, 5: 674624}),
    ("pos4",
     "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
     {1: 6, 2: 264, 3: 9467, 4: 422333}),
]

# ── Positions for search/eval comparison ──────────────────────────────────
POSITIONS = [
    # label, fen
    ("startpos",    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"),
    ("sicilian",    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2"),
    ("ruy-lopez",   "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"),
    ("middlegame",  "r1bq1rk1/ppp2ppp/2np1n2/2b1p3/2B1P3/2NP1N2/PPP2PPP/R1BQR1K1 w - - 0 9"),
    ("endgame-pp",  "8/3k4/8/1p1P4/pP6/P7/4K3/8 w - - 0 1"),  # passed pawns
    ("doubled-pawn","8/p3kp2/3p4/2pPp3/2P1P3/1P6/P2K4/8 w - - 0 1"),
    ("tactics-pin", "r1bqk2r/pppp1ppp/2n2n2/4p3/1bB1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 4 4"),
    ("mat-in-2",    "r1bqkb1r/pppp1ppp/2n5/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 4"),
    ("open-endgame","4k3/8/4K3/4P3/8/8/8/8 w - - 0 1"),
    ("complex-mid", "r2q1rk1/ppp2ppp/2n2n2/2bpp3/2B1P1b1/2NP1N2/PPP2PPP/R1BQR1K1 w - - 0 9"),
]

# ── Tactical positions expected best moves ─────────────────────────────────
TACTICAL = [
    # label, fen, expected_best, depth
    ("back-rank",  "6k1/5ppp/8/8/8/8/8/4R1K1 w - - 0 1", "e1e8", 3),
    ("fork-knight","r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
                   None, 5),  # no fixed answer; just check both engines agree
]


def run_engine_raw(path, commands, timeout=30):
    """Send list of UCI commands to engine, return stdout."""
    p = subprocess.Popen(
        [path],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdin_data = "\n".join(commands) + "\n"
        out, _ = p.communicate(stdin_data, timeout=timeout)
        return out
    except subprocess.TimeoutExpired:
        p.kill()
        return ""


def parse_perft(output):
    """Return perft node count from engine output (format: '    Nodes: 8902')."""
    for line in output.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith("nodes:"):
            try:
                return int(stripped.split()[-1].replace(",", ""))
            except ValueError:
                pass
    return None


def parse_search(output, target_depth=None):
    """
    Return (bestmove, score_cp, depth_reached) from engine UCI output.
    If target_depth given, return info line at exactly that depth.
    """
    bestmove = None
    last_score = None
    last_depth = None
    depth_scores = {}

    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("bestmove"):
            parts = line.split()
            bestmove = parts[1] if len(parts) > 1 else None
        elif line.startswith("info") and "depth" in line and "score" in line:
            parts = line.split()
            try:
                d = int(parts[parts.index("depth") + 1])
            except (ValueError, IndexError):
                continue
            score = None
            if "score" in parts:
                si = parts.index("score")
                if si + 2 < len(parts) and parts[si + 1] == "cp":
                    try:
                        score = int(parts[si + 2])
                    except ValueError:
                        pass
                elif si + 2 < len(parts) and parts[si + 1] == "mate":
                    try:
                        m = int(parts[si + 2])
                        score = 100000 - abs(m) * 100
                        if m < 0:
                            score = -score
                    except ValueError:
                        pass
            depth_scores[d] = score
            last_score = score
            last_depth = d

    if target_depth is not None:
        return bestmove, depth_scores.get(target_depth), target_depth
    return bestmove, last_score, last_depth


def pos_cmd(fen):
    if fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1":
        return "position startpos"
    return f"position fen {fen}"


# ═══════════════════════════════════════════════════════════════════════════
# TEST 1 — Perft
# ═══════════════════════════════════════════════════════════════════════════
def test_perft():
    print("\n" + "═" * 70)
    print("TEST 1: PERFT — move generation correctness")
    print("═" * 70)
    all_ok = True

    for label, fen, known in PERFT_POSITIONS:
        pcmd = pos_cmd(fen)
        max_depth = max(known.keys())
        for depth, expected in sorted(known.items()):
            cmds = ["uci", "isready", pcmd, f"perft {depth}", "quit"]
            out13 = run_engine_raw(V13, cmds)
            out14 = run_engine_raw(V14, cmds)

            n13 = parse_perft(out13)
            n14 = parse_perft(out14)

            v13_ok = "✓" if n13 == expected else f"✗(got {n13})"
            v14_ok = "✓" if n14 == expected else f"✗(got {n14})"
            match  = "✓" if n13 == n14 else "✗ MISMATCH"

            status = "OK" if (n13 == expected and n14 == expected) else "FAIL"
            if status == "FAIL":
                all_ok = False

            print(f"  [{status}] {label} perft({depth}): "
                  f"expected={expected:,}  v13={v13_ok}  v14={v14_ok}  match={match}")

    return all_ok


# ═══════════════════════════════════════════════════════════════════════════
# TEST 2 — Evaluation comparison (depth 1)
# ═══════════════════════════════════════════════════════════════════════════
def test_eval():
    print("\n" + "═" * 70)
    print("TEST 2: EVAL — depth-1 score comparison")
    print("═" * 70)
    diffs = []

    for label, fen in POSITIONS:
        cmds = ["uci", "isready", pos_cmd(fen), "go depth 1", "quit"]
        out13 = run_engine_raw(V13, cmds)
        out14 = run_engine_raw(V14, cmds)

        bm13_e, sc13, _ = parse_search(out13, target_depth=1)
        bm14_e, sc14, _ = parse_search(out14, target_depth=1)

        if sc13 is None and sc14 is None:
            # Engine used opening book - use depth 2 fallback
            cmds2 = ["uci", "isready", pos_cmd(fen), "go depth 2", "quit"]
            bm13_e, sc13, _ = parse_search(run_engine_raw(V13, cmds2), target_depth=2)
            bm14_e, sc14, _ = parse_search(run_engine_raw(V14, cmds2), target_depth=2)

        if sc13 is None or sc14 is None:
            print(f"  [SKIP] {label}: could not parse score")
            continue

        diff = abs(sc13 - sc14)
        marker = "✓" if diff == 0 else (f"⚠ diff={diff:+d}cp" if diff < 50 else f"✗ LARGE diff={diff:+d}cp")
        print(f"  {label:20s}  v13={sc13:+5d}cp  v14={sc14:+5d}cp  {marker}")
        if diff > 0:
            diffs.append((label, sc13, sc14, diff))

    if diffs:
        print(f"\n  Positions with eval differences: {len(diffs)}")
    return diffs


# ═══════════════════════════════════════════════════════════════════════════
# TEST 3 — Search divergence: depth 1 → 12
# ═══════════════════════════════════════════════════════════════════════════
def test_search_divergence():
    print("\n" + "═" * 70)
    print("TEST 3: SEARCH DIVERGENCE — first depth where bestmoves differ")
    print("═" * 70)

    for label, fen in POSITIONS[:6]:  # first 6 positions
        first_diff = None
        print(f"\n  Position: {label}")
        for depth in range(1, 11):
            cmds = ["uci", "isready", pos_cmd(fen), f"go depth {depth}", "quit"]
            out13 = run_engine_raw(V13, cmds, timeout=30)
            out14 = run_engine_raw(V14, cmds, timeout=30)

            bm13, sc13, _ = parse_search(out13, target_depth=depth)
            bm14, sc14, _ = parse_search(out14, target_depth=depth)

            match = bm13 == bm14
            sc_match = sc13 == sc14
            marker = "✓" if match else "✗"

            sc13_s = f"{sc13:+d}" if sc13 is not None else "?"
            sc14_s = f"{sc14:+d}" if sc14 is not None else "?"
            print(f"    d{depth:2d}: v13={bm13}({sc13_s}) v14={bm14}({sc14_s}) {marker}")

            if not match and first_diff is None:
                first_diff = depth

        if first_diff:
            print(f"  ↳ First divergence at depth {first_diff}")
        else:
            print(f"  ↳ Engines agree at all depths tested")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 4 — Tactical positions
# ═══════════════════════════════════════════════════════════════════════════
def test_tactics():
    print("\n" + "═" * 70)
    print("TEST 4: TACTICAL POSITIONS — both engines agree on best move")
    print("═" * 70)

    for label, fen, expected, depth in TACTICAL:
        cmds = ["uci", "isready", pos_cmd(fen), f"go depth {depth}", "quit"]
        out13 = run_engine_raw(V13, cmds, timeout=30)
        out14 = run_engine_raw(V14, cmds, timeout=30)

        bm13, sc13, _ = parse_search(out13)
        bm14, sc14, _ = parse_search(out14)

        agree = bm13 == bm14
        if expected:
            ok13 = bm13 == expected
            ok14 = bm14 == expected
            marker = "✓" if (ok13 and ok14) else f"✗"
            print(f"  [{marker}] {label}: v13={bm13} v14={bm14} expected={expected}")
        else:
            marker = "✓" if agree else "✗ DISAGREE"
            print(f"  [{marker}] {label}: v13={bm13}({sc13}) v14={bm14}({sc14})")


# ═══════════════════════════════════════════════════════════════════════════
# TEST 5 — Bestmove agreement on large position set
# ═══════════════════════════════════════════════════════════════════════════
def test_bestmove_agreement():
    print("\n" + "═" * 70)
    print("TEST 5: BESTMOVE AGREEMENT — depth 8 on all positions")
    print("═" * 70)

    agree_count = 0
    disagree = []

    for label, fen in POSITIONS:
        cmds = ["uci", "isready", pos_cmd(fen), "go depth 8", "quit"]
        out13 = run_engine_raw(V13, cmds, timeout=60)
        out14 = run_engine_raw(V14, cmds, timeout=60)

        bm13, sc13, _ = parse_search(out13)
        bm14, sc14, _ = parse_search(out14)

        sc13_s = f"{sc13:+d}cp" if sc13 is not None else "?"
        sc14_s = f"{sc14:+d}cp" if sc14 is not None else "?"
        if bm13 == bm14:
            agree_count += 1
            print(f"  ✓ {label:20s}  both={bm13} ({sc13_s})")
        else:
            print(f"  ✗ {label:20s}  v13={bm13}({sc13_s}) v14={bm14}({sc14_s})")
            disagree.append(label)

    print(f"\n  Agreement: {agree_count}/{len(POSITIONS)} positions")
    return disagree


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    for path, name in [(V13, "v13_engine"), (V14, "v14_engine")]:
        if not os.path.isfile(path):
            print(f"ERROR: {name} not found at {path}")
            sys.exit(1)

    print("Chess Engine Diagnostic: v13 vs v14")
    print(f"v13: {V13}")
    print(f"v14: {V14}")

    t0 = time.time()
    perft_ok = test_perft()
    eval_diffs = test_eval()
    test_search_divergence()
    test_tactics()
    disagree = test_bestmove_agreement()

    print("\n" + "═" * 70)
    print("SUMMARY")
    print("═" * 70)
    print(f"  Perft:            {'PASS' if perft_ok else 'FAIL — move gen bug'}")
    print(f"  Eval diffs:       {len(eval_diffs)} positions differ at depth 1")
    print(f"  Bestmove (d=8):   {len(POSITIONS)-len(disagree)}/{len(POSITIONS)} agree")
    print(f"  Elapsed:          {time.time()-t0:.1f}s")
    print("═" * 70)
