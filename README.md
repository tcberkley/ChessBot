Project Description:

This was a project that I decided to build to touch up on my python before I started working. 

The bot uses the mini max algorithm to navigate decision trees and an evaluation function that returns the "score" of a position (node on the decision tree).
On top of that, I implemented some "pruning techniques" that speed up the search for the best move. 
Pruning generally prevents the bot from examining parts of the decision tree where a "bad move" (ex. unnecessarily sacrificing the queen) has already taken place.

------------
How to play:

chess_game.ipynb - 
  File where user can play against the chess bot of choosing. This defaults to king_safety_v6, the strongest bot.
  However the bot can be chosen by changing the line in the second cell: "bot_move = king_safety_v6.get_best_move(board,depth=5)" into, for example,
  "bot_move = castle_bot_v5.get_best_move(board,depth=5)".

-----------
Dependencies:
- Python 3.x
- `python-chess` (`chess`)
  - Install using `pip install python-chess`
- `svgwrite` (for generating SVGs)
  - Install using `pip install svgwrite`
- `IPython` (for displaying SVGs in Jupyter notebooks)
  - Install using `pip install ipython`
- `random` (standard Python library)
- `time` (standard Python library)
- All notebook files from this repository
  
-----------------
Bot Descriptions:

Random Bot - Makes a random move every turn

mini_max_v1 - Uses mini max algo to find best position based on only material

mini_max_v2 - Uses mini max algo to find best position based on material and position of knights and pawns, but does so incorrectly

alpha_beta_mm_v3 - Uses alpha/beta pruning to speed up algo. Incentivizes good positioning for queen and bishop

endgame_faster_v4 - Searches deeper in the endgame, optimizes get_adj_material algo

castle_bot_v5 - rewards abaility to castle (1 point per side), rewards castling more (5 points)

king_safety_v6 - rewards king safety, removes castling incentive, fixes material evaluation error
