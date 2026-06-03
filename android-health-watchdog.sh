#!/data/data/com.termux/files/usr/bin/bash
# Android/Termux Health Watchdog
# Silent unless a threshold is breached.

ALERTS=""

# --- STORAGE ---
STORAGE_PCT=$(df /storage/emulated | awk 'NR==2 {gsub(/%/,""); print $5}')
if [ -n "$STORAGE_PCT" ] && [ "$STORAGE_PCT" -gt 90 ]; then
  ALERTS="${ALERTS}STORAGE ALERT: /storage/emulated is ${STORAGE_PCT}% full\n"
fi

# --- MEMORY ---
# Parse /proc/meminfo for precise values (free -h not always present)
MEM_TOTAL=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
MEM_AVAIL=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
if [ -n "$MEM_TOTAL" ] && [ -n "$MEM_AVAIL" ] && [ "$MEM_TOTAL" -gt 0 ]; then
  MEM_AVAIL_MB=$((MEM_AVAIL / 1024))
  MEM_PCT_AVAIL=$((MEM_AVAIL * 100 / MEM_TOTAL))
  if [ "$MEM_AVAIL_MB" -lt 512 ]; then
    ALERTS="${ALERTS}MEMORY ALERT: only ${MEM_AVAIL_MB}MB available (${MEM_PCT_AVAIL}%)\n"
  fi
fi

# --- SWAP ---
SWAP_TOTAL=$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)
SWAP_FREE=$(awk '/SwapFree:/ {print $2}' /proc/meminfo)
if [ -n "$SWAP_TOTAL" ] && [ "$SWAP_TOTAL" -gt 0 ] && [ -n "$SWAP_FREE" ]; then
  SWAP_USED=$((SWAP_TOTAL - SWAP_FREE))
  SWAP_PCT=$((SWAP_USED * 100 / SWAP_TOTAL))
  if [ "$SWAP_PCT" -gt 95 ]; then
    SWAP_USED_MB=$((SWAP_USED / 1024))
    ALERTS="${ALERTS}SWAP ALERT: ${SWAP_PCT}% used (${SWAP_USED_MB}MB)\n"
  fi
fi

# --- LOAD (1-min) ---
LOAD1=$(cut -d' ' -f1 /proc/loadavg 2>/dev/null | cut -d. -f1)
if [ -n "$LOAD1" ] && [ "$LOAD1" -gt 15 ]; then
  ALERTS="${ALERTS}LOAD ALERT: 1-min load average is $(cut -d' ' -f1 /proc/loadavg)\n"
fi

# --- OUTPUT ---
if [ -n "$ALERTS" ]; then
  echo -e "Android Health Watchdog Alert:\n\n${ALERTS}"
fi
