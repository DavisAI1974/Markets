# Read-only probe for the cycles-stage refusal of pipeline run 35508198333 (day 20211003).
#
# Run 35510320789 (the first version of this probe) moved the diagnosis twice:
#   1. run_directory is the retained actual-feedback-run, NOT the day directory, so the
#      run-directory-binding hypothesis is dead: cycle-00 already holds host-preparation.c15.json
#      and host-ready-6d02c1fc....c15.json, and the 09-19 witness is the one the runner would read.
#   2. The failing FRANKIE_PROGRESS line carries phase data_delivery, owner transport, completed 0,
#      unit bytes -- which is verbatim the INITIAL state RunProbe sets in full_run_progress.py:64.
#      Nothing ever advanced it, and the first progress() call is the first line of runtime(). So
#      run_actual_sunday.py 812-843 never executed and is ruled out; the ValueError is raised in
#      ActualHost.__init__ or the run() setup above it.
#
# The __init__ ValueErrors, in the order they can fire:
#   a. retained_instance_id()  -> 'retained logical host instance differs'
#   b. boss_commit mismatch    -> 'explicit current BOSS commit required'
#   c. save('host-identity.c15.json') -> sunday_execution._save raises
#      'retained Sunday execution evidence changed' when the file exists with different bytes.
#      That file pins the WHOLE configuration plus a hash of every frankie_boss/refrag .py, and
#      yesterday's host advance (96e26f7d -> 6b0b37fe, boss_commit rewritten in the configuration)
#      changed both sides. This is the leading candidate and section 4 tests it directly.
#
# READ-ONLY. Starts, stops, writes and re-dispatches nothing, mints no host instance id, writes no
# witness, touches no SSM parameter, and creates nothing outside $env:TEMP (removed at the end).
# pack/canonical_bytes/unpack are pure functions; no _save is ever called.
#
# $Day, $RunRoot, $ToolsRoot and $Python are prepended by ssm_run_ps1.py --set, so this file carries
# no path literal and no credential, exactly as day_cycles.ps1 does.
$ErrorActionPreference = 'Continue'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { Write-Output ("NO_CONFIG at " + $cfgPath); return }

Write-Output "### 0 day-cycles.log (the runner catches the ValueError, so no traceback reaches it)"
$log = Join-Path $dayDirectory 'day-cycles.log'
if (Test-Path $log) {
    Write-Output ("path=" + $log + "  bytes=" + (Get-Item $log).Length + "  modified=" + (Get-Item $log).LastWriteTimeUtc.ToString('s') + 'Z')
    # SSM caps command output near 24 KB; a full run's log is far larger. Status lines and the tail only.
    Select-String -Path $log -Pattern '"status": ?"' | Select-Object -Last 8 | ForEach-Object { '  ' + $_.Line.Substring(0, [Math]::Min(300, $_.Line.Length)) }
    Write-Output '  --- last 6 lines ---'
    Get-Content $log -Tail 6 | ForEach-Object { '  ' + $_.ToString().Substring(0, [Math]::Min(300, $_.ToString().Length)) }
} else { Write-Output ("NO_LOG at " + $log) }

Write-Output "### 1 the run directory the cycles stage binds to (settled by run 35510320789; re-read)"
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
Write-Output ("run_id                   = " + $cfg.run_id)
Write-Output ("run_directory            = " + $cfg.run_directory)
Write-Output ("host_runtime.boss_commit = " + $cfg.host_runtime.boss_commit)
Write-Output ("host_runtime.repository  = " + $cfg.host_runtime.repository)
$g = Get-Command git -ErrorAction SilentlyContinue
if ($g) {
    Write-Output ("host checkout HEAD       = " + (& $g.Source -C $cfg.host_runtime.repository rev-parse HEAD))
    Write-Output ("host checkout dirty (frankie_boss/refrag), first 10:")
    & $g.Source -C $cfg.host_runtime.repository diff --name-only HEAD -- research/kalshi/frankie_boss research/refrag 2>&1 |
        Select-Object -First 10 | ForEach-Object { '    ' + $_ }
}
Write-Output ("configuration backups in the day directory (the advance writes one):")
Get-ChildItem $dayDirectory -Filter 'actual-host-configuration*' | ForEach-Object { '    ' + $_.Name + '  bytes=' + $_.Length + '  mtime=' + $_.LastWriteTimeUtc.ToString('s') + 'Z' }

