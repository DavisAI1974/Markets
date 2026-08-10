#!/usr/bin/env bash
# C2C-005 - deploy Markets Terminal onto the durable box as a systemd service.
#
# Run ON THE BOX, from the checkout, as root:
#     cd /opt/markets-terminal && git pull && bash mcp_server/deploy_box.sh
#
# IDEMPOTENT by design - safe to re-run after every code change; that is the update path.
#
# WHAT THIS DELIBERATELY DOES NOT DO, because the dashboard lives on this host:
#   * never touches /opt/markets-live, its branch, its unit, or its port (8091)
#   * never reboots
#   * never writes a secret VALUE into the repo, a unit file, a log line, or an SSM command
#     argument. The OpenAI key is pulled from SSM SecureString by THIS SCRIPT, running on the box,
#     into a 0600 file outside the repo. SSM RunShellScript command text is retained in command
#     history and CloudTrail, so passing a key as an argument is a second place to leak it.
set -euo pipefail

REPO=/opt/markets-terminal
ENV_FILE=/etc/markets/tunnel.env
PROFILE=markets-box-stdio
UNIT=markets-mcp-tunnel.service
BUCKET=bento-568968024170-us-east-2-an

# THE OFFICIAL RELEASE, not a local build. C2C-004 shipped a `go build` of an untagged dev HEAD
# because GitHub release downloads 403 from the session container; C2C-006 replaced it with the
# signed release once Greg found it. Two hashes are pinned so integrity is checked twice - the
# ZIP against the vendor's own published SHA256SUMS, and then the extracted binary itself.
TC_VERSION=v0.0.11
TC_ZIP=tunnel-client-${TC_VERSION}-linux-amd64.zip
TC_ZIP_SHA=29adfe5c1399dfb9fda9383f230c324355912f50dc36e2e416b1f1322317b3c4
TC_BIN_SHA=c79ad91d929f50cb1676c4fcbce937c81b1854ec37ca758118c2d78a373c431f
TC_URL=https://github.com/openai/tunnel-client/releases/download/${TC_VERSION}/${TC_ZIP}
TC_S3_KEY=tooling/tunnel-client/${TC_ZIP}      # mirror, in case GitHub is unreachable at deploy time

# Non-secret identifiers. Safe in git; they are useless without the key.
TUNNEL_ID=tunnel_6a797a199f04819188e7ecb0ecf1ca6d
ORG_ID=org-0FKq6FrDt9tfN3QrpVS6akE8

[ "$(id -u)" = "0" ] || { echo "must run as root"; exit 1; }

# SSM RunShellScript executes with NEITHER $HOME NOR $XDG_CONFIG_HOME set, and tunnel-client
# resolves its profile directory from them - so `init` fails with "neither $XDG_CONFIG_HOME nor
# $HOME are defined" when this script is driven over SSM but works fine in an interactive shell.
# Set it explicitly so the deploy path behaves identically either way.
export HOME="${HOME:-/root}"

echo "== AWS credentials (existing box config, not created by this script) =="
set -a; . /etc/markets/pull.env; set +a

echo "== tunnel-client ${TC_VERSION} =="
have=""
[ -x /usr/local/bin/tunnel-client ] && have=$(sha256sum /usr/local/bin/tunnel-client | cut -d' ' -f1)
if [ "$have" = "$TC_BIN_SHA" ]; then
  echo "  already ${TC_VERSION} (sha verified) - no replacement needed"
else
  echo "  installed sha ${have:-none} != pinned - fetching the official release"
  work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
  # GitHub first (the vendor is the source of truth); S3 is only a mirror for when it is
  # unreachable. Both paths verify the SAME pinned hash, so the fallback cannot weaken integrity.
  if ! curl -fsSL --max-time 300 -o "$work/$TC_ZIP" "$TC_URL"; then
    echo "  GitHub unreachable, falling back to the S3 mirror"
    python3 - "$BUCKET" "$TC_S3_KEY" "$work/$TC_ZIP" <<'PY'
