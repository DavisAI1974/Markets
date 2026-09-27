# Manual retirement of an exact reviewed list; never traverses a tree for deletion.
set -eu
[ "${CONFIRM:-}" = RETIRE_SUPERSEDED_MEMBER_LEDGERS ] || { echo "explicit retirement confirmation required"; exit 2; }
: "${MARKETS_SHA:?dispatched commit required}"
export PYTHONDONTWRITEBYTECODE=1
/opt/frankie-box/venv/bin/python -I -S -B - "$MARKETS_SHA" <<'PY'
import hashlib, json, os, pathlib, stat, sys, time, uuid
plan = json.loads("{\"schema\":\"FRANKIE_SUPERSEDED_MEMBER_LEDGER_RETIREMENT_PLAN_V1\",\"root\":\"/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48\",\"checkpoint\":\"work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/checkpoint-000000.json\",\"checkpoint_sha256\":\"2d61559ca9f5c650cdb22fa9aff29b8f0a366a648983493d435c26a3387943e6\",\"descriptor\":\"work/bedrock/recovery-8c03f629f01747158535f3cfa4f01f2d/checkpoints/controller-state-000000.json\",\"descriptor_sha256\":\"3cc7e16ce0cfa3e2c5297d98d860c5231e09c747e5f82c2de698d7f41ed26ab4\",\"keep_generation\":\"work/bedrock/recovery-9defa3169f7d46679491da2b1bfbbce2\",\"required_pid\":59092,\"required_process_token\":\"099d4eb6-a46d-4b94-a888-f15e55c1ee7e:54118158\",\"files\":[{\"path\":\"work/bedrock/recovery-03a70711353a433c989b18074d7baacd/ledgers/exact_member_rows.jsonl\",\"bytes\":312296413348,\"mtime_ns\":\"1790500613606697170\"},{\"path\":\"work/bedrock/recovery-d4b20c8f7e834d7abb1a435ff8199442/ledgers/exact_member_rows.jsonl\",\"bytes\":231083239987,\"mtime_ns\":\"1790496559775129258\"},{\"path\":\"work/bedrock/recovery-7bd18d968a384248b02e58c74f5456c6/ledgers/exact_member_rows.jsonl\",\"bytes\":186271626117,\"mtime_ns\":\"1790492722788511574\"},{\"path\":\"work/bedrock/ledgers/exact_member_rows.jsonl\",\"bytes\":118280552448,\"mtime_ns\":\"1790479714598509082\"},{\"path\":\"work/bedrock/recovery-f13de5640bf549feaae493d8861bfae1/ledgers/exact_member_rows.jsonl\",\"bytes\":97907529420,\"mtime_ns\":\"1790487293609602712\"}],\"retention_rule\":\"Keep all receipts, checkpoints, driver/adapter states, historical sections and hashes, current complete ledgers and all projection artifacts. Retire only the five explicitly listed superseded member-ledger bulk files. Earlier partial checkpoints become historical references; recovery uses the retained full terminal checkpoint.\",\"basis\":\"Full terminal checkpoint finalized at 2032203 records. restore_closed uses only its three materialized complete ledgers, whose bytes were verified during the current resume. Earlier partial ledgers are not claimed byte-identical to full current outputs.\"}")
root = pathlib.Path(plan['root'])
def safe(relative):
    path = root / relative
    if '..' in path.parts or not path.is_relative_to(root) or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('retirement path escapes the fixed root or traverses a link')
    return path
def read_pinned(relative, expected):
    raw = safe(relative).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('retained terminal evidence changed')
    return json.loads(raw)
checkpoint = read_pinned(plan['checkpoint'],plan['checkpoint_sha256'])
descriptor = read_pinned(plan['descriptor'],plan['descriptor_sha256'])
if (not checkpoint['locked'] or not descriptor['finalized']
        or checkpoint['completed_mbo_records'] != 2032203 or descriptor['completed_mbo_records'] != 2032203):
    raise ValueError('complete terminal checkpoint required')
required = []
for value in descriptor['ledgers'].values():
    path = safe(str(pathlib.Path(value['path']).relative_to(root)))
    if path.parent.parent != safe(plan['keep_generation']) or value['attributes']['_closed'] is not True:
        raise ValueError('retained checkpoint requires an unexpected ledger')
    info = path.stat()
    if info.st_size != value['attributes']['_bytes']:
        raise ValueError('retained complete ledger size differs')
    required.append(dict(path=str(path),bytes=info.st_size,sha256=value['sha256']))
progress = json.loads(safe('progress.json').read_bytes())
if progress.get('pid') != plan['required_pid'] or progress.get('process_token') != plan['required_process_token']:
    raise ValueError('current ROOT ownership changed')
proc = pathlib.Path('/proc') / str(plan['required_pid'])
if proc.exists():
    fields = (proc/'stat').read_text().rsplit(')',1)[1].split()
    token = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()+':'+fields[19]
    if token != plan['required_process_token']:
        raise ValueError('ROOT PID was reused')
targets, inodes = [], set()
for entry in plan['files']:
    path = safe(entry['path'])
    if path.name != 'exact_member_rows.jsonl' or path.parent.name != 'ledgers' or path.is_relative_to(safe(plan['keep_generation'])):
        raise ValueError('target is outside exact superseded member-ledger scope')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            info.st_size != entry['bytes'] or info.st_mtime_ns != int(entry['mtime_ns'])):
        raise ValueError('superseded ledger identity changed')
    targets.append((path,entry,info))
    inodes.add((info.st_dev,info.st_ino))
# Refuse any live reader/writer of a target, including a process outside ROOT.
for process in pathlib.Path('/proc').iterdir():
    if not process.name.isdigit():
        continue
    try:
        for fd in (process/'fd').iterdir():
            try:
                info = fd.stat()
            except FileNotFoundError:
                continue
            if (info.st_dev,info.st_ino) in inodes:
                raise ValueError('superseded ledger still open by PID '+process.name)
    except FileNotFoundError:
        continue
def sync(directory):
    fd = os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
def save(path,value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,sort_keys=True,indent=1)
        handle.flush();os.fsync(handle.fileno())
    sync(path.parent)
parent = safe('work/retention')
parent.mkdir(exist_ok=True)
sync(parent.parent)
operation = parent/('superseded-members-'+uuid.uuid4().hex)
operation.mkdir()
sync(parent)
save(operation/'intent.json',dict(plan=plan,retained_ledgers=required,dispatched_commit=sys.argv[1],at=time.time(),
    note='Complete retained-ledger hashes were verified by the current ROOT resume; this maintenance does not rerun scientific validation.'))
removed = []
for path,entry,before in targets:
    now = path.lstat()
    if (now.st_dev,now.st_ino,now.st_size,now.st_mtime_ns,now.st_nlink) != (
            before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,1):
        raise ValueError('target changed after retirement admission')
    path.unlink()
    sync(path.parent)
    row = dict(entry,allocated_bytes=before.st_blocks*512,at=time.time())
    save(operation/('removed-%02d.json'%len(removed)),row)
    removed.append(row)
space=os.statvfs(root)
receipt=dict(schema='FRANKIE_SUPERSEDED_MEMBER_LEDGER_RETIREMENT_V1',operation=str(operation),
    removed=removed,bytes_reclaimed=sum(e['allocated_bytes'] for e in removed),
    available_bytes=space.f_bavail*space.f_frsize,retained_ledgers=required,
    retained_checkpoint=plan['checkpoint'],root_restarted=False,scientific_records_replayed=0)
save(operation/'receipt.json',receipt)
print(json.dumps(receipt,sort_keys=True))
PY
