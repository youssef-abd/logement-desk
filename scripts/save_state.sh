#!/usr/bin/env bash
# Commit and push state/seen_listings.json when it changed. Prints SAVED or FAILED.
set -u
cd "$(dirname "$0")/.."
[ "${GITHUB_REF:-refs/heads/main}" = "refs/heads/main" ] || { echo "FAILED: refusing to push state from a ref other than main"; exit 1; }
git add -- state/seen_listings.json 2>/dev/null
if git diff --cached --quiet; then
  echo "SAVED (nothing changed)"
  exit 0
fi
git commit -q -m "state: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
for i in 1 2 3; do
  if git pull --rebase --autostash -q origin main && git push -q origin HEAD:main; then
    echo "SAVED to main: $(git rev-parse --short HEAD)"
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep 3
done
echo "FAILED: could not push"
exit 1
