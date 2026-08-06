#!/usr/bin/env bash
# SessionStart hook for Claude Code on the web — bootstraps the Operator-Discovery
# toolchain and the real data every session, GUARDED so it always reaches completion
# (the research log notes a latent hook failure once stalled a whole session; we never
# let a single failed step abort the hook). Mirrors the basic_equations Session-9 hook.
set +e

echo "[session_start] bootstrapping OD toolchain (numpy/scipy/sklearn + PySR + Julia)..."
# Prefer the pinned manifest (BUILD_PLAN Phase 0); fall back to the explicit list.
pip install --quiet -r requirements.txt >/dev/null 2>&1 \
  || pip install --quiet numpy scipy scikit-learn pysr pytest >/dev/null 2>&1 \
  || echo "[session_start] pip step had issues (continuing)"

# PySR pulls the Julia backend via juliacall; it precompiles on the first fit.
python3 -c "import pysr" >/dev/null 2>&1 \
  && echo "[session_start] PySR import OK (Julia precompiles on first fit)" \
  || echo "[session_start] PySR not importable yet (continuing)"

# Materialize the real collector bins from the data/* branches if missing (the container
# is ephemeral, so this is a one-time-per-container fetch). Never commit realbins/.
# Bins are stored gzipped on the branches (GitHub caps single files at 100 MiB; raw 30-day
# JSON is 110-136 MiB). Prefer <name>.gz (gunzip), fall back to legacy raw <name>.
materialize() {  # $1=branch  $2=basename e.g. btc_coinbase_bins.json
  local branch="$1" name="$2"
  if git cat-file -e "origin/${branch}:${name}.gz" 2>/dev/null; then
    git show "origin/${branch}:${name}.gz" 2>/dev/null | gunzip -c > "realbins/${name}" 2>/dev/null || true
  elif git cat-file -e "origin/${branch}:${name}" 2>/dev/null; then
    git show "origin/${branch}:${name}" > "realbins/${name}" 2>/dev/null || true
  fi
}
if [ ! -d realbins ] || [ -z "$(ls -A realbins 2>/dev/null)" ]; then
  echo "[session_start] materializing real bins from data/* branches..."
  mkdir -p realbins
  git fetch origin data/btc-bins data/eth-bins data/perp-history >/dev/null 2>&1
  for f in btc_coinbase_bins.json btc_kraken_bins.json btc_bybit_perp_bins.json; do
    materialize data/btc-bins "$f"
  done
  for f in eth_coinbase_bins.json eth_kraken_bins.json eth_bybit_perp_bins.json; do
    materialize data/eth-bins "$f"
  done
  echo "[session_start] realbins: $(ls realbins 2>/dev/null | wc -l) files"
fi

# ---------------------------------------------------------------------------
# Kalshi NG forecaster substrate (S108). data/ is gitignored and DIES WITH THE
# CONTAINER, while the committed state/forecast artifacts survive. Restoring it
# was a manual rediscovery at the top of S107 and again at the top of S108, so
# it happens here instead.
#
# TWO RULES, both learned the hard way:
#   1. ALWAYS run boto3 under `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`.
#      The container injects PLACEHOLDER creds into the environment that override
#      ~/.aws/credentials, so an un-stripped call authenticates as nobody.
#   2. NO-OP LOUDLY when the keys are absent. A half-restored plane is exactly the
#      silently-empty-input failure this project keeps getting bitten by - six in
#      one session - and it reads downstream like a deliberate price mask. Say
#      plainly that nothing was restored; never leave a partial plane looking whole.
# Keys live ONLY in ~/.aws/credentials and scratchpad/*.env (chmod 600). This hook
# never prints, copies or commits them.
# ---------------------------------------------------------------------------
if [ -f research/kalshi/restore_substrate.py ]; then
  pip install --quiet numpy pandas matplotlib boto3 databento >/dev/null 2>&1 \
    || echo "[session_start] kalshi dep install had issues (continuing)"

  # S115: detect credentials by EFFECTIVE resolution (creds.py), not by file presence.
  # creds.get walks MARKETS_ env vars (set once in the Claude Code environment config,
  # injected into every fresh container) -> ~/.config/markets/env -> legacy. With the
  # environment config carrying MARKETS_AWS_ACCESS_KEY_ID / MARKETS_AWS_SECRET_ACCESS_KEY,
  # a fresh session restores the data plane with ZERO manual steps.
  if python3 -c "import sys; sys.path.insert(0,'research/kalshi'); import creds; sys.exit(0 if (creds.get('AWS_ACCESS_KEY_ID',required=False) and creds.get('AWS_SECRET_ACCESS_KEY',required=False)) else 1)" 2>/dev/null; then
    echo "[session_start] AWS creds resolvable - restoring the NG data plane (S3 + vol_regime rebuild)..."
    env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY \
      python3 research/kalshi/restore_substrate.py 2>&1 | tail -5 \
      || echo "[session_start] restore_substrate had issues - VERIFY BEFORE STAGING"
    # The completeness gate is the whole point: it refuses to stage a group with an
    # empty block, so surface its verdict at session start rather than mid-run.
    python3 research/kalshi/state_health.py 2>&1 | grep -E "PASS|HARD|REFUS" | head -12 \
      || echo "[session_start] state_health did not run"
  else
    echo "[session_start] ================================================================"
    echo "[session_start] NG DATA PLANE NOT RESTORED - no AWS credentials resolvable."
    echo "[session_start]   data/ is EMPTY or STALE. Staging a group, re-staging, and the"
    echo "[session_start]   round-2 handoff on any group staged before S108 will FAIL or,"
    echo "[session_start]   worse, read as an empty block. Committed artifacts are fine:"
    echo "[session_start]   a group staged at S108 or later runs BOTH rounds without data/."
    echo "[session_start]   PERMANENT FIX (one-time): add MARKETS_AWS_ACCESS_KEY_ID and"
    echo "[session_start]   MARKETS_AWS_SECRET_ACCESS_KEY to the Claude Code ENVIRONMENT"
    echo "[session_start]   configuration - every future session then restores automatically."
    echo "[session_start]   Session-only fix: write ~/.config/markets/env (chmod 600), then"
    echo "[session_start]     python3 research/kalshi/restore_substrate.py"
    echo "[session_start] ================================================================"
  fi
fi

echo "[session_start] done."
exit 0
