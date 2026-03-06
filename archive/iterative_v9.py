import chess
import random

board = chess.Board()

piece_values = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0
}

#piece-square tables (from white's perspective, row 0 = rank 1)
#values are bonus/penalty added to base piece value

pst_pawn_mg = [
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.05, 0.1,  0.1, -0.2, -0.2,  0.1,  0.1,  0.05],
    [ 0.05,-0.05,-0.1,  0.0,  0.0, -0.1, -0.05, 0.05],
    [ 0.0,  0.0,  0.0,  0.25, 0.25, 0.0,  0.0,  0.0],
    [ 0.05, 0.05, 0.1,  0.3,  0.3,  0.1,  0.05, 0.05],
    [ 0.1,  0.1,  0.2,  0.35, 0.35, 0.2,  0.1,  0.1],
    [ 0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

pst_pawn_eg = [
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
    [ 0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1],
    [ 0.2,  0.2,  0.2,  0.2,  0.2,  0.2,  0.2,  0.2],
    [ 0.3,  0.3,  0.3,  0.3,  0.3,  0.3,  0.3,  0.3],
    [ 0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5,  0.5],
    [ 0.8,  0.8,  0.8,  0.8,  0.8,  0.8,  0.8,  0.8],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

pst_knight = [
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5],
    [-0.4, -0.2,  0.0,  0.0,  0.0,  0.0, -0.2, -0.4],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3,  0.05, 0.15, 0.2,  0.2,  0.15, 0.05,-0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.05, 0.1,  0.15, 0.15, 0.1,  0.05,-0.3],
    [-0.4, -0.2,  0.0,  0.05, 0.05, 0.0, -0.2, -0.4],
    [-0.5, -0.4, -0.3, -0.3, -0.3, -0.3, -0.4, -0.5],
]

pst_bishop = [
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.1,  0.1,  0.05, 0.0, -0.1],
    [-0.1,  0.05, 0.05, 0.1,  0.1,  0.05, 0.05,-0.1],
    [-0.1,  0.0,  0.1,  0.1,  0.1,  0.1,  0.0, -0.1],
    [-0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.1, -0.1],
    [-0.1,  0.05, 0.0,  0.0,  0.0,  0.0,  0.05,-0.1],
    [-0.2, -0.1, -0.1, -0.1, -0.1, -0.1, -0.1, -0.2],
]

pst_rook = [
    [ 0.0,  0.0,  0.0,  0.05, 0.05, 0.0,  0.0,  0.0],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [-0.05, 0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.05],
    [ 0.05, 0.1,  0.1,  0.1,  0.1,  0.1,  0.1,  0.05],
    [ 0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0],
]

pst_queen = [
    [-0.2, -0.1, -0.1, -0.05,-0.05,-0.1, -0.1, -0.2],
    [-0.1,  0.0,  0.0,  0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.1],
    [-0.05, 0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05],
    [ 0.0,  0.0,  0.05, 0.05, 0.05, 0.05, 0.0, -0.05],
    [-0.1,  0.05, 0.05, 0.05, 0.05, 0.05, 0.0, -0.1],
    [-0.1,  0.0,  0.05, 0.0,  0.0,  0.0,  0.0, -0.1],
    [-0.2, -0.1, -0.1, -0.05,-0.05,-0.1, -0.1, -0.2],
]

pst_king_mg = [
    [ 0.2,  0.3,  0.1,  0.0,  0.0,  0.1,  0.3,  0.2],
    [ 0.2,  0.2,  0.0,  0.0,  0.0,  0.0,  0.2,  0.2],
    [-0.1, -0.2, -0.2, -0.2, -0.2, -0.2, -0.2, -0.1],
    [-0.2, -0.3, -0.3, -0.4, -0.4, -0.3, -0.3, -0.2],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
    [-0.3, -0.4, -0.4, -0.5, -0.5, -0.4, -0.4, -0.3],
]

#king endgame: centralize + approach enemy king
pst_king_eg = [
    [-0.5, -0.3, -0.3, -0.3, -0.3, -0.3, -0.3, -0.5],
    [-0.3, -0.1,  0.0,  0.0,  0.0,  0.0, -0.1, -0.3],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.0,  0.15, 0.2,  0.2,  0.15, 0.0, -0.3],
    [-0.3,  0.0,  0.1,  0.15, 0.15, 0.1,  0.0, -0.3],
    [-0.3, -0.1,  0.0,  0.0,  0.0,  0.0, -0.1, -0.3],
    [-0.5, -0.3, -0.3, -0.3, -0.3, -0.3, -0.3, -0.5],
]

