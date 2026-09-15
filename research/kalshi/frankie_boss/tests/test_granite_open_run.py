from research.kalshi.frankie_boss import granite_retained_lifecycle as life


def test_open_start_has_no_elapsed_budget_and_observer_replacement_never_restarts(monkeypatch):
    info = dict(pod_id=life.POD_ID, intent={})
    startup = life.make_startup(info, start=1000., request_sha256='a'*64,
        local_ready=dict(request_sha256='a'*64, host_instance_id='local-ready-instance', admitted_at=999.))
    assert startup['startup_deadline'] is None
    run = life.make_run(info, startup, ready_at=1000000.)
    assert run['deadline'] is None
    class Journal:
        def get(self, name):
            assert name == 'retained-start-intent.json'
            return dict(startup_sha256=life.check_startup(startup, info), pod_id=life.POD_ID)
    class Api:
        def request(self, *args):
            raise AssertionError('reobserving an existing start must not mutate the Pod')
    result = life.start_once(Api(), Journal(), info, {}, startup, now=2000000.,
        request_body=b'', tokenizer_admission=None, expected_watchdog_identity=None)
    assert result['status'] == 'observe_existing_start'
