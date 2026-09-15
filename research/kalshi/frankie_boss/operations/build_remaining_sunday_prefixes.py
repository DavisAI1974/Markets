"""Prepare remaining actual Sunday prefix witnesses after pinned final receipts.

No model calls, source replay, source mutation, or paid/cloud operation. Run once
with the fully pinned actual-host configuration; safe reruns reuse published
witnesses and recover receipt-before-witness publication, never overwrite files.
"""
import argparse
from contextlib import contextmanager
import hashlib
import heapq
import json
import os
from pathlib import Path
import sys
import time

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from research.kalshi.frankie_boss import journal_prefix_snapshot as snapshot
from research.kalshi.frankie_boss.c15_journal import unpack, pack, canonical_bytes, evidence_hash
from research.kalshi.frankie_boss.feedback_cycle import _exclusive
from research.kalshi.frankie_boss import context_session, sunday_native_runtime
from research.kalshi.frankie_boss.selected_source_scope import source_scope
from research.kalshi.frankie_boss.causal_prefix import PREFIX_SCHEME, _domain_hash
from research.kalshi.frankie_boss.causal_prefix_records import RecordInput, _DOMAIN_RECORD


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pinned(witness):
    path = Path(witness['path'])
    if path.is_symlink() or not path.is_file() or sha(path) != witness['sha256']:
        raise ValueError('independently pinned file missing or changed: ' + str(path))
    if 'bytes' in witness and path.stat().st_size != witness['bytes']:
        raise ValueError('pinned file size changed')
    return path


def read_pinned(witness):
    return json.loads(pinned(witness).read_bytes())


def witness(path):
    path = Path(path)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=sha(path))


def save_new(path, value):
    path = Path(path)
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    # The existing directory is not replaceable; xb refuses a duplicate writer.
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def progress(directory, phase, **values):
    row = dict(pid=os.getpid(), phase=phase, time_unix=time.time(), **values)
    raw = json.dumps(row, sort_keys=True, separators=(',', ':')).encode()
    with (directory / 'remaining-prefix-progress.jsonl').open('ab') as stream:
        stream.write(raw + b'\n'); stream.flush(); os.fsync(stream.fileno())
    print(raw.decode(), flush=True)


@contextmanager
def snapshot_progress(directory, cycle_index, through_cursor, seed_collector=None):
    """Observe the existing copy/verify iterators without another read or scan.

    Overrides are local to this exclusive scratch process and always restored;
    no repository source, copier or reader file is changed. A callback I/O
    failure cannot abort copying or turn telemetry into a run-time budget.
    """
    original_pages, original_verify = snapshot._pages, snapshot._verify_pairs
    total = through_cursor + 1
    def emit(phase, completed):
        try:
            progress(directory, phase, cycle_index=cycle_index,
                     completed_records=completed, total_records=total)
        except OSError as error:
            try:
                print(json.dumps(dict(phase='prefix_progress_write_failed', cycle_index=cycle_index,
                                      error_type=type(error).__name__)), flush=True)
            except OSError:
                pass
    def pages(connection, last_ordinal, page_rows):
        reported = 0
        emit('prefix_copy', 0)
        for page in original_pages(connection, last_ordinal, page_rows):
            yield page
            # The copier has committed this page before requesting the next one.
            completed = (page[-1][0] + 1) // 2
            if completed - reported >= 1000 or completed == total:
                emit('prefix_copy', completed)
                reported = completed
    def verify(entries, cursor):
        emit('prefix_verify', 0)
        def observed():
            reported = 0
            for entry in entries:
                yield entry
                if entry['kind'] == 'APPLIED':
                    if seed_collector is not None:
                        seed_collector.observe(entry)
                    completed = (entry['ordinal'] + 1) // 2
                    if completed - reported >= 1000 or completed == total:
                        emit('prefix_verify', completed)
                        reported = completed
        # Original verification still owns the final tail and pair checks.
        result = original_verify(observed(), cursor)
        if seed_collector is not None:
            seed_collector.finish(result)
        return result
    snapshot._pages, snapshot._verify_pairs = pages, verify
    try:
        yield
    finally:
        snapshot._pages, snapshot._verify_pairs = original_pages, original_verify


