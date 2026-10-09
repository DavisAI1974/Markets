"""Durable full native-driver save/restore; pinned producer math is unchanged."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import threading
import time

import cloudpickle
from research.kalshi.frankie_raw_mbo_benchmark import periodic_checkpointer as P
from frankie_box_prepare_trading_day import safe_path, save_new, sync_directory, witness
import frankie_box_segmented_ledger as ledger_storage
import frankie_box_finalization as finalization

SCHEMA = 'FRANKIE_NATIVE_FULL_STATE_V1'
RUNTIME_SCHEMA = 'FRANKIE_NATIVE_RUNTIME_CODE_V2'
# Greg, 2026-10-09 (standing): the code version is RECORDED, NEVER COMPARED. A saved full state is accepted on the
# FORMAT of its saved bytes only: NATIVE_STATE_FORMAT (a small integer, bumped ONLY when the pickled object graph, the
# descriptor or the ledger-storage layout a save carries changes FORMAT) plus the Python major.minor (the pickle
# compatibility key: a pickled object graph's code objects and protocol belong to a minor version). The full Python
# version string and the cloudpickle version are recorded, never compared (a patch rebuild of the venv keeps every
# save). Every code identity below (serializer_code,
# ledger_storage_code, finalization_code, finalization_sha256 and the earlier whole-file *_sha256 forms) is recorded
# beside them and never refuses a save. A save written before this field existed (every V1 and V2 runtime form up to
# 2026-10-09) carries format 1: the object graph, the descriptor and the segment storage are those of format 1.
NATIVE_STATE_FORMAT = 1
RECORDED_CODE = ('serializer_code', 'ledger_storage_code', 'finalization_code', 'finalization_sha256',
                 'serializer_sha256', 'ledger_storage_sha256')
# The definitions in THIS file whose change may change the saved FORMAT (bump NATIVE_STATE_FORMAT when it does); their
# identity is recorded as serializer_code.
NATIVE_VALUE_CODE = ('SCHEMA', 'sink_items', 'ledger_state', 'copy_ledger_prefixes', '_runtime_binding', 'StatePickler',
                     'StateUnpickler',
                     'FullCheckpointer.externals', 'FullCheckpointer._write', 'FullCheckpointer.save_boundary',
                     'restore_driver', 'compare_reconstructed_prefix', 'consume_recovery')


def runtime_identity():
    """The runtime a full state is written under: schema, NATIVE_STATE_FORMAT and the Python major.minor (the compared
    fields), the full Python version, cloudpickle and the code identities of this file, frankie_box_segmented_ledger
    and frankie_box_finalization (recorded only)."""
    from frankie_box_bedrock import code_identity
    return dict(schema=RUNTIME_SCHEMA, format=NATIVE_STATE_FORMAT, python=sys.version,
                cloudpickle=cloudpickle.__version__,
                serializer_code=code_identity(__file__, NATIVE_VALUE_CODE)['sha256'],
                ledger_storage_code=ledger_storage.native_code_identity()['sha256'],
                finalization_sha256=witness(Path(finalization.__file__).resolve())['sha256'],
                finalization_code=finalization.native_code_identity()['sha256'])


def python_minor(version):
    """'3.12' of a sys.version string ('3.12.3 (main, ...) [GCC ...]'), or None."""
    try:
        major, minor = str(version).split()[0].split('.')[:2]
        return '%d.%d' % (int(major), int(minor))
    except (ValueError, IndexError):
        return None


def runtime_acceptance(saved):
    """Why a saved descriptor's runtime is accepted, or None (refused). Compared: the saved format (absent = 1) against
    NATIVE_STATE_FORMAT, and the Python major.minor (the pickle compatibility key). The full Python version, the
    cloudpickle version and the code identities are recorded, never compared: the label names any recorded field that
    differs ('format_1; code recorded: serializer_code, python')."""
    if not isinstance(saved, dict):
        return None
    current = runtime_identity()
    if saved.get('format', 1) != NATIVE_STATE_FORMAT:
        return None
    if python_minor(saved.get('python')) != python_minor(current['python']):
        return None
    differs = sorted(k for k in RECORDED_CODE + ('python', 'cloudpickle')
                     if k in saved and saved.get(k) != current.get(k))
    label = 'format_%d' % NATIVE_STATE_FORMAT
    return label + ('; code recorded: ' + ', '.join(differs) if differs else '')


def continuation_meaning(binding):
    """A continuation binding in its compared form: the opening book exactly, the emission helper by its schema only
    (frankie_box_native_emission.meaning; its helper_sha256 is recorded, never compared)."""
    if isinstance(binding, dict) and isinstance(binding.get('emission'), dict):
        import frankie_box_native_emission
        return dict(binding, emission=frankie_box_native_emission.meaning(binding['emission']))
    return binding


def sink_items(sinks):
    return [(name, getattr(sinks, name)) for name in ('member', 'lifecycle', 'legacy')]


def ledger_state(sinks):
    result = {}
    for name, sink in sink_items(sinks):
        if not sink._closed:
            sink._handle.flush()
            os.fsync(sink._handle.fileno())
        attrs = ledger_storage.checkpoint_attributes(sink)
        result[name] = dict(path=str(sink.path), attributes=attrs, sha256=sink._digest.hexdigest(),
                           **ledger_storage.checkpoint_storage(sink))
    return result


def copy_ledger_prefixes(saved, sinks):
    # Frozen original extents remain untouched; verify and continue into new
    # append segments. I/O workers build the ordinary final files in parallel.
    ledger_storage.restore_prefixes(saved, sinks)


_RESTORING = threading.local()


def _runtime_binding(key):
    """A runtime binding (sinks, checkpointer, stage_spawn) inside a full state: resolved only by the StateUnpickler
    that is loading it, to that restore's own objects."""
    externals = getattr(_RESTORING, 'externals', None)
    if externals is None:
        raise ValueError('runtime binding outside a full-state restore')
    return externals[key]


