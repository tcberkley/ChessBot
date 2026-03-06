#!/bin/bash
# Start the lichess bot with API token from .env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

if [ -z "$LICHESS_BOT_TOKEN" ]; then
    echo "Error: LICHESS_BOT_TOKEN not set. Create a .env file in the project root."
    exit 1
fi

cd "$SCRIPT_DIR"
python lichess-bot.py "$@"
