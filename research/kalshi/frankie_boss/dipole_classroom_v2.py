"""Classroom package V2 = the integrated classroom package, unchanged, plus the BOSS teacher's external section
(dipole_classroom_external.py: Frankie's historical data points beside the 19 Dipole columns).

The V1 package is built by the SAME call with the SAME arguments (dipole_classroom_integration.prepare_integrated_cycle),
so its source snapshot, teacher key, pre-message and binding, and the grade computed from them, are exactly what the
experiment's classroom arm produces without the external section. The external section reads the V1 snapshot's rows and
never writes into the V1 package: the four recorded V1 hashes are checked unchanged after it is attached, and the external
key's Dipole directions must equal the V1 key's for every column (both keys describe the same rows).

The model-visible classroom V2 is {'dipole_classroom': the V1 model-visible classroom (byte-identical),
'dipole_external': the external section's model-visible part}. Nothing pinned is edited.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import dipole_classroom_external as EXT
from .c15_normalizer import COLUMNS
from .dipole_classroom_final_review import final_model_visible_classroom
from .dipole_classroom_integration import prepare_integrated_cycle

SCHEMA = 'DIPOLE_CLASSROOM_PACKAGE_V2'
V1_HASHES = (('source', 'source_snapshot_hash'), ('teacher_key', 'teacher_key_hash'),
             ('pre_message', 'teacher_message_hash'), ('binding', 'classroom_binding_hash'))


def _v1_hashes(v1):
    return {part: v1[part][field] for part, field in V1_HASHES}


def prepare_cycle_v2(teacher: Mapping[str, Any], *, request_id: str, cycle_index: int, cycle_count: int, source_hash: str,
                     as_of: int, through_cursor: int, history: Sequence[Mapping[str, Any]] = (),
                     prior_grade: Mapping[str, Any] | None = None, section_directory, day_file, day_file_sha256,
                     trading_day, prior_external_grade: Mapping[str, Any] | None = None, built_by='classroom V2') -> dict:
    v1 = prepare_integrated_cycle(teacher, request_id=request_id, cycle_index=cycle_index, cycle_count=cycle_count,
                                  source_hash=source_hash, as_of=as_of, through_cursor=through_cursor, history=history,
                                  prior_grade=prior_grade)
    before = _v1_hashes(v1)
    key, section_receipt = EXT.ensure_external_section(section_directory, v1['source'], day_file, day_file_sha256,
                                                       trading_day=trading_day, built_by=built_by)
    v1_dirs = {d['name']: d['first_to_last_present_direction'] for d in v1['teacher_key']['dimensions']}
    if any(key['dipole_directions'][c] != v1_dirs[c] for c in COLUMNS):
        raise ValueError('the external section and the classroom key read the Dipole rows differently; refused')
    if key['cutoff_ns'] != as_of:
        raise ValueError('the external section was read at another cutoff than the classroom as_of; refused')
    mode = v1['binding']['mode']
    pre = EXT.build_external_pre_message(key, mode=mode, prior_grade=prior_external_grade)
    binding = EXT.build_external_binding(key, pre, v1_binding=v1['binding'])
    after = _v1_hashes(v1)
    if after != before:
        raise ValueError('the V1 classroom package changed while the external section was attached; refused')
    return dict(schema=SCHEMA, v1=v1, external=dict(teacher_key=key, pre_message=pre, binding=binding,
                                                    section_receipt=section_receipt),
                v1_unchanged=dict(hashes=before, checked_after_attach=True))


def model_visible_v2(package: Mapping[str, Any]) -> dict:
    if package.get('schema') != SCHEMA:
        raise ValueError('a classroom package V2 is required')
    ext = package['external']
    return {'dipole_classroom': final_model_visible_classroom(package['v1']),
            'dipole_external': EXT.model_visible_external(ext['binding'], ext['pre_message'])}

