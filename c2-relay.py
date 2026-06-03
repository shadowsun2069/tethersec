#!/data/data/com.termux/files/usr/bin/python3
"""
Hermes Agent Mobile C2 Relay
Listens on port 8888 for authenticated command execution.
"""

import json
import os
import subprocess
import sys
import time
import logging
import secrets
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Configuration ---
HERMES_DIR = os.path.expanduser("~/.hermes")
TOKEN_FILE = os.path.join(HERMES_DIR, ".c2-token")
LOG_DIR = os.path.join(HERMES_DIR, "c2-logs")
DEFAULT_PORT = 8888
CMD_TIMEOUT = 30  # seconds

os.makedirs(LOG_DIR, exist_ok=True)

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "relay.log")),
        logging.StreamHandler(sys.stdout),
    ],
)


def load_auth_token():
    """Load the auth token from file, generating one if missing."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
            if token:
                return token
    token = secrets.token_urlsafe(32)
    with open(TOKEN_FILE, "w") as f:
        f.write(token + "\n")
    os.chmod(TOKEN_FILE, 0o600)
    logging.info(f"Generated new auth token: {token}")
    return token


AUTH_TOKEN = load_auth_token()


def log_command(cmd, exit_code, stdout, stderr, client_ip):
    """Log a command execution to a timestamped file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_cmd = "".join(c if c.isalnum() or c in "._- " else "_" for c in cmd[:60])
    log_file = os.path.join(LOG_DIR, f"{timestamp}_{safe_cmd}.log")

    entry = {
        "timestamp": datetime.now().isoformat(),
        "client_ip": client_ip,
        "command": cmd,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    with open(log_file, "w") as f:
        json.dump(entry, f, indent=2)
    logging.info(f"Command logged: {timestamp}_{safe_cmd}.log")


class C2Handler(BaseHTTPRequestHandler):
    """HTTP request handler for the C2 relay."""

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "alive", "server": "hermes-c2"}).encode())

    def do_POST(self):
        """Handle incoming command requests."""
        client_ip = self.client_address[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        # Validate auth token
        token = payload.get("token", "") or self.headers.get("X-Auth-Token", "")
        if token != AUTH_TOKEN:
            self._respond(401, {"error": "Unauthorized"})
            logging.warning(f"Unauthorized attempt from {client_ip}")
            return

        # Extract command
        cmd = payload.get("command", "").strip()
        if not cmd:
            self._respond(400, {"error": "No command provided"})
            return

        logging.info(f"Executing command from {client_ip}: {cmd[:120]}")

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=CMD_TIMEOUT,
            )
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        except subprocess.TimeoutExpired:
            exit_code = -1
            stdout = ""
            stderr = f"Command timed out after {CMD_TIMEOUT}s"
            logging.warning(f"Command timed out: {cmd[:80]}")
        except Exception as e:
            exit_code = -2
            stdout = ""
            stderr = str(e)
            logging.error(f"Execution error: {e}")

        # Log everything
        log_command(cmd, exit_code, stdout, stderr, client_ip)

        self._respond(200, {
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
        })

    def _respond(self, status_code, data):
        """Send a JSON response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Suppress default HTTP server logging; we use our own."""
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT

    server = HTTPServer(("0.0.0.0", port), C2Handler)
    print(f"Hermes C2 Relay listening on 0.0.0.0:{port}")
    print(f"Auth token: {AUTH_TOKEN}")
    print(f"Log directory: {LOG_DIR}")
    print("Send commands via: curl -X POST http://<host>:<port> \\")
    print(f'  -H "Content-Type: application/json" \\')
    print(f'  -d \'{{"token":"{AUTH_TOKEN}","command":"ls -la"}}\'')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()