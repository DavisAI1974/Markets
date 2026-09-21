# Job 0 step 3 (prep): install the agent runtime on Frankie's box per deploy/aws/COACH_AGENT_SETUP_S93.md (Node 20 +
# Claude Code), and probe, read-only, which credentials the box can reach for the backend, the heartbeat and the git
# push: SSM SecureString names under /markets/ in both regions (names only, never decrypted here), Bedrock invoke in
# us-east-1, and whether the role may write the progress prefix. No credential is created or printed. Idempotent.
set -u
ROOT=/opt/frankie-box
mkdir -p "$ROOT/receipts" "$ROOT/logs"
export DEBIAN_FRONTEND=noninteractive HOME=/root
# The system boto3 (1.34.46) predates bedrock-runtime converse; use the staged venv's boto3 1.42 when present.
PY=/usr/bin/python3; [ -x "$ROOT/venv/bin/python" ] && PY="$ROOT/venv/bin/python"
echo "### node + claude code"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x -o /tmp/nodesource_setup.sh && bash /tmp/nodesource_setup.sh >"$ROOT/logs/nodesource.log" 2>&1 && apt-get install -y nodejs >>"$ROOT/logs/nodesource.log" 2>&1 || { echo "node install failed"; tail -5 "$ROOT/logs/nodesource.log"; }
fi
node --version 2>&1; npm --version 2>&1
if ! command -v claude >/dev/null 2>&1; then npm install -g @anthropic-ai/claude-code >"$ROOT/logs/claude-code-install.log" 2>&1 || { echo "claude code install failed"; tail -5 "$ROOT/logs/claude-code-install.log"; }; fi
claude --version 2>&1 || echo "(claude absent)"
echo "### aws cli (for Frankie's own heartbeat/downloads once the role has rights)"
if ! command -v aws >/dev/null 2>&1; then apt-get install -y awscli >"$ROOT/logs/awscli.log" 2>&1 || echo "awscli apt install failed (fine: boto3 is present)"; fi
aws --version 2>&1 | head -1
echo "### credential reach (read-only, names only; boto3 $("$PY" -c 'import boto3;print(boto3.__version__)'))"
"$PY" - <<'PY'
import boto3, json, time
def code(e): return getattr(e, 'response', {}).get('Error', {}).get('Code') or type(e).__name__
# Can the role DECRYPT a SecureString? Tested on the one parameter known to exist; the value is never printed or kept.
try:
    v = boto3.client('ssm', region_name='us-east-2').get_parameter(Name='/markets/frankie/granite-service', WithDecryption=True)['Parameter']['Value']
    print('ssm us-east-2 decrypt /markets/frankie/granite-service: OK (role may read SecureStrings; %d chars, not printed)' % len(v)); del v
except Exception as e:
    print('ssm us-east-2 decrypt /markets/frankie/granite-service:', code(e))
for region in ('us-east-1', 'us-east-2'):
    ssm = boto3.client('ssm', region_name=region)
    try:
        names = []
        for page in ssm.get_paginator('describe_parameters').paginate(ParameterFilters=[{'Key': 'Name', 'Option': 'BeginsWith', 'Values': ['/markets/']}]):
            names += [p['Name'] for p in page['Parameters']]
        print(f'ssm {region} describe_parameters /markets/*: {names or "(none)"}')
    except Exception as e:
        print(f'ssm {region} describe_parameters: {code(e)}')
    for name in ('/markets/frankie/github-token', '/markets/frankie/anthropic-api-key', '/markets/frankie/openai-api-key', '/markets/frankie/granite-service'):
        try:
            ssm.get_parameter(Name=name, WithDecryption=False); print(f'  {region} {name}: exists (not decrypted)')
        except Exception as e:
            print(f'  {region} {name}: {code(e)}')
br = boto3.client('bedrock-runtime', region_name='us-east-1')
for model in ('us.anthropic.claude-opus-4-6-v1:0', 'us.anthropic.claude-opus-4-1-20250805-v1:0', 'us.anthropic.claude-haiku-4-5-20251001-v1:0'):
    try:
        r = br.converse(modelId=model, messages=[{'role': 'user', 'content': [{'text': 'Reply with exactly: FRANKIE-BOX-ONLINE'}]}], inferenceConfig={'maxTokens': 16})
        print('bedrock converse', model, 'OK:', r['output']['message']['content'][0]['text'][:40]); break
    except Exception as e:
        print('bedrock converse', model, code(e))
s3 = boto3.client('s3', region_name='us-east-1')
key = f'host-deliveries/20211003/principal-response/cycle-00/progress/probe-{int(time.time())}-role-write-check.json'
try:
    s3.put_object(Bucket='frankie-granite42-568968024170-us-east-1', Key=key, Body=json.dumps(dict(schema='ROLE_WRITE_PROBE', note='written by the box role to test PutObject; not a heartbeat')).encode())
    print('s3 put progress/ OK (role may write heartbeats):', key)
except Exception as e:
    print('s3 put progress/:', code(e))
PY
echo "### git identity for the box (no credential yet)"
git config --global user.name >/dev/null 2>&1 || git config --global user.name "frankie-box"
git config --global user.email >/dev/null 2>&1 || git config --global user.email "frankie-box@markets.local"
git config --global --add safe.directory '*' 2>/dev/null
printf '{"schema":"FRANKIE_BOX_AGENT_BACKEND_PREP_V1","at":%s,"node":"%s","claude":"%s"}\n' "$(date +%s)" "$(node --version 2>/dev/null)" "$(claude --version 2>/dev/null | head -1)" > "$ROOT/receipts/agent-backend-prep-$(date +%s).json"
echo "### done"