class ContextSeedCollector:
    """Same bounded receive-time selection as ContextSessionRunner._prepare.

    Only normalized hashing is recomputed over entries already being verified;
    no reader, adapter, teacher or model is run. Each candidate carries its exact
    predecessor from the full source chain, including other-entity records.
    """
    def __init__(self, scope, *, entity, t_ctx, step):
        if (type(entity) is not tuple or len(entity)!=2 or any(type(x) is not int for x in entity)
                or type(t_ctx) is not int or t_ctx<1):
            raise ValueError('explicit context selection required')
        self.scope, self.entity, self.t_ctx, self.step = scope, entity, t_ctx, dict(step)
        self.previous = scope.genesis_hash()
        self.next_cursor = 0
        self.heap = []
        self.receipt = None

    def observe(self, entry):
        row = entry['payload']
        cursor = row['cursor']; normalized = row['normalized']
        if type(cursor) is not int or cursor!=self.next_cursor or cursor>self.step['through_cursor']:
            raise ValueError('seed selection source cursor gap')
        record = RecordInput(cursor, row['source_member_index'], normalized, self.scope.adapter_revision)
        member = self.scope.members[record.source_member_index]
        lower, upper = self.scope.member_cursor_bounds(record.source_member_index)
        if not lower<=cursor<upper or record.action['source_dbn_sha256']!=member.sha256:
            raise ValueError('seed source member differs from bound scope')
        after = _domain_hash(_DOMAIN_RECORD, dict(scheme=PREFIX_SCHEME, record_kind='NORMALIZED_MBO_RECORD',
            previous_prefix_hash=self.previous, scope_kind=self.scope.kind.value, scope_id=self.scope.scope_id,
            source_member_index=record.source_member_index, source_member_sha256=member.sha256,
            cursor=cursor, instrument_id=record.instrument_id, publisher_id=record.publisher_id,
            action=record.stable_action(), adapter_revision=self.scope.adapter_revision))
        if after!=row['terminal_prefix_hash']:
            raise ValueError('verified journal source prefix does not reconstruct under pinned scope')
        recv=normalized['ts_recv_ns']
        if recv>self.step['as_of']:
            raise ValueError('seed selection includes future receive time')
        if (normalized['publisher_id'],normalized['instrument_id'])==self.entity:
            item=(recv,cursor,self.previous)
            if len(self.heap)<self.t_ctx: heapq.heappush(self.heap,item)
            else: heapq.heappushpop(self.heap,item)
        self.previous=after; self.next_cursor+=1

    def finish(self, summary):
        if (self.next_cursor!=self.step['through_cursor']+1 or self.previous!=self.step['source_hash']
                or summary['source_prefix_hash']!=self.previous or summary['as_of']!=self.step['as_of']
                or summary['source_as_of']!=self.step['source_as_of']):
            raise ValueError('seed selection terminal commitment or clocks differ')
        selected=sorted(self.heap)
        cursors=[item[1] for item in selected]
        ascending=sorted(cursors)
        if not cursors: reason='no_entity_context'
        elif ascending!=list(range(ascending[0],ascending[0]+len(ascending))): reason='noncontiguous_source_cursors'
        elif ascending[-1]!=self.step['through_cursor']: reason='context_omits_terminal_cursor'
        else: reason=None
        seed=None
        if reason is None:
            first=min(selected,key=lambda item:item[1])
            seed=dict(next_cursor=first[1],previous_prefix_hash=first[2],scope_genesis_hash=self.scope.genesis_hash())
        self.receipt=dict(schema='FRANKIE_VERIFIED_CONTEXT_PREFIX_SEED_V1',
            entity=list(self.entity),t_ctx=self.t_ctx,through_cursor=self.step['through_cursor'],
            as_of=self.step['as_of'],source_as_of=self.step['source_as_of'],
            source_scope_hash=self.scope.genesis_hash(),source_prefix_hash=self.previous,
            context_cursors=cursors,context_cursors_sha256=evidence_hash(tuple(cursors)),
            seed=seed,derivable=reason is None,reason=reason,
            selection='TOP_T_CTX_BY_RECEIVE_TIME_AND_CURSOR',verified_records=self.next_cursor)
        return self.receipt


