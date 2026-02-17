import chess
import random
import time
import logging
import math

logger = logging.getLogger(__name__)

# ─── Global time-abort signal for deep search ───
_search_start_time = 0
_search_time_budget = None
_search_aborted = False
_node_count = 0
_TIME_CHECK_INTERVAL = 2048  # check time every N nodes
_time_check_counter = _TIME_CHECK_INTERVAL

# ─── Piece values as tuple (index by piece_type: 1=PAWN..6=KING) ───
PIECE_VALUES = (0, 1, 3, 3, 5, 9, 0)

# ─── 2D PST source tables (from white's perspective, row 0 = rank 1) ───

_pst_pawn_mg = [
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.05, 0.1,  0.1, -0.2, -0.2,  0.1,  0.1,  0.05],
    [ 0.05,-0.05,-0.1,  0.0,  0.0, -0.1, -0.05, 0.05],
    [ 0.0,  0.0,  0.0,  0.25, 0.25, 0.0,  0.0,  0.0],
    [ 0.05, 0.05, 0.1,  0.3,  0.3,  0.1,  0.05, 0.05],
    [ 0.1,  0.1,  0.2,  0.35, 0.35, 0.2,  0.1,  0.1],
    [ 0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

_pst_pawn_eg = [
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1],
    [ 0.2,  0.2,  0.2,  0.2,  0.2,  0.2,  0.2,  0.2],
    [ 0.3,  0.3,  0.3,  0.3,  0.3,  0.3,  0.3,  0.3],
    [ 0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5],
    [ 0.8,  0.8,  0.8,  0.8,  0.8,  0.8,  0.8,  0.8],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

_pst_knight = [
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5],
    [-0.4, -0.2,  0.0,  0.0,  0.0,  0.0, -0.2, -0.4],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3,  0.05, 0.15, 0.2,  0.2,  0.15, 0.05,-0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.05, 0.1,  0.15, 0.15, 0.1,  0.05,-0.3],
    [-0.4, -0.2,  0.0,  0.05, 0.05, 0.0, -0.2, -0.4],
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5],
]

_pst_bishop = [
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.1,  0.1,  0.05, 0.0, -0.1],
    [-0.1,  0.05, 0.05, 0.1,  0.1,  0.05, 0.05,-0.1],
    [-0.1,  0.0,  0.1,  0.1,  0.1,  0.1,  0.0, -0.1],
    [-0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1, -0.1],
    [-0.1,  0.05, 0.0,  0.0,  0.0,  0.0,  0.05,-0.1],
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2],
]

_pst_rook = [
    [ 0.0,  0.0,  0.0,  0.05, 0.05, 0.0,  0.0,  0.0],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [ 0.05, 0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.05],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

_pst_queen = [
    [-0.2, -0.1, -0.1, -0.05,-0.05,-0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.1],
    [-0.05, 0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05],
    [ 0.0,  0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05],
    [-0.1,  0.05, 0.05, 0.05, 0.05, 0.05, 0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.2, -0.1, -0.1, -0.05,-0.05,-0.1, -0.1, -0.2],
]

_pst_king_mg = [
    [ 0.2,  0.3,  0.1,  0.0,  0.0,  0.1,  0.3,  0.2],
    [ 0.2,  0.2,  0.0,  0.0,  0.0,  0.0,  0.2,  0.2],
    [-0.1, -0.2, -0.2, -0.2, -0.2, -0.2, -0.2, -0.1],
    [-0.2, -0.3, -0.3, -0.4, -0.4, -0.3, -0.3, -0.2],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
]

_pst_king_eg = [
    [-0.5, -0.3, -0.3, -0.3, -0.3, -0.3, -0.3, -0.5],
    [-0.3, -0.1,  0.0,  0.0,  0.0,  0.0, -0.1, -0.3],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3, -0.1,  0.0,  0.0,  0.0,  0.0, -0.1, -0.3],
    [-0.5, -0.3, -0.3, -0.3, -0.3, -0.3, -0.3, -0.5],
]

# ─── Flatten PST tables to 1D tuples indexed by square ───

