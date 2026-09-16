"""Measure one real native learner step without Granite or principal execution.

This is a disposable benchmark harness for a SCRATCH CLONE of the failed Sunday run.
It deliberately imports the checkout named by --repository so source(), prefix() and
_training() are the exact host/native implementations bound by that checkout.

The retained clone is read only. A fresh sibling benchmark work directory is used for all
host verification files and training.sqlite. The clone contributes only its saved
cycles.sqlite feedback/binding evidence.

The harness NEVER constructs a critic, calls Granite, invokes the Frankie principal,
advances CycleCoordinator, applies a completed checkpoint, or touches production state.
The one optimizer update exists only in memory and is discarded when the process exits.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time


def _rss():
    if os.name != 'nt':
        try:
            values = {}
            for line in Path('/proc/self/status').read_text().splitlines():
                key, _, tail = line.partition(':')
                if key in ('VmRSS', 'VmHWM'):
                    values[key] = int(tail.split()[0]) * 1024
            return dict(rss=values.get('VmRSS'), peak_rss=values.get('VmHWM'))
        except OSError:
            return {}

    class Counters(ctypes.Structure):
        _fields_ = [
            ('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
            ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
            ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
            ('PrivateUsage', ctypes.c_size_t),
        ]
    counters = Counters(); counters.cb = ctypes.sizeof(counters)
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return {}
    return dict(rss=int(counters.WorkingSetSize), peak_rss=int(counters.PeakWorkingSetSize),
                private=int(counters.PrivateUsage), peak_pagefile=int(counters.PeakPagefileUsage))


class Log:
    def __init__(self, path):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.started = time.perf_counter(); self.lock = threading.Lock()

    def write(self, stage, **values):
        record = dict(stage=stage, t=round(time.perf_counter()-self.started, 3),
                      unix=time.time(), **_rss(), **values)
        with self.lock, self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, sort_keys=True, default=str)+'\n')
        print('BENCH '+json.dumps(record, sort_keys=True, default=str), flush=True)


def _load_stage(db_path, request_id, stage, *, unpack, evidence_hash):
    with sqlite3.connect(db_path) as db:
        row = db.execute('SELECT payload,digest FROM stages WHERE request=? AND stage=?',
                         (request_id, stage)).fetchone()
    if row is None: raise ValueError(f'missing retained {stage} stage for {request_id}')
    value = unpack(json.loads(row[0]))
    if evidence_hash(value) != row[1]: raise ValueError(f'retained {stage} stage digest changed')
    return value


def _typed_feedback(saved, learning):
    body = saved.get('feedback')
    if type(body) is not dict or saved.get('feedback_hash') is None:
        raise ValueError('saved feedback stage has wrong shape')
    sessions=[]
    for item in body.get('sessions', ()):
        sessions.append(learning.SessionFeedback(
            session_id=item['session_id'],
            timing=tuple(learning.TimingLabel(**label) for label in item['timing']),
            gap=None if item.get('gap') is None else learning.ValueLabel(**item['gap']),
            path=tuple(learning.ValueLabel(**label) for label in item['path'])))
    feedback=learning.FrankieFeedback(request_id=body['request_id'],input_hash=body['input_hash'],
        source_hash=body['source_hash'],available_ns=body['available_ns'],
        principal_receipt_hash=body['principal_receipt_hash'],sessions=tuple(sessions))
    if feedback.digest != saved['feedback_hash']:
        raise ValueError('typed feedback differs from saved feedback_hash')
    return feedback


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository',required=True,
        help='checkout whose exact host/native learner implementation is benchmarked')
    parser.add_argument('--configuration',required=True,
        help='Sunday configuration whose run_directory points to the disposable retained clone')
    parser.add_argument('--threads',type=int,required=True)
    parser.add_argument('--interop-threads',type=int,default=1)
    parser.add_argument('--cycle-index',type=int,default=0)
    parser.add_argument('--cycles-db',default=None,
        help='retained cycles.sqlite; defaults to <clone run_directory>/cycles.sqlite')
    parser.add_argument('--work-directory',default=None,
        help='fresh benchmark state directory; defaults to a sibling of the retained clone')
    parser.add_argument('--log',required=True)
    parser.add_argument('--sample-seconds',type=float,default=.25)
    args=parser.parse_args()

    if args.threads<1 or args.interop_threads<1: raise SystemExit('positive PyTorch thread counts required')
    if not 0<=args.cycle_index<19: raise SystemExit('cycle-index must be 0..18')
    if args.sample_seconds<=0: raise SystemExit('positive sample interval required')

    repository=Path(args.repository).resolve(); configuration_path=Path(args.configuration).resolve()
    configuration=json.loads(configuration_path.read_bytes())
    clone_directory=Path(configuration['run_directory']).resolve()
    disposable=clone_directory.as_posix().lower()
    if 'scratch' not in disposable and 'bench' not in clone_directory.name.lower():
        raise SystemExit('refusing: configuration run_directory is not a disposable scratch/bench clone')
    if Path(configuration['host_runtime']['repository']).resolve()!=repository:
        raise SystemExit('configuration host repository differs from --repository')

    work_directory=(Path(args.work_directory).resolve() if args.work_directory else
                    clone_directory.with_name(clone_directory.name+f'-native-learner-{args.threads}t'))
    if work_directory==clone_directory or clone_directory in work_directory.parents:
        raise SystemExit('benchmark work directory must not modify the retained clone tree')
    work_name=work_directory.name.lower()
    if 'scratch' not in work_name and 'bench' not in work_name and 'native-learner' not in work_name:
        raise SystemExit('benchmark work directory must be explicitly disposable')
    if work_directory.exists(): shutil.rmtree(work_directory)
    work_directory.mkdir(parents=True)

    # Keep retained clone evidence read-only: only substitute the host's scratch state root.
    bench_configuration=json.loads(json.dumps(configuration))
    bench_configuration['run_directory']=str(work_directory)

    sys.path.insert(0,str(repository)); os.chdir(repository)
    import torch
    torch.set_num_threads(args.threads); torch.set_num_interop_threads(args.interop_threads)

    from research.kalshi.frankie_boss import c15_journal
    from research.kalshi.frankie_boss import native_forecast_learning as learning
    from research.kalshi.frankie_boss import sunday_execution
    from research.kalshi.frankie_boss.operations import run_actual_sunday as actual
    from research.kalshi.frankie_boss.source_contract_runtime import bind_cycle

    log=Log(args.log)
    log.write('driver_start',repository=str(repository),configuration=str(configuration_path),
        clone_directory=str(clone_directory),work_directory=str(work_directory),cycle_index=args.cycle_index,
        threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),
        torch=torch.__version__,python=sys.version.split()[0],cpus=os.cpu_count())

    host=actual.ActualHost(bench_configuration); stop=threading.Event()
    def sampler():
        while not stop.wait(args.sample_seconds): log.write('sample')
    threading.Thread(target=sampler,daemon=True).start()
    try:
        host.source(); log.write('source_verified')
        schedule_path=actual.verified(configuration['host_runtime']['schedule']); schedule_raw=schedule_path.read_bytes()
        if hashlib.sha256(schedule_raw).hexdigest()!=configuration['host_runtime']['schedule']['sha256']:
            raise ValueError('trusted schedule hash changed')
        schedule=json.loads(schedule_raw); steps=schedule['steps'] if isinstance(schedule,dict) else schedule
        if len(steps)!=19: raise ValueError('complete 19-step schedule required')

        binding=bind_cycle(configuration['contract']['path'],configuration['contract']['sha256'],
                           args.cycle_index,steps[args.cycle_index])
        request_id=f"{configuration['run_id']}-cycle-{args.cycle_index:02d}"
        log.write('binding_rebuilt',request_id=request_id,as_of=binding['as_of'],
                  through_cursor=binding['through_cursor'],sessions=len(binding['sessions']))

        cycle_directory=work_directory/f'cycle-{args.cycle_index:02d}'; cycle_directory.mkdir(exist_ok=True)
        host.prefix(binding,cycle_directory); log.write('prefix_verified',source_hash=binding['source_hash'])
        host._training()
        if host.checkpoint.training_cursor!=-1:
            raise ValueError('fresh benchmark checkpoint must start before any training update')
        log.write('fresh_checkpoint_ready',checkpoint_hash=host.checkpoint.checkpoint_hash)

        cycles_db=Path(args.cycles_db).resolve() if args.cycles_db else clone_directory/'cycles.sqlite'
        if clone_directory not in cycles_db.parents and cycles_db!=clone_directory/'cycles.sqlite':
            raise ValueError('cycles database must belong to the disposable clone')
        saved_binding=_load_stage(cycles_db,request_id,'binding',unpack=c15_journal.unpack,
                                  evidence_hash=c15_journal.evidence_hash)
        saved_feedback=_load_stage(cycles_db,request_id,'feedback',unpack=c15_journal.unpack,
                                   evidence_hash=c15_journal.evidence_hash)
        feedback=_typed_feedback(saved_feedback,learning)

        expected_learning=saved_binding.get('learning')
        if type(expected_learning) is not dict: raise ValueError('saved binding lacks learning identity')
        for name in ('as_of','through_cursor','source_hash','expected_sessions_hash','learning_cutoff_ns'):
            if expected_learning.get(name)!=binding[name]:
                raise ValueError(f'rebuilt binding differs from saved learning field {name}')
        if c15_journal.evidence_hash(expected_learning.get('sessions'))!=c15_journal.evidence_hash(
                sunday_execution._plain(binding['sessions'])):
            raise ValueError('rebuilt session roster differs from saved Sunday binding')
        if expected_learning.get('input_hash')!=feedback.input_hash:
            raise ValueError('saved binding input hash differs from independently saved feedback')
        if feedback.request_id!=request_id or feedback.source_hash!=binding['source_hash']:
            raise ValueError('saved typed feedback differs from rebuilt cycle identity')
        log.write('feedback_verified',feedback_hash=feedback.digest,input_hash=feedback.input_hash,
                  available_ns=feedback.available_ns)

        config=host.api.native.learning_config(host.optimizer,binding['sessions'],
            timing_policy_hash=binding['timing_policy_hash'],query_policy_hash=binding['query_policy_hash'],
            split_hash=binding['split_hash'])
        def learner_event(payload):
            payload=dict(payload); stage=payload.pop('stage'); log.write('learner.'+stage,**payload)
        learner=learning.NativeForecastLearner(host.context,host.decoder,host.optimizer,config,event=learner_event)

        log.write('learner_step_start',feedback_hash=feedback.digest); started=time.perf_counter()
        result=learner.step(request_id=request_id,as_of=binding['as_of'],through_cursor=binding['through_cursor'],
            source_hash=binding['source_hash'],input_hash=feedback.input_hash,sessions=binding['sessions'],
            expected_sessions_hash=binding['expected_sessions_hash'],feedback=feedback,
            expected_feedback_hash=feedback.digest,learning_cutoff_ns=binding['learning_cutoff_ns'])
        elapsed=time.perf_counter()-started; result_hash=c15_journal.evidence_hash(result)
        log.write('learner_step_complete',wall_seconds=elapsed,result_hash=result_hash,
                  checkpoint_persisted=False,production_state_advanced=False)
        print(json.dumps(dict(schema='FRANKIE_NATIVE_LEARNER_DIRECT_BENCHMARK_V1',request_id=request_id,
            threads=args.threads,interop_threads=args.interop_threads,wall_seconds=elapsed,
            result_hash=result_hash,feedback_hash=feedback.digest,checkpoint_persisted=False,
            production_state_advanced=False,**_rss()),sort_keys=True),flush=True)
        return 0
    except BaseException as error:
        log.write('driver_failed',error_type=type(error).__name__,error_message=str(error)[:500]); raise
    finally:
        stop.set()
        try: host.close()
        finally: log.write('driver_end')


if __name__=='__main__': raise SystemExit(main())
