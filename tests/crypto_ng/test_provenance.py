"""The crypto and ng program is the July program: each file's git blob id equals the one on Markets `75b15fa`."""
import hashlib
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[2] / 'crypto_ng' / 'program'
JULY = {'flip_detector.py': '8d0ff2f0e9c7bfda7550becf781bd6690f873eeb',
        'swing_maker.py': '3ea61f3eb3bcf0bed07e51fcc964d1040ead900d',
        'info_dipole.py': 'c04751cbe5f92952e33328f6c04fcae6392e05e5',
        'platform.py': '5b299d7b00ab5b1dacde449285e8081dc98812a4'}


def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()


def test_three_files_are_byte_for_byte_the_july_files():
    for name in ('flip_detector.py', 'swing_maker.py', 'info_dipole.py'):
        assert blob((PROGRAM / name).read_bytes()) == JULY[name], name


def test_platform_differs_in_its_three_import_lines_only():
    raw = (PROGRAM / 'platform.py').read_bytes()
    assert raw.count(b'from crypto_ng.program.') == 3
    assert blob(raw.replace(b'from crypto_ng.program.', b'from odcore.')) == JULY['platform.py']
