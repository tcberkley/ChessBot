Project Description:

This was a project that I decided to build to touch up on my python before I started working. 

The bot uses the mini max algorithm to navigate decision trees and an evaluation function that returns the "score" of a position (node on the decision tree).
On top of that, I implemented some "pruning techniques" that speed up the search for the best move. 
Pruning generally prevents the bot from examining parts of the decision tree where a "bad move" (ex. unnecessarily sacrificing the queen) has already taken place.

------------

Two years later, I let Claude Code make some improvements and rewrite the whole thing in C. It now runs on lichess @tombot1234.
