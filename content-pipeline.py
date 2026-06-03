#!/data/data/com.termux/files/usr/bin/env python3
"""
Content Creation Pipeline for Big Country.
Reads recent nb notes and produces:
  1) a newsletter markdown issue
  2) a podcast script chunked for TTS (~3-5 min read)

Usage:
  python3 content-pipeline.py              # uses last 24h of notes
  python3 content-pipeline.py --days 7     # uses last week
  python3 content-pipeline.py --limit 5    # uses last 5 notes
"""
import os, sys, re, argparse
from datetime import datetime, timedelta
from pathlib import Path

def parse_args():
    p = argparse.ArgumentParser(description="nb → newsletter + podcast script")
    p.add_argument("--days", type=int, default=1, help="lookback window in days (default 1)")
    p.add_argument("--limit", type=int, default=0, help="alternatively limit to N most recent notes")
    return p.parse_args()

def recent_notes(nb_path, days=1, limit=0):
    cutoff = datetime.now().timestamp() - (days * 86400)
    notes = []
    for md in sorted(Path(nb_path).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if md.name.startswith("."):
            continue
        mtime = md.stat().st_mtime
        if limit == 0 and mtime < cutoff:
            break
        with open(md, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
        # strip nb frontmatter
        body = re.sub(r"^---\n.*?\n---\n", "", raw, count=1, flags=re.DOTALL).strip()
        title = md.stem
        # try to extract header/title line
        lines = body.splitlines()
        first_line = lines[0].strip().lstrip("#").strip() if lines else title
        notes.append({"path": md, "mtime": mtime, "title": first_line, "body": body})
        if limit and len(notes) >= limit:
            break
    return list(reversed(notes))  # chronological order

def build_newsletter(notes):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# Tether Dispatch — {date_str}",
        "",
        "*Notes from the S26 Ultra, compiled by Tether.*",
        "",
        "---",
        "",
    ]
    for n in notes:
        lines.append(f"## {n['title']}")
        lines.append("")
        lines.append(n["body"])
        lines.append("")
        lines.append("---")
        lines.append("")
    lines.append("*Sent from the Louisiana node.*")
    return "\n".join(lines)

def build_podcast_script(notes):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"Tether Radio — Episode {date_str.replace('-','')}",
        "",
        "[OPEN: soft lo-fi beat, 3 seconds]",
        "",
        f"Hey. This is Big Country. It is {datetime.now().strftime('%A, %B %-d')}.",
        "I have been thinking again. Here is what made it to the notebook.",
        "",
    ]
    for i, n in enumerate(notes, 1):
        lines.append(f"Think {i}: {n['title']}.")
        # remove markdown links/headers for speech
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", n["body"])
        clean = re.sub(r"^#+\s*", "", clean, flags=re.MULTILINE)
        clean = clean.replace("*", "").replace("`", "")
        # TTS works best with shorter chunks
        for para in clean.split("\n"):
            para = para.strip()
            if para:
                lines.append(para)
        lines.append("Pause.")
        lines.append("")
    lines.append("That is all for tonight. Keep your eyes open. This is Big Country, signing off.")
    lines.append("")
    lines.append("[OUTRO]")
    return "\n".join(lines)

def chunk_for_tts(text, max_chars=1500):
    """Split podcast script into edge-tts friendly chunks."""
    chunks = []
    current = ""
    for line in text.splitlines():
        if len(current) + len(line) + 1 > max_chars:
            chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks

def main():
    args = parse_args()
    nb_home = os.path.join(os.environ["HOME"], ".nb", "home")
    if not os.path.isdir(nb_home):
        print(f"nb home not found: {nb_home}")
        sys.exit(1)

    notes = recent_notes(nb_home, days=args.days, limit=args.limit)
    if not notes:
        print("No recent notes found. Add some with nb add.")
        sys.exit(0)

    out_dir = os.path.join(os.environ["HOME"], "storage", "shared", "content-creation")
    os.makedirs(out_dir, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d")
    nl_path = os.path.join(out_dir, f"{stamp}_newsletter.md")
    pod_path = os.path.join(out_dir, f"{stamp}_podcast.txt")
    chunks_path = os.path.join(out_dir, f"{stamp}_podcast_chunks.txt")

    newsletter = build_newsletter(notes)
    with open(nl_path, "w", encoding="utf-8") as f:
        f.write(newsletter)
    print(f"Newsletter: {nl_path}")

    podcast = build_podcast_script(notes)
    with open(pod_path, "w", encoding="utf-8") as f:
        f.write(podcast)
    print(f"Podcast script: {pod_path}")

    chunks = chunk_for_tts(podcast)
    with open(chunks_path, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(chunks, 1):
            f.write(f"\n--- CHUNK {i} ---\n{chunk}\n")
    print(f"TTS chunks: {chunks_path} ({len(chunks)} file(s) ready)")

    print(f"\nReady to publish. Check {out_dir}")

if __name__ == "__main__":
    main()
