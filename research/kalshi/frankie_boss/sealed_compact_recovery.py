"""Read-only reconstruction of a completed sealed C15 compact journal.

No source extraction, adapter.apply, journal append or seal operation is allowed.
The checkpoint retains its original implementation identity. Completion is a
new conformance claim; it never backdates the cancelled ingestion's receipt.
"""
from collections import deque
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time

from .c15_journal import SCHEMA, pack, canonical_bytes, evidence_hash
from .c15_registry import implementation_identity
from .causal_prefix_records import RecordInput, RecordPrefixChain
from .compact_conformance_reader import project_entries
from .frankie_journal_reader import FrankieCompactReader, _read_block
from .mbo_resume_state import SCHEMA as ADAPTER_SCHEMA, adapter_state_hash, export_adapter_state, restore_adapter_state
from .source_conformance import SourceCompletion
from research.ng_exhaustion_mbo_v4_state_adapter_20260820 import ADAPTER_REVISION, ACTIVITY_WINDOWS_S

ORIGINAL_CODE_BLOBS = {
    "c15_builder.py": "7d30ce9601bce92bb37fad1721226b91db209b80",
    "c15_observer.py": "e6f36bccd5f9c8b4aa2f200301798154c40f19be",
    "c15_journal.py": "dd323e2ac423988a0b78d066071f8e8b79a30951",
    "c15_registry.py": "1a6eab95672353f854fdcb8399b62185cc98791f",
    "causal_prefix.py": "ca5d1db4e4d036a9079c58bea2ac14a262910c63",
    "causal_prefix_records.py": "f792c00bbf2401072583e3e4d1266c44344addc4",
    "causal_packet.py": "e204565411062ecca09fa593ecced7d3b59ba60d",
    "mbo_resume_state.py": "1bea3bc2b77dcde55e91dd0e8367f05abee819d6",
    "ng_exhaustion_mbo_v4_state_adapter_20260820.py": "1f07a786cab890b955fb1c631d10900fd5a09e06"
}
CODE_ORDER = tuple(ORIGINAL_CODE_BLOBS)


def original_identity(code_blobs, *, require_adapter_semantics=True):
    current = implementation_identity()['code_blobs']
    if code_blobs != ORIGINAL_CODE_BLOBS and code_blobs != current:
        raise ValueError('unsupported original implementation')
    # Reconstruction restores adapter state and must retain its exact semantics.
    # A completed-evidence reader never restores or calls an adapter: it still
    # requires the original identity and unchanged journal/prefix codecs.
    unused = {'c15_builder.py', 'c15_observer.py'}
    if not require_adapter_semantics:
        unused.add('ng_exhaustion_mbo_v4_state_adapter_20260820.py')
    for name in CODE_ORDER:
        if name not in unused and code_blobs[name] != current[name]:
            raise ValueError('recovery state semantics differ: ' + name)
    return dict(schema=SCHEMA, code_blobs={name: code_blobs[name] for name in CODE_ORDER},
                contract_hash=evidence_hash(dict(schema=SCHEMA, retention='all supplied evidence',
                                                 reductions=[], fields='all original fields')))


def physical_witness(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('journal path must be a regular file without symbolic links')
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('sealed journal has a sidecar')
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(8 << 20), b''):
            h.update(chunk)
        finished = os.fstat(stream.fileno())
    after = path.stat()
    if any(getattr(before, k) != getattr(v, k) for k in fields for v in (opened, finished, after)):
        raise ValueError('journal changed while hashing')
    return dict(path=str(path), bytes=after.st_size, sha256=h.hexdigest())


def _recovery_block(path, index):
    entries, cpu = _read_block(path, index)
    projection = project_entries(entries)
    for full, small in zip(entries, projection):
        if full['kind'] != 'APPLIED':
            continue
        p, q = full['payload'], small['payload']
        q['effect'] = p['effect']
        q['integrity'] = p['integrity']
        frame, observation = p['frame'], p['observation']
        q['frame'] = None if frame is None else {k: frame[k] for k in
            ('instrument_id', 'raw_symbol', 'ts_recv_ns', 'ts_event_ns', 'integrity')}
        q['observation'] = None if observation is None else {k: observation[k] for k in
            ('instrument_id', 'last_sequence', 'last_recv_ns', 'last_event_ns', 'integrity')}
    return projection, cpu


