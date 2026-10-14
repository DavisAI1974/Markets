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
PARTIAL_CHECKPOINT_SCHEMA = 'FRANKIE_NATIVE_PARTIAL_CHECKPOINT_V1'
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
# Format 2 adds the explicit carried adapter witness to the full descriptor.
# The full driver pickle is unchanged; format-1 closed-group saves remain readable.
NATIVE_STATE_FORMAT = 2
RECORDED_CODE = ('serializer_code', 'ledger_storage_code', 'finalization_code', 'finalization_sha256',
                 'serializer_sha256', 'ledger_storage_sha256')
# The definitions in THIS file whose change may change the saved FORMAT (bump NATIVE_STATE_FORMAT when it does); their
# identity is recorded as serializer_code.
NATIVE_VALUE_CODE = ('SCHEMA', 'sink_items', 'ledger_state', 'copy_ledger_prefixes', '_runtime_binding', 'StatePickler',
                     'StateUnpickler',
                     'PARTIAL_CHECKPOINT_SCHEMA', '_partial_checkpoint', 'load_chain',
                     'FullCheckpointer.externals', 'FullCheckpointer._partial_adapter_save',
                     'FullCheckpointer._write', 'FullCheckpointer.save_boundary',
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
    the supported formats 1 and 2, and the Python major.minor (the pickle compatibility key). The full Python version, the
    cloudpickle version and the code identities are recorded, never compared: the label names any recorded field that
    differs ('format_1; code recorded: serializer_code, python')."""
    if not isinstance(saved, dict):
        return None
    current = runtime_identity()
    saved_format = saved.get('format', 1)
    if type(saved_format) is not int or saved_format not in (1, NATIVE_STATE_FORMAT):
        return None
    if python_minor(saved.get('python')) != python_minor(current['python']):
        return None
    differs = sorted(k for k in RECORDED_CODE + ('python', 'cloudpickle')
                     if k in saved and saved.get(k) != current.get(k))
    label = 'format_%d' % saved_format
    return label + ('; code recorded: ' + ', '.join(differs) if differs else '')


def continuation_meaning(binding):
    """A continuation binding in its compared form: the opening book exactly, the emission helper by its schema only
    (frankie_box_native_emission.meaning; its helper_sha256 is recorded, never compared).
    V3's record_provenance, including every DBN member and its order/count, remains an exact data-policy comparison.
    """
    if isinstance(binding, dict) and isinstance(binding.get('emission'), dict):
        import frankie_box_native_emission
        return dict(binding, emission=frankie_box_native_emission.meaning(binding['emission']))
    return binding


def _partial_checkpoint(**fields):
    """The existing checkpoint fields with an explicit carried-group format.

    The pinned benchmark schema remains closed-group-only. Its builder validates
    the common identity/count fields; this wrapper then binds the actual open
    flag under the partial format. No scientific group is closed to make a save.
    """
    opened = fields.pop('event_group_open')
    if type(opened) is not bool or (opened and fields['locked']):
        raise ValueError('a terminal native save cannot carry unfinished groups')
    value = P.build_checkpoint(event_group_open=False, **fields)
    value.update(schema=PARTIAL_CHECKPOINT_SCHEMA, event_group_open=opened)
    value['checkpoint_hash'] = P.canonical_hash({k: v for k, v in value.items() if k != 'checkpoint_hash'})
    return value


def load_chain(directory):
    """Keep the original reader for old saves; also read exact partial saves."""
    paths = sorted(Path(directory).glob(P.CHECKPOINT_GLOB))
    if not paths or json.loads(paths[0].read_bytes()).get('schema') != PARTIAL_CHECKPOINT_SCHEMA:
        return P.load_chain(directory)
    chain = []
    stable = ('run_id', 'controller', 'memory_mode', 'source_manifest_hash', 'total_mbo_records')
    for index, path in enumerate(paths):
        value = json.loads(path.read_bytes())
        fields = {k: v for k, v in value.items() if k not in ('schema', 'checkpoint_hash', 'progress_percent')}
        if value != _partial_checkpoint(**fields) or path != P.checkpoint_path(directory, index):
            raise ValueError('native partial checkpoint identity differs')
        previous = chain[-1] if chain else None
        if (value['sequence'] != index
                or value['previous_checkpoint_hash'] != (previous['checkpoint_hash'] if previous else None)
                or (previous and (previous['locked']
                    or value['completed_mbo_records'] < previous['completed_mbo_records']
                    or any(value[k] != previous[k] for k in stable)))):
            raise ValueError('native partial checkpoint chain differs')
        chain.append(value)
    return chain


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
                 continuation_binding=None, save_requested=None, input_position=None, carry_open_groups=False, **kwargs):
        super().__init__(**kwargs)
        self.driver = None
        self.driver_identity = driver_identity
        self.progress = progress
        self.parent_checkpoint = parent_checkpoint
        self.continuation_binding = continuation_binding
        self.save_requested = save_requested
        self.input_position = input_position
        self.carry_open_groups = carry_open_groups
        self.stop_checkpoint = None
        self.low_space_stop = False
        self.last_state_bytes = 0
        self.total_records = kwargs.get('total_mbo_records')
        self.last_disk = None

    def disk_projection(self):
        """The free space against what the rest of this traversal will write (Greg, 2026-10-09: a gate never stops a
        run on fine data; stop only when the work demonstrably cannot fit): the next full-state save (the last save's
        size) plus the exact ledgers' remaining bytes, projected from the bytes written so far per record. Recorded at
        every save (the descriptor's `disk`, recorded only) and read by maybe_save; never raises."""
        try:
            free = shutil.disk_usage(self.checkpoint_dir if self.checkpoint_dir.exists()
                                     else self.checkpoint_dir.parent).free
        except OSError:
            return None
        written = done = None
        try:
            sinks = self.driver.sinks
            written = sum(int(getattr(getattr(sinks, name), '_bytes', 0) or 0) for name in ('member', 'lifecycle', 'legacy'))
            done = int(self.driver.counters.records_seen)
        except (AttributeError, TypeError, ValueError):
            pass
        remaining = None
        if written is not None and done and isinstance(self.total_records, int) and self.total_records >= done:
            remaining = written * (self.total_records - done) // done
        projected = self.last_state_bytes + (remaining or 0)
        self.last_disk = dict(free_bytes=free, next_save_bytes=self.last_state_bytes, ledger_bytes_written=written,
                              records_done=done, records_total=self.total_records,
                              ledger_bytes_remaining_projected=remaining, projected_bytes=projected,
                              fits=projected <= free, at_ns=time.time_ns(),
                              rule='stop only when projected (next save + remaining ledger bytes) exceeds free')
        return self.last_disk

    def externals(self):
        return dict(sinks=self.driver.sinks, checkpointer=self, stage_spawn=self.driver.stage_spawn)

    def _partial_adapter_save(self, state, descriptor, *, completed_mbo_records, locked):
        """Persist the existing open-group adapter state beside the full driver."""
        sequence = self.sequence + 1
        paths = (P.adapter_state_path(self.checkpoint_dir, sequence),
                 P.controller_state_path(self.checkpoint_dir, sequence),
                 P.checkpoint_path(self.checkpoint_dir, sequence))
        P.write_gzip_json_atomic(paths[0], state)
        save_new(paths[1], descriptor)
        checkpoint = _partial_checkpoint(run_id=self.run_id, controller=self.controller,
            memory_mode=self.memory_mode, sequence=sequence, source_manifest_hash=self.source_manifest_hash,
            completed_mbo_records=completed_mbo_records, total_mbo_records=self.total_mbo_records,
            event_group_open=descriptor['adapter_state']['event_group_open'],
            adapter_state_hash=state['state_hash'], controller_state_hash=P.canonical_hash(descriptor),
            previous_checkpoint_hash=self._previous_hash, phase=self.phase, locked=locked)
        pending = paths[2].with_suffix('.pending')
        save_new(pending, checkpoint)
        os.link(pending, paths[2])
        sync_directory(self.checkpoint_dir)
        pending.unlink()
        self._sequence, self._previous_hash = sequence, checkpoint['checkpoint_hash']
        self._last_saved_records, self._last_saved_at = completed_mbo_records, self._monotonic()
        self._saved.append(checkpoint)
        if self._durable_sync is not None:
            self._durable_sync(paths)
        self.report_progress(completed_mbo_records)
        return checkpoint

    def _write(self, adapter, *, completed_mbo_records, event_group_open, controller_state, locked,
               interval_save=True):
        if self.driver is None or self.driver.counters.records_seen != completed_mbo_records:
            raise ValueError('full driver and checkpoint cursor differ')
        partial = None
        if self.carry_open_groups:
            from research.kalshi.frankie_boss.mbo_resume_state import export_adapter_state
            partial = export_adapter_state(adapter, include_open_groups=True)
        if not self.carry_open_groups or locked:
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
        if partial is not None:
            descriptor['adapter_state'] = dict(schema=partial['schema'], sha256=partial['state_hash'],
                event_group_open=any(book.event_group for book in adapter.books.values()))
        disk = self.disk_projection()
        if disk is not None:
            descriptor['disk'] = disk                  # recorded at every save, never compared
        if self.continuation_binding is not None:
            descriptor['continuation_binding'] = self.continuation_binding
        if self.input_position is not None:
            position = self.input_position(completed_mbo_records)
            if not isinstance(position, dict):
                raise ValueError('native input checkpoint position must be a durable mapping')
            descriptor['input_position'] = position
        if partial is None:
            checkpoint = super()._write(adapter, completed_mbo_records=completed_mbo_records,
                event_group_open=event_group_open, controller_state=descriptor, locked=locked)
        else:
            checkpoint = self._partial_adapter_save(partial, descriptor,
                completed_mbo_records=completed_mbo_records, locked=locked)
        # Durable readback verifies the adapter chain, controller descriptor and full
        # serialized bytes. Restoration uses the same pinned runtime and object graph.
        if load_chain(self.checkpoint_dir)[-1] != checkpoint:
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
        # Old saved runs keep their closed-group checkpoint contract. New
        # member-bound runs retain every instrument's open state in the full save.
        if not self.carry_open_groups and (kwargs.get('event_group_open')
                                          or any(book.event_group for book in adapter.books.values())):
            return None
        # Greg, 2026-10-09: no reserve gate. The traversal keeps running while the rest of its work fits; only when the
        # projected bytes (the next save plus the ledgers' remaining bytes) exceed the free space is the next
        # checkpoint saved and the traversal stopped (an actual ENOSPC also stops it, as any crash does)
        disk = self.disk_projection()
        if disk is not None and not disk['fits'] and not self.low_space_stop:
            self._last_saved_at = 0  # Save at this checkpoint call before stopping.
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
    latest = load_chain(path.parent)[-1]
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
        if latest.get('schema') == PARTIAL_CHECKPOINT_SCHEMA:
            from research.kalshi.frankie_boss.mbo_resume_state import OPEN_SCHEMA
            expected = dict(schema=OPEN_SCHEMA, sha256=latest['adapter_state_hash'],
                            event_group_open=latest['event_group_open'])
            if (descriptor.get('adapter_state') != expected or state.get('schema') != OPEN_SCHEMA
                    or descriptor['runtime'].get('format') != 2
                    or bool(any(book['event_group'] for book in state['books'])) != latest['event_group_open']):
                raise ValueError('native partial adapter state differs from its full save')
        elif 'adapter_state' in descriptor:
            raise ValueError('partial adapter state requires its explicit checkpoint format')
        if witness(safe_path(descriptor['driver_state']['path'])) != descriptor['driver_state']:
            raise ValueError('full checkpoint bytes differ')
    if latest.get('schema') == PARTIAL_CHECKPOINT_SCHEMA and descriptor is None:
        raise ValueError('partial native checkpoint requires the full calculation state')
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
    if 'adapter_state' in descriptor:
        from research.kalshi.frankie_boss.mbo_resume_state import export_adapter_state
        if not checkpointer.carry_open_groups:
            raise ValueError('partial native state requires its member-bound continuation route')
        state = export_adapter_state(driver.adapter, include_open_groups=True)
        if (state['schema'] != descriptor['adapter_state']['schema']
                or state['state_hash'] != descriptor['adapter_state']['sha256']):
            raise ValueError('restored partial native adapter differs from its saved state')
    else:
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
    start = driver.counters.records_seen
    seek = getattr(records, 'iter_from', None)
    if descriptor is not None and callable(seek):
        # The source verifies this retained ordinal/offset before yielding. The
        # checkpoint hash covers the optional position; old descriptors supply
        # None and the source may resolve the ordinal through its durable index.
        iterator = iter(seek(start, position=descriptor.get('input_position')))
    else:
        iterator = iter(records)
        # Legacy counted sources keep the original continuation behavior.
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
                raise OSError('the rest of the native traversal does not fit the free space (%s); full checkpoint '
                              'saved before controlled stop' % driver.checkpointer.last_disk)
            yield record
            done += 1
            if target is not None and done == target:
                confirm_reconstruction()
            if driver.checkpointer.stop_checkpoint is not None:
                # _on_group has returned, including its saved-point increment;
                # the durable state and this cursor now describe the same boundary.
                from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
                raise TeacherSaved('native ROOT saved at %s' % driver.checkpointer.checkpoint_dir)
            if (driver.checkpointer.carry_open_groups and driver.checkpointer.save_requested is not None
                    and driver.checkpointer.save_requested() and target is None):
                # The driver has returned from this INPUT's application. Preserve
                # the partial calculation and all open groups at this position;
                # do not read ahead looking for another instrument's F_LAST.
                driver.checkpointer.save_boundary()
                driver.checkpointer.raise_if_requested()
            stage = 'root-native-reconstruct' if target is not None and done < target else 'root-native-records'
            if progress:
                progress.update(stage, done, total, force=False)
        if done != total:
            raise ValueError('native continuation source count differs')
    driver.consume(tracked())