def matches_step(receipt, step):
    checks = {'records_in_prefix': step['through_cursor'] + 1,
              'journal_count': 2 * (step['through_cursor'] + 1),
              'source_prefix_hash': step['source_hash'],
              'as_of': step['as_of'], 'source_as_of': step['source_as_of']}
    if any(receipt.get(key) != value for key, value in checks.items()):
        raise ValueError('prefix differs from authored completed schedule')


def validate_inputs(configuration):
    """Read receipt/checkpoint files only; must finish before ANY source DB open."""
    host = configuration['host_runtime']
    source = Path(configuration['source_directory']).resolve()
    schedule_dir = Path(configuration['schedule_directory']).resolve()
    for directory in (source, schedule_dir, Path(host['source_lineage']['path']).parent):
        if (directory / 'failure.json').exists():
            raise ValueError('failure evidence forbids prefix materialization')
    for key, expected in (('ingestion_receipt', source / 'ingestion-receipt.json'),
                          ('schedule_receipt', schedule_dir / 'receipt.json'),
                          ('schedule', schedule_dir / 'schedule.json')):
        if Path(host[key]['path']).resolve() != expected:
            raise ValueError('receipt must belong to declared final source/schedule')
    ingestion = read_pinned(host['ingestion_receipt'])
    outer = read_pinned(host['schedule_receipt'])
    schedule = read_pinned(host['schedule'])
    lineage = read_pinned(host['source_lineage'])
    completion = json.loads((source / 'completion.json').read_bytes())
    if (ingestion['record_count'] != 57027 or completion['record_count'] != 57027
            or outer['source_records'] != 57027 or outer['steps'] != 19
            or outer['source_completion'] != completion or len(schedule['steps']) != 19
            or outer['schedule_file_sha256'] != host['schedule']['sha256']):
        raise ValueError('full Sunday source and full nineteen-cutoff schedule required')
    from research.kalshi.frankie_boss.verified_sunday_schedule import verified_schedule
    schedule = verified_schedule(schedule, expected_digest=outer['schedule_sha256'])
    checkpoint_path = source / 'builder-checkpoint.c15.json'
    if sha(checkpoint_path) != ingestion['checkpoint_sha256'] or outer['source_checkpoint_sha256'] != ingestion['checkpoint_sha256']:
        raise ValueError('complete source checkpoint bytes differ')
    state = unpack(json.loads(checkpoint_path.read_bytes()))
    if (state['state_hash'] != ingestion['checkpoint_state_hash']
            or completion['builder_state_hash'] != state['state_hash']
            or outer['source_checkpoint_state_hash'] != state['state_hash']
            or state['journal_count'] != completion['journal_count']
            or state['journal_hash'] != completion['journal_hash']
            or state['scope_genesis_hash'] != completion['scope_hash']):
        raise ValueError('completed source checkpoint/completion differs')
    journal = source / 'source.sqlite'
    if (lineage.get('schema') != 'FRANKIE_CLOSED_SOURCE_LINEAGE_V1'
            or Path(lineage['final_source_path']).resolve() != journal
            or not lineage['links']
            or lineage['links'][0]['recovery_receipt']['sha256'] != ingestion['recovery_receipt_sha256']):
        raise ValueError('independently verified closed lineage required')
    # Receipt is emitted only after driver.close(), but explicitly reject active
    # progress too. A concurrent schedule reader may leave empty WAL sidecars.
    source_progress = json.loads((source / 'progress' / 'progress.json').read_bytes())
    phase = source_progress.get('phase')
    if phase != 'complete':
        raise ValueError('source worker has not published complete progress')
    if snapshot._sidecars(journal):
        raise ValueError('final source has unclosed journal content')
    cursors = [step['through_cursor'] for step in schedule['steps']]
    if cursors != sorted(set(cursors)) or cursors[0] != 3261 or cursors[-1] >= 57027:
        raise ValueError('original ordered Sunday cutoffs required')
    return source, ingestion, completion, schedule, lineage


