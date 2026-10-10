# Set up a worker Linux box like the main box (Greg, 2026-09-29: "Set up the linux one and switch the other box from
# windows to aws"). Idempotent; run through frankie_box_run.yml with instance=<worker> region=<its region>.
# 1. apt: git zstd sqlite3 curl.
# 2. Python 3.13.15, the same actions/python-versions build the main box's venv points at
#    (/opt/hostedtoolcache/Python/3.13.15/x64), taken from that project's versions-manifest for this Ubuntu release.
# 3. /opt/frankie-box/venv with the main box's exact pip freeze of 2026-09-29 (75 distributions; torch from the PyTorch
#    CPU index).
# 4. /opt/frankie-box/markets: a plain https checkout of the dispatched commit (MARKETS_SHA), detached, like the main
#    box's; ingest worktrees are added from it per dispatch.
# 5. The layout /opt/frankie-box/{work,data,code,ingest-code,receipts,brain,tmp,logs} and root's git identity.
# Prints versions and a freeze diff against the pin list; writes receipts/worker-setup-<utc>.json. No data is copied.
# SSM runs this under sh: POSIX only.
set -eu
: "${MARKETS_SHA:?dispatched commit required}"
ROOT=/opt/frankie-box
export DEBIAN_FRONTEND=noninteractive HOME="${HOME:-/root}"   # SSM runs without HOME; git --global needs it
echo "### identity"; hostname; . /etc/os-release; echo "$PRETTY_NAME"; nproc; free -g | head -2; df -h / | tail -1
echo "### apt"
apt-get update -q >/dev/null
apt-get install -y -q git zstd sqlite3 curl ca-certificates >/dev/null
# No unattended upgrades and no service restarts after a package upgrade (2026-10-10): on the main box the
# apt-daily-upgrade timer upgraded libssl3/libxml2/the kernel at 06:09Z, re-executed systemd and restarted every
# service holding the old libraries, the two frankie transient units among them (SIGTERM, then SIGKILL after 90 s):
# the teacher lost its whole-day second set 2.5 h in and the classroom its running block. The experiment units are
# never killed by the box (Greg: a dead piece is revived, never skipped; keep the workflow running).
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer >/dev/null 2>&1 || true
systemctl mask apt-daily.service apt-daily-upgrade.service >/dev/null 2>&1 || true
systemctl disable --now unattended-upgrades.service >/dev/null 2>&1 || true
printf 'APT::Periodic::Update-Package-Lists "0";\nAPT::Periodic::Unattended-Upgrade "0";\nAPT::Periodic::Download-Upgradeable-Packages "0";\n' > /etc/apt/apt.conf.d/99frankie-no-auto-upgrade
mkdir -p /etc/needrestart/conf.d
printf '# frankie box: never restart services after a package upgrade; the experiment units must not be killed\n$nrconf{restart} = '"'"'l'"'"';\n' > /etc/needrestart/conf.d/99-frankie-no-restart.conf
mkdir -p "$ROOT"/work "$ROOT"/data "$ROOT"/code "$ROOT"/ingest-code "$ROOT"/receipts "$ROOT"/brain "$ROOT"/tmp "$ROOT"/logs
echo "### python 3.13.15"
PYDIR=/opt/hostedtoolcache/Python/3.13.15/x64
if [ ! -x "$PYDIR/bin/python3.13" ]; then
  URL=$(curl -fsSL https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json | python3 -c "
import json,sys
rel='$VERSION_ID'
for v in json.load(sys.stdin):
    if v['version']=='3.13.15':
        for f in v['files']:
            if f['platform']=='linux' and f['arch']=='x64' and f.get('platform_version')==rel:
                print(f['download_url']); raise SystemExit
raise SystemExit('no 3.13.15 build for linux '+rel)")
  echo "$URL"
  T=$(mktemp -d); curl -fsSL "$URL" -o "$T/py.tgz"; tar -xzf "$T/py.tgz" -C "$T"
  ( cd "$T" && RUNNER_TOOL_CACHE=/opt/hostedtoolcache bash ./setup.sh >/dev/null )
  rm -rf "$T"
fi
"$PYDIR/bin/python3.13" -V
echo "### venv"
[ -x "$ROOT/venv/bin/python" ] || "$PYDIR/bin/python3.13" -m venv "$ROOT/venv"
REQ="$ROOT/tmp/worker-requirements.txt"
cat > "$REQ" <<'EOF'
aiohappyeyeballs==2.7.1
aiohttp==3.14.3
aiosignal==1.4.0
annotated-doc==0.0.5
anyio==4.15.1
attrs==26.1.0
boto3==1.42.23
botocore==1.42.97
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
click==8.5.0
cloudpickle==3.1.2
contourpy==1.4.0
cryptography==46.0.3
cycler==0.12.1
databento==0.81.0
databento-dbn==0.62.0
filelock==3.32.3
fonttools==4.65.0
frozenlist==1.8.0
fsspec==2026.7.0
h11==0.16.0
hf-xet==1.6.0
httpcore==1.0.9
httpx==0.28.1
huggingface_hub==1.32.0
idna==3.20
iniconfig==2.3.0
Jinja2==3.1.6
jmespath==1.1.0
joblib==1.6.0
kiwisolver==1.5.1
markdown-it-py==4.2.0
MarkupSafe==3.0.3
matplotlib==3.11.2
mdurl==0.1.2
mpmath==1.3.0
multidict==6.9.0
narwhals==2.26.0
networkx==3.6.1
numpy==2.5.3
packaging==26.3
pandas==3.0.6
pillow==12.3.0
pluggy==1.6.0
propcache==0.5.4
pyarrow==25.0.1
pycparser==3.0
Pygments==2.21.0
pyparsing==3.3.3
pytest==9.1.1
python-dateutil==2.9.0.post0
PyYAML==6.0.3
regex==2026.9.10
requests==2.34.2
rich==15.0.0
s3transfer==0.16.1
safetensors==0.8.0
scikit-learn==1.9.1
scipy==1.18.1
setuptools==78.1.0
shellingham==1.5.4
six==1.17.0
sympy==1.14.0
threadpoolctl==3.7.0
tokenizers==0.22.2
torch==2.11.0+cpu
tqdm==4.70.1
transformers==5.8.0
typer==0.27.2
typing_extensions==4.16.0
urllib3==2.8.0
yarl==1.25.1
zstandard==0.25.0
EOF
"$ROOT/venv/bin/python" -m pip install -q --disable-pip-version-check --no-cache-dir \
  --extra-index-url https://download.pytorch.org/whl/cpu -r "$REQ"
"$ROOT/venv/bin/python" -m pip freeze --disable-pip-version-check | sort -f > "$ROOT/tmp/worker-freeze.txt"
sort -f "$REQ" > "$ROOT/tmp/worker-requirements.sorted"
DIFF=$(diff "$ROOT/tmp/worker-requirements.sorted" "$ROOT/tmp/worker-freeze.txt" || true)
[ -z "$DIFF" ] && echo "freeze matches the main box's 75 pins" || { echo "freeze differs:"; echo "$DIFF"; }
echo "### markets checkout"
git config --global user.name frankie-box; git config --global user.email frankie-box@markets.local
git config --global --add safe.directory '*'
if [ ! -d "$ROOT/markets/.git" ]; then
  git init -q "$ROOT/markets"; git -C "$ROOT/markets" remote add origin https://github.com/DavisAI1974/Markets.git
fi
git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$MARKETS_SHA"
git -C "$ROOT/markets" checkout -q --detach "$MARKETS_SHA"
git -C "$ROOT/markets" log --oneline -1
# the dispatched commit as an ingest worktree too, like frankie_box_ingest_block.sh makes (a CODE_ROOT for day facts)
[ -e "$ROOT/ingest-code/$MARKETS_SHA/.git" ] || git -C "$ROOT/markets" worktree add -q --detach "$ROOT/ingest-code/$MARKETS_SHA" "$MARKETS_SHA"
echo "ingest worktree $ROOT/ingest-code/$MARKETS_SHA"
echo "### receipt"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
"$ROOT/venv/bin/python" - "$ROOT/receipts/worker-setup-$STAMP.json" "$MARKETS_SHA" "$DIFF" <<'PY'
import json, os, platform, sys
with open(sys.argv[1], 'x') as f:
    json.dump(dict(schema='FRANKIE_WORKER_SETUP_V1', host=platform.node(), os=platform.platform(),
                   python=platform.python_version(), cpus=os.cpu_count(), markets_commit=sys.argv[2],
                   freeze_matches_main=sys.argv[3] == '', freeze_diff=sys.argv[3]), f, sort_keys=True, indent=1)
print(open(sys.argv[1]).read())
PY
df -h / | tail -1
