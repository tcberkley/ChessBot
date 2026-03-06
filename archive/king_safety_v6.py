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
home_square_penalty = 1
can_castle_reward = 1
is_castling_reward = 5

#checks if it's endgame (to increase depth)
def is_endgame(board):
    return sum([1 for square in chess.SQUARES if board.piece_at(square)]) <= 8

#see how open the king is (higher is worse)
def calculate_king_safety(board, color):
    test_board = board.copy()
    test_board.turn = color
    king_square = board.king(color)
    test_board.set_piece_at(king_square, chess.Piece(chess.QUEEN, color))
    attacked_squares = len([move for move in test_board.legal_moves if move.from_square == king_square])
    return attacked_squares

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
        elif piece.piece_type == chess.KNIGHT:
            material_value += piece_values[chess.KNIGHT] * knight_mult[row][col]
        elif piece.piece_type in [chess.BISHOP, chess.QUEEN]:
            legal_moves = [move for move in board.legal_moves if move.from_square == square]
            mobility = len(legal_moves)
            material_value += piece_values[piece.piece_type] + 0.2 * (mobility**0.5)
        else:
            material_value += piece_values[piece.piece_type]
            
    if color == chess.WHITE:
        if board.has_kingside_castling_rights(chess.WHITE):
            material_value += can_castle_reward
        if board.has_queenside_castling_rights(chess.WHITE):
            material_value += can_castle_reward
    else:
        if board.has_kingside_castling_rights(chess.BLACK):
            material_value += can_castle_reward
        if board.has_queenside_castling_rights(chess.BLACK):
            material_value += can_castle_reward
    
    if end_game==False:
        material_value -= calculate_king_safety(board, color)**0.75

    return material_value


#evaluation funciton: how much white is beating black
def evaluate(board,end_game):
    black_material = get_adj_material(board,chess.BLACK,end_game)
    white_material = get_adj_material(board,chess.WHITE,end_game)
    return white_material - black_material

#mini max like algo - this one implements alpha beta pruning and sorts the moves (castling incentive)
def mini_max(board, color, depth=5, alpha=float('-inf'), beta=float('inf'), end_game=False):
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return -9999 if color == 'White' else 9999
        elif board.is_game_over():
            return 0
        else:
            return evaluate(board, end_game=end_game)
    
    if is_endgame(board) and not end_game:
        depth += 2
        end_game = True
        
    legal_moves = list(board.legal_moves)
    legal_moves.sort(key=lambda move: board.gives_check(move) or board.is_capture(move), reverse=True)
    
    if color == 'White':
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            
            if board.is_castling(move):
                eval_ = is_castling_reward + mini_max(board, 'Black', depth - 1, alpha, beta, end_game=end_game)
            else:
                eval_ = mini_max(board, 'Black', depth - 1, alpha, beta, end_game=end_game)
            board.pop()
            max_eval = max(max_eval, eval_)
            alpha = max(alpha, eval_)
            if beta <= alpha:
                break 
        return max_eval
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            if board.is_castling(move):
                eval_ = -is_castling_reward + mini_max(board, 'White', depth - 1, alpha, beta, end_game=end_game)
            else:
                eval_ = mini_max(board, 'White', depth - 1, alpha, beta, end_game=end_game)
            board.pop()
            min_eval = min(min_eval, eval_)
            beta = min(beta, eval_)
            if beta <= alpha:
                break 
        return min_eval


# call mini_max to get the best move
def get_best_move(board,depth=5):
    best_move = None
    best_value = float('-inf') if board.turn == chess.WHITE else float('inf')
    current_color = 'White' if board.turn == chess.WHITE else 'Black'
    
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            board.pop()
            return move
        board_value = mini_max(board, 'Black' if current_color == 'White' else 'White',depth - 1)
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
    