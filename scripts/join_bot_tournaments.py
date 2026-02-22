#!/usr/bin/env python3
"""
join_bot_tournaments.py — Join all bot-eligible Lichess arena tournaments in the next 7 days.

Fetches the list of upcoming tournaments from the Lichess API, checks each one for
bot eligibility (conditions.bots == true), and joins them using the tournament token.

Requires env vars (loaded from .env):
    LICHESS_TOURNAMENT_TOKEN   Lichess API token with 'tournament:write' scope
                               Falls back to LICHESS_BOT_TOKEN if not set.

Cron (server, UTC): 5 0 * * * /root/lichess-bot-master/venv/bin/python \
    /root/scripts/join_bot_tournaments.py >> /root/scripts/join_bot_tournaments.log 2>&1
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

LICHESS_API = "https://lichess.org"
LOOKAHEAD_DAYS = 7


# ── .env loader (identical pattern to daily_summary.py) ──────────────────────

def load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent.parent / "lichess-bot-master" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(path: str, token: str | None = None) -> dict | list | None:
    url = LICHESS_API + path
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  GET {path} → HTTP {e.code}", flush=True)
        return None
    except Exception as e:
        print(f"  GET {path} → error: {e}", flush=True)
        return None


def api_post(path: str, token: str, data: dict | None = None) -> tuple[int, str]:
    """Returns (status_code, response_body)."""
    url = LICHESS_API + path
    body = urllib.parse.urlencode(data or {}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        return e.code, body_text
    except Exception as e:
        return 0, str(e)


# ── Tournament logic ──────────────────────────────────────────────────────────

def fetch_upcoming_tournaments() -> list[dict]:
    """Fetch tournaments with status=10 (upcoming) starting within LOOKAHEAD_DAYS."""
    data = api_get("/api/tournament")
    if not data:
        return []

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    cutoff_ms = now_ms + LOOKAHEAD_DAYS * 24 * 3600 * 1000

    upcoming = []
    # The response has top-level keys: "created", "started", "finished"
    for group_key in ("created", "started"):
        for t in data.get(group_key, []):
            starts_at = t.get("startsAt", 0)
            # Only upcoming (not yet started) tournaments within the lookahead window
            if group_key == "created" and starts_at <= cutoff_ms:
                upcoming.append(t)
    return upcoming


def is_bot_eligible(tournament_id: str) -> bool:
    """Check if a tournament allows bots via the full tournament detail endpoint."""
    data = api_get(f"/api/tournament/{tournament_id}")
    if not data:
        return False
    # API returns top-level "botsAllowed": true (not conditions.bots)
    return bool(data.get("botsAllowed", False))


def format_start(t: dict) -> str:
    starts_ms = t.get("startsAt", 0)
    if not starts_ms:
        return "unknown time"
    dt = datetime.fromtimestamp(starts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def join_tournament(tournament_id: str, token: str) -> tuple[bool, str]:
    status, body = api_post(f"/api/tournament/{tournament_id}/join", token)
    if status == 200:
        return True, "ok"
    # Parse error message from Lichess response
    try:
        err = json.loads(body).get("error", body)
    except Exception:
        err = body[:120]
    if "already" in err.lower():
        return True, "already joined"
    return False, f"HTTP {status}: {err}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    load_dotenv()

    token = os.environ.get("LICHESS_TOURNAMENT_TOKEN") or os.environ.get("LICHESS_BOT_TOKEN", "")
    if not token:
        print("ERROR: LICHESS_TOURNAMENT_TOKEN not set in .env", flush=True)
        return 1

    token_source = "LICHESS_TOURNAMENT_TOKEN" if os.environ.get("LICHESS_TOURNAMENT_TOKEN") else "LICHESS_BOT_TOKEN"
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] "
          f"join_bot_tournaments.py starting (token: {token_source})", flush=True)

    upcoming = fetch_upcoming_tournaments()
    print(f"Found {len(upcoming)} upcoming tournament(s) in the next {LOOKAHEAD_DAYS} days", flush=True)

    if not upcoming:
        print("Nothing to join.", flush=True)
        return 0

    joined = already = skipped = failed = 0

    for t in upcoming:
        tid = t["id"]
        name = t.get("fullName", tid)
        starts = format_start(t)

        time.sleep(0.5)  # stay well under Lichess rate limit

        if not is_bot_eligible(tid):
            skipped += 1
            continue

        time.sleep(0.5)
        ok, msg = join_tournament(tid, token)

        if ok and msg == "already joined":
            already += 1
            print(f"  ALREADY   {name} ({tid}) @ {starts}", flush=True)
        elif ok:
            joined += 1
            print(f"  JOINED    {name} ({tid}) @ {starts}", flush=True)
        else:
            failed += 1
            print(f"  FAILED    {name} ({tid}) @ {starts} — {msg}", flush=True)
            if "scope" in msg.lower() or "403" in msg or "401" in msg:
                print("  HINT: Token may be missing 'tournament:write' scope.", flush=True)

    print(f"\nDone: {joined} joined, {already} already joined, "
          f"{skipped} not bot-eligible, {failed} failed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
