import chess
import chess.svg
import os
import random
import time

from IPython.display import display, SVG, clear_output

from bots import mini_max_v1
from bots import mini_max_v2
from bots import alpha_beta_mm_v3
from bots import endgame_faster_v4
from bots import castle_bot_v5
from bots import king_safety_v6
from bots import quiescence_v7

#If you want to change the starting position
#Set endgame_fen to the fen associated position
endgame_fen = ""
board = chess.Board()

user_color_prompt = input("White or Black?: ")
if user_color_prompt.upper() in ["Black","B"]:
    user_color = "Black"
else:
    user_color = "White"
print(f"User will play as: {user_color}")
move_count = 1
move = ''
quit = False

while not board.is_game_over():
    user_turn = (user_color == 'White' and board.turn == chess.WHITE) or (user_color == 'Black' and board.turn == chess.BLACK)
    clear_output(wait=True)
    
    if move != '' and user_turn:
        print(f"\nBot move: {move}")

    if board.turn==chess.WHITE:
        print("\nWhite to move\n")
    else:
        print("\nBlack to move\n")
    display(SVG(chess.svg.board(board=board, size=400)))
    
    if user_turn:
        user_move = input("Enter your move: ")
        try:
            move = chess.Move.from_uci(user_move)
        except:
            pass
        if user_move.upper() in ["QUIT","Q"]:
            print("Bot wins")
            quit = True
            break
    else:
        bot_move = castle_bot_v5.get_best_move(board,depth=5)
        move = bot_move
        print(f"Bot move: {move}")
    
    if move in board.legal_moves:
        board.push(move)
        move_count+=1
    else:
        print("Illegal Move (Try again)")
        time.sleep(3)
        
clear_output(wait=True)
display(SVG(chess.svg.board(board=board, size=400)))
result = board.result()
if result == "1-0":
    print("White wins!")
elif result == "0-1":
    print("Black wins!")
elif quit:
    pass
else:
    print("It's a draw!")