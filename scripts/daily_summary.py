#!/usr/bin/env python3
"""
daily_summary.py — Fetch tombot1234's last 24h of Lichess games and email a summary.

Requires environment variables (loaded from .env if present):
    LICHESS_BOT_TOKEN         Lichess API token
    SUMMARY_EMAIL_SENDER      Gmail address used as sender
    SUMMARY_EMAIL_APP_PASSWORD  Gmail App Password for that account
    SUMMARY_EMAIL_TO          Recipient address (default: tcberkley@gmail.com)

Cron (server, UTC): 0 23 * * * /root/lichess-bot-master/venv/bin/python \
    /root/scripts/daily_summary.py >> /root/scripts/daily_summary.log 2>&1
"""

import csv
import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env if present (simple key=value parser, no external dependency)
# ---------------------------------------------------------------------------
def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        # Try one level up from the script's directory (/root/)
        env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        # Try lichess-bot-master/.env (where it actually lives on the server)
        env_path = Path(__file__).parent.parent / "lichess-bot-master" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BOT_USERNAME = "tombot1234"
LICHESS_API_BASE = "https://lichess.org"
CSV_LOG_PATH = "/root/scripts/challenge_log.csv"

# ---------------------------------------------------------------------------
# Lichess API helpers (stdlib urllib only — no requests dependency)
# ---------------------------------------------------------------------------
import urllib.request
import urllib.parse


def fetch_games(token: str, since_ms: int) -> list[dict]:
    """Return list of game dicts from the past 24 hours."""
    params = urllib.parse.urlencode({
        "since": since_ms,
        "pgnInJson": "false",
        "clocks": "false",
        "opening": "true",
        "moves": "false",
    })
    url = f"{LICHESS_API_BASE}/api/games/user/{BOT_USERNAME}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/x-ndjson",
        },
    )
    games = []
    with urllib.request.urlopen(req, timeout=30) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if line:
                try:
                    games.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return games


# ---------------------------------------------------------------------------
# Challenge log
# ---------------------------------------------------------------------------
def read_challenge_log(since_ms: int) -> dict:
    """Read challenge_log.csv and return outgoing/incoming rows from the last 24h."""
    since_dt = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc).replace(tzinfo=None)
    outgoing_sent: dict[str, dict] = {}    # challenge_id -> sent row
    outgoing_declined: dict[str, dict] = {}  # challenge_id -> declined row
    incoming: list[dict] = []

    try:
        with open(CSV_LOG_PATH, newline="") as f:
            for row in csv.DictReader(f):
                try:
                    row_dt = datetime.strptime(row["timestamp_utc"], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if row_dt < since_dt:
                    continue
                # Convert timestamp to ET for display
                row["time"] = datetime.fromtimestamp(
                    row_dt.replace(tzinfo=timezone.utc).timestamp(), tz=ET
                ).strftime("%I:%M %p").lstrip("0")

                direction = row.get("direction", "")
                event = row.get("event", "")
                if direction == "outgoing":
                    if event == "sent":
                        outgoing_sent[row["challenge_id"]] = row
                    elif event == "declined":
                        outgoing_declined[row["challenge_id"]] = row
                elif direction == "incoming":
                    incoming.append(row)
    except FileNotFoundError:
        pass  # CSV not created yet

    # Merge sent + declined into one outgoing list
    outgoing = []
    for cid, sent_row in outgoing_sent.items():
        declined_row = outgoing_declined.get(cid)
        if declined_row:
            sent_row["outcome"] = "Declined"
            sent_row["decline_reason"] = declined_row.get("decline_reason", "")
            sent_row["opponent_rating"] = declined_row.get("opponent_rating", "")
        else:
            sent_row["outcome"] = "Accepted"
            sent_row["decline_reason"] = ""
        outgoing.append(sent_row)

    # Sort by time
    outgoing.sort(key=lambda r: r["timestamp_utc"])
    incoming.sort(key=lambda r: r["timestamp_utc"])

    return {"outgoing": outgoing, "incoming": incoming}


# ---------------------------------------------------------------------------
# Stats computation
# ---------------------------------------------------------------------------
def parse_games(games: list[dict]) -> dict:
    """Build stats dict from raw game list."""
    wins = losses = draws = 0
    net_rating = 0
    final_rating = None
    rating_by_speed: dict[str, int] = {}  # most recent post-game rating per speed
    best_win = None      # (opponent_rating, game_id, opponent_name)
    by_speed: dict[str, dict] = {}
    game_rows = []

    for g in games:
        players = g.get("players", {})
        white = players.get("white", {})
        black = players.get("black", {})

        # Player name is nested: players.white.user.id / players.white.user.name
        white_id = (white.get("user") or {}).get("id", "").lower()
        black_id = (black.get("user") or {}).get("id", "").lower()

        if white_id == BOT_USERNAME.lower():
            bot_side = "white"
            opp = black
            bot_player = white
        elif black_id == BOT_USERNAME.lower():
            bot_side = "black"
            opp = white
            bot_player = black
        else:
            # Can't determine sides — skip
            continue

        winner = g.get("winner")  # "white", "black", or absent
        if winner is None:
            result = "D"
            draws += 1
        elif winner == bot_side:
            result = "W"
            wins += 1
        else:
            result = "L"
            losses += 1

        rating_diff = bot_player.get("ratingDiff", 0) or 0
        net_rating += rating_diff
        bot_rating = bot_player.get("rating", 0) or 0
        speed = g.get("speed", "other")
        # Games come newest-first — first seen per speed = most recent rating
        if final_rating is None:
            final_rating = bot_rating + rating_diff
        if speed not in rating_by_speed:
            rating_by_speed[speed] = bot_rating + rating_diff

        opp_name = (opp.get("user") or {}).get("name") or (opp.get("user") or {}).get("id") or "?"
        opp_rating = opp.get("rating", 0) or 0

        if result == "W" and (best_win is None or opp_rating > best_win[0]):
            best_win = (opp_rating, g.get("id", ""), opp_name)

        if speed not in by_speed:
            by_speed[speed] = {"W": 0, "L": 0, "D": 0, "net": 0}
        by_speed[speed][result] += 1
        by_speed[speed]["net"] += rating_diff

        created_ms = g.get("createdAt", 0)
        created_dt = datetime.fromtimestamp(created_ms / 1000, tz=ET)
        opening_name = (g.get("opening") or {}).get("name", "—")

        game_rows.append({
            "time": created_dt.strftime("%I:%M %p").lstrip("0"),
            "speed": speed,
            "opponent": opp_name,
            "opp_rating": opp_rating,
            "result": result,
            "rating_diff": rating_diff,
            "opening": opening_name,
            "id": g.get("id", ""),
        })

    total = wins + losses + draws
    win_pct = round(100 * wins / total, 1) if total else 0

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_pct": win_pct,
        "net_rating": net_rating,
        "final_rating": final_rating,
        "best_win": best_win,
        "by_speed": by_speed,
        "rating_by_speed": rating_by_speed,
        "game_rows": game_rows,
    }


