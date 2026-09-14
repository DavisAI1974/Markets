"""Opt-in verified rolling forecast -> category-free Frankie record.

No provider, model forward, scheduling, delivery, execution or Memory A writes.
Disabled calls bypass imports, ledger reads and all enabled argument validation.
"""


def _computation_binding(artifact):
    """Require the complete same-forward receipts and their causal packet link."""
    from dataclasses import asdict
    import json
    try:
        from .context_session import ContextReceipt, SCHEMA, TRUNK_SCHEMA
        from .b1_reasoner import RecurrenceReceipt, RECURRENCE_SCHEMA, HALT_SCHEMA
        from .c15_journal import evidence_hash, unpack, pack, canonical_bytes
        from .forecast_contract import sha256_digest
    except ImportError:
        from context_session import ContextReceipt, SCHEMA, TRUNK_SCHEMA
        from b1_reasoner import RecurrenceReceipt, RECURRENCE_SCHEMA, HALT_SCHEMA
        from c15_journal import evidence_hash, unpack, pack, canonical_bytes
        from forecast_contract import sha256_digest
    binding = unpack(json.loads(artifact.context_receipt))
    if type(binding) is not dict or set(binding) != {'context', 'recurrence', 'native_execution_hash'}:
        raise ValueError('complete native computation binding required')
    context = asdict(ContextReceipt(**binding['context']))
    recurrence = asdict(RecurrenceReceipt(**binding['recurrence']))
    if (context['schema'] != SCHEMA or context['trunk_schema'] != TRUNK_SCHEMA
            or recurrence['schema'] != RECURRENCE_SCHEMA or recurrence['halt_schema'] != HALT_SCHEMA
            or canonical_bytes(pack(binding)) != artifact.context_receipt):
        raise ValueError('unsupported or noncanonical computation receipt')
    sha256_digest(binding['native_execution_hash'], 'native execution')
    # Evidence packing preserves mapping order. Reproduce ContextSessionRunner's
    # packet order, which differs from the ContextReceipt dataclass field order.
    packet_fields = ('schema', 'trunk_schema', 'registry_hash', 'journal_prefix_hash',
        'journal_entries', 'source_prefix_hash', 'scope_kind', 'scope_hash',
        'teacher_hash', 'teacher_binding', 'prefix_rows', 'entity_rows', 'other_entity_rows',
        'context_start', 'context_end', 'outside_context_rows', 'context_cursors',
        'packet_hashes', 'consumed_rows', 'as_of', 't_ctx')
    info = {k: context[k] for k in packet_fields}
    # These are the two existing context-session packet conventions: plain and QSV.
    packets = (evidence_hash(info), evidence_hash(dict(context=info, input_hash=artifact.input_hash)))
    if recurrence['packet_hash'] not in packets:
        raise ValueError('recurrence packet differs from forecast context')
    return binding


def consume_forecast(*, legacy, enabled=False, book=None, publication_hash=None, metadata=None):
    if type(enabled) is not bool:
        raise ValueError('explicit boolean enable flag required')
    if not enabled:
        return legacy()
    import sqlite3
    import struct
    try:
        from .forecast_artifact import NativeForecastArtifact
        from .forecast_bridge import prepare_frankie_forecast, route_frankie_forecast
        from .frankie_category_free import category_free_abstain
        from .frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, ContractError
        from .c15_journal import evidence_hash
    except ImportError:
        from forecast_artifact import NativeForecastArtifact
        from forecast_bridge import prepare_frankie_forecast, route_frankie_forecast
        from frankie_category_free import category_free_abstain
        from frankie_contract import BLD1_FIELDS, BLD1_FIELD_NAMES, ContractError
        from c15_journal import evidence_hash
    forecast_fields = {'guessed_net_usd', 'overnight_gap_usd', 'path_p50_curve', 'confidence'}
    if not isinstance(metadata, dict) or set(metadata) != set(BLD1_FIELD_NAMES)-forecast_fields:
        raise ValueError('complete existing Frankie metadata required')
    # Caller context must be valid even when the forecast is unavailable.
    for field in BLD1_FIELDS:
        if field.name in metadata:
            field.validate(metadata[field.name])
    if metadata['state_defects_and_gaps_reported']:
        return category_free_abstain(metadata, metadata['state_defects_and_gaps_reported'])
    try:
        if not callable(getattr(book, 'publication', None)):
            raise ValueError('verified forecast book unavailable')
        publication = book.publication(publication_hash)
        candidate = publication.selected
        # Normalize expected deserialization failures only at the artifact boundary.
        try:
            artifact = NativeForecastArtifact.from_payload(candidate.forecast_artifact,
                                                           expected_digest=candidate.candidate_id)
            binding = _computation_binding(artifact)
        except (IndexError, AttributeError, struct.error) as exc:
            raise ValueError('malformed native artifact or computation receipt') from exc
        session = artifact.session
        if (candidate.target.instrument != session.instrument or candidate.target.target_ns != session.close_ns
                or candidate.as_of != session.receive_cutoff_ns or candidate.source_as_of != session.event_cutoff_ns
                or candidate.source_hash != session.source_hash or candidate.arm_hash != artifact.arm_hash
                or artifact.context_receipt is None):
            raise ValueError('publication source/target/arm differs from native artifact')
        expected_model = evidence_hash(dict(native=artifact.native_model_hash,
            execution=binding['native_execution_hash'], decoder=artifact.snapshot.digest))
        if candidate.model_hash != expected_model:
            raise ValueError('publication model differs from native artifact')
        prepared = prepare_frankie_forecast(artifact, expected_digest=candidate.candidate_id, metadata=metadata)
        return route_frankie_forecast(enabled=True, legacy=None, load_native=lambda: prepared,
            expected_digest=candidate.candidate_id, publication_hash=publication.receipt_hash,
            metadata=metadata)
    except (ValueError, TypeError, KeyError, ContractError, RuntimeError, OSError, sqlite3.Error) as exc:
        return category_free_abstain(metadata, (f'native_forecast_unavailable: {type(exc).__name__}: {exc}',))
