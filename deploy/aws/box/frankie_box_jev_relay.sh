# Jev's relay (Greg, 2026-09-28: Jev sits in with Frankie through classroom and they talk "more than every 30 min").
# READ-ONLY on the running principal session: every RELAY_SECONDS it bundles what is new in the session (phase, note,
# progress, work/classroom/*.json, each finished model call's name and answer text) and PUTs the bundle to the next
# presigned slot clm-sidecar/<STAMP>/feed/NNNN.json. Nothing is cut (Greg, 2026-09-28: no file, answer or note is
# truncated): every file and answer goes whole; a bundle larger than MAX_BUNDLE_BYTES (the size of one slot object, not
# a data cap) is written as JEV_FEED_PART_V1 parts over consecutive slots (bundle sha256, part i of n) that the reader
# (clm_sidecar/sit_in.py) joins and checks. A bundle that fits is the unchanged JEV_FEED_BUNDLE_V1 object. The first bundle also carries the dipole classroom material from
# the request (attachment.dipole_classroom). Jev's Pod reads the same slots. The box role writes nothing in S3, so the
# runner signs the slots: dispatch with presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/feed:240"
# presign_hours=12. DIPOLE_FILE (Greg, 2026-09-28: "resend the earlier dipole info"): a JSON file under /opt/frankie-box
# (e.g. <code root>/research/kalshi/frankie_boss/knowledge/DIPOLE_SHARED_CATALOG_20260922.json, the shared dipole catalog
# the classroom loads) sent whole in the first bundle, labelled as that file, while the relay keeps looking for the
# request's own attachment.dipole_classroom and sends that too once a launch writes it.
# Inputs: STAMP, SESSION (session root; default the Monday calculations root), REQUEST_DIRECTORY,
# RELAY_SECONDS (default 120), MAX_BUNDLE_BYTES (default 4000000). Ends when the slots run out or the session phase is final.
set -eu
: "${STAMP:?Jev stamp required}"; : "${MAP_URL:?presigned map required (presign putrange)}"
case "$STAMP" in *[!A-Za-z0-9_.-]*|'') echo "invalid STAMP" >&2; exit 2;; esac
export STAMP MAP_URL SESSION="${SESSION:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48}"
export DIPOLE_FILE="${DIPOLE_FILE:-}" REQUEST_DIRECTORY="${REQUEST_DIRECTORY:-}" RELAY_SECONDS="${RELAY_SECONDS:-120}" MAX_BUNDLE_BYTES="${MAX_BUNDLE_BYTES:-4000000}"
case "$SESSION" in /opt/frankie-box/*) ;; *) echo "SESSION must be under /opt/frankie-box" >&2; exit 2;; esac
case "$DIPOLE_FILE" in ''|/opt/frankie-box/*) ;; *) echo "DIPOLE_FILE must be under /opt/frankie-box" >&2; exit 2;; esac
case "$DIPOLE_FILE" in *..*) echo "DIPOLE_FILE without .." >&2; exit 2;; esac
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
file_sent = not os.environ['DIPOLE_FILE']


def read(path):
    # whole, never cut
    try:
        return path.read_bytes().decode('utf-8', errors='replace')
    except OSError:
        return None


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


import hashlib
position = 0
while position < len(slots):
    index = position
    phase = (read(SESSION / 'phase') or '').strip()
    bundle = dict(schema='JEV_FEED_BUNDLE_V1', stamp=STAMP, index=index, at=time.time(), phase=phase,
                  note=(read(SESSION / 'note') or '').strip(), progress=None, classroom={}, answers=[])
    try:
        bundle['progress'] = json.loads(read(SESSION / 'progress.json') or 'null')
    except ValueError:
        pass
    if not dipole_sent:
        # every bundle carries the dipole material until it has been found once (Greg, 2026-09-28: the request is
        # written when the launch reaches its WAIT, after the relay starts; bundle 0 alone would miss it)
        bundle['dipole'] = dipole_material()
        dipole_sent = bundle['dipole'].get('dipole_classroom') is not None
    if not file_sent and not (bundle.get('dipole') or {}).get('dipole_classroom'):
        # the earlier dipole material, whole, once (Greg: resend it now), in the field every Jev reader takes, labelled
        # with its source; the relay goes on looking for the request's own attachment and sends that too
        try:
            bundle['dipole'] = dict(path=os.environ['DIPOLE_FILE'], source='DIPOLE_FILE (not a request attachment)',
                                    dipole_classroom=json.loads(Path(os.environ['DIPOLE_FILE']).read_bytes()))
            file_sent = True
        except (OSError, ValueError) as error:
            bundle['dipole_file_error'] = dict(path=os.environ['DIPOLE_FILE'], error='%s: %s' % (type(error).__name__, error))
    for path in sorted((work / 'classroom').glob('*.json')) if (work / 'classroom').is_dir() else []:
        if changed(path):
            bundle['classroom'][path.name] = read(path)
    for outcome in sorted((work / 'boss-jobs').glob('*/outcome.json'), key=lambda p: p.stat().st_mtime) if (work / 'boss-jobs').is_dir() else []:
        if changed(outcome):
            try:
                value = json.loads(outcome.read_bytes())
            except (OSError, ValueError):
                continue
            bundle['answers'].append(dict(job=outcome.parent.name, name=value.get('name'), incomplete=value.get('incomplete'),
                                          error=value.get('error'), text=value.get('text') or ''))
    raw = json.dumps(bundle, sort_keys=True).encode()
    if len(raw) <= CAP:
        objects = [raw]
    else:
        # too big for one slot object: consecutive JEV_FEED_PART_V1 parts, joined and checked by the reader
        text, digest = raw.decode(), hashlib.sha256(raw).hexdigest()
        step = max(1, CAP // 2)
        chunks = [text[i:i + step] for i in range(0, len(text), step)]
        objects = [json.dumps(dict(schema='JEV_FEED_PART_V1', stamp=STAMP, index=index, part=i, parts=len(chunks),
                                   sha256=digest, bytes=len(raw), data=chunk), sort_keys=True).encode()
                   for i, chunk in enumerate(chunks)]
    if position + len(objects) > len(slots):
        raise SystemExit('bundle %04d needs %d slots, %d left: dispatch the relay again with more slots (nothing was cut)'
                         % (index, len(objects), len(slots) - position))
    for number, data in enumerate(objects):
        request = urllib.request.Request(slots[position][1], data=data, method='PUT')
        with urllib.request.urlopen(request, timeout=300) as response:
            print('feed %04d phase=%s classroom=%d answers=%d bytes=%d part=%d/%d http=%d' % (
                position, phase, len(bundle['classroom']), len(bundle['answers']), len(data), number + 1, len(objects),
                response.status), flush=True)
        position += 1
    if phase in FINAL:
        print('session phase %s is final; relay ends' % phase, flush=True)
        break
    time.sleep(PERIOD)
PY
