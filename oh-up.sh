#!/data/data/com.termux/files/usr/bin/bash
# Start OpenHuman core server inside Ubuntu proot
# Usage: ./oh-up.sh [port]

PORT="${1:-7788}"

echo "→ Starting OpenHuman core on port $PORT..."
echo "cd /root && ./openhuman-core run --jsonrpc-only --port $PORT 2>&1" | \
  proot-distro login ubuntu
