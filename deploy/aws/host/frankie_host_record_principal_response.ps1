# Record Root's actual Frankie response on the native host (2026-09-20 20:55Z).
#
# Why: Root ran operations/record_actual_frankie_response.py on his own machine, but the recorder
# writes into the retained run directory under the run's lock, so the record must be made ON the
# host. This delivers Root's three files (the response, the host attestation, the host session
# record the attestation pins) from a presigned staging (URLs signed and masked by the workflow,
# never printed here), verifies each by sha256 and bytes, places the session record where the
# attestation says it lives (derived from the configuration's run directory; the attestation's
# host_record.path must name exactly that file), runs the recorder from the host tools checkout,
# and writes one receipt into the day directory. Nothing is deleted or written over: an existing
# session-response.json is reported and left alone, an existing session record with different
# bytes refuses. $Day, $RunRoot, $ToolsRoot, $Python, $CycleIndex, the three Url/Sha256/Bytes triples
# and $SourceRef arrive from ssm_run_ps1.py --set; no path literal here.
$ErrorActionPreference = 'Stop'
foreach ($required in 'Day', 'RunRoot', 'ToolsRoot', 'Python', 'CycleIndex', 'SourceRef',
        'ResponseUrl', 'ResponseSha256', 'ResponseBytes',
        'AttestationUrl', 'AttestationSha256', 'AttestationBytes',
        'RecordUrl', 'RecordSha256', 'RecordBytes') {
    $value = Get-Variable -Name $required -ValueOnly -ErrorAction SilentlyContinue
    if (-not $value -or $value -like 'HOST_*') { throw "$required was not supplied by ssm_run_ps1.py --set (value: '$value')" }
}
if ($CycleIndex -notmatch '^\d{2}$') { throw "CycleIndex must be two digits (value: '$CycleIndex')" }
foreach ($name in 'ResponseSha256', 'AttestationSha256', 'RecordSha256') {
    if ((Get-Variable -Name $name -ValueOnly) -notmatch '^[0-9a-f]{64}$') { throw "$name must be 64 lowercase hex" }
}
foreach ($name in 'ResponseBytes', 'AttestationBytes', 'RecordBytes') {
    if ((Get-Variable -Name $name -ValueOnly) -notmatch '^\d+$') { throw "$name must be digits" }
}
$dayDirectory = Join-Path $RunRoot $Day
$cfgPath = Join-Path $dayDirectory 'actual-host-configuration.json'
if (-not (Test-Path $cfgPath)) { throw "no run configuration for $Day at $cfgPath" }
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
$sha = [System.Security.Cryptography.SHA256]::Create()
function Digest([string]$path) { ([BitConverter]::ToString($script:sha.ComputeHash([IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLower() }
function Normal([string]$path) { ($path -replace '\\', '/').TrimEnd('/').ToLowerInvariant() }
$cfgSha = Digest $cfgPath
$run = $cfg.run_directory
if (-not $run -or -not (Test-Path $run)) { throw ("run directory absent: " + $run) }
$principal = Join-Path (Join-Path (Join-Path $run 'execution') ('cycle-' + $CycleIndex)) 'principal'
$requestPath = Join-Path $principal 'session-request.json'
$responsePath = Join-Path $principal 'session-response.json'
if (-not (Test-Path $requestPath)) { throw ("no durable principal request for cycle " + $CycleIndex + " at " + $requestPath + "; recording cannot precede it") }
Write-Output ("configuration " + $cfgPath + " sha256=" + $cfgSha)
Write-Output ("principal directory " + $principal)
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
if (Test-Path $responsePath) {
    Write-Output ("ALREADY_RECORDED session-response.json present, bytes=" + (Get-Item $responsePath).Length + " sha256=" + (Digest $responsePath) + "; nothing written")
    exit 0
}
$incoming = Join-Path $principal ('incoming-' + $stamp)
if (Test-Path $incoming) { throw ("incoming path already exists: " + $incoming) }
New-Item -ItemType Directory -Path $incoming | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Fetch([string]$url, [string]$target, [string]$expectedSha, [string]$expectedBytes, [string]$label) {
    $previous = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing } finally { $ProgressPreference = $previous }
    if (-not (Test-Path $target)) { throw ($label + ': download produced no file') }
    $got = Get-Item $target
    $gotDigest = Digest $target
    if ($got.Length -ne [int64]$expectedBytes -or $gotDigest -ne $expectedSha) {
        throw ($label + " differs from the declaration (" + $got.Length + " bytes, sha256 " + $gotDigest + " vs " + $expectedBytes + " " + $expectedSha + "); left in " + $incoming)
    }
    Write-Output ("delivered " + $label + " bytes=" + $got.Length + " sha256=" + $gotDigest)
}
$responseFile = Join-Path $incoming 'response.json'
$attestationFile = Join-Path $incoming 'host-attestation.json'
$recordFile = Join-Path $incoming 'host-session-record.json'
Fetch $ResponseUrl $responseFile $ResponseSha256 $ResponseBytes 'response'
Fetch $AttestationUrl $attestationFile $AttestationSha256 $AttestationBytes 'host attestation'
Fetch $RecordUrl $recordFile $RecordSha256 $RecordBytes 'host session record'
# The attestation pins the session record by path, bytes and sha256; the recorder reads that path on
# THIS machine, so the record is placed beside the request and the attestation must name that file.
$attestation = Get-Content $attestationFile -Raw | ConvertFrom-Json
$recordTarget = Join-Path $principal 'host-session-record.json'
$pinned = $attestation.host_record
if (-not $pinned -or -not $pinned.path -or -not $pinned.sha256) { throw 'the attestation carries no host_record {path, bytes, sha256}' }
$attestationPathRewrittenFrom = $null
if ((Normal $pinned.path) -ne (Normal $recordTarget)) {
    # Greg, 2026-09-20 21:05Z: this provenance gate is overridden with a receipt. Root produced the
    # attestation on his own machine, so host_record.path names a file there; what the pin verifies is
    # the record's bytes and sha256, and those are checked below unchanged. Only the path is rewritten,
    # to where the record is placed on this host, into a NEW file; Root's original stays untouched in
    # the incoming directory and the original value goes into the receipt.
    $attestationPathRewrittenFrom = [string]$pinned.path
    $attestation.host_record.path = $recordTarget
    $attestationFile = Join-Path $incoming 'host-attestation.host-path.json'
    Set-Content -Path $attestationFile -Value ($attestation | ConvertTo-Json -Depth 12) -NoNewline -Encoding UTF8
    $AttestationSha256 = Digest $attestationFile
    $AttestationBytes = [string](Get-Item $attestationFile).Length
    $pinned = $attestation.host_record
    Write-Output ("attestation host_record.path rewritten from '" + $attestationPathRewrittenFrom + "' to the host path (receipted); rewritten file sha256=" + $AttestationSha256 + " bytes=" + $AttestationBytes)
}
if ($pinned.sha256 -ne $RecordSha256 -or [int64]$pinned.bytes -ne [int64]$RecordBytes) {
    throw ("refusing: the attestation pins the record as " + $pinned.bytes + " bytes sha256 " + $pinned.sha256 + "; the delivered record is " + $RecordBytes + " " + $RecordSha256)
}
if (Test-Path $recordTarget) {
    if ((Digest $recordTarget) -ne $RecordSha256) { throw ("refusing: a different host-session-record.json is present at " + $recordTarget + " (sha256 " + (Digest $recordTarget) + "); not replaced") }
    Write-Output 'host session record already in place with the pinned digest'
} else {
    Copy-Item -LiteralPath $recordFile -Destination $recordTarget
    if ((Digest $recordTarget) -ne $RecordSha256) { throw 'host session record digest changed on placement' }
    Write-Output ("placed host session record at " + $recordTarget)
}
$tool = Join-Path $ToolsRoot 'research\kalshi\frankie_boss\operations\record_actual_frankie_response.py'
if (-not (Test-Path $tool)) { throw ("recorder missing from the tools checkout: " + $tool) }
if (-not (Test-Path $Python)) { throw ("host python missing: " + $Python) }
$git = Get-Command git -ErrorAction SilentlyContinue
$toolsHead = if ($git) { (& $git.Source -C $ToolsRoot rev-parse HEAD) } else { 'unknown' }
Write-Output ("TOOLS_HEAD=" + $toolsHead)
$log = Join-Path $dayDirectory ('principal-response-recorder-' + $stamp + '.log')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = $ToolsRoot
$env:PYTHONIOENCODING = 'utf-8'
# The recorder's own __main__ prints only {"status": "refused", "error_type": ...} and swallows the message (run
# 35630974458, 2026-09-21: a ValueError with no text). This wrapper, sent with the script from the dispatched ref,
# runs the same main() from the host tools checkout and, on a refusal, prints the traceback and the message too.
# THE RECORDER SOURCE TRAVELS WITH THIS SCRIPT (verbatim copy of operations/record_actual_frankie_response.py on the
# dispatched ref; tests/test_frankie_host_recorder_script.py fails when the copy drifts). The host tools checkout
# (35f857f0) carries the recorder without the candidate admission-inputs fix; moving that checkout mid-run is a host
# action with a code-bound consequence, so the fixed recorder is written beside the log and run from there, with
# PYTHONPATH still the host tools checkout for every import it makes.
$recorderSource = @'
"""Record an actual host-attested Frankie response; inert until explicitly invoked.

This helper neither invokes an agent nor creates session provenance. The root
host must supply the real response and independent session attestation witnesses.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
from types import SimpleNamespace


def verified_json(path,digest):
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('independent file witness differs')
    return json.loads(raw)


def candidate_of(adapter,directory):
    """The candidate adapter that validates in `directory` before the immutable final write. The admission record is
    provenance of the PRINCIPAL directory: sealed_absence() records the proof's resolved path, file_witness() refuses a
    link, and the attachment carries the record prepared there; so a candidate can neither copy nor link the proof
    (runs 35630974458, 35632243715, 35632610025, 2026-09-21). The candidate answers _admission_record with the real
    adapter's own bound method (an instance attribute shadows the class method), everything else in its own directory."""
    candidate=copy.copy(adapter)
    candidate.directory=Path(directory)
    candidate._admission_record=adapter._admission_record
    return candidate


def live_classroom(request,classroom_package,derive,json_form):
    """The attachment's Dipole classroom block in its LIVE form. The classroom adapter compares
    attachment['dipole_classroom'] with final_model_visible_classroom(package) by Python equality; the package comes
    from the c15 loader (tuples), the attachment from session-request.json (lists), so the retained request could never
    pass ('principal attachment Dipole classroom differs from final model-visible contract', run 35632927377,
    2026-09-21). Every comparison of a retained file against a live object goes through json_form (the adapter's own
    rule): when the two agree in JSON form, the live object is put into the attachment; otherwise the attachment is
    left as read and the adapter refuses as before. Returns 'live' or 'unchanged'."""
    attachment=request.get('attachment') or {}
    if 'dipole_classroom' not in attachment:return 'unchanged'
    live=derive(classroom_package)
    if json_form(live)!=attachment['dipole_classroom']:return 'unchanged'
    attachment['dipole_classroom']=live
    return 'live'


def classroom_normalizer(classroom_package,derive,json_form):
    """A function attachment -> attachment with the Dipole classroom block in its live form (see live_classroom). The
    adapter re-reads session-request.json inside verify() and recovers again (run 35633328702), so every recover the
    recorder makes goes through this, not only the first."""
    def normalize(attachment):
        holder={'attachment':dict(attachment)}
        live_classroom(holder,classroom_package,derive,json_form)
        return holder['attachment']
    return normalize


def record_checked(adapter,request,response,attestation,binding,input_hash,canonical,normalize_attachment=lambda attachment:attachment):
    """Validate in a retained candidate directory before the immutable final write."""
    from research.kalshi.frankie_boss.frankie_principal_adapter import FrankiePrincipalAdapter
    final=adapter.directory/'session-response.json'
    expected=dict(response=response,host_attestation=attestation)
    candidate=candidate_of(adapter,adapter.directory/('response-check-'+uuid.uuid4().hex))
    candidate.directory.mkdir()
    (candidate.directory/'receiver').mkdir()
    (candidate.directory/'session-request.json').write_bytes(canonical(request))
    (candidate.directory/'session-response.json').write_bytes(canonical(expected))
    for name in request['attachment']['preparation_receipt']['outputs']:
        if Path(name).name!=name:raise ValueError('receiver output must be a direct member')
        shutil.copyfile(adapter.directory/'receiver'/name,candidate.directory/'receiver'/name)
    # Validate the initial durable response without pretending that the mandatory
    # second classroom turn has already completed. The live host owns grading.
    initial_recover=lambda request_id,attachment: FrankiePrincipalAdapter.recover(candidate,request_id,normalize_attachment(attachment))
    envelope=initial_recover(request['request_id'],request['attachment'])
    view=SimpleNamespace(directory=candidate.directory,recover=initial_recover)
    feedback=FrankiePrincipalAdapter.verify(view,envelope,request_id=request['request_id'],input_hash=input_hash,
        source_hash=binding['source_hash'],learning_cutoff_ns=binding['learning_cutoff_ns'])
    if (not binding['as_of']<=feedback.available_ns<=binding['learning_cutoff_ns'] or
        tuple(s.session_id for s in feedback.sessions)!=tuple(s.session_id for _,s in binding['sessions']) or
        type(envelope['lessons']) not in (list,tuple)):
        raise ValueError('principal feedback chronology, roster or lessons differ')
    # Use the learner's exact pure label checks without constructing a model,
    # optimizer, context, or source reader. In particular, a censored tail does
    # not establish STOP; STOP requires observations through the session close.
    from research.kalshi.frankie_boss.native_forecast_learning import NativeForecastLearner
    validator=object.__new__(NativeForecastLearner)
    validator.config=SimpleNamespace(session_weights=tuple((s.session_id,1.0) for _,s in binding['sessions']))
    validator._validate(binding['sessions'],feedback,binding['as_of'],binding['learning_cutoff_ns'])
    if final.exists():
        if final.read_bytes()!=canonical(expected):raise ValueError('retained final principal response differs')
    else:adapter.record_session_response(response,host_attestation=attestation)
    return FrankiePrincipalAdapter.recover(adapter,request['request_id'],normalize_attachment(request['attachment']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('configuration','configuration-sha256','response','response-sha256','host-attestation','host-attestation-sha256'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--cycle-index',type=int,required=True)
    args=parser.parse_args()
    config=verified_json(args.configuration,args.configuration_sha256);h=config['host_runtime']
    sys.path.insert(0,h['repository'])
    from research.kalshi.frankie_boss.sunday_execution import _load
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle,make_principal_adapter
    from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
    from research.kalshi.frankie_boss.feedback_cycle import _exclusive
    from research.kalshi.frankie_boss.dipole_classroom_integration import IntegratedDipoleClassroomPrincipalAdapter
    if not 0<=args.cycle_index<19:raise ValueError('authored cycle index required')
    schedule=verified_json(h['schedule']['path'],h['schedule']['sha256'])
    steps=schedule['steps'] if type(schedule) is dict else schedule
    binding=bind_cycle(config['contract']['path'],config['contract']['sha256'],args.cycle_index,steps[args.cycle_index])
    run=Path(config['run_directory']);directory=run/'execution'/f'cycle-{args.cycle_index:02d}'
    with _exclusive(run/'actual-host.lock'):
        plan=_load(directory/'request-plan.c15.json');export=_load(directory/'principal-export.c15.json')
        principal=directory/'principal'
        # Recording cannot initiate source binding, receiver preparation or a session.
        if not (principal/'bound-mapping.json').exists() or not (principal/'session-request.json').exists():
            raise ValueError('actual retained principal request and mapping required')
        request=json.loads((principal/'session-request.json').read_bytes())
        if request['request_id']!=plan['request_id']:raise ValueError('retained principal request differs from plan')
        # Host-only package loading: withheld targets are never printed or placed
        # in the model-facing response. The actual host still grades both turns.
        classroom_package={
            name.replace('-','_'): _load(directory/('host-dipole-classroom-'+name+'.c15.json'))
            for name in ('source','teacher-key','pre-message','binding')}
        from research.kalshi.frankie_boss.dipole_classroom_final_review import final_model_visible_classroom
        from research.kalshi.frankie_boss.frankie_principal_adapter import json_form
        print('attachment dipole_classroom: '+live_classroom(request,classroom_package,final_model_visible_classroom,json_form))
        normalize=classroom_normalizer(classroom_package,final_model_visible_classroom,json_form)
        adapter=make_principal_adapter(binding=binding,handoff_directory=export['directory'],
            expected_manifest_sha256=export['manifest_sha256'],boss_journal_path=plan['source_journal_path'],
            source_journal_checkpoint=plan['source_journal_checkpoint'],mapping_directory=str(Path(config['mapping']['path']).parent),
            expected_mapping_sha256=config['mapping']['sha256'],receiver_root=config['receiver_root'],
            receiver_commit=config['receiver_commit'],python=sys.executable,directory=principal,admission=config.get('principal_admission'),
            retained_directory=str(Path(config['retained_witnesses']['path']).parent),
            expected_retained_witnesses_sha256=config['retained_witnesses']['sha256'],
            delivery_receipt=config['delivery_receipt']['path'],expected_delivery_file_sha256=config['delivery_receipt']['sha256'],
            result_path=config['calculation_result']['path'],session_executor=None,
            classroom_package=classroom_package,adapter_class=IntegratedDipoleClassroomPrincipalAdapter)
        response=verified_json(args.response,args.response_sha256)
        attestation=verified_json(args.host_attestation,args.host_attestation_sha256)
        result=record_checked(adapter,request,response,attestation,binding,plan['input_hash'],canonical,normalize_attachment=normalize)
        print(json.dumps(dict(status='actual_principal_response_recorded',request_id=request['request_id'],
            principal_receipt_sha256=result['principal_receipt']['receipt_sha256'])))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps(dict(status='refused',error_type=type(error).__name__,error=str(error)[:800])))
        raise SystemExit(1)
'@
$shippedTool = Join-Path $dayDirectory ('principal-response-recorder-' + $stamp + '.py')
[System.IO.File]::WriteAllText($shippedTool, $recorderSource, (New-Object System.Text.UTF8Encoding $false))
Write-Output ("SHIPPED_RECORDER=" + $shippedTool + " bytes=" + (Get-Item $shippedTool).Length)
$tool = $shippedTool
$wrapper = @'
import importlib.util, json, sys, traceback
tool = sys.argv[1]
sys.argv = [tool] + sys.argv[2:]
spec = importlib.util.spec_from_file_location('record_actual_frankie_response', tool)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
try:
    module.main()
except SystemExit:
    raise
except Exception as error:
    traceback.print_exc(file=sys.stdout)      # stdout: under Stop, the first stderr line would end the host script early (run 35631652890)
    print(json.dumps(dict(status='refused', error_type=type(error).__name__, error=str(error)[:800])))
    sys.stdout.flush()
    raise SystemExit(1)
'@
Push-Location $ToolsRoot
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'   # a line on stderr from the recorder is output to keep, not a terminating error
try {
    & $Python -c $wrapper $tool --configuration $cfgPath --configuration-sha256 $cfgSha --cycle-index ([int]$CycleIndex) `
        --response $responseFile --response-sha256 $ResponseSha256 `
        --host-attestation $attestationFile --host-attestation-sha256 $AttestationSha256 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath $log
    $recorderExit = $LASTEXITCODE
} finally { Pop-Location; $ErrorActionPreference = $previousPreference }
$output = if (Test-Path $log) { Get-Content $log -Raw } else { '' }
if ($recorderExit -ne 0 -or $output -notmatch 'actual_principal_response_recorded') {
    throw ("the recorder did not record (exit " + $recorderExit + "); its output is above and in " + $log)
}
if (-not (Test-Path $responsePath)) { throw 'the recorder reported success but session-response.json is absent' }
$statusLine = ($output -split "`n" | Where-Object { $_ -match 'actual_principal_response_recorded' } | Select-Object -Last 1).Trim()
$receipt = [ordered]@{
    schema                  = 'FRANKIE_PRINCIPAL_RESPONSE_RECORDED_V1'
    day                     = $Day
    run_id                  = $cfg.run_id
    cycle_index             = [int]$CycleIndex
    source_ref              = $SourceRef
    tools_head              = $toolsHead
    configuration_sha256    = $cfgSha
    response_sha256         = $ResponseSha256
    response_bytes          = [int64]$ResponseBytes
    host_attestation_sha256 = $AttestationSha256
    host_attestation_bytes  = [int64]$AttestationBytes
    host_attestation_path_rewritten_from = $attestationPathRewrittenFrom
    host_record_path        = $recordTarget
    host_record_sha256      = $RecordSha256
    host_record_bytes       = [int64]$RecordBytes
    session_response_path   = $responsePath
    session_response_sha256 = (Digest $responsePath)
    session_response_bytes  = (Get-Item $responsePath).Length
    recorder_status         = $statusLine
    incoming_directory      = $incoming
    at                      = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}
$receiptPath = Join-Path $dayDirectory ('principal-response-recorded-' + $stamp + '.json')
Set-Content -Path $receiptPath -Value ($receipt | ConvertTo-Json -Depth 4) -NoNewline -Encoding UTF8
Write-Output ("receipt: " + $receiptPath)
Write-Output ('RECEIPT ' + ($receipt | ConvertTo-Json -Depth 4 -Compress))
