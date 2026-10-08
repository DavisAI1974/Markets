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
  bind_mount  (Greg, 2026-10-08: "Do what is best for both, without changing science or dropping important data") a
           GUARDED directory (the next stage's readers open it through safe_path, which refuses a symlink: the ROOT's
           work/derived/.rows and work/bedrock) of FLOOR_BYTES or more holding pinned files is MOVED by bind mount:
           every file copied to <archive>/<rel> (one pass each, sha256 on the write stream in 4 MiB reads, compared
           with the pin when pinned, largest first on the lane; symlinks and modes recreated), the original renamed
           aside, `mount --bind <copy> <old path>` plus a matching fstab line (bind,nofail), every pin verified THROUGH
           the mount by stat against the already-computed stream hash (no second read), and only then the original
           removed. A file held open under it, a copy that differs from a pin, or a failed mount leaves the original
           in place (the mount point is unwound). The validator sees a real directory, no symlink chain.
  archive (redundant native segments)  inside work/bedrock, once native-stage.json is complete: the resumed native
           sink's append segments <ledger>.append.jsonl and the pre-save copy work/bedrock/ledgers/<ledger>.jsonl are
           byte prefix/suffix of the pinned final ledger (a2: 66,121,336,080 + 127,622,314,364 = 193,743,650,444 =
           exact_member_rows.jsonl exactly); referenced only by frankie_box_segmented_ledger._resume_sink and the
           checkpoint descriptor for a resume that cannot happen any more. When the final ledger is pinned with its
           sha256 and final bytes == prefix bytes + append bytes EXACTLY (sizes only: the 194 GB file is never read
           again), both are archived as tar.zst with the same one-pass stream sha256 (redundant_ledger_segments); any
           other arithmetic refuses (they stay, the reason listed).
  S3 Glacier second copy (call (f): both)  after the trigger, upload_archives sends every copy the clean made (the
           tar.zst files, the moved files, every file of a bind-mounted copy) through frankie_box_s3_transport.upload
           with storage_class GLACIER and the sha256 as object metadata; FRANKIE_ARCHIVE_S3=on (default) with
           FRANKIE_ARCHIVE_BUCKET / FRANKIE_ARCHIVE_PREFIX / FRANKIE_ARCHIVE_REGION; unset = recorded refusal, never a
           failed clean; nothing on the volume is deleted by it; the day's chain never waits for it.
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
import contextlib
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


