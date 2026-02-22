#!/usr/bin/env python3
"""
Texel tuner orchestrator for v20_engine.

- Stops lichess-bot service
- Launches v20_tuner as a subprocess
- Parses TUNER_EPOCH lines from stdout
- Sends an HTML progress email every 20 epochs (via Gmail SMTP)
- Sends a final email on convergence or timeout
- Does NOT restart lichess-bot when done

Email credentials (environment variables, same as daily_summary.py):
  SUMMARY_EMAIL_SENDER        Gmail address to send from
  SUMMARY_EMAIL_APP_PASSWORD  Gmail App Password

Usage:
  python3 run_tuner.py [options]

  --dataset FILE   Dataset path (default: dataset_pgn.txt)
  --engine PATH    v20_tuner binary (default: ./v20_tuner)
  --test-email     Send a test email and exit
"""

import argparse
import html
import os
import re
import smtplib
import subprocess
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def load_dotenv():
    """Load .env variables from known server locations (no external deps)."""
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parent / ".env",
        Path("/root/lichess-bot-master/.env"),
    ]
    for path in candidates:
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())
            break


load_dotenv()

# ─── Email config ────────────────────────────────────────────────────────────
SMTP_HOST  = "smtp.gmail.com"
SMTP_PORT  = 587
RECIPIENT  = "tcberkley@gmail.com"

# v19 scalar baseline for comparison table (tp[704..743])
V19_SCALARS = [
    ("MAT_PAWN",      100),
    ("MAT_KNIGHT",    320),
    ("MAT_BISHOP",    330),
    ("MAT_ROOK",      500),
    ("MAT_QUEEN",     900),
    ("DOUBLED_PAWN",   30),
    ("ISOLATED_PAWN",  20),
    ("PAWN_ISLAND",     8),
    ("BACKWARD_PAWN",  10),
    ("BISHOP_PAIR",    30),
    ("BAD_BISHOP",      5),
    ("OUTPOST",        15),
    ("OUTPOST_DEF",    10),
    ("OPEN_FILE",      20),
    ("SEMI_OPEN",      10),
    ("ROOK_7TH_MG",    15),
    ("ROOK_7TH_EG",    25),
    ("ROOK_BEHIND",    20),
    ("CONN_ROOKS",     15),
    ("KNIGHT_TROP",     3),
    ("BISHOP_TROP",     2),
    ("ROOK_TROP",       2),
    ("QUEEN_TROP",      3),
    ("SHIELD_1",       15),
    ("SHIELD_2",        8),
    ("KING_OPEN",      10),
    ("KING_SEMI",       5),
    ("CASTLE_RIGHT",   10),
    ("CASTLED",        40),
    ("THREAT_ATK",      8),
    ("PASSED_MG",      50),
    ("PASSED_EG",     100),
    ("CAND_DENOM",      4),
    ("KING_CTR",       10),
    ("KING_KING",       5),
    ("KPASS_OWN",       5),
    ("KPASS_ENE",       5),
    ("KING_MOB",        3),
    ("MOPUP_CRN",      15),
    ("MOPUP_KDIST",    10),
]

# Parameters that should stay >= 0 (sign-constrained)
SIGN_CONSTRAINED = {
    "DOUBLED_PAWN", "ISOLATED_PAWN", "PAWN_ISLAND", "BACKWARD_PAWN",
    "BISHOP_PAIR", "OUTPOST", "OUTPOST_DEF", "OPEN_FILE", "SEMI_OPEN",
    "ROOK_7TH_MG", "ROOK_7TH_EG", "ROOK_BEHIND", "CONN_ROOKS",
    "KNIGHT_TROP", "BISHOP_TROP", "ROOK_TROP", "QUEEN_TROP",
    "SHIELD_1", "SHIELD_2", "KING_SEMI", "THREAT_ATK",
    "PASSED_MG", "PASSED_EG", "KING_CTR", "KING_KING",
    "KPASS_OWN", "KPASS_ENE", "KING_MOB", "MOPUP_CRN", "MOPUP_KDIST",
}


# ─── Email helpers ────────────────────────────────────────────────────────────

def send_email(subject, html_body):
    sender   = os.environ.get("SUMMARY_EMAIL_SENDER", "")
    password = os.environ.get("SUMMARY_EMAIL_APP_PASSWORD", "")
    if not sender or not password:
        print("WARNING: SUMMARY_EMAIL_SENDER or SUMMARY_EMAIL_APP_PASSWORD not set. "
              "Skipping email.", flush=True)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, RECIPIENT, msg.as_string())
        print(f"Email sent: {subject}", flush=True)
    except Exception as e:
        print(f"Email failed: {e}", flush=True)


def fmt_delta(delta):
    """Format a parameter change with sign and colour."""
    if delta > 0:
        return f'<span style="color:#2e7d32">+{delta}</span>'
    elif delta < 0:
        return f'<span style="color:#c62828">{delta}</span>'
    else:
        return "0"


