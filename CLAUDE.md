# Chess Bot — Claude Instructions

## Scope
All work stays within `/Users/tomberkley/Desktop/CodeProjects/Chess/` and its subdirectories.
Do NOT read, write, or execute anything outside this tree without explicit user confirmation.

---

## Project Overview
- **Lichess bot**: `tombot1234` on Hetzner CPX11 (`178.156.243.29`, Ubuntu 24.04)
- **Engine**: C (BBC magic bitboard), UCI, multi-threaded (Lazy SMP + pondering)
- **Bridge**: Python `lichess-bot` in `bot/`
- **Current deployed**: `v2.1_engine` (~2300 Elo)
- **Engine source**: `engine/` | **Fathom Syzygy lib**: `engine/fathom*.{h,c}` + `tbconfig.h` `tbchess.c` `stdendian.h`

---

## Deployment Workflow

```bash
# 1. SSH key is stored in macOS keychain — no manual ssh-add needed.
#    If it ever stops working: ssh-add --apple-use-keychain ~/.ssh/id_ed25519

# 2. Transfer source (fathom files needed for v2.0+)
scp engine/vX.Y_engine.c engine/Makefile \
    engine/fathom.h engine/fathom.c engine/tbconfig.h \
    engine/tbchess.c engine/stdendian.h \
    root@178.156.243.29:~/c_rewrite/

# 3. Compile on server (NEVER copy Mac binary — always recompile)
ssh root@178.156.243.29 "cd ~/c_rewrite && make clean && make vX.Y_engine"

# 4. Verify perft on server
ssh root@178.156.243.29 "echo -e 'position startpos\nperft 5' | ~/c_rewrite/vX.Y_engine | tail -3"
# Must print: Nodes: 4865609

# 5. Update config and restart
ssh root@178.156.243.29 "sed -i 's|vOLD|vNEW|g' ~/lichess-bot-master/config.yml"
ssh root@178.156.243.29 "systemctl restart lichess-bot"
ssh root@178.156.243.29 "journalctl -u lichess-bot -n 20 --no-pager"
```

---

## Testing Protocol (per search feature)

```bash
cd engine

# 1. Compile
make vTest_engine

# 2. Correctness — must equal 4865609
echo -e "position startpos\nperft 5" | ./vTest_engine | tail -3

# 3. Tournament vs baseline (50 games, 100ms, 25 opening pairs)
python3 tournament_v1.9.py --engine1 ./vTest_engine --engine2 ./v2.1_baseline \
    --openings 25 --movetime 100 --seed 42 2>&1 | tail -8
```

**Keep if**: perft = 4865609 AND tournament ≥ 48%. Revert immediately otherwise.
**Baseline binary**: `engine/v2.1_baseline` (copy before adding features: `cp vX.Y_engine vX.Y_baseline`)

### Perft Reference Values
| Position | Depth | Nodes |
|----------|-------|-------|
| startpos | 5 | 4,865,609 |
| Kiwipete | 4 | 4,085,603 |
| pos3 | 6 | 11,030,083 |
| CMK (`rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8`) | 3 | 62,379 |

---

## Makefile Targets

| Target | Source | Notes |
|--------|--------|-------|
| `vTest_engine` | `vTest_engine.c fathom.c` | Working test file — modify freely |
| `v2.1_engine` | `v2.1_engine.c fathom.c` | Current deployed version |
| `v2.1_tuner` | `v2.1_engine.c fathom.c` | `-DTUNER` |
| `vTest_tuner` | `vTest_engine.c` | `-DTUNER`, no fathom |

Compile flags: `-O3 -march=native -fomit-frame-pointer -pthread`

**Workflow**: cp vX.Y_engine.c → vTest_engine.c → test → cp vTest_engine.c → vX.(Y+1)_engine.c

---

## Critical Engine Gotchas

### Threading / TLS
- **ALL board state is `__thread` TLS** (bitboards, occupancies, side, hash_key, etc.)
- New pthreads start zero-initialized — MUST call `copy_master_to_thread()` after main thread calls `save_board_to_master()`
- `pawn_table` is intentionally shared (benign races, no clear on ucinewgame)

