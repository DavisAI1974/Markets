import asyncio

import pytest

from test_feedback_cycle import fixture


def test_new_request_cannot_use_weights_before_previous_feedback_availability(tmp_path, monkeypatch):
    store, checkpoint, args, calls = fixture(tmp_path, monkeypatch)
    asyncio.run(store.run(**args))
    args['request_id'] = 'next'
    args['learning_kwargs'] = dict(args['learning_kwargs'], as_of=19, through_cursor=3)
    args['controller_factory'] = lambda: pytest.fail('future-trained weights used in the past')
    with pytest.raises(ValueError, match='feedback availability'):
        asyncio.run(store.run(**args))
    assert calls['learner'] == 1
    store.close()
    checkpoint.close()
