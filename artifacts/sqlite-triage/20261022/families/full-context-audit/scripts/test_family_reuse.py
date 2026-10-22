import copy
import pathlib
import unittest
import json
import tempfile
from unittest.mock import patch
from family_reuse_support import task_owner,cohorts_for_worker,validate_preparation,global_ready
from family_reuse_epoch import make_epoch,reuse_source


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.a=['core',['o','1','2'],'a']
        self.b=['core',['p','1','2'],'b']
        self.c=['core',['p','1','2'],'c']
        self.plan=dict(instances={'A':'i-a','B':'i-b'},slots={'A':96,'B':32},
            cohorts=[dict(owner='A',cohort=self.a[1]),dict(owner='B',cohort=self.b[1])],
            coverage_gate='NOT_PASSED')
        self.snapshots={
            'A':dict(required=[self.a],committed=[self.a],jobs=[],unregistered=[],
                     preparations=[dict(cohort=self.a[1],info={'groups':[]})]),
            'B':dict(required=[self.b,self.c],committed=[self.b],jobs=[],unregistered=[],
                     preparations=[dict(cohort=self.b[1],info={'groups':[]})])}

    def test_idle_recipient_takes_only_pending_key(self):
        p=make_epoch(self.plan,self.snapshots,'old')
        self.assertEqual(task_owner(p,self.b),'B')
        self.assertEqual(task_owner(p,self.c),'A')
        self.assertEqual(cohorts_for_worker(None,p,'A'),[tuple(self.a[1]),tuple(self.b[1])])
        self.assertEqual(task_owner(self.plan,self.c),'B')

    def test_running_key_and_completed_key_never_move(self):
        self.snapshots['B']['jobs']=[dict(kind='core',cohort=self.c[1],model='c',pid=1,token='t',cpu=0)]
        with self.assertRaises(ValueError):make_epoch(self.plan,self.snapshots,'old')
        self.snapshots['B']['jobs']=[]
        self.snapshots['B']['committed'].append(self.c)
        with self.assertRaises(ValueError):make_epoch(self.plan,self.snapshots,'old')

    def test_duplicate_or_unowned_capture_refuses_epoch(self):
        self.snapshots['B']['required'].append(self.c)
        with self.assertRaises(ValueError):make_epoch(self.plan,self.snapshots,'old')
        self.snapshots['B']['required'].pop()
        self.snapshots['A']['required'].append(self.c)
        with self.assertRaises(ValueError):make_epoch(self.plan,self.snapshots,'old')

    def test_unknown_training_preparation_cannot_be_delegated(self):
        self.snapshots['B']['preparations']=[]
        with self.assertRaises(ValueError):make_epoch(self.plan,self.snapshots,'old')

    def test_preparation_shape_and_group_changes_refuse(self):
        p=make_epoch(self.plan,self.snapshots,'old')
        validate_preparation(p,tuple(self.b[1]),{'groups':[]})
        with self.assertRaises(ValueError):validate_preparation(p,tuple(self.b[1]),{'groups':['changed']})

    def test_global_readiness_requires_all_owners_same_epoch_and_unique_keys(self):
        rows={x:dict(worker=x,status='fits_complete',assignment_sha256='d',coverage_gate='NOT_PASSED',
             required_jobs=[k]) for x,k in [('A',self.a),('B',self.b)]}
        self.assertTrue(global_ready(self.plan,'d',rows))
        self.assertFalse(global_ready(self.plan,'d',dict(A=rows['A'])))
        rows['B']['required_jobs']=[self.a]
        with self.assertRaises(ValueError):global_ready(self.plan,'d',rows)

    def test_source_is_additive_scheduling_only_and_compiles(self):
        import resume_multibox_candidate
        original=pathlib.Path(resume_multibox_candidate.__file__).read_text()
        source=reuse_source(original)
        self.assertIn('wait_all_shards(',source)
        self.assertIn('validate_preparation(',source)
        self.assertIn('task_owner(assignment,k)',source)
        self.assertIn('Budget(total, 192*GIB',source)
        compile(source,'reuse-source','exec')

    def test_bootstrap_freezes_all_mandatory_keys_without_moving_work(self):
        self.snapshots['A']['jobs']=[dict(kind='core',cohort=self.a[1],model='a',pid=7,token='t',cpu=0)]
        p=make_epoch(self.plan,self.snapshots,'old',bootstrap=True)
        self.assertEqual(p['task_delegations'],[])
        self.assertEqual(len(p['mandatory_jobs']),3)

    def test_two_finished_helpers_receive_disjoint_pending_tasks(self):
        d=['core',['q','1','2'],'d']
        self.plan['instances']['C']='i-c';self.plan['slots'].update(A=16,C=16)
        self.plan['cohorts'].append(dict(owner='C',cohort=d[1]))
        self.snapshots['C']=dict(required=[d],committed=[d],jobs=[],unregistered=[],preparations=[])
        self.snapshots['B']['required'] += [['core',self.b[1],'pending'+str(n)] for n in range(35)]
        p=make_epoch(self.plan,self.snapshots,'old')
        tasks=[json.dumps(row['task']) for row in p['pending_transfers']]
        self.assertEqual(len(tasks),32)
        self.assertEqual(len(set(tasks)),32)
        self.assertEqual({r['owner'] for r in p['pending_transfers']},{'A','C'})

    def test_verified_box_waits_for_exact_global_release_before_shutdown(self):
        from family_reuse_support import wait_before_stop
        rows={x:dict(worker=x,status='fits_complete',assignment_sha256='d'*64,coverage_gate='NOT_PASSED',required_jobs=[k])
              for x,k in [('A',self.a),('B',self.b)]}
        proof=dict(status='all_fits_complete',assignment_sha256='d'*64,coverage_gate='NOT_PASSED',shards=rows)
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder)/'plan.json';path.write_text(json.dumps(self.plan))
            config=dict(reuse_before_stop=True,owner='B',assignment=str(path),digest='d'*64,receipt_key='proof',run=folder)
            with patch('family_reuse_support.publish'),patch('family_reuse_support.optional_json',side_effect=[None,proof]),patch('family_reuse_support.time.sleep') as sleep:
                wait_before_stop(None,config)
                sleep.assert_called_once_with(15)
            self.assertEqual(json.loads((pathlib.Path(folder)/'hook-status.json').read_text())['status'],'backup_verified_ready_for_reuse')

    def test_exited_replacement_requires_exact_complete_shard_before_rearm(self):
        from family_reuse_rollout import validate_replacement_exit
        config=dict(owner='B');receipt=dict(token='t',digest='d');state=dict(status='shard_fits_complete')
        completion=dict(worker='B',assignment_sha256='d',status='fits_complete')
        validate_replacement_exit(config,receipt,state,completion,None)
        for bad in (None,dict(completion,assignment_sha256='wrong'),dict(completion,worker='C')):
            with self.assertRaises(ValueError):validate_replacement_exit(config,receipt,state,bad,None)
        with self.assertRaises(ValueError):validate_replacement_exit(config,receipt,state,completion,'reused')
        with self.assertRaises(ValueError):validate_replacement_exit(dict(owner='A'),receipt,state,completion,None)


if __name__=='__main__':unittest.main()
