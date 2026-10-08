"""Clean and zip a finished stage's outputs ONCE the day is saved at that stage's boundary (Greg, 2026-10-08: "when he
saves is then when he starts cleaning and zipping"; "we only do 1 pass. Eliminate the 2nd pass"; the archive-policy
lesson of session 5: per-directory archives so compression uses many CPUs, sha256 on the WRITE stream, the listing
from tar -v at creation, zstd -T0 pinned to its own CPUs, no read-back).

Two kinds of item, decided by plan() from the stage's PINS (what its receipts record as {path, bytes, sha256}) and the
pinned-input rule: an artifact a later stage reads BY PATH may move behind a symlink; the stage's output root itself,
anything a live process holds open (/proc/*/fd), the receipt files (calculations-receipt.json, derive.json,
derivation-digest-full.md, MANIFEST.json, receipt.json, completion.json), anything under FLOOR_BYTES (1 GiB) and
anything under a GUARDED prefix (a location the next stage reads through frankie_box_prepare_trading_day.safe_path,
which refuses a symlink at the path or any parent: for the ROOT, work/derived/.rows/, work/bedrock/ and
work/derived/.projection-v2/) stays where it is, with the reason listed.
  move     a PINNED file of FLOOR_BYTES or more outside every guarded prefix: copied UNCOMPRESSED to
           <archive>/<path relative to the box root> with sha256 computed on the write stream (4 MiB reads), the stream
           hash compared with the pin (bytes and sha256), then the source renamed aside, a symlink put at the old path,
           the aside unlinked, an ARCHIVED README beside it. The symlink serves the exact pinned bytes, so every reader
           that opens the path (frankie_box_filehash.witness, RowSpool.reopen, layer_spool, _JSON/layer_text,
           load_retained_layers) and the validator (frankie_box_root_validate) are satisfied.
  archive  a directory of FLOOR_BYTES or more that holds NO pinned file: tar -v | zstd -T0 to <archive>/<rel>.tar.zst,
           sha256 on the write stream, the tar -v listing captured at creation, zstd's own frame checksums (its default)
           plus that stream sha256 are the integrity record; ONE PASS ONLY: no read-back, no decompress-list; then the
           source directory is removed, a symlink to the .tar.zst stands at the old path with the README.
Cross-device: copy + verify + replace, never os.replace across devices. Largest first across the lane's CPUs through
frankie_box_lane_pin (core order; each job owns a CPU slice, zstd -T0 inside it; a failed job keeps its source and is
listed, never retried here). --dry-run prints the plan with sizes and changes nothing. The moved-manifest
(FRANKIE_ROOT_MOVE_MANIFEST_V1: {old_path, new_path, kind, bytes, sha256, listing_path, ...} per item) is what the
validator cross-checks (frankie_box_root_validate.add_manifest) and what a restore reads.

S3 as the destination (Greg's call (f), recorded, not the default): with --s3 bucket[/prefix] --region, a 'move' item
is uploaded through frankie_box_s3_transport.upload (CRT first, 128 MiB x 16, classic fallback; the pin's sha256 is
given, no local read) and a <name>.s3.json pointer stands at the old path; the validator then checks it by HeadObject.
Trade-off recorded on the receipt: gp3 2048 GiB archive volume ~$234/month at 1000 MiB/s (readable in place by the
teacher through the symlink) vs S3 Standard ~$0.023/GB-month (~$30/month for 1.3 TB) where nothing reads the file
until it is restored.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

SCHEMA = 'FRANKIE_ROOT_MOVE_RECEIPT_V1'
MANIFEST_SCHEMA = 'FRANKIE_ROOT_MOVE_MANIFEST_V1'
BOX_ROOT = Path('/opt/frankie-box')
ARCHIVE_ROOT = BOX_ROOT / 'archive'
FLOOR_BYTES = 1 << 30
CHUNK = 4 << 20                       # the shared transport's READ_CHUNK (the box's read-ahead)
STAY_NAMES = ('calculations-receipt.json', 'derive.json', 'derivation-digest-full.md', 'MANIFEST.json', 'receipt.json',
              'completion.json')
README_SUFFIX = '.ARCHIVED.README.txt'
VOLUME_VS_S3 = ('archive volume gp3 2048 GiB: ~$234/month, 1000 MiB/s, readable in place through the symlink; S3 Standard: '
                '~$0.023/GB-month (~$30/month for 1.3 TB), CRT upload 128 MiB x 16, nothing reads the object until restored; '
                "Greg's call (f)")

# ---------------------------------------------------------------------------------------------------------- reads
# Every read of a file by this module goes through _open_read, so a test can prove the archive is never read back.


def _open_read(path):
    return open(path, 'rb', buffering=0)


def open_files():
    """Real paths every live process holds open (its fds and cwd); empty when /proc is unreadable."""
    held = set()
    proc = Path('/proc')
    if not proc.is_dir():
        return held
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        for sub in ('fd', 'cwd'):
            try:
                if sub == 'cwd':
                    held.add(os.path.realpath(os.readlink(entry / 'cwd')))
                    continue
                for fd in (entry / 'fd').iterdir():
                    target = os.readlink(fd)
                    if target.startswith('/'):
                        held.add(os.path.realpath(target))
            except OSError:
                continue
    return held


# ----------------------------------------------------------------------------------------------------------- plan

def _du(path):
    total = 0
    for base, _, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def _guarded(rel, guarded):
    return any(rel == g.rstrip('/') or rel.startswith(g if g.endswith('/') else g + '/') for g in guarded)


def plan(roots, pins, *, guarded=(), floor=FLOOR_BYTES, archive_root=ARCHIVE_ROOT, box_root=BOX_ROOT, held=None):
    """The items: [{kind: move|archive|stay, old_path, new_path, bytes, reason, pinned, expected}], largest first.
    roots: the stage's output directories; pins: {realpath: expected {bytes, sha256, ...}} from the validator's
    collector; guarded: prefixes relative to each root a safe_path reader of the next stage opens."""
    held = open_files() if held is None else set(held)
    items = []
    pinned_dirs = set()
    for real in pins:
        parent = os.path.dirname(real)
        while parent and parent != '/':
            pinned_dirs.add(parent)
            parent = os.path.dirname(parent)

    def new_path_for(old, suffix=''):
        try:
            rel = Path(old).relative_to(box_root)
        except ValueError:
            rel = Path(str(old).lstrip('/'))
        return str(Path(archive_root) / rel) + suffix

    def stay(path, size, why, pinned):
        items.append(dict(kind='stay', old_path=str(path), new_path=None, bytes=size, reason=why, pinned=pinned))

    for root in roots:
        root = Path(root)
        if not root.is_dir() or root.is_symlink():
            items.append(dict(kind='stay', old_path=str(root), new_path=None, bytes=0, pinned=False,
                              reason='not a directory or already a symlink: nothing planned'))
            continue
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                entries = sorted(directory.iterdir())
            except OSError as error:
                stay(directory, 0, 'unreadable: %s' % error, False)
                continue
            for entry in entries:
                rel = entry.relative_to(root).as_posix()
                try:
                    info = entry.lstat()
                except OSError as error:
                    stay(entry, 0, 'unreadable: %s' % error, False)
                    continue
                real = os.path.realpath(str(entry))
                if entry.is_symlink():
                    stay(entry, info.st_size, 'already a symlink', real in pins)
                    continue
                if entry.is_dir():
                    if real in pinned_dirs:
                        stack.append(entry)                   # holds a pinned file: looked at file by file
                        continue
                    size = _du(entry)
                    # a directory with no pin inside is read by no later stage through a pin, so the guarded prefixes
                    # (which protect PINNED paths a safe_path reader opens) do not hold it back: a2's 68 GB pre-save
                    # ledger copy under work/bedrock/ledgers is exactly this case
                    if size < floor:
                        stay(entry, size, 'under the floor (%d < %d bytes); nothing inside is pinned' % (size, floor), False)
                    elif any(h == real or h.startswith(real + '/') for h in held):
                        stay(entry, size, 'a live process holds a file in it open', False)
                    else:
                        items.append(dict(kind='archive', old_path=str(entry), new_path=new_path_for(entry, '.tar.zst'),
                                          bytes=size, pinned=False, reason='no pinned file inside; %d bytes' % size))
                    continue
                pinned = real in pins
                if entry.name in STAY_NAMES or entry.name.endswith(README_SUFFIX) or entry.name.endswith('.s3.json'):
                    stay(entry, info.st_size, 'a receipt or marker file', pinned)
                elif info.st_size < floor:
                    stay(entry, info.st_size, 'under the floor (%d < %d bytes)' % (info.st_size, floor), pinned)
                elif not pinned:
                    stay(entry, info.st_size, 'not pinned by any receipt (listed, not moved on its own)', False)
                elif _guarded(rel, guarded):
                    stay(entry, info.st_size, 'read by a safe_path reader of the next stage (refuses symlinks): stays on this '
                                              'volume; Greg\'s call: bind mount or reader change', True)
                elif real in held:
                    stay(entry, info.st_size, 'a live process holds it open', True)
                else:
                    items.append(dict(kind='move', old_path=str(entry), new_path=new_path_for(entry), bytes=info.st_size,
                                      pinned=True, expected={k: pins[real].get(k) for k in ('bytes', 'sha256')},
                                      reason='pinned, %d bytes, outside every guarded prefix: behind a symlink' % info.st_size))
    order = {'move': 0, 'archive': 0, 'stay': 1}
    items.sort(key=lambda i: (order[i['kind']], -i['bytes'], i['old_path']))
    return items


# -------------------------------------------------------------------------------------------------------- execute

def _readme(old, new, kind, bytes_, sha256, listing=None):
    text = ('ARCHIVED %s\n%s -> %s\nkind: %s\nbytes: %d\nsha256 (of the %s, computed on the write stream): %s\n%s'
            'restore: %s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), old, new, kind, bytes_,
                              'archive' if kind == 'archive' else 'file', sha256,
                              ('listing: %s\n' % listing) if listing else '',
                              ('rm the symlink; zstd -dc %s | tar -xf - -C %s' % (new, os.path.dirname(old)))
                              if kind == 'archive' else 'rm the symlink; cp %s %s' % (new, old)))
    Path(old + README_SUFFIX).write_text(text, encoding='utf-8')


def _taskset(cpus):
    if cpus and shutil.which('taskset'):
        return ['taskset', '-c', ','.join(str(c) for c in cpus)]
    return []


def _copy_hashed(source, destination):
    """One pass: the bytes read from source are hashed as they are written to destination.part; (bytes, sha256)."""
    part = destination + '.part'
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    hashed, size = hashlib.sha256(), 0
    with _open_read(source) as src, open(part, 'wb') as out:
        for block in iter(lambda: src.read(CHUNK), b''):
            out.write(block)
            hashed.update(block)
            size += len(block)
        out.flush()
        os.fsync(out.fileno())
    return part, size, hashed.hexdigest()


def _replace_with_symlink(old, new, aside_suffix):
    """old -> aside (same device), symlink old -> new, aside removed; the original stands until the symlink exists."""
    aside = old + aside_suffix
    os.rename(old, aside)
    try:
        os.symlink(new, old)
    except OSError:
        os.rename(aside, old)
        raise
    if os.path.isdir(aside) and not os.path.islink(aside):
        shutil.rmtree(aside)
    else:
        os.unlink(aside)


def do_move(item, cpus=None, say=print):
    old, new, expected = item['old_path'], item['new_path'], item.get('expected') or {}
    started = time.monotonic()
    part, size, sha = _copy_hashed(old, new)
    out = dict(item, bytes_copied=size, sha256=sha, seconds=None, status=None)
    if expected.get('bytes') is not None and size != expected['bytes'] or \
            expected.get('sha256') and sha != expected['sha256']:
        os.rename(part, part + '.rejected')
        out.update(status='failed', reason='the write-stream hash differs from the pin (bytes %s vs %s, sha256 %s vs %s); '
                                           'source kept, copy kept aside as .part.rejected'
                                           % (size, expected.get('bytes'), sha, expected.get('sha256')))
        out['seconds'] = round(time.monotonic() - started, 3)
        return out
    os.rename(part, new)
    _replace_with_symlink(old, new, '.moving-aside')
    _readme(old, new, 'move', size, sha)
    out.update(status='done', seconds=round(time.monotonic() - started, 3))
    say('moved %14d B %8.1f s  %s -> %s' % (size, out['seconds'], old, new))
    return out


def do_archive(item, cpus=None, say=print, zstd=None):
    """tar -v | zstd -T0 -> <new>.part with the stream sha256; the listing from tar -v; ONE pass, no read-back."""
    old, new = item['old_path'], item['new_path']
    started = time.monotonic()
    zstd = zstd or os.environ.get('FRANKIE_ZSTD') or 'zstd'
    out = dict(item, status=None)
    if not shutil.which(zstd):
        out.update(status='failed', reason='%s not installed; source kept' % zstd)
        return out
    Path(new).parent.mkdir(parents=True, exist_ok=True)
    part, listing_path = new + '.part', new + '.listing.txt'
    pin = _taskset(cpus)
    tar_cmd = pin + ['tar', '-cvf', '-', '-C', os.path.dirname(old), os.path.basename(old)]
    zstd_cmd = pin + [zstd, '-T0', '-q', '-']
    hashed, size = hashlib.sha256(), 0
    with open(listing_path, 'wb') as listing, open(part, 'wb') as archive:
        tar = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE, stderr=listing)
        comp = subprocess.Popen(zstd_cmd, stdin=tar.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar.stdout.close()
        for block in iter(lambda: comp.stdout.read(CHUNK), b''):
            archive.write(block)
            hashed.update(block)
            size += len(block)
        errors = comp.stderr.read().decode('utf-8', 'replace')
        tar_rc, zstd_rc = tar.wait(), comp.wait()
        archive.flush()
        os.fsync(archive.fileno())
    try:
        entries = sum(1 for _ in open(listing_path, 'rb'))
    except OSError:
        entries = None
    out.update(bytes_archived=size, sha256=hashed.hexdigest(), tar_rc=tar_rc, zstd_rc=zstd_rc, listing_path=listing_path,
               entries=entries, source_bytes=item['bytes'], cpus=list(cpus or []))
    if tar_rc != 0 or zstd_rc != 0 or size == 0:
        os.rename(part, part + '.rejected')
        out.update(status='failed', reason='tar rc %s, zstd rc %s, %d bytes (%s); source kept, archive kept aside as '
                                           '.part.rejected' % (tar_rc, zstd_rc, size, errors.strip()[:200]))
        out['seconds'] = round(time.monotonic() - started, 3)
        return out
    os.rename(part, new)
    Path(new + '.sha256').write_text('%s  %s\n' % (out['sha256'], os.path.basename(new)), encoding='utf-8')
    _replace_with_symlink(old, new, '.archiving-aside')
    _readme(old, new, 'archive', size, out['sha256'], listing_path)
    out.update(status='done', seconds=round(time.monotonic() - started, 3))
    say('archived %14d B -> %14d B %8.1f s  %s -> %s' % (item['bytes'], size, out['seconds'], old, new))
    return out


def execute(items, *, cpus=None, say=print, zstd=None, s3=None):
    """Every move/archive item, largest first, in parallel over the lane's CPUs: jobs = min(items, max(1, lane // 4)),
    each job owning a CPU slice of the core order (zstd -T0 runs inside it). Returns the results (stay items copied
    through). A failed job keeps its source; nothing is retried here."""
    import frankie_box_lane_pin as LP
    lane = list(cpus) if cpus else LP.lane_cpus()
    order, basis = LP.core_order(lane)
    todo = [i for i in items if i['kind'] in ('move', 'archive')]
    results = [dict(i, status='stay') for i in items if i['kind'] == 'stay']
    if not todo:
        return results, dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, jobs=0, slices=[], basis=basis)
    jobs = min(len(todo), max(1, len(order) // 4))
    slices = [order[i::jobs] for i in range(jobs)]
    lock, counter, done = threading.Lock(), [0], []

    def run(item):
        with lock:
            index = counter[0]
            counter[0] += 1
        slice_cpus = slices[index % jobs]
        try:
            if item['kind'] == 'move':
                if s3 is not None:
                    result = s3(item)
                else:
                    result = do_move(item, slice_cpus, say)
            else:
                result = do_archive(item, slice_cpus, say, zstd)
        except Exception as error:  # noqa: BLE001 - one item's failure is listed; the others go on
            result = dict(item, status='failed', reason='%s: %s' % (type(error).__name__, str(error)[:300]))
        result['cpu_slice'] = list(slice_cpus)
        with lock:
            done.append(result)
        return result
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        list(pool.map(run, todo))
    return results + done, dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, jobs=jobs, slices=slices, basis=basis,
                                rule='largest first; each job owns one slice of the core order; zstd -T0 inside it')


def write_manifest(path, results, **fields):
    moves = [{k: r.get(k) for k in ('kind', 'old_path', 'new_path', 'bytes', 'bytes_archived', 'bytes_copied', 'sha256',
                                    'listing_path', 'entries', 'status', 'bucket', 'key')}
             for r in results if r['kind'] in ('move', 'archive') and r.get('status') == 'done']
    body = dict(schema=MANIFEST_SCHEMA, at=time.time(), moves=moves, volume_vs_s3=VOLUME_VS_S3,
                rule='every move: the symlink at old_path serves new_path; every archive: one tar -v | zstd -T0 pass, sha256 '
                     'on the write stream, no read-back; a failed item keeps its source and is not listed here', **fields)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(body, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)
    return body


def clean(roots, pins, *, out_dir, cpus=None, guarded=(), floor=FLOOR_BYTES, archive_root=ARCHIVE_ROOT, box_root=BOX_ROOT,
          dry_run=False, say=print, zstd=None, s3=None, held=None):
    """plan -> execute -> manifest; returns the receipt (FRANKIE_ROOT_MOVE_RECEIPT_V1). dry_run prints the plan only."""
    started = time.time()
    items = plan(roots, pins, guarded=guarded, floor=floor, archive_root=archive_root, box_root=box_root, held=held)
    planned = [i for i in items if i['kind'] != 'stay']
    for item in items:
        say('%-8s %14d B  %s%s' % (item['kind'], item['bytes'], item['old_path'],
                                   ('  -> ' + item['new_path']) if item['new_path'] else '  (' + item['reason'] + ')'))
    receipt = dict(schema=SCHEMA, at=started, roots=[str(r) for r in roots], dry_run=dry_run, floor_bytes=floor,
                   guarded=list(guarded), archive_root=str(archive_root), planned=len(planned),
                   planned_bytes=sum(i['bytes'] for i in planned), volume_vs_s3=VOLUME_VS_S3, items=items)
    if dry_run:
        receipt.update(status='planned', seconds=round(time.time() - started, 3))
        return receipt
    results, placement = execute(items, cpus=cpus, say=say, zstd=zstd, s3=s3)
    failed = [r for r in results if r.get('status') == 'failed']
    manifest = write_manifest(Path(out_dir) / 'moved-manifest.json', results, roots=[str(r) for r in roots])
    receipt.update(items=results, placement=placement, manifest=str(Path(out_dir) / 'moved-manifest.json'),
                   moved=len(manifest['moves']), failed=[dict(old_path=r['old_path'], reason=r.get('reason')) for r in failed],
                   bytes_freed=sum((r.get('bytes') or 0) for r in results if r['kind'] == 'archive' and r.get('status') == 'done')
                   + sum((r.get('bytes') or 0) for r in results if r['kind'] == 'move' and r.get('status') == 'done'),
                   status='failed' if failed else 'done', seconds=round(time.time() - started, 3))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n', 1)[0])
    parser.add_argument('--root', action='append', required=True, help='an output directory to clean (repeatable)')
    parser.add_argument('--receipt', action='append', default=[], help='a receipt file whose {path,bytes,sha256} pins protect files')
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--cpus')
    parser.add_argument('--guarded', action='append', default=[])
    parser.add_argument('--archive-root', default=str(ARCHIVE_ROOT))
    parser.add_argument('--floor-bytes', type=int, default=FLOOR_BYTES)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    import frankie_box_root_validate as V
    pins = V.collect_generic(args.receipt).jobs if args.receipt else {}
    cpus = sorted(V._parse_cpus(args.cpus)) if args.cpus else None
    receipt = clean([Path(r) for r in args.root], {k: v['expected'] for k, v in pins.items()}, out_dir=args.out_dir,
                    cpus=cpus, guarded=args.guarded, floor=args.floor_bytes, archive_root=Path(args.archive_root),
                    dry_run=args.dry_run)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.out_dir) / 'clean-receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + '\n')
    print('clean %s: %s, %d planned (%d bytes), %d moved, %d failed' % (
        ', '.join(args.root), receipt['status'], receipt['planned'], receipt['planned_bytes'], receipt.get('moved', 0),
        len(receipt.get('failed') or [])))
    return 0 if receipt['status'] in ('done', 'planned') else 3


if __name__ == '__main__':
    sys.exit(main())
