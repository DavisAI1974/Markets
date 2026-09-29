# Put GitHub-runner ingests (frankie_runner_ingest.sh) onto Frankie's box as sealed ingest directories, exactly as the
# runner wrote them (Greg, 2026-09-29: the discovery days ingested on runners are pulled onto the box for the day files
# and ROOT). Dispatched through frankie_box_run.yml with presign="getprefix:bento-568968024170-us-east-2-an/frankie/ingest/<day>/ ..."
# (the box's role reads nothing in S3; it fetches through MAP_URL) and variables:
#   DAYS=<d1,d2,..>  RUN=<GitHub run id of the runner ingest>  ATTEMPT=<its attempt, default 1>
#   POINTERS_SHA=<the commit on branch frankie-ingest-pointers holding ingest_pointers/<day>-gh-<run>-<attempt>.json>
#   PARALLEL=<days pulled side by side, default 2>
#   POINTER_SOURCE=artifact (instead of POINTERS_SHA; 2026-09-29, the combined pointer commit is written only after every
#     day of the run ends): each day's pointer is its own runner-ingest job's workflow artifact ingest-pointer-<day> of
#     RUN, read from the GitHub API with the token in SSM /markets/frankie/github-token (us-east-2; memory only, never
#     printed); the zip must match the artifact's recorded sha256 digest; then the same checks as a committed pointer.
# Per day:
#   1. refused when the day already has a sealed ingest on the box (ingestion-receipt.json of that trading_day, schema
#      BOSS_BLOCK_INGESTION_RECEIPT_V1, writer compact, completion.json beside it) or the target directory exists;
#   2. every object of s3://<bucket>/frankie/ingest/<day>/gh-<run>-<attempt>/ downloaded from the map into the staging
#      directory /opt/frankie-box/work/.runner-pull-<day>-gh-<run>-<attempt>/ (a dot name: no ingest-* glob sees it; an
#      interrupted file resumes by HTTP range into <name>.part);
#   3. with POINTERS_SHA: the pointer (FRANKIE_INGEST_POINTER_V1, status sealed) read from that commit; the map's objects
#      must be exactly the pointer's files with the pointer's bytes; every staged file re-read from disk and its sha256
#      and bytes compared with the pointer; the receipt must equal the pointer's receipt and carry the day, the schema,
#      writer compact and the journal's sha256; then the staging directory is RENAMED into
#      /opt/frankie-box/work/ingest-<day>-gh-<run>-<attempt>/ (one rename: the directory appears whole, never partial),
#      create-only; a placement record goes to /opt/frankie-box/receipts/runner-pull-<day>-gh-<run>-<attempt>.json.
#      Without POINTERS_SHA the day is only staged (downloaded, bytes and sha256 printed), never placed.
# The receipts are never edited (evidence is never altered); a receipt string that names a runner path is listed.
# Nothing deleted, nothing overwritten; no model call, no Databento, no S3 write. SSM runs this under sh: POSIX only.
# CPU light (nice 10, idle-class-leaning I/O): the box's own ingests keep priority.
set -u
ROOT=/opt/frankie-box; WORK="$ROOT/work"
DAYS="${DAYS:-}"; RUN="${RUN:-}"; ATTEMPT="${ATTEMPT:-1}"; POINTERS_SHA="${POINTERS_SHA:-}"; PARALLEL="${PARALLEL:-2}"
POINTER_SOURCE="${POINTER_SOURCE:-}"
case "$POINTER_SOURCE" in ""|artifact) ;; *) echo "POINTER_SOURCE must be artifact (or unset)"; exit 2;; esac
[ -z "$POINTER_SOURCE" ] || [ -z "$POINTERS_SHA" ] || { echo "POINTERS_SHA or POINTER_SOURCE=artifact, not both"; exit 2; }
case "$RUN" in ""|*[!0-9]*) echo "RUN must be the runner ingest's GitHub run id"; exit 2;; esac
case "$ATTEMPT" in ""|*[!0-9]*) echo "ATTEMPT must be an integer"; exit 2;; esac
case "$PARALLEL" in ""|*[!0-9]*|0) echo "PARALLEL must be a positive integer"; exit 2;; esac
[ -n "$DAYS" ] || { echo "DAYS required (comma list of YYYYMMDD)"; exit 2; }
for D in $(echo "$DAYS" | tr ',' ' '); do
  case "$D" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAYS must be YYYYMMDD values ($D)"; exit 2;; esac
  [ "$D" != 20211004 ] || { echo "Monday 20211004 is the gold standard: never pulled or touched; refused"; exit 2; }