Write-Output "### 2-5 the __init__ refusals, in order, with repr (c15 payloads are unpacked, never written)"
$out = Join-Path $env:TEMP 'frankie_binding_probe.out'
Remove-Item $out -ErrorAction SilentlyContinue
$probe = @"
import json, os, sys, traceback, hashlib
from pathlib import Path
TOOLS = r'$ToolsRoot'
sys.path.insert(0, TOOLS)
log = open(r'$out', 'a', encoding='ascii', errors='replace')
def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True); log.write(line + '\n'); log.flush()
try:
    from research.kalshi.frankie_boss.c15_journal import pack, unpack, canonical_bytes
    def c15(path):
        # sunday_execution._load without its canonical re-check, so a noncanonical file still reads.
        return unpack(json.loads(Path(path).read_bytes()))
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    cfg = json.loads(Path(r'$cfgPath').read_bytes())
    run_directory = Path(cfg['run_directory'])
    cycle = run_directory / 'execution' / 'cycle-$CycleIndex'
    request_id = '%s-cycle-$CycleIndex' % cfg['run_id']
    repo = Path(cfg['host_runtime']['repository']).resolve()

    say('=== CHECK a (__init__) retained_instance_id -> retained logical host instance differs ===')
    inst_path = run_directory / 'host-instance.c15.json'
    say('  REPR path =', repr(str(inst_path)), 'exists', inst_path.exists())
    instance_id = None
    if inst_path.exists():
        rec = c15(inst_path)
        say('  REPR record =', repr(rec))
        say('  keys ok   =', set(rec) == {'schema', 'run_id', 'instance_id'})
        say('  schema ok =', rec.get('schema') == 'FRANKIE_ACTUAL_HOST_INSTANCE_V1')
        say('  REPR record.run_id =', repr(rec.get('run_id')))
        say('  REPR config.run_id =', repr(cfg['run_id']))
        say('  run_id ok =', rec.get('run_id') == cfg['run_id'])
        instance_id = rec.get('instance_id')
        say('  REFUSES  =', not (set(rec) == {'schema', 'run_id', 'instance_id'}
            and rec.get('schema') == 'FRANKIE_ACTUAL_HOST_INSTANCE_V1' and rec.get('run_id') == cfg['run_id']))
    else:
        say('  absent: the runner would MINT a fresh uuid here and pass.')

    say('=== CHECK b (__init__) boss_commit -> explicit current BOSS commit required ===')
    say('  REPR config.host_runtime.boss_commit =', repr(cfg['host_runtime'].get('boss_commit')))
    say('  (host checkout HEAD is printed in section 1; equal means this check passes)')

    say('=== CHECK c (__init__) save(host-identity.c15.json) -> retained Sunday execution evidence changed ===')
    identity = run_directory / 'host-identity.c15.json'
    say('  REPR path =', repr(str(identity)), 'exists', identity.exists())
    if identity.exists():
        say('  bytes =', identity.stat().st_size, '| mtime =', identity.stat().st_mtime)
        stored = c15(identity)
        say('  stored keys =', repr(sorted(stored)))
        stored_cfg = stored.get('configuration', {})
        stored_code = stored.get('code', {})
        say('  REPR stored.configuration.host_runtime.boss_commit =',
            repr((stored_cfg.get('host_runtime') or {}).get('boss_commit')))
        say('  REPR live   .configuration.host_runtime.boss_commit =',
            repr(cfg['host_runtime'].get('boss_commit')))
        say('  configuration EQUAL =', stored_cfg == cfg)
        if stored_cfg != cfg:
            for k in sorted(set(stored_cfg) | set(cfg)):
                if stored_cfg.get(k) != cfg.get(k):
                    if k == 'host_runtime':
                        s, l = stored_cfg.get(k) or {}, cfg.get(k) or {}
                        for hk in sorted(set(s) | set(l)):
                            if s.get(hk) != l.get(hk):
                                say('    DIFFERS host_runtime.' + hk, 'stored=', repr(s.get(hk))[:200], 'live=', repr(l.get(hk))[:200])
                    else:
                        say('    DIFFERS', k, 'stored=', repr(stored_cfg.get(k))[:200], 'live=', repr(cfg.get(k))[:200])
        # self.code, rebuilt exactly as __init__ builds it.
        live_code = {str(p.relative_to(repo)): sha(p)
                     for root in ('research/kalshi/frankie_boss', 'research/refrag')
                     for p in sorted((repo / root).rglob('*.py')) if 'tests' not in p.parts}
        script = repo / 'research/kalshi/frankie_boss/operations/run_actual_sunday.py'
        if script.exists():
            live_code['host_script'] = sha(script)
        say('  code entries stored =', len(stored_code), '| live =', len(live_code))
        changed = sorted(k for k in set(stored_code) & set(live_code) if stored_code[k] != live_code[k])
        say('  code EQUAL =', stored_code == live_code)
        say('  code entries ADDED   =', repr(sorted(set(live_code) - set(stored_code))[:40]))
        say('  code entries REMOVED =', repr(sorted(set(stored_code) - set(live_code))[:40]))
        say('  code entries CHANGED =', repr(changed[:40]))
        say('  NOTE host_script is sha(__file__) of the runner actually executing; run_actual_sunday_ec2.py')
        say('  may be the real __file__, so treat a lone host_script difference as inconclusive.')
        body = dict(configuration=cfg, code=live_code)
        try:
            same = canonical_bytes(pack(body)) == identity.read_bytes()
        except Exception as e:
            same = 'could not pack: %s: %s' % (type(e).__name__, e)
        say('  BYTES EQUAL (what _save compares) =', same)
        say('  REFUSES =', same is not True)
    else:
        say('  absent: _save would create it and pass.')

    say('=== the 812-843 comparisons (downstream of the above; recorded, not the cause) ===')
    service_record = cycle / 'host-service.c15.json'
    preparation = cycle / 'host-preparation.c15.json'
    say('  cycle_directory =', repr(str(cycle)), 'exists', cycle.exists())
    say('  host-service.c15.json exists =', service_record.exists())
    say('  host-preparation.c15.json exists =', preparation.exists())
    prepared = c15(preparation) if preparation.exists() else None
    src = cfg['host_runtime'].get('pod_credential_ssm') or {}
    trig = Path(src.get('trigger_directory', '')) / request_id / 'FRANKIE_ACTUAL_EXECUTE_V1.json'
    trigger = json.loads(trig.read_bytes()) if trig.exists() else None
    ready = Path(trigger['readiness_directory']) if trigger else None
    pins = json.loads((ready / 'service-pins.json').read_bytes()) if ready and (ready / 'service-pins.json').exists() else None
    startup = json.loads((ready / 'startup-intent.json').read_bytes()) if ready and (ready / 'startup-intent.json').exists() else None
    say('  line 836 admission equal =', (pins or {}).get('admission') == (prepared or {}).get('admission'))
    delivered = (startup or {}).get('local_ready', {}).get('host_instance_id')
    say('  line 837 REPR startup.local_ready.host_instance_id =', repr(delivered))
    say('  line 837 REPR host-instance.c15.json instance_id   =', repr(instance_id))
    say('  line 837 equal =', delivered == instance_id)
    if instance_id is not None:
        rp = cycle / ('host-ready-' + instance_id + '.c15.json')
        say('  line 331 witness', repr(str(rp.name)), 'exists', rp.exists())

    say('=== WHEN the retained evidence was written (which boss_commit last entered __init__) ===')
    import datetime
    def when(path):
        return datetime.datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + 'Z'
    for path in sorted(run_directory.glob('*.c15.json')) + sorted(run_directory.glob('*.json')):
        if path.is_file():
            say('  run/ ', path.name, when(path), path.stat().st_size)
    if cycle.exists():
        for path in sorted(cycle.iterdir()):
            say('  cycle-$CycleIndex/', path.name, when(path) if path.is_file() else 'DIR',
                path.stat().st_size if path.is_file() else '')
