import pytest

from research.kalshi.frankie_boss.operations.audit_sunday_restoration_manifest import audit


def base_manifest():
    return dict(schema='FRANKIE_SUNDAY_RESTORATION_MANIFEST_V1',
        configuration_sha256='f'*64,files_bulk=2,
        pinned_files=[dict(path='E:/bulk/a.bin',sha256='a'*64)],secondary_pins=[],files=[
            dict(original_path='E:/bulk/a.bin',bytes=10,in_git=False,sha256=None),
            dict(original_path='E:/bulk/b.bin',bytes=20,in_git=False,sha256='b'*64),
            dict(original_path='E:/small/c.json',bytes=3,in_git=True,sha256='c'*64),
        ])


def addendum(path='E:/bulk/a.bin', size=10, digest='a'*64):
    return dict(schema='FRANKIE_SUNDAY_BULK_HASH_ADDENDUM_V1',
        manifest_configuration_sha256='f'*64,files=[dict(path=path,bytes=size,
            sha256=digest,closed=True,sidecars_absent=True)])


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


def test_addendum_closes_missing_bulk_hash_without_editing_manifest():
    manifest=base_manifest()
    manifest['pinned_files']=[]
    result=audit(manifest,addendum())
    assert result['passed'] is True
    assert result['addendum_files']==1
    assert result['hash_complete']==2


def test_conflicting_bulk_hashes_fail_closed():
    manifest=base_manifest()
    manifest['files'][0]['sha256']='d'*64
    result=audit(manifest)
    assert result['passed'] is False
    assert result['conflicting_hashes'][0]['original_path']=='E:/bulk/a.bin'


def test_addendum_conflict_with_existing_pin_fails_closed():
    result=audit(base_manifest(),addendum(digest='d'*64))
    assert result['passed'] is False
    assert result['conflicting_hashes'][0]['original_path']=='E:/bulk/a.bin'


def test_addendum_requires_closed_file_and_absent_sidecars():
    value=addendum();value['files'][0]['sidecars_absent']=False
    with pytest.raises(ValueError,match='closed file'):
        audit(base_manifest(),value)


def test_addendum_byte_count_must_match_manifest():
    with pytest.raises(ValueError,match='byte count'):
        audit(base_manifest(),addendum(size=11))


def test_addendum_cannot_introduce_nonbulk_path():
    with pytest.raises(ValueError,match='outside manifest bulk set'):
        audit(base_manifest(),addendum(path='E:/bulk/not-in-manifest.bin'))
