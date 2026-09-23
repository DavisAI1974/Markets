"""Static delivery and scope contracts for durable host-state preservation.

The real PowerShell behavior runs in tests/test_host_state_preservation.py.
These tests preserve the existing host variable, stale selection, identity,
kept evidence and dispatch workflow restrictions while checking the durable
intent/manifest/receipt protocol carried verbatim to the host.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
SCRIPT = ROOT / 'deploy/aws/host/frankie_host_supersede_code_bound_state.ps1'
WORKFLOW = ROOT / '.github/workflows/frankie_host_supersede_code_bound_state.yml'
JOURNAL = ROOT / 'research/kalshi/frankie_boss/c15_journal.py'
REQUIRED_VARIABLES = ('Day', 'RunRoot', 'ToolsRoot', 'Python')
OPTIONAL_VARIABLES = ('CycleIndex', 'OldCommit')
SCHEMA = 'FRANKIE_CODE_BOUND_STATE_SUPERSEDED_V1'
TEXT = SCRIPT.read_text()
LINES = TEXT.splitlines()
# Comments explain the why; the tests pin the code, so drop comment lines before looking for verbs.
CODE = '\n'.join(line for line in LINES if not line.lstrip().startswith('#'))
STALE_BLOCK = CODE.split("if ($stored -ne 'absent' -and $stored -ne $head) {\n", 1)[1].split('\n} elseif', 1)[0]
RECEIPT = re.search(r'\$receipt = \[ordered\]@\{(.*?)^\s*\}', TEXT, re.S | re.M).group(1)
INTENT = re.search(r'\$intent = \[ordered\]@\{(.*?)^\s*\}', TEXT, re.S | re.M).group(1)
RUNTIME = CODE[CODE.index("foreach ($required in "):]
COMPLETION = CODE.split('function Complete-StateIntent', 1)[1].split("foreach ($required in ", 1)[0]
EMBEDDED_PYTHON = TEXT.split('$code = @"\n', 1)[1].split('\n"@', 1)[0]

# The eight items the 2026-09-20 brief named (the first revision of the script).
ORIGINAL_EIGHT = {
    'host-identity.c15.json', 'initialization.c15.json', 'training.sqlite', 'training-witnesses',
    'host-preparation.c15.json', 'host-context-cache.c15.json', 'actual-critic-request.json',
    'host-ready-*.c15.json',
}
# Added after pipeline run 35511984264 refused on execution-identity (see the script header).
ADDED_AFTER_35511984264 = {'execution-identity.c15.json', 'host-service.c15.json', 'request-plan.c15.json'}
KEPT_ITEMS = ('host-instance.c15.json', 'native-host-runtime.json')
OLD, HEAD = 'a' * 40, 'b' * 40


def _index(needle, text=CODE):
    position = text.find(needle)
    assert position >= 0, f'{needle!r} not in script'
    return position


def _journal():
    # The package __init__ imports torch. c15_journal and causal_packet are stdlib only and
    # c15_journal already falls back to a flat import, so use that path rather than the package.
    sys.path.insert(0, str(JOURNAL.parent))
    return importlib.import_module('c15_journal')


# --- variables ---------------------------------------------------------------------------------

def test_the_script_refuses_a_variable_the_sender_did_not_supply():
    loop = re.search(r"foreach \(\$required in (.+?)\) \{", CODE).group(1)
    assert set(re.findall(r"'([A-Za-z]+)'", loop)) == set(REQUIRED_VARIABLES)
    assert "-like 'HOST_*'" in CODE          # an unfilled placeholder is refused, never used as a path
    assert 'throw "$required was not supplied by ssm_run_ps1.py --set' in CODE


def test_cycle_index_defaults_to_the_first_cycle_and_is_refused_unless_two_digits():
    assert "if (-not (Get-Variable CycleIndex -ErrorAction SilentlyContinue)) { $CycleIndex = '00' }" in CODE
    assert """if ($CycleIndex -notmatch '^\\d{2}$') { throw "CycleIndex must be two digits""" in CODE
    # Validate before either recovery or the fresh selection path can run.
    assert _index("-notmatch '^\\d{2}$'", RUNTIME) < _index('Complete-StateIntent $unfinished[0]', RUNTIME)
    assert _index("-notmatch '^\\d{2}$'", RUNTIME) < _index("'execution/cycle-' + $CycleIndex", RUNTIME)


def test_every_error_stops_the_script_so_a_failed_move_never_continues_to_the_next_item():
    assert re.search(r"^\$ErrorActionPreference = 'Stop'$", CODE, re.M)
    assert "$ErrorActionPreference = 'Continue'" not in CODE


def test_the_sender_renders_the_variables_this_script_requires():
    sys.path.insert(0, str(ROOT / 'deploy/aws'))
    import ssm_run_ps1

    names = REQUIRED_VARIABLES + OPTIONAL_VARIABLES
    rendered = ssm_run_ps1.preamble([f'{name}=value-{index}' for index, name in enumerate(names)])
    for name in names:
        assert f'${name} = ' in rendered
    assert rendered.count('\n') == len(names)
    with pytest.raises(SystemExit):                     # no quoting logic: a quote is refused
        ssm_run_ps1.preamble(["RunRoot=D:\\it's"])


# --- what travels ------------------------------------------------------------------------------

def test_no_path_literal_and_no_credential_travels_in_the_sent_script():
    assert not re.search(r'[A-Za-z]:[\\/]', TEXT), 'a drive-letter path is baked into a sent script'
    for word in ('secret', 'api_key', 'password', 'AWS_ACCESS', 'bearer '):
        assert word.lower() not in TEXT.lower()
    # Every path the script touches is built from the supplied variables or the configuration.
    for root in ('$dayDirectory = Join-Path $RunRoot $Day',
                 "$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'",
                 '$runDirectory = $cfg.run_directory'):
        assert root in CODE, root


# --- nothing is deleted ------------------------------------------------------------------------

@pytest.mark.parametrize('verb', ['Remove-Item', '.Delete(', 'Clear-Content', 'Clear-Item', '[IO.File]::Delete',
                                  '[IO.Directory]::Delete', 'Out-File', 'Copy-Item', 'Rename-Item', 'Add-Content'])
def test_no_delete_or_stray_write_verb_appears_anywhere_in_the_script(verb):
    assert verb.lower() not in TEXT.lower(), f'{verb} in the supersede script'


@pytest.mark.parametrize('word', ['rmdir', 'del', 'rm', 'rd', 'erase', 'unlink', 'remove'])
def test_no_delete_command_word_appears_anywhere_in_the_script(word):
    # Word-bounded so 'delivered' and 'DELETED' (in the prose promising nothing is deleted) do not match.
    assert not re.search(rf'\b{word}\b', TEXT, re.I), f'{word} in the supersede script'



def test_exactly_one_move_item_by_literal_path_and_the_move_is_verified_both_ways():
    moves = [line for line in LINES if 'Move-Item' in line]
    assert len(moves) == 1, moves
    assert moves[0].strip() == 'Move-Item -LiteralPath $source -Destination $destination'
    assert '-Force' not in moves[0]
    before, after = COMPLETION.split('Move-Item -LiteralPath $source -Destination $destination')
    assert 'Assert-StateManifest $source $entry.manifest' in before
    assert "if (Test-Path -LiteralPath $destination) { throw 'destination already exists' }" in before
    assert 'if (Test-Path -LiteralPath $source) { throw ("move left the source in place: "' in after
    assert 'if (-not (Test-Path -LiteralPath $destination)) { throw ("move lost the item: "' in after
    assert _index('Assert-StateManifest $destination $entry.manifest', after) < _index('Write-StateJson $moveReceiptPath', after)
    # Stream hashes and complete manifests precede the durable intent and execution.
    assert '[IO.File]::OpenRead((Assert-StatePath $Path))' in CODE
    assert '$hasher.ComputeHash($stream)' in CODE
    assert _index('$manifest = @(Get-StateManifest $source)', RUNTIME) < _index('Write-StateJson $intentPath $intent', RUNTIME)
    assert _index('Write-StateJson $intentPath $intent', RUNTIME) < _index('Complete-StateIntent $intentPath', RUNTIME)


def test_the_only_other_writes_are_the_destination_directory_and_the_receipt():
    creates = [line for line in LINES if 'New-Item' in line]
    assert len(creates) == 1 and '-ItemType Directory' in creates[0], creates
    assert '-Path $parent' in creates[0]
    assert '$parent = Assert-StatePath (Split-Path $destination -Parent)' in COMPLETION
    assert 'Set-Content' not in CODE
    writer = CODE.split('function Write-StateJson', 1)[1].split('function Assert-StateManifest', 1)[0]
    assert '[IO.FileMode]::CreateNew' in writer
    assert '[IO.FileShare]::None' in writer
    assert '$stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true)' in writer
    assert 'finally { $stream.Dispose() }' in writer
    calls = [line.strip() for line in CODE.splitlines() if 'Write-StateJson ' in line and not line.startswith('function ')]
    assert len(calls) == 3, calls
    for path in ('$intentPath $intent', '$moveReceiptPath $moveReceipt', '$receiptPath $receipt'):
        assert any('Write-StateJson ' + path in line for line in calls), path
    assert '>' not in CODE.replace('2>&1', ''), 'a redirection writes a file'

# --- the code-bound items and the two kept -----------------------------------------------------

def test_the_enumerated_candidates_are_the_original_eight_plus_the_three_named_additions():
    base = re.search(r"^\s*\$candidates = @\((.*)\)$", STALE_BLOCK, re.M).group(1)
    base = re.findall(r"'([a-z0-9\-.]+)'", base)
    identities = re.findall(r"^\s*if \(\$(\w+) -ne 'absent' -and \$\1 -ne \$head\) \{ \$candidates \+= '([a-z0-9\-./]+)' \}$",
                            STALE_BLOCK, re.M)
    cycle_level = re.findall(r"\(\$cycleRelative \+ '/([a-z0-9\-.]+)'\)", STALE_BLOCK)
    globbed = re.findall(r"Get-ChildItem -LiteralPath \(Assert-StatePath \$cycle\) -Filter '([a-z0-9\-*.]+)' \| ForEach-Object \{ \$candidates \+= "
                         r"\(\$cycleRelative \+ '/' \+ \$_\.Name\) \}", STALE_BLOCK)
    assert base == ['initialization.c15.json', 'training.sqlite', 'training-witnesses'], base
    assert identities == [('hostIdentity', 'host-identity.c15.json'),
                          ('executionIdentity', 'execution/execution-identity.c15.json')], identities
    assert cycle_level == ['host-preparation.c15.json', 'host-service.c15.json', 'host-context-cache.c15.json',
                           'request-plan.c15.json', 'actual-critic-request.json'], cycle_level
    assert globbed == ['host-ready-*.c15.json']
    names = set(base) | {item.rsplit('/', 1)[-1] for _, item in identities} | set(cycle_level) | set(globbed)
    assert ORIGINAL_EIGHT <= names, ORIGINAL_EIGHT - names
    assert names == ORIGINAL_EIGHT | ADDED_AFTER_35511984264, names - ORIGINAL_EIGHT - ADDED_AFTER_35511984264
    assert len(base) + len(identities) + len(cycle_level) + len(globbed) == 11


def test_an_identity_record_is_moved_only_when_it_is_the_stale_one():
    # A fresh record written by a refused run at the current commit is what the next run re-saves
    # byte for byte, so moving it would gain nothing and lose evidence.
    assert "if ($hostIdentity -ne 'absent' -and $hostIdentity -ne $head) { $candidates += 'host-identity.c15.json' }" in STALE_BLOCK
    assert ("if ($executionIdentity -ne 'absent' -and $executionIdentity -ne $head) "
            "{ $candidates += 'execution/execution-identity.c15.json' }") in STALE_BLOCK
    assert "'host-identity.c15.json'" not in STALE_BLOCK.split('$candidates += @(', 1)[1]   # never unconditional


def test_the_candidate_list_is_grown_only_inside_the_stale_branch():
    assert CODE.count('$candidates = @()') == 1                 # empty unless something is stale
    assert CODE.count('$candidates = @(') == 2                  # the empty list + the base list
    assert CODE.count('$candidates +=') == STALE_BLOCK.count('$candidates +=') == 5
    assert 'foreach ($relative in $candidates) {' in CODE


def test_the_catch_all_scan_only_moves_c15_records_that_carry_the_old_commit_literal():
    # Scoped, never recursive: another cycle's completion.c15.json carries boss_commit lawfully.
    assert '-Recurse' not in CODE
    assert "foreach ($scanRoot in @($runDirectory, (Join-Path $runDirectory 'execution'), $cycle)) {" in STALE_BLOCK
    assert ("Get-ChildItem -LiteralPath $scanRoot -File -Filter '*.c15.json' | Where-Object { -not ($_.Attributes -band $reparse) } "
            "| ForEach-Object {") in STALE_BLOCK
    assert '$reparse = [IO.FileAttributes]::ReparsePoint' in STALE_BLOCK
    assert "if (-not (Test-StateWithin $_.FullName $root)) { throw 'scan escaped run directory' }" in STALE_BLOCK
    assert '$null = Assert-StatePath $scanRoot' in STALE_BLOCK
    # Kept records and chained journals are excluded by name before the literal is even looked for.
    assert ("if ($name -eq 'host-instance.c15.json' -or $name -like 'verified-*' -or $name -eq 'genesis.c15.json' "
            "-or $name -like 'append-*') { return }") in STALE_BLOCK
    assert _index("$name -eq 'host-instance.c15.json'", STALE_BLOCK) < _index('-SimpleMatch $stored', STALE_BLOCK)
    assert 'if (Select-String -LiteralPath $_.FullName -SimpleMatch $stored -Quiet) {' in STALE_BLOCK
    assert 'if ($candidates -notcontains $relative) {' in STALE_BLOCK
    assert "$relative = $_.FullName.Substring($root.Length).TrimStart('\\', '/').Replace('\\', '/')" in STALE_BLOCK
    assert '$root = Assert-StatePath $runDirectory' in STALE_BLOCK
    # Inside the stale branch the literal is a 40-hex OLD commit, never 'absent' nor the current one
    # (Select-String on either of those would sweep live records).
    assert _index('$candidates = @(\'initialization', STALE_BLOCK) < _index('-SimpleMatch $stored', STALE_BLOCK)
    assert "if ($value -ne 'absent' -and $value -notmatch '^[0-9a-f]{40}$') { throw" in CODE


def test_the_cycle_bound_items_live_under_the_requested_cycle_only():
    assert "$cycleRelative = 'execution/cycle-' + $CycleIndex" in STALE_BLOCK
    assert '$cycle = Join-Path $runDirectory $cycleRelative' in STALE_BLOCK
    assert 'if (Test-Path $cycle) {' in STALE_BLOCK
    assert STALE_BLOCK.count("($cycleRelative + '/") == 6          # five names + the host-ready glob
    assert 'cycle-*' not in STALE_BLOCK and 'cycle-0' not in STALE_BLOCK
    assert "throw 'intent selects kept or other-cycle evidence'" in COMPLETION


@pytest.mark.parametrize('kept', KEPT_ITEMS)
def test_the_data_bound_items_are_never_enumerated_and_the_receipt_says_they_were_kept(kept):
    # A kept name may appear in the stale branch only on the scan's exclusion line, never near $candidates.
    for line in STALE_BLOCK.splitlines():
        if kept in line:
            assert '{ return }' in line and '$candidates' not in line, line
    kept_line = re.search(r"^\s*kept\s*=\s*@\((.*)\)$", RECEIPT, re.M).group(1)
    assert f"'{kept}'" in kept_line
    # The host-ready glob is prefix-anchored, so it cannot match a kept name.
    assert not re.fullmatch(r'host-ready-.*\.c15\.json', kept)



def test_host_instance_must_be_present_and_is_only_ever_tested_never_moved():
    guard = "if (-not (Test-Path (Join-Path $runDirectory 'host-instance.c15.json'))) { throw 'refusing: host-instance.c15.json absent"
    assert guard in RUNTIME
    assert "$null = Assert-StatePath (Join-Path $runDirectory 'host-instance.c15.json')" in RUNTIME
    mentions = [line for line in CODE.splitlines() if 'host-instance.c15.json' in line]
    assert any('kept' in line for line in mentions)
    assert any('{ return }' in line for line in mentions)
    assert not any('$candidates' in line or 'Move-Item' in line for line in mentions)
    assert _index(guard, RUNTIME) < _index('Complete-StateIntent $unfinished[0]', RUNTIME)
    assert "$relative -in @('host-instance.c15.json', 'native-host-runtime.json')" in COMPLETION

# --- the destination is a sibling of the run directory -----------------------------------------


def test_the_destination_is_built_from_the_run_directory_parent_never_inside_the_run_directory():
    assert ("$target = Join-Path (Join-Path (Split-Path $runDirectory -Parent) 'superseded') "
            "($runName + '-' + $stamp + '-code-' + $stored)") in RUNTIME
    assert '$runName = Split-Path $runDirectory -Leaf' in RUNTIME
    assert '$destination = Assert-StatePath (Join-Path $target $relative)' in RUNTIME
    assert "Join-Path $runDirectory 'superseded'" not in TEXT
    assert "throw 'archive must be outside run directory'" in RUNTIME
    assert "throw 'candidate escaped run directory'" in RUNTIME
    assert "throw 'candidate destination escaped archive'" in RUNTIME
    assert "throw 'intent destination escaped the sibling archive'" in COMPLETION
    assert "throw 'intent path escaped its root'" in COMPLETION
    boundary = CODE.split('function Test-StateWithin', 1)[1].split('function Assert-StatePath', 1)[0]
    assert '$base + [IO.Path]::DirectorySeparatorChar' in boundary
    assert '[StringComparison]::Ordinal' in boundary
    assert '[StringComparison]::OrdinalIgnoreCase' in boundary

def test_the_superseded_folder_is_stamped_with_the_stale_commit_so_two_supersedes_never_collide():
    assert "$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N')" in RUNTIME
    assert "if (Test-Path -LiteralPath $target) { throw 'archive destination already exists' }" in RUNTIME
    assert "'-code-' + $stored" in CODE
    # $stored is a 40-hex commit or the literal 'absent' (both safe folder-name fragments), never free text.
    assert "$stored = 'absent'" in CODE
    assert "if ($value -ne 'absent' -and $value -ne $head) { $stored = $value; break }" in CODE


# --- the refusal guards and the nothing-stale branches -----------------------------------------

def test_refuses_unless_the_tools_head_is_the_configurations_boss_commit():
    assert '$git = (Get-Command git -ErrorAction Stop).Source' in CODE
    assert '$head = (& $git -C $ToolsRoot rev-parse HEAD).Trim()' in CODE
    assert ('if ($head -ne $cfg.host_runtime.boss_commit) { throw ("refusing: tools HEAD " + $head + '
            '" is not the configuration\'s boss_commit " + $cfg.host_runtime.boss_commit) }') in CODE


def test_nothing_moves_when_the_stored_commit_equals_head_or_no_identity_is_stored():
    # The first revision threw here; this revision is re-runnable: the candidate list stays empty and a
    # receipt with moved = [] is still written, so a second dispatch is a no-op with evidence.
    assert "} elseif ($stored -eq $head) {\n    Write-Output 'stored identity already matches the current commit; nothing is stale'" in CODE
    assert "} else {\n    Write-Output 'no stored identity found'" in CODE
    # A fresh identity at HEAD means every other record was written by HEAD too: no throw there.
    assert 'throw' not in CODE.split("} elseif ($stored -eq $head) {", 1)[1].split('} else {', 1)[0]
    # No identity at all: leftover checkpoint-bound records cannot be judged, so the script refuses
    # to report success while they remain (code review, Important) unless OldCommit names them stale.
    absent = RUNTIME.split("} else {\n    Write-Output 'no stored identity found'", 1)[1].split('$stamp =', 1)[0]
    assert 'throw ("refusing: no identity record to judge by, but checkpoint-bound records are present: "' in absent
    assert "Write-Output 'nothing is stale'" in absent
    assert "if ($stored -eq 'absent' -and ($hostIdentity -eq $head -or $executionIdentity -eq $head)) { $stored = $head }" in CODE
    # The operator override is pinned to 40 hex, must differ from HEAD, and may not contradict a stored identity.
    assert "if ($OldCommit -notmatch '^[0-9a-f]{40}$') { throw 'OldCommit must be a full 40-hex commit' }" in CODE
    assert "if ($OldCommit -eq $head) { throw" in CODE
    assert "if ($stored -ne 'absent' -and $stored -ne $OldCommit) { throw" in CODE



def test_every_refusal_fires_before_anything_is_moved():
    # Helpers are defined before the main program; execution order is determined
    # by their calls, not the lexical position of the Move-Item function body.
    recovery = _index('Complete-StateIntent $unfinished[0]', RUNTIME)
    for guard in ('throw "$required was not supplied', 'throw "CycleIndex must be two digits',
                  'throw "no run configuration for $Day', 'throw "run_directory absent',
                  "throw 'refusing: run_directory carries a quote or newline'",
                  'throw ("refusing: tools HEAD', "throw 'refusing: host-instance.c15.json absent"):
        assert _index(guard, RUNTIME) < recovery, guard
    intent_write = _index('Write-StateJson $intentPath $intent', RUNTIME)
    for guard in ('throw ("could not read the identity records', 'throw ("could not read a stored boss_commit',
                  "throw 'OldCommit must be a full 40-hex commit'",
                  'throw ("refusing: no identity record to judge by'):
        assert _index(guard, RUNTIME) < intent_write, guard
    assert _index("$candidates = @('initialization", RUNTIME) < intent_write
    for guard in ("throw 'invalid or duplicate intent relative path'",
                  "throw 'intent selects unapproved evidence'", "throw 'intent lacks a complete manifest'",
                  'throw ("ambiguous or missing preserved item: '):
        assert _index(guard, COMPLETION) < _index('Move-Item', COMPLETION), guard

# --- the embedded identity reader --------------------------------------------------------------

def test_the_embedded_python_only_reads_and_prints_one_line_per_identity_record():
    rendered = EMBEDDED_PYTHON.replace('$ToolsRoot', '/tools').replace('$runDirectory', '/run')
    assert '$' not in rendered, [line for line in rendered.splitlines() if '$' in line]
    compile(rendered, str(SCRIPT), 'exec')
    assert 'from research.kalshi.frankie_boss.c15_journal import unpack' in rendered
    assert rendered.count('.read_bytes()') == 1
    assert "print(pick(unpack(json.loads(path.read_bytes()))) if path.exists() else 'absent')" in rendered
    for writer in ('open(', 'write', 'unlink', 'rename', 'replace(', 'shutil', 'os.', 'subprocess'):
        assert writer not in rendered, writer
    assert "(run / 'host-identity.c15.json', lambda v: v['configuration']['host_runtime']['boss_commit'])" in rendered
    assert "(run / 'execution' / 'execution-identity.c15.json', lambda v: v['boss_commit'])" in rendered
    # PowerShell keeps exactly the last two lines, one per record, in that order.
    assert '$identities = @(& $Python -c $code 2>&1 | Select-Object -Last 2 | ForEach-Object { $_.ToString().Trim() })' in CODE
    assert 'if ($LASTEXITCODE -ne 0 -or $identities.Count -ne 2) { throw' in CODE
    assert '$hostIdentity = $identities[0]; $executionIdentity = $identities[1]' in CODE
    assert "$env:PYTHONDONTWRITEBYTECODE = '1'; $env:PYTHONPATH = $ToolsRoot" in CODE


def _run_reader(tmp_path, host_commit, execution_commit):
    journal = _journal()
    tools = tmp_path / 'tools'
    package = tools / 'research/kalshi/frankie_boss'
    package.mkdir(parents=True)
    for directory in (tools / 'research', tools / 'research/kalshi', package):
        (directory / '__init__.py').write_text('')
    # The stub package re-exports the REAL unpack so the c15 tagged-list shape is exercised.
    (package / 'c15_journal.py').write_text(
        f'import sys; sys.path.insert(0, {str(JOURNAL.parent)!r})\n'
        'import c15_journal as real\n'
        'unpack = real.unpack\n')
    run = tmp_path / 'run'
    (run / 'execution').mkdir(parents=True)
    if host_commit:
        record = dict(configuration=dict(host_runtime=dict(boss_commit=host_commit)), code={})
        (run / 'host-identity.c15.json').write_bytes(journal.canonical_bytes(journal.pack(record)))
    if execution_commit:
        record = dict(schema='x', boss_commit=execution_commit)
        (run / 'execution/execution-identity.c15.json').write_bytes(journal.canonical_bytes(journal.pack(record)))
    rendered = EMBEDDED_PYTHON.replace('$ToolsRoot', str(tools)).replace('$runDirectory', str(run))
    result = subprocess.run([sys.executable, '-c', rendered], capture_output=True, text=True, cwd=tmp_path,
                            env={'PATH': '', 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stderr
    return (result.stdout + result.stderr).splitlines()[-2:]


@pytest.mark.parametrize('host_commit, execution_commit, expected', [
    (OLD, None, [OLD, 'absent']),          # the ordinary stale run directory
    (HEAD, OLD, [HEAD, OLD]),              # pipeline 35511984264: a fresh host-identity masking a stale execution-identity
    (None, None, ['absent', 'absent']),    # nothing retained: nothing is stale
    (None, OLD, ['absent', OLD]),          # host-identity already superseded, execution-identity not yet
])
def test_the_identity_reader_reports_each_record_on_its_own_line_through_the_real_unpack(tmp_path, host_commit, execution_commit, expected):
    assert _run_reader(tmp_path, host_commit, execution_commit) == expected


# --- the receipt -------------------------------------------------------------------------------


def test_the_receipt_carries_the_schema_and_every_field_a_reader_needs_to_undo_the_move():
    assert re.search(rf"^\s*schema\s*=\s*'{SCHEMA}'$", RECEIPT, re.M)
    declared = re.findall(r'^\s*([a-z_0-9]+)\s*=', RECEIPT, re.M)
    assert declared == ['schema', 'day', 'run_id', 'run_directory', 'stored_boss_commit', 'current_boss_commit',
                        'stale', 'superseded_root', 'kept', 'moved', 'at', 'intent_path', 'intent_sha256'], declared
    assert 'superseded_root     = $(if ($moved.Count -gt 0) { $target } else { $null })' in RECEIPT
    per_item = TEXT.split('$plan += [ordered]@{', 1)[1].split('}', 1)[0]
    assert re.findall(r'([a-z_0-9]+) =', per_item) == [
        'relative', 'destination', 'sha256', 'bytes', 'mtime_utc', 'manifest']
    assert '$moved += $entry' in COMPLETION
    assert 'intent_sha256 = $intentHash; item = $entry' in COMPLETION
    assert "schema = 'FRANKIE_CODE_BOUND_STATE_MOVE_V1'" in COMPLETION


def test_the_receipt_is_written_into_the_day_directory_and_echoed_last():
    assert "$intentPath = Join-Path $dayDirectory ('superseded-code-bound-state-' + $stamp + '.intent.json')" in RUNTIME
    assert "$stem = $IntentPath.Substring(0, $IntentPath.Length - '.intent.json'.Length)" in COMPLETION
    assert "$receiptPath = $stem + '.json'" in COMPLETION
    assert "$moveReceiptPath = $stem + '.move-' + $index + '.json'" in COMPLETION
    assert 'Write-StateJson $receiptPath $receipt' in COMPLETION
    assert _index('Write-StateJson $receiptPath $receipt', COMPLETION) < _index("Write-Output ('RECEIPT '", COMPLETION)
    assert sum('RECEIPT ' in line for line in LINES) == 1

def test_a_rerun_skips_absent_items_instead_of_failing():
    assert 'if (-not (Test-Path -LiteralPath $source)) { Write-Output ("  absent, skipped: " + $relative); continue }' in CODE
    assert '$moved = @()' in CODE



def test_durable_intent_contains_the_complete_plan_and_recovery_precedes_identity_reads():
    for field in ('schema', 'day', 'run_id', 'run_directory', 'cycle_index',
                  'stored_boss_commit', 'current_boss_commit', 'superseded_root', 'items'):
        assert re.search(rf'^\s*{field}\s*=', INTENT, re.M), field
    assert "schema = 'FRANKIE_CODE_BOUND_STATE_INTENT_V1'" in INTENT
    assert 'items = @($plan)' in INTENT
    assert _index('Complete-StateIntent $unfinished[0]', RUNTIME) < _index('$identities =', RUNTIME)
    assert "throw 'multiple unfinished preservation intents require reconciliation'" in RUNTIME
    assert '$done.intent_sha256 -cne (Get-StateHash $file.FullName)' in RUNTIME
    assert "throw 'completion receipt does not bind the retained intent'" in RUNTIME


def test_manifests_walk_every_child_and_each_operation_refuses_linked_ancestors():
    path_guard = CODE.split('function Assert-StatePath', 1)[1].split('function Get-StateHash', 1)[0]
    assert 'while ($cursor)' in path_guard
    assert '[IO.FileAttributes]::ReparsePoint' in path_guard
    assert '$parent = [IO.Path]::GetDirectoryName($cursor)' in path_guard
    manifest = CODE.split('function Get-StateManifest', 1)[1].split('function Write-StateJson', 1)[0]
    assert '$current = Assert-StatePath ($pending.Pop())' in manifest
    assert 'Get-ChildItem -LiteralPath $current -Force' in manifest
    assert "kind = 'directory'" in manifest and "kind = 'file'" in manifest
    assert 'sha256 = (Get-StateHash $current); bytes = $item.Length' in manifest
    assert "manifest escaped selected item" in manifest


def test_run_lock_serializes_recovery_and_new_intent_creation():
    assert "$lockPath = Assert-StatePath (Join-Path $dayDirectory 'code-bound-state.lock')" in RUNTIME
    assert '$stateLock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)' in RUNTIME
    assert _index('$stateLock =', RUNTIME) < _index('$unfinished = @()', RUNTIME)
    assert RUNTIME.rstrip().endswith('} finally { $stateLock.Dispose() }')


# --- the workflow ------------------------------------------------------------------------------

def test_the_workflow_supplies_exactly_the_variables_the_script_requires():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    steps = workflow['jobs']['supersede']['steps']
    run = next(step['run'] for step in steps if 'frankie_host_supersede_code_bound_state.ps1' in step.get('run', ''))
    supplied = set(re.findall(r'--set "([A-Za-z]+)=', run))
    assert supplied == set(REQUIRED_VARIABLES) | set(OPTIONAL_VARIABLES), supplied
    assert '--script deploy/aws/host/frankie_host_supersede_code_bound_state.ps1' in run
    assert SCRIPT.is_file()


def test_the_workflow_is_dispatch_only_read_only_and_pinned_to_the_one_repository():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    assert workflow['permissions'] == {'contents': 'read'}
    assert set(workflow[True]) == {'workflow_dispatch'}          # yaml reads the `on:` key as True
    assert set(workflow[True]['workflow_dispatch']['inputs']) == {'instance', 'day', 'run_root', 'tools_root', 'python',
                                                                  'cycle_index', 'old_commit'}
    # Inputs reach the shell through env, never by expression interpolation into run: (audit, Medium).
    step = next(s for s in workflow['jobs']['supersede']['steps'] if 'frankie_host_supersede_code_bound_state.ps1' in s.get('run', ''))
    assert '${{' not in step['run']
    assert set(step['env']) == {'INSTANCE', 'DAY', 'RUN_ROOT', 'TOOLS_ROOT', 'HOST_PYTHON', 'CYCLE_INDEX', 'OLD_COMMIT'}
    assert workflow['jobs']['supersede']['if'] == "github.repository == 'DavisAI1974/Markets'"
    assert workflow[True]['workflow_dispatch']['inputs']['cycle_index']['default'] == '00'   # matches the script default
    for step in workflow['jobs']['supersede']['steps']:
        if 'uses' in step:
            assert re.fullmatch(r'[\w.-]+/[\w.-]+@[0-9a-f]{40}', step['uses']), step['uses']   # actions pinned by sha
