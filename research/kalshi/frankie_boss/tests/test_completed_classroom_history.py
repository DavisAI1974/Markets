"""Completed history through real durable adapters and coordinator origins.

Receiver preparation/export and model transport are synthetic boundaries.
The classroom grader, two-turn adapter, host attestations, coordinator,
checkpoint updates and completed-history loader are real.
"""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_boss import feedback_cycle as cycle
from research.kalshi.frankie_boss import sunday_execution as driver
from research.kalshi.frankie_boss.critic_knowledge import CUMULATIVE
from research.kalshi.frankie_boss.dipole_classroom_integration import (
    IntegratedDipoleClassroomPrincipalAdapter, prepare_integrated_cycle,
)
from research.kalshi.frankie_boss.dipole_classroom_learning import completed_history
from research.kalshi.frankie_boss.frankie_principal_adapter import (
    canonical, digest, file_witness,
)
from research.kalshi.frankie_boss.operations.run_actual_sunday_classroom import (
    ClassroomActualHost,
)
from test_feedback_cycle import fixture as coordinator_fixture
from test_frankie_principal_adapter import case as receiver_case
from test_dipole_classroom import _teacher
from test_box_classroom_mode_progression import (
    C, answer_objects, assemble, parse_answers, public_of,
)


def attest(adapter, request, response, turn):
    body = dict(
        schema="FRANKIE_HOST_AGENT_SESSION_ATTESTATION_V1",
        mechanism="AGENT_SESSION",
        request_sha256=digest(request), response_sha256=digest(response),
        session_id=response["session_id"],
        model_identity_as_reported_by_session=response["model_identity_as_reported_by_session"],
    )
    path = adapter.directory / ("host-" + turn + "-record.json")
    path.write_bytes(canonical(dict(body, host_authority="synthetic offline host")))
    return dict(body, host_record=dict(path=str(path), **file_witness(path)))


