#!/data/data/com.termux/files/usr/bin/bash
# Hermes backup script — runs daily, stashes configs + logs + scripts
# Pushes to GitHub for off-device redundancy
set -euo pipefail

SRC="/data/data/com.termux/files/home/.hermes"
LOCAL_DEST="/data/data/com.termux/files/home/storage/shared/hermes-backup"
STAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${LOCAL_DEST}/hermes_${STAMP}.tar.gz"

mkdir -p "${LOCAL_DEST}"

# Exclude heavy temp/venv/node_modules from backup
# Use --warning=no-file-changed to ignore the "file changed as we read it" race
# that occurs when other cron jobs (gateway logs, memory sync) write during backup
tar -czf "${ARCHIVE}" \
  --warning=no-file-changed \
  --exclude='*/tmp/*' \
  --exclude='*/venv/*' \
  --exclude='*/node_modules/*' \
  --exclude='*/__pycache__/*' \
  --exclude='.hermes/hermes-agent/*' \
  --exclude='*/.ollama/*' \
  -C "$(dirname "${SRC}")" "$(basename "${SRC}")"

# Keep only last 7 local backups
ls -t "${LOCAL_DEST}"/hermes_*.tar.gz | tail -n +8 | xargs -r rm -f

echo "Local backup: ${ARCHIVE}"

# GitHub push (configs only — lighter)
WORKDIR=$(mktemp -d)
cp -r "${SRC}/config.yaml" "${SRC}/.env" "${SRC}/skills" "${SRC}/scripts" "${WORKDIR}/" 2>/dev/null || true

cd "${WORKDIR}"
git init -q
git config user.email "tether-backup@hermes"
git config user.name "Tether Backup"
echo "*.tar.gz" > .gitignore
echo ".env" >> .gitignore

# Don't commit .env with actual secrets — just the file existence
rm -f .env
touch .env.sample
echo "# API keys go in .env — this file is just a placeholder" > .env.sample

git add -A
git commit -q -m "hermes config backup ${STAMP}"
git remote add origin "https://github.com/shadowsun2069/hermes-backup.git"

if git push -q origin master 2>/dev/null; then
  echo "Remote backup: pushed to github.com/shadowsun2069/hermes-backup"
else
  echo "Remote backup: skipped (push failed — repo may need initial commit or token)"
fi

rm -rf "${WORKDIR}"
