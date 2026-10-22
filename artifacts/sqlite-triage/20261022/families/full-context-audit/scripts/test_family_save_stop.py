import hashlib,io,json,pathlib,tempfile,unittest
from family_save_stop import validate_shard, verify_remote, validate_predictions, record_and_stop

class SaveStopTests(unittest.TestCase):
    def setUp(self):
        self.key=['core',['o','1','2'],'m']
        self.plan={'cohorts':[{'owner':'C','cohort':['o','1','2']}],'instances':{'C':'i-c'}}
        self.config={'owner':'C','instance':'i-c','digest':'d'*64,'receipt_key':'receipt.json'}
        self.state={'status':'shard_fits_complete','coverage_gate':'NOT_PASSED',
                    'required_jobs':[self.key],'committed_jobs':[self.key]}
        self.receipt={'status':'fits_complete','worker':'C','coverage_gate':'NOT_PASSED',
            'assignment_sha256':'d'*64,'cohorts':[['o','1','2']],
            'required_jobs':[self.key],'locations':[{'task':self.key,'folder':'jobs/task'}],
            'archive_sha256':'a'*64,'archive_bytes':3}
    def test_completed_shard_validates_exact_required_and_committed_keys(self):
        validate_shard(self.config,self.plan,self.state,self.receipt)
        self.state['committed_jobs']=[]
        with self.assertRaises(ValueError):validate_shard(self.config,self.plan,self.state,self.receipt)
    def test_wrong_owner_or_duplicate_keys_refuse_shutdown(self):
        self.receipt['worker']='D'
        with self.assertRaises(ValueError):validate_shard(self.config,self.plan,self.state,self.receipt)
        self.receipt['worker']='C';self.receipt['required_jobs']*=2
        with self.assertRaises(ValueError):validate_shard(self.config,self.plan,self.state,self.receipt)
    def test_s3_full_archive_bytes_must_match_recorded_hash(self):
        class S3:
            def get_object(self,**kw):return {'Body':io.BytesIO(b'abc'),'ContentLength':3}
        verify_remote(S3(),'key',hashlib.sha256(b'abc').hexdigest(),3)
        with self.assertRaises(ValueError):verify_remote(S3(),'key','0'*64,3)
        with self.assertRaises(ValueError):verify_remote(S3(),'key',hashlib.sha256(b'abc').hexdigest(),4)
    def test_predictions_require_unique_samples_and_exact_declared_counts(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'pred.csv'
            head='outcome,horizon_s,fold,model,sample_id,prediction,observed\n'
            p.write_text(head+'o,1,2,m,s1,0.2,0\no,1,2,m,s2,0.3,1\n')
            required={('o','1','2','m'):2}
            self.assertEqual(validate_predictions(p,required)['rows'],2)
            p.write_text(head+'o,1,2,m,s1,0.2,0\no,1,2,m,s1,0.3,1\n')
            with self.assertRaises(ValueError):validate_predictions(p,required)
    def test_no_stop_until_backup_receipt_is_read_back_identically(self):
        events=[]
        class S3:
            def put_object(self,**kw):events.append('put');self.body=kw['Body']
            def get_object(self,**kw):events.append('get');return {'Body':io.BytesIO(self.body),'ContentLength':len(self.body)}
        with tempfile.TemporaryDirectory() as d:
            cfg=dict(self.config,run=d)
            record_and_stop(S3(),cfg,{'backup_verified':True},lambda:events.append('stop'))
        self.assertEqual(events,['put','get','stop'])
        class BadS3(S3):
            def get_object(self,**kw):return {'Body':io.BytesIO(b'{}'),'ContentLength':2}
        events=[]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):record_and_stop(BadS3(),dict(self.config,run=d),{'backup_verified':True},lambda:events.append('stop'))
        self.assertNotIn('stop',events)

if __name__=='__main__':unittest.main()
