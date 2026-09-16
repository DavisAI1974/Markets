from research.kalshi.frankie_boss.operations.audit_sunday_restoration_manifest import audit


def base_manifest():
    return dict(schema='FRANKIE_SUNDAY_RESTORATION_MANIFEST_V1',files_bulk=2,
        pinned_files=[dict(path='E:/bulk/a.bin',sha256='a'*64)],secondary_pins=[],files=[
            dict(original_path='E:/bulk/a.bin',bytes=10,in_git=False,sha256=None),
            dict(original_path='E:/bulk/b.bin',bytes=20,in_git=False,sha256='b'*64),
            dict(original_path='E:/small/c.json',bytes=3,in_git=True,sha256='c'*64),
        ])


def test_bulk_hash_can_come_from_independent_pin_or_file_row():
    result=audit(base_manifest())
    assert result['passed'] is True
    assert result['bulk_files']==2
    assert result['hash_complete']==2


def test_bulk_without_any_sha256_fails_closed():
    manifest=base_manifest()
    manifest['pinned_files']=[]
    result=audit(manifest)
    assert result['passed'] is False
    assert [row['original_path'] for row in result['missing_hashes']]==['E:/bulk/a.bin']


def test_conflicting_bulk_hashes_fail_closed():
    manifest=base_manifest()
    manifest['files'][0]['sha256']='d'*64
    result=audit(manifest)
    assert result['passed'] is False
    assert result['conflicting_hashes'][0]['original_path']=='E:/bulk/a.bin'
