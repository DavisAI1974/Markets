"""Classroom wrapper around the lawful actual Sunday host.

The lawful host remains byte-for-byte separate.  This wrapper only:
- reuses the already prepared governed teacher attachment from PreparedContextCache;
- builds and retains the per-cycle Dipole classroom package without rerunning teacher math;
- hardens model-visible correction/taper/statistics transport without changing teacher evidence;
- gives Frankie a protected, non-punitive novelty channel;
- injects that package into SundayRuntime for the existing principal boundary;
- extends the existing recorded-session waiter to the same-session correction turn.

It starts no resource and performs no model call by importing this module.
"""
from __future__ import annotations
import json
from pathlib import Path
import time
from research.kalshi.frankie_boss import source_contract_runtime
from research.kalshi.frankie_boss.dipole_classroom_final_review import FinalDipoleClassroomPrincipalAdapter, prepare_final_cycle
from research.kalshi.frankie_boss.dipole_classroom_session import CORRECTION_REQUEST_SCHEMA
from research.kalshi.frankie_boss.operations import run_actual_sunday as base
INITIAL_REQUEST_SCHEMA="FRANKIE_BOSS_SESSION_REQUEST_V1"

def _load_json(path):return json.loads(Path(path).read_bytes())

def await_recorded_principal(request,directory,host_lock,probe=None):
    schema=request.get("schema") if type(request) is dict else None
    if schema==INITIAL_REQUEST_SCHEMA:request_name,response_name,status="session-request.json","session-response.json","actual_frankie_session_pending"
    elif schema==CORRECTION_REQUEST_SCHEMA:request_name,response_name,status="classroom-correction-request.json","classroom-correction-response.json","actual_frankie_classroom_correction_pending"
    else:raise ValueError("known Frankie principal/classroom request schema required")
    # Search every retained cycle directory; the cycle count belongs to the schedule, not to this loop.
    matches=[path for path in sorted(Path(directory).glob("execution/cycle-*/principal/"+request_name)) if _load_json(path)==request]
    if len(matches)!=1:raise ValueError("unique retained Frankie classroom request required")
    request_path=matches[0];response_path=request_path.with_name(response_name)
    if probe is not None:probe.advance("frankie_calculation",unit="outputs")
    public={"status":status,"request_path":str(request_path),"prepared_context_retained":True}
    if schema==INITIAL_REQUEST_SCHEMA:public["request_id"]=request["request_id"]
    else:public["session_id"]=request["session_id"]
    print(json.dumps(public),flush=True);host_lock.release()
    try:
        while not response_path.exists():time.sleep(1)
    finally:host_lock.acquire(wait=True)
    if _load_json(request_path)!=request:raise ValueError("Frankie classroom request changed while awaiting response")
    result=_load_json(response_path)
    if type(result) is not dict or set(result)!={"response","host_attestation"}:raise ValueError("recorded Frankie classroom response envelope differs")
    if probe is not None:probe.advance("frankie_calculation",completed=1,total=1,unit="outputs")
    return result

class ClassroomActualHost(base.ActualHost):
    def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.classroom_package=None
    def _classroom_paths(self,cycle_directory):
        directory=Path(cycle_directory);return {name:directory/("host-dipole-classroom-"+name+".c15.json") for name in ("source","teacher-key","pre-message","binding")}
    def _load_classroom_package(self,cycle_directory):
        paths=self._classroom_paths(cycle_directory)
        if not all(path.exists() for path in paths.values()):return None
        return {"source":self.api.driver._load(paths["source"]),"teacher_key":self.api.driver._load(paths["teacher-key"]),"pre_message":self.api.driver._load(paths["pre-message"]),"binding":self.api.driver._load(paths["binding"])}
    def _history(self,index):
        values=[]
        for prior in range(index):
            path=self.directory/"execution"/f"cycle-{prior:02d}"/"principal"/"dipole-classroom-completion.json"
            if not path.exists():raise ValueError("prior Sunday cycle completed without retained Dipole classroom completion")
            values.append(_load_json(path))
        return tuple(values)
    def _previous_source_and_grade(self,index):
        if index==0:return None,None
        prior=self.directory/"execution"/f"cycle-{index-1:02d}";source=self.api.driver._load(prior/"host-dipole-classroom-source.c15.json")
        # The full post-grade is host-owned audit evidence, retained beside the principal directory.
        grade_path=prior/"classroom-audit"/"dipole-classroom-post-grade.json"
        if not grade_path.exists():raise ValueError("previous Dipole post-grade required before next cycle")
        return source,_load_json(grade_path)
    def _curriculum_cycle_count(self):
        schedule=json.loads(base.verified(self.host["schedule"]).read_bytes());steps=schedule["steps"] if isinstance(schedule,dict) else schedule
        if type(steps) is not list or not steps:raise ValueError("retained Sunday schedule must contain cycles")
        return len(steps)
    def prime_cache(self,binding,cycle_directory):
        super().prime_cache(binding,cycle_directory)
        _,info,input_hash,teacher,_=self.cache.prepare(binding["as_of"],binding["through_cursor"])
        if input_hash!=self.cache.receipt["input_hash"] or teacher is None:raise ValueError("classroom must reuse exact prepared governed teacher attachment")
        index=binding["cycle_index"];request_id=f"{self.config['run_id']}-cycle-{index:02d}";previous,prior_grade=self._previous_source_and_grade(index)
        package=prepare_final_cycle(teacher,request_id=request_id,cycle_index=index,cycle_count=self._curriculum_cycle_count(),source_hash=binding["source_hash"],as_of=binding["as_of"],through_cursor=binding["through_cursor"],previous_snapshot=previous,history=self._history(index),prior_grade=prior_grade)
        if tuple(package["source"]["context_cursors"])!=tuple(self.cache.receipt["context_cursors"]):raise ValueError("Dipole classroom rows differ from prepared native context rows")
        paths=self._classroom_paths(cycle_directory)
        for name,key in (("source","source"),("teacher-key","teacher_key"),("pre-message","pre_message"),("binding","binding")):self.api.driver._save(paths[name],package[key])
        self.classroom_package=package
    def runtime(self,binding,cycle_directory,retained_plan):
        retained=self._load_classroom_package(cycle_directory)
        if retained is not None:self.classroom_package=retained
        original_runtime=self.api.driver.SundayRuntime
        def classroom_runtime(**kwargs):
            package=self.classroom_package or self._load_classroom_package(cycle_directory)
            if package is None:raise ValueError("Dipole classroom package must exist before Sunday runtime construction")
            return original_runtime(classroom_package=package,**kwargs)
        self.api.driver.SundayRuntime=classroom_runtime
        try:return super().runtime(binding,cycle_directory,retained_plan)
        finally:self.api.driver.SundayRuntime=original_runtime
ActualHost=ClassroomActualHost;verified=base.verified;verified_json=base.verified_json;PreparationComplete=base.PreparationComplete;HostProbe=base.HostProbe;ReleasableHostLock=base.ReleasableHostLock;imports=base.imports

def main():
    source_contract_runtime.DipoleClassroomPrincipalAdapter=FinalDipoleClassroomPrincipalAdapter;base.ActualHost=ActualHost;base.await_recorded_principal=await_recorded_principal;return base.main()
