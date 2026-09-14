"""The BLD-1 output-shape finding, tested against the actual contracts.

The Codex Slice-1 preflight proposed asserting that the protected legacy BLD-1
prompt's OUTPUT field list equals ``frankie_contract.BLD1_FIELD_NAMES`` and stopped
because the prompt names eleven fields while the contract names twelve
(``disposition``). Tracing the callers shows these are two distinct interfaces,
not one stale prompt and not a two-stage transform:

* ``store/sop_templates.json`` BLD-1 (round-trip tested against RUN_SOP.md by
  ``spawn.py``) tells a walk specialist to WRITE ``forecasts/g{N}_perday/...json``.
  That file is consumed by walk tooling (``path_contract.py``, ``merge_perday.py``,
  the coordinators). Nothing in that path imports ``frankie_contract``.
* ``frankie_contract.BLD1_FIELDS`` / ``validate_bld1`` is the BOSS projection
  target. Its only producers are ``FrankieProjector.abstain/project/project_internal``
  and ``frankie_category_free.category_free_abstain``, all deterministic Python
  that SET ``disposition`` themselves (``frankie_contract.py`` lines 465, 520,
  ``frankie_category_free.py`` line 103). No module parses a model emission into
  ``validate_bld1``. ``disposition`` was already present in the supplied
  checkpoint (``provenance/supplied_checkpoint/frankie_contract.py``), so the
  contract did not grow a field after the prompt was written.

These tests freeze that relationship so a future change to either shape, or a
new caller that feeds a model emission into ``validate_bld1``, fails loudly and
records an ownership decision instead of a silent drift.
"""
import json
from pathlib import Path
import re

import pytest

try:
    from research.kalshi.frankie_boss.frankie_contract import (
        BLD1_FIELD_NAMES, ContractError, Disposition, FrankieProjector, validate_bld1,
    )
except ImportError:  # standalone package-directory import
    from frankie_contract import BLD1_FIELD_NAMES, ContractError, Disposition, FrankieProjector, validate_bld1

PACKAGE = Path(__file__).resolve().parents[1]
TEMPLATE_STORE = PACKAGE.parent / 'store' / 'sop_templates.json'
LEGACY_BLD1_MODEL_EMISSION_FIELDS = (
    'specialist', 'group', 'date', 'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve',
    'reasoning', 'plays_fired', 'plays_stood_down', 'confidence', 'state_defects_and_gaps_reported',
)


def legacy_bld1_output_fields():
    """Field names, in order, from the protected BLD-1 template's OUTPUT JSON shape."""
    store = json.loads(TEMPLATE_STORE.read_text(encoding='utf-8'))
    body = next(t['body'] for t in store['templates'] if t['name'] == 'BLD-1')
    start = body.index('OUTPUT')
    shape = body[body.index('{', start):body.index('plus handoff_out', start)]
    return tuple(re.findall(r'"([a-z0-9_]+)":', shape))


def test_protected_legacy_prompt_emits_eleven_fields_in_order():
    assert legacy_bld1_output_fields() == LEGACY_BLD1_MODEL_EMISSION_FIELDS


def test_boss_contract_is_the_legacy_emission_plus_deterministic_disposition():
    legacy = legacy_bld1_output_fields()
    assert BLD1_FIELD_NAMES[:len(legacy)] == legacy
    assert BLD1_FIELD_NAMES[len(legacy):] == ('disposition',)
    assert set(BLD1_FIELD_NAMES) - set(legacy) == {'disposition'}


def _heads():
    return {'guessed_net_usd': 100.0, 'overnight_gap_usd': 40.0,
            'path_p50_curve': [[20, 0.0], [22, 10.0], [24, 60.0]], 'confidence': 'med'}


def test_legacy_emission_alone_is_not_a_validate_bld1_input():
    """An eleven-field emission is refused by the BOSS validator: the two shapes never meet."""
    payload = {**_heads(), 'specialist': 'A', 'group': 'g1', 'date': '20260914', 'reasoning': 'read',
               'plays_fired': [], 'plays_stood_down': [], 'state_defects_and_gaps_reported': []}
    assert set(payload) == set(LEGACY_BLD1_MODEL_EMISSION_FIELDS)
    with pytest.raises(ContractError, match=r"absent fields: \['disposition'\]"):
        validate_bld1(payload)


def test_projector_sets_disposition_itself_never_reading_it_from_an_emission():
    projector = FrankieProjector('A', 'g1')
    called = projector.project('20260914', _heads(), 'p' * 64, 'm/1', reasoning='read')
    assert called.payload['disposition'] == Disposition.CALL.value
    abstained = projector.abstain('20260914', ['defect'], 'p' * 64, 'm/1')
    assert abstained.payload['disposition'] == Disposition.ABSTAIN.value
    for record in (called, abstained):
        assert tuple(record.payload) == BLD1_FIELD_NAMES


def test_no_module_feeds_a_model_emission_into_validate_bld1():
    """Fail closed: a new validate_bld1 caller must record its ownership decision here."""
    owners = {'frankie_contract.py'}
    callers = sorted(path.name for path in PACKAGE.glob('*.py')
                     if 'validate_bld1(' in path.read_text(encoding='utf-8'))
    assert set(callers) == owners, (
        'validate_bld1 gained a caller outside the deterministic projector; decide whether it '
        'parses a model emission and, if so, where disposition is owned: %s' % callers)