done
if [ -n "$POINTERS_SHA" ]; then
  case "$POINTERS_SHA" in *[!0-9a-f]*) echo "POINTERS_SHA must be a full 40-hex commit"; exit 2;; esac
  [ "${#POINTERS_SHA}" -eq 40 ] || { echo "POINTERS_SHA must be a full 40-hex commit"; exit 2; }
fi
[ -n "${MAP_URL:-}" ] || { echo "MAP_URL not set (dispatch with presign=getprefix:<bucket>/frankie/ingest/<day>/ per day)"; exit 2; }
case "$MAP_URL" in https://*.amazonaws.com/*) ;; *) echo "MAP_URL must be an https amazonaws URL"; exit 2;; esac
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY=python3
mkdir -p "$ROOT/tmp" "$ROOT/receipts"
MAPF="$ROOT/tmp/runner-pull-map-$$.json"
curl -fsS --proto =https -m 60 --retry 3 -o "$MAPF" --url "$MAP_URL" || { echo "map download failed"; exit 2; }
if [ -n "$POINTERS_SHA" ]; then
  # the same lock the ingest wrapper takes around fetches into the shared checkout; only the object is fetched
  ( flock 9; git -C "$ROOT/markets" fetch -q --depth 1 origin -- "$POINTERS_SHA" ) 9>"$ROOT/tmp/ingest-code.lock" \
    || { echo "fetch of the pointers commit $POINTERS_SHA failed"; exit 2; }
  git -C "$ROOT/markets" cat-file -e "$POINTERS_SHA^{commit}" || { echo "pointers commit $POINTERS_SHA not present"; exit 2; }
  echo "pointers commit $POINTERS_SHA"
fi
echo "### free before: $(df -B1 --output=avail "$ROOT" | tail -1) bytes"
MAPF="$MAPF" WORK="$WORK" ROOT="$ROOT" DAYS="$DAYS" RUN="$RUN" ATTEMPT="$ATTEMPT" POINTERS_SHA="$POINTERS_SHA" \
POINTER_SOURCE="$POINTER_SOURCE" PARALLEL="$PARALLEL" nice -n 10 ionice -c2 -n7 "$PY" - <<'PYEOF'
import hashlib, json, os, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
E = os.environ
WORK = Path(E['WORK']); ROOT = Path(E['ROOT']); RUN = E['RUN']; ATTEMPT = E['ATTEMPT']; PSHA = E['POINTERS_SHA']
ART = E.get('POINTER_SOURCE') == 'artifact'
REPO = 'DavisAI1974/Markets'
TOKEN = None
if ART:
    import boto3
    TOKEN = boto3.client('ssm', region_name='us-east-2').get_parameter(
        Name='/markets/frankie/github-token', WithDecryption=True)['Parameter']['Value'].strip()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

def artifact_pointer(day):
    """(pointer, source) from the run's ingest-pointer-<day> artifact, or (None, why)."""
    import io, zipfile
    auth = {'Authorization': 'Bearer ' + TOKEN, 'Accept': 'application/vnd.github+json', 'User-Agent': 'frankie-box'}
    url = 'https://api.github.com/repos/%s/actions/runs/%s/artifacts?name=ingest-pointer-%s' % (REPO, RUN, day)
    with urllib.request.urlopen(urllib.request.Request(url, headers=auth), timeout=60) as r:
        arts = [a for a in json.load(r)['artifacts'] if a['name'] == 'ingest-pointer-%s' % day and not a['expired']]
    if len(arts) != 1:
        return None, '%d artifacts ingest-pointer-%s in run %s (exactly one needed)' % (len(arts), day, RUN)
    a = arts[0]
    try:                                         # the API answers with a redirect to the blob; followed without the token
        urllib.request.build_opener(NoRedirect).open(urllib.request.Request(
            'https://api.github.com/repos/%s/actions/artifacts/%d/zip' % (REPO, a['id']), headers=auth), timeout=60)
        return None, 'artifact %d zip: no redirect' % a['id']
    except urllib.error.HTTPError as e:
        if e.code not in (301, 302, 303, 307, 308):
            raise
        location = e.headers['Location']
    with urllib.request.urlopen(urllib.request.Request(location, headers={'User-Agent': 'frankie-box'}), timeout=120) as r:
        raw = r.read()
    digest = hashlib.sha256(raw).hexdigest()
    if a.get('digest') and a['digest'] != 'sha256:' + digest:
        return None, 'artifact %d zip sha256 %s differs from its recorded digest %s' % (a['id'], digest, a['digest'])
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    if names != ['pointer-%s.json' % day]:
        return None, 'artifact %d holds %s, not pointer-%s.json' % (a['id'], names, day)
    data = z.read(names[0])
    return json.loads(data), dict(artifact_id=a['id'], artifact_digest=a.get('digest'), zip_sha256=digest,
                                  pointer_sha256=hashlib.sha256(data).hexdigest(), created_at=a.get('created_at'))
SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
MAP = json.load(open(E['MAPF']))
DAYS = [d for d in E['DAYS'].split(',') if d]
RUNNER_MARKS = ('/home/runner', '/mnt/frankie', '/tmp/', 'RUNNER_TEMP', '/opt/hostedtoolcache')

def say(*a):
    print(*a, flush=True)

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()

def sealed(day):
    out = []
    for r in sorted(WORK.glob('ingest-*/ingestion-receipt.json')):
        try:
            x = json.loads(r.read_bytes())
        except (OSError, ValueError):
            continue
        if x.get('schema') == SCHEMA and x.get('writer') == 'compact' and str(x.get('trading_day')) == day \
                and (r.parent / 'completion.json').is_file():
            out.append(str(r.parent))
    return out

def download(url, dest, size):
    """dest written whole (via dest.part, resumed by range); True when it holds exactly size bytes."""
    if dest.exists():
        return dest.stat().st_size == size
    part = dest.with_name(dest.name + '.part')
    for attempt in range(8):
        have = part.stat().st_size if part.exists() else 0
        if have == size:
            break
        if have > size:
            raise SystemExit('%s is larger than the object; left as it is' % part)
        req = urllib.request.Request(url, headers={'Range': 'bytes=%d-' % have} if have else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(part, 'ab') as f:
                if have and r.status != 206:
                    raise SystemExit('range resume refused for %s (status %s)' % (dest.name, r.status))
                for b in iter(lambda: r.read(8 << 20), b''):
                    f.write(b)
        except (OSError, urllib.error.URLError) as e:
            say('   retry %d for %s after %s' % (attempt + 1, dest.name, e))
            time.sleep(min(60, 5 * (attempt + 1)))
    if not part.exists() or part.stat().st_size != size:
        return False
    os.rename(part, dest)
    return True

def runner_paths(obj, where=''):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += runner_paths(v, where + '.' + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits += runner_paths(v, '%s[%d]' % (where, i))
    elif isinstance(obj, str) and (obj.startswith('/') or any(m in obj for m in RUNNER_MARKS)):
        hits.append('%s=%s' % (where, obj))
    return hits

def one(day):
    tag = '%s-gh-%s-%s' % (day, RUN, ATTEMPT)
    prefix = 'frankie/ingest/%s/gh-%s-%s/' % (day, RUN, ATTEMPT)
    final = WORK / ('ingest-' + tag); stage = WORK / ('.runner-pull-' + tag)
    res = dict(day=day, directory=str(final))
    have = sealed(day)
    if have:
        return dict(res, status='refused', reason='the day already has a sealed ingest on the box: ' + ', '.join(have))
    if os.path.lexists(final):
        return dict(res, status='refused', reason='%s exists (never overwritten)' % final)
    objs = {k[len(prefix):]: v for k, v in MAP.items() if k.startswith(prefix) and not k.startswith('put:')}
    if not objs:
        return dict(res, status='waiting', reason='no object under s3 %s in the map (the runner ingest has not uploaded '
                                                  'it, or the dispatch did not presign it)' % prefix)
    pointer = None; source = None
    if PSHA or ART:
        path = 'ingest_pointers/%s.json' % tag
        if ART:
            pointer, source = artifact_pointer(day)
            if pointer is None:
                return dict(res, status='waiting', reason=source)
            path = 'artifact %s' % source['artifact_id']
            say('   %s pointer from %s' % (day, json.dumps(source, sort_keys=True)))
        else:
            got = subprocess.run(['git', '-C', str(ROOT / 'markets'), 'show', '%s:%s' % (PSHA, path)], capture_output=True)
            if got.returncode:
                return dict(res, status='waiting', reason='no pointer %s at %s' % (path, PSHA))
            pointer = json.loads(got.stdout)
            source = dict(commit=PSHA, path=path)
        bad = [k for k, want in (('schema', 'FRANKIE_INGEST_POINTER_V1'), ('day', day), ('status', 'sealed'),
                                 ('prefix', prefix.rstrip('/'))) if str(pointer.get(k)) != want]
        rn = pointer.get('runner') or {}
        if str(rn.get('run_id')) != RUN or str(rn.get('attempt')) != ATTEMPT:
            bad.append('runner')
        if bad:
            return dict(res, status='refused', reason='pointer %s differs on %s (status %s)' % (path, bad, pointer.get('status')))
        want = {f['path']: f for f in pointer['files']}
        if set(want) != set(objs) or any(objs[p]['bytes'] != want[p]['bytes'] for p in want):
            return dict(res, status='refused', reason='the S3 objects differ from the pointer: s3 %s, pointer %s' % (
                sorted((p, o['bytes']) for p, o in objs.items()), sorted((p, f['bytes']) for p, f in want.items())))
    stage.mkdir(exist_ok=True)
    t0 = time.time()
    for p in sorted(objs, key=lambda p: objs[p]['bytes']):
        if '/' in p or p.startswith('.'):
            return dict(res, status='refused', reason='object name %r is not a plain file name' % p)
        if not download(objs[p]['url'], stage / p, objs[p]['bytes']):
            return dict(res, status='waiting', reason='download of %s incomplete (kept as .part; the next dispatch resumes it)' % p)
    files = {}
    for p in sorted(objs):
        files[p] = dict(bytes=(stage / p).stat().st_size, sha256=sha256_file(stage / p))
        say('   %s %s %d %s' % (day, p, files[p]['bytes'], files[p]['sha256']))
    res.update(staged=str(stage), files=files, download_seconds=round(time.time() - t0, 1))
    if pointer is None:
        return dict(res, status='staged', reason='no pointer source given: staged only, never placed')
    diff = [p for p in want if files[p] != dict(bytes=want[p]['bytes'], sha256=want[p]['sha256'])]
    if diff:
        return dict(res, status='refused', reason='sha256 or bytes differ from the pointer: %s (staged copy kept)' % diff)
    receipt = json.loads((stage / 'ingestion-receipt.json').read_bytes())
    checks = [receipt == pointer.get('receipt'), receipt.get('schema') == SCHEMA, receipt.get('writer') == 'compact',
              str(receipt.get('trading_day')) == day, (stage / 'completion.json').is_file(),
              receipt.get('journal_sha256') == files.get(receipt.get('journal_file'), {}).get('sha256'),
              receipt.get('journal_bytes') == files.get(receipt.get('journal_file'), {}).get('bytes')]
    if not all(checks):
        return dict(res, status='refused', reason='receipt checks failed %s (receipt=pointer, schema, writer, day, '
                                                  'completion, journal sha256, journal bytes)' % checks)
    paths = runner_paths(receipt)
    for extra in ('completion.json',):
        try:
            paths += runner_paths(json.loads((stage / extra).read_bytes()), extra)
        except ValueError:
            pass
    res['receipt_path_strings'] = paths          # listed only; the receipts are never edited
    have = sealed(day)
    if have or os.path.lexists(final):
        return dict(res, status='refused', reason='a sealed ingest of the day or the target appeared meanwhile: %s' % (have or final))
    os.rename(stage, final)                      # the whole directory at once, create-only
    rec = ROOT / 'receipts' / ('runner-pull-%s.json' % tag)
    record = dict(schema='FRANKIE_RUNNER_INGEST_PLACEMENT_V1', day=day, directory=str(final), pointer_source=source,
                  s3_prefix=prefix, files=files, placed_unix=int(time.time()),
                  receipt_path_strings=paths)
    with open(rec, 'x') as f:                    # create-only
        json.dump(record, f, indent=1, sort_keys=True)
    j = receipt['journal_file']
    return dict(res, status='placed', journal_sha256=files[j]['sha256'], journal_bytes=files[j]['bytes'],
                record=str(rec), sealed_now=sealed(day))

def guarded(day):
    try:
        return one(day)
    except BaseException as e:                   # one day's failure never stops the others; its staged files are kept
        return dict(day=day, status='failed', reason='%s: %s' % (type(e).__name__, e))

with ThreadPoolExecutor(int(E['PARALLEL'])) as ex:
    results = list(ex.map(guarded, DAYS))
say('### results')
for r in results:
    say(json.dumps({k: v for k, v in r.items() if k != 'files'}, sort_keys=True))
for r in results:
    if r['status'] == 'placed':
        say('PLACED %s %s journal sha256 %s bytes %d' % (r['day'], r['directory'], r['journal_sha256'], r['journal_bytes']))
say('summary', {s: sorted(r['day'] for r in results if r['status'] == s) for s in sorted({r['status'] for r in results})})
sys.exit(0 if all(r['status'] in ('placed', 'staged') for r in results) else 3)
PYEOF
RC=$?
echo "### free after: $(df -B1 --output=avail "$ROOT" | tail -1) bytes"
exit $RC
