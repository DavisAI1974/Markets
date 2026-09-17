"""Synthetic tokenizer admission; no model, downloads or network."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from copy import deepcopy
import pytest
from research.kalshi.frankie_boss import granite_runpod_admission as m


def test_standalone_import_needs_no_pytorch():
    code = '''import builtins, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name == 'torch' or name.startswith('torch.'):
        raise AssertionError('token admission must not import PyTorch')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import granite_runpod_admission
assert granite_runpod_admission.CONTEXT == 131072
'''
    subprocess.run([sys.executable, '-c', code, str(Path(m.__file__).parent)],
                   check=True, capture_output=True, timeout=10)


def tokenizer_fixture(tmp_path, ids=None):
    manifest=m.artifacts.strict_json(m.artifacts.DEFAULT_MANIFEST.read_bytes())
    for row in manifest['files']:
        if row['path'] not in m.TOKENIZER_FILES:continue
        data=json.dumps({'max_position_embeddings':131072}).encode() if row['path']=='config.json' else b'synthetic '+row['path'].encode()
        row.update(size=len(data),sha256=hashlib.sha256(data).hexdigest())
        (tmp_path/row['path']).write_bytes(data)
    calls=[]
    class Tokenizer:
        def apply_chat_template(self,messages,**kwargs):
            calls.append((messages,kwargs));return [1,2,3] if ids is None else ids
    def loader(path,**kwargs):
        assert kwargs=={'local_files_only':True,'trust_remote_code':False}
        return Tokenizer()
    return manifest,loader,calls


def admitted(tmp_path,ids=None):
    manifest,loader,calls=tokenizer_fixture(tmp_path,ids)
    receipt=m.admit(tmp_path,manifest=manifest,loader=loader,version_reader=m.TOKENIZER_VERSIONS.__getitem__)
    return receipt,calls


def digest(receipt):return hashlib.sha256(m.artifacts.canonical(receipt)).hexdigest()


def test_exact_request_tokens_and_no_truncation(tmp_path):
    receipt,calls=admitted(tmp_path)
    assert receipt['input_tokens']==3 and receipt['total_tokens']==19
    assert calls[0][0]==[{'role':'user','content':'Reply exactly READY.'}]
    assert calls[0][1]==m.invocation() and calls[0][1]['truncation'] is False
    assert m.validate_receipt(receipt,digest(receipt),allow_synthetic=True)==m.request_bytes()
    with pytest.raises(ValueError):m.validate_receipt(receipt,digest(receipt))


@pytest.mark.parametrize('ids',[[],[True],[-1],[1.0],list(range(131057))])
def test_invalid_or_oversized_token_stream_refuses(tmp_path,ids):
    with pytest.raises(ValueError):admitted(tmp_path,ids)


def test_exact_context_boundary(tmp_path):
    receipt,_=admitted(tmp_path,list(range(131056)))
    assert receipt['total_tokens']==131072


@pytest.mark.parametrize('damage',['request','tokens','context','model','versions','truncation','receipt_pin'])
def test_receipt_drift_refuses_even_with_rehashed_envelope(tmp_path,damage):
    receipt,_=admitted(tmp_path)
    if damage=='request':receipt['request']['messages'][0]['content']='Different'
    elif damage=='tokens':receipt['token_ids'].append(4)
    elif damage=='context':receipt['context']=8192
    elif damage=='model':receipt['model_revision']='a'*40
    elif damage=='versions':receipt['tokenizer_manifest']['versions']['transformers']='latest'
    elif damage=='truncation':receipt['tokenizer_manifest']['invocation']['truncation']=True
    with pytest.raises(ValueError):m.validate_receipt(receipt,'a'*64 if damage=='receipt_pin' else digest(receipt),allow_synthetic=True)


def test_file_drift_refuses_before_loading(tmp_path):
    manifest,_,_=tokenizer_fixture(tmp_path)
    (tmp_path/'tokenizer.json').write_bytes(b'corrupt')
    with pytest.raises(ValueError):m.admit(tmp_path,manifest=manifest,version_reader=m.TOKENIZER_VERSIONS.__getitem__,
                                        loader=lambda *a,**k:pytest.fail('corrupt tokenizer loaded'))


def test_wrong_runtime_version_refuses_before_files(tmp_path):
    with pytest.raises(ValueError):m.admit(tmp_path,version_reader=lambda _: 'wrong',loader=lambda *a,**k:pytest.fail('wrong runtime loaded'))


def test_real_validator_refuses_synthetic_files_relabelled_real(tmp_path):
    receipt,_=admitted(tmp_path);receipt['evidence_class']='LOCAL_TOKENIZER_ADMISSION'
    with pytest.raises(ValueError):m.validate_receipt(receipt,digest(receipt))


def test_receipt_mutation_does_not_change_frozen_invocation(tmp_path):
    receipt,_=admitted(tmp_path)
    receipt['tokenizer_manifest']['invocation']['truncation']=True
    assert m.invocation()['truncation'] is False



def test_lightweight_pins_match_existing_live_controller_without_importing_it():
    import ast
    from pathlib import Path
    source=Path(m.__file__).with_name('granite_live_controller.py').read_text(encoding='utf-8-sig')
    values={n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(source).body
            if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
            and n.targets[0].id in ('TOKENIZER_FILES','TOKENIZER_VERSIONS')}
    assert values['TOKENIZER_FILES']==m.TOKENIZER_FILES
    assert values['TOKENIZER_VERSIONS']==m.TOKENIZER_VERSIONS
