import copy
import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from family_final_backup import pack_final, validate_final
from family_completion_hook import wait_exact_exit, ensure_idle, run
from family_save_stop import validate_predictions, record_and_stop


class CompletionTests(unittest.TestCase):
    def test_pack_retains_learned_links_attempts_and_references_remote(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d); out = p/'out'; out.mkdir()
            (out/'parallel-63/attempts/bad').mkdir(parents=True)
            (out/'parallel-63/attempts/bad/weights.jls').write_bytes(b'failed')
            (out/'weights.jls').write_bytes(b'learned')
            (out/'model_matrix.jls').write_bytes(b'dense input')
            (out/'model_predictions.csv').write_bytes(b'predictions')
            if os.name == 'posix':
                remote = p/'remote-B'; remote.mkdir(); (remote/'jobs').mkdir()
                (remote/'jobs/job').mkdir(); (remote/'jobs/job/remote.jls').write_bytes(b'remote')
                (out/'alias.jls').symlink_to(out/'weights.jls')
                (out/'remote.jls').symlink_to(remote/'jobs/job/remote.jls')
                remotes = {'B':remote}
            else:
                remotes = {}
            manifest = pack_final(out,p/'backup.tar.gz',remotes)
            with tarfile.open(p/'backup.tar.gz') as tar:
                names = tar.getnames()
                self.assertIn('weights.jls',names)
                self.assertIn('parallel-63/attempts/bad/weights.jls',names)
                self.assertNotIn('model_matrix.jls',names)
                if os.name == 'posix':
                    self.assertTrue(tar.getmember('alias.jls').issym())
                    self.assertEqual(manifest['external_links']['remote.jls'],
                                     {'owner':'B','member':'jobs/job/remote.jls'})

    @unittest.skipUnless(os.name == 'posix', 'Linux symlink boundary')
    def test_unknown_external_learned_link_refuses_backup(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d); (p/'out').mkdir(); (p/'lost.jls').write_bytes(b'learned')
            (p/'out/state.jls').symlink_to(p/'lost.jls')
            with self.assertRaises(ValueError):pack_final(p/'out',p/'backup.tar.gz',{})

    @unittest.skipUnless(os.name == 'posix', 'Linux input metadata links')
    def test_known_frozen_metadata_is_materialized_with_internal_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);out=p/'out';out.mkdir()
            inputs=p/'joint-inputs-v4-candidate-20261022';inputs.mkdir()
            (inputs/'model_outcomes.csv').write_text('as-of provenance')
            (out/'model_outcomes.csv').symlink_to(inputs/'model_outcomes.csv')
            (out/'job').mkdir();(out/'job/model_outcomes.csv').symlink_to(out/'model_outcomes.csv')
            pack_final(out,p/'backup.tar.gz',{})
            with tarfile.open(p/'backup.tar.gz') as tar:
                self.assertEqual(tar.extractfile('model_outcomes.csv').read(),b'as-of provenance')
                self.assertEqual(tar.getmember('job/model_outcomes.csv').linkname,'../model_outcomes.csv')

    @unittest.skipUnless(hasattr(os, 'pidfd_open'), 'Linux pidfd')
    def test_waits_for_exact_process_exit_and_rejects_reused_identity(self):
        with tempfile.TemporaryDirectory() as d:
            child = subprocess.Popen([sys.executable,'-c','import time; time.sleep(0.2)'])
            token = pathlib.Path('/proc',str(child.pid),'stat').read_text().rsplit(')',1)[1].split()[19]
            cfg = dict(pid=child.pid,token=token,run=d)
            with self.assertRaises(ValueError):wait_exact_exit(dict(cfg,token='wrong'))
            wait_exact_exit(cfg)
            child.wait()
            self.assertEqual(json.loads((pathlib.Path(d)/'hook-status.json').read_text())['status'],'waiting_for_exit')

    def test_missing_predictions_noncontiguous_and_nonfinite_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)/'pred.csv'
            head='outcome,horizon_s,fold,model,sample_id,prediction,observed\n'
            for rows, counts in [('',{('o','1','2','m'):1}),
                ('o,1,2,m,s1,nan,0\n',{('o','1','2','m'):1}),
                ('o,1,2,m,s1,1,0\no,1,2,n,s1,1,0\no,1,2,m,s2,1,0\n',
                 {('o','1','2','m'):2,('o','1','2','n'):1})]:
                p.write_text(head+rows)
                with self.assertRaises(ValueError):validate_predictions(p,counts)

    def test_unverified_backup_cannot_call_shutdown_or_s3(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                record_and_stop(None,dict(run=d),{'backup_verified':False},lambda:calls.append(1))
        self.assertFalse(calls)

    def test_final_requires_exact_global_models_predictions_and_postprocessing(self):
        with tempfile.TemporaryDirectory() as d:
            out=pathlib.Path(d);root=out/'parallel-63';root.mkdir();work=root/'run';work.mkdir()
            cohorts=[('o',str(i),'2') for i in range(63)]
            plan={'cohorts':[dict(cohort=list(t),owner='A') for t in cohorts]}
            (root/'parallel_plan.json').write_text(json.dumps(dict(status='complete_candidate',
                coverage_gate='NOT_PASSED',recovery=str(work),recovered_committed_jobs=63)))
            caches=[]
            for t in cohorts:
                p=root/'cache'/t[1];p.mkdir(parents=True);(p/'ready.json').write_text('{"groups":[]}')
                caches.append(dict(cohort=list(t),cache=str(p)))
            for prefix,model in [('model','m'),('neural','n')]:
                with (out/(prefix+'_metrics.csv')).open('w',newline='') as f:
                    f.write('outcome,horizon_s,fold,model,test_n\n')
                    for t in cohorts:f.write(','.join(t+(model,'1'))+'\n')
                with (out/(prefix+'_predictions.csv')).open('w',newline='') as f:
                    f.write('outcome,horizon_s,fold,model,sample_id,prediction,observed\n')
                    for t in cohorts:f.write(','.join(t+(model,'s1','0.2','0'))+'\n')
            cfg=dict(out=d,run=str(work))
            state=dict(status='complete_candidate',coverage_gate='NOT_PASSED',committed_jobs=126,deferred_memory_jobs=0)
            published=json.loads((root/'parallel_plan.json').read_text());published['recovered_committed_jobs']=126
            (root/'parallel_plan.json').write_text(json.dumps(published))
            with patch('multibox_support.prepared_cache_index',return_value=caches),patch('resume_multibox_candidate.expected_models',return_value=(['m'],['n'])),patch('resume_multibox_candidate.committed',return_value=True):
                proof,_=validate_final(cfg,plan,state,{})
                self.assertEqual(len(proof['required_jobs']),126)
                with (out/'neural_metrics.csv').open('a') as f:f.write('o,0,2,n,1\n')
                with self.assertRaises(ValueError):validate_final(cfg,plan,state,{})
                with self.assertRaises(ValueError):validate_final(cfg,plan,dict(state,status='global_fits_complete'),{})

    @unittest.skipUnless(os.name == 'posix', 'Linux completion callback')
    def test_complete_shard_saves_then_mock_stops_and_corrupt_archive_retains(self):
        class S3:
            def __init__(self):self.objects={}
            def get_object(self,**kw):
                body=self.objects[kw['Key']]
                return {'Body':io.BytesIO(body),'ContentLength':len(body)}
            def put_object(self,**kw):self.objects[kw['Key']]=kw['Body']
        from multibox_support import object_key
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d); root=p/'parallel-63'; root.mkdir(); work=root/'run';work.mkdir()
            assignment=root/'assignment.json'
            plan={'instances':{'C':'i-c'},'cohorts':[{'owner':'C','cohort':['o','1','2']}]}
            assignment.write_text(json.dumps(plan)); digest=hashlib.sha256(assignment.read_bytes()).hexdigest()
            key=['core',['o','1','2'],'m']
            receipt=dict(status='fits_complete',worker='C',coverage_gate='NOT_PASSED',assignment_sha256=digest,
                cohorts=[['o','1','2']],required_jobs=[key],locations=[dict(task=key,folder='jobs/task')],
                archive_sha256=hashlib.sha256(b'abc').hexdigest(),archive_bytes=3)
            (root/'box-C-transfer-receipt.json').write_text(json.dumps(receipt))
            (work/'shard-completion.json').write_text(json.dumps(receipt))
            (work/'recovery-plan.json').write_text(json.dumps(dict(status='shard_fits_complete',
                coverage_gate='NOT_PASSED',required_jobs=[key],committed_jobs=[key],worker_id='C',assignment_sha256=digest,
                all_declared_tasks_mandatory=True,unregistered_cohorts=[],deferred_memory_jobs=[])))
            cache=root/'cache/o-h1-fold2';cache.mkdir(parents=True);(cache/'ready.json').write_text('{"groups":[]}')
            cfg=dict(owner='C',instance='i-c',base=d,out=d,run=str(work),assignment=str(assignment),
                digest=digest,pid=99999999,token='old',shutdown_behavior_verified='stop',receipt_key='stop.json')
            s3=S3();s3.objects[object_key(digest,'C-status.json')]=json.dumps(receipt).encode()
            archive_key=object_key(digest,'C-results.tar.gz');s3.objects[archive_key]=b'abc'
            stopped=[]
            with patch('family_completion_hook.imds_instance',return_value='i-c'),patch('multibox_support.client',return_value=s3),patch('resume_multibox_candidate.expected_models',return_value=(['m'],[])):
                run(cfg,lambda:stopped.append(True))
                self.assertTrue(stopped)
                self.assertTrue(json.loads(s3.objects['stop.json'])['backup_verified'])
                stopped.clear();s3.objects[archive_key]=b'bad'
                with self.assertRaises(ValueError):run(cfg,lambda:stopped.append(True))
                self.assertFalse(stopped)


if __name__ == '__main__': unittest.main()