def build_email_html(epoch, k_value, mse_history, current_scalars,
                     elapsed_s, secs_per_epoch):
    lines = []
    lines.append("""
<html><body style="font-family:monospace;font-size:13px;">
<h2 style="margin-bottom:4px">v20 Texel Tuner Progress</h2>
""")

    # Progress header
    eta_epochs = "?" if secs_per_epoch <= 0 else "converging"
    eta_str    = "?" if secs_per_epoch <= 0 else f"{secs_per_epoch/60:.1f} min/epoch"
    lines.append(f"""
<table style="margin-bottom:16px">
  <tr><td><b>Epoch:</b></td><td>{epoch}</td></tr>
  <tr><td><b>Current MSE:</b></td><td>{mse_history[-1][1]:.8f}</td></tr>
  <tr><td><b>Initial MSE:</b></td><td>{mse_history[0][1]:.8f}</td></tr>
  <tr><td><b>Total improvement:</b></td>
      <td>{mse_history[0][1] - mse_history[-1][1]:.8f}</td></tr>
  <tr><td><b>K (sigmoid scale):</b></td><td>{k_value:.2f}</td></tr>
  <tr><td><b>Time elapsed:</b></td><td>{elapsed_s/3600:.2f} hours</td></tr>
  <tr><td><b>Time per epoch:</b></td><td>{eta_str}</td></tr>
</table>
""")

    # MSE history table
    lines.append("""
<h3>MSE History</h3>
<table border="1" cellpadding="4" cellspacing="0"
       style="border-collapse:collapse;margin-bottom:16px">
  <tr style="background:#e0e0e0">
    <th>Epoch</th><th>MSE</th><th>Δ prev</th><th>Elapsed (h)</th>
  </tr>
""")
    for i, (ep, mse, el_s) in enumerate(mse_history):
        delta_str = ""
        if i > 0:
            d = mse - mse_history[i-1][1]
            col = "#c62828" if d > 0 else "#2e7d32"
            delta_str = f'<span style="color:{col}">{d:+.8f}</span>'
        bg = "#f5f5f5" if i % 2 == 0 else "#ffffff"
        lines.append(
            f'<tr style="background:{bg}">'
            f'<td>{ep}</td><td>{mse:.8f}</td>'
            f'<td>{delta_str}</td><td>{el_s/3600:.2f}</td></tr>'
        )
    lines.append("</table>")

    # Scalar bonuses comparison table
    lines.append("""
<h3>Scalar Bonuses (current vs v19 baseline)</h3>
<table border="1" cellpadding="4" cellspacing="0"
       style="border-collapse:collapse;margin-bottom:16px">
  <tr style="background:#e0e0e0">
    <th>Parameter</th><th>v19</th><th>Current</th><th>Change</th><th>Note</th>
  </tr>
""")
    for i, (name, v19_val) in enumerate(V19_SCALARS):
        cur_val  = current_scalars[i] if i < len(current_scalars) else v19_val
        delta    = cur_val - v19_val
        bg       = "#f5f5f5" if i % 2 == 0 else "#ffffff"
        note     = ""
        if name in SIGN_CONSTRAINED and cur_val == 0 and v19_val > 0:
            note = '<span style="color:#e65100">⚠ clamped to 0</span>'
        lines.append(
            f'<tr style="background:{bg}">'
            f'<td><b>{html.escape(name)}</b></td>'
            f'<td style="text-align:right">{v19_val}</td>'
            f'<td style="text-align:right">{cur_val}</td>'
            f'<td style="text-align:right">{fmt_delta(delta)}</td>'
            f'<td>{note}</td></tr>'
        )
    lines.append("</table>")
    lines.append("</body></html>")
    return "\n".join(lines)


# ─── Scalar parser ────────────────────────────────────────────────────────────

# Matches lines like: "  tp[704] =  100  // MAT_PAWN"
_SCALAR_RE = re.compile(r"tp\[(\d+)\]\s*=\s*(-?\d+)")

