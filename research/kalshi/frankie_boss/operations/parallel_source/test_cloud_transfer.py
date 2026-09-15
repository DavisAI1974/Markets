"""Small new archive-boundary tests; never reads a source journal or uses network."""
import io
import tarfile
import unittest
from cloud_transfer import safe_members

def archive_with(name, kind=tarfile.REGTYPE):
    memory = io.BytesIO()
    with tarfile.open(fileobj=memory, mode='w') as archive:
        member = tarfile.TarInfo(name)
        member.type = kind
        if kind == tarfile.SYMTYPE:
            member.linkname = '/etc/passwd'
        archive.addfile(member)
    memory.seek(0)
    return tarfile.open(fileobj=memory, mode='r')

class ArchiveBoundaries(unittest.TestCase):
    def test_exact_bundle_member_is_retained(self):
        with archive_with('bundle/checkpoint.json') as archive:
            self.assertEqual([v.name for v in safe_members(archive)], ['bundle/checkpoint.json'])

    def test_escape_absolute_and_link_are_rejected(self):
        for name, kind in (('bundle/../../outside',tarfile.REGTYPE),
                           ('/bundle/file',tarfile.REGTYPE),
                           ('other/file',tarfile.REGTYPE),
                           ('bundle/link',tarfile.SYMTYPE)):
            with self.subTest(name=name), archive_with(name,kind) as archive:
                with self.assertRaises(ValueError):
                    list(safe_members(archive))

if __name__ == '__main__':
    unittest.main()
