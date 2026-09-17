"""Synthetic tokenizer files and loaders only: no network or real tokenization."""
import hashlib

import pytest

from research.kalshi.frankie_boss import granite_runpod_tokenizer as m


def synthetic(tmp_path, ids=None):
    manifest = m.artifacts.strict_json(m.artifacts.DEFAULT_MANIFEST.read_bytes())
    for row in manifest['files']:
        if row['path'] in m.TOKENIZER_FILES:
            raw = b'{"max_position_embeddings":131072}' if row['path'] == 'config.json' else b'synthetic'
            (tmp_path / row['path']).write_bytes(raw)
            row.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    calls, loads = [], []
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            calls.append((messages, kwargs))
            return [1, 2, 3] if ids is None else ids
    def loader(path, **kwargs):
        loads.append((path, kwargs))
        return Tokenizer()
    options = dict(served_model_name='granite42-smoke', manifest=manifest,
                   loader=loader, version_reader=m.TOKENIZER_VERSIONS.__getitem__)
    return options, calls, loads


def request(text='Complete Sun prompt \u2600\n' * 1000, **updates):
    value = dict(model='granite42-smoke', messages=[dict(role='user', content=text)],
                 temperature=0, max_tokens=1200, stream=False,
                 chat_template_kwargs=dict(enable_thinking=False))
    value.update(updates)
    return m.artifacts.canonical(value)


def test_full_requests_measured_each_time_and_loaded_once(tmp_path):
    options, calls, loads = synthetic(tmp_path)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    first, second = request(), request('A completely different prompt')
    for body in (first, second):
        assert admit(body) == dict(request_sha256=hashlib.sha256(body).hexdigest(),
            input_tokens=3, output_tokens=1200, context=131072, tokenizer_sha256=admit.tokenizer_sha256)
    assert len(loads) == 1 and loads[0][1] == dict(local_files_only=True, trust_remote_code=False)
    assert calls == [(m.artifacts.strict_json(body)['messages'], m.invocation()) for body in (first, second)]
    assert calls[0][1]['truncation'] is False
    assert admit.evidence_class == 'SYNTHETIC_TOKENIZER'


def test_identity_matches_production_manifest_convention_and_is_defensive(tmp_path):
    options, _, _ = synthetic(tmp_path)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    expected = dict(schema='GRANITE_TOKENIZER_MANIFEST_V1',
        files=[r for r in options['manifest']['files'] if r['path'] in m.TOKENIZER_FILES],
        versions=m.TOKENIZER_VERSIONS, invocation=dict(message_roles=['user'], **m.invocation()))
    assert admit.tokenizer_manifest == expected
    assert admit.tokenizer_sha256 == hashlib.sha256(m.artifacts.canonical(expected)).hexdigest()
    admit.tokenizer_manifest['invocation']['truncation'] = True
    options['manifest']['files'].clear()
    assert admit.tokenizer_manifest == expected


@pytest.mark.parametrize('updates', [dict(model='another'), dict(temperature=0.1), dict(temperature=False),
    dict(stream=0), dict(stream=True), dict(max_tokens=True), dict(max_tokens=0), dict(max_tokens=131073),
    dict(chat_template_kwargs={'enable_thinking': True}), dict(chat_template_kwargs={'enable_thinking': False, 'x': 1}),
    dict(messages=[dict(role='system', content='x')]), dict(messages=[dict(role='user', content='x', extra=1)]),
    dict(messages=[dict(role='user', content='x'), dict(role='user', content='y')]), dict(extra='secret')])
def test_request_drift_rejected_before_tokenization(tmp_path, updates):
    options, calls, _ = synthetic(tmp_path)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    with pytest.raises(ValueError):
        admit(request(**updates))
    assert calls == []


@pytest.mark.parametrize('body', [b'{}', b'not json', b'{"model":"x","model":"y"}',
    b' ' + request('x'), b'x' * (1024 * 1024 + 1), request('x').decode()],
    ids=['missing-fields', 'not-json', 'duplicate-key', 'not-canonical', 'oversized', 'not-bytes'])
def test_malformed_noncanonical_or_oversized_body_rejected(tmp_path, body):
    options, calls, _ = synthetic(tmp_path)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    with pytest.raises(ValueError):
        admit(body)
    assert calls == []


@pytest.mark.parametrize('ids', [[], [True], [-1], [1.5], [1] * (131072 - 1200 + 1), {'input_ids': [1]}])
def test_bad_or_overflow_token_output_refuses(tmp_path, ids):
    options, _, _ = synthetic(tmp_path, ids)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    with pytest.raises(ValueError):
        admit(request('x'))


def test_exact_context_boundary(tmp_path):
    options, _, _ = synthetic(tmp_path, [1] * 2896)
    assert m.LocalTokenizerAdmission(tmp_path, **options)(request('x'))['input_tokens'] == 2896


def test_changed_bytes_during_load_are_not_bound_to_identity(tmp_path):
    options, _, _ = synthetic(tmp_path)
    original = options['loader']
    def changing_loader(*args, **kwargs):
        result = original(*args, **kwargs)
        (tmp_path / 'tokenizer.json').write_bytes(b'changed during load')
        return result
    options['loader'] = changing_loader
    with pytest.raises(ValueError):
        m.LocalTokenizerAdmission(tmp_path, **options)


def test_tokenizer_error_does_not_expose_prompt(tmp_path):
    options, _, _ = synthetic(tmp_path)
    class BrokenTokenizer:
        def apply_chat_template(self, messages, **kwargs):
            raise RuntimeError(messages[0]['content'])
    options['loader'] = lambda *args, **kwargs: BrokenTokenizer()
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    with pytest.raises(ValueError) as error:
        admit(request('PRIVATE_PROMPT_SENTINEL'))
    assert 'PRIVATE_PROMPT_SENTINEL' not in str(error.value)


@pytest.mark.parametrize('damage', ['bytes', 'roster', 'version', 'context', 'position'])
def test_local_evidence_rejected_before_loader(tmp_path, damage):
    options, _, loads = synthetic(tmp_path)
    if damage == 'bytes':
        (tmp_path / 'tokenizer.json').write_bytes(b'wrong')
    elif damage == 'roster':
        (tmp_path / 'extra.json').write_bytes(b'x')
    elif damage == 'version':
        options['version_reader'] = lambda _: 'wrong'
    elif damage == 'context':
        options['context'] = 8192
    else:
        raw = b'{"max_position_embeddings":2048}'
        (tmp_path / 'config.json').write_bytes(raw)
        next(r for r in options['manifest']['files'] if r['path'] == 'config.json').update(
            size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError):
        m.LocalTokenizerAdmission(tmp_path, **options)
    assert loads == []


def test_retired_smoke_context_is_refused_and_the_service_context_is_the_default(tmp_path):
    options, _, _ = synthetic(tmp_path)
    with pytest.raises(ValueError):
        m.LocalTokenizerAdmission(tmp_path, context=4096, **options)
    admit = m.LocalTokenizerAdmission(tmp_path, **options)
    assert admit(request())['context'] == 131072
    # The old 1,200-token output ceiling went with the smoke context: output is bounded by the context alone.
    assert admit(request(max_tokens=8193))['output_tokens'] == 8193
