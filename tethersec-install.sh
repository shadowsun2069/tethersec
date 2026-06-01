#!/data/data/com.termux/files/usr/bin/bash
# TetherSec Mobile — Installer
# One-command setup for Big Country's pentest tool suite.
# Usage: bash tethersec-install.sh

set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
cat << "BANNER"
  _______    _   _               _____            _
 |__   __|  | | | |             / ____|          | |
    | | ___ | |_| | ___ _ __   | (___   ___ _ __ | |__   ___ _ __ ___
    | |/ _ \| __| |/ _ \ '__|   \___ \ / _ \ '_ \| '_ \ / _ \ '__/ __|
    | | (_) | |_| |  __/ |      ____) |  __/ | | | |_) |  __/ |  \__ \
    |_|\___/ \__|_|\___|_|     |_____/ \___|_| |_|_.__/ \___|_|  |___/
BANNER
echo -e "${NC}"
echo -e "${BOLD}TetherSec Mobile — Pentest Suite Installer${NC}"
echo ""

SCRIPTS_DIR="/data/data/com.termux/files/home/.hermes/scripts"
BIN_DIR="/data/data/com.termux/files/home/.local/bin"
SOURCE_URL="https://raw.githubusercontent.com/shadowsun2069/tethersec/main"

# Detect if running from local scripts dir or remote
if [ -d "$SCRIPTS_DIR" ] && [ -f "$SCRIPTS_DIR/portable-lab.py" ]; then
    LOCAL_MODE=true
    echo -e "${GREEN}[*] Local install mode${NC}"
else
    LOCAL_MODE=false
    echo -e "${GREEN}[*] Remote install mode${NC}"
fi

echo ""
echo -e "${BOLD}Step 1/4 — Installing system dependencies${NC}"
pkg update -y 2>/dev/null | tail -1
DEPS="python golang curl wget"
for dep in $DEPS; do
    if ! command -v "$dep" &>/dev/null; then
        echo -e "  ${YELLOW}[*] Installing $dep...${NC}"
        pkg install -y "$dep" 2>/dev/null | tail -1
    else
        echo -e "  ${GREEN}[✓] $dep${NC}"
    fi
done

# Install gobuster (not in Termux repos, need go install)
if ! command -v gobuster &>/dev/null; then
    echo -e "  ${YELLOW}[*] Installing gobuster via go...${NC}"
    go install github.com/OJ/gobuster/v3@latest 2>&1 | tail -1
    cp "$(go env GOPATH)/bin/gobuster" "$BIN_DIR/gobuster" 2>/dev/null || true
else
    echo -e "  ${GREEN}[✓] gobuster${NC}"
fi

echo ""
echo -e "${BOLD}Step 2/4 — Installing TetherSec tools${NC}"
mkdir -p "$BIN_DIR"

install_tool() {
    local name="$1"
    local file="$2"
    if [ "$LOCAL_MODE" = true ]; then
        cp "$SCRIPTS_DIR/$file" "$BIN_DIR/$name"
    else
        curl -fsSL "$SOURCE_URL/$file" -o "$BIN_DIR/$name"
    fi
    chmod +x "$BIN_DIR/$name"
    echo -e "  ${GREEN}[✓] $name${NC}"
}

install_tool "tether-lab" "portable-lab.py"
install_tool "tether-recon" "ai-recon.py"
install_tool "tether-bounty" "bounty-harness.py"
install_tool "tether-c2" "c2-tether.sh"

echo ""
echo -e "${BOLD}Step 3/4 — Setting up PATH${NC}"
if ! grep -q ".local/bin" ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo -e "  ${GREEN}[✓] PATH updated in .bashrc${NC}"
else
    echo -e "  ${GREEN}[✓] PATH already set${NC}"
fi

# Source it now
export PATH="$HOME/.local/bin:$PATH"

echo ""
echo -e "${BOLD}Step 4/4 — Creating launch menu${NC}"

# Write the launch script
cat > "$BIN_DIR/tethersec" << 'TETHERMENU'
#!/data/data/com.termux/files/usr/bin/bash
# TetherSec Mobile — Launch Menu

BOLD='\033[1m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

clear
echo -e "${CYAN}"
echo "  ╔══════════════════════════════════╗"
echo "  ║       TetherSec Mobile           ║"
echo "  ║   Mobile Pentest Suite v1.0      ║"
echo "  ╚══════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "  ${BOLD}Available Tools:${NC}"
echo ""
echo -e "  ${GREEN}1${NC})  Start Security Lab    ${YELLOW}(tether-lab)${NC}"
echo -e "      Spins up vulnerable HTTP targets on ports 9000+"
echo ""
echo -e "  ${GREEN}2${NC})  Run AI Recon          ${YELLOW}(tether-recon <url>)${NC}"
echo -e "      gobuster → brute force → Ollama AI analysis"
echo ""
echo -e "  ${GREEN}3${NC})  Run Bounty Harness    ${YELLOW}(tether-bounty <url>)${NC}"
echo -e "      Full scan → AI vuln assessment → Markdown report"
echo ""
echo -e "  ${GREEN}4${NC})  Start C2 Relay        ${YELLOW}(tether-c2)${NC}"
echo -e "      Mobile command relay on port 8888"
echo ""
echo -e "  ${GREEN}5${NC})  Kill Lab Servers      ${YELLOW}(tether-lab --kill)${NC}"
echo ""
echo -e "  ${GREEN}0${NC})  Exit"
echo ""
echo -ne "  ${BOLD}Select:${NC} "
read -r choice
echo ""

case "$choice" in
    1)
        echo -e "  ${CYAN}[*] Starting security lab...${NC}"
        tether-lab --ports 3
        ;;
    2)
        echo -ne "  ${CYAN}Target URL:${NC} "
        read -r url
        tether-recon "$url"
        ;;
    3)
        echo -ne "  ${CYAN}Target URL:${NC} "
        read -r url
        tether-bounty "$url"
        ;;
    4)
        echo -e "  ${CYAN}[*] Starting C2 relay on port 8888...${NC}"
        tether-c2
        ;;
    5)
        echo -e "  ${CYAN}[*] Killing lab servers...${NC}"
        tether-lab --kill
        ;;
    0)
        echo -e "  ${GREEN}TetherSec out.${NC}"
        exit 0
        ;;
    *)
        echo -e "  ${RED}Invalid choice.${NC}"
        sleep 1
        exec "$0"
        ;;
esac
TETHERMENU
chmod +x "$BIN_DIR/tethersec"

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  TetherSec Mobile installed!${NC}"
echo ""
echo -e "  Type:  ${CYAN}tethersec${NC}        — Launch menu"
echo -e "  Type:  ${CYAN}tether-recon <url>${NC} — Quick recon"
echo -e "  Type:  ${CYAN}tether-bounty <url>${NC} — Full bounty scan"
echo -e "  Type:  ${CYAN}tether-lab${NC}        — Start lab"
echo ""
echo -e "  Reports go to:  ~/.hermes/bounty-reports/"
echo ""
echo -e "  ${YELLOW}Tip: Restart Termux or run 'source ~/.bashrc'${NC}"
echo -e "  ${YELLOW}to pick up the new PATH.${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"