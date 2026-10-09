# Put a day's calculations into Frankie's brain before any principal has finished (Greg, 2026-09-29: the Monday
# calculations never reached the brain because no Monday principal reached its brain step). Writes
# <brain>/<DAY>-cycle-<CYCLE>/ (days never share a slot: Sunday 20211003 and Monday 20211004 stay separate) through frankie_box_brain.write_entry(calcs_only=True): the derivation digest, the derivation
# receipt, the comparison and bedrock receipts and the derived-file witness only; everything a principal writes
# (ledgers, analysis, classroom, priming, the corrected classroom exchange) is listed under "unavailable". Another
# day's entry (Sunday's older cycle-<NN> slot included) is never touched; only an earlier entry for this same day and
# cycle is archived by write_entry with a move receipt (nothing deleted), and a later full entry for the day and cycle
# archives this one the same way. No model call; read-only on the root.
# ACTION=show (read-only): print what the brain holds now (every cycle-NN manifest, its entries and unavailable list).
# ACTION=write: write the entry. Inputs: CODE_ROOT (the staged checkout), DAY (YYYYMMDD), WORK (the root's work directory, e.g.
# /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work), CYCLE (e.g. 00), BRAIN (default
# /opt/frankie-box/brain, the directory the principal session uses).
set -eu
: "${MARKETS_SHA:?full dispatched commit required}"
: "${CODE_ROOT:?staged clean checkout required}"
ACTION="${ACTION:-show}"; BRAIN="${BRAIN:-/opt/frankie-box/brain}"
case "$CODE_ROOT" in /opt/frankie-box/code/*) ;; *) echo "staged checkout under /opt/frankie-box/code required" >&2; exit 2;; esac
case "$BRAIN" in /opt/frankie-box/*) ;; *) echo "BRAIN must be under /opt/frankie-box" >&2; exit 2;; esac
HEAD_SHA=$(git -C "$CODE_ROOT" rev-parse HEAD 2>/dev/null) || HEAD_SHA="${MARKETS_SHA:-}"  # 2026-10-09: recorded, never compared
[ "$HEAD_SHA" = "${MARKETS_SHA:-}" ] || { echo "code version: MARKETS_SHA ${MARKETS_SHA:-unset}, checkout $CODE_ROOT at $HEAD_SHA; this step runs on (and records) $HEAD_SHA" >&2; MARKETS_SHA=$HEAD_SHA; }
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 PYTHONPATH="$CODE_ROOT"
case "$ACTION" in
  show)
    exec /opt/frankie-box/venv/bin/python -B - "$BRAIN" <<'PY'
import json, sys
from pathlib import Path
brain = Path(sys.argv[1])
dirs = sorted({p for g in ('cycle-*', '[0-9]' * 8 + '-cycle-*') for p in brain.glob(g) if p.is_dir()}) if brain.is_dir() else []
print('%s: %d cycle entries' % (brain, len(dirs)))
for d in dirs:
    try:
        m = json.loads((d / 'MANIFEST.json').read_bytes())
    except (OSError, ValueError) as error:
        print('  %s: manifest unreadable (%s)' % (d.name, error)); continue
    print('  %s: day %s, kind %s, status %s, written %s' % (d.name, m.get('day') or 'not recorded', m.get('entry_kind', 'session'),
                                                         m.get('knowledge_status'), m.get('at')))
    for e in m.get('entries', []):
        print('    %s %s bytes include=%s  (%s)' % (e.get('name'), e.get('bytes'), e.get('include'), e.get('kind')))
    for u in m.get('unavailable', []):
        print('    UNAVAILABLE %s: %s' % (u.get('name'), u.get('reason')))
history = brain / 'history'
if history.is_dir():
    print('history: %d archived entries' % sum(1 for _ in history.iterdir()))
PY
    ;;
  write)
    : "${WORK:?root work directory required}"; : "${CYCLE:?cycle required}"; : "${DAY:?YYYYMMDD required}"
    case "$DAY" in [0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]) ;; *) echo "DAY must be YYYYMMDD" >&2; exit 2;; esac
    case "$WORK" in /opt/frankie-box/work/*) ;; *) echo "work directory under /opt/frankie-box/work required" >&2; exit 2;; esac
    case "$CYCLE" in *[!0-9]*|'') echo "CYCLE must be digits" >&2; exit 2;; esac
    [ -f "$WORK/derivation-digest-full.md" ] || { echo "no derivation digest at $WORK/derivation-digest-full.md: the calculations have not been rendered" >&2; exit 3; }
    exec /opt/frankie-box/venv/bin/python -B "$CODE_ROOT/deploy/aws/box/frankie_box_brain.py" --work "$WORK" \
      --out "$(dirname "$WORK")/out" --brain "$BRAIN" --cycle "$CYCLE" --day "$DAY" --calcs-only
    ;;
  *) echo "ACTION must be show or write" >&2; exit 2;;
esac
