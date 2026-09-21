# Job 0 step 2 (code): stage the ten producers the calculation pins name, this branch's frankie_boss tools and a
# Python environment beside Frankie's session on his box; verify every producer against the sha256 pinned BELOW
# (computed in git at the receiver lineage tip 2ebb8ce8, ccode/frankie-receiver-feed-20260916); run the producers'
# own tests; write a receipt. Nothing existing on the box is modified: new directories under /opt/frankie-box only.
# Inputs (optional): MARKETS_REF (this branch; default claude/cycle-0-frankie-box-rerun-od5sxk).
set -u
ROOT=/opt/frankie-box
RECEIVER_BRANCH=ccode/frankie-receiver-feed-20260916
RECEIVER_COMMIT=2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134
MARKETS_REF="${MARKETS_REF:-claude/cycle-0-frankie-box-rerun-od5sxk}"
PY313=/opt/hostedtoolcache/Python/3.13.15/x64/bin/python
mkdir -p "$ROOT/receipts" "$ROOT/logs"
export PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 GIT_TERMINAL_PROMPT=0
t0=$(date +%s)

echo "### producers checkout (pinned sibling lineage, read-only for Frankie's inspection; he copies before modifying)"
if [ ! -d "$ROOT/producers/.git" ]; then
  git clone -q --depth 1 --branch "$RECEIVER_BRANCH" https://github.com/DavisAI1974/Markets.git "$ROOT/producers" || { echo "producers clone failed"; exit 2; }
fi
head=$(git -C "$ROOT/producers" rev-parse HEAD)
[ "$head" = "$RECEIVER_COMMIT" ] || { echo "producers checkout is $head, not the pinned $RECEIVER_COMMIT (lineage moved; refusing)"; exit 2; }
echo "producers HEAD $head"

echo "### markets tools checkout (this branch: frankie_boss tools, pins, registry, task document)"
if [ ! -d "$ROOT/markets/.git" ]; then
  git clone -q --depth 1 --branch "$MARKETS_REF" https://github.com/DavisAI1974/Markets.git "$ROOT/markets" || { echo "markets clone failed"; exit 2; }
else
  git -C "$ROOT/markets" fetch -q --depth 1 origin "$MARKETS_REF" && git -C "$ROOT/markets" checkout -q FETCH_HEAD
fi
echo "markets HEAD $(git -C "$ROOT/markets" rev-parse HEAD) ($MARKETS_REF)"

echo "### python environment"
[ -x "$PY313" ] || { echo "no Python 3.13 at $PY313"; exit 2; }
if [ ! -x "$ROOT/venv/bin/python" ]; then "$PY313" -m venv "$ROOT/venv" || exit 2; fi
"$ROOT/venv/bin/python" -m pip install -q --upgrade pip >"$ROOT/logs/pip.log" 2>&1
"$ROOT/venv/bin/python" -m pip install -q torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu >>"$ROOT/logs/pip.log" 2>&1 || { echo "torch install failed (see logs/pip.log)"; tail -5 "$ROOT/logs/pip.log"; exit 2; }
"$ROOT/venv/bin/python" -m pip install -q "numpy>=1.26" "scipy>=1.11" boto3==1.42.23 botocore==1.42.97 zstandard "databento-dbn==0.62.0" cryptography==46.0.3 "pytest>=7.4" >>"$ROOT/logs/pip.log" 2>&1 || { echo "pip install failed (see logs/pip.log)"; tail -5 "$ROOT/logs/pip.log"; exit 2; }
"$ROOT/venv/bin/python" - <<'PY'
import importlib, platform
print('python', platform.python_version())
for n in ('torch','numpy','scipy','boto3','zstandard','databento_dbn','cryptography','pytest'):
    m = importlib.import_module(n); print(' ', n, getattr(m, '__version__', '?'))
import torch; print('  torch threads', torch.get_num_threads(), 'cpu count', __import__('os').cpu_count())
PY

