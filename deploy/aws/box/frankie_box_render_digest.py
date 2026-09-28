"""Render-only: re-write a RETAINED Monday calculation root's derivation digest in the current digest schema.

Greg, 2026-09-28: the digest is Granite's reading; the calculations under it do not change, so they are not re-run.
The saved legacy layers and spools (load_retained_layers, no journal read) and the saved derive.json are written by the
same assembly ROOT uses (write_retained_digest), with bedrock=False: the digest holds the header, layer statuses and
legacy tables, which is all Granite reads (frankie_box_digest_read.legacy_read stops at the bedrock heading). The bedrock
layers stay whole in their retained layer files, and the previous digest's bedrock tables stay in the moved-aside digest.
No layer, bedrock or source recalculation, no model call.

The previous digest, its proof and the previous calculations receipt are moved aside under
<root>/superseded/digest-render-<stamp>/ (nothing deleted). A new calculations receipt carries the new digest witnesses,
the staged commit and a digest_render record naming the receipt it supersedes; the principal inputs are then
re-assembled from it (frankie_box_principal_inputs.sh with the new receipt's path and sha256).

    frankie_box_render_digest.py --commit <staged sha> --output-root /opt/frankie-box/work/monday-calculations/<root>
"""
import argparse
import fcntl
import glob
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import read_pin, require_checkout, save_new, witness, safe_path
from frankie_box_monday_calculations import PARENT, load_retained_layers, write_retained_digest


def _same(path, pinned):
    """The file carries the pinned bytes and sha256 (its path may differ: it can have been moved aside)."""
    if path.stat().st_size != pinned['bytes']:
        return False
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == pinned['sha256']


def _has_bedrock(path, heading=b'\n## Bedrock ('):
    """Streamed search for the bedrock heading (the digest runs to GBs; never held whole)."""
    tail = b''
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(16 << 20), b''):
            if heading in tail + block:
                return True
            tail = block[-len(heading):]
    return False


def render(commit, output_root):
    require_checkout(commit)
    output = safe_path(output_root)
    if output.parent != PARENT or not output.is_dir():
        raise ValueError('retained Monday calculation root required')
    lock = (output / 'calculation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    from frankie_box_progress import snapshot, for_session
    if snapshot(output).get('process_alive'):
        raise ValueError('a calculation process is still alive on this root')
    receipt_path = output / 'calculations-receipt.json'
    old = read_pin(witness(receipt_path))
    if old.get('schema') != 'FRANKIE_MONDAY_CALCULATIONS_V1' or old.get('status') != 'calculations_retained':
        raise ValueError('retained Monday calculations required')
    for key in ('source_binding', 'calculation_pins', 'derivation', 'result'):
        if witness(Path(old[key]['path'])) != old[key]:
            raise ValueError(key + ' changed since the calculation was retained')
    derivation = json.loads(Path(old['derivation']['path']).read_bytes())
    if derivation.get('failure_count') != 0:
        raise ValueError('calculation failures remain')

    from frankie_box_boss_session import Session
    import frankie_box_digest_render as DG
    session = Session(output, '20211004', '00', None)
    session.request_sha256 = old['source_binding']['sha256']
    for_session(session)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    aside = output / 'superseded' / ('digest-render-' + stamp)
    aside.mkdir(parents=True)
    moved = {}
    for key in ('digest', 'digest_proof'):
        # A rerun after a stopped render can find the receipt's file already moved aside, or a stopped render's own
        # output in its place. Only a file whose bytes and sha256 match the receipt's witness is the previous one.
        path = Path(old[key]['path'])
        if path.parent != session.work:
            raise ValueError(key + ' path outside the root work directory')
        if path.exists() and not _same(path, old[key]):
            path.rename(aside / ('orphan-' + path.name))       # a stopped render's output: kept, never named previous
            moved['orphan_' + key] = str(aside / ('orphan-' + path.name))
        if path.exists():
            path.rename(aside / path.name)
            moved[key] = str(aside / path.name)
        else:
            earlier = [p for p in (output / 'superseded').glob('digest-render-*/' + glob.escape(path.name))
                       if p.parent != aside and _same(p, old[key])]
            if earlier:
                moved[key] = str(sorted(earlier)[0])
    session.phase('deriving', 'render-only: the digest in ' + DG.SCHEMA + ' from the retained layers (legacy tables; bedrock stays in its layer files); no recalculation')
    _, _, _, prices, frames, structures, _, layers, _ = load_retained_layers(session)
    write_retained_digest(session, derivation, layers, prices, frames, structures, bedrock=False)

    # where the bedrock tables are: the moved-aside digest when it carries them, else wherever the last render said
    previous = old.get('digest_render', {})
    bedrock_in = moved['digest'] if 'digest' in moved and _has_bedrock(Path(moved['digest'])) else previous.get('bedrock_tables_in')
    superseded = aside / 'calculations-receipt.json'
    os.link(receipt_path, superseded)                 # the old receipt stays in place until the new one replaces it
    receipt = dict(old, commit=commit,
                   digest=witness(session.work / 'derivation-digest-full.md'),
                   digest_proof=witness(session.work / 'digest-proof.json'),
                   digest_render=dict(schema='FRANKIE_DIGEST_RENDER_V1', digest_schema=DG.SCHEMA, at=time.time(),
                                      supersedes=witness(superseded), previous_digest=old['digest'],
                                      previous_digest_proof=old['digest_proof'], moved_aside=moved,
                                      recalculation=False, model_calls=0, bedrock_tables_in=bedrock_in,
                                      bedrock_tables='not rendered: retained in the layer files' +
                                                     (' and in ' + bedrock_in if bedrock_in else '')))
    pending = output / 'calculations-receipt.json.new'
    if pending.exists():                              # left by a render stopped between writing and replacing
        pending.rename(aside / 'calculations-receipt.json.stale-new')
    save_new(pending, receipt)
    os.replace(pending, receipt_path)
    if read_pin(witness(receipt_path)) != receipt:
        raise ValueError('rendered calculations receipt readback differs')
    session.phase('derived', 'render-only done: ' + DG.SCHEMA)
    print('RENDER ' + json.dumps(dict(receipt=witness(receipt_path), digest=receipt['digest'], schema=DG.SCHEMA),
                                 sort_keys=True), flush=True)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--output-root', required=True)
    args = parser.parse_args()
    render(args.commit, args.output_root)


if __name__ == '__main__':
    main()
