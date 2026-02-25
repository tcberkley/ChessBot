# Chess Bot — tombot1234

A Lichess bot powered by a custom C chess engine (v20), running on a Hetzner cloud server. The engine uses magic bitboards, advanced search techniques (Lazy SMP, singular extensions, probcut), and a Texel-tuned evaluation function.

**Lichess profile:** [tombot1234](https://lichess.org/@/tombot1234)

---

## Origin

Started as a Python minimax bot to brush up on Python skills before starting work. Two years later, Claude Code helped rewrite the entire thing in C and it now runs 24/7 on Lichess as `tombot1234`.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Lichess.org                         │
│  (challenges, game streams, opening explorer, EGTB)  │
└───────────────────────┬─────────────────────────────┘
                        │ HTTPS / NDJSON streaming
┌───────────────────────▼─────────────────────────────┐
│           lichess-bot-master/  (Python)              │
│  lichess-bot.py — main loop                          │
│  lib/lichess_bot.py — event handling                 │
│  lib/matchmaking.py — outgoing challenge logic       │
│  lib/engine_wrapper.py — UCI communication           │
│  extra_game_handlers.py — custom challenge filter    │
└───────────────────────┬─────────────────────────────┘
                        │ stdin/stdout (UCI)
┌───────────────────────▼─────────────────────────────┐
│           c_rewrite/v20_engine  (C)                  │
│  Magic bitboard move generation (BBC foundation)     │
│  Negamax + PVS, iterative deepening, Lazy SMP        │
│  Texel-tuned evaluation (744 parameters)             │
└─────────────────────────────────────────────────────┘

Server: Hetzner CPX11 (2 vCPU, Ubuntu 24.04)
Service: systemd lichess-bot
```

---

## Engine Features (v20)

### Move Generation
- Magic bitboard attack tables (BBC 1.0 foundation by Code Monkey King)
- Full pseudo-legal generation with in-check filter
- Zobrist hashing with transposition table (4M clustered entries, 64 MB)

### Search

| Technique | Details |
|---|---|
| Negamax + PVS | Principal Variation Search |
| Iterative deepening | With aspiration windows (±25cp, widening on fail) |
| Lazy SMP | 2 threads sharing TT/history/killers |
| Null move pruning | Adaptive R = 3 + depth/6 |
| Late Move Reductions | History-adjusted LMR |
| Late Move Pruning | Quiet moves pruned at low depth |
| Futility pruning | Reverse futility + standard futility |
| Razoring | At depth 1–3 |
| Probcut | At non-PV nodes depth ≥ 5 |
| Singular extensions | At depth ≥ 8 |
| TT pre-try | Before move generation when TT hit is singular |
| SEE | Static Exchange Evaluation for capture ordering/pruning |

### Move Ordering
1. TT move
2. Winning captures (SEE ≥ 0) — MVV-LVA
3. Killer moves (2 per ply)
4. Countermove
5. Quiet moves (history + continuation history)
6. Losing captures (SEE < 0)

### Evaluation (Texel-tuned)
- Tapered piece-square tables (middlegame ↔ endgame interpolation)
- Pawn structure: doubled, isolated, backward pawns; passed pawns with king proximity
- Pawn hash table (8192 entries)
- King safety: attack count, open files near king, pawn shield
- Piece activity: rook on 7th, bishop pair, mobility
- Threat detection: undefended/hanging pieces
- Mop-up evaluation (bare king endgames)
- Tempo bonus (+10cp for side to move in search)

### Texel Tuning
- Coordinate descent over **744 parameters**
- Training: ~1M positions from master games (EPD format)
- Converged at epoch 28, MSE 0.19530
- Result: **+35 Elo vs v19** (1800 games with opening book)

### Time Management
- Dynamic allocation based on clock, increment, and move number
- Easy-move detection: exits early when best move is stable across iterations
- Panic mode for sub-10s no-increment games (capped at 50–250ms per move)

---

## Version History

| Version | Key Additions |
|---|---|
| v13 | Initial C rewrite; BBC foundation, UCI protocol, ~1.3M nodes/sec |
| v14 | Reverse futility pruning, aggressive time management, 64 MB TT |
| v15 | Rook/knight bonuses, backward pawns, tapered PSTs |
| v16 | SEE, IID, aspiration windows, draw detection (50-move, repetition) |
| v17 | Adaptive null move R, countermove heuristic, history gravity, king attack count |
| v18 | TT pre-try, Probcut, pawn hash table, lazy eval, capture/continuation history, Lazy SMP |
| v18+SE | Singular extensions |
| v19 | Razoring, history-adjusted LMR, Late Move Pruning, king tropism, passed pawn king proximity, threat detection |
| v20 | Texel tuning (coordinate descent, 744 parameters, MSE 0.19530), +35 Elo vs v19 |

---

## Deployment

### Server
- **Host:** Hetzner CPX11 — `root@178.156.243.29` (Ubuntu 24.04)
- **Service:** `systemctl status lichess-bot`
- **Engine threads:** 2 (Lazy SMP, both vCPUs)

### Deploy a New Engine Version

```bash
# 1. Add SSH key
ssh-add ~/.ssh/id_ed25519

# 2. Transfer source
scp c_rewrite/vN_engine.c c_rewrite/Makefile root@178.156.243.29:~/c_rewrite/

# 3. Compile on server (never copy Mac binary)
ssh root@178.156.243.29 "cd ~/c_rewrite && make clean && make vN_engine"

# 4. Update config
ssh root@178.156.243.29 "sed -i 's|vOLD|vN|g' ~/lichess-bot-master/config.yml"

# 5. Restart
ssh root@178.156.243.29 "systemctl restart lichess-bot"

# 6. Verify
ssh root@178.156.243.29 "journalctl -u lichess-bot -n 20 --no-pager"
```

### Cron Jobs (server)

| Schedule | Job |
|---|---|
| `0 0 * * *` | Restart lichess-bot (clears in-session decline filter) |
| `0 23 * * *` | Daily game summary email |
| `*/30 * * * *` | Auto-join bot-eligible tournaments |
| `*/15 * * * *` | Watchdog — restart if silent >30 min |

---

## Configuration

### Challenge Acceptance (incoming)

| Challenger | Rule |
|---|---|
| Human | Accepted at any rating (rated or casual) |
| Bot | Must be within ±300 of tombot1234's rating in that time control; rated games only |

Configured in `extra_game_handlers.py` and `config.yml`.

### Matchmaking (outgoing)

| Setting | Value |
|---|---|
| Rating window | ±200 of tombot1234's current rating in the time control |
| Minimum opponent rating | 1600 |
| Time controls | 30s, 1+0, 2+0, 2+1, 3+0, 3+1, 3+2, 5+0, 5+1, 5+2 |
| Mode | Rated only |
| Challenge timeout | 1.5 min between games |
| Decline filter | Fine (per time-control per opponent, resets at midnight) |
| Daily limit | ~250 (Lichess API limit); auto-throttles as volume increases |

### Online Resources
- **Opening explorer:** Lichess masters database (≥500 games per move)
- **Endgame tablebases:** Lichess online 7-piece syzygy

---

## Scripts

### `scripts/daily_summary.py`
Fetches the last 24h of rated games from the Lichess API and emails an HTML summary containing:
- W-L-D record, win %, net rating change
- Per-time-control breakdown
- Game-by-game table with links
- Challenges sent and received (from `challenge_log.csv`)

**Cron:** `0 23 * * *` (11 PM UTC)
**Requires:** `LICHESS_BOT_TOKEN`, `SUMMARY_EMAIL_SENDER`, `SUMMARY_EMAIL_APP_PASSWORD`, `SUMMARY_EMAIL_TO` in `.env`

### `scripts/join_bot_tournaments.py`
Polls the Lichess tournament API every 30 minutes and joins any upcoming arena tournaments that have bots enabled. Logs results to `join_bot_tournaments.log`.

**Cron:** `*/30 * * * *`
**Requires:** `LICHESS_TOURNAMENT_TOKEN` (separate token with `tournament:write` scope)

### `scripts/watchdog_lichess_bot.sh`
Checks the systemd journal for recent lichess-bot output. If the service has been silent for >30 minutes, it restarts the service and logs the event to `watchdog_lichess_bot.log`.

**Cron:** `*/15 * * * *`

---

## Challenge Log

Every outgoing and incoming challenge is logged to `/root/scripts/challenge_log.csv` at runtime by `lib/challenge_logger.py` and included in the daily email.

**Columns:** `timestamp_utc, direction, event, opponent, opponent_rating, opponent_is_bot, time_control, variant, rated, decline_reason, challenge_id`

**Events logged:**
- `outgoing / sent` — challenge we sent
- `outgoing / declined` — opponent declined our challenge
- `incoming / accepted` — we accepted an incoming challenge
- `incoming / declined` — we declined an incoming challenge

---

## Perft Verification

| Position | Depth | Nodes |
|---|---|---|
| Startpos | 5 | 4,865,609 |
| Kiwipete | 4 | 4,085,603 |
| CMK position | 3 | 62,379 |

Run with: `./v20_engine` → `position startpos` → `go perft 5`

---

## Development Workflow

### Running a Tournament (engine vs engine)
```bash
cd c_rewrite
python3 tournament.py
```

### Texel Tuning
```bash
cd c_rewrite
python3 run_tuner.py
```

### Building Locally (Mac — for testing only)
```bash
cd c_rewrite
make v20_engine
```
> **Never copy the Mac binary to the server** — always recompile with `make` on the server (`-march=native` differs between machines).

---

## Environment Variables

Stored in `lichess-bot-master/.env` on the server:

| Variable | Purpose |
|---|---|
| `LICHESS_BOT_TOKEN` | Bot API token (`bot:play` scope) |
| `LICHESS_TOURNAMENT_TOKEN` | Tournament token (`tournament:write` scope) |
| `SUMMARY_EMAIL_SENDER` | Gmail address for daily summary |
| `SUMMARY_EMAIL_APP_PASSWORD` | Gmail App Password |
| `SUMMARY_EMAIL_TO` | Recipient email address |

---

## Project Structure

```
Chess/
├── c_rewrite/
│   ├── v20_engine.c            # Current engine source
│   ├── Makefile
│   ├── tournament.py           # Engine vs engine testing
│   ├── run_tuner.py            # Texel tuning
│   └── generate_dataset.py     # Training data generation
├── lichess-bot-master/
│   ├── lichess-bot.py          # Entry point
│   ├── config.yml              # Bot configuration (gitignored)
│   ├── extra_game_handlers.py  # Custom challenge filter
│   └── lib/
│       ├── lichess_bot.py      # Main control loop
│       ├── matchmaking.py      # Challenge creation
│       ├── engine_wrapper.py   # UCI communication
│       ├── lichess.py          # API wrapper
│       ├── model.py            # Game/challenge models
│       └── challenge_logger.py # CSV challenge logging
├── scripts/
│   ├── daily_summary.py        # Email summary
│   ├── join_bot_tournaments.py # Tournament auto-join
│   └── watchdog_lichess_bot.sh # Service watchdog
└── notes.txt                   # Detailed version history and feature candidates
```
