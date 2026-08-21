# TetherSec Mobile

> **Mobile pentest suite for Android/Termux. No Docker, no laptop.**

A self-contained security testing toolkit that runs entirely on your phone. Spin up vulnerable targets, run AI-assisted recon, generate bug bounty reports, and relay commands — all from Termux.

---

## ⚠️ Legal Disclaimer

TetherSec is for **authorized security testing only** — your own systems, or systems you have explicit written permission to test. Unauthorized access to computer systems is illegal. You are solely responsible for how you use these tools.

---

## Quick Install

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/shadowsun2069/tethersec/main/tethersec-install.sh)"
```

Then restart Termux (or run `source ~/.bashrc`) and type:

```bash
tethersec
```

---

## Tools

| Command | What it does |
|---------|-------------|
| `tethersec` | Interactive launch menu |
| `tether-lab` | Spin up vulnerable HTTP targets on ports 9000+ (no Docker) |
| `tether-recon <url>` | gobuster → brute force → Ollama AI analysis |
| `tether-bounty <url>` | Full pipeline → AI vuln assessment → Markdown report |
| `tether-c2` | Mobile C2 HTTP relay on port 8888 (localhost only) |

---

## Workflow

```bash
# 1. Start a practice lab (3 vulnerable targets)
tether-lab --ports 3

# 2. Run AI-assisted recon against a target
tether-recon http://127.0.0.1:9000

# 3. Run the full bounty pipeline (scan + AI report)
tether-bounty http://127.0.0.1:9000
```

Reports are saved to `~/.hermes/bounty-reports/`.

---

## What's Inside

### `tether-lab` — Portable Vulnerable Lab
Pure-Python vulnerable HTTP server. No Docker required. Includes:
- `.git/config` exposure
- Basic-auth protected `/admin` (default creds `admin:password123`)
- Exposed `/api/users` with password hashes
- `/wp-admin`, `/backup`, `/phpmyadmin` misconfigurations
- A capture-the-flag endpoint

### `tether-recon` — AI Recon
Chains directory busting → endpoint probing → brute force → AI analysis:
- **Gobuster** with automatic wildcard-response detection (kills false positives)
- **Python Basic-auth brute force** (replaces hydra, which is broken on Android due to the fdsan bug)
- **Ollama AI analysis** of findings, ranked by severity, with recommended next steps

### `tether-bounty` — Bounty Harness
Full pipeline that ends in a clean Markdown vulnerability report:
- Executive summary with risk level
- Findings table
- AI vulnerability assessment
- Recommended next commands

### `tether-c2` — C2 Relay
Authenticated command relay on port 8888. **Binds to localhost by default** for safety. Token stored in `~/.hermes/.c2-token` (chmod 600).

---

## Requirements

- Android 10+ with [Termux](https://termux.dev/)
- `python` and `golang` (auto-installed by the setup script)
- [Ollama](https://ollama.com) running locally or cloud-connected (for AI analysis)

---

## Why This Exists

Most pentest tooling assumes a laptop and Docker. TetherSec proves you can do real security work from a phone. It's built for learning, bug bounty hunting, and portable testing.

---

## License

[MIT](LICENSE) — free to use, modify, and build on. Just keep the attribution.
