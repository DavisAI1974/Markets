import copy

import pytest

from research.kalshi.frankie_boss import selected_source_scope as selected
from research.kalshi.frankie_boss.causal_prefix import ScopeKind


def test_sunday_scope_preserves_exact_source_and_explicit_development_role():
    manifest = selected.source_manifest()
    scope = selected.source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
    assert scope.kind is ScopeKind.RESULT_BEARING
    assert scope.scope_id == manifest['manifest_hash']
    assert len(scope.members) == 1
    assert scope.members[0].mbo_records == 57027
    assert scope.members[0].sha256 == '4380bd9ba83a5badc4839e12785aa464817b87e3fac11176b951e7b474446d88'
    assert manifest['role'] == 'DEVELOPMENT_TRAINING'
    assert 'source_day' not in manifest
    assert manifest['sampled'] is False


@pytest.mark.parametrize('field,value', [('role', 'HELD_OUT_BLIND'), ('sampled', True)])
def test_changed_scope_is_rejected_even_with_recomputed_self_hash(field, value):
    manifest = copy.deepcopy(selected.source_manifest())
    manifest[field] = value
    manifest['manifest_hash'] = selected.manifest_hash(manifest)
    with pytest.raises(ValueError):
        selected.source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])


def test_independent_scope_pin_is_required():
    with pytest.raises(ValueError):
        selected.source_scope(selected.source_manifest(), expected_manifest_hash='0' * 64)
