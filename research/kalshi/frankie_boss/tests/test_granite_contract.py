"""Granite critique contract: frozen prompt bytes, no output caps, honest identity.

The three system prompts were frozen at de27bb26 (tests/fixtures/granite_prompts)
BEFORE granite_contract.py existed and RE-FROZEN on 2026-09-21 when every output cap
left the contract (Greg Davis: no limits on the BOSS's outputs). Every test here runs
against the refactored modules and proves: (1) the rendered prompts are byte-identical
to those fixtures, (2) the validator imposes no count or length cap and keeps the
lower bound on hypotheses,
(3) a contract source change moves every parser identity even when it leaves the
prompt bytes unchanged, and (4) package and standalone imports see one contract.
"""
import asyncio
import hashlib
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
import sys

import pytest

from research.kalshi.frankie_boss import granite_contract as contract
from research.kalshi.frankie_boss import granite_output_schema as schema
from research.kalshi.frankie_boss import granite_parser, granite_prompt, granite_context, granite_context_compact
from research.kalshi.frankie_boss.granite_shadow import parser_code_hash, serve_native_shadow, serve_shadow
from test_granite_parser import snapshot, valid_output

FIXTURES = Path(__file__).with_name('fixtures') / 'granite_prompts'
CONTRACT_FILE = Path(contract.__file__)
# Re-frozen 2026-09-21 (no output caps). A change here is a prompt change and must be deliberate.
FROZEN_SHA256 = {
    'serialized_v2': '39ee5480d95929ca60d35df2a2fb9d2cad9b58bfdef9ff33871cccbf9f993060',
    'native_v1': '214d76a5bb1c44d13e92d96a98110d0a110f974ad42366b524654675f2887930',
    'compact_native_v1': '11360d72fee565ab9f5f4791100d5b4a9a0c5e550264122a0b671a445998a21d',
}
OWNER = {'serialized_v2': granite_prompt, 'native_v1': granite_context, 'compact_native_v1': granite_context_compact}


def identities():
    return {'serialized': parser_code_hash(),
            'native': granite_context.native_parser_code_hash(),
            'compact': granite_context_compact.compact_parser_code_hash()}


def runtime_system_prompt_hash(variant):
    if variant == 'serialized_v2':
        return granite_prompt.build_prompt(snapshot()).system_prompt_hash
    if variant == 'native_v1':
        return granite_context.NativePrompt('t', 'a' * 64).system_prompt_hash
    return granite_context_compact.CompactPrompt('t', 'a' * 64).system_prompt_hash


# --- 1. frozen bytes ---------------------------------------------------------

def test_fixture_index_matches_the_literal_frozen_hashes():
    index = json.loads((FIXTURES / 'frozen_prompt_hashes.json').read_text(encoding='utf-8'))
    assert set(index) == set(FROZEN_SHA256) == set(contract.PROMPT_VARIANTS)
    for variant, entry in index.items():
        data = (FIXTURES / (variant + '.txt')).read_bytes()
        assert b'\r' not in data, ('checkout rewrote fixture line endings; .gitattributes must keep '
                                   'tests/fixtures/granite_prompts/** -text')
        assert entry == {'bytes': len(data), 'sha256': FROZEN_SHA256[variant]}
        assert hashlib.sha256(data).hexdigest() == FROZEN_SHA256[variant]


@pytest.mark.parametrize('variant', contract.PROMPT_VARIANTS)
def test_rendered_prompt_is_byte_identical_to_frozen_fixture(variant):
    frozen = (FIXTURES / (variant + '.txt')).read_bytes()
    rendered = contract.render_system_text(variant).encode('utf-8')
    assert rendered == frozen
    assert OWNER[variant].SYSTEM_TEXT.encode('utf-8') == frozen
    assert contract.system_prompt_hash(variant) == FROZEN_SHA256[variant]
    assert runtime_system_prompt_hash(variant) == FROZEN_SHA256[variant]


def test_contract_values_frozen_at_de27bb26():
    # 2026-09-21: no output caps remain; the only limit value is the lower bound on hypotheses.
    assert contract.LIMITS == contract.GraniteLimits(min_hypotheses=1)
    assert set(vars(contract.LIMITS)) == {'min_hypotheses'}
    assert contract.SCHEMA_VERSION == 'BOSS_GRANITE_OUTPUT_SCHEMA_V1'
    assert contract.REQUIRED_KEY_ORDER == ('schema_version', 'snapshot_hash', 'evidence_refs', 'contradictions',
                                           'missing_evidence', 'hypotheses', 'evidence_verdict')
    assert contract.CONTRACT.evidence_verdicts == ('CONSISTENT', 'CONFLICTED', 'INSUFFICIENT')


