"""One exact final conformance traversal of a separately pinned closed snapshot.

No producer changes, shared cache, launch authority, or replacement completion files.
Checkpoint restoration retains every C15Builder.restore state predicate; the
journal proof runs together with the unchanged SourceConformanceDriver semantics.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import time

try:
    from .c15_builder import C15Builder
    from .c15_journal import SCHEMA, evidence_hash, pack, unpack
    from .c15_registry import implementation_identity
    from .causal_prefix_records import RecordPrefixChain
    from .mbo_resume_state import restore_adapter_state
    from .source_conformance import SourceConformanceDriver
    from .verified_journal_reader import VerifiedJournalReader
except ImportError:
    from c15_builder import C15Builder
    from c15_journal import SCHEMA, evidence_hash, pack, unpack
    from c15_registry import implementation_identity
    from causal_prefix_records import RecordPrefixChain
    from mbo_resume_state import restore_adapter_state
    from source_conformance import SourceConformanceDriver
    from verified_journal_reader import VerifiedJournalReader


@dataclass(frozen=True)
class Finalization:
    completion: object
    checkpoint: dict
    physical_sha256: str
    wall_seconds: float
    cpu_seconds: float
    worker_cpu_seconds: float = 0.0
    gate_authority: bool = False


def physical_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class _CaptureDriver(SourceConformanceDriver):
    def _verified_checkpoint(self):
        state, counts = super()._verified_checkpoint()
        self.verified_state = state
        return state, counts


def finalize_snapshot(path, scope, state, *, expected_scope_hash,
                      expected_state_hash, expected_physical_sha256,
                      storage='legacy', workers=1, reader_factory=None):
    path = Path(path)
    wall, cpu = time.perf_counter(), time.process_time()
    SourceConformanceDriver._check_scope(scope, expected_scope_hash)
    if path.is_symlink() or any(Path(str(path)+suffix).exists()
                               for suffix in ('-wal', '-shm', '-journal')):
        raise ValueError('closed standalone snapshot required')
    if physical_hash(path) != expected_physical_sha256:
        raise ValueError('snapshot physical identity differs')
    state = unpack(pack(state))
    keys = {'schema', 'scope_genesis_hash', 'implementation', 'adapter', 'prefix',
            'sessions', 'journal_count', 'journal_hash', 'state_hash'}
    if type(state) is not dict or set(state) != keys:
        raise ValueError('invalid full-evidence checkpoint fields')
    body = {k: v for k, v in state.items() if k != 'state_hash'}
    if (state['state_hash'] != expected_state_hash or evidence_hash(body) != expected_state_hash
            or state['schema'] != SCHEMA or state['scope_genesis_hash'] != scope.genesis_hash()
            or state['implementation'] != implementation_identity()):
        raise ValueError('full-evidence checkpoint identity mismatch')
    builder = C15Builder.__new__(C15Builder)
    builder.scope, builder.identity = scope, implementation_identity()
    builder.chain = RecordPrefixChain.restore(scope, state['prefix'])
    builder.adapter = restore_adapter_state(state['adapter'])
    builder._sessions, builder._failed = dict(state['sessions']), False
    if reader_factory is not None:
        reader = reader_factory(path, expected_count=state['journal_count'],
                                expected_head_hash=state['journal_hash'])
    elif storage == 'legacy':
        reader = VerifiedJournalReader(path, expected_count=state['journal_count'],
                                       expected_head_hash=state['journal_hash'])
    elif storage == 'compact':
        try:
            from .compact_conformance_reader import CompactConformanceReader
        except ImportError:
            from compact_conformance_reader import CompactConformanceReader
        reader = CompactConformanceReader(path, expected_count=state['journal_count'],
            expected_head_hash=state['journal_hash'], workers=workers)
    else:
        raise ValueError('unknown journal storage format')
    with reader:
        builder.journal = reader
        if reader.count != 2 * builder.chain.next_cursor or builder.export_state() != state:
            raise ValueError('checkpoint state is inconsistent or noncanonical')
        driver = _CaptureDriver.__new__(_CaptureDriver)
        driver._builder = builder
        driver._stopped = driver._completed = driver._closed = False
        completion = driver.complete()
        checkpoint = driver.verified_state
    if physical_hash(path) != expected_physical_sha256:
        raise ValueError('snapshot physical identity changed during verification')
    return Finalization(completion, checkpoint, expected_physical_sha256,
                        time.perf_counter()-wall, time.process_time()-cpu,
                        getattr(reader, 'worker_cpu_seconds', 0.0))
