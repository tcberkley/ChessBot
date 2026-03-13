# Chess Bot — Claude Instructions

## Scope
All work stays within `/Users/tomberkley/Desktop/CodeProjects/Chess/` and its subdirectories.
Do NOT read, write, or execute anything outside this tree without explicit user confirmation.

---

## Project Overview
- **Lichess bot**: `tombot1234` on Hetzner CPX11 (`178.156.243.29`, Ubuntu 24.04)
- **Engine**: C (BBC magic bitboard), UCI, multi-threaded (Lazy SMP + pondering)
- **Bridge**: Python `lichess-bot` in `bot/`
- **Current deployed**: `v2.4_engine` (~2300 Elo)
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
python3 tournament_v1.9.py --engine1 ./vTest_engine --engine2 ./v2.3_engine \
    --openings 25 --movetime 100 --seed 42 2>&1 | tail -8
```

**Keep if**: perft = 4865609 AND tournament ≥ 48%. Revert immediately otherwise.
**Baseline**: `engine/v2.3_engine` binary (copy before adding features: `cp vX.Y_engine vX.Y_baseline`)

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
| `v2.3_engine` | `v2.3_engine.c fathom.c` | Current deployed version |
| `v2.3_tuner` | `v2.3_engine.c fathom.c` | `-DTUNER` |
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
- **`score_move()` is shared** between negamax and qsearch — killers (900k) and countermoves (700k) are scored in both. In qsearch, killers sort above losing captures (500k), so the non-capture filter must use `continue` not `break` (otherwise killers trigger a full loop exit before reaching quiet promotions)
- **Qsearch lazy eval guard removed** (v2.2): the old `evaluate_lazy() ± 350` guard was aborting before captures in positions where stand_pat + best capture > alpha. Delta pruning (`stand_pat + 900 < alpha`) is sufficient and already present

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

### Singular Extensions (v2.2)
- SE margin: `se_tt_score - 8 * depth` (was 25)
- Double extension: `se_score < se_beta - 50` → `se_extension = 2`
- `se_extension` applied only to the TT pre-try search, not the main move loop
- `se_excluded_move` is `__thread`; `get_tt_info()` peeks raw TT without alpha/beta

---

## Key Search Parameters (v2.2)

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
| TT replacement | depth >= stored depth only (no EXACT free-eviction) |
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
| Connected/chained pawn bonus (rank-indexed 0→44) | 44.0% | 8-entry rank-indexed bonus for pawns defended by own pawn; clear regression vs v2.4 |
| History aging (÷16 all history tables) | 50.0% | Divide history/capture/cont_hist by 16 each search instead of clearing; perfectly neutral vs v2.4 |

---

## To-Do / Features to Try

| Feature | Notes |
|---------|-------|
| ~~Pawn shield (rank-indexed, per-file)~~ | Implemented in v2.4 (49.0% vs v2.3). 5 tunable params at tp[781-785] |
| Connected/chained pawn bonus | Bonus for pawns protecting each other (rank-indexed, 0→+44 range). We have isolated/doubled/backward but no chain bonus |
| ~~Backward pawns: open vs closed file~~ | Implemented in v2.4 (54.0%). TP_BACKWARD_PAWN=12 (closed), TP_BACKWARD_OPEN=30 (open) |
| ~~History aging~~ | Tested in v2.4 session (50.0% — neutral). ÷16 all history tables instead of clearing |
| **v2.3 search regression investigation** | v2.3 was only tested vs v2.2 (51%). Self-play shows v2.3 barely beats v2.1 (52.2%) and v2.2 is clearly weaker than v2.1 (35.4%). v2.3 inherits all 5 v2.2 changes — the TT replacement change (removed `\|\| flag == HASH_FLAG_EXACT`) is the prime suspect. Need formal 100-game tournament: `v2.3_engine vs v2.1_engine` at movetime 100ms to confirm whether v2.3's edge is engine or opening book. If opening book only, revert TT change in v2.4. |

---

## v2.2 Search Regression

v2.2 introduced 5 changes over v2.1. Tournament confirmed −10 Elo vs v2.1 (48.5%, 100 games) and v2.2 was deleted. All 5 changes were inherited by v2.3.

**The 5 changes:**
1. **OCB guard** (`wn==0 && bn==0`) — correct, low impact
2. **TT replacement** — removed `|| flag == HASH_FLAG_EXACT`. Prime suspect: prevents a fresh shallow EXACT entry from evicting a stale deep entry, possibly serving worse results during iterative deepening
3. **Qsearch lazy eval guard removed** — correct fix
4. **Qsearch `break` → `continue`** — correct fix (killers at 900k were triggering early exit)
5. **Killer dedup** (×2 sites) — small correctness fix, neutral

v2.3 was never tested directly vs v2.1. Its narrow self-play edge (52.2%) is likely from the opening book (c4), not search. The TT change should be the first thing reverted when investigating v2.4.

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
| v2.2 | Six correctness fixes: OCB scaling (wn==0&&bn==0 guard), qsearch lazy eval guard removed, qsearch break→continue, TT replacement (no EXACT free-eviction), killer dedup (×2 sites) | ~2300 |
| v2.3 | Opening book: c4 as white (58% win rate), extended black responses; explorer source masters→player, min_games 500→5. Tournament 51.0% vs v2.2 | ~2300 |
| v2.4 | Rank-indexed pawn shield (5 params: rank1/2/3 bonus, missing penalty, king-file bonus) + backward pawn open/closed file split (12cp closed, 30cp open). Tournament: shield 49.0% vs v2.3, backward split 54.0% vs shield | ~2300 |

---

## Texel Tuning

```bash
# On server — bot goes DOWN during tuning (run_tuner.py stops lichess-bot)
# Compile tuner
make v2.3_tuner   # -DTUNER flag disables correction history and pondering

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
echo -e "position fen r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq -\ngo depth 12" | ./v2.3_engine

# Git workflow
git add engine/vX.Y_engine.c engine/Makefile
git commit -m "vX.Y: <description>"
git push
```
