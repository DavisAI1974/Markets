"""The trading-day ingest wrapper on the box (SPEC-trading-day-ingest.md): read-then-act, never overwrite, no key, no S3 write."""
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_ingest_block.sh'


def test_the_wrapper_fetches_by_the_map_verifies_every_partition_and_runs_the_tool_under_the_trading_day_policy():
    text = SCRIPT.read_text(encoding='utf-8')
    assert 'ACTION must be fetch, canary, ingest or status' in text
    assert 'BLOCK_20211004_SOURCE_MANIFEST.json' in text and 'blocks/BLOCK_*_SOURCE_MANIFEST.json' in text
    assert '--session-policy cme_trading_day' in text and '--workers "$WORKERS"' in text and 'WORKERS="${WORKERS:-31}"' in text
    assert '--canary-records $CANARY' in text and 'ingest_block_sources.py' in text
    assert 'not overwritten (move it aside with a receipt first)' in text and ".rejected-" in text
    assert "git -C \"$ROOT/markets\" fetch -q --depth 1 origin -- \"$MARKETS_REF\"" in text
    assert 'units_idle' in text and 'frankie-cycle-$CYCLE' in text and 'frankie-heartbeat-$CYCLE' in text
    assert 'boto3' not in text and 'put_object' not in text and 'rm -rf' not in text and 'os.remove' not in text
    assert "rm -f \"$ROOT/tmp/ingest-map.json\"" in text                 # only the private map leaves; data never does
    assert 'a fresh directory per run' in text and 'mkdir -p "$OUT"' not in text      # the tool creates its output directory and refuses an existing one
    assert '[[' not in text and 'local ' not in text and '$((' not in text    # SSM runs the script under sh (dash): POSIX only
