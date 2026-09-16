from research.kalshi.frankie_boss.c15_normalizer import COLUMNS
from research.kalshi.frankie_boss.dipole_classroom import GRADE_SCHEMA, KEY_SCHEMA, MESSAGE_SCHEMA, PAIR_COUNT, ClassroomMode
from research.kalshi.frankie_boss.dipole_classroom_final_review import NOVEL_FINDING_SCHEMA, apply_relationship_view_crosscheck, build_final_correction_request, final_model_visible_classroom, investigate_novel_findings, validate_novel_findings


def _package(mode):
    pre={"schema":MESSAGE_SCHEMA,"request_id":"r","cycle_index":0,"mode":mode,"teacher_key_hash":"a"*64,"coverage_columns":tuple(COLUMNS),"coverage_count":len(COLUMNS),"relationship_pairs_required":PAIR_COUNT,"prior_cycle_correction":None,"teacher_opening":"teacher","components":tuple({"name":name,"role":"role","behavior_basis":"basis","unit":"u","required_review":"review","teacher_explanation":"teach"} for name in COLUMNS),"relationship_review":None,"relationship_instruction":"pairs","teachback_instruction":"teach back","future_wall":"wall","direction_definition":"first PRESENT to last PRESENT","novelty_invitation":"find something new","teacher_message_hash":"b"*64}
    return {"source":{"schema":"DIPOLE_CLASSROOM_SOURCE_V1","source_snapshot_hash":"c"*64},"teacher_key":{"schema":KEY_SCHEMA,"source_snapshot_hash":"c"*64,"teacher_key_hash":"a"*64,"coverage_count":len(COLUMNS),"relationship_pairs_scanned":PAIR_COUNT},"pre_message":pre,"binding":{"source_snapshot_hash":"c"*64,"teacher_key_hash":"a"*64,"teacher_message_hash":"b"*64,"mode":mode}}


def test_discovery_eligibility_starts_at_socratic(monkeypatch):
    from research.kalshi.frankie_boss import dipole_classroom_final_review as final
    monkeypatch.setattr(final,"validate_package",lambda value:dict(value))
    assert final_model_visible_classroom(_package(ClassroomMode.TEACH.value))["independent_discovery_eligible"] is False
    assert final_model_visible_classroom(_package(ClassroomMode.GUIDED.value))["independent_discovery_eligible"] is False
    assert final_model_visible_classroom(_package(ClassroomMode.SOCRATIC.value))["independent_discovery_eligible"] is True


def test_novel_finding_changes_only_specific_contradicted_instance():
    raw=[{"schema":NOVEL_FINDING_SCHEMA,"finding_id":"new-1","premise":"A broader structure may be developing.","why_novel":"Dipole did not teach this combined mechanism.","evidence_refs":[{"kind":"DIPOLE_OBSERVATION","component":COLUMNS[0],"cursor":7,"claimed_state":"PRESENT","claimed_value":99.0,"reasoning":"This observation is part of the premise."}],"future_outcome_claimed":False}]
    findings=validate_novel_findings(raw,{"teacher_message_hash":"b"*64})
    key={"dimensions":[{"name":COLUMNS[0],"observations":({"cursor":7,"state":"PRESENT","value":4.25},)}],"relationship_scan":()}
    investigation=investigate_novel_findings(key,findings,mode=ClassroomMode.SOCRATIC.value)
    item=investigation["findings"][0]
    assert item["scored_for_classroom_mastery"] is False
    assert item["premise_disposition"]=="RETAIN_AS_NOVEL_HYPOTHESIS"
    assert item["specific_data_differences"][0]["data_shows"]["value"]==4.25
    text=item["specific_data_differences"][0]["message"].lower()
    assert "data is showing" in text and "broader premise" in text and "wrong" not in text


def test_other_causal_evidence_is_not_rejected():
    raw=[{"schema":NOVEL_FINDING_SCHEMA,"finding_id":"new-2","premise":"FIFO interaction may define a new family.","why_novel":"This relationship is outside the existing Dipole pair key.","evidence_refs":[{"kind":"OTHER_CAUSAL_EVIDENCE","evidence_pointer":"principal/full-book/fifo","description":"A FIFO/full-book structure Frankie observed.","reasoning":"The structure moved with Dipole persistence."}],"future_outcome_claimed":False}]
    findings=validate_novel_findings(raw,{"teacher_message_hash":"b"*64})
    investigation=investigate_novel_findings({"dimensions":[],"relationship_scan":()},findings,mode=ClassroomMode.GUIDED.value)
    item=investigation["findings"][0]
    assert item["status"]=="PARTIALLY_TESTABLE_NOVEL_HYPOTHESIS"
    assert item["premise_disposition"]=="RETAIN_AS_NOVEL_HYPOTHESIS"
    assert item["independent_discovery_eligible"] is False


def test_relationship_records_are_crosschecked():
    left,right=COLUMNS[:2]
    grade={"schema":GRADE_SCHEMA,"post_grade_hash":"c"*64,"correction_ids":(),"mastered":True}
    response={"dipole_teachback":{"components":[{"name":left,"relationships":[{"with":right,"relation":"SAME_DIRECTION","explanation":"component view"}]}]},"dipole_relationship_scan":[{"left":left,"right":right,"direction_relation":"OPPOSITE_DIRECTION"}]}
    checked=apply_relationship_view_crosscheck(grade,response)
    assert checked["mastered"] is False
    assert f"representation:{left}:{right}" in checked["correction_ids"]


def test_final_correction_uses_data_showing_language_without_full_grade():
    name=COLUMNS[0]
    grade={"schema":GRADE_SCHEMA,"post_grade_hash":"c"*64,"correction_ids":(f"component:{name}",),"mastered":False,"component_grades":(),"exhaustive_audit":{"coverage_proven":True},"relationship_view_crosscheck":{"inconsistencies":()}}
    key={"dimensions":[{"name":name,"state_counts":{"PRESENT":2,"MISSING":0,"INVALID":0,"ABLATED":0},"terminal_state":"PRESENT","first_to_last_present_direction":"RISE"}],"relationship_scan":()}
    teachback={"components":[{"name":name,"state_counts":{"PRESENT":2,"MISSING":0,"INVALID":0,"ABLATED":0},"terminal_state":"PRESENT","direction":"FALL"}],"observation_review":()}
    novelty={"schema":"DIPOLE_NOVELTY_INVESTIGATION_V1","mode":"TEACH","findings":(),"finding_count":0,"scored_for_classroom_mastery":False,"investigation_bundle_hash":"d"*64}
    request=build_final_correction_request(original_request_sha256="e"*64,response={"session_id":"s","model_identity_as_reported_by_session":"frankie"},grade=grade,key=key,teachback=teachback,novelty_investigation=novelty)
    rendered=repr(request).lower()
    assert "post_grade" not in request and "exhaustive_audit" not in request
    assert "data is showing" in rendered and "wrong" not in rendered
