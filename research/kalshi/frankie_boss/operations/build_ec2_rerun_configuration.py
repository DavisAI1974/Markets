"""Build a NEW-run Sunday configuration while preserving evidence paths and pins.

Preferred restoration is a Windows EC2 host with the original E:/Codex and
C:/Users/A/Documents/Codex layouts materialized exactly. That keeps nested witness
bytes and SHA-256 identities unchanged. This builder changes only new-run identity,
run directory, reviewed BOSS commit, completion-workflow ref, and the explicit
numeric runtime policy.

Cycle 0 is intentionally rerun from its lawful source boundary. The failed run's
retained preparation-recovery witness is removed from the new configuration so
cycle-0 context preparation is recomputed rather than adopted from the failed run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

SOURCE_CONFIGURATION_SHA256 = 'a5eef9157130a596da4d5b62e9be2a268f95a561987b59481de4642f33b29f38'
SOURCE_RUN_ID = 'frankie-boss-own-source-sunday-20260915'
LAWFUL_PARENT = '050c5056c3657a954d6a3ee17f3a216999930768'


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()


def boolean(value):
    if value == 'true': return True
    if value == 'false': return False
    raise argparse.ArgumentTypeError('expected true or false')


def completion_ref_contains_commit(repository, ref, boss_commit):
    """Fail closed unless the remote workflow branch contains the reviewed BOSS commit.

    `gh workflow run --ref` chooses which workflow YAML GitHub executes. Resolve that
    branch from origin instead of trusting a local tracking ref, fetch its branch history
    into FETCH_HEAD without moving any local branch, then require boss_commit to be its
    ancestor. This also works when the restored checkout has not fetched the reviewed
    commit objects yet.
    """
    repository=Path(repository).resolve()
    if not repository.is_dir():
        raise SystemExit('host repository required to verify completion workflow ref')
    if ref.startswith('refs/heads/'):
        remote_ref=ref
    elif ref.startswith('refs/'):
        raise SystemExit('completion workflow ref must be a branch ref')
    else:
        remote_ref='refs/heads/'+ref
    try:
        rows=subprocess.check_output(
            ['git','ls-remote','--heads','origin',remote_ref],cwd=repository,text=True,
            stderr=subprocess.STDOUT).splitlines()
    except subprocess.CalledProcessError as error:
        raise SystemExit('unable to resolve completion workflow ref from origin') from error
    parsed=[]
    for row in rows:
        parts=row.split()
        if len(parts)==2 and parts[1]==remote_ref and re.fullmatch(r'[0-9a-f]{40}',parts[0]):
            parsed.append(parts[0])
    if len(set(parsed))!=1:
        raise SystemExit('completion workflow ref must resolve to one remote branch tip')
    tip=parsed[0]
    try:
        subprocess.run(['git','fetch','--no-tags','--quiet','origin',remote_ref],cwd=repository,check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as error:
        raise SystemExit('unable to fetch completion workflow branch for ancestry verification') from error
    for commit,message in ((tip,'completion workflow branch tip is not a commit'),
                           (boss_commit,'reviewed BOSS commit is not present after fetching workflow branch')):
        try:
            subprocess.run(['git','cat-file','-e',commit+'^{commit}'],cwd=repository,check=True,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as error:
            raise SystemExit(message) from error
    if subprocess.run(['git','merge-base','--is-ancestor',boss_commit,tip],cwd=repository,
                      stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0:
        raise SystemExit('completion workflow ref does not contain the reviewed BOSS commit')
    return tip


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-configuration',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--run-directory',required=True)
    parser.add_argument('--boss-commit',required=True)
    parser.add_argument('--completion-workflow-ref',required=True)
    parser.add_argument('--python-version',default='3.13.7')
    parser.add_argument('--torch-version',default='2.9.1+cpu')
    parser.add_argument('--numpy-version',default='2.3.5')
    parser.add_argument('--torch-intraop-threads',required=True,type=int)
    parser.add_argument('--torch-interop-threads',default=1,type=int)
    parser.add_argument('--deterministic-algorithms',required=True,type=boolean)
    parser.add_argument('--minimum-logical-cpus',required=True,type=int)
    parser.add_argument('--minimum-memory-gib',required=True,type=int)
    args=parser.parse_args()

    source=Path(args.source_configuration)
    if sha256(source)!=SOURCE_CONFIGURATION_SHA256:
        raise SystemExit('source Sunday configuration differs from reviewed package')
    config=json.loads(source.read_bytes())
    if (config.get('schema')!='FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1'
            or config.get('run_id')!=SOURCE_RUN_ID
            or config.get('host_runtime',{}).get('boss_commit')!=LAWFUL_PARENT):
        raise SystemExit('source Sunday identity differs from failed lawful run')
    if args.run_id==SOURCE_RUN_ID or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',args.run_id):
        raise SystemExit('fresh bounded run id required')
    if not re.fullmatch(r'[0-9a-f]{40}',args.boss_commit):
        raise SystemExit('reviewed 40-hex BOSS commit required')
    if args.boss_commit==LAWFUL_PARENT:
        raise SystemExit('rerun configuration must name the reviewed recovery commit, not the failed commit')
    if (not re.fullmatch(r'[A-Za-z0-9._/-]{1,200}',args.completion_workflow_ref)
            or args.completion_workflow_ref.startswith('/') or '..' in args.completion_workflow_ref.split('/')):
        raise SystemExit('explicit safe completion workflow ref required')
    if args.completion_workflow_ref=='codex/full-frankie-boss-connection-20260915':
        raise SystemExit('completion workflow ref cannot point back to the divergent lineage')
    completion_tip=completion_ref_contains_commit(
        config['host_runtime']['repository'],args.completion_workflow_ref,args.boss_commit)
    if any(value<1 for value in (args.torch_intraop_threads,args.torch_interop_threads,
                                  args.minimum_logical_cpus,args.minimum_memory_gib)):
        raise SystemExit('positive explicit runtime resources required')
    if args.torch_intraop_threads>args.minimum_logical_cpus:
        raise SystemExit('intra-op threads cannot exceed declared minimum logical CPUs')
    run_directory=Path(args.run_directory)
    if str(run_directory)==config['run_directory']:
        raise SystemExit('fresh run_directory required')

    # Preserve every source/evidence path and every existing witness hash. Only
    # new-run identity/code/runtime dispatch policy changes. The old run-specific
    # cycle-0 preparation recovery is deliberately not an input to this fresh benchmark.
    config['run_id']=args.run_id
    config['run_directory']=str(run_directory)
    config['host_runtime']['boss_commit']=args.boss_commit
    config['host_runtime']['completion_workflow_ref']=args.completion_workflow_ref
    config['host_runtime'].pop('retained_preparation_recovery',None)
    config['model_calls_performed']=False
    config['training_updates_performed']=False
    config['native_host_runtime']=dict(schema='FRANKIE_NATIVE_HOST_POLICY_V1',
        parent_run_id=SOURCE_RUN_ID,numeric_identity='NEW',
        python_version=args.python_version,torch_version=args.torch_version,numpy_version=args.numpy_version,
        torch_intraop_threads=args.torch_intraop_threads,torch_interop_threads=args.torch_interop_threads,
        deterministic_algorithms=args.deterministic_algorithms,minimum_logical_cpus=args.minimum_logical_cpus,
        minimum_memory_bytes=args.minimum_memory_gib*1024**3)
    raw=json.dumps(config,indent=2,sort_keys=True).encode()+b'\n'
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('xb') as stream:stream.write(raw)
    print(json.dumps(dict(schema='FRANKIE_EC2_RERUN_CONFIGURATION_BUILT_V1',out=str(out),
        run_id=args.run_id,run_directory=str(run_directory),boss_commit=args.boss_commit,
        completion_workflow_ref=args.completion_workflow_ref,completion_workflow_tip=completion_tip,
        cycle0_preparation_reused=False,configuration_sha256=hashlib.sha256(raw).hexdigest())))
    return 0


if __name__=='__main__':raise SystemExit(main())