class StatePickler(cloudpickle.CloudPickler):
    """The driver's full state with its three runtime bindings by reference. Since 2026-10-07 night (native levers) a
    binding is found by reducer_override, which the C pickler consults only for objects that are not atoms or builtin
    containers, instead of persistent_id, which it called for every object (on a2's checkpoints ~17-34 s per save,
    most of it a Python call per int of every calculator's Random state). The object graph is unchanged; a binding
    is written as _runtime_binding(key) and memoized like any reduced object, so every reference restores to the same
    restore-time object, exactly as the persistent id did. Saves of the persistent-id form still restore
    (StateUnpickler.persistent_load)."""

    def __init__(self, stream, externals):
        super().__init__(stream, protocol=5)
        self.externals = {id(value): key for key, value in externals.items() if value is not None}

    def reducer_override(self, value):
        key = self.externals.get(id(value))
        if key:
            return _runtime_binding, (key,)
        return super().reducer_override(value)


class StateUnpickler(pickle.Unpickler):
    def __init__(self, stream, externals):
        super().__init__(stream)
        self.externals = externals

    def persistent_load(self, identity):
        if not isinstance(identity, tuple) or len(identity) != 2 or identity[0] != 'frankie-runtime':
            raise ValueError('unknown runtime binding in checkpoint')
        return self.externals[identity[1]]

    def load(self):
        previous = getattr(_RESTORING, 'externals', None)
        _RESTORING.externals = self.externals
        try:
            return super().load()
        finally:
            _RESTORING.externals = previous


