"""The opening book of a trading day that starts at the prior day's halt (Greg, 2026-09-29: "build the remaining missing
hrs for Tuesday so we can combine with what we already have for Tue to get a complete tue book").

A trading day D opens at 18:00 ET on the prior calendar day, so its first records are the TAIL of the prior UTC partition
(after the 21:00Z halt). The orders resting at that halt were placed during the prior trading day; a book that starts
empty at the halt would miss every one of them until they trade or cancel. The prior day's sealed ingest already holds
that book: its builder checkpoint (builder-checkpoint.c15.json) is the adapter's exact state after its last record,
which is the record before the halt. This module reads it in place, checks it against the prior day's receipt (sha256
of the file, the state hash, the hash recomputed from the body) and returns the adapter state (every instrument's
book: resting orders, levels, activity) plus a descriptor of where it came from. Nothing is re-ingested, nothing is
recomputed, nothing is copied; the day's own journal holds only the day's own records.

Two prior receipts are read:
  BOSS_BLOCK_INGESTION_RECEIPT_V1                an ingest by operations/ingest_block_sources.py (Tuesday for Wednesday):
                                                  the checkpoint sits beside the receipt; the day's end is its partial
                                                  member (member_key, take)
  FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1   Monday 20211004 (its ingest was recovered, blocks/MONDAY_RECOVERY_*):
                                                  the checkpoint sits beside the container; the day's end is the partial
                                                  member of the committed manifest named by its manifest_hash
The caller restores the state with mbo_resume_state.restore_adapter_state (its own validation and exact round trip)
and zeroes the two counters, so the day's counts are the day's own records while its book is the real book.
"""
import hashlib
import json
from pathlib import Path

try:
    from .c15_journal import evidence_hash, unpack
    from .raw_mbo_source_manifest import manifest_hash
except ImportError:   # flat import
    from c15_journal import evidence_hash, unpack
    from raw_mbo_source_manifest import manifest_hash

INGESTION = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
RECOVERY = 'FRANKIE_SEALED_INGESTION_RECOVERY_RECEIPT_V1'
CHECKPOINT = 'builder-checkpoint.c15.json'
BLOCKS = Path(__file__).resolve().parent / 'blocks'


def _sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def _manifest_by_hash(expected):
    """The committed trading-day manifest whose hash is `expected` (blocks/BLOCK_*_SOURCE_MANIFEST.json)."""
    found = []
    for path in sorted(BLOCKS.glob('BLOCK_*_SOURCE_MANIFEST.json')):
        body = json.loads(path.read_bytes())
        if body.get('manifest_hash') == expected and manifest_hash(body) == expected:
            found.append(path)
    if len(found) != 1:
        raise ValueError(f'{len(found)} committed manifests carry hash {expected}; exactly one is required')
    return found[0], json.loads(found[0].read_bytes())


def load(receipt_path):
    """(adapter_state, descriptor) of the prior trading day's closing book, verified against its receipt."""
    receipt_path = Path(receipt_path).resolve()
    raw_receipt = receipt_path.read_bytes()
    receipt = json.loads(raw_receipt)
    schema = receipt.get('schema')
    if schema == INGESTION:
        if receipt.get('writer') != 'compact':
            raise ValueError('the prior ingestion receipt must be a compact ingest')
        checkpoint = receipt_path.parent / CHECKPOINT
        checkpoint_sha256 = receipt['checkpoint_sha256']
        ends = list(receipt.get('partial_members_ingested') or [])
        end = dict(member_key=ends[-1]['member_key'], take=ends[-1]['take']) if ends else None
        last_session = receipt['sessions'][-1]['session_id'] if receipt.get('sessions') else None
    elif schema == RECOVERY:
        if receipt.get('status') != 'complete':
            raise ValueError('the prior recovery receipt is not complete')
        artifact = receipt['artifacts']['checkpoint']
        checkpoint = Path(receipt['container']['path']).parent / artifact['file']
        checkpoint_sha256 = artifact['sha256']
        manifest_path, manifest = _manifest_by_hash(receipt['manifest_hash'])
        partial = list(manifest.get('partial_members') or [])
        end = dict(member_key=partial[-1]['member_key'], take=partial[-1]['take'], manifest=manifest_path.name) if partial else None
        boundaries = receipt.get('member_boundaries') or {}
        last_session = boundaries[max(boundaries, key=int)]['session_id'] if boundaries else None
    else:
        raise ValueError(f'the opening receipt must be {INGESTION} or {RECOVERY}, not {schema}')
    raw = checkpoint.read_bytes()
    if _sha256(raw) != checkpoint_sha256:
        raise ValueError(f'{checkpoint} differs from the sha256 its receipt declares')
    state = unpack(json.loads(raw))
    body = {key: value for key, value in state.items() if key != 'state_hash'}
    if state.get('state_hash') != receipt['checkpoint_state_hash'] or evidence_hash(body) != state['state_hash']:
        raise ValueError(f'{checkpoint} state hash differs from its receipt or from its own body')
    adapter = state.get('adapter')
    if type(adapter) is not dict or type(adapter.get('books')) is not list:
        raise ValueError(f'{checkpoint} carries no adapter state')
    descriptor = dict(status='seeded', receipt=str(receipt_path), receipt_schema=schema, receipt_sha256=_sha256(raw_receipt),
                      checkpoint=str(checkpoint), checkpoint_sha256=checkpoint_sha256, checkpoint_state_hash=state['state_hash'],
                      adapter_state_hash=adapter.get('state_hash'), prior_trading_day=receipt.get('trading_day'),
                      prior_record_count=receipt.get('record_count'), prior_journal_hash=receipt.get('journal_hash'),
                      prior_last_session=last_session, prior_end=end, instruments=len(adapter['books']),
                      resting_orders=sum(len(book.get('orders') or []) for book in adapter['books']),
                      rule='the orders resting at the prior day\'s halt, read from its sealed ingest; the counters are the '
                           'day\'s own (zeroed), the book is the real book')
    return adapter, descriptor


def absent(reason):
    """The descriptor when no prior day's book is given: the day is ingested from an empty book, and that is listed."""
    return dict(status='absent', reason=reason,
                consequence='orders resting at the prior halt are not in the book until they trade, are modified or '
                            'cancelled, or a snapshot resets the book; every record of the day is still ingested')