# ---------------------------------------------------------------------------
# Email building
# ---------------------------------------------------------------------------
RESULT_COLORS = {"W": "#27ae60", "L": "#e74c3c", "D": "#95a5a6"}
RESULT_LABELS = {"W": "Win", "L": "Loss", "D": "Draw"}


def build_challenge_html(outgoing: list, incoming: list) -> str:
    """Build HTML tables for outgoing and incoming challenges."""
    # Outgoing table
    out_rows = ""
    for r in outgoing:
        rated_str = "Yes" if str(r.get("rated", "")).lower() in ("true", "yes", "1") else "No"
        if r["outcome"] == "Declined":
            reason = r.get("decline_reason", "")
            outcome_html = f"<span style='color:#e74c3c'>Declined</span>" + (f" <small>({reason})</small>" if reason else "")
        else:
            outcome_html = "<span style='color:#27ae60'>Accepted</span>"
        opp_rating = r.get("opponent_rating", "")
        opp_str = r["opponent"] + (f" ({opp_rating})" if opp_rating else "")
        out_rows += (
            f"<tr><td>{r['time']}</td><td>{opp_str}</td>"
            f"<td>{r.get('time_control','')}</td><td>{r.get('variant','')}</td>"
            f"<td>{rated_str}</td><td>{outcome_html}</td></tr>\n"
        )
    if not out_rows:
        out_rows = "<tr><td colspan='6' style='color:#888'>No outgoing challenges logged</td></tr>\n"

    # Incoming table
    in_rows = ""
    for r in incoming:
        rated_str = "Yes" if str(r.get("rated", "")).lower() in ("true", "yes", "1") else "No"
        is_bot = str(r.get("opponent_is_bot", "")).lower() in ("true", "1")
        bot_str = "Bot" if is_bot else "Human"
        event = r.get("event", "")
        if event == "accepted":
            outcome_html = "<span style='color:#27ae60'>Accepted</span>"
        else:
            reason = r.get("decline_reason", "")
            outcome_html = f"<span style='color:#e74c3c'>Declined</span>" + (f" <small>({reason})</small>" if reason else "")
        in_rows += (
            f"<tr><td>{r['time']}</td><td>{r['opponent']}</td>"
            f"<td>{r.get('opponent_rating','')}</td><td>{bot_str}</td>"
            f"<td>{r.get('time_control','')}</td><td>{rated_str}</td>"
            f"<td>{outcome_html}</td></tr>\n"
        )
    if not in_rows:
        in_rows = "<tr><td colspan='7' style='color:#888'>No incoming challenges logged</td></tr>\n"

    return f"""
<div class="section">
<h2>Challenges Sent</h2>
<table>
  <tr><th>Time</th><th>Opponent</th><th>Time Control</th><th>Variant</th><th>Rated</th><th>Outcome</th></tr>
  {out_rows}
</table>
</div>

<div class="section">
<h2>Challenges Received</h2>
<table>
  <tr><th>Time</th><th>Challenger</th><th>Rating</th><th>Type</th><th>Time Control</th><th>Rated</th><th>Outcome</th></tr>
  {in_rows}
</table>
</div>
"""


