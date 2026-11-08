set -eu
cd "$HOME/ng-root-bounded-13eb0f6ab"
export PYTHONDONTWRITEBYTECODE=1
venv/bin/python - <<'PY'
from pathlib import Path
import json
from research.kalshi.frankie_boss.block_source_scope import block_source_scope
from research.kalshi.frankie_boss.operations.ingest_block_sources import partial_takes, tail_skips
base=Path('/mnt/e/Markets-family-research-handoff/research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/discovery-block-manifests')
for path in sorted(base.glob('BLOCK_*_SOURCE_MANIFEST.json')):
    data=json.loads(path.read_bytes())
    scope=block_source_scope(data, expected_manifest_hash=data['manifest_hash'])
    print(data['trading_day'], len(scope.members),
          partial_takes(data, policy_name='cme_trading_day'), tail_skips(data, policy_name='cme_trading_day'))
PY