except BaseException as e:
    say('probe failed:', type(e).__name__, e); say(traceback.format_exc())
log.close(); sys.stdout.flush(); os._exit(0)
"@
$tmp = Join-Path $env:TEMP 'frankie_binding_probe.py'
Set-Content -Path $tmp -Value $probe -Encoding ASCII
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $ToolsRoot
& $Python $tmp 2>&1 | ForEach-Object { "$_" }
if (Test-Path $out) { Write-Output '--- probe file capture ---'; Get-Content $out }
Remove-Item $tmp, $out -ErrorAction SilentlyContinue

Write-Output "### 6 the LAST gate, replayed for real: lines 818-843 with verified_service_inputs and the actual exception"
# Pipeline 35512638774 wrote host-service.c15.json (line 817) and then refused 0.5 s into granite_request:
# the remaining candidates are the service-file re-hash (823), 836, 837, verified_service_inputs itself and
# line 843. Every step below is pure verification (hashing, object construction, tokenizer load); nothing
# is written, no credential is read, and the exception text is printed here because the runner scrubs it.
$out6 = Join-Path $env:TEMP 'frankie_gate_probe.out'
Remove-Item $out6 -ErrorAction SilentlyContinue
$gate = @"
import json, sys, traceback
from pathlib import Path
TOOLS = r'$ToolsRoot'
sys.path.insert(0, TOOLS)
log = open(r'$out6', 'a', encoding='ascii', errors='replace')
def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True); log.write(line + '\n'); log.flush()
try:
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    api = actual.imports(Path(TOOLS))
    cfg = json.loads(Path(r'$cfgPath').read_bytes()); host = cfg['host_runtime']
    run_directory = Path(cfg['run_directory']); cycle = run_directory / 'execution' / 'cycle-$CycleIndex'
    prepared = api.driver._load(cycle / 'host-preparation.c15.json')
    service = api.driver._load(cycle / 'host-service.c15.json')
    ready = Path(service['directory'])
    say('REPR ready =', repr(str(ready)), '| pins_sha256 =', service['pins_sha256'])
    pins = actual.verified_json(dict(path=str(ready / 'service-pins.json'), sha256=service['pins_sha256']))
    for k in ('config_hash', 'identity_hash', 'runtime_sha256', 'request_sha256'):
        say('REPR pins.' + k, '=', repr(pins.get(k)))
    for name, digest in service['files'].items():
        actual.verified(dict(path=str(ready / name), sha256=digest))
    say('line 823 service files re-hash OK')
    say('line 836 equal =', pins['request_sha256'] == prepared['admission']['request_sha256'] and pins['admission'] == prepared['admission'])
    info = json.loads((ready / 'pod-info.json').read_bytes())
    open_run = 'run.json' in service['files']
    run = json.loads((ready / ('run.json' if open_run else 'lease.json')).read_bytes())
    startup = json.loads((ready / 'startup-intent.json').read_bytes()) if open_run else None
    instance = api.driver._load(run_directory / 'host-instance.c15.json')['instance_id']
    say('open_run =', open_run, '| line 837 equal =', bool(startup) and startup['local_ready']['host_instance_id'] == instance)
    runtime = json.loads((ready / 'service-ready.json').read_bytes())
    manifest = json.loads(api.artifacts.DEFAULT_MANIFEST.read_bytes())
    say('pod-info keys =', repr(sorted(info)), '| pod-info id =', repr(info.get('id')), '| service-ready pod_id =', repr(runtime.get('pod_id')))
    from research.kalshi.frankie_boss import granite_retained_identity as rid
    say('REPR POD_ID at host checkout =', repr(getattr(rid, 'POD_ID', None)))
    say('building LocalTokenizerAdmission ...')
    admit = api.LocalTokenizerAdmission(host['tokenizer_directory'], served_model_name='granite42-smoke', context=host['service_context'])
    say('tokenizer_sha256 equals expected =', admit.tokenizer_sha256 == host['expected_tokenizer_sha256'], '| context =', admit.context)
    try:
        si = api.verified_service_inputs(info, manifest, run, runtime_receipt=runtime,
            expected_runtime_sha256=pins['runtime_sha256'], tokenizer_admission=admit,
            output_tokens=prepared['admission']['output_tokens'], startup_intent=startup,
            request_timeout=None if open_run else 80, context_encoding=host['context_encoding'],
            service_context=host['service_context'], transport_protocol=host['transport_protocol'])
        say('verified_service_inputs RETURNED')
        say('REPR host config_hash   =', repr(si['config'].config_hash))
        say('REPR pins config_hash   =', repr(pins['config_hash']))
        say('REPR host identity_hash =', repr(si['identity'].identity_hash))
        say('REPR pins identity_hash =', repr(pins['identity_hash']))
        say('line 843 REFUSES =', si['config'].config_hash != pins['config_hash'] or si['identity'].identity_hash != pins['identity_hash'])
        say('REPR config   =', repr(si['config']))
        say('REPR identity =', repr(si['identity']))
    except Exception as e:
        say('verified_service_inputs RAISED', type(e).__name__ + ':', e)
        say(traceback.format_exc())
