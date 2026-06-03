#!/data/data/com.termux/files/usr/bin/bash
# Tether splash — display on session start
python3 -m pyfiglet "TETHER" -f slant 2>/dev/null
echo ""
echo "  System: $(uptime -p | sed 's/up //')  |  RAM: $(free -h | awk '/Mem:/{print $7}') free  |  $(df -h /data/data/com.termux/files/home | awk 'NR==2{print $4}') free"
echo "  Gateway: $(hermes gateway status 2>&1 | head -1 | sed 's/.*PID: //' | sed 's/)//')  |  Cron: $(hermes cron list 2>&1 | grep -c 'Name:') jobs  |  $(date '+%a %b %-d %-I:%M %p')"
echo "  Worker ready: worker chat"
echo ""
