#!/usr/bin/env bash
# Install addyosmani/agent-skills into the session's user-level Claude dir.
#
# Intended as a Claude Code CLOUD ENVIRONMENT setup script: it runs at container
# start for EVERY session in the environment, in every repo, so the pack is not
# tied to any one repository's .claude/settings.json.
#
# Idempotent. Safe to re-run. Pin PACK_REF to control the version.
set -euo pipefail

PACK_REPO="${PACK_REPO:-https://github.com/addyosmani/agent-skills.git}"
PACK_REF="${PACK_REF:-0.6.8}"
DEST="${HOME}/.claude"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "[agent-skills] cloning ${PACK_REPO} @ ${PACK_REF}"
git clone --depth 1 --branch "$PACK_REF" "$PACK_REPO" "$TMP/pack" >/dev/null 2>&1

mkdir -p "$DEST/skills" "$DEST/commands" "$DEST/agents"

# skills/<name>/SKILL.md -> ~/.claude/skills/<name>/
cp -r "$TMP"/pack/skills/* "$DEST/skills/"

# 12 skills cite ../../references/*.md; from ~/.claude/skills/<n>/SKILL.md that
# resolves to ~/.claude/references/. Without this those links dangle.
rm -rf "$DEST/references"
cp -r "$TMP"/pack/references "$DEST/references"

# 9 phase commands (/spec /plan /build /test /constraints /review
# /code-simplify /ship /webperf) and 4 review personas.
cp "$TMP"/pack/.claude/commands/*.md "$DEST/commands/"
cp "$TMP"/pack/agents/*.md           "$DEST/agents/"

cat > "$DEST/skills/PROVENANCE.md" <<EOF
Vendored from ${PACK_REPO} @ ${PACK_REF}
Commit: $(git -C "$TMP/pack" rev-parse HEAD)
License: MIT. Installed by deploy/claude/setup_agent_skills.sh at session start.
Third-party instructions that load into agent context.
EOF

echo "[agent-skills] skills=$(find "$DEST/skills" -maxdepth 2 -name SKILL.md | wc -l)" \
     "commands=$(ls "$DEST"/commands/*.md 2>/dev/null | wc -l)" \
     "agents=$(ls "$DEST"/agents/*.md 2>/dev/null | wc -l)" \
     "references=$(ls "$DEST"/references/*.md 2>/dev/null | wc -l)"