@pytest.fixture
def completed_run(tmp_path, monkeypatch, request):
    ordinary, checkpoint, arguments, calls = coordinator_fixture(tmp_path, monkeypatch)
    ordinary.close()

    def reopen():
        return cycle.CycleCoordinator(
            tmp_path / "cumulative.sqlite",
            lessons_path=tmp_path / "cumulative-lessons.sqlite",
            frozen_memory_path=tmp_path / "memory-a",
            frozen_memory_sha256=cycle.file_hash(tmp_path / "memory-a"),
            create=not (tmp_path / "cumulative.sqlite").exists(),
            learning_policy=CUMULATIVE,
        )

    store = reopen()
    host = ClassroomActualHost.__new__(ClassroomActualHost)
    host.directory = tmp_path / "host"
    host.directory.mkdir()
    host.config = {"run_id": "history"}
    host.coordinator = store
    host.api = SimpleNamespace(driver=driver)
    dispatched = []
    shared = None
    research_bytes = None
    if getattr(request, 'param', None) == 'science':
        import test_dipole_teacher_discussion as discussion_fixture
        scientific_fixture = discussion_fixture.DiscussionTests()
        scientific_fixture.setUp()
        shared = scientific_fixture.request['shared_knowledge']
        research_bytes = scientific_fixture.fixture.research

    class Controller:
        context_encoding = "stacked_v1"

        async def refresh(self, *, request_id, **kwargs):
            return dict(request_id=request_id, request_hash="e" * 64,
                        status="complete", records=())

    previous_learner = arguments["learner_factory"]

    class Learner(previous_learner):
        def step(self, **kwargs):
            return dict(super().step(**kwargs),
                        feedback_hash=kwargs["feedback"].digest)

    packages = []
    completions = []
    adapters = []

    def complete(index):
        request_id = f"history-cycle-{index:02d}"
        as_of = 2_000_000 + index
        available = 3_000_000 - index * 100
        directory = host.directory / "execution" / f"cycle-{index:02d}"
        directory.mkdir(parents=True)
        learned = completed_history(
            host, request_id=request_id, cutoff_ns=as_of, cycle_index=index
        )
        package = prepare_integrated_cycle(
            _teacher(offset=float(index)),
            request_id=request_id, cycle_index=index, cycle_count=8,
            source_hash="c" * 64, as_of=as_of, through_cursor=6 + index,
            previous_snapshot=None if not packages else packages[-1]["source"],
            history=tuple(completions), learning_history=learned, shared_knowledge=shared,
        )
        for key, filename in (
            ("source", "source"), ("teacher_key", "teacher-key"),
            ("pre_message", "pre-message"), ("binding", "binding"),
        ):
            driver._save(
                directory / ("host-dipole-classroom-" + filename + ".c15.json"),
                package[key],
            )
        base, attachment = receiver_case(directory)
        adapter = IntegratedDipoleClassroomPrincipalAdapter.__new__(
            IntegratedDipoleClassroomPrincipalAdapter
        )
        adapter.__dict__.update(base.__dict__)
        adapter.classroom_package = package
        adapter.directory = directory / "principal"
        adapter.directory.mkdir()
        adapter.audit_directory = directory / "classroom-audit"
        adapter.audit_directory.mkdir()
        adapter.cycle_index = index
        attachment = dict(attachment, dipole_classroom=public_of(package))
        attachment["config_hash"] = adapter._config_hash()
        attachment["attachment_hash"] = digest(
            {key: value for key, value in attachment.items()
             if key != "attachment_hash"}
        )
        adapter.prepare = lambda unused: copy.deepcopy(attachment)

        def transport(request):
            initial = request["schema"] == "FRANKIE_BOSS_SESSION_REQUEST_V1"
            turn = "initial" if initial else "correction"
            dispatched.append((request_id, turn))
            if initial:
                public = public_of(package)
                ledgers = assemble(
                    public, parse_answers(public, answer_objects(package))
                )
                response = dict(
                    session_id="synthetic-session-" + str(index),
                    model_identity_as_reported_by_session="synthetic-principal",
                    request_sha256=digest(request),
                    sections={key: value["sha256"]
                              for key, value in adapter.section_evidence.items()},
                    feedback=dict(
                        request_id=request_id, input_hash="f" * 64,
                        source_hash="c" * 64, available_ns=available, sessions=[],
                    ),
                    lessons=[dict(
                        explanation="COMPLETE_RESEARCH_" + str(index),
                        unsuccessful_idea="FAILED_IDEA_" + str(index),
                        uncertainty="UNRESOLVED_" + str(index),
                    )],
                    **ledgers,
                )
            else:
                parsed = C.parse_correction(json.dumps(dict(
                    what_i_will_change="FULL_CORRECTION_REASONING_" + str(index),
                    remaining_disagreements=[],
                    correction_resolutions=[
                        dict(correction_id=identity,
                             corrected_understanding="CORRECTED_" + identity)
                        for identity in request["correction_ids"]
                    ],
                )), request)
                response = C.correction_response(
                    request, parsed, session_id=request["session_id"],
                    model_identity=request["model_identity_as_reported_by_session"],
                )
            if not initial and shared is not None:
                import test_dipole_teacher_discussion as discussion_fixture
                from research.kalshi.frankie_boss import dipole_scientific_review as science
                scientific_fixture = discussion_fixture.DiscussionTests()
                scientific_fixture.setUp()
                scientific_fixture.request = request['scientific_review_request']
                scientific_fixture.fixture.request = scientific_fixture.request
                scientific_fixture.fixture.descriptor = shared
                scientific_fixture.fixture.research = research_bytes
                scientific_fixture.base = scientific_fixture.fixture.complete()
                scientific_fixture.sources = [dict(source_id='research',content=research_bytes)]
                scientific_fixture.sources += [dict(source_id=key,content=science.canonical(scientific_fixture.request[field]))
                    for key,field in [('initial-response','initial_response'),('fact-review','fact_review'),
                                      ('learning-history','learning_history')]]
                response['dipole_scientific_exchange'] = scientific_fixture.complete()
            return dict(response=response,
                        host_attestation=attest(adapter, request, response, turn))

        adapter.session_executor = transport
        args = dict(arguments, request_id=request_id, principal=adapter,
                    controller_factory=Controller, learner_factory=Learner)
        args["learning_kwargs"] = dict(
            arguments["learning_kwargs"], as_of=as_of,
            through_cursor=6 + index, learning_cutoff_ns=available,
        )
        asyncio.run(store.run(**args))
        assert store._load(request_id, "complete") is not None
        packages.append(package)
        adapters.append(adapter)
        completions.append(json.loads(
            (adapter.directory / "dipole-classroom-completion.json").read_bytes()
        ))

    try:
        complete(0)
        complete(1)
        yield SimpleNamespace(
            host=host, store=store, checkpoint=checkpoint, calls=dispatched,
            packages=packages, adapters=adapters, reopen=reopen, research_bytes=research_bytes,
        )
    finally:
        host.coordinator.close()
        checkpoint.close()


def load_next(run):
    return completed_history(
        run.host, request_id="history-cycle-02",
        cutoff_ns=1, cycle_index=2,
    )


