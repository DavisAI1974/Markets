#!/usr/bin/env bash
# deploy/aws/markets-update.sh — keep the box's checkout on the latest trunk (code lives on the box, git is
# the source of truth). Run daily by markets-update.timer. Fetches + rebases the canonical trunk; never
# force-pushes, never touches local data caches.
set -euo pipefail
MARKETS_DIR="${MARKETS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TRUNK="claude/kalshi-s79-kickoff-ij8t9o"
cd "$MARKETS_DIR"
git fetch origin "$TRUNK"
# fast-forward the local trunk checkout; if the working tree is dirty, stash-safe: only pull when clean
if [ -z "$(git status --porcelain)" ]; then
  git checkout "$TRUNK" 2>/dev/null || git checkout -B "$TRUNK" "origin/$TRUNK"
  git pull --rebase origin "$TRUNK"
  echo "[markets-update] updated to $(git rev-parse --short HEAD)"
else
  echo "[markets-update] working tree dirty — skipped pull (manual intervention)"
fi