def parse_scalars_from_dump(dump_lines):
    """Extract tp[704..743] values from a print_params() dump."""
    scalars = {}
    for line in dump_lines:
        m = _SCALAR_RE.search(line)
        if m:
            idx = int(m.group(1))
            val = int(m.group(2))
            if 704 <= idx <= 743:
                scalars[idx - 704] = val
    result = [scalars.get(i, V19_SCALARS[i][1]) for i in range(40)]
    return result


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="v20 Texel tuner orchestrator")
    parser.add_argument("--dataset",    default="dataset_pgn.txt")
    parser.add_argument("--engine",     default="./v20_tuner")
    parser.add_argument("--test-email", action="store_true", dest="test_email")
    args = parser.parse_args()

    if args.test_email:
        print("Sending test email...", flush=True)
        test_scalars = [v for _, v in V19_SCALARS]
        html_body = build_email_html(
            epoch=0, k_value=400.0,
            mse_history=[(0, 0.22500, 0)],
            current_scalars=test_scalars,
            elapsed_s=0, secs_per_epoch=0
        )
        send_email("[v20 Tuner] TEST EMAIL — setup verification", html_body)
        return

    # Stop lichess-bot
    print("Stopping lichess-bot...", flush=True)
    ret = subprocess.run(
        ["systemctl", "stop", "lichess-bot"],
        capture_output=True, text=True
    )
    if ret.returncode == 0:
        print("lichess-bot stopped.", flush=True)
    else:
        print(f"systemctl stop returned {ret.returncode}: {ret.stderr.strip()}", flush=True)

    # Verify dataset
    if not os.path.isfile(args.dataset):
        print(f"ERROR: Dataset not found: {args.dataset}", flush=True)
        sys.exit(1)
    n_positions = sum(1 for _ in open(args.dataset))
    print(f"Dataset: {args.dataset}  ({n_positions:,} positions)", flush=True)

    if not os.path.isfile(args.engine):
        print(f"ERROR: Engine not found: {args.engine}", flush=True)
        sys.exit(1)

    print(f"Launching: {args.engine} {args.dataset}", flush=True)
    print("=" * 60, flush=True)

    # Launch tuner
    proc = subprocess.Popen(
        [args.engine, args.dataset],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # State
    mse_history    = []   # list of (epoch, mse, elapsed_s)
    current_scalars = [v for _, v in V19_SCALARS]  # start with v19 values
    k_value        = 400.0
    dump_buf       = []   # accumulate lines of a print_params() dump
    in_dump        = False
    start_time     = time.time()
    last_epoch_time = start_time
    secs_per_epoch = 0.0

    # Calibration K line
    k_re    = re.compile(r"Calibrated K\s*=\s*([\d.]+)")
    epoch_re = re.compile(
        r"TUNER_EPOCH epoch=(\d+) mse=([\d.]+) elapsed_s=(\d+) improved=(\d+)"
    )
    dump_start_re = re.compile(r"=== Epoch (\d+)\s+MSE=")
    dump_end_re   = re.compile(r"^  tp\[743\]")   # last scalar line

    for raw_line in proc.stdout:
        line = raw_line.rstrip()
        print(line, flush=True)  # mirror to log

        # K calibration
        m = k_re.search(line)
        if m:
            k_value = float(m.group(1))

        # Epoch summary line
        m = epoch_re.match(line)
        if m:
            ep      = int(m.group(1))
            mse     = float(m.group(2))
            el_s    = int(m.group(3))
            now     = time.time()
            secs_per_epoch = (now - last_epoch_time)
            last_epoch_time = now

            # Initial MSE stored at epoch 0 from the "Initial MSE:" line;
            # epoch 1 is the first coordinate-descent pass
            if not mse_history:
                # Shouldn't happen, but guard
                mse_history.append((0, mse, 0))
            mse_history.append((ep, mse, el_s))

            if ep % 20 == 0:
                elapsed = time.time() - start_time
                subj    = f"[v20 Tuner] Epoch {ep} — MSE: {mse:.8f}"
                body    = build_email_html(
                    epoch=ep, k_value=k_value,
                    mse_history=mse_history,
                    current_scalars=current_scalars,
                    elapsed_s=elapsed,
                    secs_per_epoch=secs_per_epoch,
                )
                send_email(subj, body)

        # Capture print_params() dump to parse scalar values
        if dump_start_re.search(line):
            in_dump  = True
            dump_buf = [line]
        elif in_dump:
            dump_buf.append(line)
            if dump_end_re.match(line):
                # End of dump — parse scalars
                current_scalars = parse_scalars_from_dump(dump_buf)
                in_dump  = False
                dump_buf = []

        # Initial MSE line (before epoch 1)
        m2 = re.match(r"Initial MSE:\s*([\d.]+)", line)
        if m2:
            mse_history.append((0, float(m2.group(1)), 0))

    proc.wait()
    elapsed = time.time() - start_time

    print("=" * 60, flush=True)
    print(f"Tuner finished. Exit code: {proc.returncode}. "
          f"Total time: {elapsed/3600:.2f}h", flush=True)

    # Final email
    final_mse = mse_history[-1][1] if mse_history else 0.0
    subj = f"[v20 Tuner] FINISHED — Final MSE: {final_mse:.8f}"
    body = build_email_html(
        epoch=mse_history[-1][0] if mse_history else 0,
        k_value=k_value,
        mse_history=mse_history,
        current_scalars=current_scalars,
        elapsed_s=elapsed,
        secs_per_epoch=secs_per_epoch,
    )
    send_email(subj, body)
    print("Done. lichess-bot has NOT been restarted (per config).", flush=True)


if __name__ == "__main__":
    main()
