#!/usr/bin/env bash
# SessionStart hook for Claude Code on the web — bootstraps the Operator-Discovery
# toolchain and the real data every session, GUARDED so it always reaches completion
# (the research log notes a latent hook failure once stalled a whole session; we never
# let a single failed step abort the hook). Mirrors the basic_equations Session-9 hook.
set +e

echo "[session_start] bootstrapping OD toolchain (numpy/scipy/sklearn + PySR + Julia)..."
pip install --quiet numpy scipy scikit-learn pysr pytest >/dev/null 2>&1 \
  || echo "[session_start] pip step had issues (continuing)"

# PySR pulls the Julia backend via juliacall; it precompiles on the first fit.
python3 -c "import pysr" >/dev/null 2>&1 \
  && echo "[session_start] PySR import OK (Julia precompiles on first fit)" \
  || echo "[session_start] PySR not importable yet (continuing)"

# Materialize the real collector bins from the data/* branches if missing (the container
# is ephemeral, so this is a one-time-per-container fetch). Never commit realbins/.
if [ ! -d realbins ] || [ -z "$(ls -A realbins 2>/dev/null)" ]; then
  echo "[session_start] materializing real bins from data/* branches..."
  mkdir -p realbins
  git fetch origin data/btc-bins data/eth-bins data/perp-history >/dev/null 2>&1
  for f in btc_coinbase_bins.json btc_kraken_bins.json btc_bybit_perp_bins.json; do
    git show "origin/data/btc-bins:$f" > "realbins/$f" 2>/dev/null || true
  done
  for f in eth_coinbase_bins.json eth_kraken_bins.json eth_bybit_perp_bins.json; do
    git show "origin/data/eth-bins:$f" > "realbins/$f" 2>/dev/null || true
  done
  echo "[session_start] realbins: $(ls realbins 2>/dev/null | wc -l) files"
fi

echo "[session_start] done."
exit 0
