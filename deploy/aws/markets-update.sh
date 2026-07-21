#!/usr/bin/env bash
# Keep the box on the configured code branch. Never touches data caches or services.
set -euo pipefail
MARKETS_DIR="${MARKETS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
TRUNK="${MARKETS_CODE_BRANCH:-claude/kalshi-s79-kickoff-ij8t9o}"
cd "$MARKETS_DIR"
git fetch origin "$TRUNK"
if [ -z "$(git status --porcelain)" ]; then
  git checkout "$TRUNK" 2>/dev/null || git checkout -B "$TRUNK" "origin/$TRUNK"
  git pull --ff-only origin "$TRUNK"
  echo "[markets-update] branch=$TRUNK commit=$(git rev-parse --short HEAD)"
else
  echo "[markets-update] working tree dirty — skipped pull"
fi
