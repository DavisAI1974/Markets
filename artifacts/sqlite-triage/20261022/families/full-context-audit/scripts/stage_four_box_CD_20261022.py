import pathlib,json,os,subprocess,time,hashlib,sys,urllib.request,uuid
def run(*args):
    r=subprocess.run(list(args),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if r.returncode and not (args[0]=='growpart' and 'NOCHANGE' in r.stdout):
        print(r.stdout,flush=True);raise RuntimeError('provisioning command failed: '+args[0])
    return r.stdout.strip()
token=urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/api/token',
    data=b'',method='PUT',headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'}),timeout=5).read().decode()
instance=urllib.request.urlopen(urllib.request.Request('http://169.254.169.254/latest/meta-data/instance-id',
    headers={'X-aws-ec2-metadata-token':token}),timeout=5).read().decode()
config={'i-031eeb577ad72b064':('C','vol07930910b3266da92'),'i-0d17573dbce871520':('D','vol0e28c104e4ea65b43')}
assert instance in config
owner,volume=config[instance]
for proc in pathlib.Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:cmd=(proc/'cmdline').read_bytes().split(b'\0')
    except OSError:continue
    if b'--execute' in cmd and any(b'resume_' in x and b'candidate' in x for x in cmd):
        raise RuntimeError('B is already executing; staging must never be replayed over live work')

matches=[p for p in pathlib.Path('/sys/block').glob('nvme*n1/device/serial') if p.read_text().strip()==volume]
assert len(matches)==1
device=pathlib.Path('/dev')/matches[0].parents[1].name
partition=pathlib.Path(str(device)+'p1')
root_source=run('findmnt','-n','-o','SOURCE','/')
assert not root_source.startswith(str(device))
assert partition.exists()
mount=pathlib.Path('/mnt/family-source');mount.mkdir(exist_ok=True)
if not os.path.ismount(mount):
    run('mount',str(partition),str(mount))  # Replay only the clone's ext4 journal.
    run('umount',str(mount))
    # Keep filesystem UUID; stable volume IDs avoid a full metadata rewrite.
    run('e2label',str(partition),'family-inputs-'+owner.lower())
    assert '--part-uuid' in run('sfdisk','--help')
    for part in [1,14,15,16]:
        if pathlib.Path(str(device)+'p'+str(part)).exists():
            run('sfdisk','--part-uuid',str(device),str(part),str(uuid.uuid4()))
    run('growpart',str(device),'1')
    run('mount',str(partition),str(mount))
    resize=run('resize2fs',str(partition))
else:
    assert run('findmnt','-n','-o','SOURCE',str(mount)).startswith(str(partition))
    resize='already mounted'
B=pathlib.Path('/opt/frankie-box/work/family-research-20261022')
source=mount/str(B).lstrip('/')
assert (source/'julia-runtime/julia-1.13.2/bin/julia').is_file()
B.mkdir(parents=True,exist_ok=True)
if not os.path.ismount(B):
    assert not any(B.iterdir())
    run('mount','--bind',str(source),str(B))
O=B/'joint-models-v4-candidate-20261022'
retained=B/'joint-models-v4-candidate-20261022-snapshot-source-184835'
if not retained.exists():
    assert O.is_dir()
    O.rename(retained)
O.mkdir(exist_ok=True);R=O/'parallel-63';R.mkdir(exist_ok=True)
for name in ['jobs','cache','serial-prefix','attempts']:(R/name).mkdir(exist_ok=True)
oldR=retained/'parallel-63'
bootstrap=pathlib.Path('/opt/family-four-box-bootstrap')
expected=json.loads((bootstrap/'frozen-source-hashes.json').read_text())
import shutil
for name,sha in expected.items():
    p=oldR/name
    assert hashlib.sha256(p.read_bytes()).hexdigest()==sha,(name,'numerical source mismatch')
    shutil.copy2(p,R/name)
if (oldR/'pool_cache_guard.py').exists():shutil.copy2(oldR/'pool_cache_guard.py',R/'pool_cache_guard.py')
if not (R/'shared').exists():(R/'shared').symlink_to(oldR/'shared',target_is_directory=True)
assert (R/'shared/raw.bin').stat().st_size==34601642880
shutil.copytree(retained/'scripts',O/'scripts',dirs_exist_ok=True)
for name in ['model_outcomes.csv','model_matrix.jls']:
    p=retained/name
    if p.exists() and not (O/name).exists():(O/name).symlink_to(p)
p=B/'full-context-audit/scripts'
for name in ['resume_multibox_candidate.py','multibox_support.py','four_box_handoff.py']:
    shutil.copy2(bootstrap/name,p/name)
plan=json.loads((oldR/'parallel_plan.json').read_text())
plan.update(status='partition_'+owner+'_staged',coverage_gate='NOT_PASSED',owned_cohorts='pending_fresh_assignment',
    global_pca_and_postprocessing_pending=True,source_snapshot='snap-0d3e867c1240b6528')
(R/'parallel_plan.json').write_text(json.dumps(plan,indent=2))
version=run(str(B/'julia-runtime/julia-1.13.2/bin/julia'),'--startup-file=no','--version')
data_link='/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_'+volume+'-part1'
assert pathlib.Path(data_link).resolve()==partition
root_device=pathlib.Path(root_source).resolve().name.rsplit('p',1)[0]
root_serial=(pathlib.Path('/sys/block')/root_device/'device/serial').read_text().strip()
root_link='/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_'+root_serial
for part in [1,15,16]:assert pathlib.Path(root_link+'-part'+str(part)).exists()
fstab=pathlib.Path('/etc/fstab')
marker='# family-research-box-'+owner.lower()+'-20261022'
text=fstab.read_text().replace('LABEL=cloudimg-rootfs',root_link+'-part1').replace('LABEL=BOOT',root_link+'-part16').replace('LABEL=UEFI',root_link+'-part15')
if marker not in text:
    text+='\n'+marker+'\n'+data_link+' /mnt/family-source ext4 defaults,nofail 0 2\n'
    text+=str(source)+' '+str(B)+' none bind,nofail,x-systemd.requires-mounts-for=/mnt/family-source 0 0\n'
    fstab.write_text(text)
sys.path.insert(0,str(p))
run('blockdev','--setra','65536',str(device))
v=dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),instance=instance,
    data_volume='vol-'+volume[3:],source_snapshot='snap-0d3e867c1240b6528',
    mount=str(mount),source_base=str(source),family_base=str(B),julia=version,
    raw_bytes=(R/'shared/raw.bin').stat().st_size,free_gib=shutil.disk_usage(B).free/1024**3,
    source_code_sha256=expected,owned_cohorts='pending_fresh_assignment',fresh_jobs=not any((R/'jobs').iterdir()),
    no_input_rebuild=True,no_runtime_download=True,old_output_preserved=str(retained),
    assignment='pending_fresh_assignment',coverage_gate='NOT_PASSED')
(R/('box-'+owner+'-staging-receipt.json')).write_text(json.dumps(v,indent=2))
print(json.dumps(v))