def _flatten(table_2d):
    flat = [0.0] * 64
    for sq in range(64):
        flat[sq] = table_2d[sq >> 3][sq & 7]
    return tuple(flat)

def _mirror(flat):
    return tuple(flat[sq ^ 56] for sq in range(64))

# Midgame PST per piece type, indexed by [color][piece_type][square]
# color: chess.WHITE=True=1, chess.BLACK=False=0
_knight_flat = _flatten(_pst_knight)
_bishop_flat = _flatten(_pst_bishop)
_rook_flat = _flatten(_pst_rook)
_queen_flat = _flatten(_pst_queen)
_pawn_mg_flat = _flatten(_pst_pawn_mg)
_pawn_eg_flat = _flatten(_pst_pawn_eg)
_king_mg_flat = _flatten(_pst_king_mg)
_king_eg_flat = _flatten(_pst_king_eg)

PST_MG = {
    True: {  # WHITE
        chess.PAWN: _pawn_mg_flat,
        chess.KNIGHT: _knight_flat,
        chess.BISHOP: _bishop_flat,
        chess.ROOK: _rook_flat,
        chess.QUEEN: _queen_flat,
        chess.KING: _king_mg_flat,
    },
    False: {  # BLACK
        chess.PAWN: _mirror(_pawn_mg_flat),
        chess.KNIGHT: _mirror(_knight_flat),
        chess.BISHOP: _mirror(_bishop_flat),
        chess.ROOK: _mirror(_rook_flat),
        chess.QUEEN: _mirror(_queen_flat),
        chess.KING: _mirror(_king_mg_flat),
    },
}

PST_EG = {
    True: {
        chess.PAWN: _pawn_eg_flat,
        chess.KNIGHT: _knight_flat,
        chess.BISHOP: _bishop_flat,
        chess.ROOK: _rook_flat,
        chess.QUEEN: _queen_flat,
        chess.KING: _king_eg_flat,
    },
    False: {
        chess.PAWN: _mirror(_pawn_eg_flat),
        chess.KNIGHT: _mirror(_knight_flat),
        chess.BISHOP: _mirror(_bishop_flat),
        chess.ROOK: _mirror(_rook_flat),
        chess.QUEEN: _mirror(_queen_flat),
        chess.KING: _mirror(_king_eg_flat),
    },
}

# ─── Pre-computed passed pawn masks (bitboard) ───

_passed_masks_white = [0] * 64
_passed_masks_black = [0] * 64
for _sq in range(64):
    _file = _sq & 7
    _rank = _sq >> 3
    _mw = 0
    _mb = 0
    for _f in range(max(0, _file - 1), min(7, _file + 1) + 1):
        for _r in range(_rank + 1, 8):
            _mw |= 1 << (_r * 8 + _f)
        for _r in range(0, _rank):
            _mb |= 1 << (_r * 8 + _f)
    _passed_masks_white[_sq] = _mw
    _passed_masks_black[_sq] = _mb
PASSED_MASKS_WHITE = tuple(_passed_masks_white)
PASSED_MASKS_BLACK = tuple(_passed_masks_black)

# ─── Game phase ───

TOTAL_PHASE = 24
_PHASE_WEIGHTS = (0, 0, 1, 1, 2, 4, 0)  # index by piece_type

def get_game_phase(board):
    pieces = board.pieces
    phase = ((len(pieces(2, True)) + len(pieces(2, False))) * 1 +  # knights
             (len(pieces(3, True)) + len(pieces(3, False))) * 1 +  # bishops
             (len(pieces(4, True)) + len(pieces(4, False))) * 2 +  # rooks
             (len(pieces(5, True)) + len(pieces(5, False))) * 4)   # queens
    return min(phase, TOTAL_PHASE) / TOTAL_PHASE

# ─── Transposition table ───

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2
transposition_table = {}  # key -> (depth, score, flag, best_move)
TT_MAX_SIZE = 2_000_000

