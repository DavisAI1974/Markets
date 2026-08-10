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
BIN_KEY=tooling/tunnel-client/tunnel-client-linux-amd64
BIN_SHA=c39d3c8181feed2eedff1d0246368af5ac3e946b416b5be810f2fbeb7172359f

# Non-secret identifiers. Safe in git; they are useless without the key.
TUNNEL_ID=tunnel_6a797a199f04819188e7ecb0ecf1ca6d
ORG_ID=org-0FKq6FrDt9tfN3QrpVS6akE8

[ "$(id -u)" = "0" ] || { echo "must run as root"; exit 1; }

echo "== AWS credentials (existing box config, not created by this script) =="
set -a; . /etc/markets/pull.env; set +a

echo "== tunnel-client binary =="
if [ ! -x /usr/local/bin/tunnel-client ] || \
   [ "$(sha256sum /usr/local/bin/tunnel-client | cut -d' ' -f1)" != "$BIN_SHA" ]; then
  python3 - "$BUCKET" "$BIN_KEY" <<'PY'
import boto3, sys
boto3.client("s3", region_name="us-east-2").download_file(
    sys.argv[1], sys.argv[2], "/usr/local/bin/tunnel-client")
print("  downloaded")
PY
  chmod 0755 /usr/local/bin/tunnel-client
fi
have=$(sha256sum /usr/local/bin/tunnel-client | cut -d' ' -f1)
[ "$have" = "$BIN_SHA" ] || { echo "  SHA MISMATCH: $have"; exit 1; }
echo "  sha256 verified"

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
