"""Integrated Dipole classroom host around the lawful actual Sunday host.

The lawful host implementation remains untouched. This composition layer only:
- reuses the already prepared governed teacher attachment from PreparedContextCache;
- builds and retains the per-cycle Dipole classroom package without rerunning teacher math;
- feeds the reviewed final classroom adapter explicitly through SundayRuntime;
- attaches the classroom package to the returned SundayRuntime without monkeypatching classes;
- extends the recorded-session waiter to the mandatory same-session correction turn.

Importing this module starts no resource and performs no model call.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

from research.kalshi.frankie_boss.dipole_classroom_integration import (
    IntegratedDipoleClassroomPrincipalAdapter,
    prepare_integrated_cycle,
)
from research.kalshi.frankie_boss.dipole_classroom_session import CORRECTION_REQUEST_SCHEMA
from research.kalshi.frankie_boss.operations import run_actual_sunday as base

INITIAL_REQUEST_SCHEMA = "FRANKIE_BOSS_SESSION_REQUEST_V1"


def _load_json(path):
    return json.loads(Path(path).read_bytes())


def _adapter_identity(adapter_class):
    return {
        "module": adapter_class.__module__,
        "qualname": adapter_class.__qualname__,
    }


def await_recorded_principal(request, directory, host_lock, probe=None):
    schema = request.get("schema") if type(request) is dict else None
    if schema == INITIAL_REQUEST_SCHEMA:
        request_name, response_name, status = (
            "session-request.json",
            "session-response.json",
            "actual_frankie_session_pending",
        )
    elif schema == CORRECTION_REQUEST_SCHEMA:
        request_name, response_name, status = (
            "classroom-correction-request.json",
            "classroom-correction-response.json",
            "actual_frankie_classroom_correction_pending",
        )
    else:
        raise ValueError("known Frankie principal/classroom request schema required")
    matches = [
        path
        for path in sorted(Path(directory).glob("execution/cycle-*/principal/" + request_name))
        if _load_json(path) == request
    ]
    if len(matches) != 1:
        raise ValueError("unique retained Frankie classroom request required")
    request_path = matches[0]
    response_path = request_path.with_name(response_name)
    if probe is not None:
        probe.advance("frankie_calculation", unit="outputs")
    public = {
        "status": status,
        "request_path": str(request_path),
        "prepared_context_retained": True,
    }
    if schema == INITIAL_REQUEST_SCHEMA:
        public["request_id"] = request["request_id"]
    else:
        public["session_id"] = request["session_id"]
    print(json.dumps(public), flush=True)
    host_lock.release()
    try:
        while not response_path.exists():
            time.sleep(1)
    finally:
        host_lock.acquire(wait=True)
    if _load_json(request_path) != request:
        raise ValueError("Frankie classroom request changed while awaiting response")
    result = _load_json(response_path)
    if type(result) is not dict or set(result) != {"response", "host_attestation"}:
        raise ValueError("recorded Frankie classroom response envelope differs")
    if probe is not None:
        probe.advance("frankie_calculation", completed=1, total=1, unit="outputs")
    return result


class ClassroomActualHost(base.ActualHost):
    """Actual Sunday host with mandatory, reviewed Dipole classroom composition."""

    principal_adapter_class = IntegratedDipoleClassroomPrincipalAdapter

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.classroom_package = None

    def _classroom_paths(self, cycle_directory):
        directory = Path(cycle_directory)
        return {
            name: directory / ("host-dipole-classroom-" + name + ".c15.json")
            for name in ("source", "teacher-key", "pre-message", "binding")
        }

    def _load_classroom_package(self, cycle_directory):
        paths = self._classroom_paths(cycle_directory)
        if not all(path.exists() for path in paths.values()):
            return None
        return {
            "source": self.api.driver._load(paths["source"]),
            "teacher_key": self.api.driver._load(paths["teacher-key"]),
            "pre_message": self.api.driver._load(paths["pre-message"]),
            "binding": self.api.driver._load(paths["binding"]),
        }

    def _history(self, index):
        values = []
        for prior in range(index):
            path = (
                self.directory
                / "execution"
                / f"cycle-{prior:02d}"
                / "principal"
                / "dipole-classroom-completion.json"
            )
            if not path.exists():
                raise ValueError(
                    "prior Sunday cycle completed without retained Dipole classroom completion"
                )
            values.append(_load_json(path))
        return tuple(values)

    def _previous_source_and_grade(self, index):
        if index == 0:
            return None, None
        prior = self.directory / "execution" / f"cycle-{index-1:02d}"
        source = self.api.driver._load(prior / "host-dipole-classroom-source.c15.json")
        grade_path = prior / "classroom-audit" / "dipole-classroom-post-grade.json"
        if not grade_path.exists():
            raise ValueError("previous Dipole post-grade required before next cycle")
        return source, _load_json(grade_path)

    def _curriculum_cycle_count(self):
        schedule = json.loads(base.verified(self.host["schedule"]).read_bytes())
        steps = schedule["steps"] if isinstance(schedule, dict) else schedule
        if type(steps) is not list or not steps:
            raise ValueError("retained Sunday schedule must contain cycles")
        return len(steps)

    def prime_cache(self, binding, cycle_directory):
        super().prime_cache(binding, cycle_directory)
        _, _, input_hash, teacher, _ = self.cache.prepare(
            binding["as_of"], binding["through_cursor"]
        )
        if input_hash != self.cache.receipt["input_hash"] or teacher is None:
            raise ValueError(
                "classroom must reuse exact prepared governed teacher attachment"
            )
        index = binding["cycle_index"]
        request_id = f"{self.config['run_id']}-cycle-{index:02d}"
        previous, prior_grade = self._previous_source_and_grade(index)
        package = prepare_integrated_cycle(
            teacher,
            request_id=request_id,
            cycle_index=index,
            cycle_count=self._curriculum_cycle_count(),
            source_hash=binding["source_hash"],
            as_of=binding["as_of"],
            through_cursor=binding["through_cursor"],
            previous_snapshot=previous,
            history=self._history(index),
            prior_grade=prior_grade,
        )
        if tuple(package["source"]["context_cursors"]) != tuple(
            self.cache.receipt["context_cursors"]
        ):
            raise ValueError("Dipole classroom rows differ from prepared native context rows")
        paths = self._classroom_paths(cycle_directory)
        for name, key in (
            ("source", "source"),
            ("teacher-key", "teacher_key"),
            ("pre-message", "pre_message"),
            ("binding", "binding"),
        ):
            self.api.driver._save(paths[name], package[key])
        self.api.driver._save(
            Path(cycle_directory) / "host-dipole-classroom-adapter.c15.json",
            _adapter_identity(self.principal_adapter_class),
        )
        self.classroom_package = package

    def runtime(self, binding, cycle_directory, retained_plan):
        # Never carry a prior cycle's classroom package into this cutoff.
        self.classroom_package = self._load_classroom_package(cycle_directory)
        self.api.driver._save(
            Path(cycle_directory) / "host-dipole-classroom-adapter.c15.json",
            _adapter_identity(self.principal_adapter_class),
        )
        runtime = super().runtime(binding, cycle_directory, retained_plan)
        package = self.classroom_package or self._load_classroom_package(cycle_directory)
        if package is None:
            raise ValueError(
                "Dipole classroom package must exist before Sunday runtime construction"
            )
        runtime.classroom_package = package
        runtime.principal_adapter_class = self.principal_adapter_class
        return runtime

    async def run(self):
        c = self.config
        h = self.host
        self.coordinator = self.api.CycleCoordinator(
            self.directory / "cycles.sqlite",
            lessons_path=self.directory / "lessons.sqlite",
            frozen_memory_path=c["memory"]["path"],
            frozen_memory_sha256=c["memory"]["sha256"],
            create=not (self.directory / "cycles.sqlite").exists(),
            phase_callback=self.phase,
        )
        principal = dict(
            mapping_directory=str(Path(c["mapping"]["path"]).parent),
            expected_mapping_sha256=c["mapping"]["sha256"],
            receiver_root=c["receiver_root"],
            receiver_commit=c["receiver_commit"],
            python=sys.executable,
            retained_directory=str(Path(c["retained_witnesses"]["path"]).parent),
            expected_retained_witnesses_sha256=c["retained_witnesses"]["sha256"],
            delivery_receipt=c["delivery_receipt"]["path"],
            expected_delivery_file_sha256=c["delivery_receipt"]["sha256"],
            result_path=c["calculation_result"]["path"],
            session_executor=lambda request: await_recorded_principal(
                request, self.directory, self.principal_host_lock, self.probe
            ),
        )
        runner = self.api.driver.SundayExecution(
            directory=self.directory / "execution",
            run_id=c["run_id"],
            coordinator=self.coordinator,
            contract_path=c["contract"]["path"],
            expected_contract_sha256=c["contract"]["sha256"],
            schedule_path=h["schedule"]["path"],
            expected_schedule_sha256=h["schedule"]["sha256"],
            runtime_factory=self.runtime,
            principal_configuration=principal,
            boss_commit=h["boss_commit"],
            agent_commit=c["receiver_commit"],
            state_defects_and_gaps_reported=h["state_defects_and_gaps_reported"],
        )
        return await runner.run_remaining()


ActualHost = ClassroomActualHost
verified = base.verified
verified_json = base.verified_json
PreparationComplete = base.PreparationComplete
HostProbe = base.HostProbe
ReleasableHostLock = base.ReleasableHostLock
imports = base.imports


def main(host_class=ActualHost):
    """Run the integrated classroom host without rebinding any module globals."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    configuration = json.loads(Path(args.configuration).read_bytes())
    if any(
        word in json.dumps(configuration).lower()
        for word in ("service_key", "api_key", "bearer ")
    ):
        raise ValueError("host configuration must contain no service credentials")
    host = None
    try:
        repo = Path(configuration["host_runtime"]["repository"])
        api = imports(repo)
        Path(configuration["run_directory"]).mkdir(parents=True, exist_ok=True)
        with api._exclusive(
            Path(configuration["run_directory"]) / "actual-host-session.lock"
        ), ReleasableHostLock(
            api._exclusive, Path(configuration["run_directory"]) / "actual-host.lock"
        ) as host_lock, HostProbe(
            api.RunProbe(
                Path(configuration["run_directory"]) / "host-progress",
                configuration["run_id"],
                resume=(
                    Path(configuration["run_directory"])
                    / "host-progress"
                    / "progress.json"
                ).exists(),
            )
        ) as probe:
            host = host_class(configuration, prepare_only=args.prepare_only, probe=probe)
            host.principal_host_lock = host_lock
            try:
                result = asyncio.run(host.run())
                probe.advance("complete", completed=len(result), total=19, unit="steps")
                print(
                    json.dumps(
                        dict(
                            status="all_nineteen_cycles_complete",
                            cycles=len(result),
                        )
                    ),
                    flush=True,
                )
                return 0
            except PreparationComplete:
                return 0
            except api.JobAttention as error:
                message = (
                    "Same durable job requires a fresh in-memory credential; no new job or Pod start."
                    if error.code == "REMOTE_JOB_CREDENTIAL_REJECTED"
                    else "Remote job ended in terminal failure; no fragment was scored or retried."
                    if error.code == "REMOTE_JOB_TERMINAL_FAILURE"
                    else "Same durable job requires attention; retained evidence prevents another inference."
                )
                print(
                    json.dumps(
                        dict(
                            status=error.code,
                            message=message,
                            job_id=error.job_id,
                            artifact_path=error.artifact_path,
                            cleanup_pending=error.details.get("cleanup_pending"),
                        )
                    ),
                    flush=True,
                )
                return 4
            except api.PendingTransport:
                print(
                    json.dumps(
                        dict(
                            status="same_critic_attempt_pending_or_ambiguous",
                            run_directory=configuration["run_directory"],
                        )
                    ),
                    flush=True,
                )
                return 4
            except api.PrincipalPending:
                print(
                    json.dumps(
                        dict(
                            status="actual_frankie_session_pending",
                            run_directory=configuration["run_directory"],
                        )
                    ),
                    flush=True,
                )
                return 3
            except api.IncompleteModelOutput as error:
                print(json.dumps(base.incomplete_output_alert(error)), flush=True)
                return 5
            finally:
                host.close()
    except Exception as error:
        print(json.dumps(dict(status="stopped", error_type=type(error).__name__)), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
