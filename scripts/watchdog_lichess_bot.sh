#!/bin/bash
# Restart lichess-bot if it has been silent for >30 minutes while marked active.
LOG=/root/scripts/watchdog_lichess_bot.log
SILENCE_THRESHOLD=1800  # 30 minutes in seconds

# Check if service is supposed to be running
if ! systemctl is-active --quiet lichess-bot; then
    exit 0  # not our job to start a stopped service
fi

# Get timestamp of last journal entry (truncate decimal)
LAST_LOG_TS=$(journalctl -u lichess-bot -n 1 --no-pager --output=short-unix 2>/dev/null | awk 'NR==1{print int($1)}')
NOW=$(date +%s)

if [ -z "$LAST_LOG_TS" ] || [ "$LAST_LOG_TS" -eq 0 ]; then
    exit 0  # no logs yet
fi

SILENCE=$((NOW - LAST_LOG_TS))

if [ $SILENCE -gt $SILENCE_THRESHOLD ]; then
    echo "$(date -u '+%Y-%m-%d %H:%M UTC'): lichess-bot silent for ${SILENCE}s — restarting" >> $LOG
    systemctl restart lichess-bot
else
    : # silent success — no noise in log when healthy
fi
