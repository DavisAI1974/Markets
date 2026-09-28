# Jev's relay (Greg, 2026-09-28: Jev sits in with Frankie through classroom and they talk "more than every 30 min").
# READ-ONLY on the running principal session: every RELAY_SECONDS it bundles what is new in the session (phase, note,
# progress, work/classroom/*.json, each finished model call's name and answer text) and PUTs the bundle to the next
# presigned slot clm-sidecar/<STAMP>/feed/NNNN.json. The first bundle also carries the dipole classroom material from
# the request (attachment.dipole_classroom). Jev's Pod reads the same slots. The box role writes nothing in S3, so the
# runner signs the slots: dispatch with presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/feed:240"
# presign_hours=12. Inputs: STAMP, SESSION (session root; default the Monday calculations root), REQUEST_DIRECTORY,
# RELAY_SECONDS (default 120), MAX_BUNDLE_BYTES (default 4000000). Ends when the slots run out or the session phase is final.
set -eu
: "${STAMP:?Jev stamp required}"; : "${MAP_URL:?presigned map required (presign putrange)}"
case "$STAMP" in *[!A-Za-z0-9_.-]*|'') echo "invalid STAMP" >&2; exit 2;; esac
export STAMP MAP_URL SESSION="${SESSION:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48}"
export REQUEST_DIRECTORY="${REQUEST_DIRECTORY:-}" RELAY_SECONDS="${RELAY_SECONDS:-120}" MAX_BUNDLE_BYTES="${MAX_BUNDLE_BYTES:-4000000}"
case "$SESSION" in /opt/frankie-box/*) ;; *) echo "SESSION must be under /opt/frankie-box" >&2; exit 2;; esac
exec nice -n 10 /usr/bin/python3 -B /dev/stdin <<'PY'
import json, os, time, urllib.request
from pathlib import Path

STAMP, SESSION = os.environ['STAMP'], Path(os.environ['SESSION'])
PERIOD, CAP = int(os.environ['RELAY_SECONDS']), int(os.environ['MAX_BUNDLE_BYTES'])
FINAL = {'pushed', 'done', 'complete', 'completed', 'refused', 'failed', 'stopped'}
slots = sorted((k, v['url']) for k, v in json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read()).items()
               if k.startswith('put:clm-sidecar/%s/feed/' % STAMP))
if not slots:
    raise SystemExit('no feed slots for ' + STAMP)
work = SESSION / 'work'
seen = {}
dipole_sent = False


def read(path, limit):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    text = data[:limit].decode('utf-8', errors='replace')
    return text if len(data) <= limit else text + '\n[... truncated at %d of %d bytes]' % (limit, len(data))


def changed(path):
    try:
        st = path.stat()
    except OSError:
        return False
    mark = (st.st_size, st.st_mtime_ns)
    if seen.get(path) == mark:
        return False
    seen[path] = mark
    return True


def dipole_material():
    candidates = [Path(os.environ['REQUEST_DIRECTORY']) / 'session-request.json'] if os.environ['REQUEST_DIRECTORY'] else []
    # the principal names its request in work/verify.json (the prompt's path): found without REQUEST_DIRECTORY too
    try:
        prompt = json.loads((SESSION / 'work' / 'verify.json').read_bytes()).get('prompt', {}).get('path')
        if prompt:
            candidates.append(Path(prompt).parent / 'session-request.json')
    except (OSError, ValueError, AttributeError):
        pass
    candidates.append(SESSION / 'request' / 'session-request.json')
    for path in candidates:
        try:
            request = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        attachment = (request.get('attachment') or {}).get('dipole_classroom')
        if attachment is not None:
            return dict(path=str(path), dipole_classroom=attachment)
    return dict(path=None, dipole_classroom=None, note='no dipole_classroom attachment found in the request')


for index, (key, url) in enumerate(slots):
    phase = (read(SESSION / 'phase', 200) or '').strip()
    bundle = dict(schema='JEV_FEED_BUNDLE_V1', stamp=STAMP, index=index, at=time.time(), phase=phase,
                  note=(read(SESSION / 'note', 1000) or '').strip(), progress=None, classroom={}, answers=[])
    try:
        bundle['progress'] = json.loads(read(SESSION / 'progress.json', 200000) or 'null')
    except ValueError:
        pass
    if not dipole_sent:
        # every bundle carries the dipole material until it has been found once (Greg, 2026-09-28: the request is
        # written when the launch reaches its WAIT, after the relay starts; bundle 0 alone would miss it)
        bundle['dipole'] = dipole_material()
        dipole_sent = bundle['dipole'].get('dipole_classroom') is not None
    size = len(json.dumps(bundle))
    for path in sorted((work / 'classroom').glob('*.json')) if (work / 'classroom').is_dir() else []:
        if size < CAP and changed(path):
            text = read(path, 400000)
            bundle['classroom'][path.name] = text
            size += len(text or '')
    for outcome in sorted((work / 'boss-jobs').glob('*/outcome.json'), key=lambda p: p.stat().st_mtime) if (work / 'boss-jobs').is_dir() else []:
        if size < CAP and changed(outcome):
            try:
                value = json.loads(outcome.read_bytes())
            except (OSError, ValueError):
                continue
            answer = dict(job=outcome.parent.name, name=value.get('name'), incomplete=value.get('incomplete'),
                          error=value.get('error'), text=(value.get('text') or '')[:60000])
            bundle['answers'].append(answer)
            size += len(answer['text'])
    raw = json.dumps(bundle, sort_keys=True).encode()
    request = urllib.request.Request(url, data=raw, method='PUT')
    with urllib.request.urlopen(request, timeout=300) as response:
        print('feed %04d phase=%s classroom=%d answers=%d bytes=%d http=%d' % (
            index, phase, len(bundle['classroom']), len(bundle['answers']), len(raw), response.status), flush=True)
    if phase in FINAL:
        print('session phase %s is final; relay ends' % phase, flush=True)
        break
    time.sleep(PERIOD)
PY