def materialize(source, output, steps, *, parent_count, parent_head_hash, binding_sha256,
                first_cycle=1, copier=snapshot.snapshot_journal_prefix, scope=None, entity=None, t_ctx=None):
    """One original-byte copy per necessary prefix; no full source rehydration."""
    output = Path(output)
    before = source.stat()
    results = []
    for index, step in enumerate(steps[first_cycle:], start=first_cycle):
        path = output / f'prefix-{index:02d}.sqlite'
        receipt_path = output / f'prefix-{index:02d}-receipt.json'
        witness_path = output / f'prefix-{index:02d}-witness.json'
        seed_path = output / f'prefix-{index:02d}-packet-seed.json'
        collector = None if scope is None else ContextSeedCollector(scope,entity=entity,t_ctx=t_ctx,step=step)
        progress(output, 'prefix_begin', cycle_index=index, through_cursor=step['through_cursor'])
        if witness_path.exists():
            value = json.loads(witness_path.read_bytes())
            receipt = read_pinned(value['receipt']); pinned(value['snapshot'])
            if Path(value['receipt']['path']).resolve() != receipt_path.resolve():
                raise ValueError('published prefix receipt path differs')
        elif receipt_path.exists():
            receipt = json.loads(receipt_path.read_bytes())
            if not path.exists() or sha(path) != receipt['snapshot_sha256']:
                raise ValueError('unpublished retained snapshot differs from receipt')
        else:
            if path.exists() or list(output.glob(path.name + '.partial-*')):
                raise ValueError('unreceipted snapshot or partial preserved; inspect before retry')
            with snapshot_progress(output, index, step['through_cursor'], collector):
                receipt = copier(source, path, parent_count=parent_count,
                                 parent_head_hash=parent_head_hash, through_cursor=step['through_cursor'],
                                 parent_sha256=None, page_rows=64)
            matches_step(receipt, step)
            save_new(receipt_path, receipt)
            if collector is not None:
                if collector.receipt is None: raise ValueError('copier did not perform seed verification pass')
                save_new(seed_path,dict(collector.receipt,cycle_index=index,
                    snapshot_receipt_sha256=sha(receipt_path),snapshot_sha256=receipt['snapshot_sha256'],
                    batch_binding_sha256=binding_sha256,selection_code_sha256=sha(context_session.__file__),
                    runtime_code_sha256=sha(sunday_native_runtime.__file__)))
        matches_step(receipt, step)
        if (receipt['schema'] != snapshot.SCHEMA or Path(receipt['original_journal']).resolve() != source.resolve()
                or Path(receipt['snapshot_journal']).resolve() != path.resolve()
                or receipt['parent'] != dict(count=parent_count, head_hash=parent_head_hash, sha256=None)):
            raise ValueError('prefix provenance differs from completed source')
        if collector is not None:
            # A lost seed write is not permission to rescan/reconstruct from an
            # unverified tail or infer a missing predecessor. Preserve for review.
            if not seed_path.exists(): raise ValueError('verified prefix seed sidecar missing; preserve snapshot for review')
            seed_receipt=json.loads(seed_path.read_bytes())
            if (seed_receipt['snapshot_receipt_sha256']!=sha(receipt_path)
                    or seed_receipt['snapshot_sha256']!=receipt['snapshot_sha256']
                    or seed_receipt['batch_binding_sha256']!=binding_sha256
                    or seed_receipt['source_scope_hash']!=scope.genesis_hash()
                    or seed_receipt['source_prefix_hash']!=step['source_hash']
                    or seed_receipt['as_of']!=step['as_of'] or seed_receipt['through_cursor']!=step['through_cursor']
                    or seed_receipt['t_ctx']!=t_ctx or seed_receipt['entity']!=list(entity)
                    or seed_receipt['selection_code_sha256']!=sha(context_session.__file__)
                    or seed_receipt['runtime_code_sha256']!=sha(sunday_native_runtime.__file__)):
                raise ValueError('retained seed sidecar differs from pinned snapshot selection')
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or snapshot._sidecars(source):
            raise ValueError('completed source changed during prefix preparation')
        if not witness_path.exists():
            save_new(witness_path, dict(snapshot=dict(path=str(path.resolve()), bytes=path.stat().st_size,
                                                    sha256=receipt['snapshot_sha256']),
                                        receipt=witness(receipt_path)))
        results.append(witness(witness_path))
        progress(output, 'prefix_complete', cycle_index=index, through_cursor=step['through_cursor'],
                 snapshot_bytes=path.stat().st_size, witness_sha256=results[-1]['sha256'],
                 batch_binding_sha256=binding_sha256)
    return results


