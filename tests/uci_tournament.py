"""
UCI Engine Tournament: play games between two UCI engines at fixed depth.

Default mode: 25 positions × 2 colors = 50 games (v13 vs v14).
Each position is played twice with colors swapped so neither engine has a
color advantage — the pair score is the fairest comparison unit.

Usage:
    python tests/uci_tournament.py [options]

Options:
    --positions N     Number of unique opening positions (default: 25)
    --depth D         Search depth per move (default: 10)
    --opening_moves N Random half-moves used to reach each position (default: 10)
    --seed N          RNG seed for reproducible position generation (default: 42)
    --engine1 PATH    Path to engine 1 (default: c_rewrite/v13_engine)
    --engine2 PATH    Path to engine 2 (default: c_rewrite/v14_engine)
"""
import argparse
import random
import sys
import os
import time
import chess
import chess.engine


PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}


def material_balance(board: chess.Board) -> int:
    """Return material balance in pawns (positive = White ahead)."""
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += value * len(board.pieces(piece_type, chess.WHITE))
        score -= value * len(board.pieces(piece_type, chess.BLACK))
    return score


def generate_positions(n: int, opening_moves: int, seed: int,
                       max_imbalance: int = 2) -> list[str]:
    """
    Generate N distinct, balanced starting positions by playing random
    legal moves from the start. Filters out game-over positions and
    any with material imbalance greater than max_imbalance pawns.
    """
    rng = random.Random(seed)
    positions = []
    seen = set()
    attempts = 0

    while len(positions) < n:
        attempts += 1
        if attempts > n * 100:
            print(f"Warning: could only generate {len(positions)} positions "
                  f"after many attempts. Lowering opening_moves may help.",
                  file=sys.stderr)
            break

        board = chess.Board()
        for _ in range(opening_moves):
            if board.is_game_over():
                break
            move = rng.choice(list(board.legal_moves))
            board.push(move)

        if board.is_game_over():
            continue

        fen = board.fen()
        if fen in seen:
            continue

        if abs(material_balance(board)) > max_imbalance:
            continue

        seen.add(fen)
        positions.append(fen)

    return positions


def play_game(engine1_path: str, engine2_path: str, depth: int,
              start_fen: str, e1_is_white: bool, game_label: str) -> dict:
    """
    Play a single game from start_fen. engine1 plays White if e1_is_white.
    Returns a result dict with outcome and timing/node stats.
    """
    white_path = engine1_path if e1_is_white else engine2_path
    black_path = engine2_path if e1_is_white else engine1_path

    board = chess.Board(start_fen)
    move_times: dict[str, list] = {engine1_path: [], engine2_path: []}
    move_nodes: dict[str, list] = {engine1_path: [], engine2_path: []}
    move_count = 0

    try:
        with chess.engine.SimpleEngine.popen_uci(white_path) as white_eng, \
             chess.engine.SimpleEngine.popen_uci(black_path) as black_eng:

            while not board.is_game_over(claim_draw=True) and move_count < 300:
                is_white_turn = board.turn == chess.WHITE
                current_eng = white_eng if is_white_turn else black_eng
                current_path = white_path if is_white_turn else black_path

                t0 = time.time()
                result = current_eng.play(
                    board,
                    chess.engine.Limit(depth=depth, time=30),
                    info=chess.engine.INFO_ALL,
                )
                elapsed = time.time() - t0

                move_times[current_path].append(elapsed)
                nodes = result.info.get("nodes", 0)
                if nodes:
                    move_nodes[current_path].append(nodes)

                board.push(result.move)
                move_count += 1

    except Exception as exc:
        print(f"  {game_label} error: {exc}", file=sys.stderr)
        return {
            "result": "*", "moves": move_count,
            "e1_times": [], "e2_times": [],
            "e1_nodes": [], "e2_nodes": [],
        }

    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        result_str = "*"
    elif outcome.winner is None:
        result_str = "1/2-1/2"
    elif outcome.winner == chess.WHITE:
        result_str = "1-0"
    else:
        result_str = "0-1"

    return {
        "result": result_str,
        "moves": move_count,
        "e1_is_white": e1_is_white,
        "e1_times": move_times[engine1_path],
        "e2_times": move_times[engine2_path],
        "e1_nodes": move_nodes[engine1_path],
        "e2_nodes": move_nodes[engine2_path],
    }


def e1_score_from_result(result_str: str, e1_is_white: bool) -> float:
    """Return engine1's score for this game (1, 0.5, or 0)."""
    if result_str == "1/2-1/2":
        return 0.5
    if result_str == "*":
        return 0.5  # count unfinished as draw
    if result_str == "1-0":
        return 1.0 if e1_is_white else 0.0
    return 0.0 if e1_is_white else 1.0