import boto3, sys
boto3.client("s3", region_name="us-east-2").download_file(sys.argv[1], sys.argv[2], sys.argv[3])
PY
  fi
  got=$(sha256sum "$work/$TC_ZIP" | cut -d' ' -f1)
  [ "$got" = "$TC_ZIP_SHA" ] || { echo "  ZIP SHA MISMATCH: $got"; exit 1; }
  echo "  zip sha256 verified against the published SHA256SUMS"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extract('tunnel-client', sys.argv[2])" \
    "$work/$TC_ZIP" "$work"
  got=$(sha256sum "$work/tunnel-client" | cut -d' ' -f1)
  [ "$got" = "$TC_BIN_SHA" ] || { echo "  BINARY SHA MISMATCH: $got"; exit 1; }
  install -m 0755 "$work/tunnel-client" /usr/local/bin/.tunnel-client.new
  mv -f /usr/local/bin/.tunnel-client.new /usr/local/bin/tunnel-client   # atomic
  echo "  installed and verified"
fi
echo "  version: $(/usr/local/bin/tunnel-client --version 2>&1 | head -1)"

echo "== python mcp package =="
python3 -c 'import mcp.server' 2>/dev/null || pip3 install --quiet mcp
python3 -c 'import mcp.server; print("  mcp import OK")'

echo "== $ENV_FILE (0600, outside the repo) =="
install -d -m 0755 /etc/markets
umask 077
python3 - "$ENV_FILE" "$TUNNEL_ID" "$ORG_ID" <<'PY'
import boto3, os, sys
env_file, tunnel_id, org_id = sys.argv[1], sys.argv[2], sys.argv[3]
ssm = boto3.client("ssm", region_name="us-east-2")
key = ssm.get_parameter(Name="/markets/OPENAI_API_KEY", WithDecryption=True)["Parameter"]["Value"]
with open(env_file, "w") as fh:                     # value written, never printed
    fh.write("CONTROL_PLANE_API_KEY=%s\n" % key)
    fh.write("CONTROL_PLANE_TUNNEL_ID=%s\n" % tunnel_id)
    fh.write("CONTROL_PLANE_ORGANIZATION_ID=%s\n" % org_id)
os.chmod(env_file, 0o600)
print("  wrote %s (%d names, key length %d - value not shown)" % (env_file, 3, len(key)))
PY

echo "== tunnel-client profile =="
set -a; . "$ENV_FILE"; set +a
if [ ! -f "/root/.config/tunnel-client/${PROFILE}.yaml" ]; then
  tunnel-client init --sample sample_mcp_stdio_local --profile "$PROFILE" \
    --tunnel-id "$TUNNEL_ID" \
    --mcp-command "/usr/bin/python3 ${REPO}/mcp_server/markets_mcp_readonly.py" >/dev/null
  echo "  profile created"
else
  echo "  profile already present"
fi
tunnel-client doctor --profile "$PROFILE" | grep -E 'FAIL|RESULT'

echo "== systemd unit =="
install -m 0644 "${REPO}/mcp_server/${UNIT}" "/etc/systemd/system/${UNIT}"
systemctl daemon-reload
systemctl enable "$UNIT" >/dev/null 2>&1
systemctl restart "$UNIT"

echo "== wait for readiness =="
for i in $(seq 1 30); do
  sleep 2
  if [ "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/readyz)" = "200" ]; then
    echo "  /readyz 200 after ${i} polls"; break
  fi
done
echo "  readyz : $(curl -s http://127.0.0.1:8080/readyz)"
echo "  healthz: $(curl -s http://127.0.0.1:8080/healthz)"

echo "== dashboard untouched =="
echo "  markets-desk.service: $(systemctl is-active markets-desk.service)"
echo "  desk branch: $(git -C /opt/markets-live rev-parse --abbrev-ref HEAD)"
