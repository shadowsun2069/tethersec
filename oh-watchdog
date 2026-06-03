#!/data/data/com.termux/files/usr/bin/bash
# OpenHuman health watchdog: start server if not running
PORT=7788
PID_FILE="/data/data/com.termux/files/home/.openhuman.pid"
LOG_FILE="/data/data/com.termux/files/home/.openhuman.log"

# 1. Port check first — if something's already listening, we're good
if curl -s --max-time 2 http://127.0.0.1:$PORT/health >/dev/null 2>&1; then
  echo "✓ OpenHuman running on port $PORT"
  if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ! kill -0 "$OLD_PID" 2>/dev/null; then
      # Port is alive but PID is stale — replace PID with a fake one so state tracking works
      PID_OF_PORT=$(lsof -ti :$PORT 2>/dev/null || ss -tlnp "sport = :$PORT" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || echo "")
      [ -n "$PID_OF_PORT" ] && echo "$PID_OF_PORT" > "$PID_FILE"
    fi
  fi
  exit 0
fi

# 2. Check PID file for a running process
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE")
  if kill -0 "$OLD_PID" 2>/dev/null; then
    # PID alive but port isn't up yet — could be booting
    for i in $(seq 1 30); do
      if curl -s --max-time 1 http://127.0.0.1:$PORT/health >/dev/null 2>&1; then
        echo "✓ OpenHealth ready on port $PORT (${i}s waiting)"
        exit 0
      fi
      sleep 1
    done
    echo "⚠ OpenHuman PID $OLD_PID alive but port $PORT not responding after 30s"
    exit 1
  fi
  rm -f "$PID_FILE"
fi

# 3. Nothing alive — start fresh
nohup bash -c "
  echo 'cd /root && ./openhuman-core run --jsonrpc-only --port $PORT' |
    proot-distro login ubuntu
" > "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

echo "⏳ OpenHuman starting (PID $NEW_PID) on port $PORT..."
for i in $(seq 1 30); do
  if curl -s --max-time 1 http://127.0.0.1:$PORT/health >/dev/null 2>&1; then
    echo "✓ OpenHuman started (PID $NEW_PID) on port $PORT (ready in ${i}s)"
    exit 0
  fi
  sleep 1
done
echo "⚠ OpenHuman started (PID $NEW_PID) but health check timed out on port $PORT"
tail -5 "$LOG_FILE" 2>/dev/null
exit 1