def tt_store(key, depth, score, flag, best_move):
    # Never store non-finite scores (protects against inf/-inf from corrupted
    # or partial searches). Also avoid storing if table full when adding new.
    if not math.isfinite(score):
        return
    existing = transposition_table.get(key)
    if existing is None or depth >= existing[0]:
        if len(transposition_table) >= TT_MAX_SIZE and existing is None:
            return  # table full, don't add new entries (existing overwrites still allowed)
        transposition_table[key] = (depth, score, flag, best_move)

# ─── Killer moves & history heuristic ───

killer_moves = {}
history_table = {}

CAN_CASTLE_REWARD = 0.1  # small bonus for retaining the option to castle
CASTLED_BONUS = 0.4      # larger bonus for having actually castled

def store_killer(move, depth):
    if depth not in killer_moves:
        killer_moves[depth] = []
    killers = killer_moves[depth]
    if move not in killers:
        killers.insert(0, move)
        if len(killers) > 2:
            killers.pop()

def update_history(move, color, depth):
    key = (color, move.from_square, move.to_square)
    history_table[key] = history_table.get(key, 0) + depth * depth

def get_history_score(move, color):
    return history_table.get((color, move.from_square, move.to_square), 0)

# ─── Move ordering ───

def mvv_lva_score(board, move):
    victim = board.piece_at(move.to_square)
    if victim is None:
        return 1.0  # en passant
    attacker = board.piece_at(move.from_square)
    v = PIECE_VALUES[victim.piece_type]
    a = PIECE_VALUES[attacker.piece_type] if attacker else 0
    return v - a / 10.0

def order_moves(board, legal_moves, depth=0, tt_move=None):
    tt_list = []
    captures = []
    killers = []
    quiet = []
    depth_killers = killer_moves.get(depth, [])
    color = board.turn
    piece_at = board.piece_at
    for move in legal_moves:
        if tt_move is not None and move == tt_move:
            tt_list.append(move)
        elif board.is_capture(move):
            # Inline MVV-LVA: compute score during categorization
            victim = piece_at(move.to_square)
            if victim is None:
                score = 1.0  # en passant
            else:
                attacker = piece_at(move.from_square)
                score = PIECE_VALUES[victim.piece_type] - (PIECE_VALUES[attacker.piece_type] / 10.0 if attacker else 0)
            captures.append((score, len(captures), move))
        elif move in depth_killers:
            killers.append(move)
        else:
            quiet.append(move)
    captures.sort(reverse=True)
    quiet.sort(key=lambda m: get_history_score(m, color), reverse=True)
    return tt_list + [m for _, _, m in captures] + killers + quiet

# ─── King safety ───

def calculate_king_safety(board, color):
    """Count friendly pawns in the 8 squares surrounding the king (pawn shield)."""
    king_square = board.king(color)
    king_ring = chess.BB_KING_ATTACKS[king_square]
    friendly_pawns = int(board.pieces(chess.PAWN, color))
    return bin(king_ring & friendly_pawns).count('1')

# ─── King endgame bonuses ───

def king_centralization(board, color):
    king_sq = board.king(color)
    rank = king_sq >> 3
    file = king_sq & 7
    center_dist = max(abs(rank - 3.5), abs(file - 3.5))
    return -center_dist * 0.1

def king_proximity_bonus(board, color):
    my_king = board.king(color)
    enemy_king = board.king(not color)
    dist = max(abs((my_king >> 3) - (enemy_king >> 3)),
               abs((my_king & 7) - (enemy_king & 7)))
    return -dist * 0.05

# ─── Evaluation ───