echo "### producer pins (sha256 at 2ebb8ce8, from git)"
export ROOT
"$ROOT/venv/bin/python" - <<'PY'
import hashlib, json, os, time
root = os.environ['ROOT']; base = os.path.join(root, 'producers')
PINS = {
 'research/kalshi/frankie_raw_mbo_benchmark/a_memory_member_first_recalculation_20260828.py': (41528, '04194df484a69bb8d91a296e67145d34ada1a24ed1cf2aa1b4529565808369bb'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_book_regime.py': (13097, 'aea1396df7cd838184de07fa029b4b2bf6d1e9434732b73f908538b4b7a62ab4'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_clocks.py': (32462, 'f333efc43345eaecef375ed3b2cb8e19c5f8d4414a47b24e93bfef58b6e99f05'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_flow_substrate.py': (29393, 'c904119f8e826e92578039182303425e0b6a0060f320c28955ebe85d8ecd8be0'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_full_capture_adapter.py': (32392, 'd45febff374323d0ef1713078ac68775bad69d3f372f5d595503479ac52b59a4'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_recognition.py': (12706, '0b279fda54cedcd3c812580da181356814afe4a35dffc52379d64814a716ac7c'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_replay_driver.py': (85491, '67996f3e1da9f6584bcca888eefe015c3b31508b9451335a76e2f49bfd7a8762'),
 'research/kalshi/frankie_raw_mbo_benchmark/native_roll20.py': (12887, '8e0a8dd6111cf65dfd87ac153f72824c75fe372da55f24a7ea0c278517d58179'),
 'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py': (41368, '4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce'),
 'research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json': (37242, '7ee754f1f9b080cdc5b7b68cf75829897d6216a1fadbb4b8a5ecd7b4f2133e06'),
}
rows, bad = [], []
for rel, (want_bytes, want_sha) in PINS.items():
    p = os.path.join(base, rel)
    if not os.path.isfile(p):
        bad.append(rel); rows.append(dict(path=rel, status='missing')); print('MISSING', rel); continue
    data = open(p, 'rb').read(); got = hashlib.sha256(data).hexdigest()
    ok = (len(data), got) == (want_bytes, want_sha)
    rows.append(dict(path=rel, bytes=len(data), sha256=got, status='pinned' if ok else 'DIFFERS'))
    print('pinned ' if ok else 'DIFFERS', rel, len(data), got[:16])
    if not ok: bad.append(rel)
receipt = dict(schema='FRANKIE_BOX_PRODUCERS_RECEIPT_V1', at=time.time(), producers_commit=os.environ.get('RECEIVER_COMMIT'),
               producers_root=base, markets_root=os.path.join(root, 'markets'), venv=os.path.join(root, 'venv'), producers=rows, differs=bad)
name = os.path.join(root, 'receipts', f'producers-{int(receipt["at"])}.json')
json.dump(receipt, open(name, 'w'), indent=1, sort_keys=True); print('RECEIPT', name)
raise SystemExit(1 if bad else 0)
PY
[ $? -eq 0 ] || exit 1

echo "### producer tests (the lineage's own; capped at 25 min; result recorded, never gates the pins above)"
cd "$ROOT/producers" || exit 2
timeout 1500 "$ROOT/venv/bin/python" -m pytest -q -p no:cacheprovider research/kalshi/frankie_raw_mbo_benchmark/tests research/test_ng_exhaustion_mbo_v4_state_adapter_20260820.py >"$ROOT/logs/producer-tests.log" 2>&1
code=$?
tail -3 "$ROOT/logs/producer-tests.log"; echo "pytest exit $code"
grep -E "^(FAILED|ERROR) " "$ROOT/logs/producer-tests.log" | head -20
printf '{"schema":"FRANKIE_BOX_PRODUCER_TESTS_RECEIPT_V1","at":%s,"pytest_exit":%s,"log":"%s","tail":"%s"}\n' "$(date +%s)" "$code" "$ROOT/logs/producer-tests.log" "$(tail -1 "$ROOT/logs/producer-tests.log" | tr -d '"')" > "$ROOT/receipts/producer-tests-$(date +%s).json"
echo "### done in $(( $(date +%s) - t0 )) s"; df -h / | tail -1
