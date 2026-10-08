"""Digest decode-ladder canary on a SLICE of a frames spool (ROOT-digest role, 2026-10-08; Greg's standing rule: a 1-2
minute canary, then extrapolate). The identity proof the container cannot run (the c15 codec needs the pinned producers
checkout): the SAME line-aligned slice of a closed RowSpool (default the first 2 GiB) is written as the table
`legacy_book_imbalance` by frankie_box_digest_parallel.write_table_parallel under FRANKIE_DIGEST_DECODES=5 (the
present writer: cross context, snapshot, plan, final, verify) and =2 (snapshot + plan, the cells scratch, the canonical
verify), on the lane's pinned helpers; the two tables' sha256 must be equal, the fused context must equal
cross_context row for row, both inverse proofs must pass. Wall seconds per run and the slice's bytes give the whole
spool's time at each setting. Read-only on the spool; writes only under --out (deleted at the end but the report,
unless --keep). Dry run by default (--run executes).

Lane: FRANKIE_LANE_CPUS (e.g. 16-31) is required for --run and checked against the box's CPU bookings
(/opt/frankie-box/cpu-bookings, frankie_box_cores.live_bookings: a booking with a live pid, or a retained one, holds
its CPUs): any overlap refuses with exit 4 and names the booking. The coordinator thread takes the lane's first CPU,
the helpers the rest (frankie_box_digest_document.cpu_placement), one part per helper."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

BOX = Path(__file__).resolve().parent
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))

DEFAULT_OUT = Path('/opt/frankie-box/work/digest-canary-slice')
SCHEMA = 'FRANKIE_DIGEST_CANARY_SLICE_V1'
TABLE = 'legacy_book_imbalance'


def parse_cpus(text):
    listed = set()
    for part in (text or '').split(','):
        part = part.strip()
        if part:
            low, _, high = part.partition('-')
            listed.update(range(int(low), int(high or low) + 1))
    return sorted(listed)


def booking_conflicts(cpus):
    """[(booking id, overlapping cpus)] for every live or retained booking holding any of cpus."""
    import frankie_box_cores as C
    wanted = set(cpus)
    out = []
    for b in C.live_bookings():
        held = set(b.get('cpus') or []) & wanted
        if held and (b.get('_alive') or b.get('_retained')):
            out.append((b.get('booking'), sorted(held)))
    return out


def slice_end(path, size, wanted):
    """The byte just after the line that holds byte wanted-1 (a line-aligned end), or the file's size."""
    if wanted >= size:
        return size
    with path.open('rb') as handle:
        handle.seek(max(0, wanted - 1))
        handle.readline()
        return min(handle.tell(), size)


