"""Isolated response/cycle preservation behavior; no native-host execution."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
import uuid
import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'b'*40
SCHEMAS = {
    'response': ('FRANKIE_PRINCIPAL_RESPONSE_INTENT_V1', 'FRANKIE_PRINCIPAL_RESPONSE_SUPERSEDED_V1'),
    'cycle': ('FRANKIE_CYCLE_STATE_INTENT_V1', 'FRANKIE_CYCLE_STATE_SUPERSEDED_V1'),
}
PREFIXES = {'response': 'principal-response-superseded-', 'cycle': 'cycle-state-superseded-'}

def sha(body): return hashlib.sha256(body).hexdigest()
def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def quote(value): return "'" + str(value).replace("'", "''") + "'"

@pytest.fixture(params=['response', 'cycle'])
def state(request, tmp_path):
    mode = request.param
    pwsh = shutil.which('pwsh')
    assert pwsh, 'PowerShell is required'
    day = tmp_path/'days/20211004'
    run = day/'fixture-run'
    cycle = run/'execution/cycle-00'
    request_id = 'isolated-remaining-preservation-cycle-00'
    handoff = 'handoff-' + sha(request_id.encode())
    if mode == 'response':
        moved = {
            'principal/session-response.json': b'{"response":"original"}',
            'principal/host-session-record.json': b'{"record":"original"}',
            'principal/incoming-1/nested/result.json': b'\x00\x80\xff\n',
            'principal/incoming-1/.hidden': b'hidden evidence',
            'principal/response-check-1/check.json': b'check',
            'principal/classroom-correction-response.json': b'correction',
            'classroom-audit/dipole-classroom-post-grade.json': b'grade',
        }
        kept = {
            'execution/cycle-00/principal/session-request.json': b'unchanged request',
            'execution/cycle-00/principal/prompt.md': b'prompt',
            'execution/cycle-00/principal/receiver/pin.json': b'receiver',
            'execution/cycle-00/principal/dipole-classroom-pre-message.json': b'pre-message',
            'execution/cycle-00/classroom-audit/dipole-classroom-teacher-key.audit.json': b'teacher key',
        }
        source = cycle
        items = {'principal/session-response.json', 'principal/host-session-record.json',
                 'principal/incoming-1', 'principal/response-check-1',
                 'principal/classroom-correction-response.json',
                 'classroom-audit/dipole-classroom-post-grade.json'}
        empty = 'principal/incoming-1/nested/empty'
    else:
        moved = {'execution/cycle-00/principal/session-request.json': b'request',
                 'execution/cycle-00/request-plan.c15.json': b'plan',
                 'execution/cycle-00/classroom-audit/.hidden': b'audit',
                 handoff+'/nested/request.json': b'handoff'}
        kept, source = {}, run
        items = {'execution/cycle-00', handoff}
        empty = 'execution/cycle-00/empty'
    kept.update({'host-instance.c15.json': b'instance', 'native-host-runtime.json': b'native',
                 'lessons.sqlite': b'lessons', 'verified-root.c15.json': b'verified',
                 'host-prefix/prefix.sqlite': b'prefix',
                 'execution/cycle-01/principal/session-response.json': b'other cycle'})
    for name, body in moved.items(): write(source/name, body)
    (source/empty).mkdir(parents=True)
    for name, body in kept.items(): write(run/name, body)
    with sqlite3.connect(run/'cycles.sqlite') as db:
        db.execute('CREATE TABLE stages (stage TEXT, request TEXT)')
        db.execute('INSERT INTO stages VALUES (?,?)', ('principal_request', request_id))
    kept['cycles.sqlite'] = (run/'cycles.sqlite').read_bytes()
    config = day/'actual-host-configuration.json'
    write(config, json.dumps(dict(run_directory=str(run), run_id='isolated-remaining-preservation',
                                 host_runtime=dict(boss_commit=COMMIT))).encode())
    name = 'frankie_host_supersede_principal_response.ps1' if mode == 'response' else 'frankie_host_supersede_cycle.ps1'
    return SimpleNamespace(mode=mode, tmp=tmp_path, pwsh=pwsh, day=day, run=run, cycle=cycle,
                           source=source, config=config, moved=moved, kept=kept, items=items,
                           script=ROOT/'deploy/aws/host'/name)

def invoke(state, *, before=False, after=0, process='absent'):
    capture = state.tmp/('observation-'+uuid.uuid4().hex+'.json')
    process_body = {'absent': "[pscustomobject]@{ Name = 'fixture-idle.exe'; CommandLine = 'fixture idle'; ProcessId = 42 }",
                    'empty': 'return',
                    'opaque-name': "[pscustomobject]@{ Name = $null; CommandLine = 'fixture idle'; ProcessId = 45 }",
                    'opaque-python': "[pscustomobject]@{ Name = 'python.exe'; CommandLine = $null; ProcessId = 43 }",
                    'opaque-py': "[pscustomobject]@{ Name = 'py.exe'; CommandLine = '   '; ProcessId = 44 }",
                    'alive': "[pscustomobject]@{ Name = 'python.exe'; CommandLine = 'python run_actual_sunday.py'; ProcessId = 12345 }",
                    'failed': "throw 'TEST_PROCESS_INVENTORY_FAILED'"}[process]
    prelude = f"""
