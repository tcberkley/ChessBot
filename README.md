# Chess Bot — tombot1234

A chess bot running on Lichess, powered by a custom C engine with magic bitboards, advanced search, and Texel-tuned evaluation.

**Challenge it here:** [lichess.org/@/tombot1234](https://lichess.org/@/tombot1234)

---

## Features

**Engine (v20)**
- Magic bitboard move generation
- Negamax + Principal Variation Search
- Iterative deepening with aspiration windows
- Lazy SMP (2 threads)
- Null move pruning, LMR, LMP, futility pruning, razoring, probcut, singular extensions
- Static Exchange Evaluation (SEE) for capture ordering
- Killer moves, countermove, history heuristic, continuation history
- Texel-tuned evaluation (744 parameters, coordinate descent, +35 Elo vs prior version)
- Tapered piece-square tables (middlegame / endgame interpolation)
- Pawn hash table, king safety, passed pawns, bishop pair, mobility, threats
- Panic time management for sub-10s games

**Bot**
- Plays bullet, blitz, rapid, and classical
- Uses Lichess masters opening explorer and 7-piece online endgame tablebases
- Auto-challenges other bots; offers rematch after winning
- Daily game summary email
- Automatically joins bot-eligible Lichess tournaments

---

*Technical details, deployment instructions, and version history are in `notes.txt`.*
