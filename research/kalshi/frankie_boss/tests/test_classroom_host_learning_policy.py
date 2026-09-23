"""Host wiring and training identities; no production or model calls."""
import asyncio
from contextlib import nullcontext
import copy
import json
from types import SimpleNamespace

import pytest

from research.kalshi.frankie_boss.c15_journal import evidence_hash
from research.kalshi.frankie_boss.critic_knowledge import CUMULATIVE
from research.kalshi.frankie_boss import granite_positive_priming as priming
from research.kalshi.frankie_boss.operations import run_actual_sunday as base
from research.kalshi.frankie_boss.operations import run_actual_sunday_classroom as classroom

HOSTS = [base.ActualHost, classroom.ClassroomActualHost]


def make_host(host_class, tmp_path, monkeypatch, *, policy=None, capsule=False):
    """Exercise run() without constructing resources or an actual coordinator."""
    host = host_class.__new__(host_class)
    events = []
    capture = {}
    coordinator = object()

    def witness(name):
        return {"path": str(tmp_path / name), "sha256": "a" * 64}

    host.config = dict(
        run_id="run",
        memory=witness("memory"),
        mapping=witness("mapping"),
        receiver_root=str(tmp_path / "receiver"),
        receiver_commit="b" * 40,
        retained_witnesses=witness("retained"),
        delivery_receipt=witness("delivery"),
        calculation_result=witness("result"),
        contract=witness("contract"),
        principal_admission={"enabled": True},
    )
    if policy is not None:
        host.config["learning_policy"] = policy
    if capsule:
        host.config["critic_priming"] = dict(
            mode=priming.MODE,
            profile="retained_cycle00_20260921",
        )
    host.host = dict(
        repository=str(tmp_path / "repository"),
        context_encoding="stacked_v1",
        schedule=witness("schedule"),
        boss_commit="c" * 40,
        state_defects_and_gaps_reported=True,
    )
    host.directory = tmp_path
    host.phase = lambda *a, **kw: None
    host.probe = object()
    host.principal_host_lock = object()
    host.runtime = lambda *a, **kw: None
    host.cycle_limit = 7

    def save(name, value):
        events.append(("save", name))
        capture.setdefault("saved", {})[name] = copy.deepcopy(value)

    def load_capsule(repository, *, mode):
        events.append(("load_capsule", repository, mode))
        return {"mode": priming.MODE, "retained_capsule_sentinel": True}

    def coordinator_factory(path, **kwargs):
        events.append(("coordinator",))
        capture["coordinator_path"] = path
        capture["coordinator_kwargs"] = kwargs
        return coordinator

    class Runner:
        def __init__(self, **kwargs):
            events.append(("runner",))
            capture["runner"] = kwargs

        async def run_remaining(self, **kwargs):
            events.append(("run_remaining",))
            capture["remaining"] = kwargs
            return ("completed",)

    host.save = save
    host.api = SimpleNamespace(
        CycleCoordinator=coordinator_factory,
        driver=SimpleNamespace(SundayExecution=Runner),
    )
    monkeypatch.setattr(priming, "load_retained_priming", load_capsule)
    return host, events, capture, coordinator


