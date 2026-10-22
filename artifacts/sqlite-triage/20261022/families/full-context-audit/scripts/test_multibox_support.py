import unittest
from multibox_support import expand_assignment, assigned_cohorts, reconcile_keys

class FourBoxOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.cohorts=[('o',str(h),str(f)) for h in range(21) for f in [2,3,4]]
        self.old=dict(instances={'A':'i-a','B':'i-b'},coverage_gate='NOT_PASSED',
            cohorts=[dict(cohort=list(t),owner='A' if i<32 else 'B') for i,t in enumerate(self.cohorts)])
        self.states={o:dict(required_jobs=[],committed_jobs=[],unregistered_cohorts=[r['cohort'] for r in self.old['cohorts'] if r['owner']==o]) for o in ['A','B']}
    def expand(self,active=None):
        return expand_assignment(self.old,self.states,active or {'A':[],'B':[]},
                                 {'C':'i-c','D':'i-d'},{'A':96,'B':96,'C':32,'D':32})
    def test_preserve_prior_required_active_and_completed(self):
        registered=self.cohorts[0];live=self.cohorts[-1]
        self.states['A']['required_jobs']=[['neural',list(registered),'m']]
        self.states['A']['committed_jobs']=[['neural',list(registered),'m']]
        self.states['A']['unregistered_cohorts'].remove(list(registered))
        v=self.expand({'A':[],'B':[dict(cohort=list(live))]})
        owners={tuple(r['cohort']):r['owner'] for r in v['cohorts']}
        self.assertEqual(owners[registered],'A');self.assertEqual(owners[live],'B')
        self.assertEqual(len(owners),63)
        self.assertEqual(set(owners.values()),{'A','B','C','D'})
        for owner in v['instances']:assigned_cohorts(self.cohorts,v,owner)
    def test_refuse_missing_source_cohort(self):
        self.states['A']['unregistered_cohorts'].pop()
        with self.assertRaises(ValueError):self.expand()
    def test_no_capacity_when_all_work_started(self):
        for o in self.states:
            self.states[o]['required_jobs']=[['core',t,'m'] for t in self.states[o]['unregistered_cohorts']]
            self.states[o]['unregistered_cohorts']=[]
        with self.assertRaises(ValueError):self.expand()
    def test_four_way_unique_required_union(self):
        pieces=[[['core',list(t),'m'] for t in self.cohorts[i::4]] for i in range(4)]
        union=[]
        for p in pieces:
            reconcile_keys(union,p,union+p);union+=p
        with self.assertRaises(ValueError):reconcile_keys(union,pieces[0],union)
    def test_completed_preparation_metadata_survives_without_live_wrapper(self):
        import tempfile,pathlib
        from multibox_support import prepared_cache_index
        with tempfile.TemporaryDirectory() as d:
            cache=pathlib.Path(d)/'memory-recovery-old/rebuilt-cache-0/o-h1-fold2'
            cache.mkdir(parents=True);(cache/'ready.json').write_text('{}')
            rows=prepared_cache_index(d,[('o','1','2'),('o','2','2')])
            self.assertEqual(rows,[dict(cohort=['o','1','2'],cache=str(cache))])
    def test_added_shard_publishes_its_own_archive_and_receipt(self):
        import importlib.util
        if importlib.util.find_spec('boto3') is None:self.skipTest('AWS SDK checked on Linux host')
        import tempfile,pathlib
        from unittest.mock import patch,Mock
        from multibox_support import publish_shard
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);job=root/'jobs/task';job.mkdir(parents=True)
            (job/'weights.jls').write_bytes(b'retained model weights')
            assignment=root/'ownership.json';assignment.write_text('{}')
            s3=Mock();tasks={('neural',('o','1','2'),'m')}
            with patch('multibox_support.client',return_value=s3):
                receipt=publish_shard(root,{next(iter(tasks)):job},tasks,[('o','1','2')],assignment,'C')
            self.assertEqual(receipt['worker'],'C')
            self.assertTrue((root/'box-C-transfer-receipt.json').is_file())
            self.assertTrue(s3.upload_file.call_args.args[2].endswith('/C-results.tar.gz'))
            self.assertTrue(s3.put_object.call_args.kwargs['Key'].endswith('/C-status.json'))

if __name__=='__main__':unittest.main()
