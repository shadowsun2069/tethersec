#!/usr/bin/env python3
"""
ai-recon.py — AI-Powered Recon for Termux
Runs gobuster/hydra/dirb and pipes results through an Ollama model
for automated post-processing, vulnerability assessment, and next-steps.

Fixes over original:
  - Gobuster wildcard detection (--wildcard -l + size filtering)
  - Defaults to minimax-m3:cloud (local CPU too slow for LLM inference)
  - Python-based Basic auth brute force (hydra broken on Android/fdsan)
  - Content probing on found endpoints
  - Smart timeout handling

Usage:
  python3 ai-recon.py http://127.0.0.1:9000               # Full scan
  python3 ai-recon.py http://127.0.0.1:9000 --model kimi-k2.6:cloud
  python3 ai-recon.py http://127.0.0.1:9000 --gobuster-only
  python3 ai-recon.py http://127.0.0.1:9000 --deep
"""

import subprocess, json, sys, os, argparse, time, urllib.request, base64

OLLAMA_URL = "http://127.0.0.1:11434"
WORDLIST = "/data/data/com.termux/files/usr/share/dirb/wordlists/common.txt"
DEEP_WORDLIST = "/data/data/com.termux/files/usr/share/dirb/wordlists/big.txt"
LAB_WORDLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab-wordlist.txt")