def get_adj_material(board, color, phase):
    material = 0.0
    end_game = phase < 0.3
    bishop_count = 0
    pawn_files = []
    pawn_file_set = set()

    pst_mg_color = PST_MG[color]
    pst_eg_color = PST_EG[color]
    phase_inv = 1.0 - phase

    # Cache enemy pawn bitboard for passed pawn checks (avoids re-fetching per pawn)
    enemy_pawns_bb = int(board.pieces(chess.PAWN, not color))
    passed_masks = PASSED_MASKS_WHITE if color else PASSED_MASKS_BLACK
    passed_bonus = 1.0 if end_game else 0.5

    for pt in chess.PIECE_TYPES:
        pst_mg_pt = pst_mg_color[pt]
        pst_eg_pt = pst_eg_color[pt]
        base_val = PIECE_VALUES[pt]
        for sq in board.pieces(pt, color):
            material += base_val
            material += pst_mg_pt[sq] * phase + pst_eg_pt[sq] * phase_inv

            if pt == chess.PAWN:
                pf = sq & 7
                pawn_files.append(pf)
                pawn_file_set.add(pf)
                if (enemy_pawns_bb & passed_masks[sq]) == 0:
                    rank = sq >> 3
                    advancement = rank if color else (7 - rank)
                    material += passed_bonus * (advancement / 6.0)
            elif pt == chess.BISHOP:
                bishop_count += 1
                material += 0.2 * (bin(board.attacks_mask(sq)).count('1') ** 0.5)
            elif pt == chess.ROOK or pt == chess.QUEEN:
                material += 0.2 * (bin(board.attacks_mask(sq)).count('1') ** 0.5)

    if bishop_count >= 2:
        material += 0.3

    for f in range(8):
        count = pawn_files.count(f)
        if count >= 2:
            material -= 0.3 * (count - 1)
    for f in pawn_files:
        if (f - 1) not in pawn_file_set and (f + 1) not in pawn_file_set:
            material -= 0.2

    if board.has_kingside_castling_rights(color):
        material += CAN_CASTLE_REWARD
    if board.has_queenside_castling_rights(color):
        material += CAN_CASTLE_REWARD

    # bonus for having castled (king on castled square, no castling rights left)
    if not board.has_kingside_castling_rights(color) and not board.has_queenside_castling_rights(color):
        king_sq = board.king(color)
        if color:  # WHITE
            if king_sq in (chess.G1, chess.H1, chess.C1, chess.B1):
                material += CASTLED_BONUS
        else:  # BLACK
            if king_sq in (chess.G8, chess.H8, chess.C8, chess.B8):
                material += CASTLED_BONUS

    if not end_game:
        material += calculate_king_safety(board, color) * 0.15

    if end_game:
        material += king_centralization(board, color)
        material += king_proximity_bonus(board, color)

    return material

def evaluate(board, phase):
    white_mat = get_adj_material(board, True, phase)
    black_mat = get_adj_material(board, False, phase)
    score = white_mat - black_mat
    return score if board.turn else -score

# ─── Quiescence search (negamax) ───

# Use a large but finite infinity to avoid float('inf') propagating through
# the search and transposition table (which can be produced by negating
# sentinel values). Keep it well above mate scores (9000) used elsewhere.
INF = 100000.0

def quiescence(board, alpha, beta, phase, depth=0):
    global _node_count, _search_aborted, _time_check_counter
    _node_count += 1

    if _search_aborted:
        return 0
    _time_check_counter -= 1
    if _time_check_counter <= 0:
        _time_check_counter = _TIME_CHECK_INTERVAL
        if _search_time_budget is not None:
            if time.time() - _search_start_time > _search_time_budget * 0.8:
                _search_aborted = True
                return 0

    stand_pat = evaluate(board, phase)

    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    if depth <= -3:
        return stand_pat

    # delta pruning
    if stand_pat + 9 < alpha:
        return alpha

    # collect and sort captures/promotions by MVV-LVA (inlined)
    capture_moves = []
    piece_at = board.piece_at
    for move in board.legal_moves:
        if board.is_capture(move) or move.promotion:
            victim = piece_at(move.to_square)
            if victim is None:
                score = 1.0
            else:
                attacker = piece_at(move.from_square)
                score = PIECE_VALUES[victim.piece_type] - (PIECE_VALUES[attacker.piece_type] / 10.0 if attacker else 0)
            capture_moves.append((score, len(capture_moves), move))
    capture_moves.sort(reverse=True)

    for _, _, move in capture_moves:
        board.push(move)
        score = -quiescence(board, -beta, -alpha, phase, depth - 1)
        board.pop()

        if _search_aborted:
            return 0

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha

# ─── Negamax with alpha-beta, TT, null move, LMR, PVS, futility pruning ───