def test_completed_loader_carries_both_full_exchanges_and_reopens_without_dispatch(
    completed_run,
):
    run = completed_run
    before = list(run.calls)
    value = load_next(run)
    assert [row["origin"]["request_id"] for row in value["exchanges"]] == [
        "history-cycle-00", "history-cycle-01",
    ]
    assert [entry["record"]["available_ns"]
            for entry in value["knowledge"]["entries"]] == [3_000_000, 2_999_900]
    for index, exchange in enumerate(value["exchanges"]):
        principal = run.adapters[index].directory
        initial = json.loads((principal / "session-response.json").read_bytes())
        corrected = json.loads(
            (principal / "classroom-correction-response.json").read_bytes()
        )
        assert exchange["frankie_response"] == initial["response"]
        assert exchange["frankie_correction_response"] == corrected["response"]
        assert exchange["completion"]["teacher_complete"] is True
        assert "FAILED_IDEA_" + str(index) in json.dumps(exchange)
        assert "UNRESOLVED_" + str(index) in json.dumps(exchange)
        assert "FULL_CORRECTION_REASONING_" + str(index) in json.dumps(exchange)
    run.store.close()
    run.host.coordinator = run.reopen()
    assert load_next(run) == value
    assert run.calls == before


@pytest.mark.parametrize("section, field, replacement", [
    ("pre_message", "teacher_opening", "FORGED_PRIOR_TEACHING"),
    ("source", "source_hash", "9" * 64),
    ("source", "request_id", "another-request"),
    ("source", "as_of", 1),
    ("source", "through_cursor", 5),
])
def test_completed_loader_rejects_changed_original_package(
    completed_run, section, field, replacement
):
    run = completed_run
    # Establish a valid fixture before changing only one retained field.
    assert len(load_next(run)["exchanges"]) == 2
    directory = run.host.directory / "execution" / "cycle-00"
    filename = "pre-message" if section == "pre_message" else "source"
    path = directory / ("host-dipole-classroom-" + filename + ".c15.json")
    retained = driver._load(path)
    assert field in retained
    retained[field] = replacement
    # Deliberate test corruption bypasses the writer's immutable-file guard.
    path.write_bytes(driver.canonical_bytes(driver.pack(retained)))
    before = list(run.calls)

    with pytest.raises(ValueError):
        load_next(run)
    assert run.calls == before


def test_completed_loader_rejects_changed_frozen_session_request(completed_run):
    run = completed_run
    assert len(load_next(run)["exchanges"]) == 2
    path = run.adapters[0].directory / "session-request.json"
    request = json.loads(path.read_bytes())
    request["instruction"] += "\nFORGED_FROZEN_REQUEST"
    path.write_bytes(canonical(request))
    with pytest.raises(ValueError):
        load_next(run)


def test_completed_loader_refuses_an_omitted_completed_origin(completed_run):
    run = completed_run
    with run.store.lessons:
        run.store.lessons.execute(
            "DELETE FROM lessons WHERE request=?", ("history-cycle-00",)
        )
    with pytest.raises(ValueError):
        load_next(run)


@pytest.mark.parametrize("completed_run",["science"],indirect=True)
def test_completed_scientific_history_restores_all_attested_conversations_without_dispatch(completed_run):
    from research.kalshi.frankie_boss import dipole_scientific_history as scientific_history
    run=completed_run
    before=list(run.calls)
    value=load_next(run)
    for index,entry in enumerate(value['exchanges']):
        view=entry['frankie_correction_response']['dipole_scientific_exchange']
        assert view['schema']==scientific_history.SCHEMA
        original=json.loads((run.adapters[index].directory/'classroom-correction-response.json').read_bytes())
        restored=scientific_history.restore(view,
            request_fields=entry['teacher_correction_without_repeated_history']['scientific_review_request'],
            initial_response=entry['frankie_response'],prior_exchanges=value['exchanges'][:index],
            resolve_source=lambda source_id:run.research_bytes)
        assert restored==original['response']['dipole_scientific_exchange']
        assert entry['scientific_delivery_artifact']['response_sha256']==digest(original['response'])
        assert 'FAILED_IDEA_'+str(index) in json.dumps(entry)
        discussion=restored['teacher_discussion']['entries'][0]
        assert discussion['boss_teacher']['parsed']['position']=='DISAGREE'
        assert discussion['classroom_teacher']['parsed']['position']=='AGREE'
        assert discussion['frankie']['parsed']['position']=='UNRESOLVED'
        assert entry['completion']['teacher_complete'] is True
    run.store.close()
    run.host.coordinator=run.reopen()
    assert load_next(run)==value
    assert run.calls==before
