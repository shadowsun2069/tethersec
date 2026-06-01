#!/usr/bin/env python3
"""
AI Bug Bounty Harness CLI
=========================
Chains gobuster -> Python brute force -> Ollama analysis -> Markdown report.
Target: Termux / Android pentesting environment.

Fixes:
  - Gobuster wildcard detection (--xl <size>) to avoid false positives
  - Python-based Basic auth brute force (hydra has fdsan bug on Android)
  - Default model: minimax-m3:cloud (local CPU models timeout on Android)
  - URL concatenation: url.rstrip('/') + '/' + path.lstrip('/') pattern
  - Ollama query includes system message for better results
"""

import argparse
import base64
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# ── Constants ────────────────────────────────────────────────────────────────
REPORTS_DIR = Path.home() / ".hermes" / "bounty-reports"
WORDLIST = "/data/data/com.termux/files/usr/share/dirb/wordlists/common.txt"
GOBUSTER_TIMEOUT = 120          # seconds
BRUTE_TIMEOUT = 180
OLLAMA_TIMEOUT = 120
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
OLLAMA_MODEL = "minimax-m3:cloud"
HYDRA_COMMON_PATHS = ["/admin", "/wp-admin", "/api"]   # retained as brute paths
HYDRA_USERLIST = ["admin", "root", "user", "test", "guest"]
HYDRA_PASSLIST = ["admin", "password", "123456", "admin123", "root", "letmein", "password123", "passw0rd", "changeme", "welcome"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_cmd(cmd: list[str], timeout: int, label: str) -> tuple[int, str]:
    """Run a subprocess, return (returncode, stdout+stderr)."""
    print(f"[{timestamp()}] 🔧 {label}: {' '.join(cmd)}")
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = r.stdout + r.stderr
        if r.returncode != 0:
            print(f"[{timestamp()}] ⚠️  {label} exited code {r.returncode}")
        return r.returncode, output
    except subprocess.TimeoutExpired:
        print(f"[{timestamp()}] ⏰ {label} timed out after {timeout}s")
        return -1, f"[TIMEOUT after {timeout}s]"
    except FileNotFoundError:
        msg = f"[ERROR] '{cmd[0]}' not found — is it installed?"
        print(f"[{timestamp()}] ❌ {msg}")
        return -2, msg


def detect_wildcard_size(url: str) -> int | None:
    """Probe a random non-existent path to detect the server's wildcard response size."""
    rand_path = f"/{random.randint(100000, 999999)}x{random.randint(100000, 999999)}"
    target = url.rstrip('/') + rand_path
    try:
        req = urllib.request.Request(target)
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read()
            return len(body)
    except urllib.error.HTTPError:
        return None
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def query_ollama(prompt: str) -> str:
    """Send a prompt to Ollama and return the model's text response."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior application security engineer analyzing bug bounty scan results. Be concise, technical, and specific."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        return f"[Ollama HTTP {e.code}] {e.read().decode(errors='replace')}"
    except urllib.error.URLError:
        return "[ERROR] Cannot reach Ollama at http://127.0.0.1:11434 — is it running?"
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return f"[ERROR] Ollama response parse failure: {e}"


def parse_gobuster_table(text: str) -> list[dict]:
    """
    Parse gobuster output into structured findings.
    Gobuster dir output lines look like:
      /path               (Status: 200) [Size: 1234]
    """
    findings = []
    for line in text.splitlines():
        m = re.match(
            r"^(\S+)\s+\(Status:\s*(\d+)\)\s+\[Size:\s*(\d+)\]",
            line.strip(),
        )
        if m:
            findings.append({
                "path": "/" + m.group(1).lstrip("/"),
                "status": int(m.group(2)),
                "size": int(m.group(3)),
                "type": "dir",
            })
    return findings


def brute_basic_auth(url: str, path: str, userlist: list[str] | None = None,
                     passlist: list[str] | None = None) -> list[dict]:
    """
    Python-based Basic auth brute force (replaces hydra, which has fdsan bug on Android).
    Checks for 401 endpoints first, then tries username:password combos.
    Returns list of found credentials.
    """
    if userlist is None:
        userlist = HYDRA_USERLIST
    if passlist is None:
        passlist = HYDRA_PASSLIST

    target = url.rstrip('/') + '/' + path.lstrip('/')
    findings = []

    # First check: is this endpoint actually asking for auth?
    try:
        req = urllib.request.Request(target)
        with urllib.request.urlopen(req, timeout=5) as r:
            # No auth required — endpoint is open
            return []
    except urllib.error.HTTPError as e:
        if e.code != 401:
            # Not a 401 auth challenge — skip
            return []
    except Exception:
        return []

    print(f"[{timestamp()}] 🔑 Brute-forcing Basic auth on {target}")
    print(f"      Users: {len(userlist)}, Passwords: {len(passlist)}")

    for username in userlist:
        for password in passlist:
            auth = base64.b64encode(f"{username}:{password}".encode()).decode()
            req = urllib.request.Request(target, headers={"Authorization": f"Basic {auth}"})
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        body_preview = r.read()[:120].decode(errors='replace')
                        print(f"      🔓 {path} — {username}:{password} (200 OK)")
                        findings.append({
                            "path": path,
                            "username": username,
                            "password": password,
                            "type": "credential",
                            "body_preview": body_preview,
                        })
                        # Found one per user — move to next user
                        break
            except urllib.error.HTTPError as e:
                if e.code != 401:
                    pass  # Unexpected status, continue
            except Exception:
                pass

    return findings


def write_report(url: str, gob_findings: list[dict],
                 gob_raw: str, brute_findings: list[dict],
                 brute_raw: str, ai_analysis: str) -> Path:
    """Write a Markdown report and return the file path."""
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", url)
    fname = f"bounty_{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.md"
    report_path = REPORTS_DIR / fname
    report_path.parent.mkdir(parents=True, exist_ok=True)

    statuses = sorted({f["status"] for f in gob_findings})
    summary_statuses = ", ".join(str(s) for s in statuses) if statuses else "none found"
    cred_count = len(brute_findings)

    lines = []
    lines.append("# AI Bug Bounty Report\n")
    lines.append(f"**Target:** `{url}`  \n")
    lines.append(f"**Scan date:** {timestamp()}  \n")
    lines.append(f"**Tool:** AI Bug Bounty Harness CLI\n")
    lines.append("---\n")

    # ── Executive Summary ──
    lines.append("## Executive Summary\n")
    lines.append(f"- **Gobuster findings:** {len(gob_findings)} paths discovered "
                 f"(status codes: {summary_statuses})")
    lines.append(f"- **Credentials found:** {cred_count}")
    lines.append(f"- **AI model:** {OLLAMA_MODEL}")
    lines.append("")

    # ── Findings Table ──
    lines.append("## Findings Table\n")
    if gob_findings:
        lines.append("| Path | Status | Size | Type |")
        lines.append("|------|--------|------|------|")
        for f in gob_findings:
            lines.append(f"| `{f['path']}` | {f['status']} | {f['size']} | {f['type']} |")
    else:
        lines.append("*No gobuster findings.*")
    lines.append("")

    if brute_findings:
        lines.append("### Credential Findings\n")
        lines.append("| Path | Username | Password |")
        lines.append("|------|----------|----------|")
        for f in brute_findings:
            lines.append(f"| `{f['path']}` | `{f['username']}` | `{f['password']}` |")
    lines.append("")

    # ── Vulnerability Assessment ──
    lines.append("## AI Vulnerability Assessment\n")
    lines.append(ai_analysis)
    lines.append("\n")

    # ── Recommended Next Commands ──
    lines.append("## Recommended Next Commands\n")
    lines.append("```bash")
    if gob_findings:
        # Suggest deeper scanning on found paths
        active_paths = [f["path"] for f in gob_findings if f["status"] < 400]
        if active_paths:
            lines.append("# Re-run gobuster with extensions on interesting paths")
            lines.append(
                f"gobuster dir -u {url} -w {WORDLIST} -x php,asp,aspx,jsp,html,txt "
                f"-t 30 -q"
            )
            lines.append("")
            lines.append("# Nikto scan on discovered paths")
            for p in active_paths[:3]:  # top 3 only to avoid wall of text
                lines.append(f"nikto -h {url.rstrip('/')}{p}")
    lines.append("")
    lines.append("# Deeper directory brute-force with a bigger wordlist")
    lines.append(
        f"gobuster dir -u {url} -w /usr/share/wordlists/dirbuster/"
        f"directory-list-2.3-medium.txt -t 40 -q"
    )
    lines.append("")
    lines.append("# Scan for SQLi / XSS with sqlmap")
    lines.append(f"sqlmap -u {url} --batch --crawl=2")
    lines.append("")
    lines.append("# Full Nmap service scan")
    lines.append(f"nmap -sV -sC -p- $(echo {url} | sed 's|.*//||;s|[:/].*||')")
    lines.append("```")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Bug Bounty Harness — chains gobuster → brute force → Ollama → report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 bounty-harness.py http://127.0.0.1:9000\n"
            "  python3 bounty-harness.py http://example.com --no-hydra\n"
            "  python3 bounty-harness.py http://target --skip-ai\n"
        ),
    )
    parser.add_argument("url", help="Target URL (e.g. http://127.0.0.1:9000)")
    parser.add_argument("--no-gobuster", action="store_true",
                        help="Skip gobuster directory scan")
    parser.add_argument("--no-hydra", action="store_true",
                        help="Skip brute-force phase")
    parser.add_argument("--skip-ai", action="store_true",
                        help="Skip Ollama analysis (still generates a basic report)")
    parser.add_argument("--wordlist", default=WORDLIST,
                        help=f"Path to wordlist (default: {WORDLIST})")
    parser.add_argument("--threads", type=int, default=20,
                        help="Gobuster thread count (default: 20)")
    parser.add_argument("--report-dir", default=str(REPORTS_DIR),
                        help="Output directory for reports")
    args = parser.parse_args()

    url = args.url.rstrip("/")
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║   AI Bug Bounty Harness — {OLLAMA_MODEL:<16}║")
    print(f"║   Target: {url:<42}║")
    print(f"║   Started: {timestamp():<39}║")
    print(f"╚══════════════════════════════════════════════════╝")
    print()

    all_gobuster_findings = []
    all_brute_findings = []
    gob_raw = ""
    brute_raw = ""

    # ── Phase 1: Gobuster ────────────────────────────────────────────────────
    if not args.no_gobuster:
        wordlist_path = args.wordlist
        if not os.path.isfile(wordlist_path):
            print(f"[WARN] Wordlist not found at {wordlist_path}, skipping gobuster.")
        else:
            # Detect wildcard response size before gobuster
            wildcard_size = detect_wildcard_size(url)
            exclude_flag = []
            if wildcard_size is not None:
                print(f"[{timestamp()}] 🎯 Detected wildcard response size: {wildcard_size}b, auto-excluding")
                exclude_flag = ["--xl", str(wildcard_size)]
            else:
                print(f"[{timestamp()}] ℹ️  No wildcard response detected")

            gob_cmd = [
                "gobuster", "dir",
                "-u", url,
                "-w", wordlist_path,
                "-t", str(args.threads),
                "-q",
            ] + exclude_flag
            rc, gob_raw = run_cmd(gob_cmd, GOBUSTER_TIMEOUT, "gobuster dir")
            if rc in (0, 1):
                all_gobuster_findings = parse_gobuster_table(gob_raw)
                print(f"[{timestamp()}] ✓ Gobuster: {len(all_gobuster_findings)} paths found")
                for f in all_gobuster_findings:
                    print(f"      {f['path']:<30} Status: {f['status']:<5} Size: {f['size']}")
            print()
    else:
        print(f"[{timestamp()}] ⏩ Gobuster skipped (--no-gobuster)")

    # ── Phase 2: Python brute-force on common paths ──────────────────────────
    if not args.no_hydra:
        for path in HYDRA_COMMON_PATHS:
            creds = brute_basic_auth(url, path, userlist=HYDRA_USERLIST, passlist=HYDRA_PASSLIST)
            all_brute_findings.extend(creds)
            for c in creds:
                brute_raw += f"[{path}] {c['username']}:{c['password']}\n"

        print(f"[{timestamp()}] ✓ Brute force: {len(all_brute_findings)} credentials found")
        print()
    else:
        print(f"[{timestamp()}] ⏩ Brute force skipped (--no-hydra)")

    # ── Phase 3: Ollama AI Analysis ──────────────────────────────────────────
    ai_text = ""
    if not args.skip_ai:
        print(f"[{timestamp()}] 🤖 Querying Ollama model '{OLLAMA_MODEL}'...")

        # Build prompt from raw outputs
        prompt_parts = [
            "You are a senior application security engineer analyzing bug bounty scan results.",
            f"Target: {url}",
            "",
            "=== GOBUSTER FINDINGS ===",
            gob_raw if gob_raw.strip() else "(no results or scan skipped)",
            "",
            "=== BRUTE FORCE FINDINGS ===",
            brute_raw if brute_raw.strip() else "(no results or scan skipped)",
            "",
            "Please provide:",
            "1. A brief executive summary of risk level (Critical / High / Medium / Low / Info).",
            "2. Notable vulnerabilities or misconfigurations observed.",
            "3. The most impactful next step an attacker would take.",
            "4. Recommended defensive actions.",
            "",
            "Format your answer in clear Markdown sections.",
        ]
        prompt = "\n".join(prompt_parts)
        ai_text = query_ollama(prompt)
        print(f"[{timestamp()}] ✓ AI analysis received ({len(ai_text)} chars)")
        print()
    else:
        ai_text = "*AI analysis skipped by user flag.*"
        print(f"[{timestamp()}] ⏩ AI analysis skipped (--skip-ai)")

    # ── Phase 4: Generate Report ─────────────────────────────────────────────
    report_path = write_report(
        url, all_gobuster_findings, gob_raw,
        all_brute_findings, brute_raw, ai_text,
    )
    print(f"[{timestamp()}] ✅ Report saved: {report_path}")
    print(f"[{timestamp()}] 🎯 Scan complete.")
    print()

    # Print quick summary to stdout
    print("── Quick Summary ──")
    print(f"  Paths found:     {len(all_gobuster_findings)}")
    print(f"  Credentials:     {len(all_brute_findings)}")
    print(f"  Report:          {report_path}")
    print(f"───────────────────")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n[{timestamp()}] ⛔ Interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[{timestamp()}] ❌ Unhandled error: {e}", file=sys.stderr)
        sys.exit(1)