def plan(roots, pins, *, guarded=(), floor=FLOOR_BYTES, archive_root=ARCHIVE_ROOT, box_root=BOX_ROOT, held=None,
         native_complete=False):
    """The items: [{kind: move|archive|bind_mount|stay, old_path, new_path, bytes, reason, pinned, expected}], the
    redundant native segments first (archived before their guarded parent is copied), then largest first.
    roots: the stage's output directories; pins: {realpath: expected {bytes, sha256, ...}} from the validator's
    collector; guarded: prefixes relative to each root a safe_path reader of the next stage opens (moved by bind mount);
    native_complete: the stage's receipt shows the native stage complete (redundant_ledger_segments)."""
    held = open_files() if held is None else set(held)
    items = []
    redundant = []
    skip = set()
    for root in roots:
        # review 2026-10-08 finding 2 (Patch B): an earlier clean that died between rename-aside and symlink/mount left
        # <old>.moving-aside / .archiving-aside / .premount-aside without its original: put it back, then plan afresh
        if Path(root).is_dir():
            for suffix in ('.moving-aside', '.archiving-aside', '.premount-aside'):
                for aside in sorted(Path(root).rglob('*' + suffix)):
                    original = Path(str(aside)[:-len(suffix)])
                    if original.exists() or original.is_symlink():
                        continue
                    try:
                        os.rename(aside, original)
                    except OSError as error:
                        items.append(dict(kind='stay', old_path=str(aside), new_path=None, bytes=0, pinned=False,
                                          reason='leftover of an interrupted clean could not be put back (%s)' % error))
                        continue
                    items.append(dict(kind='stay', old_path=str(aside), new_path=str(original), pinned=False,
                                      bytes=original.lstat().st_size if original.is_file() else _du(original),
                                      reason='leftover of an interrupted earlier clean: renamed back to %s and planned afresh '
                                             'below' % original.name))
    for root in roots:
        redundant += redundant_ledger_segments(Path(root), pins, native_complete, floor=floor, archive_root=archive_root,
                                               box_root=box_root, held=held)
        for prefix in guarded:
            directory = Path(root) / prefix.rstrip('/')
            if not directory.is_dir() or directory.is_symlink():
                continue
            real = os.path.realpath(str(directory))
            inside = {os.path.relpath(r, real): pins[r] for r in pins if r.startswith(real + '/')}
            size = _du(directory)
            skip.add(real)
            if not inside:
                skip.discard(real)                              # no pin inside: the ordinary walk decides (archive/stay)
            elif size < floor:
                items.append(dict(kind='stay', old_path=str(directory), new_path=None, bytes=size, pinned=True,
                                  reason='guarded directory under the floor (%d < %d bytes)' % (size, floor)))
            elif any(h == real or h.startswith(real + '/') for h in held):
                items.append(dict(kind='stay', old_path=str(directory), new_path=None, bytes=size, pinned=True,
                                  reason='guarded directory with a file a live process holds open: not bind-mounted'))
            else:
                try:
                    rel = directory.relative_to(box_root)
                except ValueError:
                    rel = Path(str(directory).lstrip('/'))
                items.append(dict(kind='bind_mount', old_path=str(directory), new_path=str(Path(archive_root) / rel), bytes=size,
                                  pinned=True, pins_inside={k: {x: v.get(x) for x in ('bytes', 'sha256')} for k, v in inside.items()},
                                  reason='guarded (safe_path readers refuse a symlink): %d bytes, %d pinned files; moved by '
                                         'bind mount' % (size, len(inside))))
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
        redundant_paths = {i['old_path'] for i in redundant}
        while stack:
            directory = stack.pop()
            try:
                entries = sorted(directory.iterdir())
            except OSError as error:
                stay(directory, 0, 'unreadable: %s' % error, False)
                continue
            for entry in entries:
                if os.path.realpath(str(entry)) in skip or str(entry) in redundant_paths:
                    continue                                     # a bind-mount unit or a redundant segment: planned above
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
    order = {'move': 0, 'archive': 0, 'bind_mount': 0, 'stay': 1}
    items.sort(key=lambda i: (order[i['kind']], -i['bytes'], i['old_path']))
    # review 2026-10-08 finding 3 (Patch C): the archive volume must hold the plan plus 5 %; otherwise everything stays
    # (the reason named on every item) and the boundary goes on without a save
    planned_bytes = sum(i['bytes'] for i in redundant + items if i['kind'] != 'stay')
    free = archive_free_bytes(archive_root)
    if planned_bytes and free < planned_bytes * 1.05:
        why = ('archive volume %s: %d bytes free, %d planned (+5%% = %d): nothing moved; free the volume or raise it'
               % (archive_root, free, planned_bytes, int(planned_bytes * 1.05)))
        return [dict(i, kind='stay', new_path=None, reason=why) if i['kind'] != 'stay' else i for i in redundant + items]
    return redundant + items