$ErrorActionPreference = 'Stop'
$Day = '20211004'
$RunRoot = {quote(state.day.parent)}
$CycleIndex = '00'
$Reason = 'isolated durability fixture'
$Python = {quote(sys.executable)}
$global:hostMoves = 0
function Get-CimInstance {{
    param($ClassName, $Filter, $ErrorAction)
    {process_body}
}}
function Get-Date {{
    param([string]$UFormat)
    $fixed = [DateTime]::Parse('2026-09-23T12:00:00Z').ToUniversalTime()
    if ($UFormat -eq '%s') {{ return ([DateTimeOffset]$fixed).ToUnixTimeSeconds().ToString() }}
    return $fixed
}}
function Move-Item {{
    param([string]$LiteralPath, [string]$Destination)
    $global:hostMoves += 1
    if ($global:hostMoves -eq 1) {{
        $intents = @(Get-ChildItem -LiteralPath {quote(state.day)} -Filter '*.intent.json' |
          ForEach-Object {{ [ordered]@{{ path = $_.FullName; content = [IO.File]::ReadAllText($_.FullName) }} }})
        [IO.File]::WriteAllText({quote(capture)}, ($intents | ConvertTo-Json -Depth 100 -AsArray))
    }}
    if ({'$true' if before else '$false'}) {{ throw 'TEST_INTERRUPT_BEFORE_MOVE' }}
    Microsoft.PowerShell.Management\\Move-Item -LiteralPath $LiteralPath -Destination $Destination
    if ($global:hostMoves -eq {after}) {{ throw 'TEST_INTERRUPT_AFTER_MOVE' }}
}}
try {{ & {quote(state.script)} }} catch {{
    [Console]::Error.WriteLine($_.ToString())
    exit 37
}}
exit 0
"""
    result = subprocess.run([state.pwsh, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', prelude],
                            capture_output=True, text=True, timeout=60)
    return result, capture

def documents(state, schema):
    found = {}
    for path in state.day.glob(PREFIXES[state.mode]+'*.json'):
        value = read(path)
        if value.get('schema') == schema: found[path] = value
    return found

def intent_of(state):
    intents = documents(state, SCHEMAS[state.mode][0])
    assert len(intents) == 1
    return next(iter(intents.items()))

def kept_unchanged(state):
    for name, body in state.kept.items(): assert (state.run/name).read_bytes() == body, name

def source_unchanged(state):
    for name, body in state.moved.items(): assert (state.source/name).read_bytes() == body, name
    kept_unchanged(state)

def assert_done(state):
    path, intent = intent_of(state)
    completions = documents(state, SCHEMAS[state.mode][1])
    assert len(completions) == 1
    completion = next(iter(completions.values()))
    assert completion['intent_path'] == str(path) and completion['intent_sha256'] == sha(path.read_bytes())
    assert set(completion['moved']) == state.items
    assert {item['relative'] for item in intent['items']} == state.items
    for item in intent['items']:
        assert not (state.source/item['relative']).exists()
        destination = Path(item['destination'])
        for record in item['manifest']:
            target = destination if record['relative'] == '.' else destination/record['relative']
            if record['kind'] == 'directory': assert target.is_dir()
            else:
                data = target.read_bytes()
                assert len(data) == record['bytes'] and sha(data) == record['sha256']
    for name, body in state.moved.items():
        item = next(item for item in intent['items']
                    if name == item['relative'] or name.startswith(item['relative']+'/'))
        suffix = name[len(item['relative']):].lstrip('/')
        destination = Path(item['destination'])
        assert (destination/suffix if suffix else destination).read_bytes() == body
    receipts = list(state.day.glob(path.name.removesuffix('.intent.json')+'.move-*.json'))
    assert len(receipts) == len(state.items)
    assert all(read(receipt)['intent_sha256'] == sha(path.read_bytes()) for receipt in receipts)
    kept_unchanged(state)

def test_complete_manifest_intent_including_grade_precedes_first_move(state):
    result, capture = invoke(state, before=True)
    assert result.returncode != 0 and 'TEST_INTERRUPT_BEFORE_MOVE' in result.stderr
    observations = read(capture)
    assert len(observations) == 1
    intent = json.loads(observations[0]['content'])
    assert intent['schema'] == SCHEMAS[state.mode][0]
    assert intent['run_directory'] == str(state.run) and intent['run_id'] == 'isolated-remaining-preservation'
    assert intent['day'] == '20211004' and intent['cycle_index'] == '00'
    assert intent['configuration_sha256'] == sha(state.config.read_bytes()) and intent['boss_commit'] == COMMIT
    assert {item['relative'] for item in intent['items']} == state.items
    for item in intent['items']:
        assert item['manifest']
        for record in item['manifest']:
            path = state.source/item['relative']
            if record['relative'] != '.': path /= record['relative']
            if record['kind'] == 'file':
                assert record['sha256'] == sha(path.read_bytes()) and record['bytes'] == path.stat().st_size
    assert any(row['relative'].endswith('empty') for item in intent['items'] for row in item['manifest'])
    source_unchanged(state)
    assert not documents(state, SCHEMAS[state.mode][1])

@pytest.mark.parametrize('after', [1, 2])
def test_retry_after_response_or_cycle_already_moved(state, after):
    result, _ = invoke(state, after=after)
    assert result.returncode != 0 and 'TEST_INTERRUPT_AFTER_MOVE' in result.stderr
    path, _ = intent_of(state)
    original = path.read_bytes()
    result, _ = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    assert path.read_bytes() == original
    assert_done(state)

@pytest.mark.parametrize('process', ['alive', 'failed', 'empty', 'opaque-python', 'opaque-py', 'opaque-name'])
def test_process_gate_refuses_alive_or_unavailable_inventory(state, process):
    result, capture = invoke(state, process=process)
    assert result.returncode != 0 and not capture.exists()
    source_unchanged(state)

@pytest.mark.parametrize('gate', ['completion', 'accepted', 'broken-database', 'missing-database'])
def test_completion_and_acceptance_gates_fail_closed(state, gate):
    if gate == 'completion': write(state.cycle/'principal/dipole-classroom-completion.json', b'finished')
    elif gate == 'accepted':
        with sqlite3.connect(state.run/'cycles.sqlite') as db:
            db.execute('INSERT INTO stages VALUES (?,?)', ('principal_output', 'isolated-remaining-preservation-cycle-00'))
    elif gate == 'missing-database':
        (state.run/'cycles.sqlite').unlink()
        state.kept.pop('cycles.sqlite')
    else: (state.run/'cycles.sqlite').write_bytes(b'not a database')
    if gate != 'missing-database': state.kept['cycles.sqlite'] = (state.run/'cycles.sqlite').read_bytes()
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    source_unchanged(state)

@pytest.mark.parametrize('state', ['cycle'], indirect=True)
def test_whole_cycle_refuses_recorded_response(state):
    write(state.cycle/'principal/session-response.json', b'recorded')
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    source_unchanged(state)

@pytest.mark.parametrize('gate', ['completion', 'accepted'])
def test_replay_rechecks_gates_after_first_item_is_archived(state, gate):
    result, _ = invoke(state, after=1)
    assert result.returncode != 0
    path, intent = intent_of(state)
    if gate == 'accepted':
        with sqlite3.connect(state.run/'cycles.sqlite') as db:
            db.execute('INSERT INTO stages VALUES (?,?)', ('principal_output', 'isolated-remaining-preservation-cycle-00'))
    else:
        cycle = state.cycle
        if state.mode == 'cycle':
            cycle = Path(next(item for item in intent['items'] if item['relative'] == 'execution/cycle-00')['destination'])
        write(cycle/'principal/dipole-classroom-completion.json', b'finished after interruption')
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    assert not documents(state, SCHEMAS[state.mode][1]) and path.exists()

@pytest.mark.parametrize('change', ['source', 'destination', 'both', 'missing', 'future-receipt'])
def test_changed_ambiguous_or_conflicting_replay_refuses_before_further_moves(state, change):
    result, _ = invoke(state, after=1)
    assert result.returncode != 0
    path, intent = intent_of(state)
    archived, pending = intent['items'][:2]
    destination, source = Path(archived['destination']), state.source/archived['relative']
    def mutate(target):
        if target.is_dir(): write(target/'unexpected-evidence', b'changed')
        else: target.write_bytes(b'changed')
    if change == 'source': mutate(state.source/pending['relative'])
    elif change == 'destination': mutate(destination)
    elif change == 'both':
        if destination.is_dir(): shutil.copytree(destination, source)
        else: write(source, destination.read_bytes())
    elif change == 'missing':
        # Missing evidence is simulated only inside this isolated fixture.
        if destination.is_dir(): shutil.rmtree(destination)
        else: destination.unlink()
    else:
        write(path.with_name(path.name.removesuffix('.intent.json')+'.move-1.json'),
              b'{"schema":"conflicting","intent_sha256":"wrong"}')
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    assert not documents(state, SCHEMAS[state.mode][1])

@pytest.mark.parametrize('kind', ['selected', 'nested', 'ancestor'])
def test_reparse_points_refuse_before_any_move(state, kind):
    outside = state.tmp/'outside'
    outside.mkdir()
    (outside/'sentinel').write_bytes(b'unchanged')
    if kind == 'selected':
        selected = state.source/next(iter(sorted(state.items)))
        selected.rename(state.tmp/'saved-selected')
        selected.symlink_to(outside, target_is_directory=True)
    elif kind == 'nested':
        parent = state.source/('principal/incoming-1' if state.mode == 'response' else 'execution/cycle-00')
        (parent/'linked-child').symlink_to(outside, target_is_directory=True)
    else:
        relocated = state.tmp/'relocated-run'
        state.run.rename(relocated)
        state.run.symlink_to(relocated, target_is_directory=True)
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    assert (outside/'sentinel').read_bytes() == b'unchanged'

@pytest.mark.parametrize('foreign', ['code-bound', 'other', 'malformed-completion'])
def test_shared_protocol_refuses_unfinished_or_unverifiable_foreign_intents(state, foreign):
    if foreign == 'code-bound': prefix, schema = 'superseded-code-bound-state-', 'FRANKIE_CODE_BOUND_STATE_INTENT_V1'
    else:
        mode = 'cycle' if state.mode == 'response' else 'response'
        prefix, schema = PREFIXES[mode], SCHEMAS[mode][0]
    path = state.day/(prefix+'foreign.intent.json')
    write(path, json.dumps(dict(schema=schema, run_directory=str(state.run))).encode())
    if foreign == 'malformed-completion':
        write(path.with_name(path.name.removesuffix('.intent.json')+'.json'), b'{"intent_sha256":"wrong"}')
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    source_unchanged(state)

def test_completed_replay_never_overwrites_receipts_or_moves_again(state):
    result, _ = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    assert_done(state)
    evidence = {p.name: p.read_bytes() for p in state.day.glob('*.json')}
    result, capture = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    assert not capture.exists()
    assert {p.name: p.read_bytes() for p in state.day.glob('*.json')} == evidence
    assert_done(state)

def test_changed_configuration_refuses_pending_intent(state):
    result, _ = invoke(state, after=1)
    assert result.returncode != 0
    intent_of(state)
    config = read(state.config)
    config['host_runtime']['boss_commit'] = 'c'*40
    write(state.config, json.dumps(config).encode())
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()

def test_shared_lock_refuses_second_helper_and_releases_when_holder_exits(state):
    import time
    ready, lock = state.tmp/'lock-ready', state.day/'code-bound-state.lock'
    prelude = f"""
