import chess
import json
import os
import sys
import time
import argparse

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")

def print_board(board, move_num, total_moves, last_move=None, bot1=None, bot2=None, bot1_color=None):
    clear_screen()

    if bot1 and bot2:
        white_bot = bot1 if bot1_color == "White" else bot2
        black_bot = bot2 if bot1_color == "White" else bot1
        print(f"  Black: {black_bot}")
    print()
    print(board.unicode(borders=True))
    print()
    if bot1 and bot2:
        print(f"  White: {white_bot}")

    print(f"\n  Move {move_num}/{total_moves}", end="")
    if last_move:
        print(f"  |  {last_move}", end="")
    print()

def list_sessions():
    if not os.path.exists(DATA_DIR):
        print("No data directory found.")
        return

    sessions = sorted([d for d in os.listdir(DATA_DIR)
                       if os.path.isdir(os.path.join(DATA_DIR, d))])

    if not sessions:
        print("No tournament sessions found.")
        return

    print("Available sessions:")
    print("-" * 60)
    for i, session in enumerate(sessions, 1):
        summary_path = os.path.join(DATA_DIR, session, "summary.json")
        if os.path.exists(summary_path):
            with open(summary_path) as f:
                s = json.load(f)
            print(f"  {i}. {session}")
            print(f"     {s['bot1']} {s['bot1_wins']} - {s['draws']} - {s['bot2_wins']} {s['bot2']}")
        else:
            print(f"  {i}. {session}")
    return sessions

def list_games(session_dir):
    games = sorted([f for f in os.listdir(session_dir)
                    if f.startswith("game_") and f.endswith(".json")])
    print(f"\nGames in session ({len(games)} total):")
    print("-" * 50)
    for g in games:
        with open(os.path.join(session_dir, g)) as f:
            data = json.load(f)
        w = data["winner"]
        label = f"{data['bot1']} wins" if w == "bot1" else f"{data['bot2']} wins" if w == "bot2" else "draw"
        print(f"  {g}: {label} ({data['move_count']} moves)")
    return games

def view_game(game_path, delay=1.0):
    with open(game_path) as f:
        data = json.load(f)

    board = chess.Board()
    moves = data["moves"]
    bot1 = data["bot1"]
    bot2 = data["bot2"]
    bot1_color = data["bot1_color"]

    print_board(board, 0, len(moves), bot1=bot1, bot2=bot2, bot1_color=bot1_color)
    print(f"\n  Controls: [Enter] next | [a] auto-play | [q] quit")
    input()

    auto = False
    for i, move_entry in enumerate(moves):
        # Support both enriched dicts and plain UCI strings
        if isinstance(move_entry, dict):
            move_uci = move_entry["uci"]
            move_time = move_entry.get("time")
        else:
            move_uci = move_entry
            move_time = None

        move = chess.Move.from_uci(move_uci)
        board.push(move)

        # Determine which bot made this move
        is_white_move = (i % 2 == 0)
        if is_white_move:
            mover = bot1 if bot1_color == "White" else bot2
        else:
            mover = bot1 if bot1_color == "Black" else bot2

        move_label = f"{mover}: {move_uci}"
        if move_time is not None:
            move_label += f" ({move_time}s)"

        print_board(board, i + 1, len(moves), last_move=move_label,
                    bot1=bot1, bot2=bot2, bot1_color=bot1_color)

        if i < len(moves) - 1:
            if auto:
                print(f"\n  Auto-playing (delay: {delay}s) | Press Ctrl+C to stop")
                try:
                    time.sleep(delay)
                except KeyboardInterrupt:
                    auto = False
                    print(f"\n  Controls: [Enter] next | [a] auto-play | [q] quit")
                    choice = input("  > ").strip().lower()
                    if choice == "q":
                        return
                    elif choice == "a":
                        auto = True
            else:
                print(f"\n  Controls: [Enter] next | [a] auto-play | [q] quit")
                choice = input("  > ").strip().lower()
                if choice == "q":
                    return
                elif choice == "a":
                    auto = True

    # Game over
    w = data["winner"]
    label = f"{bot1} wins" if w == "bot1" else f"{bot2} wins" if w == "bot2" else "Draw"
    print(f"\n  Result: {data['result']} ({label})")
    print(f"  Moves: {data['move_count']} | Time: {data['elapsed_seconds']}s")
    input("\n  Press Enter to exit...")

def main():
    parser = argparse.ArgumentParser(description="Replay saved chess games")
    parser.add_argument("game_file", nargs="?", help="Path to a specific game JSON file")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Auto-play delay in seconds (default: 1.0)")
    args = parser.parse_args()

    # Direct file path provided
    if args.game_file:
        if not os.path.exists(args.game_file):
            print(f"File not found: {args.game_file}")
            sys.exit(1)
        view_game(args.game_file, delay=args.delay)
        return

    # Interactive session/game browser
    sessions = list_sessions()
    if not sessions:
        return

    session_choice = input("\nSelect session number (or q to quit): ").strip()
    if session_choice.lower() == "q":
        return
    try:
        session_dir = os.path.join(DATA_DIR, sessions[int(session_choice) - 1])
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    games = list_games(session_dir)
    if not games:
        return

    game_choice = input("\nSelect game number (or q to quit): ").strip()
    if game_choice.lower() == "q":
        return
    try:
        game_file = os.path.join(session_dir, games[int(game_choice) - 1])
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    view_game(game_file, delay=args.delay)


if __name__ == "__main__":
    main()