def archive_free_bytes(archive_root):
    """Free bytes of the filesystem the archive root is (or will be created) on: the nearest existing ancestor."""
    path = Path(archive_root)
    while not path.exists() and path.parent != path:
        path = path.parent
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def redundant_ledger_segments(root, pins, native_complete, *, floor=FLOOR_BYTES, archive_root=ARCHIVE_ROOT,
                              box_root=BOX_ROOT, held=()):
    """The resumed native sink's append segments and the pre-save ledger copy that are byte prefix/suffix of a pinned
    final ledger (see the module docstring): 'archive' items (redundant=True) when native-stage.json is complete and
    final bytes == prefix bytes + append bytes EXACTLY; 'stay' with the arithmetic otherwise. Sizes only, no read."""
    items = []
    if not native_complete:
        return items
    presave = Path(root) / 'work' / 'bedrock' / 'ledgers'

    def new_path_for(old):
        try:
            rel = Path(old).relative_to(box_root)
        except ValueError:
            rel = Path(str(old).lstrip('/'))
        return str(Path(archive_root) / rel) + '.tar.zst'

    for real, expected in sorted(pins.items()):
        path = Path(real)
        if path.suffix != '.jsonl' or path.parent.name != 'ledgers' or not path.parent.parent.name.startswith('recovery-') \
                or not expected.get('sha256') or expected.get('bytes') is None:
            continue
        append = path.with_name(path.stem + '.append.jsonl')
        prefix = presave / path.name
        if not append.is_file() and not prefix.is_file():
            continue
        if append.is_symlink() or prefix.is_symlink():
            continue                                             # archived already
        append_bytes = append.stat().st_size if append.is_file() else 0
        prefix_bytes = prefix.stat().st_size if prefix.is_file() else 0
        arithmetic = '%s: final %d == prefix %d + append %d' % (path.name, expected['bytes'], prefix_bytes, append_bytes)
        holds = expected['bytes'] == prefix_bytes + append_bytes and (append.is_file() and prefix.is_file())
        for segment, size, role in ((append, append_bytes, 'append segment'), (prefix, prefix_bytes, 'pre-save prefix copy')):
            if not segment.is_file():
                continue
            real_segment = os.path.realpath(str(segment))
            if real_segment in pins:
                items.append(dict(kind='stay', old_path=str(segment), new_path=None, bytes=size, pinned=True,
                                  reason='%s is itself pinned; not a redundant segment' % role))
            elif not holds:
                items.append(dict(kind='stay', old_path=str(segment), new_path=None, bytes=size, pinned=False,
                                  reason='redundant %s refused: the arithmetic does not hold exactly (%s)' % (role, arithmetic)))
            elif real_segment in held:
                items.append(dict(kind='stay', old_path=str(segment), new_path=None, bytes=size, pinned=False,
                                  reason='redundant %s held open by a live process' % role))
            elif size < floor:
                items.append(dict(kind='stay', old_path=str(segment), new_path=None, bytes=size, pinned=False,
                                  reason='redundant %s under the floor (%d < %d)' % (role, size, floor)))
            else:
                items.append(dict(kind='archive', old_path=str(segment), new_path=new_path_for(segment), bytes=size, pinned=False,
                                  redundant=True, final_ledger=str(path), final_sha256=expected['sha256'],
                                  reason='redundant %s of the pinned final ledger (%s; sha256 %s...): archived, never read by '
                                         'a later stage' % (role, arithmetic, expected['sha256'][:12])))
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
    try:
        with _open_read(source) as src, open(part, 'wb') as out:
            for block in iter(lambda: src.read(CHUNK), b''):
                out.write(block)
                hashed.update(block)
                size += len(block)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(part)                      # review finding 3 (Patch C): never a partial copy left on the archive volume
        raise
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


def _copy_tree_hashed(old, new, pins_inside, threads, say):
    """Every file of `old` copied under `new` (largest first, `threads` at once), each hashed on its write stream and
    compared with its pin when pinned; symlinks and modes recreated. Returns (files, problems)."""
    from concurrent.futures import ThreadPoolExecutor
    files, links, dirs = [], [], []
    for base, names, fnames in os.walk(old):
        rel_base = os.path.relpath(base, old)
        dirs.append(rel_base)
        for name in names:
            full = os.path.join(base, name)
            if os.path.islink(full):
                links.append(os.path.normpath(os.path.join(rel_base, name)))
        for name in fnames:
            full = os.path.join(base, name)
            rel = os.path.normpath(os.path.join(rel_base, name))
            if os.path.islink(full):
                links.append(rel)
            else:
                files.append((rel, os.lstat(full).st_size))
    for rel in dirs:
        target = Path(new) / rel
        target.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copystat(os.path.join(old, rel), target)
        except OSError:
            pass
    for rel in links:
        target = Path(new) / rel
        if not target.exists() and not target.is_symlink():
            os.symlink(os.readlink(os.path.join(old, rel)), target)
    problems, records = [], []

    def one(entry):
        rel, size = entry
        src, dst = os.path.join(old, rel), os.path.join(new, rel)
        part, got, digest = _copy_hashed(src, dst)
        expected = pins_inside.get(rel)
        record = dict(rel=rel, bytes=got, sha256=digest, pinned=expected is not None)
        if expected and (expected.get('bytes') is not None and got != expected['bytes'] or
                         expected.get('sha256') and digest != expected['sha256']):
            os.rename(part, part + '.rejected')
            return record, 'copy of %s differs from its pin (bytes %s vs %s, sha256 %s vs %s)' % (
                rel, got, expected.get('bytes'), digest, expected.get('sha256'))
        os.rename(part, dst)
        try:
            shutil.copystat(src, dst)
        except OSError:
            pass
        return record, None
    with ThreadPoolExecutor(max_workers=max(1, threads)) as pool:
        for record, problem in pool.map(one, sorted(files, key=lambda f: -f[1])):
            records.append(record)
            if problem:
                problems.append(problem)
    return records, problems