def query_ollama(model, prompt, system="You are a penetration testing assistant. Be concise and technical."):
    """Query any Ollama model (local or cloud) via OpenAI-compatible endpoint."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "max_tokens": 1024,
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERROR] Ollama query failed: {e}"


def detect_wildcard_size(url):
    """Probe a non-existent path to detect wildcard response size."""
    import random
    rand_path = f"/{random.randint(100000, 999999)}x{random.randint(100000, 999999)}"
    try:
        req = urllib.request.Request(url.rstrip('/') + rand_path)
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read()
            return len(body)
    except Exception:
        return None


def run_gobuster(url, wordlist, threads=30):
    """Run gobuster dir scan with auto wildcard exclusion."""
    wildcard_size = detect_wildcard_size(url)
    if wildcard_size:
        print(f"  [*] Wildcard size={wildcard_size}b, auto-excluding")
        exclude_flag = ["--xl", str(wildcard_size)]
    else:
        exclude_flag = []
    print(f"[*] gobuster dir -u {url} -w {os.path.basename(wordlist)} -t {threads}")
    start = time.time()
    try:
        cmd = ["gobuster", "dir", "-u", url, "-w", wordlist,
               "-t", str(threads), "-q"] + exclude_flag
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        elapsed = time.time() - start
        lines = [l for l in result.stdout.split('\n') if 'Size:' in l]

        findings = []
        for l in lines:
            parts = l.split()
            if len(parts) >= 4:
                path = parts[0]
                # Parse "Status: 200" or "Status: 401"
                status = parts[2].strip('()')
                size = parts[4].strip('[]') if len(parts) > 4 else '?'
                findings.append({"path": path, "status": status, "size": size})

        return {"findings": findings, "raw": result.stdout, "elapsed": elapsed,
                "count": len(findings), "wildcard_size": wildcard_size}
    except subprocess.TimeoutExpired:
        return {"findings": [], "raw": "[TIMEOUT]", "elapsed": 180, "count": 0, "error": "timeout"}


def probe_endpoints(url, paths):
    """Probe specific paths with curl and return real content/size/status."""
    print(f"[*] Probing endpoints: {len(paths)} paths")
    results = []
    for path in paths:
        target = url.rstrip('/') + '/' + path.lstrip('/')
        try:
            req = urllib.request.Request(target)
            with urllib.request.urlopen(req, timeout=5) as r:
                body = r.read()
                results.append({
                    "path": path,
                    "status": r.status,
                    "size": len(body),
                    "body": body[:200].decode(errors='replace')
                })
        except urllib.request.HTTPError as e:
            results.append({"path": path, "status": e.code, "size": 0, "body": ""})
        except Exception as e:
            results.append({"path": path, "status": 0, "size": 0, "body": f"Error: {e}"})
    return results


def brute_basic_auth(url, path, user="admin", wordlist=None):
    """Python-based Basic auth brute force (alternative to hydra on Android)."""
    if wordlist is None:
        # Generate common passwords
        wordlist = ["password123", "admin", "123456", "letmein", "secret",
                     "passw0rd", "qwerty", "test", "root", "admin123",
                     "password", "admin1", "changeme", "welcome", "admin2024"]

    target = url.rstrip('/') + '/' + path.lstrip('/')
    print(f"[*] Basic auth brute: {user}:<password> on {target} ({len(wordlist)} passwords)")
    start = time.time()

    for pw in wordlist:
        auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
        req = urllib.request.Request(target, headers={"Authorization": f"Basic {auth}"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    elapsed = time.time() - start
                    return {"found": True, "user": user, "password": pw,
                            "body": r.read()[:200].decode(errors='replace'), "elapsed": elapsed}
        except urllib.request.HTTPError as e:
            if e.code != 401:
                pass  # Unexpected
        except Exception:
            pass

    elapsed = time.time() - start
    return {"found": False, "elapsed": elapsed}


def parse_url(url):
    """Extract host and port from URL."""
    default_port = 80 if url.startswith("http://") else 443
    host = url.replace("http://", "").replace("https://", "").split("/")[0]
    if ":" in host:
        parts = host.split(":")
        return parts[0], int(parts[1])
    return host, default_port


def main():
    parser = argparse.ArgumentParser(description="AI-Powered Recon")
    parser.add_argument("url", help="Target URL (e.g. http://127.0.0.1:9000)")
    parser.add_argument("--model", default="minimax-m3:cloud",
                        help="Ollama model (default: minimax-m3:cloud)")
    parser.add_argument("--gobuster-only", action="store_true", help="Skip brute force")
    parser.add_argument("--deep", action="store_true", help="Use big.txt wordlist")
    parser.add_argument("--brute-wordlist", help="Custom password list for brute force")
    parser.add_argument("--no-probe", action="store_true", help="Skip endpoint probing")
    args = parser.parse_args()

    wordlist = DEEP_WORDLIST if args.deep else WORDLIST
    host, port = parse_url(args.url)
    base_url = f"http://{host}:{port}"

    print(f"=== AI-Powered Recon ===")
    print(f"Target: {base_url}")
    print(f"Model:  {args.model}")
    print(f"Date:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # ————— Phase 1: Gobuster Directory Busting —————
    print("=== Phase 1: Directory Busting ===")
    gb = run_gobuster(base_url, wordlist)
    print(f"  Found {gb['count']} paths in {gb['elapsed']:.1f}s")
    for f in gb['findings']:
        print(f"    {f['path']} (Status: {f['status']}, Size: {f['size']})")
    if gb.get('error'):
        print(f"  [!] gobuster error: {gb['error']}")
    print()

    # ————— Phase 1b: Endpoint Probing —————
    if not args.no_probe and gb['findings']:
        print("=== Phase 1b: Endpoint Content Probe ===")
        paths = [f['path'] for f in gb['findings']]
        probe_results = probe_endpoints(base_url, paths)
        interesting = [p for p in probe_results if p['status'] == 200 and p['size'] > 50]
        for p in probe_results:
            snippet = p['body'][:80].replace('\n', ' ') if p['body'] else ''
            print(f"    {p['path']} ({p['status']}, {p['size']}b) {snippet}")
        print()

    # ————— Phase 2: Brute Force —————
    brute_result = None
    if not args.gobuster_only:
        print("=== Phase 2: Brute Force ===")
        # Check for auth endpoints
        auth_endpoints = [f['path'] for f in gb['findings']
                          if f['status'] in ('401', '403') or 'admin' in f['path']]
        if not auth_endpoints:
            auth_endpoints = ['/admin']

        for ep in auth_endpoints[:3]:  # Try up to 3 auth endpoints
            pwlist = None
            if args.brute_wordlist and os.path.exists(args.brute_wordlist):
                pwlist = open(args.brute_wordlist).read().splitlines()
            result = brute_basic_auth(base_url, ep, wordlist=pwlist)
            brute_result = result
            if result['found']:
                print(f"  [+] CREDENTIALS FOUND: {result['user']}:{result['password']}")
                print(f"  [+] Body: {result['body'][:120]}")
                break
            else:
                print(f"  [-] {ep}: no credentials found in {result['elapsed']:.1f}s")
        print()

    # ————— Phase 3: AI Analysis —————
    print("=== Phase 3: AI Analysis ===")
    context = f"Target: {base_url}\n\nDirectory Scan Results ({gb['count']} findings):\n"
    for f in gb['findings']:
        context += f"  {f['path']} ({f['status']}) - {f['size']} bytes\n"

    if brute_result:
        if brute_result['found']:
            context += f"\nCredentials found: {brute_result['user']}:{brute_result['password']}\n"
        else:
            context += "\nBrute force: no credentials found (tried common passwords)\n"

    prompt = f"""Analyze these recon results and answer:

1. What are the most interesting findings? Rank by severity.
2. What's the likely attack path based on what's exposed?
3. What should the next scan step be? (specific endpoints to probe deeper)
4. Any obvious misconfigurations or security issues?

{context}

Be specific — reference actual paths and status codes found."""

    print(f"[*] Querying {args.model}...")
    analysis = query_ollama(args.model, prompt)
    print(f"\n{analysis}\n")

    # ————— Phase 4: Action Plan —————
    action_prompt = f"""Based on these recon results, write exactly 3 terminal commands to run next for deeper recon or exploitation. One command per line, no explanations.

{context}"""
    print("=== Phase 4: Recommended Commands ===")
    commands = query_ollama(args.model, action_prompt)
    print(f"\n{commands}\n")

    print("[+] ai-recon.py complete")


if __name__ == '__main__':
    main()