class FullCheckpointer(P.PeriodicCheckpointer):
    def __init__(self, *, driver_identity, progress=None, parent_checkpoint=None,
                 continuation_binding=None, save_requested=None, **kwargs):
        super().__init__(**kwargs)
        self.driver = None
        self.driver_identity = driver_identity
        self.progress = progress
        self.parent_checkpoint = parent_checkpoint
        self.continuation_binding = continuation_binding
        self.save_requested = save_requested
        self.stop_checkpoint = None
        self.low_space_stop = False
        self.last_state_bytes = 0

    def externals(self):
        return dict(sinks=self.driver.sinks, checkpointer=self, stage_spawn=self.driver.stage_spawn)

    def _write(self, adapter, *, completed_mbo_records, event_group_open, controller_state, locked,
               interval_save=True):
        if self.driver is None or self.driver.counters.records_seen != completed_mbo_records:
            raise ValueError('full driver and checkpoint cursor differ')
        adapter.assert_groups_closed()
        sequence = self.sequence + 1
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        state_path = self.checkpoint_dir / ('driver-state-%06d.pkl.gz' % sequence)
        pending = state_path.with_suffix('.pending')
        if state_path.exists() or pending.exists():
            raise FileExistsError('checkpoint evidence already exists')
        ledgers = ledger_state(self.driver.sinks)
        # The pinned driver increments this counter just AFTER maybe_save returns.
        # Serialize the continuation value without changing the running calculation.
        interval_save = interval_save and completed_mbo_records > 0 and not locked and self.sequence >= 0
        if interval_save:
            self.driver.counters.save_points += 1
        try:
            with pending.open('xb') as raw:
                with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=1, mtime=0) as stream:
                    StatePickler(stream, self.externals()).dump(self.driver)
                raw.flush()
                os.fsync(raw.fileno())
        finally:
            if interval_save:
                self.driver.counters.save_points -= 1
        os.rename(pending, state_path)
        sync_directory(self.checkpoint_dir)
        state_pin = witness(state_path)
        self.last_state_bytes = state_pin['bytes']
        descriptor = dict(schema=SCHEMA, runtime=runtime_identity(),
            driver_identity=self.driver_identity, driver_state=state_pin,
            ledgers=ledgers, completed_mbo_records=completed_mbo_records,
            finalized=locked, parent_checkpoint=self.parent_checkpoint)
        if self.continuation_binding is not None:
            descriptor['continuation_binding'] = self.continuation_binding
        checkpoint = super()._write(adapter, completed_mbo_records=completed_mbo_records,
            event_group_open=event_group_open, controller_state=descriptor, locked=locked)
        # Durable readback verifies the adapter chain, controller descriptor and full
        # serialized bytes. Restoration uses the same pinned runtime and object graph.
        if P.load_chain(self.checkpoint_dir)[-1] != checkpoint:
            raise ValueError('checkpoint chain readback differs')
        actual = json.loads(P.controller_state_path(self.checkpoint_dir, sequence).read_bytes())
        if P.canonical_hash(actual) != checkpoint['controller_state_hash'] or actual != descriptor:
            raise ValueError('full checkpoint descriptor readback differs')
        if witness(state_path) != state_pin:
            raise ValueError('full checkpoint state readback differs')
        state = P.read_gzip_json(P.adapter_state_path(self.checkpoint_dir, sequence))
        if P.adapter_state_hash(state) != checkpoint['adapter_state_hash']:
            raise ValueError('checkpoint adapter readback differs')
        if self.progress:
            self.progress.checkpoint('saved', P.checkpoint_path(self.checkpoint_dir, sequence))
            self.progress.checkpoint('read_verified', P.checkpoint_path(self.checkpoint_dir, sequence))
        return checkpoint

    def maybe_save(self, adapter, **kwargs):
        # One instrument's F_LAST can leave another instrument's group open.
        # Neither a periodic nor a requested save may serialize that boundary.
        if kwargs.get('event_group_open') or any(book.event_group for book in adapter.books.values()):
            return None
        reserve = max(32 << 30, 3 * self.last_state_bytes)
        if shutil.disk_usage(self.checkpoint_dir).free < reserve:
            self._last_saved_at = 0  # Save the next closed group before stopping.
            self.low_space_stop = True
        requested = (self.save_requested is not None and self.save_requested()
                     and getattr(self.driver, '_frankie_reconstruction_checkpoint', None) is None)
        if requested:
            arguments = dict(kwargs)
            arguments.setdefault('controller_state', None)
            arguments.setdefault('event_group_open', False)
            saved = self._write(adapter, **arguments, locked=False)
            self.stop_checkpoint = saved
            return saved
        return super().maybe_save(adapter, **kwargs)

    def save_boundary(self):
        """Coordinator-owned save; the driver will not increment its counter afterward."""
        return self._write(self.driver.adapter, completed_mbo_records=self.driver.counters.records_seen,
                           event_group_open=False, controller_state=None, locked=False,
                           interval_save=False)

    def raise_if_requested(self):
        if self.save_requested is not None and self.save_requested():
            from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
            raise TeacherSaved('native ROOT saved at %s' % self.checkpoint_dir)


def read_checkpoint(path, identity, *, continuation_binding=None):
    path = safe_path(path)
    latest = P.load_chain(path.parent)[-1]
    if path != P.checkpoint_path(path.parent, latest['sequence']) :
        raise ValueError('latest checkpoint required')
    if (latest['run_id'] != identity['run_id'] or
            latest['source_manifest_hash'] != identity['source_manifest_hash']):
        raise ValueError('checkpoint run or source identity differs')
    state = P.read_gzip_json(P.adapter_state_path(path.parent, latest['sequence']))
    if P.adapter_state_hash(state) != latest['adapter_state_hash']:
        raise ValueError('checkpoint adapter state is corrupt')
    descriptor = None
    if latest['controller_state_hash'] is not None:
        descriptor = json.loads(P.controller_state_path(path.parent, latest['sequence']).read_bytes())
        if P.canonical_hash(descriptor) != latest['controller_state_hash']:
            raise ValueError('checkpoint controller state is corrupt')
        if continuation_meaning(descriptor.get('continuation_binding')) != continuation_meaning(continuation_binding):
            raise ValueError('checkpoint opening state or provenance differs')
        acceptance = runtime_acceptance(descriptor['runtime'])
        if (descriptor.get('schema') != SCHEMA or descriptor['driver_identity'] != identity or
                acceptance is None or descriptor['finalized'] != latest['locked']):
            raise ValueError('full checkpoint runtime or producer identity differs')
        # recorded in the native receipt (frankie_box_bedrock.run: recovery.runtime_acceptance)
        latest['_runtime_acceptance'] = acceptance
        if witness(safe_path(descriptor['driver_state']['path'])) != descriptor['driver_state']:
            raise ValueError('full checkpoint bytes differ')
    if latest['locked'] and descriptor is None:
        raise ValueError('terminal adapter-only checkpoint lacks finalized calculations')
    if descriptor is None and continuation_binding is not None:
        raise ValueError('adapter-only checkpoint does not bind the required opening state')
    return latest, descriptor


