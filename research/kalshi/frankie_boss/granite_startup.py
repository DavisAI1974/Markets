"""Verify mounted Granite bytes before the real vLLM server can start.

Selected image's standard-supervisor command override is documented by AWS:
https://github.com/aws/model-hosting-container-standards/blob/main/python/model_hosting_container_standards/supervisor/README.md
The bootstrap is a separate AdditionalModelDataSource, never an added weight file.
"""
import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

try:
    from . import granite_run_artifacts as artifacts
except ImportError:
    import granite_run_artifacts as artifacts

IMAGE_DIGEST = 'sha256:18998be4e1276d4eb6e98afe80798aa357c1cc37545150de5c210bc9111beb1d'
BOOTSTRAP_PATH = '/opt/ml/additional-model-data-sources/bootstrap/granite_startup.py'
COMMAND = 'python3 ' + BOOTSTRAP_PATH
IMAGE_IDENTITY_FILE = Path(__file__).with_name('granite_image_identity.json')


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def launch_environment(*, max_model_len, served_model):
    if type(max_model_len) is not int or max_model_len <= 0:
        raise ValueError('explicit positive runtime context required')
    if type(served_model) is not str or not re.fullmatch('[A-Za-z0-9_.-]{1,100}', served_model):
        raise ValueError('explicit served model name required')
    return {
        'SUPERVISOR_PROGRAM__APP_COMMAND': COMMAND,
        'SUPERVISOR_PROGRAM__APP_AUTORESTART': 'false',
        'SUPERVISOR_PROGRAM__APP_STARTRETRIES': '0',
        # Keep the documented supervisor path active; disabling PROCESS_AUTO_RECOVERY
        # bypasses supervisor overrides in the selected package.
        'PROCESS_AUTO_RECOVERY': 'true',
        'STANDARD_AUTO_INSTALL_REQ': 'false',
        'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1',
        'HF_HUB_DISABLE_TELEMETRY': '1',
        'VLLM_NO_USAGE_STATS': '1',
        'GRANITE_MAX_MODEL_LEN': str(max_model_len),
        'GRANITE_SERVED_MODEL': served_model,
        'GRANITE_IMAGE_DIGEST': IMAGE_DIGEST,
        'GRANITE_IMAGE_IDENTITY_SHA256': digest_file(IMAGE_IDENTITY_FILE),
        'GRANITE_BOOTSTRAP_SHA256': digest_file(__file__),
        'GRANITE_VERIFIER_SHA256': digest_file(artifacts.__file__),
        'GRANITE_MANIFEST_SHA256': artifacts.manifest_digest(artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())),
    }


