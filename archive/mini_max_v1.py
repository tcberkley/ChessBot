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

#returns the value of the adjusted material of a specified color
def get_material(board, piece_values, color):
    return sum([len(board.pieces(piece, color)) * piece_values[piece] for piece in piece_values])


#evaluation funciton: how much white is beating black
def evaluate(board,piece_values):
    black_material = get_material(board,piece_values,chess.BLACK)
    white_material = get_material(board,piece_values,chess.WHITE)
    return white_material - black_material

#simple random bot
def random_bot_v1(board):
    return random.choice(list(board.legal_moves))

#mini max like algo
def mini_max(board, color, depth=5):
    if depth == 0 or board.is_game_over():
        if board.is_checkmate():
            if color == 'White':
                return float('-inf')
            else:
                return float('inf')
        return evaluate(board,piece_values)
    
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
def get_best_move(board, depth=5):
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
    