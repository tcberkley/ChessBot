import chess
import random

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
    phase = 0
    for pt in range(2, 6):  # KNIGHT=2, BISHOP=3, ROOK=4, QUEEN=5
        phase += len(board.pieces(pt, True)) * _PHASE_WEIGHTS[pt]
        phase += len(board.pieces(pt, False)) * _PHASE_WEIGHTS[pt]
    return min(phase, TOTAL_PHASE) / TOTAL_PHASE

# ─── Transposition table ───

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2
transposition_table = {}  # key -> (depth, score, flag, best_move)
TT_MAX_SIZE = 2_000_000

def tt_store(key, depth, score, flag, best_move):
    existing = transposition_table.get(key)
    if existing is None or depth >= existing[0]:
        if len(transposition_table) >= TT_MAX_SIZE and existing is None:
            # Table full, always-replace oldest-depth entry is complex;
            # just allow overwrite (Python handles memory)
            pass
        transposition_table[key] = (depth, score, flag, best_move)

# ─── Killer moves & history heuristic ───

killer_moves = {}
history_table = {}

CAN_CASTLE_REWARD = 1

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
    for move in legal_moves:
        if tt_move is not None and move == tt_move:
            tt_list.append(move)
        elif board.is_capture(move):
            captures.append(move)
        elif move in depth_killers:
            killers.append(move)
        else:
            quiet.append(move)
    captures.sort(key=lambda m: mvv_lva_score(board, m), reverse=True)
    quiet.sort(key=lambda m: get_history_score(m, color), reverse=True)
    return tt_list + captures + killers + quiet

# ─── Passed pawn check (bitboard) ───

def is_passed_pawn(board, square, color):
    enemy_pawns = int(board.pieces(chess.PAWN, not color))
    if color:
        return (enemy_pawns & PASSED_MASKS_WHITE[square]) == 0
    else:
        return (enemy_pawns & PASSED_MASKS_BLACK[square]) == 0

# ─── King safety ───

def calculate_king_safety(board, color):
    king_square = board.king(color)
    return len(board.attacks(king_square))

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

    pst_mg_color = PST_MG[color]
    pst_eg_color = PST_EG[color]
    phase_inv = 1.0 - phase

    for pt in chess.PIECE_TYPES:
        pst_mg_pt = pst_mg_color[pt]
        pst_eg_pt = pst_eg_color[pt]
        base_val = PIECE_VALUES[pt]
        for sq in board.pieces(pt, color):
            material += base_val
            material += pst_mg_pt[sq] * phase + pst_eg_pt[sq] * phase_inv

            if pt == chess.PAWN:
                pawn_files.append(sq & 7)
                if is_passed_pawn(board, sq, color):
                    rank = sq >> 3
                    advancement = rank if color else (7 - rank)
                    material += (1.0 if end_game else 0.5) * (advancement / 6.0)
            elif pt == chess.BISHOP:
                bishop_count += 1
                material += 0.2 * (len(board.attacks(sq)) ** 0.5)
            elif pt == chess.ROOK or pt == chess.QUEEN:
                material += 0.2 * (len(board.attacks(sq)) ** 0.5)

    if bishop_count >= 2:
        material += 0.3

    for f in range(8):
        count = pawn_files.count(f)
        if count >= 2:
            material -= 0.3 * (count - 1)
    for f in pawn_files:
        if (f - 1) not in pawn_files and (f + 1) not in pawn_files:
            material -= 0.2

    if board.has_kingside_castling_rights(color):
        material += CAN_CASTLE_REWARD
    if board.has_queenside_castling_rights(color):
        material += CAN_CASTLE_REWARD

    if not end_game:
        material -= calculate_king_safety(board, color) ** 0.75

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

INF = float('inf')