def runtime_facts():
    import torch
    packages = {name: importlib.metadata.version(name) for name in
                ('torch', 'transformers', 'tokenizers', 'vllm', 'model-hosting-container-standards')}
    count = torch.cuda.device_count()
    properties = torch.cuda.get_device_properties(0) if count == 1 else None
    driver = subprocess.run(['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                            capture_output=True, text=True, check=True, timeout=10).stdout.strip()
    import model_hosting_container_standards.supervisor.generator as generator
    import model_hosting_container_standards.supervisor.models as models
    import model_hosting_container_standards.supervisor.scripts.standard_supervisor as supervisor
    return {'packages': packages, 'python': platform.python_version(), 'cuda': torch.version.cuda,
            'gpu_count': count, 'gpu': properties.name if properties else None,
            'gpu_total_memory': properties.total_memory if properties else None,
            'driver': driver, 'source_sha256': {
                'model_hosting_container_standards/supervisor/generator.py': digest_file(generator.__file__),
                'model_hosting_container_standards/supervisor/models.py': digest_file(models.__file__),
                'model_hosting_container_standards/supervisor/scripts/standard_supervisor.py': digest_file(supervisor.__file__),
                '/usr/local/bin/sagemaker_entrypoint.sh': digest_file('/usr/local/bin/sagemaker_entrypoint.sh')}}


def prepare_startup(directory, manifest, environment, *, runtime_facts=runtime_facts):
    directory = Path(directory)
    try:
        length = int(environment['GRANITE_MAX_MODEL_LEN'])
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('explicit runtime context required') from exc
    expected = launch_environment(max_model_len=length, served_model=environment.get('GRANITE_SERVED_MODEL'))
    expected['GRANITE_MANIFEST_SHA256'] = artifacts.manifest_digest(manifest)
    if any(environment.get(key) != value for key, value in expected.items()):
        raise ValueError('startup identity/configuration mismatch')
    controlled = ('SUPERVISOR_', 'SM_VLLM_', 'GRANITE_', 'STANDARD_', 'HF_MODEL_ID')
    if any(key.startswith(controlled) and key not in expected for key in environment):
        raise ValueError('unapproved startup override')
    mount = artifacts.verify_directory(directory, manifest)
    facts = runtime_facts()
    if facts.get('gpu_count') != 1:
        raise ValueError('exactly one GPU required')
    image_identity = artifacts.strict_json(IMAGE_IDENTITY_FILE.read_bytes())
    if (facts.get('source_sha256') != image_identity['source_sha256'] or
            facts.get('packages', {}).get('model-hosting-container-standards') != image_identity['supervisor_version'] or
            facts.get('packages', {}).get('vllm') != '0.20.2'):
        raise ValueError('installed runtime source/version mismatch')
    argv = ['python3', '-m', 'vllm.entrypoints.openai.api_server', '--host', '0.0.0.0', '--port', '8080',
            '--model', str(directory), '--tokenizer', str(directory), '--served-model-name', environment['GRANITE_SERVED_MODEL'],
            '--dtype', 'bfloat16', '--tensor-parallel-size', '1', '--pipeline-parallel-size', '1',
            '--data-parallel-size', '1', '--max-num-seqs', '1', '--max-model-len', str(length),
            '--gpu-memory-utilization', '0.9', '--generation-config', 'vllm']
    return {'schema': 'GRANITE_STARTUP_RUNTIME_V1', 'mount': mount, 'runtime': facts,
            'image_digest': IMAGE_DIGEST, 'bootstrap_sha256': digest_file(__file__),
            'argv': argv, 'environment': expected,
            'generation_policy': {'temperature': 0, 'thinking': False, 'output_limit': 'explicit request max_tokens',
                                  'quantization': 'none', 'adapters': False, 'speculative_decoding': False}}


def bootstrap_manifest():
    files = [Path(__file__), Path(artifacts.__file__), artifacts.DEFAULT_MANIFEST, IMAGE_IDENTITY_FILE]
    return {'schema': 'GRANITE_BOOTSTRAP_MANIFEST_V1', 'files': [
        {'path': path.name, 'size': path.stat().st_size, 'sha256': digest_file(path)}
        for path in sorted(files)]}


def stage_bootstrap(client, bucket, receipt_path):
    """Stage only four reviewed bootstrap files, separately from model artifacts."""
    manifest = bootstrap_manifest()
    digest = hashlib.sha256(artifacts.canonical(manifest)).hexdigest()
    prefix = 'models/bootstrap/' + digest + '/'
    expected = {prefix + row['path']: row['size'] for row in manifest['files']}
    existing = artifacts.listed_objects(client, bucket, prefix)
    if any(key not in expected or expected[key] != size for key, size in existing.items()):
        raise ValueError('bootstrap S3 roster mismatch')
    receipt = {'schema': 'GRANITE_BOOTSTRAP_STAGING_V1', 'status': 'staging', 'manifest': manifest,
               'manifest_sha256': digest, 'prefix': prefix, 'files': []}
    artifacts.save_receipt(receipt_path, receipt)
    for row in manifest['files']:
        if prefix + row['path'] in existing:
            receipt['files'].append(artifacts.verify_s3_object(client, bucket, prefix, row))
            artifacts.save_receipt(receipt_path, receipt)
    for row in manifest['files']:
        if prefix + row['path'] in existing:
            continue
        client.upload_file(str(Path(__file__).with_name(row['path'])), bucket, prefix + row['path'],
                           ExtraArgs={'ServerSideEncryption': 'AES256'})
        receipt['files'].append(artifacts.verify_s3_object(client, bucket, prefix, row))
        artifacts.save_receipt(receipt_path, receipt)
    if artifacts.listed_objects(client, bucket, prefix) != expected:
        raise ValueError('final bootstrap S3 roster mismatch')
    receipt['status'] = 'verified'
    artifacts.save_receipt(receipt_path, receipt)
    return receipt


def main():
    manifest = artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    receipt = prepare_startup('/opt/ml/model', manifest, os.environ)
    path = Path('/tmp/granite-startup-receipt.json')
    artifacts.save_receipt(path, receipt)
    # Retained in endpoint CloudWatch logs before launch/readiness. Not hardware attestation.
    print('GRANITE_STARTUP_RECEIPT ' + artifacts.canonical(receipt).decode(), flush=True)
    os.execvp(receipt['argv'][0], receipt['argv'])


if __name__ == '__main__':
    main()