# Futility pruning margins indexed by depth (0 unused, 1=1 pawn, 2=minor piece)
_FUTILITY_MARGINS = (0, 1.5, 3.5)

# Pre-computed LMR reduction table: _LMR_TABLE[depth][move_idx]
_LMR_TABLE = [[0] * 64 for _ in range(64)]
for _d in range(1, 64):
    for _m in range(1, 64):
        _LMR_TABLE[_d][_m] = int(1 + math.log(_d) * math.log(_m) / 2.5)

MAX_PLY = 40

def negamax(board, depth, alpha, beta, phase, null_ok=True, ply=0):
    global _node_count, _search_aborted, _time_check_counter
    _node_count += 1

    # periodic time check inside the search tree (decrementing counter avoids modulo)
    _time_check_counter -= 1
    if _time_check_counter <= 0:
        _time_check_counter = _TIME_CHECK_INTERVAL
        if _search_time_budget is not None:
            elapsed = time.time() - _search_start_time
            if elapsed > _search_time_budget * 0.8:
                _search_aborted = True
                logger.debug(f"v12 ABORT in negamax: {elapsed:.2f}s > {_search_time_budget*0.8:.2f}s")
                return 0

    if _search_aborted:
        return 0

    # repetition
    if board.is_repetition(2):
        return 0

    in_check = board.is_check()

    # check extension — must happen BEFORE depth-0 check
    # so we don't drop into quiescence while in check
    if in_check and ply < MAX_PLY - 5:
        depth += 1

    if depth <= 0 or ply >= MAX_PLY:
        return quiescence(board, alpha, beta, phase)

    # TT lookup
    tt_key = board._transposition_key()
    tt_move = None
    entry = transposition_table.get(tt_key)
    if entry is not None:
        tt_depth, tt_score, tt_flag, tt_move = entry
        # If a corrupted non-finite score slipped into the TT previously,
        # remove it and ignore the entry to avoid propagating infinities.
        if not math.isfinite(tt_score):
            transposition_table.pop(tt_key, None)
            entry = None
        if entry is not None and tt_depth >= depth:
            if tt_flag == EXACT:
                return tt_score
            elif tt_flag == LOWERBOUND:
                alpha = max(alpha, tt_score)
            elif tt_flag == UPPERBOUND:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    # null move pruning
    if null_ok and not in_check and phase >= 0.3 and depth >= 3:
        board.push(chess.Move.null())
        null_score = -negamax(board, depth - 3, -beta, -beta + 1, phase, False, ply + 1)
        board.pop()
        if _search_aborted:
            return 0
        if null_score >= beta:
            return beta

    # futility pruning: at shallow depths, if static eval + margin < alpha,
    # skip quiet moves (they can't possibly raise alpha)
    futile = False
    if depth <= 2 and not in_check and abs(alpha) < 9000:
        static_eval = evaluate(board, phase)
        if static_eval + _FUTILITY_MARGINS[depth] <= alpha:
            futile = True

    legal_moves = order_moves(board, list(board.legal_moves), depth, tt_move)

    if not legal_moves:
        # no legal moves: checkmate or stalemate
        if in_check:
            return -9999  # checkmate
        return 0  # stalemate

    best_score = -INF
    best_move = None
    color = board.turn
    orig_alpha = alpha

    for move_idx, move in enumerate(legal_moves):
        is_capture = board.is_capture(move)

        # futility pruning: skip quiet moves in futile positions
        if futile and move_idx > 0 and not is_capture and not move.promotion:
            continue

        # only compute gives_check for moves where LMR applies (saves time on early moves)
        gives_check = False
        if move_idx >= 3 and depth >= 3 and not in_check and not is_capture:
            gives_check = board.gives_check(move)

        board.push(move)

        # LMR: log-based reduction for late quiet moves (pre-computed table)
        reduction = 0
        if move_idx >= 3 and depth >= 3 and not in_check and not is_capture and not gives_check:
            reduction = _LMR_TABLE[depth][move_idx] if move_idx < 64 else _LMR_TABLE[depth][63]
            reduction = min(reduction, depth - 2)  # don't reduce into negative depth

        # PVS
        if move_idx == 0:
            score = -negamax(board, depth - 1, -beta, -alpha, phase, True, ply + 1)
        else:
            # null window search (with LMR)
            score = -negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, phase, True, ply + 1)
            # re-search if it beats alpha
            if not _search_aborted and score > alpha and (reduction > 0 or score < beta):
                score = -negamax(board, depth - 1, -beta, -alpha, phase, True, ply + 1)

        board.pop()

        if _search_aborted:
            break

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, score)
        if alpha >= beta:
            if not is_capture:
                store_killer(move, depth)
                update_history(move, color, depth)
            break

    # Don't store corrupted results from aborted searches
    if not _search_aborted and best_score > -INF:
        if best_score <= orig_alpha:
            tt_flag = UPPERBOUND
        elif best_score >= beta:
            tt_flag = LOWERBOUND
        else:
            tt_flag = EXACT
        tt_store(tt_key, depth, best_score, tt_flag, best_move)

    return best_score