def do_bind_mount(item, cpus=None, say=print, mount_cmd=None, fstab=None):
    """See the module docstring: copy (one pass, hashed) -> rename aside -> mount --bind -> verify through the mount
    (stat + the stream hashes) -> fstab line -> remove the original. Any failure before the removal unwinds the mount
    point and leaves the original in place."""
    old, new, pins_inside = item['old_path'], item['new_path'], item.get('pins_inside') or {}
    started = time.monotonic()
    out = dict(item, status=None)
    mount_cmd = mount_cmd or os.environ.get('FRANKIE_MOUNT_CMD') or 'mount'
    fstab = fstab or os.environ.get('FRANKIE_FSTAB') or '/etc/fstab'
    held = open_files()
    real = os.path.realpath(old)
    if any(h == real or h.startswith(real + '/') for h in held):
        out.update(status='failed', reason='a live process holds a file under %s open; original untouched' % old)
        return out
    Path(new).mkdir(parents=True, exist_ok=True)
    files, problems = _copy_tree_hashed(old, new, pins_inside, max(1, len(cpus or []) or 4), say)
    out.update(files=files, bytes_copied=sum(f['bytes'] for f in files), copied=len(files))
    if problems:
        out.update(status='failed', reason='; '.join(problems)[:1000] + '; original untouched, copy kept at %s' % new)
        return out
    missing = [rel for rel in pins_inside if rel not in {f['rel'] for f in files}]
    if missing:
        out.update(status='failed', reason='pinned files not found under the directory: %s; original untouched' % missing[:10])
        return out
    aside = old + '.premount-aside'
    os.rename(old, aside)
    os.mkdir(old)
    result = subprocess.run([mount_cmd, '--bind', new, old], capture_output=True, text=True)
    out['mount'] = dict(command=[mount_cmd, '--bind', new, old], exit_code=result.returncode, stderr=result.stderr[-500:])

    def unwind(why):
        # review finding 2 (Patch B): never rename the original back over a path that is still a mount point
        if mount_cmd == 'mount':
            subprocess.run(['umount', old], capture_output=True)
            if os.path.ismount(old):
                out.update(status='failed', reason=why + '; umount %s refused (busy): the copy STAYS MOUNTED, the original is '
                                                         'at %s; an operator umounts and renames it back; the next boundary '
                                                         'validates again' % (old, aside))
                out['seconds'] = round(time.monotonic() - started, 3)
                return out
        try:
            os.rmdir(old)
        except OSError as error:
            out.update(status='failed', reason=why + '; the mount point %s could not be removed (%s): the original is at %s; '
                                                     'an operator renames it back' % (old, error, aside))
            out['seconds'] = round(time.monotonic() - started, 3)
            return out
        os.rename(aside, old)
        out.update(status='failed', reason=why + '; the original is back in place, the copy kept at %s' % new)
        out['seconds'] = round(time.monotonic() - started, 3)
        return out
    if result.returncode != 0:
        return unwind('mount --bind failed (rc %d: %s)' % (result.returncode, result.stderr.strip()[:300]))
    by_rel = {f['rel']: f for f in files}
    verified, bad = [], []
    for rel, expected in pins_inside.items():
        try:
            size = os.stat(os.path.join(old, rel)).st_size
        except OSError as error:
            bad.append('%s: %s' % (rel, error.__class__.__name__))
            continue
        if size != by_rel[rel]['bytes'] or (expected.get('sha256') and by_rel[rel]['sha256'] != expected['sha256']):
            bad.append('%s: through the mount %d bytes, copied %d, pin %s' % (rel, size, by_rel[rel]['bytes'], expected))
        else:
            verified.append(rel)
    out.update(verified_through_mount=len(verified), ismount=os.path.ismount(old))
    if bad or (mount_cmd == 'mount' and not os.path.ismount(old)):
        return unwind('verification through the mount failed: %s' % (bad[:5] or 'not a mount point'))
    line = '%s %s none bind,nofail 0 0' % (new, old)
    try:
        current = Path(fstab).read_text() if Path(fstab).is_file() else ''
        if line not in current:
            with open(fstab, 'a') as handle:
                handle.write(line + '\n')
        out['fstab'] = dict(path=fstab, line=line)
    except OSError as error:
        out['fstab'] = dict(path=fstab, line=line, error=str(error))
    shutil.rmtree(aside)
    _readme(old + '.bind-mount', new, 'bind_mount', out['bytes_copied'], 'per file: see the moved-manifest')
    out.update(status='done', seconds=round(time.monotonic() - started, 3))
    say('bind-mounted %14d B %8.1f s  %s -> %s (%d files, %d pins verified through the mount)' % (
        out['bytes_copied'], out['seconds'], old, new, len(files), len(verified)))
    return out