except BaseException as e:
    say('gate probe failed:', type(e).__name__, e); say(traceback.format_exc())
log.close(); sys.stdout.flush()
"@
$tmp6 = Join-Path $env:TEMP 'frankie_gate_probe.py'
Set-Content -Path $tmp6 -Value $gate -Encoding ASCII
& $Python $tmp6 2>&1 | Select-String -NotMatch 'DeprecationWarning|utcfromtimestamp' | ForEach-Object { "$_" }
if (Test-Path $out6) { Write-Output '--- gate probe file capture ---'; Get-Content $out6 }
Remove-Item $tmp6, $out6 -ErrorAction SilentlyContinue
Write-Output "### 7 line 833 (run 35517953486): the NEW host-preparation against the SUPERSEDED one(s) and the delivered pins"
# Which fields of the re-prepared request changed since the request the observer pinned (6cd46f98...).
# Reads only; c15 payloads unpacked; long lists summarized by length; no credential path is opened.
$out7 = Join-Path $env:TEMP 'frankie_prep_diff.out'
Remove-Item $out7 -ErrorAction SilentlyContinue
$diff = @"
import json, sys, traceback, datetime
from pathlib import Path
TOOLS = r'$ToolsRoot'
sys.path.insert(0, TOOLS)
log = open(r'$out7', 'a', encoding='ascii', errors='replace')
def say(*a):
    line = ' '.join(str(x) for x in a)
    print(line, flush=True); log.write(line + '\n'); log.flush()