# --- 2. single source for the validator ----------------------------------------

def test_schema_and_parser_consume_the_contract_objects():
    assert schema.LIMITS is contract.LIMITS
    assert schema.SCHEMA_VERSION is contract.SCHEMA_VERSION
    assert schema.REQUIRED_KEYS is contract.REQUIRED_KEYS
    assert schema.EVIDENCE_VERDICTS is contract.EVIDENCE_VERDICTS
    assert granite_parser.REQUIRED_KEYS is contract.REQUIRED_KEYS
    assert granite_context.REQUIRED_KEYS is contract.REQUIRED_KEYS
    assert schema.validate_schema(valid_output(snapshot())) is True
    assert schema.validate_schema({}) is False


REF = {'row': 0, 'field': 'mid'}
FORMER_CAPS = {'evidence_refs': 16, 'contradictions': 8, 'missing_evidence': 8, 'hypotheses': 4,
               'note': 200, 'missing_text': 120, 'label': 40}   # the de27bb26 caps, gone since 2026-09-21


def at(name, n):
    out = valid_output(snapshot())
    if name == 'evidence_refs':
        out['evidence_refs'] = [dict(REF)] * n
    elif name == 'contradictions':
        out['contradictions'] = [{'a': dict(REF), 'b': dict(REF), 'note': 'n'}] * n
    elif name == 'missing_evidence':
        out['missing_evidence'] = ['m'] * n
    elif name == 'hypotheses':
        out['hypotheses'] = [{'label': 'h', 'support': [], 'against': []}] * n
    elif name == 'note':
        out['contradictions'] = [{'a': dict(REF), 'b': dict(REF), 'note': 'x' * n}]
    elif name == 'missing_text':
        out['missing_evidence'] = ['x' * n]
    elif name == 'label':
        out['hypotheses'] = [{'label': 'x' * n, 'support': [], 'against': []}]
    return out


@pytest.mark.parametrize('name', sorted(FORMER_CAPS))
def test_validator_imposes_no_cap_above_the_former_boundary(name):
    former = FORMER_CAPS[name]
    assert schema.validate_schema(at(name, former)) is True
    assert schema.validate_schema(at(name, former + 1)) is True
    assert schema.validate_schema(at(name, former * 50 + 1)) is True


def test_hypotheses_lower_bound_is_the_contract_minimum():
    low = contract.LIMITS.min_hypotheses
    assert schema.validate_schema(at('hypotheses', low)) is True
    assert schema.validate_schema(at('hypotheses', low - 1)) is False


def test_support_and_against_carry_no_invented_cap():
    out = valid_output(snapshot())
    many = [dict(REF)] * (FORMER_CAPS['evidence_refs'] + 1)
    out['hypotheses'] = [{'label': 'h', 'support': list(many), 'against': list(many)}]
    assert schema.validate_schema(out) is True
    assert sum(1 for _ in schema.iter_refs(out)) == 1 + 2 * len(many)
    assert not hasattr(contract.LIMITS, 'max_support') and not hasattr(contract.LIMITS, 'max_against')


BAD_REFS = [{'row': '0', 'field': 'mid'}, {'row': 0}, {'field': 'mid'}, {'row': 0, 'field': 'mid', 'x': 1},
            {'row': True, 'field': 'mid'}, {'row': 0, 'field': 1}, {'row': 0.0, 'field': 'mid'},
            ['0', 'mid'], 'mid', None]


@pytest.mark.parametrize('location', ['evidence_refs', 'contradiction_a', 'contradiction_b', 'support', 'against'])
@pytest.mark.parametrize('bad', BAD_REFS)
def test_malformed_references_are_rejected_everywhere(location, bad):
    out = valid_output(snapshot())
    if location == 'evidence_refs':
        out['evidence_refs'] = [bad]
    elif location.startswith('contradiction_'):
        pair = {'a': dict(REF), 'b': dict(REF), 'note': 'n'}
        pair[location[-1]] = bad
        out['contradictions'] = [pair]
    else:
        out['hypotheses'][0][location] = [bad]
    assert schema.validate_schema(out) is False


