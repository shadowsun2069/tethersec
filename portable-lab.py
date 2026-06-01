#!/usr/bin/env python3
"""
portable-lab.py — Portable Security Lab for Termux/Android
Spins up vulnerable HTTP targets for practicing gobuster/hydra/dirb.
No Docker needed — pure Python stdlib.

Usage:
  python3 portable-lab.py            # 3 targets on ports 9000-9002
  python3 portable-lab.py --ports 5  # 5 targets on ports 9000-9004
  python3 portable-lab.py --kill     # Kill all running lab servers
"""

import http.server, socketserver, base64, os, sys, signal, json, threading, time, argparse

START_PORT = 9000
LAB_PID_FILE = '/data/data/com.termux/files/home/.hermes/scripts/.lab_pids'

class VulnHTTP(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def do_GET(self):
        path = self.path.rstrip('/') or '/'

        if path in ('/.git/config', '/.git/HEAD'):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'[core]\n\trepositoryformatversion = 0')
            return
        if path == '/admin':
            auth = self.headers.get('Authorization', '')
            if auth.startswith('Basic '):
                decoded = base64.b64decode(auth[6:]).decode()
                if decoded == 'admin:password123':
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'Admin panel - user database exposed')
                    return
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="Admin"')
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return
        if path == '/api/users':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"users": [{"id": 1, "role": "admin", "password_hash": "5e884898da28047151d0e56f8dc62927"}]}).encode())
            return
        if path == '/wp-admin':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'WordPress login page - version 4.7')
            return
        if path == '/backup':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'DB backup: users_2024.sql contains password hashes')
            return
        if '/phpmyadmin' in path:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'phpMyAdmin - MySQL admin interface exposed')
            return
        if path == '/api/flag':
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f'FLAG{{h4ck3d_th3_l4b_{os.urandom(4).hex()}}}'.encode())
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'<html><body><h1>Index of /</h1><a href="admin">admin</a><br><a href="backup">backup</a></body></html>')


def run_server(port, vuln_handlers):
    handler = type(f'VulnHTTP{port}', (VulnHTTP,), {})
    s = socketserver.TCPServer(('127.0.0.1', port), handler)
    vuln_handlers[port] = s
    s.serve_forever()


def main():
    parser = argparse.ArgumentParser(description='Portable Security Lab')
    parser.add_argument('--ports', type=int, default=3, help='Number of target ports (default: 3)')
    parser.add_argument('--kill', action='store_true', help='Kill all lab servers')
    args = parser.parse_args()

    if args.kill:
        if os.path.exists(LAB_PID_FILE):
            with open(LAB_PID_FILE) as f:
                pids = [int(line.strip()) for line in f if line.strip()]
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except (OSError, ProcessLookupError):
                    pass
            os.remove(LAB_PID_FILE)
            print(f"[*] Killed {len(pids)} lab server(s)")
        else:
            print("[*] No lab PID file found — servers may still be running")
        return

    os.makedirs(os.path.dirname(LAB_PID_FILE), exist_ok=True)
    vuln_handlers = {}
    threads = []
    parent_pid = os.getpid()

    print(f"[*] Starting {args.ports} vulnerable targets on ports {START_PORT}-{START_PORT+args.ports-1}")
    for i in range(args.ports):
        port = START_PORT + i
        t = threading.Thread(target=run_server, args=(port, vuln_handlers), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.1)

    # Save PIDs
    with open(LAB_PID_FILE, 'w') as f:
        for p in range(START_PORT, START_PORT + args.ports):
            f.write(f"{parent_pid}\n")

    print(f"\n  Targets ready:")
    for i in range(args.ports):
        port = START_PORT + i
        print(f"    http://127.0.0.1:{port}/")
    print(f"\n  Commands to run:")
    print(f"    gobuster dir -u http://127.0.0.1:{START_PORT}/ -w /usr/share/dirb/wordlists/common.txt")
    print(f"    hydra -l admin -P passwords.txt 127.0.0.1 http-get /admin -s {START_PORT}")
    print(f"\n  Stop: python3 portable-lab.py --kill")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        for s in vuln_handlers.values():
            s.shutdown()


if __name__ == '__main__':
    main()