def flat(value, prefix=''):
    out = {}
    if isinstance(value, dict):
        for k, v in value.items(): out.update(flat(v, prefix + str(k) + '.'))
    elif isinstance(value, (list, tuple)) and len(value) > 12:
        out[prefix.rstrip('.')] = '<list len %d>' % len(value)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value): out.update(flat(v, prefix + str(i) + '.'))
    else:
        out[prefix.rstrip('.')] = value
    return out
def when(path):
    return datetime.datetime.fromtimestamp(path.stat().st_mtime, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
try:
    from research.kalshi.frankie_boss.c15_journal import unpack
    cfg = json.loads(Path(r'$cfgPath').read_bytes())
    run = Path(cfg['run_directory']); cycle = run / 'execution' / 'cycle-$CycleIndex'
    request_id = '%s-cycle-$CycleIndex' % cfg['run_id']
    new_path = cycle / 'host-preparation.c15.json'
    say('new host-preparation exists =', new_path.exists(), '|', when(new_path) if new_path.exists() else '-')
    olds = sorted((run.parent / 'superseded').glob(run.name + '-*/execution/cycle-$CycleIndex/host-preparation.c15.json'))
    say('superseded host-preparation records =', len(olds))
    new = unpack(json.loads(new_path.read_bytes())) if new_path.exists() else None
    if new is not None:
        adm = new['admission']
        say('NEW request_sha256 =', adm.get('request_sha256'), '| input_tokens =', adm.get('input_tokens'), '| output_tokens =', adm.get('output_tokens'))
        say('NEW receipt.prompt_sha256 =', new['receipt'].get('prompt_sha256'), '| encoded_snapshot_hash =', new['receipt'].get('encoded_snapshot_hash'), '| native_snapshot_hash =', new['receipt'].get('native_snapshot_hash'))
        say('NEW context.input_hash =', new['receipt']['context'].get('input_hash'), '| model_hash =', new['receipt']['context'].get('model_hash'), '| teacher_hash =', new['receipt']['context'].get('teacher_hash'))
    for old_path in olds:
        old = unpack(json.loads(old_path.read_bytes()))
        say('--- OLD', str(old_path.parent.parent.parent.name), when(old_path))
        say('OLD request_sha256 =', old['admission'].get('request_sha256'), '| input_tokens =', old['admission'].get('input_tokens'), '| output_tokens =', old['admission'].get('output_tokens'))
        if new is None: continue
        a, b = flat(old), flat(new)
        keys = sorted(set(a) | set(b))
        same = [k for k in keys if a.get(k) == b.get(k)]
        say('  equal keys =', len(same), '| differing keys =', len(keys) - len(same))
        for k in keys:
            if a.get(k) != b.get(k):
                say('  DIFFERS', k, '| old =', repr(a.get(k))[:90], '| new =', repr(b.get(k))[:90])
    source = cfg['host_runtime'].get('pod_credential_ssm') or {}
    trigger_path = Path(source.get('trigger_directory', '')) / request_id / 'FRANKIE_ACTUAL_EXECUTE_V1.json'
    say('trigger exists =', trigger_path.exists(), '|', str(trigger_path))
    if trigger_path.exists():
        trigger = json.loads(trigger_path.read_bytes())
        pins = json.loads((Path(trigger['readiness_directory']) / 'service-pins.json').read_bytes())
        say('PINS request_sha256 =', pins.get('request_sha256'), '| admission =', repr(pins.get('admission'))[:200])
        if new is not None:
            say('line 833 REFUSES =', pins['request_sha256'] != new['admission']['request_sha256'] or pins['admission'] != new['admission'])
except BaseException as e:
    say('prep diff failed:', type(e).__name__, e); say(traceback.format_exc())
log.close(); sys.stdout.flush()
"@
$tmp7 = Join-Path $env:TEMP 'frankie_prep_diff.py'
Set-Content -Path $tmp7 -Value $diff -Encoding ASCII
& $Python $tmp7 2>&1 | Select-String -NotMatch 'DeprecationWarning' | ForEach-Object { "$_" }
Remove-Item $tmp7, $out7 -ErrorAction SilentlyContinue
Write-Output '### done (nothing was written, started, stopped or dispatched)'