# ─── Time management ───

MAX_DEPTH = 30  # cap depth; time controls the search

def allocate_time(my_time, my_inc, move_number):
    """Decide how much time to spend on this move (in seconds)."""
    # estimate moves remaining in game
    if move_number < 10:
        moves_left = 40
    elif move_number < 30:
        moves_left = 30
    else:
        moves_left = 20

    # base time: divide remaining time by estimated moves left
    base = my_time / moves_left

    # add a portion of increment
    base += my_inc * 0.8

    # don't use more than 1/5 of remaining time on a single move
    max_time = my_time * 0.2

    # minimum think time of 0.5s (unless nearly out of time)
    min_time = min(0.5, my_time * 0.05)

    return max(min_time, min(base, max_time))

# ─── Root search with time-managed iterative deepening + aspiration windows ───

def get_best_move(board, depth=None, time_budget=None):
    """
    Get the best move. Accepts either:
    - depth: fixed depth search (backwards compatible with v10/tournament runner)
    - time_budget: time in seconds to spend on this move
    If neither is given, defaults to depth=7.
    """
    global killer_moves, history_table
    killer_moves = {}
    history_table = {}
    # TT persists across moves — entries from previous positions help with move ordering

    # opening book
    if board.fullmove_number == 1:
        if board.turn == chess.WHITE:
            move = random.choice([chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4")])
            if move in board.legal_moves:
                return move
        elif board.move_stack:
            last_move = board.peek()
            if last_move == chess.Move.from_uci("e2e4"):
                move = chess.Move.from_uci("e7e5")
                if move in board.legal_moves:
                    return move
            elif last_move == chess.Move.from_uci("d2d4"):
                move = chess.Move.from_uci("d7d5")
                if move in board.legal_moves:
                    return move

    # determine search mode
    global _search_start_time, _search_time_budget, _search_aborted, _node_count, _time_check_counter
    use_time = time_budget is not None
    if not use_time and depth is None:
        depth = 7
    max_depth = MAX_DEPTH if use_time else depth

    phase = get_game_phase(board)
    best_move = None
    prev_score = 0
    ASPIRATION_DELTA = 0.5
    start_time = time.time()
    _search_start_time = start_time
    _search_time_budget = time_budget if use_time else None
    _search_aborted = False
    _node_count = 0
    _time_check_counter = _TIME_CHECK_INTERVAL
    completed_depth = 0

    side = "W" if board.turn else "B"
    mode = f"t={time_budget:.1f}s" if use_time else f"d={depth}"
    n_legal = len(list(board.legal_moves))
    logger.info(f"v12 START {side} m{board.fullmove_number} {mode} ph={phase:.2f} moves={n_legal} TT={len(transposition_table)}")
    logger.debug(f"v12 FEN: {board.fen()}")

    # minimum guaranteed depth scales with budget: depth 3 for <2s, 4 for <5s, 5 otherwise
    if use_time:
        if time_budget < 2.0:
            min_depth = 3
        elif time_budget < 5.0:
            min_depth = 4
        else:
            min_depth = 5
    else:
        min_depth = max_depth  # fixed depth mode: no early stop

    for current_depth in range(1, max_depth + 1):
        # time check: don't start a new depth if we've used 40%+ of budget
        if use_time and current_depth > min_depth:
            elapsed = time.time() - start_time
            if elapsed > time_budget * 0.4:
                logger.info(f"v12 STOP {elapsed:.2f}s/{time_budget:.1f}s before d{current_depth}")
                break
        _search_aborted = False
        nodes_before = _node_count

        if current_depth <= 2:
            alpha, beta = -INF, INF
        else:
            alpha = prev_score - ASPIRATION_DELTA
            beta = prev_score + ASPIRATION_DELTA

        # root search — endgame extension: search 1 ply deeper when few pieces remain
        search_depth = current_depth + 1 if phase < 0.3 else current_depth
        current_best_move = None
        best_value = -INF

        legal_moves = order_moves(board, list(board.legal_moves), current_depth,
                                  transposition_table.get(board._transposition_key(), (None, None, None, None))[3])

        aborted = False
        for move_idx, move in enumerate(legal_moves):
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move

            # PVS at root: full window for first move, null window for rest
            if move_idx == 0:
                score = -negamax(board, search_depth - 1, -beta, -alpha, phase, True, 1)
            else:
                score = -negamax(board, search_depth - 1, -alpha - 1, -alpha, phase, True, 1)
                if not _search_aborted and score > alpha and score < beta:
                    score = -negamax(board, search_depth - 1, -beta, -alpha, phase, True, 1)
            board.pop()

            if _search_aborted:
                aborted = True
                break

            if score > best_value:
                best_value = score
                current_best_move = move
            alpha = max(alpha, score)

        if aborted:
            elapsed = time.time() - start_time
            logger.info(f"v12 d{current_depth} ABORT m{move_idx+1}/{len(legal_moves)} t={elapsed:.2f}s")
            break

        # aspiration fail — widen and re-search, but only if we have enough time
        if current_depth > 2 and (best_value <= prev_score - ASPIRATION_DELTA or best_value >= prev_score + ASPIRATION_DELTA):
            if use_time:
                elapsed = time.time() - start_time
                if elapsed > time_budget * 0.5:
                    # not enough time for aspiration re-search, use result from narrow window
                    if current_best_move is not None:
                        depth_nodes = _node_count - nodes_before
                        prev_score = best_value
                        best_move = current_best_move
                        completed_depth = current_depth
                        logger.info(f"v12 d{current_depth} OK(asp-skip) {best_move} sc={best_value:.2f} n={depth_nodes} t={elapsed:.2f}s")
                        if abs(best_value) >= 9000:
                            logger.info(f"v12 MATE found at d{current_depth}, stopping")
                            break
                    continue
            alpha, beta = -INF, INF
            current_best_move = None
            best_value = -INF
            for move in legal_moves:
                board.push(move)
                if board.is_checkmate():
                    board.pop()
                    return move
                score = -negamax(board, search_depth - 1, -beta, -alpha, phase, True, 1)
                board.pop()

                if _search_aborted:
                    aborted = True
                    break

                if score > best_value:
                    best_value = score
                    current_best_move = move
                alpha = max(alpha, score)

            if aborted:
                elapsed = time.time() - start_time
                logger.info(f"v12 d{current_depth} ABORT aspiration t={elapsed:.2f}s")
                break

        depth_nodes = _node_count - nodes_before
        prev_score = best_value
        if current_best_move is not None:
            best_move = current_best_move
            completed_depth = current_depth
            elapsed = time.time() - start_time
            logger.info(f"v12 d{current_depth} OK {best_move} sc={best_value:.2f} n={depth_nodes} t={elapsed:.2f}s")

            # stop deepening if we found a forced mate
            if abs(best_value) >= 9000:
                logger.info(f"v12 MATE found at d{current_depth}, stopping")
                break

    total_time = time.time() - start_time
    logger.info(f"v12 DONE {best_move} d={completed_depth} t={total_time:.2f}s n={_node_count} TT={len(transposition_table)}")
    return best_move
