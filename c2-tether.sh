#!/data/data/com.termux/files/usr/bin/bash
#
# Hermes Agent — Mobile C2 Tether Setup Script
# =============================================
# Sets up a local HTTP C2 relay endpoint on port 8888
# that accepts authenticated command execution via POST requests.
#
# Usage:
#   bash ~/.hermes/scripts/c2-tether.sh [install|start|stop|status|help]
#
# Commands:
#   install   - Generate auth token, set up background service (default)
#   start     - Start the C2 relay as a background process
#   stop      - Stop the running C2 relay
#   status    - Check if the C2 relay is running
#   help      - Show this help message

set -e

HERMES_DIR="${HOME}/.hermes"
SCRIPTS_DIR="${HERMES_DIR}/scripts"
LOG_DIR="${HERMES_DIR}/c2-logs"
TOKEN_FILE="${HERMES_DIR}/.c2-token"
RELAY_SCRIPT="${SCRIPTS_DIR}/c2-relay.py"
CRON_FILE="${HERMES_DIR}/cron"
PID_FILE="${HERMES_DIR}/.c2-relay.pid"
PORT=8888

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[*]${NC} $1"; }
ok()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }

# Ensure directories exist
mkdir -p "${SCRIPTS_DIR}" "${LOG_DIR}" "${HERMES_DIR}/cron"

# ──────────────────────────────────────────────
# 1. Generate / load auth token
# ──────────────────────────────────────────────
generate_token() {
    if [[ -f "${TOKEN_FILE}" ]] && [[ -n "$(cat "${TOKEN_FILE}" 2>/dev/null | tr -d '[:space:]')" ]]; then
        AUTH_TOKEN=$(cat "${TOKEN_FILE}" | tr -d '[:space:]')
        ok "Using existing auth token: ${AUTH_TOKEN}"
    else
        AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        printf '%s\n' "${AUTH_TOKEN}" > "${TOKEN_FILE}"
        chmod 600 "${TOKEN_FILE}"
        ok "Generated new auth token: ${AUTH_TOKEN}"
    fi
    export AUTH_TOKEN
}

# ──────────────────────────────────────────────
# 2. Check if relay script exists
# ──────────────────────────────────────────────
check_relay_script() {
    if [[ ! -f "${RELAY_SCRIPT}" ]]; then
        err "Relay script not found at ${RELAY_SCRIPT}"
        info "Make sure c2-relay.py is in the same directory as this script."
        exit 1
    fi
    chmod +x "${RELAY_SCRIPT}" 2>/dev/null || true
    ok "Relay script found: ${RELAY_SCRIPT}"
}