@pytest.mark.parametrize("host_class", HOSTS)
@pytest.mark.parametrize("policy", [None, CUMULATIVE])
@pytest.mark.parametrize("capsule", [False, True])
def test_hosts_share_initialization_and_preserve_own_execution_boundary(
    tmp_path, monkeypatch, host_class, policy, capsule
):
    host, events, capture, coordinator = make_host(
        host_class, tmp_path, monkeypatch, policy=policy, capsule=capsule
    )
    calls = []

    def base_waiter(request, directory, lock, probe):
        calls.append(("base", request, directory, lock, probe))
        return "base-response"

    def classroom_waiter(request, directory, lock, probe):
        calls.append(("classroom", request, directory, lock, probe))
        return "classroom-response"

    monkeypatch.setattr(base, "await_recorded_principal", base_waiter)
    monkeypatch.setattr(classroom, "await_recorded_principal", classroom_waiter)
    assert asyncio.run(host.run()) == ("completed",)
    assert host.coordinator is coordinator
    kwargs = capture["coordinator_kwargs"]
    assert kwargs["learning_policy"] == policy
    assert kwargs["frozen_memory_path"] == host.config["memory"]["path"]
    assert kwargs["frozen_memory_sha256"] == host.config["memory"]["sha256"]
    assert kwargs["create"] is True
    assert kwargs["phase_callback"] is host.phase

    if capsule:
        saved = capture["saved"]["historical-priming-provenance.c15.json"]
        assert kwargs["critic_priming"] == saved
        assert events[:3] == [
            ("load_capsule", host.host["repository"], priming.MODE),
            ("save", "historical-priming-provenance.c15.json"),
            ("coordinator",),
        ]
    else:
        assert kwargs["critic_priming"] is None
        assert events[0] == ("coordinator",)

    runner = capture["runner"]
    assert runner["coordinator"] is coordinator
    assert runner["runtime_factory"] is host.runtime
    assert runner["schedule_path"] == host.host["schedule"]["path"]
    assert runner["expected_schedule_sha256"] == host.host["schedule"]["sha256"]
    assert runner["contract_path"] == host.config["contract"]["path"]
    assert runner["expected_contract_sha256"] == host.config["contract"]["sha256"]
    request = {"schema": "correction-request-test"}
    reply = runner["principal_configuration"]["session_executor"](request)
    expected_lane = "classroom" if host_class is classroom.ClassroomActualHost else "base"
    assert reply == expected_lane + "-response"
    assert calls == [
        (expected_lane, request, host.directory, host.principal_host_lock, host.probe)
    ]
    assert capture["remaining"] == (
        {"cycles": 7} if expected_lane == "classroom" else {}
    )


@pytest.mark.parametrize("host_class", HOSTS)
@pytest.mark.parametrize("encoding", ["native_v1", "compact_v1", None])
@pytest.mark.parametrize("policy,capsule", [(CUMULATIVE, False), (None, True)])
def test_unsupported_route_refuses_before_loading_or_coordinator(
    tmp_path, monkeypatch, host_class, encoding, policy, capsule
):
    host, events, capture, coordinator = make_host(
        host_class, tmp_path, monkeypatch, policy=policy, capsule=capsule
    )
    host.host["context_encoding"] = encoding
    with pytest.raises(ValueError, match="stacked critic route"):
        asyncio.run(host.run())
    assert events == []


@pytest.mark.parametrize("host_class", HOSTS)
@pytest.mark.parametrize(
    "declared",
    [
        "retained_cycle00_20260921",
        {},
        {"mode": priming.MODE, "profile": "other"},
        {"mode": priming.MODE, "profile": "retained_cycle00_20260921", "extra": True},
    ],
)
def test_bad_priming_profile_refuses_before_load_or_coordinator(
    tmp_path, monkeypatch, host_class, declared
):
    host, events, capture, coordinator = make_host(host_class, tmp_path, monkeypatch)
    host.config["critic_priming"] = declared
    with pytest.raises(ValueError, match="retained historical priming profile"):
        asyncio.run(host.run())
    assert events == []


@pytest.mark.parametrize("host_class", HOSTS)
def test_failed_capsule_verification_never_constructs_coordinator(
    tmp_path, monkeypatch, host_class
):
    host, events, capture, coordinator = make_host(
        host_class, tmp_path, monkeypatch, capsule=True
    )

    def reject(*args, **kwargs):
        raise ValueError("retained capsule bytes differ")

    monkeypatch.setattr(priming, "load_retained_priming", reject)
    with pytest.raises(ValueError, match="capsule bytes"):
        asyncio.run(host.run())
    assert events == []


def test_ordinary_and_existing_primed_training_hashes_are_unchanged():
    development = {"learning_rate": 0.001, "optimizer": "retained"}
    ordinary = {"schema": "lineage", "priming": None}
    result = base.training_configuration(development, ordinary)
    assert result is development
    assert evidence_hash(result) == evidence_hash(development)

    lineage = {"schema": "lineage", "priming": {"mode": priming.MODE, "source": "pin"}}
    previous = dict(
        schema="FRANKIE_PRIMED_TRAINING_CONFIGURATION_V1",
        development=development,
        knowledge_lineage=lineage,
    )
    assert base.training_configuration(development, lineage) == previous
    assert evidence_hash(base.training_configuration(development, lineage)) == evidence_hash(previous)


