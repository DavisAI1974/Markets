"""The trading-day ingest wrapper on the box (SPEC-trading-day-ingest.md): read-then-act, never overwrite, no key, no S3 write."""
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box' / 'frankie_box_ingest_block.sh'


def _body(text, name):
    start = text.index(name + '() {')
    return text[start:text.index('\n}\n', start)]


def test_the_wrapper_fetches_by_the_map_verifies_every_partition_and_runs_the_tool_under_the_trading_day_policy():
    text = SCRIPT.read_text(encoding='utf-8')
    assert 'ACTION must be fetch, canary, ingest or status' in text
    assert 'BLOCK_20211004_SOURCE_MANIFEST.json' in text and 'blocks/BLOCK_*_SOURCE_MANIFEST.json' in text
    assert '--session-policy cme_trading_day' in text and '--workers "$WORKERS"' in text and 'WORKERS="${WORKERS:-31}"' in text
    assert '--canary-records $CANARY' in text and 'ingest_block_sources.py' in text
    assert 'not overwritten (move it aside with a receipt first)' in text and ".rejected-" in text
    assert 'units_idle' in text and 'frankie-cycle-$CYCLE' in text and 'frankie-heartbeat-$CYCLE' in text
    assert 'boto3' not in text and 'put_object' not in text and 'rm -rf' not in text and 'os.remove' not in text
    assert "rm -f \"$ROOT/tmp/ingest-map.json\"" in text                 # only the private map leaves; data never does
    assert 'a fresh directory per run' in text and 'mkdir -p "$OUT"' not in text      # the tool creates its output directory and refuses an existing one
    assert '[[' not in text and 'local ' not in text and '$((' not in text    # SSM runs the script under sh (dash): POSIX only
    assert subprocess.run(['dash', '-n', str(SCRIPT)]).returncode == 0


def test_the_wrapper_checks_out_the_dispatched_commit_only_after_the_units_are_idle_and_status_moves_nothing():
    # the chat-9 ship review: the checkout ran at the top for EVERY action, before units_idle, on a BRANCH NAME whose
    # default was another branch; a running session lazy-loads modules from that checkout
    text = SCRIPT.read_text(encoding='utf-8')
    assert 'MARKETS_REF' not in text and 'MARKETS_SHA="${MARKETS_SHA:-}"' in text
    assert 'case "$MARKETS_SHA" in ""|*[!0-9a-f]*)' in text and '[ "${#MARKETS_SHA}" -eq 40 ]' in text
    checkout = _body(text, 'checkout_markets')
    assert "git -C \"$ROOT/markets\" fetch -q --depth 1 origin -- \"$MARKETS_SHA\"" in checkout
    assert 'git -C "$ROOT/markets" checkout -q "$MARKETS_SHA"' in checkout and 'rev-parse HEAD)" = "$MARKETS_SHA" ]' in checkout
    assert text.count('git -C "$ROOT/markets" fetch') == 1 and text.index('units_idle() {') < text.index('git -C "$ROOT/markets" fetch')
    assert 'prepare() { units_idle || return 2; checkout_markets || return 2; manifest_ok || return 2;' in text
    assert 'fetch) prepare && fetch ;;' in text and 'canary) prepare && run_tool canary ;;' in text and 'ingest) prepare && run_tool ingest ;;' in text
    assert 'status) manifest_ok && status ;;' in text
    status = _body(text, 'status')
    assert 'fetch' not in status and 'checkout' not in status and 'rev-parse HEAD' in status       # reads the checkout as it stands
    assert 'MARKETS_SHA' not in _body(text, 'manifest_ok')


def test_the_wrapper_validates_the_manifest_with_the_tools_own_scope_pins_every_destination_and_bounds_its_inputs():
    # the chat-9 security audit: fetch trusted manifest.block and member_key before any validation (a root write anywhere);
    # the map URL and every map entry must be https amazonaws; WORKERS and CANARY are checked separately and bounded
    text = SCRIPT.read_text(encoding='utf-8')
    assert 'from research.kalshi.frankie_boss.block_source_scope import block_source_scope' in text
    assert "scope = block_source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])" in text
    assert 'for member in scope.members:' in text and "dest = os.path.realpath(os.path.join(data, member.member_key))" in text
    assert 'escapes the data directory; refused' in text and 'case "$BLOCK" in ""|*[!0-9_]*)' in text
    assert 'case "$MAP_URL" in https://*.amazonaws.com/*)' in text and "'.amazonaws.com/' in u.split('?', 1)[0]" in text
    assert text.count('--proto =https') == 1 and text.count("'--proto', '=https'") == 1 and '--url "$MAP_URL"' in text and "'--url', m[key]['url']" in text
    assert 'case "$WORKERS" in ""|*[!0-9]*)' in text and 'case "$CANARY" in ""|*[!0-9]*)' in text and '"$WORKERS$CANARY"' not in text
    assert '[ "$WORKERS" -le "$NCPU" ]' in text and '[ "$CANARY" -ge 1 ]' in text
    assert 'case "$MANIFEST" in *..*|research/kalshi/frankie_boss/blocks/*/*)' in text
    assert "with open(name, 'x') as f" in text and "markets_sha=os.environ['MARKETS_SHA']" in text and "manifest_hash=manifest['manifest_hash']" in text
    assert '.late-' in text and "if os.path.exists(dest):   # something landed at the destination during the download" in text
    assert "{k: r[k] for k in keys if k in r}" in text                        # status prints the keys a receipt has, never nulls
