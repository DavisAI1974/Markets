"""Local-only final candidate assembly from an explicit frozen commit."""
from pathlib import Path
import ast,hashlib,json,re,shlex,subprocess,sys
repo=Path(__file__).resolve().parents[4]
commit=sys.argv[1]
if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('exact commit required')
root=Path(sys.argv[2] if len(sys.argv)>2 else 'E:/Codex/Frankie-BOSS-20260915/bootstrap-jobs-final-v1').resolve()
if root.parent != Path('E:/Codex/Frankie-BOSS-20260915').resolve() or not re.fullmatch(r'bootstrap-jobs-final-v[1-9][0-9]*',root.name) or root.exists():raise ValueError('new final candidate directory required')
def exported(name):
 return subprocess.check_output(['git','show',commit+':research/kalshi/frankie_boss/'+name],cwd=repo)
helper=exported('granite_runpod_package.py')
module=type(sys)('committed_package');exec(compile(helper,'committed_granite_runpod_package.py','exec'),module.__dict__)
values={name:exported(name) for name in module.FILES}
if any(b'\r\n' in data for name,data in values.items() if name.endswith('.py')):raise ValueError('committed LF source required')
for name,data in values.items():
 if name.endswith('.py'):compile(data,name,'exec')
stage_tree=ast.parse(exported('granite_bootstrap_stage.py'))
constants={node.targets[0].id:ast.literal_eval(node.value) for node in stage_tree.body if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('DIRECTORY','BUCKET')}
runtime,bucket=constants['DIRECTORY'],constants['BUCKET']
if bucket!='frankie-granite42-568968024170-us-east-1':raise ValueError('bootstrap origin changed')
source=root/'committed-lf';source.mkdir(parents=True)
for name,data in values.items():(source/name).write_bytes(data)
receipt=module.package(source,root/'files',runtime_directory=runtime)
receipt['source_commit']=commit
cloud_tree=ast.parse(exported('granite_runpod_cloud.py'))
selected=[node for node in cloud_tree.body if isinstance(node,ast.FunctionDef) and node.name in ('supervisor_metadata_code','bootstrap_command')]
if len(selected)!=2:raise ValueError('committed supervisor functions missing')
cloud_namespace=dict(package=module,shlex=shlex)
exec(compile(ast.Module(body=selected,type_ignores=[]),'committed_cloud_bootstrap_command.py','exec'),cloud_namespace)
rows=json.loads(json.dumps(receipt['files'],sort_keys=True))
command=cloud_namespace['bootstrap_command'](rows,receipt['bundle_sha256'],bucket,directory=runtime,open_ended=True)
receipt['preexec_command_sha256']=receipt['supervisor_command_sha256']
receipt['supervisor_command']=command;receipt['supervisor_command_sha256']=hashlib.sha256(command.encode()).hexdigest()
config=dict(schema='GRANITE_RETAINED_RUNTIME_CONFIGURATION_V1',files=rows,bundle_sha256=receipt['bundle_sha256'],supervisor_command_sha256=receipt['supervisor_command_sha256'],source_commit=commit,context_encoding='stacked_v1',service_context=131072,transport_protocol='jobs_v1',bootstrap_directory=runtime)
# Verify exact persisted row order regenerates the same command.
serialized=json.dumps(config,sort_keys=True,indent=2)
restored=json.loads(serialized)
if cloud_namespace['bootstrap_command'](restored['files'],restored['bundle_sha256'],bucket,directory=restored['bootstrap_directory'],open_ended=True)!=command:raise ValueError('persisted supervisor identity changed')
(root/'package-receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2))
(root/'runtime-configuration.json').write_text(serialized)
public=json.loads(Path('C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/bootstrap-jobs/recipient-public.json').read_bytes())
marker=dict(source_commit=commit,bundle_sha256=receipt['bundle_sha256'],recipient_public_key_der_base64=public['recipient_public_key_der_base64'])
marker_path=root/'bootstrap-stage-marker-final.json'
with marker_path.open('x') as f:json.dump(marker,f,sort_keys=True,indent=2)
summary=dict(schema='FRANKIE_FINAL_BOOTSTRAP_PACKAGE_V1',source_commit=commit,bundle_sha256=receipt['bundle_sha256'],supervisor_command_sha256=receipt['supervisor_command_sha256'],file_count=len(rows),package_directory=str(root),runtime_directory=runtime,runtime_configuration_sha256=hashlib.sha256((root/'runtime-configuration.json').read_bytes()).hexdigest(),cloud_actions=0,model_calls=0)
(root/'assembly-receipt.json').write_text(json.dumps(summary,sort_keys=True,indent=2))
print(json.dumps(summary))