def slice_specs(path, end, parts):
    """Ordered part specs over the spool's first `end` bytes (spool_specs' cut rule, bounded to the slice)."""
    cuts = [0]
    with path.open('rb') as handle:
        for k in range(1, max(1, parts)):
            nominal = end * k // parts
            if nominal <= cuts[-1]:
                continue
            handle.seek(nominal - 1)
            handle.readline()
            cut = handle.tell()
            if cuts[-1] < cut < end:
                cuts.append(cut)
    cuts.append(end)
    return [dict(kind='spool', path=str(path), start=a, end=b) for a, b in zip(cuts, cuts[1:]) if b > a]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--spool', required=True, help='a closed RowSpool file (work/derived/.rows/frames.jsonl)')
    parser.add_argument('--bytes', type=int, default=2 << 30, help='slice size, line-aligned up (default 2 GiB)')
    parser.add_argument('--out', default=None, help='report + scratch directory (default %s/<stamp>)' % DEFAULT_OUT)
    parser.add_argument('--run', action='store_true', help='execute (default: dry run, the plan printed)')
    parser.add_argument('--keep', action='store_true', help='keep the two tables and scratch (default: deleted)')
    parser.add_argument('--settings', default='5,2', help='the FRANKIE_DIGEST_DECODES values to run, in order (default 5,2)')
    parser.add_argument('--reserve', type=int, default=None,
                        help='bytes kept free on the scratch filesystem (default FRANKIE_DIGEST_DISK_RESERVE, else the writer\'s 32 GiB)')
    args = parser.parse_args()

    spool = Path(args.spool)
    if not spool.is_file():
        print('refused: %s is not a file' % spool, file=sys.stderr)
        return 2
    settings = [int(s) for s in args.settings.split(',') if s.strip()]
    if any(s not in (5, 4, 3, 2) for s in settings) or len(settings) < 2:
        print('refused: --settings needs two or more of 5,4,3,2', file=sys.stderr)
        return 2
    lane_text = os.environ.get('FRANKIE_LANE_CPUS', '')
    lane = parse_cpus(lane_text)
    affinity = sorted(os.sched_getaffinity(0))
    if args.run and not lane:
        print('refused: FRANKIE_LANE_CPUS is required to run (the lane the canary may use)', file=sys.stderr)
        return 2
    if lane and [c for c in lane if c not in affinity]:
        print('refused: FRANKIE_LANE_CPUS %s is not inside this process\'s affinity %s' % (lane_text, affinity), file=sys.stderr)
        return 2
    conflicts = booking_conflicts(lane) if lane else []
    size = spool.stat().st_size
    end = slice_end(spool, size, args.bytes)
    import frankie_box_digest_document as DD
    place = DD.cpu_placement(lane) if lane else dict(coordinator=None, helpers=[], basis='no lane given')
    helpers = place['helpers']
    parts = max(1, len(helpers))
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    out = Path(args.out) if args.out else DEFAULT_OUT / stamp
    plan = dict(schema=SCHEMA, spool=str(spool), spool_bytes=size, slice_bytes=end, slice_share=round(end / size, 6) if size else None,
                table=TABLE, settings=settings, lane=lane, coordinator=place['coordinator'], helpers=helpers, parts=parts,
                placement_basis=place['basis'], bookings_overlap=[dict(booking=b, cpus=c) for b, c in conflicts],
                out=str(out), run=bool(args.run), keep=bool(args.keep))
    print('PLAN ' + json.dumps(plan, sort_keys=True), flush=True)
    if conflicts:
        print('refused: FRANKIE_LANE_CPUS %s overlaps a live or retained booking: %s' % (
            lane_text, '; '.join('%s holds %s' % (b, c) for b, c in conflicts)), file=sys.stderr)
        return 4
    if not args.run:
        print('DRY RUN: nothing read beyond the slice cut, nothing written. Add --run (RUN=1 through the .sh) to execute.')
        return 0

    import frankie_box_digest_parallel as PP
    import frankie_box_digest_render as DG
    reserve = args.reserve if args.reserve is not None else int(os.environ.get('FRANKIE_DIGEST_DISK_RESERVE', PP.DISK_RESERVE))
    os.sched_setaffinity(0, {place['coordinator']})
    out.mkdir(parents=True, exist_ok=False)
    specs = slice_specs(spool, end, parts)
    columns = sorted({col for (_, _), (source, col) in DG.CROSS_DERIVED.items() if source == TABLE})
    report = dict(plan, started=time.time(), runs=[], disk_reserve=reserve,
                  part_specs=[dict(start=s['start'], end=s['end']) for s in specs])
    for name in PP.PASS_SETTINGS.values():
        os.environ.pop(name, None)
    contexts = {}
    tables = {}
    for setting in settings:
        os.environ[PP.DECODES_SETTING] = str(setting)
        modes = PP.pass_modes()
        directory = out / ('decodes-%d' % setting)
        directory.mkdir()
        table = directory / 'table.txt'
        phases = []
        t0 = time.time()
        with PP.PinnedPool(helpers, label='canary decodes=%d' % setting) as pool:
            if not modes['fuse_context']:
                t = time.time()
                contexts[setting] = list(PP.cross_context(specs, columns, helpers, pool=pool))
                phases.append(dict(pass_='cross_context', seconds=round(time.time() - t, 3)))
            # the columns handed over under every setting (as the document does): fused only under the setting
            proof = PP.write_table_parallel(
                table, TABLE, specs, directory / 'scratch', helpers, pool=pool, reserve=reserve,
                progress=lambda name, label: phases.append(dict(pass_=label, at=round(time.time() - t0, 3))),
                cross_columns=columns or None,
                on_cross=(lambda it, s=setting: contexts.__setitem__(s, list(it))) if modes['fuse_context'] else None)
            helpers_record = pool.record()
        wall = time.time() - t0
        with table.open('rb') as handle:
            sha = hashlib.file_digest(handle, 'sha256').hexdigest()
        tables[setting] = sha
        run = dict(setting=setting, modes={k: modes[k] for k in PP.PASS_SETTINGS}, wall_seconds=round(wall, 3),
                   slice_mb_per_second=round(end / wall / 1e6, 3) if wall else None, table_bytes=table.stat().st_size,
                   table_sha256=sha, rows=proof['rows'], verified=proof['verified'], passes=proof['passes'],
                   phases=phases, helpers=helpers_record, context_rows=len(contexts[setting]),
                   whole_spool_estimate_seconds=round(wall * size / end, 1) if end else None)
        report['runs'].append(run)
        print('RUN ' + json.dumps({k: v for k, v in run.items() if k not in ('phases', 'helpers')}, sort_keys=True), flush=True)
    first = settings[0]
    report['identical_tables'] = all(tables[s] == tables[first] for s in settings)
    report['identical_contexts'] = all(contexts[s] == contexts[first] for s in settings)
    report['verdict'] = ('IDENTICAL: the %s tables share sha256 %s and the context rows are equal' % (settings, tables[first][:16])
                         if report['identical_tables'] and report['identical_contexts'] else 'DIFFERENT: see runs')
    report['ended'] = time.time()
    (out / 'canary.json').write_text(json.dumps(report, indent=1, sort_keys=True))
    print('VERDICT ' + report['verdict'], flush=True)
    print('REPORT ' + str(out / 'canary.json'), flush=True)
    if not args.keep:
        for setting in settings:
            shutil.rmtree(out / ('decodes-%d' % setting), ignore_errors=True)
    return 0 if report['identical_tables'] and report['identical_contexts'] else 5


if __name__ == '__main__':
    sys.exit(main())