def execute(items, *, cpus=None, say=print, zstd=None, s3=None):
    """Every move/archive item, largest first, in parallel over the lane's CPUs: jobs = min(items, max(1, lane // 4)),
    each job owning a CPU slice of the core order (zstd -T0 runs inside it). Returns the results (stay items copied
    through). A failed job keeps its source; nothing is retried here."""
    import frankie_box_lane_pin as LP
    lane = list(cpus) if cpus else LP.lane_cpus()
    order, basis = LP.core_order(lane)
    phases = [[i for i in items if i['kind'] == 'archive' and i.get('redundant')],      # before their guarded parent moves
              [i for i in items if i['kind'] in ('move', 'archive', 'bind_mount') and not i.get('redundant')]]
    results = [dict(i, status='stay') for i in items if i['kind'] == 'stay']
    if not any(phases):
        return results, dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, jobs=0, slices=[], basis=basis)
    jobs = min(max(len(p) for p in phases), max(1, len(order) // 4))
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
            elif item['kind'] == 'bind_mount':
                result = do_bind_mount(item, slice_cpus, say)
            else:
                result = do_archive(item, slice_cpus, say, zstd)
        except Exception as error:  # noqa: BLE001 - one item's failure is listed; the others go on
            result = dict(item, status='failed', reason='%s: %s' % (type(error).__name__, str(error)[:300]))
        result['cpu_slice'] = list(slice_cpus)
        with lock:
            done.append(result)
        return result
    from concurrent.futures import ThreadPoolExecutor
    for phase in phases:
        if phase:
            with ThreadPoolExecutor(max_workers=jobs) as pool:
                list(pool.map(run, phase))
    return results + done, dict(schema='FRANKIE_LANE_PLACEMENT_V1', lane=lane, jobs=jobs, slices=slices, basis=basis,
                                rule='the redundant native segments first, then largest first; each job owns one slice of '
                                     'the core order; zstd -T0 inside it; a bind-mount copy uses its slice as copy threads')


def write_manifest(path, results, **fields):
    moves = [{k: r.get(k) for k in ('kind', 'old_path', 'new_path', 'bytes', 'bytes_archived', 'bytes_copied', 'sha256',
                                    'listing_path', 'entries', 'status', 'bucket', 'key', 'redundant', 'final_ledger',
                                    'files', 'fstab', 'verified_through_mount')}
             for r in results if r['kind'] in ('move', 'archive', 'bind_mount') and r.get('status') == 'done']
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
          dry_run=False, say=print, zstd=None, s3=None, held=None, native_complete=False):
    """plan -> execute -> manifest; returns the receipt (FRANKIE_ROOT_MOVE_RECEIPT_V1). dry_run prints the plan only."""
    started = time.time()
    items = plan(roots, pins, guarded=guarded, floor=floor, archive_root=archive_root, box_root=box_root, held=held,
                 native_complete=native_complete)
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
                   bytes_freed=sum((r.get('bytes') or 0) for r in results
                                   if r['kind'] in ('archive', 'move', 'bind_mount') and r.get('status') == 'done'),
                   bind_mounts=[dict(old_path=r['old_path'], new_path=r['new_path'], files=r.get('copied'),
                                     verified_through_mount=r.get('verified_through_mount'), fstab=r.get('fstab'))
                                for r in results if r['kind'] == 'bind_mount' and r.get('status') == 'done'],
                   status='failed' if failed else 'done', seconds=round(time.time() - started, 3))
    return receipt


S3_SCHEMA = 'FRANKIE_ROOT_MOVE_S3_COPY_V1'