def restore_driver(descriptor, checkpointer, sinks, stage_spawn):
    if descriptor['finalized']:
        finalization.restore_closed(descriptor['ledgers'], sinks, checkpointer.progress)
    else:
        copy_ledger_prefixes(descriptor['ledgers'], sinks)
    externals = dict(sinks=sinks, checkpointer=checkpointer, stage_spawn=stage_spawn)
    with gzip.open(safe_path(descriptor['driver_state']['path']), 'rb') as stream:
        driver = StateUnpickler(stream, externals).load()
    if (driver.counters.records_seen != descriptor['completed_mbo_records'] or
            driver.sinks is not sinks or driver.run.sinks is not sinks or driver.checkpointer is not checkpointer):
        raise ValueError('restored driver bindings or cursor differ')
    driver.adapter.assert_groups_closed()
    checkpointer.driver = driver
    return driver


def compare_reconstructed_prefix(driver, checkpoint, old_directory):
    # This is the required reconstruction readback, not a separate calculation run.
    if (driver.counters.records_seen != checkpoint['completed_mbo_records'] or
            P.adapter_state_hash(P.export_adapter_state(driver.adapter)) != checkpoint['adapter_state_hash']):
        raise ValueError('reconstructed adapter differs from retained checkpoint')
    for _, sink in sink_items(driver.sinks):
        sink._handle.flush()
        old_path = old_directory.parent / 'ledgers' / sink.path.name
        remaining = sink._bytes
        digest = hashlib.sha256()
        with safe_path(old_path).open('rb') as stream:
            while remaining:
                chunk = stream.read(min(8 << 20, remaining))
                if not chunk:
                    raise ValueError('retained ledger is shorter than reconstructed prefix')
                digest.update(chunk)
                remaining -= len(chunk)
        if digest.hexdigest() != sink._digest.hexdigest():
            raise ValueError('reconstructed exact ledger prefix differs')


def consume_recovery(driver, records, total, progress, checkpoint=None, descriptor=None):
    iterator = iter(records)
    start = driver.counters.records_seen
    # Full-state continuation skips source records without recalculating them.
    if descriptor is not None:
        for _ in range(start):
            next(iterator)
    if checkpoint and descriptor is None:
        driver._frankie_reconstruction_checkpoint = checkpoint
    reconstruction = getattr(driver, '_frankie_reconstruction_checkpoint', None)
    target = reconstruction['completed_mbo_records'] if reconstruction else None
    def confirm_reconstruction():
        compare_reconstructed_prefix(driver, reconstruction, Path(reconstruction['_directory']))
        save_new(driver.checkpointer.checkpoint_dir.parent / 'reconstruction-receipt.json',
            dict(parent_checkpoint_hash=reconstruction['checkpoint_hash'], records=target,
                 adapter_and_exact_ledger_prefixes_verified=True, source_writes=0))
        driver._frankie_reconstruction_checkpoint = None
    if target is not None and start >= target:
        if start != target:
            raise ValueError('unverified reconstruction cursor passed its checkpoint')
        confirm_reconstruction()
        target = None
    def tracked():
        done = start
        if progress:
            progress.update('root-native-reconstruct' if target else 'root-native-records', done, total)
        for record in iterator:
            if driver.checkpointer.low_space_stop:
                raise OSError('low disk reserve; full checkpoint saved before controlled stop')
            yield record
            done += 1
            if target is not None and done == target:
                confirm_reconstruction()
            if driver.checkpointer.stop_checkpoint is not None:
                # _on_group has returned, including its saved-point increment;
                # the durable state and this cursor now describe the same boundary.
                from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
                raise TeacherSaved('native ROOT saved at %s' % driver.checkpointer.checkpoint_dir)
            stage = 'root-native-reconstruct' if target is not None and done < target else 'root-native-records'
            if progress:
                progress.update(stage, done, total, force=False)
        if done != total:
            raise ValueError('native continuation source count differs')
    driver.consume(tracked())