### Search Correctness
- `copy_board` / `take_back` are **macros** (stack-based). Both the caller and `make_move` have their own copies
- `make_move()` returns 0 if resulting king is in check and internally restores board — always check the return value; if 0, also decrement `repetition_index` before continuing
- `pv_length[0]` can be 0 even when `pv_table[0][0]` is valid (timer fires before length is set) — use `pv_table[0][0]` to check for valid best move
- **Tempo bonus (+10)**: goes in the negamax futility block ONLY — NOT in `evaluate()` (breaks qsearch stand_pat)
- `go infinite` does NOT stop mid-search (check_time doesn't read stdin by design)

### Pondering
- python-chess sends `go ponder wtime X btime Y` — detect with `strncmp(cmd,"go ponder",9)`
- TT collisions: ponder TT entries can inject illegal moves. Fix: `is_tt_move_valid()` at BOTH TT probe sites in negamax + IID
- Guard `read_input()` with `if (is_pondering) return` to prevent stdin race
- `parse_position()` must check `make_move()` return value — silent failure causes search from wrong position
- Validate `best_ponder_move` before output: `copy_board(); make_move(bm); is_tt_move_valid(ponder); take_back()`
- Ponder early-finish: if search completes all depths before `ponderhit`, loop reading commands and handle `position` inline

### BBC Conventions
- Squares: a8=0, h1=63 (BBC standard) vs fathom: a1=0
- Fathom conversion: bitboards via `__builtin_bswap64()`, individual squares via `XOR 56`
- Pawn shifts: white `>>9 & ~file_masks[7]` (not_h_file), `>>7 & ~file_masks[0]` (not_a_file); black opposite

### Singular Extensions (v2.1)
- SE margin: `se_tt_score - 8 * depth` (was 25)
- Double extension: `se_score < se_beta - 50` → `se_extension = 2`
- `se_extension` applied only to the TT pre-try search, not the main move loop
- `se_excluded_move` is `__thread`; `get_tt_info()` peeks raw TT without alpha/beta

---

## Key Search Parameters (v2.1)

| Feature | Value |
|---------|-------|
| Null move R | `3 + depth/6 + (!improving)` |
| LMR | table-based, `reduction -= hist/8192`, cap at `depth−1` |
| LMP thresholds | `{0, 5, 10, 18}` + `improving*3` |
| Razoring | depth==1, margin=450 |
| IIR | non-PV, no TT move, depth≥4 → depth−1 |
| SE margin | `8 * depth` |
| Double extension | `se_score < se_beta − 50` |
| Phase-aware futility | `fm * (4 + game_phase) / 16` when phase<12 |
| Improving flag | `raw_eval > static_evals_by_ply[ply-2]` |
| Correction history | CORR_SIZE=16384, CORR_GRAIN=256, CORR_MAX=1024 |
| TT size | 64MB |
| Syzygy tables | `~/syzygy` on server (145 .rtbw + 145 .rtbz, ~680MB) |

---

## Features Tested and Rejected (do not re-implement without good reason)

| Feature | Result | Notes |
|---------|--------|-------|
| PV LMR modifier (reduce−1 at PV) | 53% | Reverted v2.0 session |
| Recapture extension | 48% | Reverted v2.1 session |
| Multi-cut pruning (M=3, C=2) | 43% | Clear regression |
| Qsearch checks at depth −1 | 52% | Expensive make_move+is_in_check filter per quiet move |
| Null move verification search | 47% | Adds nodes at every null cutoff |
| 2-ply continuation history | 47.8% | Reverted v2.1 (old) session |
| Capture pruning | 47.5% | Reverted v2.1 (old) session |
| SEE-weighted capture history | 44.0% | Winning SEE→bonus, losing SEE→malus; clear regression vs v2.2 |
| Aspiration window time guard (0.7→0.5) | 45.0% | Guard already existed at 0.7; tightening to 0.5 hurts (bails too early) |
| King virtual mobility (middlegame, 5cp/missing square) | 44.0% | (8−mob)×5 penalty in MG king safety; not discriminating enough vs v2.2 |

---

## Engine Version History

| Version | Key additions | Est. Elo |
|---------|--------------|----------|
| v1.0 | C rewrite, BBC, UCI, ~1.3M nps | ~1940 |
| v1.1 | Time management, -march=native, 64MB TT, reverse futility | ~2090 |
| v1.2 | Rook bonuses, knight outpost, backward pawns, tapered PSTs | ~2110 |
| v1.3 | IID, aspiration widening, score instability detection | ~2100 |
| v1.4 | SEE, king attack count, adaptive null move R, countermove, history malus+gravity, tempo, bad bishop | ~2130 |
| v1.5 | Lazy SMP, pawn hash, Probcut, cont history, capture history, TT pre-try, Singular Extensions | ~2105 |
| v1.6 | Razoring, history-adjusted LMR, LMP, king tropism, passed pawn proximity, mop-up eval, threat detection | ~2075 |
| v1.7 | Texel-tuned PSTs (Lichess DB, 1M positions, K=844, 28 epochs) | ~2110 |
| v1.8 | Pondering (TT collision fix, ponder move validation, early-finish loop) | ~2120 |
| v1.9 | Clock-differential time management (1.08–1.25× budget when ahead) | ~2115 |
| v1.10 | Mate Distance Pruning, ETT cache (128K), endgame scaling, safe mobility | ~2130 |
| v1.11 | King area threats, rank-indexed passed pawn tables, inner/outer mobility, minor→heavy attack bonus; full Texel retune 781 params | ~2155 |
| v2.0 | Syzygy WDL probing (fathom), root TB probe, mate-in-X chat, improving flag | ~2225 |
| v2.1 | IIR, razoring 450, SE margin 8×depth, double extension, phase-aware futility | ~2300 |

---

## Texel Tuning

```bash
# On server — bot goes DOWN during tuning (run_tuner.py stops lichess-bot)
# Compile tuner
make v2.1_tuner   # -DTUNER flag disables correction history and pondering

# Dataset: ~/c_rewrite/dataset_pgn.txt (1M quiet positions, Lichess DB ≥2000 Elo ≥3min)
# Script:  engine/run_tuner.py  (emails hourly MSE plot)
# Env:     /root/lichess-bot-master/.env  (SUMMARY_EMAIL_* vars)
```

After tuning: verify `perft 5 = 4865609`, run tournament, update `tp[]` array comment with MSE.

---

## Bot Configuration

- **Challenge filter** (`bot/extra_game_handlers.py`): humans always accepted; bots ≥1600 rated only
- **Matchmaking** (`config.yml`): `opponent_min_rating: 1600`
- **Rate limit fix** (`lichess_bot.py`): HTTP 429 on event stream → sleep 60s (not crash)

---

## Common Commands

```bash
# Check bot logs on server
ssh root@178.156.243.29 "journalctl -u lichess-bot -n 50 --no-pager"

# Quick engine benchmark (Kiwipete depth 12)
echo -e "position fen r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -\ngo depth 12" | ./v2.1_engine

# Git workflow
git add engine/vX.Y_engine.c engine/Makefile
git commit -m "vX.Y: <description>"
git push
```
