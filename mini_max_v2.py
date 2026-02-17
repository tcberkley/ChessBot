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
def get_adj_material(board,color):
    material_value = 0
    for piece in piece_values:
        piece_positions = board.pieces(piece, color)
        if piece == chess.PAWN:
            for pos in piece_positions:
                row = pos // 8
                col = pos % 8
                material_value += piece_values[piece] * pawn_mult[row][col]
        elif piece == chess.KNIGHT:
            for pos in piece_positions:
                row = pos // 8
                col = pos % 8
                material_value += piece_values[piece] * knight_mult[row][col]
        else:
            material_value += len(piece_positions) * piece_values[piece]
    return material_value

#evaluation funciton: how much white is beating black
def evaluate(board):
    black_material = get_adj_material(board,chess.BLACK)
    white_material = get_adj_material(board,chess.WHITE)
    return white_material - black_material

#mini max like algo
def mini_max(board,color,depth=5):
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            if color == 'White':
                return float('-inf')
            else:
                return float('inf')
        return evaluate(board)
    
    if color == 'White':
        max_eval = float('-inf')
        for move in board.legal_moves:
            board.push(move)
            eval_ = mini_max(board,'Black',depth - 1)
            board.pop()
            max_eval = max(max_eval, eval_)
        return max_eval
    else:
        min_eval = float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_ = mini_max(board,'White',depth - 1)
            board.pop()
            min_eval = min(min_eval, eval_)
        return min_eval

# call mini_max to get the best move
def get_best_move(board,depth=5):
    best_move = None
    best_value = -9999 if board.turn == chess.WHITE else 9999
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
    