#penalties/rewards
can_castle_reward = 1

#transposition table constants
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2
transposition_table = {}
TT_MAX_SIZE = 100000

#killer moves: 2 slots per depth
killer_moves = {}

#calculate game phase (0 = endgame, 1 = opening/middlegame)
TOTAL_PHASE = 24  # 4 knights + 4 bishops + 4 rooks + 2 queens = 4*1 + 4*1 + 4*2 + 2*4
phase_weights = {chess.PAWN: 0, chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4, chess.KING: 0}

def get_game_phase(board):
    phase = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            phase += phase_weights.get(piece.piece_type, 0)
    return min(phase, TOTAL_PHASE) / TOTAL_PHASE  # 1.0 = full material, 0.0 = endgame

def is_endgame(board):
    return get_game_phase(board) < 0.3

#get PST value for a piece, handling color flip
def get_pst_value(piece_type, square, color, phase):
    row = chess.square_rank(square)
    col = chess.square_file(square)
    #flip row for black (so tables are always from white's perspective)
    if color == chess.BLACK:
        row = 7 - row

    if piece_type == chess.PAWN:
        mg = pst_pawn_mg[row][col]
        eg = pst_pawn_eg[row][col]
        return phase * mg + (1 - phase) * eg
    elif piece_type == chess.KNIGHT:
        return pst_knight[row][col]
    elif piece_type == chess.BISHOP:
        return pst_bishop[row][col]
    elif piece_type == chess.ROOK:
        return pst_rook[row][col]
    elif piece_type == chess.QUEEN:
        return pst_queen[row][col]
    elif piece_type == chess.KING:
        mg = pst_king_mg[row][col]
        eg = pst_king_eg[row][col]
        return phase * mg + (1 - phase) * eg
    return 0

#see how open the king is (higher is worse) - uses attacks() for speed
def calculate_king_safety(board, color):
    king_square = board.king(color)
    return len(board.attacks(king_square))

#checks if a pawn is passed (no enemy pawns blocking on same or adjacent files)
def is_passed_pawn(board, square, color):
    col = chess.square_file(square)
    row = chess.square_rank(square)
    enemy = not color
    for f in range(max(0, col - 1), min(7, col + 1) + 1):
        if color == chess.WHITE:
            for r in range(row + 1, 8):
                p = board.piece_at(chess.square(f, r))
                if p and p.piece_type == chess.PAWN and p.color == enemy:
                    return False
        else:
            for r in range(0, row):
                p = board.piece_at(chess.square(f, r))
                if p and p.piece_type == chess.PAWN and p.color == enemy:
                    return False
    return True

#king distance to center (for endgame centralization bonus when winning)
def king_centralization(board, color):
    king_sq = board.king(color)
    rank = chess.square_rank(king_sq)
    file = chess.square_file(king_sq)
    #distance from center (3.5, 3.5)
    center_dist = max(abs(rank - 3.5), abs(file - 3.5))
    return -center_dist * 0.1  # closer to center = higher bonus

#king proximity to enemy king (for endgame mating)
def king_proximity_bonus(board, color):
    my_king = board.king(color)
    enemy_king = board.king(not color)
    dist = max(abs(chess.square_rank(my_king) - chess.square_rank(enemy_king)),
               abs(chess.square_file(my_king) - chess.square_file(enemy_king)))
    return -dist * 0.05  # closer = higher bonus (less negative)

#MVV-LVA score for capture ordering
def mvv_lva_score(board, move):
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    if victim is None:  # en passant
        return 1.0
    victim_val = piece_values.get(victim.piece_type, 0)
    attacker_val = piece_values.get(attacker.piece_type, 0) if attacker else 0
    return victim_val - attacker_val / 10

#order moves: captures by MVV-LVA first, then killer moves, then quiet moves
def order_moves(board, legal_moves, depth=0):
    captures = []
    killers = []
    quiet = []
    depth_killers = killer_moves.get(depth, [])
    for move in legal_moves:
        if board.is_capture(move):
            captures.append(move)
        elif move in depth_killers:
            killers.append(move)
        else:
            quiet.append(move)
    captures.sort(key=lambda m: mvv_lva_score(board, m), reverse=True)
    return captures + killers + quiet

#store a killer move for a given depth
def store_killer(move, depth):
    if depth not in killer_moves:
        killer_moves[depth] = []
    killers = killer_moves[depth]
    if move not in killers:
        killers.insert(0, move)
        if len(killers) > 2:
            killers.pop()

