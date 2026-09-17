import json
from pathlib import Path

import pytest

from research.kalshi.frankie_boss import launch_pins

PACKAGE = Path(__file__).resolve().parent.parent / 'sunday_20260915_package' / 'FB' / 'sunday-launch-20260915'


def fresh():
    return {'receiver_commit': launch_pins.NEXT_RUN['receiver_commit'],
            'principal_admission': {'output_bundle': {'principal_artifact': 'artifact.json', 'outputs_dir': 'outputs'},
                                    'sealed_proof': 'sealed-proof.json'},
            'host_runtime': {'boss_commit': 'f'*40, 'context_encoding': 'stacked_v1', 'native_threads': 8,
                             'science_byte_exceptions': dict(launch_pins.NEXT_RUN['science_byte_exceptions']),
                             'repository': '/opt/frankie/Markets'}}


def test_fresh_pins_validate_and_the_historical_configuration_is_refused_with_every_reason():
    launch_pins.validate(fresh(), boss_commit='f'*40)
    reasons = launch_pins.historical_configuration_is_refused(PACKAGE / 'actual-host-final-configuration.json', boss_commit='f'*40)
    for named in ('boss_commit', 'receiver_commit', 'retired 2026-09-15 completion ref', 'principal_admission', 'desktop path'):
        assert named in reasons, reasons
    stale = fresh(); stale['host_runtime']['native_threads'] = 48; stale['principal_admission']['sealed_proof'] = 'UNPROVEN'
    with pytest.raises(ValueError, match='native_threads.*UNPROVEN'):
        launch_pins.validate(stale, boss_commit='f'*40)
