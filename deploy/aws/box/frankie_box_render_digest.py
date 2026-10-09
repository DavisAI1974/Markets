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

Session 9 (2026-10-08), the render INSIDE the day's own booking (frankie_box_render_digest.sh FRANKIE_RENDER_BOOKING=<id>,
beside the teacher): --keep-receipt leaves calculations-receipt.json exactly as the ROOT wrote it (the teacher's shared
identity binds its sha256: frankie_box_experiment teacher judging compares it), and records the render in
work/digest-render.json (FRANKIE_DIGEST_RENDER_V1) instead; the class line reads work/derivation-digest-full.md itself. An
experiment root is opened as the ROOT resume opens it (session 9): layers by their file claims, the five legacy spools from
their sealed counts (frankie_box_experiment_root.reopen_retained_spools), so no 497 GB whole count and the SAME spool path
strings as the ROOT child: the parallel table's part specs and pass save point key are the ROOT child's.

One pass (Greg, 2026-10-09): an experiment root is rendered ONLY through the keep-receipt route (without the flag it is
taken anyway): the ROOT's calculations-receipt.json is never rewritten by a render. A complete digest of the current
DIGEST SCHEMA that still holds by its claim row (work/file-claims.jsonl, appended by Session._write_digest from the
write-stream sha256) returns at once (already_rendered: no second render). The new digest's pin is the writer's proof
(write_retained_digest returns it), never a second read; a previous digest is recognised by its claim row (_same) and
its bedrock tables by its proof's table names (_has_bedrock), a whole read only when neither is there.
"""
import argparse
import fcntl
import glob
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from frankie_box_prepare_trading_day import read_pin, require_checkout, save_new, witness, safe_path
from frankie_box_monday_calculations import PARENT, load_retained_layers, write_retained_digest


DIGEST_NAME = 'derivation-digest-full.md'
RENDER_RECORD = 'digest-render.json'        # under <root>/work, the --keep-receipt route's record (create-only)


def _claim_of(work, path, pinned=None):
    """One pass (2026-10-09): the basis text when a FRANKIE_FILE_CLAIM row of <work>/file-claims.jsonl still describes
    the file at `path` (matched by the file's identity, inode + size + mtime_ns, so a digest moved aside by rename finds
    the row its writer appended: Session._write_digest, from the write-stream sha256) and, when `pinned` is given, names
    its bytes and sha256; checked by ingest_block_sources.claim_still_holds (the last 64 KiB and the filesystem). None
    when no row holds: the caller reads whole. Never raises."""
    try:
        from research.kalshi.frankie_boss.operations.ingest_block_sources import (claim_identity, claim_still_holds,
                                                                                   FILE_CLAIMS_NAME)
        info = os.stat(path)
        found = None
        for line in (Path(work) / FILE_CLAIMS_NAME).read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if claim_identity(row) != (info.st_ino, info.st_size, info.st_mtime_ns):
                continue
            if pinned is not None and (row.get('bytes'), row.get('sha256')) != (pinned['bytes'], pinned['sha256']):
                continue
            found = row
        if found is None:
            return None
        held = claim_still_holds(found, path)
        return held['text'] if held else None
    except Exception:  # noqa: BLE001 - a claim is a hint
        return None


def _same(path, pinned, work=None):
    """The file carries the pinned bytes and sha256 (its path may differ: it can have been moved aside): by its claim
    row when one holds (one 64 KiB read), else streamed whole once."""
    if path.stat().st_size != pinned['bytes']:
        return False
    if work is not None and _claim_of(work, path, pinned):
        return True
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() == pinned['sha256']


def _has_bedrock(path, heading=b'\n## Bedrock (', proof=None):
    """Whether a digest carries the bedrock tables: from its proof (digest-proof.json lists every table; a bedrock table
    is named bedrock.*, and the heading is written exactly when bedrock tables are) when there is one, else a streamed
    search for the heading (the digest runs to GBs; never held whole)."""
    if proof is not None:
        try:
            tables = json.loads(Path(proof).read_bytes()).get('tables')
            if isinstance(tables, list):
                return any(str(t.get('name', '')).startswith('bedrock.') for t in tables)
        except (OSError, ValueError, AttributeError):
            pass
    tail = b''
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(16 << 20), b''):
            if heading in tail + block:
                return True
            tail = block[-len(heading):]
    return False


def _current_schema(path, schema):
    """The digest's first line names `schema` (DG.digest_header: '# Derivation digest <SCHEMA> ...'): one small read."""
    want = b'# Derivation digest ' + schema.encode() + b' '
    try:
        with open(path, 'rb') as stream:
            return stream.read(len(want)) == want
    except OSError:
        return False


