#!/bin/bash
set -e

echo "[entrypoint] Starting Tor..."
tor &

# Wait for Tor to bootstrap (check SOCKS port)
for i in $(seq 1 30); do
    if curl -s --socks5-hostname 127.0.0.1:9050 https://check.torproject.org > /dev/null 2>&1; then
        echo "[entrypoint] Tor is ready"
        break
    fi
    if [ "$i" = "30" ]; then
        echo "[entrypoint] WARNING: Tor failed to start after 30s, continuing without Tor"
    fi
    sleep 1
done

echo "[entrypoint] Starting scraper worker..."
exec uvicorn worker:app --host 0.0.0.0 --port 8001