def build_html(stats: dict, date_str: str, challenge_data: dict | None = None) -> str:
    s = stats
    record = f"{s['wins']}-{s['losses']}-{s['draws']}"
    net_sign = "+" if s["net_rating"] >= 0 else ""
    net_str = f"{net_sign}{s['net_rating']}"
    rating_str = f" (now ~{s['final_rating']})" if s["final_rating"] else ""

    # Speed breakdown table rows
    speed_rows = ""
    for speed in ["bullet", "blitz", "rapid", "classical", "other"]:
        if speed not in s["by_speed"]:
            continue
        sp = s["by_speed"][speed]
        sp_total = sp["W"] + sp["L"] + sp["D"]
        sp_net_sign = "+" if sp["net"] >= 0 else ""
        sp_rating = s["rating_by_speed"].get(speed, "—")
        speed_rows += (
            f"<tr><td>{speed.capitalize()}</td>"
            f"<td>{sp['W']}-{sp['L']}-{sp['D']}</td>"
            f"<td>{sp_total}</td>"
            f"<td>{sp_net_sign}{sp['net']}</td>"
            f"<td>{sp_rating}</td></tr>\n"
        )
    if not speed_rows:
        speed_rows = "<tr><td colspan='5'>No games</td></tr>\n"

    # Game-by-game rows
    game_rows_html = ""
    for r in s["game_rows"]:
        color = RESULT_COLORS[r["result"]]
        label = RESULT_LABELS[r["result"]]
        diff_sign = "+" if r["rating_diff"] >= 0 else ""
        diff_str = f"{diff_sign}{r['rating_diff']}" if r["rating_diff"] != 0 else "0"
        game_url = f"https://lichess.org/{r['id']}"
        game_rows_html += (
            f"<tr>"
            f"<td>{r['time']}</td>"
            f"<td>{r['speed'].capitalize()}</td>"
            f"<td><a href='{game_url}'>{r['opponent']}</a></td>"
            f"<td>{r['opp_rating']}</td>"
            f"<td style='color:{color};font-weight:bold'>{label}</td>"
            f"<td>{diff_str}</td>"
            f"</tr>\n"
        )
    if not game_rows_html:
        game_rows_html = "<tr><td colspan='6'>No games</td></tr>\n"

    best_win_str = "—"
    if s["best_win"]:
        bw_rating, bw_id, bw_name = s["best_win"]
        best_win_str = f'<a href="https://lichess.org/{bw_id}">{bw_name} ({bw_rating})</a>'

    speed_order = ["bullet", "blitz", "rapid", "classical", "other"]
    rating_chips = ""
    for sp in speed_order:
        if sp in s["rating_by_speed"]:
            rating_chips += (
                f"<div class='stat'>"
                f"<div class='stat-val'>{s['rating_by_speed'][sp]}</div>"
                f"<div class='stat-label'>{sp.capitalize()} Rating</div>"
                f"</div>\n  "
            )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>
  body {{ font-family: Arial, sans-serif; color: #222; max-width: 800px; margin: auto; padding: 20px; }}
  h1 {{ color: #2c3e50; }}
  .stat {{ display: inline-block; margin: 10px 20px 10px 0; }}
  .stat-val {{ font-size: 28px; font-weight: bold; color: #2c3e50; }}
  .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
  th {{ background: #2c3e50; color: #fff; padding: 8px 10px; text-align: left; font-size: 13px; }}
  td {{ padding: 6px 10px; font-size: 13px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f8f9fa; }}
  .section {{ margin-top: 30px; }}
  h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 6px; }}
  a {{ color: #3498db; text-decoration: none; }}
</style></head>
<body>
<h1>tombot1234 — Daily Summary</h1>
<p style="color:#888">{date_str} &nbsp;|&nbsp; Past 24 hours</p>

<div>
  <div class="stat">
    <div class="stat-val">{record}</div>
    <div class="stat-label">W-L-D</div>
  </div>
  <div class="stat">
    <div class="stat-val">{s['total']}</div>
    <div class="stat-label">Games</div>
  </div>
  <div class="stat">
    <div class="stat-val">{s['win_pct']}%</div>
    <div class="stat-label">Win Rate</div>
  </div>
  <div class="stat">
    <div class="stat-val">{best_win_str}</div>
    <div class="stat-label">Best Win</div>
  </div>
</div>

<div class="section">
<h2>By Time Control</h2>
<table>
  <tr><th>Speed</th><th>W-L-D</th><th>Total</th><th>Rating ±</th><th>Rating</th></tr>
  {speed_rows}
</table>
</div>

<div class="section">
<h2>All Games</h2>
<table>
  <tr><th>Time</th><th>Speed</th><th>Opponent</th><th>Their Rating</th><th>Result</th><th>Rating ±</th></tr>
  {game_rows_html}
</table>
</div>

{build_challenge_html(challenge_data["outgoing"], challenge_data["incoming"]) if challenge_data else ""}

<p style="margin-top:30px;color:#bbb;font-size:11px">
  Generated automatically by daily_summary.py
</p>
</body></html>"""
    return html


def build_no_games_html(date_str: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;color:#222;max-width:600px;margin:auto;padding:20px">
<h1>tombot1234 — Daily Summary</h1>
<p style="color:#888">{date_str}</p>
<p>No rated games were played in the past 24 hours.</p>
</body></html>"""


# ---------------------------------------------------------------------------
# Email sending
# ---------------------------------------------------------------------------
def send_email(sender: str, app_password: str, recipient: str,
               subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, app_password)
        server.sendmail(sender, [recipient], msg.as_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    load_dotenv()

    token = os.environ.get("LICHESS_BOT_TOKEN", "")
    sender = os.environ.get("SUMMARY_EMAIL_SENDER", "")
    app_password = os.environ.get("SUMMARY_EMAIL_APP_PASSWORD", "")
    recipient = os.environ.get("SUMMARY_EMAIL_TO", "tcberkley@gmail.com")

    if not token:
        print("ERROR: LICHESS_BOT_TOKEN not set", flush=True)
        return 1
    if not sender or not app_password:
        print("ERROR: SUMMARY_EMAIL_SENDER or SUMMARY_EMAIL_APP_PASSWORD not set", flush=True)
        return 1

    now = datetime.now(tz=ET)
    date_str = now.strftime("%A, %B %-d, %Y")
    since_ms = int((time.time() - 86400) * 1000)

    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S UTC')}] Fetching games since "
          f"{datetime.fromtimestamp(since_ms/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
          flush=True)

    try:
        games = fetch_games(token, since_ms)
    except Exception as e:
        print(f"ERROR fetching games: {e}", flush=True)
        try:
            subject = f"tombot1234 Daily Summary — ERROR ({date_str})"
            html = f"<p>Error fetching game data from Lichess API: {e}</p>"
            send_email(sender, app_password, recipient, subject, html)
        except Exception as mail_err:
            print(f"ERROR sending error email: {mail_err}", flush=True)
        return 1

    print(f"Fetched {len(games)} games", flush=True)

    challenge_data = read_challenge_log(since_ms)
    print(f"Challenge log: {len(challenge_data['outgoing'])} outgoing, "
          f"{len(challenge_data['incoming'])} incoming", flush=True)

    stats = parse_games(games)
    record_str = f"{stats['wins']}-{stats['losses']}-{stats['draws']}"
    if not games:
        subject = f"tombot1234 Daily Summary — {date_str} | No games"
    else:
        subject = f"tombot1234 Daily Summary — {date_str} | {record_str}"
    html = build_html(stats, date_str, challenge_data=challenge_data)

    try:
        send_email(sender, app_password, recipient, subject, html)
        print(f"Email sent to {recipient} (subject: {subject})", flush=True)
    except Exception as e:
        print(f"ERROR sending email: {e}", flush=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
