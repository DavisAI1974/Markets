"""Package six committed LF bootstrap files and generate a pre-import verifier.

Local-only helper. It never transfers files or launches a Pod.
"""
import hashlib
import json
from pathlib import Path
import shlex

FILES=('granite_runpod.py','granite_runpod_proxy.py','granite_startup.py',
       'granite_run_artifacts.py','granite_artifacts_manifest.json','granite_image_identity.json')
ROOT='/opt/ml/additional-model-data-sources/bootstrap'


def preexec_code(rows, bundle_sha256, *, directory=ROOT):
    # Embed the exact audited roster rather than trusting executable volume files.
    if len(rows)!=len(FILES) or {r['path'] for r in rows}!=set(FILES):
        raise ValueError('exact six-file bootstrap roster required')
    return ('import hashlib,os,pathlib,sys\n'
            'p=pathlib.Path('+repr(str(directory))+')\nrows='+repr(rows)+'\n'
            'if p.is_symlink() or hashlib.sha256((p/"runpod_bundle.json").read_bytes()).hexdigest()!='+repr(bundle_sha256)+':\n'
            ' raise SystemExit("bootstrap manifest mismatch")\n'
            'for r in rows:\n'
            ' f=p/r["path"]\n'
            ' if f.is_symlink() or not f.is_file() or f.stat().st_size!=r["size"] or hashlib.sha256(f.read_bytes()).hexdigest()!=r["sha256"]:\n'
            '  raise SystemExit("bootstrap file mismatch")\n'
            'os.execv(sys.executable,[sys.executable,str(p/"granite_runpod.py")])')



def package(source, destination, *, runtime_directory=ROOT):
    """Input must be a trusted committed LF export, not a CRLF working checkout."""
    source,destination=Path(source),Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('empty output directory required')
    values={name:(source/name).read_bytes() for name in FILES}
    if any(b'\r\n' in data for name,data in values.items() if name.endswith('.py')):
        raise ValueError('export committed LF source before packaging')
    rows=[dict(path=name,size=len(values[name]),sha256=hashlib.sha256(values[name]).hexdigest()) for name in FILES]
    raw=json.dumps(dict(schema='GRANITE_RUNPOD_BUNDLE_V1',files=rows),sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(raw).hexdigest()
    code=preexec_code(rows,digest,directory=runtime_directory)
    command='python3 -c '+shlex.quote('exec(bytes.fromhex('+repr(code.encode().hex())+').decode())')
    destination.mkdir(parents=True,exist_ok=True)
    for name,data in values.items():(destination/name).write_bytes(data)
    (destination/'runpod_bundle.json').write_bytes(raw)
    return {'bundle_sha256':digest,'supervisor_command':command,
            'supervisor_command_sha256':hashlib.sha256(command.encode()).hexdigest(),
            'files':rows}
