import chess

board = chess.Board()

piece_values = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0
}

#pawn position value multiplier
pawn_mult = [[round(2 - j/5,2) for i in range(8)] for j in range(8)]

#knight position value multiplier
knight_mult = [
    [0.6, 0.6, 0.8, 0.8, 0.8, 0.8, 0.6, 0.6],
    [0.6, 0.8, 1.0, 1.0, 1.0, 1.0, 0.8, 0.6],
    [0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.0, 0.8],
    [0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.0, 0.8],
    [0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.0, 0.8],
    [0.8, 1.0, 1.2, 1.2, 1.2, 1.2, 1.0, 0.8],
    [0.6, 0.8, 1.0, 1.0, 1.0, 1.0, 0.8, 0.6],
    [0.6, 0.6, 0.8, 0.8, 0.8, 0.8, 0.6, 0.6]
]

#penalties/rewards
can_castle_reward = 1

#transposition table constants
EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2
transposition_table = {}

#checks if it's endgame (to increase depth)
def is_endgame(board):
    return sum([1 for square in chess.SQUARES if board.piece_at(square)]) <= 8

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

#order moves: captures by MVV-LVA first, then quiet moves
def order_moves(board, legal_moves):
    captures = []
    quiet = []
    for move in legal_moves:
        if board.is_capture(move):
            captures.append(move)
        else:
            quiet.append(move)
    captures.sort(key=lambda m: mvv_lva_score(board, m), reverse=True)
    return captures + quiet

#returns the value of the adjusted material of a specified color
def get_adj_material(board, color, end_game):
    material_value = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.color != color:
            continue

        row = square // 8
        col = square % 8

        if piece.piece_type == chess.PAWN:
            material_value += piece_values[chess.PAWN] * pawn_mult[row][col] * (1 if end_game else 1.2)
            #passed pawn bonus
            if is_passed_pawn(board, square, color):
                advancement = row if color == chess.WHITE else (7 - row)
                bonus = 1.0 if end_game else 0.5
                material_value += bonus * (advancement / 6)
        elif piece.piece_type == chess.KNIGHT:
            material_value += piece_values[chess.KNIGHT] * knight_mult[row][col]
        elif piece.piece_type in [chess.BISHOP, chess.QUEEN]:
            mobility = len(board.attacks(square))
            material_value += piece_values[piece.piece_type] + 0.2 * (mobility**0.5)
        elif piece.piece_type == chess.ROOK:
            mobility = len(board.attacks(square))
            material_value += piece_values[chess.ROOK] + 0.2 * (mobility**0.5)
        else:
            material_value += piece_values[piece.piece_type]

    if board.has_kingside_castling_rights(color):
        material_value += can_castle_reward
    if board.has_queenside_castling_rights(color):
        material_value += can_castle_reward

    if not end_game:
        material_value -= calculate_king_safety(board, color)**0.75

    return material_value


#evaluation function: how much white is beating black
def evaluate(board, end_game):
    black_material = get_adj_material(board, chess.BLACK, end_game)
    white_material = get_adj_material(board, chess.WHITE, end_game)
    return white_material - black_material

#quiescence search: extend search with captures only until position is quiet
def quiescence(board, color, alpha, beta, end_game, depth=0):
    stand_pat = evaluate(board, end_game)

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
                          alpha, beta, end_game, depth - 1)
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

#mini max with alpha beta pruning, transposition table, and repetition detection
def mini_max(board, color, depth=5, alpha=float('-inf'), beta=float('inf'), end_game=False):
    #repetition detection - penalize repeated positions
    if board.is_repetition(2):
        return -0.5 if color == 'White' else 0.5

    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return -9999 if color == 'White' else 9999
        elif board.is_game_over():
            return 0
        else:
            return quiescence(board, color, alpha, beta, end_game)

    if is_endgame(board) and not end_game:
        depth += 2
        end_game = True

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

    legal_moves = order_moves(board, list(board.legal_moves))

    if color == 'White':
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval_ = mini_max(board, 'Black', depth - 1, alpha, beta, end_game=end_game)
            board.pop()
            max_eval = max(max_eval, eval_)
            alpha = max(alpha, eval_)
            if beta <= alpha:
                break
        #store in transposition table
        if max_eval <= alpha:
            tt_flag = UPPERBOUND
        elif max_eval >= beta:
            tt_flag = LOWERBOUND
        else:
            tt_flag = EXACT
        transposition_table[tt_key] = (depth, max_eval, tt_flag)
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval_ = mini_max(board, 'White', depth - 1, alpha, beta, end_game=end_game)
            board.pop()
            min_eval = min(min_eval, eval_)
            beta = min(beta, eval_)
            if beta <= alpha:
                break
        if min_eval <= alpha:
            tt_flag = UPPERBOUND
        elif min_eval >= beta:
            tt_flag = LOWERBOUND
        else:
            tt_flag = EXACT
        transposition_table[tt_key] = (depth, min_eval, tt_flag)
        return min_eval


# call mini_max to get the best move
def get_best_move(board, depth=5):
    global transposition_table
    transposition_table = {}

    best_move = None
    best_value = float('-inf') if board.turn == chess.WHITE else float('inf')
    current_color = 'White' if board.turn == chess.WHITE else 'Black'

    legal_moves = order_moves(board, list(board.legal_moves))

    for move in legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board_value = mini_max(board, 'Black' if current_color == 'White' else 'White', depth - 1)
        board.pop()

        if current_color == 'White':
            if board_value > best_value:
                best_value = board_value
                best_move = move
        else:
            if board_value < best_value:
                best_value = board_value
                best_move = move

    return best_move