def quiescence(board, alpha, beta, phase, depth=0):
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

    for move in board.generate_legal_captures():
        board.push(move)
        score = -quiescence(board, -beta, -alpha, phase, depth - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha

# ─── Negamax with alpha-beta, TT, null move, LMR, PVS ───

MAX_PLY = 40

def negamax(board, depth, alpha, beta, phase, null_ok=True, ply=0):
    # repetition
    if board.is_repetition(2):
        return 0

    if depth <= 0 or board.is_game_over() or ply >= MAX_PLY:
        if board.is_checkmate():
            return -9999
        if board.is_game_over():
            return 0
        return quiescence(board, alpha, beta, phase)

    in_check = board.is_check()

    # check extension
    if in_check and ply < MAX_PLY - 5:
        depth += 1

    # endgame depth extension at root
    if phase < 0.3 and ply == 0:
        depth += 1

    # TT lookup
    tt_key = board._transposition_key()
    tt_move = None
    entry = transposition_table.get(tt_key)
    if entry is not None:
        tt_depth, tt_score, tt_flag, tt_move = entry
        if tt_depth >= depth:
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
        if null_score >= beta:
            return beta

    legal_moves = order_moves(board, list(board.legal_moves), depth, tt_move)

    best_score = -INF
    best_move = None
    color = board.turn
    orig_alpha = alpha

    for move_idx, move in enumerate(legal_moves):
        is_capture = board.is_capture(move)
        gives_check = board.gives_check(move)
        board.push(move)

        # LMR reduction
        reduction = 0
        if move_idx >= 3 and depth >= 3 and not in_check and not is_capture and not gives_check:
            reduction = 1

        # PVS
        if move_idx == 0:
            score = -negamax(board, depth - 1, -beta, -alpha, phase, True, ply + 1)
        else:
            # null window search (with LMR)
            score = -negamax(board, depth - 1 - reduction, -alpha - 1, -alpha, phase, True, ply + 1)
            # re-search if it beats alpha
            if score > alpha and (reduction > 0 or score < beta):
                score = -negamax(board, depth - 1, -beta, -alpha, phase, True, ply + 1)

        board.pop()

        if score > best_score:
            best_score = score
            best_move = move

        alpha = max(alpha, score)
        if alpha >= beta:
            if not is_capture:
                store_killer(move, depth)
                update_history(move, color, depth)
            break

    # TT store — use orig_alpha to determine flag correctly
    if best_score <= orig_alpha:
        tt_flag = UPPERBOUND
    elif best_score >= beta:
        tt_flag = LOWERBOUND
    else:
        tt_flag = EXACT
    tt_store(tt_key, depth, best_score, tt_flag, best_move)

    return best_score

# ─── Root search with iterative deepening + aspiration windows ───

def get_best_move(board, depth=5):
    global killer_moves, history_table
    killer_moves = {}
    history_table = {}
    # TT persists across moves

    # opening book
    if board.fullmove_number == 1:
        if board.turn == chess.WHITE:
            move = random.choice([chess.Move.from_uci("e2e4"), chess.Move.from_uci("d2d4")])
            if move in board.legal_moves:
                return move
        else:
            last_move = board.peek()
            if last_move == chess.Move.from_uci("e2e4"):
                move = chess.Move.from_uci("e7e5")
                if move in board.legal_moves:
                    return move
            elif last_move == chess.Move.from_uci("d2d4"):
                move = chess.Move.from_uci("d7d5")
                if move in board.legal_moves:
                    return move

    phase = get_game_phase(board)
    best_move = None
    prev_score = 0
    ASPIRATION_DELTA = 0.5

    for current_depth in range(1, depth + 1):
        if current_depth <= 2:
            alpha, beta = -INF, INF
        else:
            alpha = prev_score - ASPIRATION_DELTA
            beta = prev_score + ASPIRATION_DELTA

        # root search
        current_best_move = None
        best_value = -INF

        legal_moves = order_moves(board, list(board.legal_moves), current_depth,
                                  transposition_table.get(board._transposition_key(), (None, None, None, None))[3])

        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            score = -negamax(board, current_depth - 1, -beta, -alpha, phase, True, 1)
            board.pop()

            if score > best_value:
                best_value = score
                current_best_move = move
            alpha = max(alpha, score)

        # aspiration fail — widen and re-search
        if current_depth > 2 and (best_value <= prev_score - ASPIRATION_DELTA or best_value >= prev_score + ASPIRATION_DELTA):
            alpha, beta = -INF, INF
            current_best_move = None
            best_value = -INF
            for move in legal_moves:
                board.push(move)
                if board.is_checkmate():
                    board.pop()
                    return move
                score = -negamax(board, current_depth - 1, -beta, -alpha, phase, True, 1)
                board.pop()
                if score > best_value:
                    best_value = score
                    current_best_move = move
                alpha = max(alpha, score)

        prev_score = best_value
        if current_best_move is not None:
            best_move = current_best_move

    return best_move