class RecoveryReader(FrankieCompactReader):
    block_task = staticmethod(_recovery_block)
    progress_phase = 'sealed_recovery_conformance'

    def terminal_observation(self, ordinal):
        index = self.db.execute(
            'SELECT start,count,previous,head FROM blocks WHERE start<=? ORDER BY start DESC LIMIT 1',
            (ordinal,)).fetchone()
        if index is None or ordinal >= index[0] + index[1]:
            raise ValueError('terminal observation is outside compact coverage')
        entries, _ = _read_block(str(self.path), index)
        entry = entries[ordinal - index[0]]
        if entry['ordinal'] != ordinal or entry['kind'] != 'APPLIED':
            raise ValueError('terminal observation identity differs')
        return entry['payload']['observation']


def reconstruct(scope, path, *, expected_sha256, expected_bytes, expected_count,
                expected_head_hash, code_blobs, workers=1, expected_session=None, emit=None):
    """Verify and reconstruct without any side effect on the source container."""
    identity = original_identity(code_blobs)
    before = physical_witness(path)
    if (before['sha256'], before['bytes']) != (expected_sha256, expected_bytes):
        raise ValueError('journal physical identity differs from independent witness')
    declared = tuple(m.mbo_records for m in scope.members)
    if type(expected_count) is not int or expected_count != 2 * sum(declared):
        raise ValueError('journal count differs from complete declared source')
    chain, counts, books, sessions, boundaries = RecordPrefixChain(scope), [0]*len(declared), {}, {}, {}
    session_spans, pending = [], None
    started = time.perf_counter()
    with RecoveryReader(path, expected_count=expected_count, expected_head_hash=expected_head_hash,
                        workers=workers, emit=emit) as reader:
        for entry in reader.entries():
            p = entry['payload']
            if entry['kind'] == 'INPUT':
                if pending is not None or p['cursor'] != chain.next_cursor or p['scope_genesis_hash'] != scope.genesis_hash():
                    raise ValueError('source journal input continuity mismatch')
                pending = entry['ordinal'], p
                continue
            if entry['kind'] != 'APPLIED' or pending is None:
                raise ValueError('source journal has failed or unpaired evidence')
            ordinal, submitted = pending
            if (p['input_ordinal'] != ordinal or pack(p['raw_record']) != pack(submitted['record'])
                    or any(p[k] != submitted[k] for k in ('cursor', 'source_member_index', 'session_id'))
                    or any(p['normalized'][k] != submitted[k] for k in ('raw_symbol', 'source_dbn_object'))):
                raise ValueError('applied evidence differs from submission')
            if expected_session is not None and p['session_id'] != expected_session:
                raise ValueError('retained source contains a different trading session')
            receipt = chain.advance(RecordInput(p['cursor'], p['source_member_index'], p['normalized'], scope.adapter_revision))
            if (p['terminal_prefix_hash'] != chain.prefix_hash or p['record_count'] != chain.next_cursor
                    or p['group_count'] != chain.next_global_group_ordinal
                    or pack(p['receipt']) != pack(None if receipt is None else receipt.public_dict())):
                raise ValueError('source journal prefix or group receipt mismatch')
            member = p['source_member_index']
            counts[member] += 1
            msg, effect = p['normalized'], p['effect']
            iid = msg['instrument_id']
            b = books.setdefault(iid, dict(raw_symbol=None, last_sequence=None, last_recv_ns=None,
                last_event_ns=None, activity_last_now_ns=None, activity=deque(), terminal=None, observation=None))
            for key, field in (('last_sequence','sequence'), ('last_recv_ns','ts_recv_ns'), ('last_event_ns','ts_event_ns')):
                b[key] = max(b[key] or msg[field], msg[field])
            b['raw_symbol'] = msg['raw_symbol'] or b['raw_symbol']
            if not msg['is_snapshot']:
                b['activity'].append(dict(ts_recv_ns=msg['ts_recv_ns'], action=msg['action'], side=msg['side'],
                    price_raw=msg['price_raw'], size=msg['size'], size_delta=effect['size_delta'],
                    priority_lost=effect['priority_lost'], missing_reference=effect['missing_reference'],
                    top_touch=effect['touched_or_improved_top_before']))
                cutoff = msg['ts_recv_ns'] - max(ACTIVITY_WINDOWS_S)*1_000_000_000
                while b['activity'] and b['activity'][0]['ts_recv_ns'] < cutoff:
                    b['activity'].popleft()
            frame, observation = p['frame'], p['observation']
            if msg['is_last']:
                if frame is None or observation is None:
                    raise ValueError('closed group lacks terminal evidence')
                if (frame['instrument_id'] != iid or observation['instrument_id'] != iid
                        or frame['ts_recv_ns'] != msg['ts_recv_ns'] or frame['ts_event_ns'] != msg['ts_event_ns']
                        or frame['raw_symbol'] != b['raw_symbol'] or frame['integrity'] != p['integrity']
                        or observation['integrity'] != p['integrity']
                        or any(observation[k] != b[k] for k in ('last_sequence','last_recv_ns','last_event_ns'))):
                    raise ValueError('terminal evidence contradicts retained history')
                b['activity_last_now_ns'], b['terminal'], b['observation'] = frame['ts_recv_ns'], entry['ordinal'], observation
            elif frame is not None or observation is not None:
                raise ValueError('open group carries unexpected terminal evidence')
            sessions[iid] = p['session_id']
            if not session_spans or session_spans[-1]['session_id'] != p['session_id']:
                session_spans.append(dict(session_id=p['session_id'], first_cursor=p['cursor'], member_index=member))
            raw = p['raw_record']
            boundaries[member] = dict(cursor=p['cursor'], ts_recv_ns=msg['ts_recv_ns'],
                session_id=p['session_id'], is_last=msg['is_last'],
                wire_sha256=hashlib.sha256(raw['dbn_wire_bytes']).hexdigest() if 'dbn_wire_bytes' in raw else None)
            pending = None
        prefix = chain.export_state()  # Refuses unclosed instrument groups.
        if pending is not None or tuple(counts) != declared or expected_count != 2*chain.next_cursor:
            raise ValueError('source member counts or pairing incomplete')
        recovered_books = []
        for iid, b in sorted(books.items()):
            if b['terminal'] is None:
                raise ValueError('instrument lacks a terminal observation')
            o = reader.terminal_observation(b['terminal'])
            if any(o[k] != b['observation'][k] for k in b['observation']):
                raise ValueError('terminal observation changed')
            recovered_books.append(dict(instrument_id=iid, raw_symbol=b['raw_symbol'],
                last_sequence=b['last_sequence'], last_recv_ns=b['last_recv_ns'], last_event_ns=b['last_event_ns'],
                activity_last_now_ns=b['activity_last_now_ns'], integrity=dict(sorted(o['integrity'].items())),
                orders=o['orders'], levels={side:[x for x in o['levels'][side] if x['order_ids']] for side in ('B','A')},
                activity=list(b['activity'])))
        adapter = dict(schema=ADAPTER_SCHEMA, adapter_revision=ADAPTER_REVISION, record_count=chain.next_cursor,
            completed_event_group_count=chain.next_global_group_ordinal, books=recovered_books, state_hash='')
        adapter['state_hash'] = adapter_state_hash(adapter)
        # Canonical original key/order layout, including dataclass orders and sorted FIFO levels.
        adapter = export_adapter_state(restore_adapter_state(adapter))
        body = dict(schema=SCHEMA, scope_genesis_hash=scope.genesis_hash(), implementation=identity,
            adapter=adapter, prefix=prefix, sessions=[[iid,s] for iid,s in sorted(sessions.items())],
            journal_count=reader.count, journal_hash=reader.head_hash)
        state = dict(body, state_hash=evidence_hash(body))
        completion = SourceCompletion('BOSS_SOURCE_CONFORMANCE_V1', scope.kind.value, scope.genesis_hash(),
            sum(counts), tuple(counts), chain.next_global_group_ordinal, chain.prefix_hash,
            reader.count, reader.head_hash, state['state_hash'])
        reader._check_seal()
        resources = dict(worker_cpus=list(reader.worker_cpus), worker_cpu_seconds=reader.worker_cpu_seconds,
                         conformance_seconds=time.perf_counter()-started)
    after = physical_witness(path)
    if after != before:
        raise ValueError('parent journal changed during recovery')
    return dict(state=state, completion=asdict(completion), completion_digest=completion.digest,
                container=after, sessions=session_spans, member_boundaries=boundaries, resources=resources,
                source_replays=0, adapter_apply_calls=0, parent_writes=0)
