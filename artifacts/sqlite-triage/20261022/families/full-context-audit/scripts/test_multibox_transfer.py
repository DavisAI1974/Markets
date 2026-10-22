import io,json,os,pathlib,tarfile,tempfile,unittest
from multibox_support import validate_members
class MultiTransferTests(unittest.TestCase):
    @unittest.skipIf(os.name=='nt','verify POSIX state links on actual Linux host')
    def test_archive_roundtrip_preserves_preprocessing_link(self):
        from multibox_support import pack_results,HashReader
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
    @unittest.skipIf(os.name=='nt','verify POSIX imported state links on actual Linux host')
    def test_completion_import_checks_archive_and_rebases_state_links(self):
        import hashlib,types
        from unittest.mock import patch
        from multibox_support import pack_results,receive_shard
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
                    body=json.dumps(receipt).encode() if args['Key'].endswith('C-status.json') else data
                    return dict(Body=io.BytesIO(body),ContentLength=len(body))
            root=d/'A';(root/'jobs').mkdir(parents=True)
            is_dir=pathlib.Path.is_dir
            only_fixture=lambda p: False if str(p)=='/opt/frankie-box/archive' else is_dir(p)
            usage=types.SimpleNamespace(free=500*1024**3)
            with patch('multibox_support.client',return_value=FakeS3()), \
                 patch.object(pathlib.Path,'is_dir',only_fixture), \
                 patch('multibox_support.shutil.disk_usage',return_value=usage):
                imported,saved=receive_shard(d,root,assignment,'C')
            self.assertEqual(set(imported),{('core',('o','1','2'),'m')})
            self.assertEqual((root/'jobs/task/state.jls').read_bytes(),b'frozen training preprocessing')
            self.assertTrue((root/'jobs/task').is_symlink())
