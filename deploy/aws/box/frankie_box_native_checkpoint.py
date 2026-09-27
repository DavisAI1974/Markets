"""Durable full native-driver save/restore; pinned producer math is unchanged."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import sys
import time

import cloudpickle
from research.kalshi.frankie_raw_mbo_benchmark import periodic_checkpointer as P
from frankie_box_prepare_trading_day import safe_path, save_new, sync_directory, witness

SCHEMA = 'FRANKIE_NATIVE_FULL_STATE_V1'


def runtime_identity():
    return dict(python=sys.version, cloudpickle=cloudpickle.__version__,
                serializer_sha256=witness(Path(__file__).resolve())['sha256'])


def sink_items(sinks):
    return [(name, getattr(sinks, name)) for name in ('member', 'lifecycle', 'legacy')]


def ledger_state(sinks):
    result = {}
    for name, sink in sink_items(sinks):
        if not sink._closed:
            sink._handle.flush()
            os.fsync(sink._handle.fileno())
        attrs = {k: v for k, v in vars(sink).items() if k not in ('_handle', '_digest', 'path')}
        result[name] = dict(path=str(sink.path), attributes=attrs, sha256=sink._digest.hexdigest())
    return result


def copy_ledger_prefixes(saved, sinks):
    # New generation files only. The old files, including any post-checkpoint tail,
    # remain intact. Rebuild hashes from the exact bytes before opening continuation.
    for name, sink in sink_items(sinks):
        entry = saved[name]
        source = safe_path(entry['path'])
        remaining = entry['attributes']['_bytes']
        digest = hashlib.sha256()
        with source.open('rb') as stream:
            while remaining:
                chunk = stream.read(min(8 << 20, remaining))
                if not chunk:
                    raise ValueError('saved ledger is shorter than checkpoint')
                sink._handle.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
        if digest.hexdigest() != entry['sha256']:
            raise ValueError('saved ledger prefix hash differs')
        sink._handle.flush()
        os.fsync(sink._handle.fileno())
        sink.__dict__.update(entry['attributes'])
        sink._closed = False
        sink._digest = digest


class StatePickler(cloudpickle.CloudPickler):
    def __init__(self, stream, externals):
        super().__init__(stream, protocol=5)
        self.externals = {id(value): key for key, value in externals.items() if value is not None}

    def persistent_id(self, value):
        key = self.externals.get(id(value))
        return ('frankie-runtime', key) if key else None


class StateUnpickler(pickle.Unpickler):
    def __init__(self, stream, externals):
        super().__init__(stream)
        self.externals = externals

    def persistent_load(self, identity):
        if not isinstance(identity, tuple) or len(identity) != 2 or identity[0] != 'frankie-runtime':
            raise ValueError('unknown runtime binding in checkpoint')
        return self.externals[identity[1]]


class FullCheckpointer(P.PeriodicCheckpointer):
    def __init__(self, *, driver_identity, progress=None, parent_checkpoint=None, **kwargs):
        super().__init__(**kwargs)
        self.driver = None
        self.driver_identity = driver_identity
        self.progress = progress
        self.parent_checkpoint = parent_checkpoint
        self.low_space_stop = False
        self.last_state_bytes = 0

    def externals(self):
        return dict(sinks=self.driver.sinks, checkpointer=self, stage_spawn=self.driver.stage_spawn)

    def _write(self, adapter, *, completed_mbo_records, event_group_open, controller_state, locked):
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
        interval_save = completed_mbo_records > 0 and not locked and self.sequence >= 0
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
        reserve = max(32 << 30, 3 * self.last_state_bytes)
        if shutil.disk_usage(self.checkpoint_dir).free < reserve:
            self._last_saved_at = 0  # Save the next closed group before stopping.
            self.low_space_stop = True
        return super().maybe_save(adapter, **kwargs)


def read_checkpoint(path, identity):
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
        if (descriptor.get('schema') != SCHEMA or descriptor['driver_identity'] != identity or
                descriptor['runtime'] != runtime_identity() or descriptor['finalized'] != latest['locked']):
            raise ValueError('full checkpoint runtime or producer identity differs')
        if witness(safe_path(descriptor['driver_state']['path'])) != descriptor['driver_state']:
            raise ValueError('full checkpoint bytes differ')
    if latest['locked'] and descriptor is None:
        raise ValueError('terminal adapter-only checkpoint lacks finalized calculations')
    return latest, descriptor


def restore_driver(descriptor, checkpointer, sinks, stage_spawn):
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
            stage = 'root-native-reconstruct' if target is not None and done < target else 'root-native-records'
            if progress:
                progress.update(stage, done, total, force=False)
        if done != total:
            raise ValueError('native continuation source count differs')
    driver.consume(tracked())
