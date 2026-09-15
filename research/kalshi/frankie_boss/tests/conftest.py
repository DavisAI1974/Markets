"""Run every verified-reader test under each declared worker count.

Only the reader test modules are parametrized; the rest of the suite is untouched. The
worker count reaches the reader through FRANKIE_JOURNAL_VERIFY_WORKERS, the same channel a
launcher uses, so acceptance AND rejection are proven identical across worker counts,
not just the happy path.
"""
import pytest

# test_verified_journal_reader and test_cpu_worker_policy pass workers= explicitly and are
# not repeated here; these two construct readers the way the host does, through the environment.
READER_TEST_MODULES = {'test_verified_reader_concurrent_tail', 'test_journal_prefix_snapshot'}
READER_WORKER_COUNTS = (1, 2, 4)


def pytest_generate_tests(metafunc):
    if metafunc.module.__name__.rsplit('.', 1)[-1] in READER_TEST_MODULES:
        metafunc.fixturenames.append('reader_workers')
        metafunc.parametrize('reader_workers', READER_WORKER_COUNTS, indirect=True,
                             ids=[f'workers={n}' for n in READER_WORKER_COUNTS])


@pytest.fixture
def reader_workers(request, monkeypatch):
    monkeypatch.setenv('FRANKIE_JOURNAL_VERIFY_WORKERS', str(request.param))
    return request.param
