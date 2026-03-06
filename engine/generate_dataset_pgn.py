#!/usr/bin/env python3
"""
Dataset generator for Texel tuning using the Lichess game database.

Streams a compressed PGN file from the Lichess database, decompresses on
the fly, and extracts quiet positions (not in check, last move not a capture
or promotion, ply >= 16) from high-quality rated games.

Output format: "<FEN> | <result>"
  result = 1.0 (white wins), 0.5 (draw), 0.0 (black wins)

Usage:
  python3 generate_dataset_pgn.py [options]

  --url URL           Lichess DB URL (default: 2024-12 standard rated)
  --output FILE       Output file (default: dataset_pgn.txt)
  --target N          Stop after N positions (default: 1_000_000)
  --min-elo N         Min Elo for both players (default: 2000)
  --min-base-secs N   Min time control base in seconds (default: 180)

Dependencies:
  pip3 install zstandard requests chess
"""

import argparse
import io
import re
import sys
import time
import os

try:
    import chess
    import chess.pgn
    import requests
    import zstandard as zstd
except ImportError as e:
    print(f"ERROR: Missing dependency — {e}")
    print("Run: pip3 install zstandard requests chess --break-system-packages")
    sys.exit(1)

DEFAULT_URL = (
    "https://database.lichess.org/standard/"
    "lichess_db_standard_rated_2024-12.pgn.zst"
)
DEFAULT_OUTPUT   = "dataset_pgn.txt"
DEFAULT_TARGET   = 1_000_000
DEFAULT_MIN_ELO  = 2000
DEFAULT_MIN_SECS = 180   # 3 min = blitz/rapid/classical


def parse_time_control(tc_str):
    """Return base seconds from a time control string like '600+5', or None."""
    if not tc_str or tc_str == "-":
        return None
    m = re.match(r"(\d+)", tc_str)
    if m:
        return int(m.group(1))
    return None


def result_to_float(result_str):
    """'1-0' -> 1.0, '0-1' -> 0.0, '1/2-1/2' -> 0.5, else None."""
    if result_str == "1-0":
        return 1.0
    elif result_str == "0-1":
        return 0.0
    elif result_str == "1/2-1/2":
        return 0.5
    return None


def is_quiet_position(board, move):
    """
    Returns True if this position (before `move` is pushed) is quiet:
      - ply >= 16 (skip opening)
      - not in check
      - the move about to be played is not a capture or promotion
    """
    # board.ply() counts half-moves played so far
    if board.ply() < 16:
        return False
    if board.is_check():
        return False
    if move.promotion is not None:
        return False
    if board.is_capture(move):
        return False
    return True


def stream_pgn_from_url(url, chunk_size=65536):
    """
    Generator that streams and decompresses a .pgn.zst file from `url`,
    yielding decoded text chunks.
    """
    dctx = zstd.ZstdDecompressor()
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with dctx.stream_reader(resp.raw) as reader:
            text_buf = b""
            while True:
                chunk = reader.read(chunk_size)
                if not chunk:
                    break
                text_buf += chunk
                # Yield complete lines only (avoid splitting mid-line)
                last_nl = text_buf.rfind(b"\n")
                if last_nl >= 0:
                    yield text_buf[: last_nl + 1].decode("utf-8", errors="replace")
                    text_buf = text_buf[last_nl + 1 :]
            if text_buf:
                yield text_buf.decode("utf-8", errors="replace")


def stream_pgn_from_file(path):
    """Stream and decompress a local .pgn.zst file, yielding text chunks."""
    dctx = zstd.ZstdDecompressor()
    with open(path, "rb") as fh:
        with dctx.stream_reader(fh) as reader:
            text_buf = b""
            while True:
                chunk = reader.read(65536)
                if not chunk:
                    break
                text_buf += chunk
                last_nl = text_buf.rfind(b"\n")
                if last_nl >= 0:
                    yield text_buf[: last_nl + 1].decode("utf-8", errors="replace")
                    text_buf = text_buf[last_nl + 1 :]
            if text_buf:
                yield text_buf.decode("utf-8", errors="replace")


