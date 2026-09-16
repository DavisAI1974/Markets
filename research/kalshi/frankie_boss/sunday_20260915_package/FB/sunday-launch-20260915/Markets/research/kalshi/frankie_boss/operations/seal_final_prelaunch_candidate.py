"""Seal an audit candidate only. Import and --help never read source data or cloud."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess

TASK=Path('C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue')
AUDIT=Path('E:/Codex/Frankie-BOSS-20260915/final-audit')
PINNED_BYTES={}
DEFAULT_HOST=Path(__file__).with_name('run_actual_sunday.py')
DEFAULT_CONFIG=DEFAULT_HOST.with_name('actual-host-configuration.json')
ROOTS=('research/kalshi/frankie_boss','research/refrag','.github/workflows')
ALLOWED={'.py','.json','.md','.yml','.yaml','.toml'}
MAX_ARTIFACT=64*1024*1024

def pin(path, expected=None):
    path=Path(path)
    if path.is_symlink():raise ValueError('symlink artifact refused')
    path=path.resolve()
    if path.suffix.lower() not in ALLOWED or path.is_symlink() or not path.is_file():raise ValueError('only existing small code/receipt artifacts may be read: '+str(path))
    size=path.stat().st_size
    if size>MAX_ARTIFACT:raise ValueError('artifact too large for receipt-only sealing: '+str(path))
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if expected is not None and (digest!=expected['sha256'] or ('bytes' in expected and size!=expected['bytes'])):raise ValueError('independent file pin differs: '+str(path))
    if str(path) in PINNED_BYTES and PINNED_BYTES[str(path)]!=raw:raise ValueError('artifact changed during seal: '+str(path))
    PINNED_BYTES[str(path)]=raw
    return dict(path=str(path),bytes=len(raw),sha256=digest),raw

def verify(witness):
    if type(witness) is not dict or 'path' not in witness or 'sha256' not in witness:raise ValueError('final independently pinned witness missing')
    result,raw=pin(witness['path'],witness)
    return result,json.loads(raw)

def git(repo,*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit',required=True)
    parser.add_argument('--audit-directory',type=Path,required=True)
    parser.add_argument('--configuration',type=Path,default=DEFAULT_CONFIG)
    parser.add_argument('--host-script',type=Path,default=DEFAULT_HOST)
    parser.add_argument('--bootstrap',type=Path,default=Path('E:/Codex/Frankie-BOSS-20260915/bootstrap-jobs-final-v1'))
    parser.add_argument('--helper',type=Path,action='append',default=[])
    parser.add_argument('--principal-instructions',type=Path,required=True)
    args=parser.parse_args()
    target=args.audit_directory/'FINAL_PRELAUNCH_CANDIDATE.json'
    snapshots=args.audit_directory/'FINAL_PRELAUNCH_AUDIT_FILES'
    if snapshots.exists():raise ValueError('preserve prior audit snapshot directory')
    if target.exists():raise ValueError('preserve previous final seal; use a new explicitly named audit output')
    config_pin,config_raw=pin(args.configuration);config=json.loads(config_raw);host=config['host_runtime']
    repo=Path(host['repository']).resolve();head=git(repo,'rev-parse','HEAD')
    if head!=args.commit or host.get('boss_commit')!=head:raise ValueError('final HEAD and host boss_commit must match')
    changed=git(repo,'diff','--name-only','HEAD','--',*ROOTS)
    if changed:raise ValueError('tracked production code is not clean: '+changed)
    untracked=git(repo,'ls-files','--others','--exclude-standard','--',*ROOTS)
    if any(Path(name).suffix in ALLOWED for name in untracked.splitlines()):raise ValueError('uncommitted production helper/spec/test/workflow exists')
    if (host.get('service_context')!=131072 or host.get('context_encoding')!='stacked_v1' or host.get('transport_protocol')!='jobs_v1' or host.get('output_budget')!='remaining_context'):raise ValueError('final runtime policy differs')
    # Required final source evidence. Never open any DB or snapshot named inside it.
    for folder in (config['source_directory'],config['schedule_directory']):
        if (Path(folder)/'failure.json').exists():raise ValueError('source finalization failure evidence remains')
    source={};source_values={}
    for name in ('ingestion_receipt','schedule_receipt','schedule','source_lineage','prefix_manifest'):
        source[name],source_values[name]=verify(host[name])
    ingestion=source_values['ingestion_receipt'];prefixes=source_values['prefix_manifest']
    if ingestion.get('record_count')!=57027:raise ValueError('complete Sunday ingestion receipt required')
    if (prefixes.get('schema')!='FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1' or prefixes.get('prefixes')!=19 or prefixes.get('source_records')!=57027 or len(prefixes.get('witnesses',[]))!=19):raise ValueError('complete nineteen-prefix manifest required')
    receipts=[];snapshot_pins=[]
    batch_pin,batch=verify(prefixes['binding']);receipts.append(batch_pin)
    if 'compact_journal' in batch:
        if batch['compact_journal'] != host.get('compact_journal'):
            raise ValueError('compact parent differs from final host configuration')
        boss=repo/'research/kalshi/frankie_boss'
        for field,path in (('compact_copier_sha256',boss/'compact_journal_snapshot.py'),
                           ('full_reader_sha256',boss/'frankie_journal_reader.py'),
                           ('script_sha256',boss/'operations/build_remaining_sunday_prefixes.py')):
            if batch[field]!=pin(path)[0]['sha256']:
                raise ValueError('compact preparation code differs from final candidate')
    for field,name in (('runtime_code_sha256','sunday_native_runtime.py'),('selection_code_sha256','context_session.py')):
        if batch['context_selection'][field]!=pin(repo/'research/kalshi/frankie_boss'/name)[0]['sha256']:raise ValueError('prefix batch selection code differs from final candidate')
    for name in ('ingestion_receipt','schedule_receipt','schedule','source_lineage'):
        if batch[name]['sha256']!=host[name]['sha256']:raise ValueError('full-prefix batch differs from final source quartet')
    for index,witness in enumerate(prefixes['witnesses']):
        outer_pin,files=verify(witness);receipt_pin,receipt=verify(files['receipt'])
        receipts.extend((outer_pin,receipt_pin))
        if index and 'compact_journal' in batch:
            if (receipt.get('schema')!='C15_COMPACT_JOURNAL_PREFIX_SNAPSHOT_V1'
                    or receipt['compact_parent']!=batch['compact_journal']):
                raise ValueError('compact prefix provenance differs')
        snapshot=files['snapshot']
        if not {'path','sha256'}<=set(snapshot):raise ValueError('snapshot lacks retained identity')
        snapshot_pins.append(dict(cycle_index=index,**snapshot,validation='trusted prior verification; not opened or rehashed by seal'))
        if index:
            seed_pin,seed=verify(prefixes['prefix_seed_witnesses'][str(index)]);receipts.append(seed_pin)
            if seed['cycle_index']!=index or seed['batch_binding_sha256']!=prefixes['binding']['sha256'] or seed['snapshot_receipt_sha256']!=files['receipt']['sha256']:raise ValueError('prefix seed receipt binding differs')
    # Package is tiny and must agree with the same frozen source commit.
    package_pin,package_raw=pin(args.bootstrap/'package-receipt.json');package=json.loads(package_raw)
    runtime_pin,runtime_raw=pin(args.bootstrap/'runtime-configuration.json');runtime=json.loads(runtime_raw)
    assembly_pin,assembly_raw=pin(args.bootstrap/'assembly-receipt.json');assembly=json.loads(assembly_raw)
    if any(value.get('source_commit')!=head for value in (package,runtime,assembly)):raise ValueError('bootstrap source commit differs from final code')
    if any(runtime[key]!=host[key] for key in ('service_context','context_encoding','transport_protocol')):raise ValueError('bootstrap policy differs from host')
    bundle_pin,bundle_raw=pin(args.bootstrap/'files/runpod_bundle.json');bundle=json.loads(bundle_raw)
    if bundle_pin['sha256']!=package['bundle_sha256'] or runtime['bundle_sha256']!=package['bundle_sha256'] or bundle['files']!=runtime['files']:raise ValueError('bootstrap bundle rows differ')
    if hashlib.sha256(package['supervisor_command'].encode()).hexdigest()!=runtime['supervisor_command_sha256']:raise ValueError('supervisor command differs')
    bootstrap_files=[]
    for row in bundle['files']:
        if Path(row['path']).name!=row['path']:raise ValueError('bootstrap filename is not flat')
        item,raw=pin(args.bootstrap/'files'/row['path'],dict(sha256=row['sha256'],bytes=row['size']))
        committed=subprocess.check_output(['git','show',head+':research/kalshi/frankie_boss/'+row['path']],cwd=repo)
        if raw!=committed:raise ValueError('bootstrap bytes differ from exact final commit')
        bootstrap_files.append(item)
    tracked=[]
    for name in git(repo,'ls-files','--',*ROOTS).splitlines():
        if Path(name).suffix in ALLOWED:
            item,_=pin(repo/name);tracked.append(dict(repository_path=name,**item))
    helpers=[]
    for path in [Path(__file__),Path(__file__).with_name('package_final_committed.py'),TASK/'work/record_actual_frankie_response.py',TASK/'work/build_remaining_sunday_prefixes.py',TASK/'work/build_remaining_sunday_prefixes_candidate.py',TASK/'work/build_remaining_sunday_prefixes_preseed.py',*args.helper]:
        item,_=pin(path);helpers.append(item)
    instructions_pin,_=pin(args.principal_instructions);helpers.append(instructions_pin)
    host_pin,_=pin(args.host_script)
    recovery_pin,recovery=verify(host['retained_preparation_recovery']);receipts.append(recovery_pin)
    for name in ('request','prepared','initialization'):
        item,_=verify(recovery[name]);receipts.append(item)
    # Capture existing actual request/admission, not another tokenization.
    actual=Path('E:/Codex/Frankie-BOSS-20260915/production-stacked-full-output')
    request_pin,request_raw=pin(actual/'actual-request.json');admit_pin,admit_raw=pin(actual/'token-admission.json');admit=json.loads(admit_raw)
    if admit['request_sha256']!=request_pin['sha256'] or admit['input_tokens']+admit['output_tokens']!=131072 or json.loads(request_raw)['max_tokens']!=admit['output_tokens']:raise ValueError('actual remaining-output admission differs')
    # Recheck mutable control files at end; no giant data reads.
    if git(repo,'rev-parse','HEAD')!=head or git(repo,'diff','--name-only','HEAD','--',*ROOTS):raise ValueError('code changed during seal')
    if pin(args.configuration)[0]!=config_pin or pin(args.host_script)[0]!=host_pin:raise ValueError('host changed during seal')
    record=dict(schema='FRANKIE_FINAL_PRELAUNCH_CANDIDATE_V1',status='candidate_for_audit',approved=False,created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_commit=head,repository=str(repo),host_script=host_pin,host_configuration=config_pin,tracked_code_specs_tests_workflows=tracked,helpers=helpers,source_receipts=source,verified_small_receipts=receipts,snapshot_identities_not_rehashed=snapshot_pins,bootstrap=dict(package=package_pin,runtime_configuration=runtime_pin,assembly=assembly_pin,bundle=bundle_pin,files=bootstrap_files),actual_request=request_pin,actual_admission=admit_pin,limitations=[*host.get('development_limitations',[]),'Candidate requires independent final audit; this seal is not launch approval.','Local source-derived tokenizer parity is verified; retained live vLLM token count is not yet proven.','No full-source or prefix database was opened or rehashed by this seal; prior verification receipts are reused.','Successful model inference, complete output, feedback acceptance and training outcomes are not established by preparation.'],source_database_reads=0,model_calls=0,cloud_actions=0)
    # Snapshot the exact bytes already hashed, preserving their absolute drive/layout.
    # No second reads of giant data, no overwrite of any previous snapshot.
    snapshot_rows=[]
    for original,raw in PINNED_BYTES.items():
        if Path(original).read_bytes()!=raw:raise ValueError('small artifact changed before snapshot: '+original)
    snapshots.mkdir(parents=True,exist_ok=False)
    for original,raw in sorted(PINNED_BYTES.items()):
        original_path=Path(original)
        relative=Path(original_path.drive.rstrip(':'))/Path(*original_path.parts[1:])
        destination=snapshots/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as stream:stream.write(raw)
        digest=hashlib.sha256(raw).hexdigest()
        snapshot_rows.append(dict(original_path=original,snapshot_path=str(destination),relative_path=relative.as_posix(),bytes=len(raw),original_sha256=digest,snapshot_sha256=digest))
    record['audit_snapshot']=dict(path=str(snapshots),files=snapshot_rows,immutable_by_policy=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as stream:json.dump(record,stream,sort_keys=True,indent=2)
    print(json.dumps(dict(status=record['status'],path=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest())))

if __name__=='__main__':main()


