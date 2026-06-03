#!/data/data/com.termux/files/home/usr/bin/bash
IP_FILE="$HOME/.hermes/scripts/last_ip.txt"
CURRENT_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null)

if [ -z "$CURRENT_IP" ]; then
  exit 0
fi

if [ -f "$IP_FILE" ]; then
  OLD_IP=$(cat "$IP_FILE")
  if [ "$CURRENT_IP" != "$OLD_IP" ]; then
    echo "IP changed: $OLD_IP → $CURRENT_IP"
    echo "$CURRENT_IP" > "$IP_FILE"
  fi
else
  echo "$CURRENT_IP" > "$IP_FILE"
fi