def test_negative_row_is_shape_valid_here_and_rejected_by_the_scorers():
    """Reference resolution belongs to the scorers (de27bb26); the shape validator must not double-own it."""
    out = valid_output(snapshot())
    out['evidence_refs'] = [{'row': -1, 'field': 'mid'}]
    assert schema.validate_schema(out) is True
    assert not granite_parser.accepts(json.dumps(out), snapshot())


# --- 3. the contract is the only prompt owner -----------------------------------

def test_render_rejects_unknown_variant_and_every_prompt_states_no_cap():
    with pytest.raises(ValueError, match='unknown prompt variant'):
        contract.render_system_text('serialized_v3')
    for variant in contract.PROMPT_VARIANTS:
        text = contract.render_system_text(variant)
        assert 'No cap' in text and 'any count' in text
        assert 'at most' not in text and '0..' not in text and 'bounded prose' not in text


@pytest.mark.parametrize('variant', contract.PROMPT_VARIANTS)
def test_changing_the_lower_bound_moves_the_prompt_hash_visibly(variant):
    higher = replace(contract.CONTRACT, limits=replace(contract.LIMITS, min_hypotheses=2))
    text = higher.render_system_text(variant)
    assert text != contract.render_system_text(variant)
    assert higher.system_prompt_hash(variant) != FROZEN_SHA256[variant]
    assert 'at least 2' in text


@pytest.mark.parametrize('variant', contract.PROMPT_VARIANTS)
def test_render_fails_closed_when_a_contract_value_cannot_reach_the_prompt(variant):
    extra = replace(contract.CONTRACT, evidence_verdicts=contract.CONTRACT.evidence_verdicts + ('UNKNOWN',))
    with pytest.raises(ValueError, match="omits contract value 'UNKNOWN'"):
        extra.render_system_text(variant)
    fewer = replace(contract.CONTRACT, evidence_verdicts=contract.CONTRACT.evidence_verdicts[:2])
    with pytest.raises(ValueError, match='undefined contract slot'):
        fewer.render_system_text(variant)


@pytest.mark.parametrize('kwargs', [dict(min_hypotheses=0), dict(min_hypotheses=-1), dict(min_hypotheses=True),
                                    dict(min_hypotheses=1.0)])
def test_invalid_limits_are_rejected(kwargs):
    with pytest.raises(ValueError):
        contract.GraniteLimits(**kwargs)


# --- 4. honest identity ---------------------------------------------------------

@pytest.fixture
def mutated_contract_source():
    """Append an inert comment to granite_contract.py on disk, restore afterwards."""
    original = CONTRACT_FILE.read_bytes()
    try:
        CONTRACT_FILE.write_bytes(original + b'\n# identity probe: no behaviour change\n')
        yield original
    finally:
        CONTRACT_FILE.write_bytes(original)
    assert CONTRACT_FILE.read_bytes() == original


def test_contract_source_change_moves_every_parser_identity_without_moving_prompt_hashes(mutated_contract_source):
    before_prompts = {v: FROZEN_SHA256[v] for v in contract.PROMPT_VARIANTS}
    CONTRACT_FILE.write_bytes(mutated_contract_source)
    before = identities()
    CONTRACT_FILE.write_bytes(mutated_contract_source + b'\n# identity probe: no behaviour change\n')
    after = identities()
    assert all(after[k] != before[k] for k in before), (before, after)
    # The mutated source still renders the frozen prompt bytes: prompt hash unchanged, parser hashes moved.
    spec = importlib.util.spec_from_file_location('granite_contract_probe', CONTRACT_FILE)
    probe = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = probe  # dataclasses resolves string annotations through sys.modules
    try:
        spec.loader.exec_module(probe)
        assert {v: probe.system_prompt_hash(v) for v in contract.PROMPT_VARIANTS} == before_prompts
    finally:
        del sys.modules[spec.name]