#returns the value of the adjusted material of a specified color
def get_adj_material(board, color, phase):
    material_value = 0
    bishop_count = 0
    pawn_files = []
    end_game = phase < 0.3

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color:
            continue

        #base piece value + piece-square table bonus
        material_value += piece_values[piece.piece_type]
        material_value += get_pst_value(piece.piece_type, square, color, phase)

        if piece.piece_type == chess.PAWN:
            pawn_files.append(chess.square_file(square))
            #passed pawn bonus
            if is_passed_pawn(board, square, color):
                row = chess.square_rank(square)
                advancement = row if color == chess.WHITE else (7 - row)
                bonus = 1.0 if end_game else 0.5
                material_value += bonus * (advancement / 6)
        elif piece.piece_type == chess.BISHOP:
            bishop_count += 1
        elif piece.piece_type in [chess.BISHOP, chess.QUEEN, chess.ROOK]:
            mobility = len(board.attacks(square))
            material_value += 0.2 * (mobility**0.5)

    #bishop pair bonus
    if bishop_count >= 2:
        material_value += 0.3

    #pawn structure penalties
    for f in range(8):
        count = pawn_files.count(f)
        if count >= 2:
            material_value -= 0.3 * (count - 1)  #doubled pawns
    for f in pawn_files:
        has_neighbor = (f - 1) in pawn_files or (f + 1) in pawn_files
        if not has_neighbor:
            material_value -= 0.2  #isolated pawn

    if board.has_kingside_castling_rights(color):
        material_value += can_castle_reward
    if board.has_queenside_castling_rights(color):
        material_value += can_castle_reward

    if not end_game:
        material_value -= calculate_king_safety(board, color)**0.75

    #endgame king bonuses
    if end_game:
        material_value += king_centralization(board, color)
        material_value += king_proximity_bonus(board, color)

    return material_value


#evaluation function: how much white is beating black
def evaluate(board, phase):
    black_material = get_adj_material(board, chess.BLACK, phase)
    white_material = get_adj_material(board, chess.WHITE, phase)
    return white_material - black_material

#quiescence search: extend search with captures only until position is quiet
def quiescence(board, color, alpha, beta, phase, depth=0):
    stand_pat = evaluate(board, phase)

    if color == 'White':
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
    else:
        if stand_pat <= alpha:
            return alpha
        if stand_pat < beta:
            beta = stand_pat

    if depth <= -3:
        return stand_pat

    #delta pruning: if even capturing a queen can't improve position, skip
    DELTA = 9
    if color == 'White' and stand_pat + DELTA < alpha:
        return alpha
    if color != 'White' and stand_pat - DELTA > beta:
        return beta

    capture_moves = [m for m in board.legal_moves if board.is_capture(m) or m.promotion]
    capture_moves.sort(key=lambda m: mvv_lva_score(board, m), reverse=True)

    for move in capture_moves:
        board.push(move)
        score = quiescence(board, 'Black' if color == 'White' else 'White',
                          alpha, beta, phase, depth - 1)
        board.pop()

        if color == 'White':
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        else:
            if score <= alpha:
                return alpha
            if score < beta:
                beta = score

    return alpha if color == 'White' else beta

