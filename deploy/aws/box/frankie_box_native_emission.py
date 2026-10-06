"""Exact native emission coordinates beside unchanged pinned scientific values.

One group context spans member and lifecycle retention, including continuity
closes before the member write. Terminal rows have an explicit FINALIZE phase;
they are not attributed to a fictional last F_LAST group. No sink is replaced.
"""
import hashlib
from pathlib import Path
from types import MethodType

SCHEMA = 'FRANKIE_NATIVE_EMISSION_V1'
KEY = 'frankie_emission'


def binding():
    return dict(schema=SCHEMA, helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def _coordinates(driver, *, phase, group_index, instrument_id, ts_recv_ns):
    return dict(schema=SCHEMA, phase=phase, group_index=group_index,
                input_cursor=int(driver.counters.records_seen) - 1,
                instrument_id=instrument_id, ts_recv_ns=ts_recv_ns)


def _with_emission(row, context):
    if KEY in row:
        raise ValueError('native producer already owns the reserved emission key')
    copied = dict(row)
    copied[KEY] = dict(context)
    return copied


def _on_group(self, envelope, source_object):
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import NativeReplayDriver
    context = _coordinates(self, phase='GROUP_CLOSE', group_index=int(self.counters.groups_seen),
                           instrument_id=int(envelope['instrument_id']),
                           ts_recv_ns=int(envelope['ts_recv_ns']))
    copied = dict(envelope)
    copied['compact_event_frame'] = _with_emission(envelope['compact_event_frame'], context)
    previous = self._frankie_emission_context
    self._frankie_emission_context = context
    try:
        # The pinned implementation carries every frame key into its member row.
        # Its clocks, section ordering, counters and original values stay intact.
        return NativeReplayDriver._on_group(self, copied, source_object)
    finally:
        self._frankie_emission_context = previous


def _retain_lifecycle(self, rows, *, section, occasion):
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import NativeReplayDriver
    context = self._frankie_emission_context

    def retained_rows():
        for row in rows or ():
            if context is None:
                raise ValueError('native lifecycle retention has no exact emission boundary')
            yield _with_emission(row, context)

    # Retain lazily, once, through the original writer and its original section,
    # occasion and availability stamp. No copied evidence pass or duplicate rows.
    return NativeReplayDriver._retain_lifecycle(self, retained_rows(), section=section, occasion=occasion)


def _finalize(self, *, recv_ns=None):
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import NativeReplayDriver
    at = recv_ns if recv_ns is not None else (self._last_recv_ns or 0)
    previous = self._frankie_emission_context
    self._frankie_emission_context = _coordinates(
        self, phase='FINALIZE', group_index=None, instrument_id=None, ts_recv_ns=at)
    try:
        return NativeReplayDriver.finalize(self, recv_ns=recv_ns)
    finally:
        self._frankie_emission_context = previous


def install(driver):
    """Install/rebind top-level methods on a fresh or closed-group restored driver.

    Full-state checkpoints can be captured inside _on_group after all work has
    committed. Restore resumes after that group, so its transient context clears.
    RuntimeSections owns _feed_sections and the member bridge; neither is touched.
    """
    from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import NativeReplayDriver
    if type(driver) is not NativeReplayDriver:
        raise ValueError('native emission requires the pinned NativeReplayDriver')
    expected = binding()
    previous = getattr(driver, '_frankie_emission_binding', None)
    if previous is not None and previous != expected:
        raise ValueError('native emission helper differs from its checkpoint')
    wrappers = {'_on_group': _on_group, '_retain_lifecycle': _retain_lifecycle, 'finalize': _finalize}
    for name, wrapper in wrappers.items():
        existing = vars(driver).get(name)
        if existing is not None and getattr(existing, '__func__', None) is not wrapper:
            raise ValueError('native emission would replace an existing driver method: ' + name)
        if existing is None and getattr(getattr(driver, name), '__func__', None) is not getattr(NativeReplayDriver, name):
            raise ValueError('native emission driver method is not the pinned implementation: ' + name)
    driver._frankie_emission_binding = expected
    driver._frankie_emission_context = None
    for name, wrapper in wrappers.items():
        setattr(driver, name, MethodType(wrapper, driver))
    return expected
