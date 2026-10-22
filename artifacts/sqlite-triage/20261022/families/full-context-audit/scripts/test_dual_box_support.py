import io,json,os,pathlib,tarfile,tempfile,unittest
from dual_box_support import assigned_cohorts, make_assignment, validate_members, reconcile_keys

class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.cohorts=[('outcome',str(h),str(f)) for h in range(21) for f in [2,3,4]]
        self.state=dict(required_jobs=[['core',list(t),'m'] for t in self.cohorts[:5]],
                        committed_jobs=[['core',list(self.cohorts[0]),'m']],
                        unregistered_cohorts=[list(t) for t in self.cohorts[5:]])
    def test_partition_retains_registered_and_covers_every_cohort(self):
        a=make_assignment(self.state,{'A':'i-a','B':'i-b'})
        left=assigned_cohorts(self.cohorts,a,'A');right=assigned_cohorts(self.cohorts,a,'B')
        self.assertEqual(set(left)|set(right),set(self.cohorts))
        self.assertFalse(set(left)&set(right))
        self.assertTrue(set(self.cohorts[:5])<=set(left))
        self.assertTrue(left and right)
    def test_inflight_preparation_pins_unregistered_cohort(self):
        self.state['pinned_cohorts']=[list(self.cohorts[-1])]
        a=make_assignment(self.state,{'A':'i-a','B':'i-b'})
        self.assertIn(self.cohorts[-1],assigned_cohorts(self.cohorts,a,'A'))

    @unittest.skipIf(os.name=='nt','verify POSIX state links on actual Linux host')
    def test_archive_roundtrip_preserves_preprocessing_link(self):
        from dual_box_support import pack_results,HashReader
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d)/'source';job=root/'jobs'/'task';job.mkdir(parents=True)
            prep=root/'memory-recovery-test'/'rebuilt-cache-0'/'cohort'/'prep.jls'
            prep.parent.mkdir(parents=True);prep.write_bytes(b'original preprocessing')
            (job/'state.jls').symlink_to(prep)
            (job/'job_receipt.json').write_text('{"returncode":0}')
            archive=pathlib.Path(d)/'results.tar.gz'
            pack_results(root,{('core',('o','1','2'),'m'):job},archive)
            dest=pathlib.Path(d)/'dest';dest.mkdir()
            with archive.open('rb') as f:
                reader=HashReader(f)
                with tarfile.open(fileobj=reader,mode='r|gz') as tar:
                    for member in tar:
                        validate_members([member]);tar.extract(member,dest,filter='data')
                while reader.read(8192):pass
            self.assertEqual((dest/'jobs'/'task'/'state.jls').read_bytes(),b'original preprocessing')
            self.assertTrue((dest/'jobs'/'task'/'state.jls').is_symlink())

    def test_missing_duplicate_or_foreign_assignment_refused(self):
        a=make_assignment(self.state,{'A':'i-a','B':'i-b'})
        for rows in [a['cohorts'][:-1],a['cohorts']+[a['cohorts'][0]],
                     a['cohorts'][:-1]+[dict(cohort=['other','1','2'],owner='A')]]:
            with self.assertRaises(ValueError):assigned_cohorts(self.cohorts,dict(a,cohorts=rows),'A')
    def test_archive_paths_cannot_escape_or_replace_shared_inputs(self):
        for name in ['/etc/passwd','../escape','jobs/../../escape','shared/raw.bin']:
            t=tarfile.TarInfo(name)
            with self.assertRaises(ValueError):validate_members([t])
        t=tarfile.TarInfo('jobs/task/state.jls');t.type=tarfile.SYMTYPE;t.linkname='../../../escape'
        with self.assertRaises(ValueError):validate_members([t])
    def test_preprocessing_link_within_shard_is_allowed(self):
        t=tarfile.TarInfo('jobs/task/state.jls');t.type=tarfile.SYMTYPE
        t.linkname='../../memory-recovery-test/rebuilt-cache-0/cohort/prep.jls'
        validate_members([t])
    @unittest.skipIf(os.name=='nt','verify POSIX imported state links on actual Linux host')
    def test_completion_import_checks_archive_and_rebases_state_links(self):
        import hashlib,types
        from unittest.mock import patch
        from dual_box_support import pack_results,receive_b
        with tempfile.TemporaryDirectory() as d:
            d=pathlib.Path(d);source=d/'B';job=source/'jobs'/'task';job.mkdir(parents=True)
            prep=source/'cache'/'cohort'/'prep.jls';prep.parent.mkdir(parents=True)
            prep.write_bytes(b'frozen training preprocessing')
            (job/'state.jls').symlink_to(prep)
            (job/'job_receipt.json').write_text('{"returncode":0}')
            archive=d/'results.tar.gz';raw=pack_results(source,{('core',('o','1','2'),'m'):job},archive)
            data=archive.read_bytes();assignment=d/'ownership.json';assignment.write_text('{}')
            digest=hashlib.sha256(assignment.read_bytes()).hexdigest()
            receipt=dict(status='fits_complete',assignment_sha256=digest,
                archive_sha256=hashlib.sha256(data).hexdigest(),artifact_bytes=raw,
                locations=[dict(task=['core',['o','1','2'],'m'],folder='jobs/task')])
            class FakeS3:
                def get_object(self,**args):
                    body=json.dumps(receipt).encode() if args['Key'].endswith('B-status.json') else data
                    return dict(Body=io.BytesIO(body),ContentLength=len(body))
            root=d/'A';(root/'jobs').mkdir(parents=True)
            is_dir=pathlib.Path.is_dir
            only_fixture=lambda p: False if str(p)=='/opt/frankie-box/archive' else is_dir(p)
            usage=types.SimpleNamespace(free=500*1024**3)
            with patch('dual_box_support.client',return_value=FakeS3()), \
                 patch.object(pathlib.Path,'is_dir',only_fixture), \
                 patch('dual_box_support.shutil.disk_usage',return_value=usage):
                imported,saved=receive_b(d,root,assignment)
            self.assertEqual(set(imported),{('core',('o','1','2'),'m')})
            self.assertEqual((root/'jobs/task/state.jls').read_bytes(),b'frozen training preprocessing')
            self.assertTrue((root/'jobs/task').is_symlink())

    def test_union_requires_disjoint_exact_required_keys(self):
        a=[['core',['o','1','2'],'m']];b=[['core',['o','1','3'],'m']]
        reconcile_keys(a,b,a+b)
        with self.assertRaises(ValueError):reconcile_keys(a,a,a)
        with self.assertRaises(ValueError):reconcile_keys(a,b,a)

if __name__=='__main__':unittest.main()

