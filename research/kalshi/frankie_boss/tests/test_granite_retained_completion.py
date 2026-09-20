import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from research.kalshi.frankie_boss.granite_active_run import canonical
from research.kalshi.frankie_boss.granite_retained_completion import publish_completion


class Journal:
    def __init__(self, startup):
        self.rows = {'retained-startup.json': startup}
    def get(self, name):
        return self.rows.get(name)
    def put(self, name, value, *, once=False):
        if once and name in self.rows:
            raise ValueError('already exists')
        self.rows[name] = value


def test_completion_requires_exact_startup_and_retains_outcome_before_marker():
    startup = dict(request_sha256='a'*64, pod_id='8vqdacl5t61rjx')  # migrated retained Pod, see aa12fd09 port
    digest = hashlib.sha256(canonical(startup)).hexdigest()
    journal = Journal(startup)
    fields = dict(request_sha256='a'*64, startup_sha256=digest,
                  outcome_sha256='b'*64, job_id='c'*64, code_commit='d'*40)
    with pytest.raises(ValueError):
        publish_completion(journal, dict(fields, startup_sha256='e'*64))
    assert 'retained-finished.json' not in journal.rows
    publish_completion(journal, fields)
    assert journal.rows['retained-finished.json'] == {'startup_sha256': digest}
    assert journal.rows['retained-completed-outcome.json'] == fields
    assert list(journal.rows)[-2:] == ['retained-completed-outcome.json', 'retained-finished.json']
    publish_completion(journal, fields)
    with pytest.raises(ValueError):
        publish_completion(journal, dict(fields, outcome_sha256='f'*64))


def test_standalone_writer_validates_code_before_dependencies_or_cloud():
    env = dict(os.environ, **{key.upper(): 'a'*64 for key in
        ('request_sha256', 'startup_sha256', 'outcome_sha256', 'job_id')},
        CODE_COMMIT='b'*40, GITHUB_SHA='c'*40)
    script = Path(__file__).parents[1]/'granite_retained_completion.py'
    result = subprocess.run([sys.executable, '-I', '-S', str(script)],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'checkout differs from actual host code' in result.stderr
    assert 'ModuleNotFoundError' not in result.stderr


def test_standalone_writer_uses_checked_out_code_not_later_marker_commit():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    env = dict(os.environ, **{key.upper(): 'a'*64 for key in
        ('request_sha256', 'startup_sha256', 'outcome_sha256', 'job_id')},
        CODE_COMMIT=head, GITHUB_SHA='c'*40)
    script = Path(__file__).parents[1]/'granite_retained_completion.py'
    # No site-packages are available: reach boto3 import only after code passes,
    # without creating a client or touching any remote service.
    result = subprocess.run([sys.executable, '-I', '-S', str(script)],
                            env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'checkout differs' not in result.stderr
    assert "No module named 'boto3'" in result.stderr