# ──────────────────────────────────────────────
# 3. Print curl command template
# ──────────────────────────────────────────────
print_curl_cmd() {
    local host="${1:-<TARGET_IP>}"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  C2 Relay Ready — Use this to send commands:${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${YELLOW}curl -X POST http://${host}:${PORT} \\\\${NC}"
    echo -e "  ${YELLOW}  -H \"Content-Type: application/json\" \\\\${NC}"
    echo -e "  ${YELLOW}  -d '{\"token\":\"${AUTH_TOKEN}\",\"command\":\"whoami\"}'${NC}"
    echo ""
    echo -e "  Or with header-based auth:"
    echo -e "  ${YELLOW}curl -X POST http://${host}:${PORT} \\\\${NC}"
    echo -e "  ${YELLOW}  -H \"Content-Type: application/json\" \\\\${NC}"
    echo -e "  ${YELLOW}  -H \"X-Auth-Token: ${AUTH_TOKEN}\" \\\\${NC}"
    echo -e "  ${YELLOW}  -d '{\"command\":\"uname -a\"}'${NC}"
    echo ""
    echo -e "  Health check:"
    echo -e "  ${YELLOW}curl http://${host}:${PORT}${NC}"
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${CYAN}Token saved to:${NC} ${TOKEN_FILE}"
    echo -e "  ${CYAN}Log directory:${NC} ${LOG_DIR}"
    echo ""
}

# ──────────────────────────────────────────────
# 4. Run as background process
# ──────────────────────────────────────────────
start_background() {
    if [[ -f "${PID_FILE}" ]]; then
        local old_pid
        old_pid=$(cat "${PID_FILE}" 2>/dev/null)
        if kill -0 "${old_pid}" 2>/dev/null; then
            warn "C2 relay is already running (PID: ${old_pid})"
            return 0
        fi
        rm -f "${PID_FILE}"
    fi

    nohup python3 "${RELAY_SCRIPT}" "${PORT}" \
        > "${LOG_DIR}/relay-stdout.log" \
        2> "${LOG_DIR}/relay-stderr.log" &

    local pid=$!
    echo "${pid}" > "${PID_FILE}"

    # Wait a moment, then verify
    sleep 1
    if kill -0 "${pid}" 2>/dev/null; then
        ok "C2 relay started as background process (PID: ${pid})"
        info "Stdout log: ${LOG_DIR}/relay-stdout.log"
        info "Stderr log: ${LOG_DIR}/relay-stderr.log"
    else
        err "C2 relay failed to start. Check logs."
        rm -f "${PID_FILE}"
        return 1
    fi
}

stop_background() {
    if [[ ! -f "${PID_FILE}" ]]; then
        warn "No PID file found (${PID_FILE})"
        # Try pkill as fallback
        if pkill -f "c2-relay.py" 2>/dev/null; then
            ok "Stopped c2-relay.py via pkill"
        else
            warn "No running c2-relay process found"
        fi
        return 0
    fi

    local pid
    pid=$(cat "${PID_FILE}" 2>/dev/null)
    if [[ -z "${pid}" ]]; then
        rm -f "${PID_FILE}"
        return 0
    fi

    if kill "${pid}" 2>/dev/null; then
        ok "Stopped C2 relay (PID: ${pid})"
    else
        warn "Process ${pid} not running"
    fi
    rm -f "${PID_FILE}"
}

status_background() {
    if [[ -f "${PID_FILE}" ]]; then
        local pid
        pid=$(cat "${PID_FILE}" 2>/dev/null)
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            echo -e "${GREEN}C2 relay is RUNNING${NC} (PID: ${pid}, port: ${PORT})"
            echo "  Process info:"
            ps -p "${pid}" -o pid,etime,cmd 2>/dev/null || true
            return 0
        fi
        rm -f "${PID_FILE}"
    fi

    # Fallback: check process list
    local pid
    pid=$(pgrep -f "c2-relay.py" 2>/dev/null || true)
    if [[ -n "${pid}" ]]; then
        echo -e "${GREEN}C2 relay is RUNNING${NC} (PID: ${pid}, port: ${PORT})"
        # Recreate PID file
        echo "${pid}" > "${PID_FILE}"
        return 0
    fi

    echo -e "${RED}C2 relay is NOT running${NC}"
    return 1
}

# ──────────────────────────────────────────────
# 5. Register as cron job (start on reboot)
# ──────────────────────────────────────────────
register_cron() {
    local cron_dir="${HERMES_DIR}/cron"
    local cron_line="@reboot ${RELAY_SCRIPT} ${PORT} >> ${LOG_DIR}/relay-stdout.log 2>> ${LOG_DIR}/relay-stderr.log &"

    mkdir -p "${cron_dir}"

    # Create a crontab fragment
    local cron_file="${cron_dir}/c2-relay.cron"
    if [[ -f "${cron_file}" ]]; then
        warn "Cron file already exists: ${cron_file}"
        echo -n "  Overwrite? [y/N] "
        read -r answer
        if [[ "${answer}" != "y" && "${answer}" != "Y" ]]; then
            info "Skipping cron registration."
            return 0
        fi
    fi

    printf '%s\n' "${cron_line}" > "${cron_file}"
    ok "Cron job registered: ${cron_file}"

    # Try to load into Hermes cron system if available
    if command -v hermes &>/dev/null && hermes cron list &>/dev/null 2>&1; then
        hermes cron add "c2-relay" "@reboot" "${RELAY_SCRIPT} ${PORT}" 2>/dev/null && \
            ok "Registered in Hermes cron system" || \
            warn "Could not register in Hermes cron (manual cron file saved)"
    else
        info "To enable auto-start via system crontab, add this line:"
        echo ""
        echo "  ${cron_line}"
        echo ""
    fi
}

# ──────────────────────────────────────────────
# Main installer
# ──────────────────────────────────────────────
do_install() {
    echo ""
    echo -e "${CYAN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    Hermes Agent — Mobile C2 Tether Setup ║${NC}"
    echo -e "${CYAN}╚═══════════════════════════════════════════╝${NC}"
    echo ""

    check_relay_script
    generate_token

    # Detect local IP for display
    local local_ip=""
    if command -v ip &>/dev/null; then
        local_ip=$(ip route get 1 2>/dev/null | awk '{print $NF; exit}' || true)
    fi
    if [[ -z "${local_ip}" ]] && command -v ifconfig &>/dev/null; then
        local_ip=$(ifconfig 2>/dev/null | grep -E 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -1 || true)
    fi
    if [[ -z "${local_ip}" ]]; then
        local_ip="<TARGET_IP>"
    fi

    print_curl_cmd "${local_ip}"

    # Ask about starting the service
    echo -e "${CYAN}How would you like to run the C2 relay?${NC}"
    echo "  1) Background process (start now, manual restart needed after reboot)"
    echo "  2) Cron job (auto-start on reboot)"
    echo "  3) Skip — just print the curl command"
    echo -n "Choose [1/2/3]: "
    read -r choice

    case "${choice}" in
        1)
            echo ""
            start_background
            ;;
        2)
            echo ""
            start_background
            register_cron
            ;;
        *)
            info "Installation complete (no service started)."
            echo ""
            info "To start manually later: bash $0 start"
            ;;
    esac

    echo ""
    ok "C2 Tether setup complete!"
    echo ""
    echo "  Manage with:"
    echo "    bash $0 start   — Start the relay"
    echo "    bash $0 stop    — Stop the relay"
    echo "    bash $0 status  — Check status"
    echo ""
}

# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
case "${1:-install}" in
    install)
        do_install
        ;;
    start)
        check_relay_script
        generate_token
        start_background
        ;;
    stop)
        stop_background
        ;;
    status)
        status_background
        ;;
    help|--help|-h)
        head -20 "$0" | grep -E '^#|^$' | sed 's/^#//' | sed 's/^ //'
        echo ""
        echo "Commands:"
        echo "  install   - Full setup (generate token, start service)"
        echo "  start     - Start the relay as background process"
        echo "  stop      - Stop the relay"
        echo "  status    - Check if running"
        echo "  help      - This message"
        ;;
    *)
        err "Unknown command: ${1}"
        echo "Usage: bash $0 [install|start|stop|status|help]"
        exit 1
        ;;
esac