def archived_copies(results, archive_root=ARCHIVE_ROOT):
    """Every file the clean put on the archive volume: (path, sha256 or None, kind); a bind-mounted copy file by file."""
    copies = []
    for r in results:
        if r.get('status') != 'done':
            continue
        if r['kind'] in ('archive', 'move'):
            copies.append((r['new_path'], r.get('sha256'), r['kind']))
        elif r['kind'] == 'bind_mount':
            for f in r.get('files') or []:
                copies.append((os.path.join(r['new_path'], f['rel']), f.get('sha256'), 'bind_mount'))
    return copies


def upload_archives(results, *, out_dir, archive_root=ARCHIVE_ROOT, transport=None, say=print,
                    switch=None, bucket=None, prefix=None, region=None, storage_class='GLACIER'):
    """The S3 Glacier second copy of every archived file (call (f): both). Records a refusal (never a failure) when the
    switch is off or the bucket is unset; nothing on the volume is deleted. Receipt s3-upload-receipt.json beside the
    clean receipt, one transport receipt per object (sha256 as object metadata)."""
    switch = (switch if switch is not None else os.environ.get('FRANKIE_ARCHIVE_S3', 'on'))
    bucket = bucket if bucket is not None else os.environ.get('FRANKIE_ARCHIVE_BUCKET')
    prefix = (prefix if prefix is not None else os.environ.get('FRANKIE_ARCHIVE_PREFIX', 'frankie/archive')).strip('/')
    region = region if region is not None else os.environ.get('FRANKIE_ARCHIVE_REGION', 'us-east-1')
    started = time.time()
    copies = archived_copies(results, archive_root)
    limit = int(os.environ.get('FRANKIE_ARCHIVE_S3_MAX_BYTES') or (2 << 40))      # review finding 3 (Patch C): 2 TiB per clean
    total = sum(os.path.getsize(c[0]) for c in copies if os.path.isfile(c[0]))
    receipt = dict(schema=S3_SCHEMA, at=started, switch=switch, bucket=bucket, prefix=prefix, region=region,
                   storage_class=storage_class, objects=[], candidates=len(copies), bytes=total, max_bytes=limit,
                   volume_vs_s3=VOLUME_VS_S3,
                   rule='a second copy only: nothing on the archive volume is deleted; the day\'s chain never waits for it')
    if switch == 'off':
        receipt.update(status='refused', reason='FRANKIE_ARCHIVE_S3=off')
    elif total > limit:
        receipt.update(status='refused', reason='%d bytes exceed FRANKIE_ARCHIVE_S3_MAX_BYTES %d; nothing uploaded' % (total, limit))
    elif not bucket:
        receipt.update(status='refused', reason='FRANKIE_ARCHIVE_BUCKET unset: no S3 copy made (recorded, not a failure)')
    else:
        if transport is None:
            import frankie_box_s3_transport as transport
        uploaded = failed = 0
        for path, sha256, kind in sorted(copies, key=lambda c: -(os.path.getsize(c[0]) if os.path.isfile(c[0]) else 0)):
            try:
                rel = os.path.relpath(path, archive_root)
            except ValueError:
                rel = path.lstrip('/')
            key = '%s/%s' % (prefix, rel) if prefix else rel
            try:
                r = transport.upload(path, bucket, key, region=region, sha256=sha256, storage_class=storage_class,
                                     extra_args=dict(Metadata=dict(sha256=sha256)) if sha256 else None)
            except Exception as error:  # noqa: BLE001 - one object's failure is listed
                r = dict(status='refused', reason='%s: %s' % (type(error).__name__, str(error)[:300]), path=path, key=key)
            r = dict(r, kind=kind)
            receipt['objects'].append(r)
            uploaded += r.get('status') == 'uploaded'
            failed += r.get('status') != 'uploaded'
            say('s3 %s %s -> s3://%s/%s (%s)' % (kind, path, bucket, key, r.get('status')))
        receipt.update(status='done' if not failed else 'partial', uploaded=uploaded, failed=failed)
    receipt['seconds'] = round(time.time() - started, 3)
    path = Path(out_dir) / 's3-upload-receipt.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    pending.write_text(json.dumps(receipt, indent=1, sort_keys=True, default=str) + '\n', encoding='utf-8')
    os.replace(pending, path)
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