def make_pgn_stream(source):
    """
    Returns a text-mode stream that python-chess can read game-by-game.
    `source` is either a URL string or a local file path.
    """
    if source.startswith("http://") or source.startswith("https://"):
        chunks = stream_pgn_from_url(source)
    else:
        chunks = stream_pgn_from_file(source)

    # python-chess needs a seekable text stream; we fake one with a pipe
    # by wrapping the generator in a readable io object
    class ChunkStream(io.RawIOBase):
        def __init__(self, gen):
            self._gen  = gen
            self._buf  = b""
            self._done = False

        def readable(self):
            return True

        def readinto(self, b):
            while not self._buf and not self._done:
                try:
                    text = next(self._gen)
                    self._buf = text.encode("utf-8")
                except StopIteration:
                    self._done = True
            if not self._buf:
                return 0
            n = min(len(b), len(self._buf))
            b[:n] = self._buf[:n]
            self._buf = self._buf[n:]
            return n

    raw   = ChunkStream(chunks)
    text  = io.TextIOWrapper(io.BufferedReader(raw), encoding="utf-8", errors="replace")
    return text


def main():
    parser = argparse.ArgumentParser(
        description="Generate Texel tuning dataset from Lichess PGN database"
    )
    parser.add_argument("--url",           default=DEFAULT_URL,
                        help="Lichess DB URL or local .pgn.zst path")
    parser.add_argument("--output",        default=DEFAULT_OUTPUT)
    parser.add_argument("--target",        type=int, default=DEFAULT_TARGET,
                        help="Stop after this many positions")
    parser.add_argument("--min-elo",       type=int, default=DEFAULT_MIN_ELO,
                        dest="min_elo")
    parser.add_argument("--min-base-secs", type=int, default=DEFAULT_MIN_SECS,
                        dest="min_base_secs")
    args = parser.parse_args()

    print("=== Lichess PGN Dataset Generator ===")
    print(f"  Source:       {args.url}")
    print(f"  Output:       {args.output}")
    print(f"  Target:       {args.target:,} positions")
    print(f"  Min Elo:      {args.min_elo}")
    print(f"  Min TC base:  {args.min_base_secs}s ({args.min_base_secs//60}m)")
    print("-" * 60)
    sys.stdout.flush()

    games_scanned  = 0
    games_accepted = 0
    positions_written = 0
    start_time = time.time()

    pgn_stream = make_pgn_stream(args.url)

    with open(args.output, "w") as out_f:
        while positions_written < args.target:
            try:
                game = chess.pgn.read_game(pgn_stream)
            except Exception:
                continue
            if game is None:
                print("Stream exhausted before reaching target.")
                break

            games_scanned += 1

            # --- Filter by result ---
            result_str = game.headers.get("Result", "*")
            w_result   = result_to_float(result_str)
            if w_result is None:
                continue   # skip unfinished / unknown result

            # --- Filter by Elo ---
            try:
                white_elo = int(game.headers.get("WhiteElo", "0"))
                black_elo = int(game.headers.get("BlackElo", "0"))
            except ValueError:
                continue
            if white_elo < args.min_elo or black_elo < args.min_elo:
                continue

            # --- Filter by time control ---
            tc_str   = game.headers.get("TimeControl", "")
            tc_secs  = parse_time_control(tc_str)
            if tc_secs is None or tc_secs < args.min_base_secs:
                continue

            # --- Play through and extract quiet positions ---
            games_accepted += 1
            board     = game.board()
            pos_batch = []

            for move in game.mainline_moves():
                if is_quiet_position(board, move):
                    pos_batch.append(f"{board.fen()} | {w_result:.1f}\n")
                board.push(move)

            for line in pos_batch:
                out_f.write(line)
                positions_written += 1
                if positions_written >= args.target:
                    break

            # Progress every 1000 games scanned
            if games_scanned % 1000 == 0:
                elapsed  = time.time() - start_time
                rate_g   = games_scanned / elapsed if elapsed > 0 else 0
                rate_a   = games_accepted / elapsed if elapsed > 0 else 0
                eta_s    = (args.target - positions_written) / max(positions_written / elapsed, 1) if positions_written > 0 else 0
                accept_pct = 100 * games_accepted / games_scanned if games_scanned > 0 else 0
                print(
                    f"Scanned {games_scanned:7,}  accepted {games_accepted:6,} ({accept_pct:.1f}%)  "
                    f"positions {positions_written:9,}/{args.target:,}  "
                    f"rate {rate_g:.0f}g/s  ETA {eta_s/60:.1f}m"
                )
                sys.stdout.flush()

    elapsed = time.time() - start_time
    print("-" * 60)
    print(f"Done: {games_scanned:,} games scanned, {games_accepted:,} accepted")
    print(f"      {positions_written:,} positions written to {args.output}")
    print(f"      Elapsed: {elapsed/60:.1f} minutes")


if __name__ == "__main__":
    main()
