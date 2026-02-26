"""Append one row per challenge event to the challenge CSV log."""
import csv
import os
from datetime import datetime, timezone


def format_tc(base: int, increment: int, days: int = 0) -> str:
    """Format a time control as a human-readable string (e.g. '½+0', '3+2', '1d')."""
    if not (base or increment):
        return f"{days}d" if days else ""
    mins = base / 60
    if mins == int(mins):
        mins_str = str(int(mins))
    elif base == 30:
        mins_str = "½"
    else:
        mins_str = f"{mins:.2g}"
    return f"{mins_str}+{increment}"

CSV_PATH = "/root/scripts/challenge_log.csv"
FIELDNAMES = [
    "timestamp_utc", "direction", "event", "opponent", "opponent_rating",
    "opponent_is_bot", "time_control", "variant", "rated",
    "decline_reason", "challenge_id",
]


def log_challenge(*, direction, event, opponent, opponent_rating="",
                  opponent_is_bot="", time_control="", variant="",
                  rated="", decline_reason="", challenge_id=""):
    """Append one challenge event row to the CSV log. Silently ignores errors."""
    try:
        write_header = not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0
        with open(CSV_PATH, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
            writer.writerow({
                "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "direction": direction,
                "event": event,
                "opponent": opponent,
                "opponent_rating": opponent_rating,
                "opponent_is_bot": opponent_is_bot,
                "time_control": time_control,
                "variant": variant,
                "rated": rated,
                "decline_reason": decline_reason,
                "challenge_id": challenge_id,
            })
    except Exception:
        pass  # Never crash the bot over logging
