import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[4]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
host=load('actual_host_probe_test',REPO/'research/kalshi/frankie_boss/operations/run_actual_sunday.py')
progress=load('actual_progress_test',REPO/'research/kalshi/frankie_boss/full_run_progress.py')

class Wiring(unittest.TestCase):
    def test_real_probe_allowlists_and_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            emitted=[];raw=progress.RunProbe(tmp,'actual-probe-test',emit=emitted.append,interval=60)
            with host.HostProbe(raw) as probe:
                instance=object.__new__(host.ActualHost);instance.probe=probe
                closed=[];instance.close_cache=lambda:closed.append(True)
                instance.phase('native_learning',request_id='secret-not-copied')
                self.assertFalse(closed)
                probe.controller(dict(phase='critic_request',through_cursor=3,api_key='SECRET'))
                captured=io.StringIO()
                with contextlib.redirect_stdout(captured):
                    probe.job(dict(phase='job_running',job_id='a'*64,api_key='SECRET',body='SECRET'))
                    probe.job(dict(phase='SECRET',job_id='b'*64))
                self.assertNotIn('SECRET',captured.getvalue())
                self.assertIn('job_running',captured.getvalue())
                instance.phase('checkpoint_readback')
                self.assertEqual(closed,[True])
                probe.advance('complete',completed=19,total=19,unit='steps')
            self.assertFalse(raw._thread.is_alive())
            records=[json.loads(line) for line in (Path(tmp)/'progress.jsonl').read_text().splitlines()]
            self.assertEqual(records[-1]['phase'],'complete')
            self.assertTrue({'boss_training','granite_request','readback'}<={r['phase'] for r in records})
            self.assertNotIn('SECRET',''.join(emitted))

    def test_diagnostic_failure_does_not_replace_primary_alert(self):
        class Broken:
            def __enter__(self):return self
            def advance(self,*a,**kw):raise OSError('SECRET')
            def __exit__(self,*a):raise RuntimeError('SECRET')
        class TypedAlert(Exception):pass
        output=io.StringIO();alert=TypedAlert('primary')
        with contextlib.redirect_stdout(output):
            with self.assertRaises(TypedAlert) as got:
                with host.HostProbe(Broken()) as probe:
                    probe.advance('boss_training');raise alert
        self.assertIs(got.exception,alert)
        self.assertEqual(output.getvalue().count('HOST_DIAGNOSTICS_UNAVAILABLE'),1)
        self.assertNotIn('SECRET',output.getvalue())

    def test_waiter_observes_without_dispatch_and_retains_lock_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'execution/cycle-00/principal';path.mkdir(parents=True)
            request={'request_id':'actual-test'};response={'response':{},'host_attestation':{}}
            (path/'session-request.json').write_text(json.dumps(request))
            calls=[]
            class Lock:
                def release(self):
                    calls.append('release');(path/'session-response.json').write_text(json.dumps(response))
                def acquire(self,wait=False):calls.append(('acquire',wait))
            class Probe:
                def advance(self,phase,**values):calls.append((phase,values))
            with contextlib.redirect_stdout(io.StringIO()):
                actual=host.await_recorded_principal(request,tmp,Lock(),Probe())
            self.assertEqual(actual,response)
            self.assertEqual(calls[1:3],['release',('acquire',True)])
            self.assertEqual(calls[-1][1]['completed'],1)

    def test_waiter_matches_a_live_request_that_holds_tuples(self):
        # Run 35522815675 (2026-09-20): the live request carried tuples the c15 loader preserved,
        # the durable file was canonical JSON (lists), and the waiter found 0 matches against a
        # request the adapter had just written itself. Identity is the canonical JSON form.
        from research.kalshi.frankie_boss.frankie_principal_adapter import canonical
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'execution/cycle-00/principal';path.mkdir(parents=True)
            request={'schema':'FRANKIE_BOSS_SESSION_REQUEST_V1','request_id':'actual-test',
                     'attachment':{'dipole_classroom':{'pre_message':{'rows':({'cursor':1,'state':'PRESENT'},)}}}}
            response={'response':{},'host_attestation':{}}
            (path/'session-request.json').write_bytes(canonical(request))
            class Lock:
                def release(self):(path/'session-response.json').write_text(json.dumps(response))
                def acquire(self,wait=False):pass
            with contextlib.redirect_stdout(io.StringIO()):
                actual=host.await_recorded_principal(request,tmp,Lock(),None)
            self.assertEqual(actual,response)
            self.assertNotEqual(json.loads(canonical(request)),request)  # the defect: tuple vs list

    def test_main_attaches_before_host_and_both_callbacks_are_wired(self):
        tree=ast.parse(Path(host.__file__).read_text())
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        owner=next(n for n in ast.walk(main) if isinstance(n,ast.With) and any(
            isinstance(i.context_expr,ast.Call) and isinstance(i.context_expr.func,ast.Name)
            and i.context_expr.func.id=='HostProbe' for i in n.items))
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ActualHost'
            for n in ast.walk(owner)))
        text=Path(host.__file__).read_text()
        self.assertIn('controller_event=None if self.probe is None else self.probe.controller',text)
        self.assertIn('event=None if self.probe is None else self.probe.job',text)

if __name__=='__main__':unittest.main(verbosity=2)
