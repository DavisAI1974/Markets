#!/usr/bin/env bash
# BR-0 (plan PLAN_CYCLE0_BEDROCK_20260921.md; Greg, 2026-09-21: no scratchpad, "there is nothing local"): the pinned
# producers, lineage ccode/frankie-receiver-feed-20260916 at 2ebb8ce8, are reached through a git worktree INSIDE the
# repo, <repo>/.producers-2ebb8ce8 (gitignored). The box holds the same commit at /opt/frankie-box/producers
# (frankie_box_stage_producers.sh); tests and CI reach this one through FRANKIE_BOX_PRODUCERS (default = this path).
# Idempotent: an existing worktree at the pin is left alone; a directory at any other commit is REFUSED, never moved.
# Prints the commit and the sha256 of native_replay_driver.py (pinned in frankie_box_stage_producers.sh). Nothing deleted.
set -euo pipefail
LINEAGE=ccode/frankie-receiver-feed-20260916
COMMIT=2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134
DRIVER=research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py
DRIVER_SHA256=67996f3e1da9f6584bcca888eefe015c3b31508b9451335a76e2f49bfd7a8762
REPO=$(git rev-parse --show-toplevel)
DIR="$REPO/.producers-${COMMIT:0:8}"
export GIT_TERMINAL_PROMPT=0

if [ -e "$DIR" ]; then
  # a worktree is identified by git's own registry and by its top level being the directory itself: a plain directory at
  # this path would otherwise resolve the PARENT repository's HEAD and be misread
  git worktree list --porcelain | grep -Fxq "worktree $DIR" || { echo "refusing: $DIR exists and is not the producers worktree (nothing moved)"; exit 2; }
  top=$(git -C "$DIR" rev-parse --show-toplevel 2>/dev/null) || { echo "refusing: $DIR is not a git checkout (nothing moved)"; exit 2; }
  [ "$top" = "$DIR" ] || { echo "refusing: $DIR is inside the checkout $top, not the producers worktree (nothing moved)"; exit 2; }
  head=$(git -C "$DIR" rev-parse HEAD)
  [ "$head" = "$COMMIT" ] || { echo "refusing: $DIR is at $head, not the pinned $COMMIT (nothing moved)"; exit 2; }
  echo "producers worktree present at the pin"
else
  # a stale registration (the directory gone, git's metadata kept) would make the add fail: prune only when the path is absent
  git worktree prune
  if ! git cat-file -e "$COMMIT^{commit}" 2>/dev/null; then
    # a shallow CI checkout: fetch the pinned commit itself first (one commit), then the lineage as a fallback
    git fetch -q --depth 1 origin "$COMMIT" 2>/dev/null || git fetch -q origin "$LINEAGE"
  fi
  git cat-file -e "$COMMIT^{commit}" 2>/dev/null || { echo "pinned commit $COMMIT is not reachable after fetching $LINEAGE"; exit 2; }
  git worktree add -q --detach "$DIR" "$COMMIT"
  echo "producers worktree added"
fi
sha=$(sha256sum "$DIR/$DRIVER" | cut -c1-64)
[ "$sha" = "$DRIVER_SHA256" ] || { echo "refusing: $DRIVER sha256 $sha differs from the pinned $DRIVER_SHA256"; exit 2; }
echo "producers worktree $DIR at $(git -C "$DIR" rev-parse HEAD) ($LINEAGE)"
echo "native_replay_driver.py sha256 $sha"
