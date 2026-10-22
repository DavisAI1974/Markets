"""Collect A's final candidate outputs without copying frozen dense inputs."""
import csv
import json
import os
import pathlib
import shutil
import tarfile
from family_save_stop import require, task_set, validate_predictions, GATE


def validate_final(config, plan, state, transfers):
    # Importing these pure helpers does not enter the numerical main function.
    from resume_multibox_candidate import expected_models, stem, job_id, committed
    from multibox_support import prepared_cache_index
    out = pathlib.Path(config['out']); root = out/'parallel-63'
    require(state['status'] == 'complete_candidate' and state['coverage_gate'] == GATE,
            'final coordinator incomplete')
    published = json.loads((root/'parallel_plan.json').read_text())
    require(published['status'] == 'complete_candidate' and published['coverage_gate'] == GATE and
            pathlib.Path(published['recovery']) == pathlib.Path(config['run']), 'final publication mismatch')
    cohorts = [tuple(r['cohort']) for r in plan['cohorts']]
    require(len(cohorts) == len(set(cohorts)) == 63, 'global cohort coverage mismatch')
    owned = [tuple(r['cohort']) for r in plan['cohorts'] if r['owner'] == 'A']
    caches = prepared_cache_index(root,owned)
    require({tuple(r['cohort']) for r in caches} == set(owned), 'missing training preparation')
    required, locations, remote_roots = set(), {}, {}
    for row in caches:
        t = tuple(row['cohort'])
        info = json.loads((pathlib.Path(row['cache'])/'ready.json').read_text())
        for kind, models in zip(('core','neural'),expected_models(t,info['groups'])):
            for model in models:
                key = kind,t,model
                folder = root/'jobs'/job_id(t,kind,model)
                serial = False
                if not committed(folder,kind,t,model):
                    folder, serial = root/'serial-prefix', True
                require(committed(folder,kind,t,model,serial=serial), 'incoherent own result: '+str(key))
                required.add(key); locations[key] = folder
    for owner, receipt in transfers.items():
        imported = json.loads((root/('box-'+owner+'-import-receipt.json')).read_text())
        require(imported == receipt, 'import receipt mismatch')
        remote_required = task_set(receipt['required_jobs'])
        require(not required & remote_required, 'duplicate global task')
        for row in receipt['locations']:
            kind,t,model = key = (row['task'][0],tuple(row['task'][1]),row['task'][2])
            local = root/row['folder']
            require(local.is_symlink() and committed(local,kind,t,model), 'incoherent imported result')
            storage = local.resolve().parent.parent
            require(local.resolve() == storage/row['folder'], 'unexpected imported path')
            require(owner not in remote_roots or remote_roots[owner] == storage, 'inconsistent import storage')
            remote_roots[owner] = storage
            locations[key] = local
        required.update(remote_required)
    require({t for k,t,m in required} == set(cohorts) and
            state['committed_jobs'] == published['recovered_committed_jobs'] == len(required),
            'mandatory global union mismatch')
    counts, prediction_proofs = {}, {}
    for kind,prefix in [('core','model'),('neural','neural')]:
        expected = {t+(m,) for k,t,m in required if k == kind}
        observed = {}
        with (out/(prefix+'_metrics.csv')).open(newline='') as f:
            for row in csv.DictReader(f):
                key = tuple(row[n] for n in ('outcome','horizon_s','fold','model'))
                require(key not in observed and key in expected, 'duplicate/undeclared metric')
                observed[key] = int(row['test_n'])
                require(observed[key] > 0, 'empty test cohort')
        require(set(observed) == expected, 'missing mandatory metrics')
        prediction_proofs[kind] = validate_predictions(out/(prefix+'_predictions.csv'),observed)
        counts[kind] = len(observed)
    # This receipt can only be written after PCA and all three original postprocessors.
    require(state.get('deferred_memory_jobs') == 0, 'mandatory deferred work remains')
    return dict(required_jobs=[[k,list(t),m] for k,t,m in sorted(required)],
                metrics=counts,predictions=prediction_proofs), remote_roots


def pack_final(out, archive, remote_roots):
    """Preserve every local artifact; explicitly map remote links to verified shards.

    Archives use paths relative to OUT. External shard entries are reconstructed
    from B/C/D archives using external_links in the manifest. Unknown links fail.
    """
    out = pathlib.Path(out).resolve()
    members, external, excluded, rewritten = {}, {}, [], {}
    input_root = out.parent/'joint-inputs-v4-candidate-20261022'
    metadata = {input_root/n:out/n for n in ('excluded_predictor_metadata.csv',
        'model_feature_registry.csv','model_input_receipt.json','model_outcomes.csv','model_sample_master.csv')}
    def add(path):
        path = pathlib.Path(path)
        name = path.relative_to(out).as_posix()
        if name in members or name in external:
            return
        if name in ('model_matrix.jls','parallel-63/shared/raw.bin') or path.name in ('a.bin','b.bin'):
            excluded.append(name)
            return
        # Existing transfer archives are represented by verified S3 references.
        if path.parent == out/'parallel-63' and path.name.startswith('box-') and path.name.endswith('.tar.gz'):
            excluded.append(name)
            return
        target = path.resolve(strict=True)
        for owner, storage in remote_roots.items():
            if target.is_relative_to(storage):
                external[name] = dict(owner=owner,member=target.relative_to(storage).as_posix())
                return
        if path.is_symlink():
            if target in metadata:
                local = metadata[target]
                if path == local:
                    members[name] = target  # Materialize these exact frozen metadata files.
                else:
                    add(local)
                    members[name] = path
                    rewritten[name] = local
                return
            require(target.is_relative_to(out), 'unknown external artifact link: '+name)
            add(target)
        elif path.is_dir():
            for child in sorted(path.iterdir()):
                add(child)
            return
        require(path.is_file() or path.is_symlink(), 'unsupported artifact: '+name)
        members[name] = path
    for child in sorted(out.iterdir()):
        add(child)
    needed = sum(p.stat().st_size for p in members.values() if not p.is_symlink())
    require(shutil.disk_usage(pathlib.Path(archive).parent).free > needed + 1024**3,
            'insufficient free space for complete final archive; EBS retained')
    total = 0
    with tarfile.open(archive,'w:gz',compresslevel=1,dereference=False) as tar:
        for name,path in sorted(members.items()):
            info = tar.gettarinfo(str(path),arcname=name)
            if info.issym():
                target = rewritten.get(name,path.resolve())
                require(target.relative_to(out).as_posix() in members, 'link target omitted: '+name)
                info.linkname = os.path.relpath(target,path.parent).replace(os.sep,'/')
                tar.addfile(info)
            else:
                total += info.size
                with path.open('rb') as f:
                    tar.addfile(info,f)
    return dict(files=len(members),artifact_bytes=total,external_links=external,
                excluded_reproducible_inputs_or_verified_shards=excluded,
                frozen_input_snapshot='snap-0d3e867c1240b6528',
                restoration='Extract A at OUT; extract each verified shard separately; recreate external_links from owner/member.')
