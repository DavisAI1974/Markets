# Jev's relay for the experiment (Greg, 2026-09-29: "yes, include him"; SPEC-experiment-orchestrator.md, section "Jev").
# Jev is the blind outside student on the three classroom-arm days: he sees what Frankie sees, never Frankie's answers
# before his own claims are filed. This box side is READ-ONLY on the day's files and uploads through presigned slots
# (the box role writes nothing in S3). Two one-shot actions, each run once per classroom-arm day:
#   ACTION=material  the day's classroom material for Jev: the classroom package (MATERIAL: a request JSON carrying
#                    attachment.dipole_classroom, or the package JSON itself) and the search's survivor list so far
#                    (SURVIVORS, optional; absent = listed as unavailable, never filled in). Refuses anything under a
#                    classroom answer or output directory (the blind wall) and any day not declared DAY_ROLE=discovery
#                    (R15: confirmation days stay untouched by the classroom, the teachers, Frankie and Jev).
#                    Slots: presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/material:8"
#   ACTION=frankie   Frankie's code-classroom outputs for the comparison Jev makes AFTER filing his claims: SESSION's
#                    work/classroom/ledgers.json and receipt.json and out/analysis.md, whole. Refuses until the
#                    classroom receipt exists (the classroom stage complete).
#                    Slots: presign="putrange:frankie-granite42-568968024170-us-east-1/clm-sidecar/<STAMP>/frankie:8"
# Nothing is cut: every file goes whole with its sha256 and bytes; a bundle larger than MAX_BUNDLE_BYTES (the size of
# one slot object, not a data cap) goes as JEV_FEED_PART_V1 parts over consecutive slots that sit_in.py joins and checks.
# The same content already uploaded (same sha256) declines with the reason (duplicate data declines the run).
# Inputs: ACTION, STAMP, DAY (YYYYMMDD), DAY_ROLE (discovery), MATERIAL / SURVIVORS (material), SESSION (frankie),
# MAX_BUNDLE_BYTES (default 4000000).
set -eu
: "${ACTION:?material or frankie}"; : "${STAMP:?Jev stamp required}"; : "${MAP_URL:?presigned map required (presign putrange)}"
: "${DAY:?YYYYMMDD required}"
case "$STAMP" in *[!A-Za-z0-9_.-]*|'') echo "invalid STAMP" >&2; exit 2;; esac
case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
for name in MATERIAL SURVIVORS SESSION; do
  eval "value=\${$name:-}"
  case "$value" in ''|/opt/frankie-box/*) ;; *) echo "$name must be under /opt/frankie-box" >&2; exit 2;; esac
  case "$value" in *..*) echo "$name without .." >&2; exit 2;; esac
done
export ACTION STAMP MAP_URL DAY DAY_ROLE="${DAY_ROLE:-}" MATERIAL="${MATERIAL:-}" SURVIVORS="${SURVIVORS:-}" \
  SESSION="${SESSION:-}" MAX_BUNDLE_BYTES="${MAX_BUNDLE_BYTES:-4000000}"
exec nice -n 10 /usr/bin/python3 -B /dev/stdin <<'PY'
import hashlib, json, os, time, urllib.request
from pathlib import Path

ACTION, STAMP, DAY = os.environ['ACTION'], os.environ['STAMP'], os.environ['DAY']
CAP = int(os.environ['MAX_BUNDLE_BYTES'])
if ACTION not in ('material', 'frankie'):
    raise SystemExit('ACTION must be material or frankie')


def whole(path):
    raw = Path(path).read_bytes()
    return raw, dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def material_bundle():
    if os.environ['DAY_ROLE'] != 'discovery':
        raise SystemExit('DAY_ROLE=%r: Jev runs on discovery days only (R15); a confirmation day stays untouched'
                         % os.environ['DAY_ROLE'])
    source = os.environ['MATERIAL']
    if not source:
        raise SystemExit('MATERIAL required: the classroom package (request JSON with attachment.dipole_classroom, or the package JSON)')
    for blocked in ('/classroom/', '/out/', '/boss-jobs/', '/critic-spool/'):
        if blocked in source:
            raise SystemExit('MATERIAL %s lies under a %s directory: Frankie\'s answers never reach Jev before his claims '
                             'are filed (the blind wall)' % (source, blocked.strip('/')))
    raw, pin = whole(source)
    value = json.loads(raw)
    package = (value.get('attachment') or {}).get('dipole_classroom') if isinstance(value, dict) and 'attachment' in value else value
    if package is None:
        raise SystemExit('MATERIAL %s carries no attachment.dipole_classroom' % source)
    bundle = dict(schema='JEV_DAY_MATERIAL_V1', stamp=STAMP, day=DAY, day_role='discovery', at=time.time(),
                  material=dict(pin, source='request attachment dipole_classroom' if 'attachment' in value else 'classroom package',
                                dipole_classroom=package),
                  survivors=None, unavailable=[])
    survivors = os.environ['SURVIVORS']
    if survivors and Path(survivors).exists():
        raw, pin = whole(survivors)
        bundle['survivors'] = dict(pin, list=json.loads(raw))
    else:
        bundle['unavailable'].append(dict(item='survivors', path=survivors or None,
                                          reason='no survivor list yet (the search has not produced one for this day)'
                                          if survivors else 'SURVIVORS not given'))
    return bundle


def frankie_bundle():
    session = Path(os.environ['SESSION'] or '/nonexistent')
    receipt = session / 'work' / 'classroom' / 'receipt.json'
    if not receipt.exists():
        raise SystemExit('%s absent: Frankie\'s classroom stage has not completed, nothing to compare yet' % receipt)
    bundle = dict(schema='JEV_FRANKIE_OUTPUTS_V1', stamp=STAMP, day=DAY, at=time.time(), files={}, unavailable=[])
    for name, path in (('ledgers', session / 'work' / 'classroom' / 'ledgers.json'), ('receipt', receipt),
                       ('analysis', session / 'out' / 'analysis.md')):
        if path.exists():
            raw, pin = whole(path)
            bundle['files'][name] = dict(pin, text=raw.decode('utf-8', errors='replace'))
        else:
            bundle['unavailable'].append(dict(item=name, path=str(path), reason='not written by the session'))
    return bundle


bundle = material_bundle() if ACTION == 'material' else frankie_bundle()
prefix = 'put:clm-sidecar/%s/%s/' % (STAMP, ACTION)
entries = json.loads(urllib.request.urlopen(os.environ['MAP_URL'], timeout=60).read())
slots = sorted((k, v['url']) for k, v in entries.items() if k.startswith(prefix))
if not slots:
    raise SystemExit('no free %s slots for %s (a slot already written is never overwritten: dispatch a fresh range)' % (ACTION, STAMP))
raw = json.dumps(bundle, sort_keys=True).encode()
digest = hashlib.sha256(raw).hexdigest()
if len(raw) <= CAP:
    objects = [raw]
else:
    text, step = raw.decode(), max(1, CAP // 2)
    chunks = [text[i:i + step] for i in range(0, len(text), step)]
    objects = [json.dumps(dict(schema='JEV_FEED_PART_V1', stamp=STAMP, index=0, part=i, parts=len(chunks), sha256=digest,
                               bytes=len(raw), data=chunk), sort_keys=True).encode() for i, chunk in enumerate(chunks)]
if len(objects) > len(slots):
    raise SystemExit('the %s bundle needs %d slots, %d free: dispatch again with more slots (nothing was cut)'
                     % (ACTION, len(objects), len(slots)))
first = slots[0][0].rsplit('/', 1)[1]
if first != '0000.json':
    raise SystemExit('slot %s is the first free one: a %s bundle was already uploaded for %s; the same day\'s material is '
                     'not sent twice (duplicate data declines the run)' % (first, ACTION, STAMP))
for number, data in enumerate(objects):
    request = urllib.request.Request(slots[number][1], data=data, method='PUT')
    with urllib.request.urlopen(request, timeout=300) as response:
        print('%s %s part=%d/%d bytes=%d http=%d' % (ACTION, slots[number][0][4:], number + 1, len(objects), len(data),
                                                      response.status), flush=True)
print(json.dumps(dict(schema='JEV_RELAY_RECEIPT_V1', action=ACTION, stamp=STAMP, day=DAY, bundle_sha256=digest,
                      bundle_bytes=len(raw), parts=len(objects),
                      unavailable=bundle.get('unavailable'),
                      files={k: dict(bytes=v['bytes'], sha256=v['sha256']) for k, v in (bundle.get('files') or {}).items()}),
                 sort_keys=True), flush=True)
PY
