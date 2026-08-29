#!/usr/bin/env bash
# Install addyosmani/agent-skills into the session's user-level Claude dir.
#
# Intended as a Claude Code CLOUD ENVIRONMENT setup script: it runs before
# Claude Code launches, for every session in the environment, in every repo.
# The resulting filesystem is snapshotted and reused, so later sessions get
# the pack already on disk and skip this script.
#
# MUST EXIT ZERO. A non-zero exit makes the session fail to start, so every
# step is best-effort and the script always ends with exit 0.
PACK_REPO="${PACK_REPO:-https://github.com/addyosmani/agent-skills.git}"
PACK_REF="${PACK_REF:-0.6.8}"
DEST="${HOME}/.claude"

install_pack() {
  set -euo pipefail
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  git clone --depth 1 --branch "$PACK_REF" "$PACK_REPO" "$tmp/pack" >/dev/null 2>&1
  [ -d "$tmp/pack/skills" ] || return 1

  mkdir -p "$DEST/skills" "$DEST/commands" "$DEST/agents"
  cp -r "$tmp"/pack/skills/* "$DEST/skills/"

  # 12 skills cite ../../references/*.md; from ~/.claude/skills/<n>/SKILL.md
  # that resolves to ~/.claude/references/. Without this those links dangle.
  rm -rf "$DEST/references"
  cp -r "$tmp"/pack/references "$DEST/references"

  cp "$tmp"/pack/.claude/commands/*.md "$DEST/commands/"
  cp "$tmp"/pack/agents/*.md           "$DEST/agents/"

  printf 'Vendored from %s @ %s\nCommit: %s\nLicense: MIT\n' \
    "$PACK_REPO" "$PACK_REF" "$(git -C "$tmp/pack" rev-parse HEAD)" \
    > "$DEST/skills/PROVENANCE.md"
}

if install_pack; then
  echo "[agent-skills] ok:" \
       "skills=$(find "$DEST/skills" -maxdepth 2 -name SKILL.md 2>/dev/null | wc -l)" \
       "commands=$(ls "$DEST"/commands/*.md 2>/dev/null | wc -l)" \
       "agents=$(ls "$DEST"/agents/*.md 2>/dev/null | wc -l)" \
       "references=$(ls "$DEST"/references/*.md 2>/dev/null | wc -l)"
else
  echo "[agent-skills] install failed (ref=${PACK_REF}); continuing without the pack" >&2
fi
exit 0
