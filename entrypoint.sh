#!/bin/sh
set -e

SCAN_INTERVAL="${SCAN_INTERVAL:-60}"

echo "linkarr starting (scan interval: ${SCAN_INTERVAL}s, dry_run: ${DRY_RUN:-false})"

# One-shot mode: run once and exit
if [ "$1" = "once" ] || [ "$SCAN_INTERVAL" = "0" ]; then
    echo "Running in one-shot mode"
    exec python3 /app/organize.py
fi

# Daemon mode: sleep loop with graceful shutdown
RUNNING=true
trap 'RUNNING=false; echo "Shutting down..."; exit 0' TERM INT

while $RUNNING; do
    python3 /app/organize.py
    sleep "$SCAN_INTERVAL" &
    wait $! || true
done
