# Read-only: why does the cycle coordinator refuse 'cycle request identity changed' (2026-09-20)?
#
# Pipeline run 35528504894 declared the identity supersede and still refused at feedback_cycle.py:288,
# so the saved binding and the rebuilt one differ in more than training_identities.code_hash. This
# rebuilds the binding from what is on disk right now (initialization.c15.json identities, the
# cycle's request-plan controller/learning kwargs, the configuration's memory sha256) and prints only
# the DIFFERING key paths with a short hash per side (full values for the identity hashes, which are
# hashes already). Reads only; writes a temporary Python file under $env:TEMP; never opens the
# credential. $Day, $RunRoot, $ToolsRoot, $Python arrive from ssm_run_ps1.py --set; no path literal.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$requestId = $cfg.run_id + '-cycle-' + $CycleIndex
$probe = Join-Path $env:TEMP 'frankie_binding_diff.py'
$code = @'
import hashlib, json, sqlite3, sys
from pathlib import Path
from research.kalshi.frankie_boss.c15_journal import canonical_bytes, evidence_hash, pack, unpack
from research.kalshi.frankie_boss.feedback_cycle import _plain
run, request_id, cycle_index, cfg_path = sys.argv[1:5]
run = Path(run)
def short(v): return evidence_hash(v)[:16]
def load_c15(p):
    return unpack(json.loads(Path(p).read_bytes()))
db = sqlite3.connect((run/'cycles.sqlite').as_uri()+'?mode=ro', uri=True)
rows = db.execute('SELECT stage, digest FROM stages WHERE request=? ORDER BY stage', (request_id,)).fetchall()
print('stages for', request_id + ':', ', '.join(f'{s} {d[:12]}' for s, d in rows))
row = db.execute("SELECT payload FROM stages WHERE request=? AND stage='binding'", (request_id,)).fetchone()
db.close()
if row is None: raise SystemExit('no saved binding')
saved = unpack(json.loads(row[0]))
print('saved binding', short(saved), 'keys', sorted(saved))
print('saved training_identities:', json.dumps(saved['training_identities'], sort_keys=True))
print('saved frozen_memory_sha256:', saved['frozen_memory_sha256'])
init = run/'initialization.c15.json'
identities = load_c15(init)['identities'] if init.exists() else None
print('current initialization.c15.json:', 'absent' if identities is None else json.dumps(identities, sort_keys=True))
plan_path = run/'execution'/f'cycle-{cycle_index}'/'request-plan.c15.json'
plan = load_c15(plan_path) if plan_path.exists() else None
print('current request-plan:', 'absent' if plan is None else 'present ' + short(plan))
def find_memory(node):
    if isinstance(node, dict):
        if 'memory' in node and isinstance(node['memory'], dict) and 'sha256' in node['memory']: return node['memory']['sha256']
        for v in node.values():
            r = find_memory(v)
            if r: return r
    return None
cfg = json.loads(Path(cfg_path).read_text(encoding='utf-8-sig'))
memory = find_memory(cfg)
print('configuration memory sha256:', memory)
if plan is not None and identities is not None:
    rebuilt = dict(request_id=request_id, controller=_plain(plan['controller_kwargs']), learning=_plain(plan['learning_kwargs']),
                   training_identities=identities, frozen_memory_sha256=memory or saved['frozen_memory_sha256'])
    print('rebuilt binding', short(rebuilt))
    masked = dict(saved, training_identities=dict(saved['training_identities'], code_hash=identities['code_hash']))
    print('saved with only code_hash replaced', short(masked), '== rebuilt:', evidence_hash(masked) == evidence_hash(rebuilt))
    def walk(a, b, path):
        if type(a) is not type(b):
            print(f'  DIFF {path}: type {type(a).__name__} vs {type(b).__name__}'); return
        if isinstance(a, dict):
            for k in sorted(set(a) | set(b)):
                if k not in a: print(f'  DIFF {path}/{k}: only rebuilt ({short(b[k])})')
                elif k not in b: print(f'  DIFF {path}/{k}: only saved ({short(a[k])})')
                else: walk(a[k], b[k], f'{path}/{k}')
        elif isinstance(a, (list, tuple)):
            if len(a) != len(b): print(f'  DIFF {path}: length {len(a)} vs {len(b)}')
            elif evidence_hash(a) != evidence_hash(b):
                for i, (x, y) in enumerate(zip(a, b)):
                    if evidence_hash(x) != evidence_hash(y): walk(x, y, f'{path}[{i}]')
        elif a != b:
            if path.startswith('/training_identities') or (isinstance(a, str) and len(a) == 64 and isinstance(b, str) and len(b) == 64):
                print(f'  DIFF {path}: {a} vs {b}')
            else:
                print(f'  DIFF {path}: {type(a).__name__} {short(a)} vs {short(b)}')
    print('differences saved -> rebuilt:')
    walk(saved, rebuilt, '')
for name in ('cycles.sqlite.identity-supersede.json', 'cycles.sqlite.identity-supersede-accepted.json'):
    p = run/name
    print(name + ':', p.read_text(encoding='utf-8')[:1200] if p.exists() else 'absent')
print('done (read-only)')
'@
Set-Content -Path $probe -Value $code -Encoding ASCII
if (-not (Test-Path $Python)) { throw "host python missing: $Python" }
$env:PYTHONPATH = $ToolsRoot
Write-Output ("### binding diff for " + $requestId + " in " + $cfg.run_directory)
& $Python $probe $cfg.run_directory $requestId $CycleIndex $cfgPath
if ($LASTEXITCODE -ne 0) { throw ("probe exited " + $LASTEXITCODE) }