@pytest.mark.parametrize("with_capsule", [False, True])
def test_cumulative_training_hash_binds_full_lineage_without_requiring_capsule(
    with_capsule,
):
    development = {"learning_rate": 0.001}
    lineage = dict(
        schema="lineage",
        priming={"mode": priming.MODE, "source": "one"} if with_capsule else None,
        learning_policy=CUMULATIVE,
        frozen_memory_sha256="a" * 64,
    )
    result = base.training_configuration(development, lineage)
    assert result["knowledge_lineage"] == lineage
    assert evidence_hash(result) != evidence_hash(development)

    changed = copy.deepcopy(lineage)
    changed["frozen_memory_sha256"] = "b" * 64
    assert evidence_hash(base.training_configuration(development, changed)) != evidence_hash(result)

    ordinary = {"schema": "lineage", "priming": lineage["priming"]}
    assert evidence_hash(base.training_configuration(development, ordinary)) != evidence_hash(result)


@pytest.mark.parametrize("host_class", HOSTS)
def test_real_training_entry_records_policy_binding_before_native_initialization(
    tmp_path, monkeypatch, host_class
):
    class StopBeforeModels(RuntimeError):
        pass

    events = []
    lineage = dict(
        schema="lineage",
        priming=None,
        learning_policy=CUMULATIVE,
    )
    development = {"learning_rate": 0.001}
    host = host_class.__new__(host_class)
    host.schedule = {"model_context_rows": 5}
    host.builder = object()
    host.coordinator = SimpleNamespace(
        _knowledge_lineage_unchanged=lambda: events.append("lineage-checked"),
        _lineage_value=lambda: lineage,
    )
    saved = {}

    def save(name, value):
        events.append("binding-saved")
        saved[name] = value

    def initialize(builder, *, context_rows):
        assert builder is host.builder
        assert context_rows == 5
        events.append("initialize")
        raise StopBeforeModels()

    host.save = save
    host.api = SimpleNamespace(
        training=SimpleNamespace(),
        journal=SimpleNamespace(evidence_hash=evidence_hash),
        native=SimpleNamespace(DEVELOPMENT=development, initialize=initialize),
    )
    with pytest.raises(StopBeforeModels):
        host._training()
    assert events == ["lineage-checked", "binding-saved", "initialize"]
    binding = saved["training-knowledge-lineage.c15.json"]
    assert binding["knowledge_mode"] == "knowledge_primed_learning_replay"
    assert binding["knowledge_lineage"] == lineage
    assert binding["training_config_hash"] == evidence_hash(
        base.training_configuration(development, lineage)
    )


@pytest.mark.parametrize("requested", [None, 2])
def test_classroom_main_preserves_supplied_host_and_schedule_cycle_limit(
    tmp_path, monkeypatch, requested
):
    configuration = dict(
        run_id="test-run",
        run_directory=str(tmp_path / "run"),
        host_runtime={"repository": str(tmp_path / "repo")},
    )
    config_path = tmp_path / "configuration.json"
    config_path.write_text(json.dumps(configuration), encoding="utf-8")
    events = []
    lock = object()
    probe = SimpleNamespace(advance=lambda *a, **kw: events.append(("progress", kw)))
    original_base_host = base.ActualHost

    api = SimpleNamespace(
        _exclusive=lambda *a, **kw: nullcontext(),
        RunProbe=lambda *a, **kw: object(),
    )
    monkeypatch.setattr(classroom, "imports", lambda repo: api)
    monkeypatch.setattr(classroom, "ReleasableHostLock", lambda *a: nullcontext(lock))
    monkeypatch.setattr(classroom, "HostProbe", lambda *a: nullcontext(probe))

    class SuppliedHost:
        def __init__(self, config, *, prepare_only, probe):
            assert config == configuration
            assert prepare_only is True
            self.schedule = {"steps": [{}, {}, {}]}
            events.append(("constructed",))

        def source(self):
            events.append(("source",))

        async def run(self):
            assert self.principal_host_lock is lock
            events.append(("run", self.cycle_limit))
            return [{}] * self.cycle_limit

        def close(self):
            events.append(("close",))

    argv = ["host", "--configuration", str(config_path), "--prepare-only"]
    if requested is not None:
        argv += ["--cycles", str(requested)]
    monkeypatch.setattr(classroom.sys, "argv", argv)
    assert classroom.main(host_class=SuppliedHost) == 0
    assert ("run", 3 if requested is None else requested) in events
    assert events[0:2] == [("constructed",), ("source",)]
    assert events[-1] == ("close",)
    assert base.ActualHost is original_base_host
