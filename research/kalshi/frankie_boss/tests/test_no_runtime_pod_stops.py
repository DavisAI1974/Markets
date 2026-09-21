"""Greg, 2026-09-21: NO runtime stops on Pod startup or lifecycle.

Pins the text of the prepare path (no stop option, no stop call), the keep-running twin's contract
(one read, no action), and completion cleanup releasing the run claim on kept_running.
"""
import re
from pathlib import Path

from research.kalshi.frankie_boss import granite_cloud_resume as resume
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss import granite_runpod_cloud_control as control
from research.kalshi.frankie_boss.granite_active_run import completion_cleanup
from research.kalshi.frankie_boss.tests.test_granite_active_run import ActiveRunStore, S3, Journal

HERE = Path(__file__).resolve().parents[1]


def intent():
    return dict(schema='GRANITE_CLOUD_INTENT_V1', nonce='a' * 32, name='granite-smoke-' + 'a' * 32 + '-migration',
                image=control.granite_runpod.IMAGE, start=1000, deadline=2800, cleanup_mode='keep')


def test_pod_prepare_carries_no_stop_path():
    source = (HERE / 'operations' / 'pod_prepare.py').read_text(encoding='utf-8')
    assert 'stop_owned_once' not in source
    assert '--on-timeout' not in source and '--stop-after-ready' not in source
    assert "cleanup_mode='keep'" in source


def test_pod_prepare_workflow_exposes_no_stop_input():
    workflow = (HERE.parents[2] / '.github' / 'workflows' / 'frankie_pod_prepare.yml').read_text(encoding='utf-8')
    assert 'on_timeout' not in workflow and 'stop_after_ready' not in workflow and '--on-timeout' not in workflow


def test_keep_owned_once_reads_once_and_never_posts():
    calls = []
    class API:
        def request(self, method, path, body=None):
            calls.append((method, path))
            assert method == 'GET'
            return dict(id='pod_abc123', name=intent()['name'], image=intent()['image'], status='RUNNING',
                        env={'RUNPOD_SMOKE_OWNER': 'a' * 32})
    result = resume.keep_owned_once(API(), intent(), 'pod_abc123')
    assert result == dict(status='kept_running', pod_id='pod_abc123', data_retained=True, pod_status='RUNNING')
    assert calls == [('GET', '/v2/pods/pod_abc123')]


def test_keep_mode_is_admitted_and_selects_the_read_only_twin():
    control.validate_intent(intent())
    assert cloud.cleanup_operation(intent()) is resume.keep_owned_once
    assert cloud.cleanup_confirmed(dict(status='kept_running'), intent())
    assert not cloud.cleanup_confirmed(dict(status='confirmed_stopped'), intent())


def test_completion_cleanup_releases_the_claim_on_kept_running():
    store = ActiveRunStore(S3(), 'bucket', 'pod')
    store.claim('a' * 64)
    journal = Journal()
    calls = []
    def keep(api, intent, pod_id, **options):
        calls.append(pod_id)
        return dict(status='kept_running', pod_id=pod_id, data_retained=True, pod_status='RUNNING')
    result = completion_cleanup(None, journal, store, {'intent': {}}, 'a' * 64, keep)
    assert result['status'] == 'kept_running' and calls == ['pod']
    assert journal.rows['retained-completion-cleanup.json']['startup_sha256'] == 'a' * 64
    assert store.read()[0]['phase'] == 'closed'
    # a replay finds the receipt and releases nothing twice
    assert completion_cleanup(None, journal, store, {'intent': {}}, 'a' * 64, keep)['status'] == 'kept_running'
    assert calls == ['pod']
