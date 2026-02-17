import chess
import json
import os
import sys
import random
import time
import argparse
from multiprocessing import Pool
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Bot registry - add new bots here
BOT_MODULES = {
    "v1": "bots.mini_max_v1",
    "v2": "bots.mini_max_v2",
    "v3": "bots.alpha_beta_mm_v3",
    "v4": "bots.endgame_faster_v4",
    "v5": "bots.castle_bot_v5",
    "v6": "bots.king_safety_v6",
    "v7": "bots.quiescence_v7",
    "v8": "bots.opening_book_v8",
    "v9": "bots.iterative_v9",
    "v10": "bots.optimized_v10",
    "v11": "bots.time_managed_v11",
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def load_bot(bot_key):
    import importlib
    module_name = BOT_MODULES[bot_key]
    return importlib.import_module(module_name)

def play_game(args):
    game_id, bot1_key, bot2_key, depth, max_moves = args
    bot1 = load_bot(bot1_key)
    bot2 = load_bot(bot2_key)

    board = chess.Board()
    bot1_color = random.choice(["White", "Black"])
    moves = []
    move_count = 0
    bot1_total_time = 0.0
    bot2_total_time = 0.0
    bot1_move_count = 0
    bot2_move_count = 0

    start_time = time.time()

    while not board.is_game_over() and move_count < max_moves:
        bot1_turn = (bot1_color == "White" and board.turn == chess.WHITE) or \
                    (bot1_color == "Black" and board.turn == chess.BLACK)

        move_start = time.time()
        if bot1_turn:
            move = bot1.get_best_move(board, depth=depth)
        else:
            move = bot2.get_best_move(board, depth=depth)
        move_time = round(time.time() - move_start, 4)

        if move is None or move not in board.legal_moves:
            break

        if bot1_turn:
            bot1_total_time += move_time
            bot1_move_count += 1
            bot_label = "bot1"
        else:
            bot2_total_time += move_time
            bot2_move_count += 1
            bot_label = "bot2"

        moves.append({"uci": move.uci(), "time": move_time, "bot": bot_label})
        board.push(move)
        move_count += 1

    elapsed = round(time.time() - start_time, 1)
    bot1_total_time = round(bot1_total_time, 2)
    bot2_total_time = round(bot2_total_time, 2)
    bot1_avg_move_time = round(bot1_total_time / bot1_move_count, 4) if bot1_move_count else 0
    bot2_avg_move_time = round(bot2_total_time / bot2_move_count, 4) if bot2_move_count else 0

    # Determine result
    result = board.result() if board.is_game_over() else "1/2-1/2"
    if result == "1-0":
        winner = "bot1" if bot1_color == "White" else "bot2"
    elif result == "0-1":
        winner = "bot1" if bot1_color == "Black" else "bot2"
    else:
        winner = "draw"

    game_data = {
        "game_id": game_id,
        "bot1": bot1_key,
        "bot2": bot2_key,
        "bot1_color": bot1_color,
        "moves": moves,
        "move_count": move_count,
        "result": result,
        "winner": winner,
        "elapsed_seconds": elapsed,
        "bot1_total_time": bot1_total_time,
        "bot2_total_time": bot2_total_time,
        "bot1_avg_move_time": bot1_avg_move_time,
        "bot2_avg_move_time": bot2_avg_move_time,
        "depth": depth,
        "final_fen": board.fen(),
        "timestamp": datetime.now().isoformat(),
    }

    return game_data


def main():
    parser = argparse.ArgumentParser(description="Run bot vs bot chess tournament")
    parser.add_argument("bot1", choices=BOT_MODULES.keys(), help="First bot")
    parser.add_argument("bot2", choices=BOT_MODULES.keys(), help="Second bot")
    parser.add_argument("-n", "--num-games", type=int, default=10, help="Number of games (default: 10)")
    parser.add_argument("-d", "--depth", type=int, default=5, help="Search depth (default: 5)")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Number of parallel workers (default: CPU count)")
    parser.add_argument("-m", "--max-moves", type=int, default=300, help="Max moves per game before draw (default: 300)")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    # Create a session folder for this tournament run
    session_name = f"{args.bot1}_vs_{args.bot2}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    session_dir = os.path.join(DATA_DIR, session_name)
    os.makedirs(session_dir)

    print(f"Tournament: {args.bot1} vs {args.bot2}")
    print(f"Games: {args.num_games} | Depth: {args.depth} | Workers: {args.workers or 'auto'} | Max moves: {args.max_moves}")
    print(f"Saving to: {session_dir}")
    print("-" * 50)

    game_args = [
        (i + 1, args.bot1, args.bot2, args.depth, args.max_moves)
        for i in range(args.num_games)
    ]

    start_time = time.time()
    results = []

    with Pool(processes=args.workers) as pool:
        for game_data in pool.imap_unordered(play_game, game_args):
            results.append(game_data)

            # Save individual game
            game_file = os.path.join(session_dir, f"game_{game_data['game_id']:03d}.json")
            with open(game_file, "w") as f:
                json.dump(game_data, f, indent=2)

            # Print progress
            w = game_data["winner"]
            label = f"{args.bot1} wins" if w == "bot1" else f"{args.bot2} wins" if w == "bot2" else "draw"
            print(f"  Game {game_data['game_id']:3d}/{args.num_games}: {label} "
                  f"({game_data['move_count']} moves, {game_data['elapsed_seconds']}s, "
                  f"{args.bot1} avg {game_data['bot1_avg_move_time']}s/move, "
                  f"{args.bot2} avg {game_data['bot2_avg_move_time']}s/move)")

    total_time = round(time.time() - start_time, 1)

    # Summary stats
    bot1_wins = sum(1 for r in results if r["winner"] == "bot1")
    bot2_wins = sum(1 for r in results if r["winner"] == "bot2")
    draws = sum(1 for r in results if r["winner"] == "draw")
    avg_moves = round(sum(r["move_count"] for r in results) / len(results), 1)
    avg_bot1_move_time = round(sum(r["bot1_avg_move_time"] for r in results) / len(results), 4)
    avg_bot2_move_time = round(sum(r["bot2_avg_move_time"] for r in results) / len(results), 4)

    summary = {
        "bot1": args.bot1,
        "bot2": args.bot2,
        "num_games": args.num_games,
        "depth": args.depth,
        "bot1_wins": bot1_wins,
        "bot2_wins": bot2_wins,
        "draws": draws,
        "avg_moves": avg_moves,
        "avg_bot1_move_time": avg_bot1_move_time,
        "avg_bot2_move_time": avg_bot2_move_time,
        "total_time_seconds": total_time,
        "timestamp": datetime.now().isoformat(),
    }

    with open(os.path.join(session_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print("-" * 50)
    print(f"Results: {args.bot1} {bot1_wins} - {draws} - {bot2_wins} {args.bot2}")
    print(f"Avg moves: {avg_moves} | Total time: {total_time}s")
    print(f"Avg move time: {args.bot1} {avg_bot1_move_time}s | {args.bot2} {avg_bot2_move_time}s")
    print(f"Data saved to: {session_dir}")


if __name__ == "__main__":
    main()