def already_rendered(output, old, schema):
    """The record of a complete digest of the current schema that still holds by its claim, else None (Greg,
    2026-10-09: no second render). The keep-receipt record (work/digest-render.json) naming the digest's bytes and
    sha256, or the ROOT receipt's own digest pin; each taken only while work/derivation-digest-full.md's claim row
    holds (inode, size, mtime_ns, filesystem, last 64 KiB) and its header names `schema`."""
    work = output / 'work'
    digest = work / DIGEST_NAME
    if not digest.is_file() or not _current_schema(digest, schema):
        return None
    record_path = work / RENDER_RECORD
    if record_path.is_file():
        try:
            done = json.loads(record_path.read_bytes())
        except (OSError, ValueError):
            done = None
        if isinstance(done, dict) and done.get('digest_schema') == schema and isinstance(done.get('digest'), dict):
            basis = _claim_of(work, digest, done['digest'])
            if basis:
                return dict(done, already_rendered=basis)
    pinned = old.get('digest')
    if isinstance(pinned, dict) and Path(str(pinned.get('path'))) == digest:
        basis = _claim_of(work, digest, pinned)
        if basis:
            return dict(schema='FRANKIE_DIGEST_RENDER_V1', digest_schema=schema, digest=pinned, already_rendered=basis,
                        reason='the ROOT\'s own digest of the current schema stands; no render')
    return None


EXPERIMENT_ROOTS = Path('/opt/frankie-box/work/experiment-roots')      # frankie_box_experiment.ROOTS
EXPERIMENT_SCHEMA = 'FRANKIE_EXPERIMENT_DAY_CALCULATIONS_V1'
MONDAY_SCHEMA = 'FRANKIE_MONDAY_CALCULATIONS_V1'


def root_kind(output, old):
    """('monday' | 'experiment', day, the receipt keys to re-witness) for a retained root, or a ValueError.
    Session 6 (2026-10-08): an experiment ROOT (frankie_box_experiment_root.py, under experiment-roots) is rendered too:
    the day from its receipt, producer failures allowed (Greg: nothing dropped, the day goes on), no `result` pin."""
    if output.parent == PARENT:
        if old.get('schema') != MONDAY_SCHEMA or old.get('status') != 'calculations_retained':
            raise ValueError('retained Monday calculations required')
        return 'monday', '20211004', ('source_binding', 'calculation_pins', 'derivation', 'result')
    if output.parent == EXPERIMENT_ROOTS:
        if old.get('schema') != EXPERIMENT_SCHEMA or not str(old.get('status', '')).startswith('calculations_retained'):
            raise ValueError('retained experiment ROOT calculations required')
        if not re.fullmatch('[0-9]{8}', str(old.get('day') or '')):
            raise ValueError('the experiment receipt names no day')
        return 'experiment', str(old['day']), ('source_binding', 'calculation_pins', 'derivation')
    raise ValueError('retained Monday calculation root or experiment root required')




def _retained_inputs(session, derivation):
    """(spools, layer_witnesses) for load_retained_layers on an experiment root, exactly as the ROOT resume takes them:
    every layer by its holding file claim (else read whole once), every sealed spool from its count (no whole count)."""
    from frankie_box_boss_session import _artifact_check, _load_file_claims, _reuse_check_mode, LEGACY_REUSE_CHECK_SETTING
    from frankie_box_experiment_root import reopen_retained_spools
    claims, mode = _load_file_claims(session.work), _reuse_check_mode(LEGACY_REUSE_CHECK_SETTING)
    witnessed, bases = {}, []
    for item in derivation['layers'].values():
        path = safe_path(item['path'])
        seen, basis = _artifact_check(dict(item, path=str(path)), claims, mode, claims_dir=session.work)
        if dict(seen, path=str(path)) != {k: item[k] for k in ('path', 'bytes', 'sha256')}:
            raise ValueError('retained calculation layer differs: ' + item['path'])
        witnessed[str(path.resolve())] = dict(path=str(path), bytes=item['bytes'], sha256=item['sha256'])
        bases.append(basis)
    checks, spools = reopen_retained_spools(session, derivation, claims, mode)
    print('RENDER inputs: %d layers, %d by their claim; %d spools, %d reopened from a sealed count' % (
        len(bases), sum(str(b).startswith('the saved claim') for b in bases), len(checks),
        sum(c['count'] is not None for c in checks)), flush=True)
    return spools, witnessed


