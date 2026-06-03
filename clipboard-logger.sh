#!/data/data/com.termux/files/usr/bin/bash
# Clipboard Logger — saves clipboard content hourly for historical recall.
# Only logs non-empty URLs or strings > 3 chars to avoid spam.
# Rotates old entries after 30 days.

LOG_DIR="$HOME/.hermes/logs/clipboard"
LOG_FILE="$LOG_DIR/$(date +%Y-%m).log"
TS=$(date '+%Y-%m-%d %H:%M:%S')

# Ensure directory exists
mkdir -p "$LOG_DIR"

# Attempt to read clipboard via termux-api
CLIP=$(termux-clipboard-get 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$CLIP" ]; then
    # Silent exit if clipboard unavailable
    exit 0
fi

# Skip trivial entries (single chars, numbers, short IDs)
LEN=${#CLIP}
if [ "$LEN" -le 3 ]; then
    exit 0
fi

# Skip duplicates (check last line of current month's log)
if [ -f "$LOG_FILE" ]; then
    LAST=$(tail -n 1 "$LOG_FILE" 2>/dev/null | sed 's/^[^|]*| //')
    if [ "$CLIP" = "$LAST" ]; then
        exit 0
    fi
fi

# Log entry (one line, timestamp + content)
printf '%s | %s\n' "$TS" "$CLIP" >> "$LOG_FILE"

# Rotate: remove logs older than 30 days (daily job, simple cleanup)
find "$LOG_DIR" -name '*.log' -type f -mtime +30 -delete 2>/dev/null
