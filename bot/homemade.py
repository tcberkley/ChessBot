"""
Some example classes for people who want to create a homemade bot.

With these classes, bot makers will not have to implement the UCI or XBoard interfaces themselves.
"""
import chess
from chess.engine import PlayResult, Limit
import random
import threading
from lib.engine_wrapper import MinimalEngine
from lib.types import MOVE, HOMEMADE_ARGS_TYPE
import logging


# Use this logger variable to print messages to the console or log files.
# logger.info("message") will always print "message" to the console or log file.
# logger.debug("message") will only print "message" if verbose logging is enabled.
logger = logging.getLogger(__name__)


class ExampleEngine(MinimalEngine):
    """An example engine that all homemade engines inherit."""

    pass


import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bots"))
import optimized_v10
import time_managed_v11
import v12


class V10Engine(ExampleEngine):
    """Chess bot v10 — optimized negamax with PVS, TT, and aspiration windows."""

    def search(self, board: chess.Board, time_limit: Limit, ponder: bool, draw_offered: bool,
               root_moves: MOVE) -> PlayResult:
        """Choose the best move using v10 at depth 7."""
        move = optimized_v10.get_best_move(board, depth=7)
        return PlayResult(move, None)


class V11Engine(ExampleEngine):
    """Chess bot v11 — time-managed iterative deepening."""

    def search(self, board: chess.Board, time_limit: Limit, ponder: bool, draw_offered: bool,
               root_moves: MOVE) -> PlayResult:
        """Choose the best move using v11 with time management."""
        # extract clock time for our side
        if board.turn == chess.WHITE:
            my_time = time_limit.white_clock if isinstance(time_limit.white_clock, (int, float)) else 300
            my_inc = time_limit.white_inc if isinstance(time_limit.white_inc, (int, float)) else 0
        else:
            my_time = time_limit.black_clock if isinstance(time_limit.black_clock, (int, float)) else 300
            my_inc = time_limit.black_inc if isinstance(time_limit.black_inc, (int, float)) else 0

        move_number = board.fullmove_number
        budget = time_managed_v11.allocate_time(my_time, my_inc, move_number)
        move = time_managed_v11.get_best_move(board, time_budget=budget)
        return PlayResult(move, None)


class V12Engine(ExampleEngine):
    """Chess bot v12 — futility pruning, log-LMR, qsearch ordering, aspiration fix."""

    def search(self, board: chess.Board, time_limit: Limit, ponder: bool, draw_offered: bool,
               root_moves: MOVE) -> PlayResult:
        """Choose the best move using v12 with time management."""
        if board.turn == chess.WHITE:
            my_time = time_limit.white_clock if isinstance(time_limit.white_clock, (int, float)) else 300
            my_inc = time_limit.white_inc if isinstance(time_limit.white_inc, (int, float)) else 0
        else:
            my_time = time_limit.black_clock if isinstance(time_limit.black_clock, (int, float)) else 300
            my_inc = time_limit.black_inc if isinstance(time_limit.black_inc, (int, float)) else 0

        move_number = board.fullmove_number
        budget = v12.allocate_time(my_time, my_inc, move_number)

        # Hard timeout: run engine in a thread so we can kill it if it hangs.
        # Allow up to 2x the budget (the engine's own 80% abort should fire well
        # before this), but never more than 90% of remaining clock.
        hard_limit = min(budget * 2, my_time * 0.9)
        result = [None]
        exc = [None]

        def run_engine():
            try:
                result[0] = v12.get_best_move(board, time_budget=budget)
            except Exception as e:
                logger.exception("v12 engine crashed")
                exc[0] = e

        t = threading.Thread(target=run_engine, daemon=True)
        t.start()
        t.join(timeout=hard_limit)

        if t.is_alive():
            # Engine is hung — force abort and use whatever we have
            v12._search_aborted = True
            logger.error(f"v12 HARD TIMEOUT after {hard_limit:.1f}s (budget={budget:.1f}s, clock={my_time:.1f}s)")
            t.join(timeout=2.0)  # give it a moment to wind down

        move = result[0]
        # Safety: if engine returned None or crashed, play first legal move
        if move is None:
            move = list(board.legal_moves)[0]
            logger.warning(f"v12 returned None, playing fallback move {move}")
        return PlayResult(move, None)


# Bot names and ideas from tom7's excellent eloWorld video

class RandomMove(ExampleEngine):
    """Get a random move."""

    def search(self, board: chess.Board, *args: HOMEMADE_ARGS_TYPE) -> PlayResult:
        """Choose a random move."""
        return PlayResult(random.choice(list(board.legal_moves)), None)


class Alphabetical(ExampleEngine):
    """Get the first move when sorted by san representation."""

    def search(self, board: chess.Board, *args: HOMEMADE_ARGS_TYPE) -> PlayResult:
        """Choose the first move alphabetically."""
        moves = list(board.legal_moves)
        moves.sort(key=board.san)
        return PlayResult(moves[0], None)


class FirstMove(ExampleEngine):
    """Get the first move when sorted by uci representation."""

    def search(self, board: chess.Board, *args: HOMEMADE_ARGS_TYPE) -> PlayResult:
        """Choose the first move alphabetically in uci representation."""
        moves = list(board.legal_moves)
        moves.sort(key=str)
        return PlayResult(moves[0], None)


class ComboEngine(ExampleEngine):
    """
    Get a move using multiple different methods.

    This engine demonstrates how one can use `time_limit`, `draw_offered`, and `root_moves`.
    """

    def search(self, board: chess.Board, time_limit: Limit, ponder: bool, draw_offered: bool, root_moves: MOVE) -> PlayResult:
        """
        Choose a move using multiple different methods.

        :param board: The current position.
        :param time_limit: Conditions for how long the engine can search (e.g. we have 10 seconds and search up to depth 10).
        :param ponder: Whether the engine can ponder after playing a move.
        :param draw_offered: Whether the bot was offered a draw.
        :param root_moves: If it is a list, the engine should only play a move that is in `root_moves`.
        :return: The move to play.
        """
        if isinstance(time_limit.time, int):
            my_time = time_limit.time
            my_inc = 0
        elif board.turn == chess.WHITE:
            my_time = time_limit.white_clock if isinstance(time_limit.white_clock, int) else 0
            my_inc = time_limit.white_inc if isinstance(time_limit.white_inc, int) else 0
        else:
            my_time = time_limit.black_clock if isinstance(time_limit.black_clock, int) else 0
            my_inc = time_limit.black_inc if isinstance(time_limit.black_inc, int) else 0

        possible_moves = root_moves if isinstance(root_moves, list) else list(board.legal_moves)

        if my_time / 60 + my_inc > 10:
            # Choose a random move.
            move = random.choice(possible_moves)
        else:
            # Choose the first move alphabetically in uci representation.
            possible_moves.sort(key=str)
            move = possible_moves[0]
        return PlayResult(move, None, draw_offered=draw_offered)