def render(commit, output_root, keep_receipt=False):
    require_checkout(commit)
    output = safe_path(output_root)
    if not output.is_dir():
        raise ValueError('retained calculation root required')
    lock = (output / 'calculation.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    from frankie_box_progress import snapshot, for_session
    if snapshot(output).get('process_alive'):
        raise ValueError('a calculation process is still alive on this root')
    receipt_path = output / 'calculations-receipt.json'
    old = read_pin(witness(receipt_path))
    kind, day, pinned_keys = root_kind(output, old)
    for key in pinned_keys:
        if witness(Path(old[key]['path'])) != old[key]:
            raise ValueError(key + ' changed since the calculation was retained')
    derivation = json.loads(Path(old['derivation']['path']).read_bytes())
    if kind == 'monday' and derivation.get('failure_count') != 0:
        raise ValueError('calculation failures remain')
    if keep_receipt and kind != 'experiment':
        raise ValueError('--keep-receipt is the experiment root route (the day in flight)')
    # 2026-10-09: --keep-receipt is the ONLY experiment route: a render without it (no FRANKIE_RENDER_BOOKING) must never
    # rewrite the ROOT's calculations-receipt.json, whose sha256 the teacher's shared identity binds
    keep_receipt = keep_receipt or kind == 'experiment'
    record_path = output / 'work' / RENDER_RECORD
    import frankie_box_digest_render as DG
    done = already_rendered(output, old, DG.SCHEMA)
    if done is not None:
        print('RENDER already done: ' + json.dumps(dict(record=str(record_path), digest=done.get('digest'),
                                                        basis=done.get('already_rendered')), sort_keys=True), flush=True)
        return done

    from frankie_box_boss_session import Session
    session = Session(output, day, '00', None)
    session.request_sha256 = old['source_binding']['sha256']
    for_session(session)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    aside = output / 'superseded' / ('digest-render-' + stamp)
    aside.mkdir(parents=True)
    moved = {}
    for key in ('digest', 'digest_proof'):
        # A rerun after a stopped render can find the receipt's file already moved aside, or a stopped render's own
        # output in its place. Only a file whose bytes and sha256 match the receipt's witness is the previous one.
        if not old.get(key):
            # an experiment ROOT run with the digest off: nothing previous to move; a stopped render's own output in
            # the way is kept aside as an orphan (never named previous)
            path = session.work / ('derivation-digest-full.md' if key == 'digest' else 'digest-proof.json')
            if path.exists():
                path.rename(aside / ('orphan-' + path.name))
                moved['orphan_' + key] = str(aside / ('orphan-' + path.name))
            continue
        path = Path(old[key]['path'])
        if path.parent != session.work:
            raise ValueError(key + ' path outside the root work directory')
        if path.exists() and not _same(path, old[key], session.work):
            path.rename(aside / ('orphan-' + path.name))       # a stopped render's output: kept, never named previous
            moved['orphan_' + key] = str(aside / ('orphan-' + path.name))
        if path.exists():
            path.rename(aside / path.name)
            moved[key] = str(aside / path.name)
        else:
            earlier = [p for p in (output / 'superseded').glob('digest-render-*/' + glob.escape(path.name))
                       if p.parent != aside and _same(p, old[key], session.work)]
            if earlier:
                moved[key] = str(sorted(earlier)[0])
    session.phase('deriving', 'render-only: the digest in ' + DG.SCHEMA + ' from the retained layers (legacy tables; bedrock stays in its layer files); no recalculation')
    # an experiment root: producer failures allowed (allow_failures reads derive.json's listed inputs); every frames row
    # rendered whole (Greg, 2026-10-08: no data dropped; the full depth as the ROOT's own digest renders it)
    spools, witnessed = _retained_inputs(session, derivation) if kind == 'experiment' else (None, None)
    _, _, _, prices, frames, structures, _, layers, _ = load_retained_layers(session, allow_failures=(kind == 'experiment'),
                                                                            receipt=derivation if kind == 'experiment' else None,
                                                                            spools=spools, layer_witnesses=witnessed)
    proof = write_retained_digest(session, derivation, layers, prices, frames, structures, bedrock=False)
    # one pass: the digest's pin is the writer's write-stream witness (its claim row was appended at write time); the
    # size on disk is checked, the bytes are not read again
    digest_path = session.work / DIGEST_NAME
    digest_pin = dict(path=str(digest_path), bytes=int(proof['bytes']), sha256=proof['sha256'])
    if digest_path.stat().st_size != digest_pin['bytes']:
        raise ValueError('the rendered digest on disk differs in size from its write-stream witness')
    if keep_receipt:
        # the day is in flight: the ROOT's receipt stays byte for byte (the teacher binds its sha256); the render's own
        # record names the digest, its proof and the receipt it left standing
        record = dict(schema='FRANKIE_DIGEST_RENDER_V1', digest_schema=DG.SCHEMA, at=time.time(), commit=commit, day=day,
                      root_kind=kind, digest=digest_pin,
                      digest_proof=witness(session.work / 'digest-proof.json'), root_receipt_kept=witness(receipt_path),
                      moved_aside=moved, recalculation=False, model_calls=0,
                      render_booking=os.environ.get('FRANKIE_RENDER_BOOKING'), lane_cpus=os.environ.get('FRANKIE_LANE_CPUS'),
                      bedrock_tables='not rendered: retained in the layer files',
                      reason='the ROOT ran with the digest off; rendered from the retained layers inside the day\'s booking')
        if record_path.exists():                      # an earlier record whose digest is gone: kept aside, never named
            record_path.rename(aside / RENDER_RECORD)
        save_new(record_path, record)
        session.phase('derived', 'render-only done (ROOT receipt kept): ' + DG.SCHEMA)
        print('RENDER ' + json.dumps(dict(record=str(record_path), digest=record['digest'], receipt_kept=record['root_receipt_kept'],
                                          schema=DG.SCHEMA), sort_keys=True), flush=True)
        return record

    # where the bedrock tables are: the moved-aside digest when it carries them, else wherever the last render said
    previous = old.get('digest_render') or {}
    bedrock_in = moved['digest'] if 'digest' in moved and _has_bedrock(
        Path(moved['digest']), proof=moved.get('digest_proof')) else previous.get('bedrock_tables_in')
    superseded = aside / 'calculations-receipt.json'
    os.link(receipt_path, superseded)                 # the old receipt stays in place until the new one replaces it
    receipt = dict(old, commit=commit,
                   digest=digest_pin,
                   digest_proof=witness(session.work / 'digest-proof.json'),
                   digest_render=dict(schema='FRANKIE_DIGEST_RENDER_V1', digest_schema=DG.SCHEMA, at=time.time(),
                                      supersedes=witness(superseded), previous_digest=old.get('digest'),
                                      previous_digest_proof=old.get('digest_proof'), moved_aside=moved,
                                      recalculation=False, model_calls=0, bedrock_tables_in=bedrock_in,
                                      root_kind=kind, day=day,
                                      bedrock_tables='not rendered: retained in the layer files' +
                                                     (' and in ' + bedrock_in if bedrock_in else '')))
    if kind == 'experiment':
        # the ROOT's own record of process 4 stays as the ROOT wrote it; the render is the additive record above
        receipt['digest_rendered_later'] = dict(at=receipt['digest_render']['at'], by='frankie_box_render_digest.py',
                                                reason='the ROOT ran with the digest off; rendered from the retained layers')
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
    parser.add_argument('--keep-receipt', action='store_true',
                        help='leave calculations-receipt.json as the ROOT wrote it; record work/digest-render.json')
    args = parser.parse_args()
    render(args.commit, args.output_root, keep_receipt=args.keep_receipt)


if __name__ == '__main__':
    main()
