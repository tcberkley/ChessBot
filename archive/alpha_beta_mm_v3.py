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
pawn_mult = [[round(1.4 - j/15,2) for i in range(8)] for j in range(8)]

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


#returns the value of the adjusted material of a specified color
def get_adj_material(board, color):
    material_value = 0
    for piece in piece_values:
        piece_positions = board.pieces(piece, color)
        for pos in piece_positions:
            row = pos // 8
            col = pos % 8
            if piece == chess.PAWN:
                material_value += piece_values[piece] * pawn_mult[row][col]
            elif piece == chess.KNIGHT:
                material_value += piece_values[piece] * knight_mult[row][col]
            elif piece in [chess.BISHOP, chess.QUEEN]:
                mobility = len(board.attacks(pos))
                material_value += piece_values[piece] + 0.2 * (mobility**0.5)
            else:
                material_value += piece_values[piece]
        material_value += 2.5
    return material_value


#evaluation funciton: how much white is beating black
def evaluate(board):
    black_material = get_adj_material(board,chess.BLACK)
    white_material = get_adj_material(board,chess.WHITE)
    return white_material - black_material

#mini max like algo - this one implements alpha beta pruning and sorts the moves
def mini_max(board, color, depth=5, alpha=float('-inf'), beta=float('inf')):
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            return -9999 if color == 'White' else 9999
        return evaluate(board)
    
    legal_moves = list(board.legal_moves)
    legal_moves.sort(key=lambda move: board.gives_check(move) or board.is_capture(move), reverse=True)
    
    if color == 'White':
        max_eval = float('-inf')
        for move in legal_moves:
            board.push(move)
            eval_ = mini_max(board, 'Black', depth - 1, alpha, beta)
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
            eval_ = mini_max(board, 'White', depth - 1, alpha, beta)
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
    