def test_every_pinned_service_rejects_a_contract_change_before_transport(tmp_path, mutated_contract_source):
    from test_granite_shadow import identity
    from test_granite_native_service import native_case
    from test_frankie_controller import build_controller
    CONTRACT_FILE.write_bytes(mutated_contract_source)
    for name in ('native', 'controller'):  # each helper creates its own evidence.sqlite
        (tmp_path / name).mkdir()
    serialized_pin, (native_state, native_pin, _) = identity(), native_case(tmp_path / 'native')
    controller, _, _, request = build_controller(tmp_path / 'controller')
    CONTRACT_FILE.write_bytes(mutated_contract_source + b'\n# identity probe: no behaviour change\n')

    async def transport(request):
        pytest.fail('transport must not be invoked once the contract differs from the pin')

    with pytest.raises(ValueError, match='identity does not match local prompt/schema/parser'):
        asyncio.run(serve_shadow(snapshot(), serialized_pin, request_id='x', timeout_seconds=1, transport=transport))
    with pytest.raises(ValueError, match='identity does not match native prompt/schema/parser'):
        asyncio.run(serve_native_shadow(native_state, native_pin, request_id='x', timeout_seconds=1,
                                        transport=transport))
    with pytest.raises(ValueError, match='critic does not pin selected context prompt/parser/schema'):
        asyncio.run(controller.refresh(**request))


def test_compact_identity_is_transitively_bound_through_native():
    """compact_parser_code_hash = sha256(own bytes + native_parser_code_hash), so no separate list to maintain."""
    expected = hashlib.sha256(Path(granite_context_compact.__file__).read_bytes()
                              + granite_context.native_parser_code_hash().encode()).hexdigest()
    assert granite_context_compact.compact_parser_code_hash() == expected


# --- 5. both import modes ---------------------------------------------------------

def test_standalone_and_package_imports_share_one_contract():
    import granite_contract as standalone
    import granite_output_schema as standalone_schema
    assert standalone is not contract and Path(standalone.__file__) == CONTRACT_FILE
    assert vars(standalone.LIMITS) == vars(contract.LIMITS)
    assert standalone.REQUIRED_KEY_ORDER == contract.REQUIRED_KEY_ORDER
    assert standalone.SCHEMA_VERSION == contract.SCHEMA_VERSION
    for variant in contract.PROMPT_VARIANTS:
        assert standalone.render_system_text(variant) == contract.render_system_text(variant)
        assert standalone.system_prompt_hash(variant) == FROZEN_SHA256[variant]
    assert standalone_schema.LIMITS is standalone.LIMITS
    assert standalone_schema.validate_schema(valid_output(snapshot())) is True
    assert standalone_schema.validate_schema(valid_output(snapshot())) is True


def test_alternate_render_contract_cannot_claim_per_instance_validation():
    higher = replace(contract.CONTRACT, limits=replace(contract.LIMITS, min_hypotheses=2))
    assert 'at least 2' in higher.render_system_text('native_v1')
    assert schema.validate_schema(at('hypotheses', 1)) is True   # the validator reads the real contract, not this one
    assert not hasattr(higher, 'validate')


def test_compact_services_and_controller_reject_changed_contract_before_work(tmp_path, mutated_contract_source):
    from test_granite_compact_service import compact_case, bedrock_config, sagemaker_config
    from test_frankie_compact_controller import build_compact
    from research.kalshi.frankie_boss.granite_bedrock import build_bedrock_service
    from research.kalshi.frankie_boss.granite_sagemaker import build_sagemaker_service
    CONTRACT_FILE.write_bytes(mutated_contract_source)
    (tmp_path / 'state').mkdir()
    (tmp_path / 'controller').mkdir()
    state, pin, _ = compact_case(tmp_path / 'state')
    controller, bridge, critic, request = build_compact(tmp_path / 'controller')
    calls = []
    factory = lambda config: calls.append(config)
    services = (
        build_bedrock_service(enabled=True, config=bedrock_config(), identity=pin, client_factory=factory),
        build_sagemaker_service(enabled=True, config=sagemaker_config(), identity=pin, client_factory=factory),
    )
    CONTRACT_FILE.write_bytes(mutated_contract_source + b'\n# compact route dependency probe\n')
    for service in services:
        with pytest.raises(ValueError, match='selected context prompt/parser/schema'):
            asyncio.run(service.critique_compact(state, request_id='contract-probe'))
    with pytest.raises(ValueError, match='selected context prompt/parser/schema'):
        asyncio.run(controller.refresh(**request))
    assert calls == [] and critic.calls == 0
    assert bridge.book.checkpoint()['count'] == 0