#mini max with alpha beta pruning, transposition table, null move pruning, check extensions, and LMR
def mini_max(board, color, depth=5, alpha=float('-inf'), beta=float('inf'), phase=1.0, null_move_allowed=True, ply=0):
    global transposition_table

    MAX_PLY = 40  #absolute depth cap to prevent recursion overflow

    #repetition detection - penalize repeated positions
    if board.is_repetition(2):
        return -0.5 if color == 'White' else 0.5

    if depth == 0 or board.is_game_over() or ply >= MAX_PLY:
        if board.is_checkmate():
            return -9999 if color == 'White' else 9999
        elif board.is_game_over():
            return 0
        else:
            return quiescence(board, color, alpha, beta, phase)

    in_check = board.is_check()

    #check extension: don't reduce depth when in check (limit to avoid blowup)
    if in_check and ply < MAX_PLY - 5:
        depth += 1

    #endgame depth extension (only apply once via ply check)
    if phase < 0.3 and ply == 0:
        depth += 1

    #transposition table lookup
    tt_key = board._transposition_key()
    if tt_key in transposition_table:
        tt_depth, tt_score, tt_flag = transposition_table[tt_key]
        if tt_depth >= depth:
            if tt_flag == EXACT:
                return tt_score
            elif tt_flag == LOWERBOUND:
                alpha = max(alpha, tt_score)
            elif tt_flag == UPPERBOUND:
                beta = min(beta, tt_score)
            if alpha >= beta:
                return tt_score

    #null move pruning: skip when in check, endgame, or low depth
    NULL_MOVE_R = 2
    if null_move_allowed and not in_check and phase >= 0.3 and depth >= 3:
        board.push(chess.Move.null())
        null_color = 'Black' if color == 'White' else 'White'
        null_score = mini_max(board, null_color, depth - 1 - NULL_MOVE_R, alpha, beta,
                             phase=phase, null_move_allowed=False, ply=ply+1)
        board.pop()
        if color == 'White' and null_score >= beta:
            return beta
        if color != 'White' and null_score <= alpha:
            return alpha

    legal_moves = order_moves(board, list(board.legal_moves), depth)

    if color == 'White':
        max_eval = float('-inf')
        for move_idx, move in enumerate(legal_moves):
            board.push(move)

            #late move reductions: reduce depth for quiet moves searched later
            reduction = 0
            if (move_idx >= 3 and depth >= 3 and not in_check
                    and not board.is_capture(move) and not board.is_check()):
                reduction = 1

            eval_ = mini_max(board, 'Black', depth - 1 - reduction, alpha, beta, phase=phase, ply=ply+1)

            #re-search at full depth if reduced search beats alpha
            if reduction > 0 and eval_ > alpha:
                eval_ = mini_max(board, 'Black', depth - 1, alpha, beta, phase=phase, ply=ply+1)

            board.pop()
            max_eval = max(max_eval, eval_)
            alpha = max(alpha, eval_)
            if beta <= alpha:
                if not board.is_capture(move):
                    store_killer(move, depth)
                break
        #store in transposition table
        if max_eval <= alpha:
            tt_flag = UPPERBOUND
        elif max_eval >= beta:
            tt_flag = LOWERBOUND
        else:
            tt_flag = EXACT
        if len(transposition_table) >= TT_MAX_SIZE:
            transposition_table.clear()
        transposition_table[tt_key] = (depth, max_eval, tt_flag)
        return max_eval
    else:
        min_eval = float('inf')
        for move_idx, move in enumerate(legal_moves):
            board.push(move)

            #late move reductions
            reduction = 0
            if (move_idx >= 3 and depth >= 3 and not in_check
                    and not board.is_capture(move) and not board.is_check()):
                reduction = 1

            eval_ = mini_max(board, 'White', depth - 1 - reduction, alpha, beta, phase=phase, ply=ply+1)

            #re-search at full depth if reduced search beats beta
            if reduction > 0 and eval_ < beta:
                eval_ = mini_max(board, 'White', depth - 1, alpha, beta, phase=phase, ply=ply+1)

            board.pop()
            min_eval = min(min_eval, eval_)
            beta = min(beta, eval_)
            if beta <= alpha:
                if not board.is_capture(move):
                    store_killer(move, depth)
                break
        if min_eval <= alpha:
            tt_flag = UPPERBOUND
        elif min_eval >= beta:
            tt_flag = LOWERBOUND
        else:
            tt_flag = EXACT
        if len(transposition_table) >= TT_MAX_SIZE:
            transposition_table.clear()
        transposition_table[tt_key] = (depth, min_eval, tt_flag)
        return min_eval


# call mini_max to get the best move using iterative deepening
def get_best_move(board, depth=5):
    global transposition_table, killer_moves
    transposition_table = {}
    killer_moves = {}

    #opening move: play e4/d4 as White, respond e5/d5 as Black
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

    current_color = 'White' if board.turn == chess.WHITE else 'Black'
    phase = get_game_phase(board)
    best_move = None

    #iterative deepening: search depth 1, 2, ... up to max depth
    #TT from previous iterations naturally improves move ordering
    for current_depth in range(1, depth + 1):
        current_best_move = None
        best_value = float('-inf') if board.turn == chess.WHITE else float('inf')

        legal_moves = order_moves(board, list(board.legal_moves))

        for move in legal_moves:
            board.push(move)
            if board.is_checkmate():
                board.pop()
                return move
            board_value = mini_max(board, 'Black' if current_color == 'White' else 'White',
                                  current_depth - 1, phase=phase)
            board.pop()

            if current_color == 'White':
                if board_value > best_value:
                    best_value = board_value
                    current_best_move = move
            else:
                if board_value < best_value:
                    best_value = board_value
                    current_best_move = move

        if current_best_move is not None:
            best_move = current_best_move

    return best_move
