# Read-only: the BOSS's measured pace on Frankie's box. For every durable job under session/work/boss-jobs/ prints the
# request (name, estimated input tokens, output room), every observation (accepted -> queued -> running -> completed with
# times) and the outcome's usage (prompt/completion tokens) when finished; then the elapsed time of any running job and
# a tokens-per-second figure for every completed one. Reads nothing outside /opt/frankie-box; changes nothing.
set -u
ROOT=/opt/frankie-box; J="$ROOT/session/work/boss-jobs"
[ -d "$J" ] || { echo "no boss-jobs directory under $ROOT/session/work"; exit 2; }
echo "### $(date -u +%FT%TZ) phase: $(cat "$ROOT/session/phase" 2>/dev/null || echo -)  note: $(head -c 160 "$ROOT/session/note" 2>/dev/null || echo -)"
"$ROOT/venv/bin/python" - "$J" <<'PY'
import json, sys, time
from pathlib import Path
jobs = Path(sys.argv[1]); now = time.time(); rows = []
for d in sorted(jobs.iterdir(), key=lambda p: p.stat().st_mtime):
    req = json.loads((d / 'request.json').read_text()) if (d / 'request.json').exists() else {}
    obs = [json.loads(l) for l in (d / 'observations.jsonl').read_text().splitlines() if l.strip()] if (d / 'observations.jsonl').exists() else []
    out = json.loads((d / 'outcome.json').read_text()) if (d / 'outcome.json').exists() else None
    t0 = obs[0]['at'] if obs else None
    phases = ' -> '.join(f"{o['phase']}@+{o['at'] - t0:.0f}s" for o in obs) if obs else '(no observations)'
    usage = (out or {}).get('usage') or {}
    end = obs[-1]['at'] if out and obs else now
    elapsed = (end - t0) if t0 else 0
    comp = usage.get('completion_tokens'); prompt = usage.get('prompt_tokens')
    rate = f"{comp / elapsed:.1f} tok/s" if comp and elapsed else '-'
    state = ('DONE' + (' INCOMPLETE' if (out or {}).get('incomplete') else '')) if out else 'RUNNING'
    rows.append((d.name[:12], req.get('name', '?'), state, req.get('estimated_input_tokens'), req.get('max_tokens'), prompt, comp, f'{elapsed:.0f}s', rate))
    print(f"{d.name[:12]} {req.get('name', '?')}: {state}; est_in={req.get('estimated_input_tokens')} out_room={req.get('max_tokens')}; {phases}; usage prompt={prompt} completion={comp}; elapsed {elapsed:.0f}s; {rate}")
print()
print('%-13s %-12s %-16s %9s %9s %9s %9s %8s %s' % ('job', 'name', 'state', 'est_in', 'out_room', 'prompt', 'compl', 'elapsed', 'rate'))
for r in rows:
    print('%-13s %-12s %-16s %9s %9s %9s %9s %8s %s' % r)
PY