$handle = [IO.File]::Open({quote(lock)}, [IO.FileMode]::OpenOrCreate,
    [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try {{
    [IO.File]::WriteAllText({quote(ready)}, 'ready')
    [Console]::ReadLine() | Out-Null
}} finally {{ $handle.Dispose() }}
"""
    holder = subprocess.Popen([state.pwsh, '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', prelude],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic()+15
        while not ready.exists() and time.monotonic() < deadline: time.sleep(0.02)
        assert ready.exists()
        result, capture = invoke(state)
        assert result.returncode != 0 and not capture.exists()
        source_unchanged(state)
    finally: holder.communicate('\n', timeout=15)
    result, _ = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    assert_done(state)


@pytest.mark.parametrize('change', ['destination', 'relative', 'duplicate', 'source-root'])
def test_replay_refuses_escaping_or_duplicate_intent_paths(state, change):
    result, _ = invoke(state, before=True)
    assert result.returncode != 0
    path, intent = intent_of(state)
    if change == 'destination':
        intent['items'][0]['destination'] = str(state.tmp/'outside-evidence')
    elif change == 'relative':
        intent['items'][0]['relative'] = '../outside-evidence'
    elif change == 'duplicate':
        intent['items'].append(intent['items'][0])
    else:
        intent['source_root'] = str(state.source)+'-sibling'
    write(path, json.dumps(intent).encode())
    result, capture = invoke(state)
    assert result.returncode != 0 and not capture.exists()
    source_unchanged(state)

def test_same_second_generations_keep_all_prior_evidence(state):
    result, _ = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    first = {p.name: p.read_bytes() for p in state.day.glob('*.json')}
    _, old = intent_of(state)
    archive = {str(p): p.read_bytes() for p in Path(old['superseded_root']).rglob('*') if p.is_file()}
    for relative, body in state.moved.items(): write(state.source/relative, body)
    result, _ = invoke(state)
    assert result.returncode == 0, result.stdout+result.stderr
    assert len(documents(state, SCHEMAS[state.mode][0])) == 2
    assert len(documents(state, SCHEMAS[state.mode][1])) == 2
    assert all((state.day/name).read_bytes() == body for name, body in first.items())
    assert all(Path(name).read_bytes() == body for name, body in archive.items())
    kept_unchanged(state)
