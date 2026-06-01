# TetherSec Mobile

Mobile pentest suite for Android/Termux. No Docker, no laptop.

```
bash -c "$(curl -fsSL https://raw.githubusercontent.com/shadowsun2069/tethersec/main/tethersec-install.sh)"
```

## Tools

| Command | What it does |
|---------|-------------|
| `tethersec` | Launch menu |
| `tether-lab` | Vulnerable HTTP targets on ports 9000+ (no Docker) |
| `tether-recon <url>` | gobuster → brute force → Ollama AI analysis |
| `tether-bounty <url>` | Full pipeline → Markdown vulnerability report |
| `tether-c2` | Mobile C2 HTTP relay on port 8888 |

## Workflow

```
tether-lab --ports 3        # Start vulnerable targets
tether-recon http://127.0.0.1:9000  # Recon + AI analysis
tether-bounty http://127.0.0.1:9000 # Full scan + report
```

Reports saved to `~/.hermes/bounty-reports/`.

## Requirements

- Android 10+ with Termux
- `pkg install python golang` (auto-installed by setup script)
- Ollama running locally or cloud-connected