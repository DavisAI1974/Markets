"""Frozen smoke token admission. Local tokenizer work only; never HTTP or model inference."""
import hashlib
import importlib.metadata
from pathlib import Path
from . import granite_run_artifacts as artifacts
# Same image pins as granite_live_controller.measure_fixture; avoid its model imports.
TOKENIZER_FILES={'config.json','generation_config.json','tokenizer.json','tokenizer_config.json',
                 'chat_template.jinja','special_tokens_map.json','vocab.json','merges.txt'}
TOKENIZER_VERSIONS={'transformers':'5.8.0','tokenizers':'0.22.2'}

REQUEST={'model':'granite42-smoke','messages':[{'role':'user','content':'Reply exactly READY.'}],
         'temperature':0,'max_tokens':16,'stream':False,'chat_template_kwargs':{'enable_thinking':False}}
CONTEXT=4096
INVOCATION=dict(tokenize=True,add_generation_prompt=True,enable_thinking=False,
                return_dict=False,truncation=False,padding=False,return_tensors=None)

_REQUEST_BYTES=artifacts.canonical(REQUEST)
_INVOCATION_BYTES=artifacts.canonical(INVOCATION)

def request_bytes():return _REQUEST_BYTES
def invocation():return artifacts.strict_json(_INVOCATION_BYTES)
def _sha(data):return hashlib.sha256(data).hexdigest()


def admit(tokenizer_directory, *, loader=None, version_reader=None, manifest=None):
    """Injected dependencies always label evidence synthetic, never real admission."""
    synthetic=any(value is not None for value in (loader,version_reader,manifest))
    version_reader=version_reader or importlib.metadata.version
    versions={name:version_reader(name) for name in TOKENIZER_VERSIONS}
    if versions!=TOKENIZER_VERSIONS:raise ValueError('pinned tokenizer versions required')
    manifest=manifest or artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    artifacts.validate_manifest(manifest)
    directory=Path(tokenizer_directory)
    if directory.is_symlink() or {p.name for p in directory.iterdir()}!=TOKENIZER_FILES:
        raise ValueError('exact local tokenizer roster required')
    rows=[row for row in manifest['files'] if row['path'] in TOKENIZER_FILES]
    for row in rows:artifacts.verify_file(directory/row['path'],row)
    if loader is None:
        from transformers import AutoTokenizer
        loader=AutoTokenizer.from_pretrained
    tokenizer=loader(str(directory),local_files_only=True,trust_remote_code=False)
    ids=tokenizer.apply_chat_template(artifacts.strict_json(request_bytes())['messages'],**invocation())
    if type(ids) is not list or not ids or any(type(token) is not int or token<0 for token in ids):
        raise ValueError('complete nonempty token IDs required')
    limit=artifacts.strict_json((directory/'config.json').read_bytes()).get('max_position_embeddings')
    if type(limit) is not int or limit<CONTEXT or len(ids)+16>CONTEXT:
        raise ValueError('untruncated input/output exceed admitted context')
    identity=dict(schema='GRANITE_TOKENIZER_MANIFEST_V1',files=rows,versions=versions,invocation=invocation())
    return dict(schema='GRANITE_RUNPOD_TOKEN_ADMISSION_V1',
        evidence_class='SYNTHETIC_TOKENIZER' if synthetic else 'LOCAL_TOKENIZER_ADMISSION',
        request=artifacts.strict_json(request_bytes()),request_sha256=_sha(request_bytes()),
        model_repository=manifest['repository'],model_revision=manifest['revision'],
        model_manifest_sha256=artifacts.manifest_digest(manifest),context=CONTEXT,
        input_tokens=len(ids),output_tokens=16,total_tokens=len(ids)+16,positional_limit=limit,
        token_ids=ids,token_ids_sha256=_sha(artifacts.canonical(ids)),
        tokenizer_manifest=identity,tokenizer_sha256=_sha(artifacts.canonical(identity)))


def validate_receipt(receipt, expected_receipt_sha256, *, allow_synthetic=False):
    """The caller supplies an independently retained hash; no provider truth inferred."""
    if type(receipt) is not dict or _sha(artifacts.canonical(receipt))!=expected_receipt_sha256:
        raise ValueError('token admission receipt pin mismatch')
    synthetic=receipt.get('evidence_class')=='SYNTHETIC_TOKENIZER'
    if receipt.get('evidence_class') not in ('SYNTHETIC_TOKENIZER','LOCAL_TOKENIZER_ADMISSION') or (synthetic and not allow_synthetic):
        raise ValueError('real local tokenizer admission required')
    manifest=artifacts.strict_json(artifacts.DEFAULT_MANIFEST.read_bytes())
    identity=receipt.get('tokenizer_manifest',{})
    ids=receipt.get('token_ids')
    if (receipt.get('schema')!='GRANITE_RUNPOD_TOKEN_ADMISSION_V1'
            or artifacts.canonical(receipt.get('request'))!=request_bytes()
            or receipt.get('request_sha256')!=_sha(request_bytes())
            or receipt.get('model_repository')!=manifest['repository']
            or receipt.get('model_revision')!=manifest['revision']
            or receipt.get('context')!=CONTEXT or type(receipt.get('context')) is not int
            or receipt.get('output_tokens')!=16 or type(receipt.get('output_tokens')) is not int
            or type(ids) is not list or not ids or any(type(t) is not int or t<0 for t in ids)
            or receipt.get('token_ids_sha256')!=_sha(artifacts.canonical(ids))
            or receipt.get('input_tokens')!=len(ids) or type(receipt.get('input_tokens')) is not int
            or receipt.get('total_tokens')!=len(ids)+16 or type(receipt.get('total_tokens')) is not int
            or len(ids)+16>CONTEXT or type(receipt.get('positional_limit')) is not int
            or receipt['positional_limit']<CONTEXT
            or identity.get('schema')!='GRANITE_TOKENIZER_MANIFEST_V1'
            or artifacts.canonical(identity.get('versions'))!=artifacts.canonical(TOKENIZER_VERSIONS)
            or artifacts.canonical(identity.get('invocation'))!=_INVOCATION_BYTES
            or receipt.get('tokenizer_sha256')!=_sha(artifacts.canonical(identity))):
        raise ValueError('token admission is inconsistent with frozen smoke request')
    if not synthetic and (receipt.get('model_manifest_sha256')!=artifacts.manifest_digest(manifest)
            or identity.get('files')!=[r for r in manifest['files'] if r['path'] in TOKENIZER_FILES]):
        raise ValueError('tokenizer/model bytes differ from frozen manifest')
    return request_bytes()
