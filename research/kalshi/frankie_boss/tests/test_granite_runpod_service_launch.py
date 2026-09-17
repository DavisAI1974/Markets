"""Only new launch behavior; the passing smoke/control baseline is retained."""
import hashlib
import json
import pytest
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss.tests.test_granite_runpod_cloud_control import intent


def test_thirty_minute_limit_and_no_larger_window():
    item = intent()
    item['deadline'] = item['start'] + cloud.TOTAL_SECONDS
    assert cloud.TOTAL_SECONDS == 1800
    cloud.control.validate_intent(item)
    for duration in (1201, 1801, 3600):
        item['deadline'] = item['start'] + duration
        with pytest.raises(ValueError):
            cloud.control.validate_intent(item)


def test_supervisor_metadata_only_is_removed():
    from types import SimpleNamespace
    environment = {'SUPERVISOR_ENABLED': '1', 'SUPERVISOR_PROCESS_NAME': 'app',
                   'SUPERVISOR_GROUP_NAME': 'app', 'SUPERVISOR_PROGRAM__APP_COMMAND': 'pinned',
                   'SUPERVISOR_UNAPPROVED_OVERRIDE': 'still rejected by bootstrap'}
    exec(cloud.supervisor_metadata_code(), {'os': SimpleNamespace(environ=environment)})
    assert environment == {'SUPERVISOR_PROGRAM__APP_COMMAND': 'pinned',
                           'SUPERVISOR_UNAPPROVED_OVERRIDE': 'still rejected by bootstrap'}


@pytest.mark.parametrize('during_write', [False, True])
def test_service_publication_refuses_cleanup_race(monkeypatch, tmp_path, during_write):
    clock = [2500 if during_write else 2650]
    monkeypatch.setattr(cloud.time, 'time', lambda: clock[0])
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    class Journal:
        def put(self, *args, **kwargs):
            assert during_write
            clock[0] = 2680
    with pytest.raises(TimeoutError):
        cloud.publish_service(Journal(), 'abc123', {'deadline': 2800}, {})
    assert not (tmp_path/'service-ready.json').exists()


@pytest.mark.parametrize('value', [None, 'other'])
def test_unexpected_supervisor_metadata_refused(value):
    from types import SimpleNamespace
    with pytest.raises(SystemExit):
        exec(cloud.supervisor_metadata_code(), {'os': SimpleNamespace(environ={'SUPERVISOR_ENABLED': value})})


def test_bounded_smoke_launch_is_retired_before_any_intent_or_provider_call(monkeypatch, tmp_path):
    # The bounded cloud smoke was built on the 4,096-token smoke context and its pinned admission receipt. Both are
    # retired: the receipt artifact is gone from the tree and the controller refuses at entry (Greg, 2026-09-16).
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setattr(cloud, 'OUT', tmp_path)
    assert not (cloud.ROOT / 'runpod_cloud_admission.json').exists()
    assert not hasattr(cloud, 'ADMISSION_SHA')
    class Journal:
        def __init__(self): self.values = {}
        def get(self, name): pytest.fail('retired launch must not read the journal')
        def put(self, name, value, **kwargs): self.values[name] = value
    class API:
        def request(self, *args, **kwargs): pytest.fail('provider must not be called on a retired launch')
    journal = Journal()
    with pytest.raises(ValueError, match='retired with the 4096 context'):
        cloud.controller(journal, API())
    assert journal.values == {}