def main():
    parser = argparse.ArgumentParser(
        description="UCI engine tournament with randomized opening positions"
    )
    parser.add_argument("--positions", type=int, default=25,
                        help="Number of unique positions (default: 25)")
    parser.add_argument("--depth", type=int, default=10,
                        help="Search depth per move (default: 10)")
    parser.add_argument("--opening_moves", type=int, default=10,
                        help="Random half-moves to reach each position (default: 10)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for position generation (default: 42)")
    parser.add_argument("--engine1", default=None,
                        help="Path to engine 1 (default: c_rewrite/v13_engine)")
    parser.add_argument("--engine2", default=None,
                        help="Path to engine 2 (default: c_rewrite/v14_engine)")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    engine1_path = args.engine1 or os.path.join(project_root, "c_rewrite", "v13_engine")
    engine2_path = args.engine2 or os.path.join(project_root, "c_rewrite", "v14_engine")
    e1_name = os.path.basename(engine1_path)
    e2_name = os.path.basename(engine2_path)

    total_games = args.positions * 2

    print(f"Tournament: {e1_name} vs {e2_name}")
    print(f"Positions: {args.positions} × 2 colors = {total_games} games | "
          f"Depth: {args.depth} | Opening moves: {args.opening_moves} | Seed: {args.seed}")
    print("-" * 70)

    # Generate positions
    print(f"Generating {args.positions} opening positions...", end=" ", flush=True)
    positions = generate_positions(args.positions, args.opening_moves, args.seed)
    print(f"done ({len(positions)} positions).")
    print()

    # Tournament state
    e1_wins = e1_losses = draws = unfinished = 0
    all_e1_times: list = []
    all_e2_times: list = []
    all_e1_nodes: list = []
    all_e2_nodes: list = []
    total_moves = 0

    game_num = 0
    for pos_idx, fen in enumerate(positions):
        pair_scores = []  # engine1 scores for this position pair

        for game_in_pair in range(2):
            game_num += 1
            e1_is_white = (game_in_pair == 0)  # game A: e1=W, game B: e1=B
            color_str = f"{e1_name}=W" if e1_is_white else f"{e1_name}=B"
            label = f"Pos {pos_idx+1}/{len(positions)} game {'A' if e1_is_white else 'B'}"

            sys.stdout.write(
                f"\rGame {game_num}/{total_games} | {label} ({color_str})...    "
            )
            sys.stdout.flush()

            result = play_game(
                engine1_path, engine2_path, args.depth,
                fen, e1_is_white,
                game_label=f"Game {game_num}",
            )

            r = result["result"]
            total_moves += result["moves"]
            all_e1_times.extend(result["e1_times"])
            all_e2_times.extend(result["e2_times"])
            all_e1_nodes.extend(result["e1_nodes"])
            all_e2_nodes.extend(result["e2_nodes"])

            score = e1_score_from_result(r, e1_is_white)
            pair_scores.append(score)

            if r == "*":
                unfinished += 1
            elif r == "1/2-1/2":
                draws += 1
            elif score == 1.0:
                e1_wins += 1
            else:
                e1_losses += 1

            score_str = f"[{e1_name}: +{e1_wins} ={draws} -{e1_losses}]"
            sys.stdout.write(
                f"\rGame {game_num}/{total_games} done ({r}) {score_str}    \n"
            )
            sys.stdout.flush()

        # Summarise the position pair
        pair_total = sum(pair_scores)
        if pair_total == 2.0:
            pair_summary = f"  >> Position {pos_idx+1}: {e1_name} won BOTH games"
        elif pair_total == 0.0:
            pair_summary = f"  >> Position {pos_idx+1}: {e2_name} won BOTH games"
        elif pair_total == 1.0:
            pair_summary = f"  >> Position {pos_idx+1}: split (1 win each)"
        else:
            pair_summary = f"  >> Position {pos_idx+1}: mixed draws ({pair_total}/2)"
        print(pair_summary)

    # Final summary
    total_finished = e1_wins + e1_losses + draws
    print("\n" + "=" * 70)
    print(f"RESULTS: {e1_name} vs {e2_name} | Depth {args.depth} | {len(positions)} positions")
    print("=" * 70)
    print(f"  {e1_name:20s}  +{e1_wins} ={draws} -{e1_losses}")
    print(f"  {e2_name:20s}  +{e1_losses} ={draws} -{e1_wins}")
    if unfinished:
        print(f"  Unfinished games:    {unfinished}")
    if total_finished > 0:
        e1_pct = (e1_wins + 0.5 * draws) / total_finished
        print(f"  {e1_name} score:      {e1_pct:.1%}  "
              f"({e1_wins + 0.5*draws:.1f}/{total_finished})")
    print(f"  Avg moves/game:      {total_moves / total_games:.1f}")
    print()

    if all_e1_times:
        avg_e1_ms = 1000 * sum(all_e1_times) / len(all_e1_times)
        print(f"  Avg move time {e1_name}: {avg_e1_ms:.1f} ms  ({len(all_e1_times)} moves)")
    if all_e2_times:
        avg_e2_ms = 1000 * sum(all_e2_times) / len(all_e2_times)
        print(f"  Avg move time {e2_name}: {avg_e2_ms:.1f} ms  ({len(all_e2_times)} moves)")

    if all_e1_nodes and all_e2_nodes:
        avg_e1_nodes = sum(all_e1_nodes) / len(all_e1_nodes)
        avg_e2_nodes = sum(all_e2_nodes) / len(all_e2_nodes)
        print(f"  Avg nodes/move {e1_name}: {avg_e1_nodes:,.0f}")
        print(f"  Avg nodes/move {e2_name}: {avg_e2_nodes:,.0f}")
        if avg_e1_nodes > 0:
            ratio = avg_e2_nodes / avg_e1_nodes
            print(f"  Node ratio ({e2_name}/{e1_name}): {ratio:.2f}x")

    print("=" * 70)
    import subprocess as _sp
    _sp.run(["osascript", "-e", 'beep'], check=False)


if __name__ == "__main__":
    main()