def main(configuration_path):
    configuration = json.loads(Path(configuration_path).read_bytes())
    source, ingestion, completion, schedule, lineage = validate_inputs(configuration)
    manifest=read_pinned(configuration['source_manifest'])
    scope=source_scope(manifest,expected_manifest_hash=manifest['manifest_hash'])
    if scope.genesis_hash()!=completion['scope_hash']: raise ValueError('final completion scope differs from pinned source')
    entity=(1,111313);t_ctx=sunday_native_runtime.DEVELOPMENT['context_rows']
    if t_ctx!=4096: raise ValueError('reviewed Sunday context selection changed')
    output = Path(configuration['host_runtime']['prefixes_directory'])
    output.mkdir(parents=True, exist_ok=True)
    with _exclusive(output / 'remaining-prefix-writer.lock'):
        progress(output, 'validating_final_source_physical_pin')
        journal = source / 'source.sqlite'
        if sha(journal) != ingestion['journal_sha256']:
            raise ValueError('final source physical pin differs')
        first_path = output / 'prefix-00-witness.json'
        first = json.loads(first_path.read_bytes()); pinned(first['snapshot'])
        first_receipt = read_pinned(first['receipt']); matches_step(first_receipt, schedule['steps'][0])
        origins = {str(journal.resolve()): completion['journal_count']}
        origins.update({str(Path(link['closed_parent']['path']).resolve()): link['closed_parent']['count']//2*2
                        for link in lineage['links']})
        if (str(Path(first_receipt['original_journal']).resolve()) not in origins
                or first_receipt['journal_count'] > origins[str(Path(first_receipt['original_journal']).resolve())]):
            raise ValueError('retained prefix00 has no verified closed ancestry')
        host = configuration['host_runtime']
        binding = dict(schema='FRANKIE_REMAINING_SUNDAY_PREFIXES_V1',
                       ingestion_receipt=host['ingestion_receipt'], schedule_receipt=host['schedule_receipt'],
                       schedule=host['schedule'], source_lineage=host['source_lineage'],
                       source_journal_sha256=ingestion['journal_sha256'],
                       source_count=completion['journal_count'], source_head_hash=completion['journal_hash'],
                       preserved_prefix00=witness(first_path), script_sha256=sha(__file__),
                       copier_sha256=sha(snapshot.__file__), model_calls=0, source_replays=0)
        binding.update(context_selection=dict(entity=list(entity),t_ctx=t_ctx,
            runtime_code_sha256=sha(sunday_native_runtime.__file__),selection_code_sha256=sha(context_session.__file__)))
        binding_path = output / 'remaining-prefix-binding.json'
        if binding_path.exists():
            if json.loads(binding_path.read_bytes()) != binding:
                raise ValueError('retained prefix batch identity changed')
        else: save_new(binding_path, binding)
        results = materialize(journal, output, schedule['steps'], parent_count=completion['journal_count'],
                              parent_head_hash=completion['journal_hash'], binding_sha256=sha(binding_path),
                              scope=scope,entity=entity,t_ctx=t_ctx)
        progress(output, 'verifying_final_source_physical_pin')
        if sha(journal) != ingestion['journal_sha256']:
            raise ValueError('source physical bytes changed during prefix batch')
        result = dict(schema='FRANKIE_FULL_SUNDAY_PREFIX_WITNESSES_V1', binding=witness(binding_path),
                      witnesses=[witness(first_path)] + results, prefixes=19, source_records=57027,
                      model_calls=0, source_replays=0,
                      prefix_seed_witnesses={str(index):witness(output/f'prefix-{index:02d}-packet-seed.json')
                                             for index in range(1,19)})
        final = output / 'full19-prefix-witnesses.json'
        if final.exists():
            if json.loads(final.read_bytes()) != result: raise ValueError('final prefix manifest changed')
        else: save_new(final, result)
        progress(output, 'complete', prefixes=19, manifest_sha256=sha(final))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configuration', required=True)
    main(parser.parse_args().configuration)

