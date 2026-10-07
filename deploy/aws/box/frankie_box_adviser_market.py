"""Exact existing-cutoff market context for governed adviser inputs.

Contract (FRANKIE_ADVISER_MARKET_CONTEXT_V1)
  Input: the shared reader identity a teacher or classroom already published, the day, and that
  measurement's ORIGINAL explicit source scope (source_hash, as_of, through_cursor). Never a Frankie
  private target selection, answer, grade, claim or private reasoning.
  Output: one complete picture at the INPUT whose original adapter cursor equals through_cursor, as
  exact typed text with its sha256; a `read` block saying what was read and verified and where the
  read stopped; a `coverage` block naming what is thin at that instant.
  Errors, one way: ValueError for contradictions of identity, pinned bytes or scope. Those are
  integrity failures and stay visible. Missing layers, a failed/unpaired/unknown outcome at the
  cutoff, an unavailable clock or an absent external day file never raise: the instant stays in,
  thinner, with its dispositions written down (Greg, 2026-10-07).

The full ordered reader stays owner-local and accessible (`iter_pictures`). This module selects no
target extrema and no new scientific window, serializes one instant (not a day) and makes no model
call. Reaching a prompt is not proof a model experienced every historical picture.
"""
import copy
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_V1'
REFERENCE_SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_REFERENCE_V1'
WORKFLOW_REPORT_SCHEMA = 'FRANKIE_PIECE_WORKFLOW_REPORT_V1'
MISSING_COVERAGE_RULE = 'every_authentic_boundary_kept_with_thinner_explicit_picture'
WORKERS = 15
USE = 'complete same-time picture at the existing original source cutoff; no target-derived selection'
LIMIT = ('model receives this complete cutoff picture, not every historical picture; full ordered reader remains '
         'available to owner code; no time-addressable model query protocol or new scientific calculation')


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


class AdviserMarketContext:
    def __init__(self, identity, *, day, source_hash, as_of, through_cursor):
        from frankie_box_durable import witness
        from frankie_box_market_timeline import SharedMarketTimeline, _json
        if type(as_of) is not int or type(through_cursor) is not int or through_cursor < 0:
            raise ValueError('adviser cutoff requires the original explicit integer as_of and through_cursor')
        self.root = Path(identity['calculations']['path']).parent
        self.day = str(day)
        self.reader = SharedMarketTimeline(self.root, day=self.day, workers=WORKERS)
        if self.reader.identity != identity:
            raise ValueError('adviser source differs from the shared market reader identity')
        ingestion = _json(self.reader.source['ingestion_receipt'])
        if ingestion['source_prefix_hash'] != source_hash:
            raise ValueError('adviser cutoff names another sealed source')
        record_count = ingestion['record_count']
        if type(record_count) is not int or not through_cursor < record_count:
            raise ValueError('adviser cutoff lies outside the sealed source record count')
        # Every pinned layer is checked whole before the read, so a read that stops exactly at
        # the cutoff loses no byte integrity. Row identities and clocks are checked by the core on
        # every consumed row. A mismatch here is corruption, never thin coverage.
        pinned = dict(identity['sources'])
        if (identity.get('external') or {}).get('status') == 'attached':
            pinned['external'] = identity['external']
        for name, pin in pinned.items():
            if witness(pin['path']) != {k: pin[k] for k in ('bytes', 'sha256')}:
                raise ValueError('pinned shared layer bytes differ from their source pin: ' + name)
        self.pins_verified = sorted(['journal', *pinned])
        self.scope = dict(day=self.day, source_hash=source_hash, as_of=as_of, through_cursor=through_cursor,
                          record_count=record_count,
                          position=('last_sealed_input' if through_cursor == record_count - 1
                                    else 'before_sealed_source_end'),
                          origin='the measurement\'s own explicit source scope; no target-derived selection')

    def _coverage(self, picture):
        """What is present and what is thin at this instant, from the picture alone; nothing invented."""
        at = picture['at']
        boundary = at['input_cursor']
        last_observed = {}
        for update in picture['last_observed_state']:
            age = ('observed_at_this_boundary' if update.get('input_cursor') == boundary
                   else 'previously_known_last_observed_value')
            last_observed.setdefault(update['source'], []).append(dict(
                instrument_id=update.get('instrument_id'), input_cursor=update.get('input_cursor'),
                known_at_ns=update.get('known_at_ns'), age=age))
        updates = {}
        for update in picture['updates']:
            updates[update['source']] = updates.get(update['source'], 0) + 1
        clock, frontier, as_of = at['ts_recv_ns'], at['publication_frontier_ns'], self.scope['as_of']
        clocks = dict(
            receive_clock='exact' if type(clock) is int else 'no_exact_receive_clock_at_cutoff_input',
            raw_receive_clock_present=at.get('raw_receive_clock') is not None,
            receive_clock_vs_declared_as_of=(None if type(clock) is not int else
                                             'at_or_before' if clock <= as_of else 'after_declared_row_as_of'),
            publication_frontier=('exact' if type(frontier) is int else 'no_exact_receive_clock_observed_yet'),
            publication_frontier_vs_declared_as_of=(None if type(frontier) is not int else
                                                    'at_or_before' if frontier <= as_of else 'after_declared_row_as_of'),
            basis='through_cursor is the binding scope; as_of is the measurement\'s declared last row clock and is '
                  'carried, not used to move the cutoff')
        layers = getattr(self.reader, 'layers', None)
        return dict(rule=MISSING_COVERAGE_RULE, source_status=picture['source_status'],
                    unpaired_outcomes=picture['unpaired_outcomes'],
                    original_applied_present=picture['original_applied'] is not None,
                    core_instant_coverage=picture.get('coverage', 'not reported by this core version'),
                    layers_known_to_reader=(layers if layers is not None else 'not reported by this core version'),
                    absent_layers=getattr(self.reader, 'absent_layers', 'not reported by this core version'),
                    updates_at_boundary=updates, last_observed=last_observed,
                    active_instrument_sources=sorted({u['source'] for u in picture['active_instrument_state']}),
                    invalidated_state=copy.deepcopy(picture['invalidated_state']),
                    published_rows=len(picture['published_state']), clocks=clocks,
                    interpretation='a missing or stale part makes this instant thinner, never absent; a previously known '
                                   'value is named as such and is not a new observation; a failed or unpaired outcome is '
                                   'carried as its original disposition, not a measurement')

    def read(self, *, check_save=lambda: None):
        from frankie_box_classroom_code import _exact_market_text
        wanted = self.scope['through_cursor']
        exhaust = self.scope['position'] == 'last_sealed_input'
        selected, matched, cursorless = None, 0, 0
        # The thinner tail (core request, 2026-10-07): the last instant at or before the
        # cutoff that carries an original APPLIED operand, and every instant after it.
        last_applied, tail_after = None, {}
        stream = self.reader.iter_pictures()
        try:
            for item in stream:
                check_save()
                picture = item['picture']
                cursor = picture['at']['adapter_cursor']
                if type(cursor) is not int:
                    cursorless += 1
                    continue
                if cursor > wanted and selected is None:
                    raise ValueError('sealed source has no INPUT at the adviser cutoff adapter cursor %d '
                                     '(%d INPUT envelopes without an adapter cursor seen)' % (wanted, cursorless))
                if cursor <= wanted:
                    if picture['original_applied'] is not None:
                        last_applied = dict(at=copy.deepcopy(picture['at']), source_status=picture['source_status'])
                        tail_after = {}
                    else:
                        status = picture['source_status']
                        tail_after[status] = tail_after.get(status, 0) + 1
                if cursor == wanted:
                    matched += 1
                    if matched > 1:
                        raise ValueError('adviser cutoff adapter cursor %d names more than one original INPUT' % wanted)
                    # Any disposition is kept: applied, failed, unpaired or unknown. The
                    # instant is the teacher's own scope boundary and is never rejected.
                    selected = copy.deepcopy(picture)
                    if not exhaust:
                        break      # nothing after the cutoff is decoded or retained
        finally:
            stream.close()
        if selected is None:
            raise ValueError('sealed source ended before the adviser cutoff adapter cursor %d' % wanted)
        tail = dict(cutoff_input_has_applied_operand=selected['original_applied'] is not None,
                    last_applied_at_or_before_cutoff=last_applied,
                    inputs_after_last_applied_through_cutoff=tail_after,
                    basis='the cutoff instant is the picture; its last-observed states come from earlier exact '
                          'boundaries; an absent APPLIED operand at or after the last applied instant blocks only '
                          'the arithmetic that needs it, never this instant or its unrelated evidence')
        report = copy.deepcopy(self.reader.report)
        read = dict(stopped='source_exhausted' if exhaust else 'at_cutoff_input',
                    source_exhausted=bool(exhaust and report.get('complete') is True),
                    core_report_complete=report.get('complete'),
                    pins_verified=self.pins_verified,
                    pins_basis='whole-file bytes/sha256 before the read; row identity/clock checks on every consumed row',
                    inputs_presented_through_cutoff=report.get('presented_inputs'),
                    inputs_without_adapter_cursor_seen=cursorless,
                    after_cutoff=('the cutoff is the last sealed INPUT; the journal was exhausted for the sealed-count '
                                  'check and no later picture exists' if exhaust else
                                  'no picture after the cutoff was decoded or retained; report dispositions cover the '
                                  'source through the cutoff only'),
                    rule=MISSING_COVERAGE_RULE,
                    not_implied='all-layer coverage or any consumer arithmetic; see coverage')
        text = _exact_market_text(selected)
        return dict(schema=SCHEMA, identity=self.reader.identity, scope=self.scope,
                    at=copy.deepcopy(selected['at']), picture_text=text, picture_sha256=_sha256(text.encode()),
                    coverage=dict(self._coverage(selected), tail=tail), read=read, report=report,
                    reader=dict(module='frankie_box_market_timeline', interface='SharedMarketTimeline.iter_pictures',
                                calculations=str(self.root), day=self.day, identity=self.reader.identity),
                    use=USE, limit=LIMIT)

    def iter_pictures(self):
        """Full exact owner-local history; never silently replace it with the cutoff snapshot."""
        from frankie_box_market_timeline import SharedMarketTimeline
        reader = SharedMarketTimeline(self.root, day=self.day, workers=WORKERS)
        if reader.identity != self.reader.identity:
            raise ValueError('adviser full history changed from its original selected source')
        yield from reader.iter_pictures()


def check(context):
    """The context is whole and self-consistent; an integrity question, not a coverage one."""
    if (not isinstance(context, dict) or context.get('schema') != SCHEMA
            or not isinstance(context.get('picture_text'), str)
            or _sha256(context['picture_text'].encode()) != context.get('picture_sha256')
            or not isinstance(context.get('read'), dict) or not context['read'].get('pins_verified')
            or not isinstance(context.get('coverage'), dict)
            or any(type(context.get('scope', {}).get(k)) is not int for k in ('as_of', 'through_cursor', 'record_count'))):
        raise ValueError('adviser market context differs from its retained complete picture')
    return context


def retain_context(path, context):
    """Durable owner-local copy; existing other bytes are a contradiction, never overwritten."""
    from frankie_box_durable import witness, write_bytes
    check(context)
    path, data = Path(path), _canonical(context)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('retained adviser market context differs; explicit owner recovery required: ' + str(path))
    else:
        write_bytes(path, data)
    return dict(path=str(path), **witness(path))


def load_context(path, *, identity, scope):
    """Reuse a retained context only for the identical source identity and explicit scope."""
    context = check(json.loads(Path(path).read_bytes()))
    if context['identity'] != identity or context['scope'] != scope:
        raise ValueError('retained adviser market context belongs to another source or original cutoff')
    return context


def from_teacher(rows_path, day, measure, *, retain=None, check_save=lambda: None):
    """(context, None) from the teacher's own explicit source/as-of/cursor, never its answers;
    (None, why) when the teacher source carries no shared identity or its rows were not readable."""
    receipt_path = Path(rows_path).parent / 'receipt.json'
    if not receipt_path.is_file():
        return None, 'no teacher receipt beside the Dipole rows; no shared market scope to bind'
    receipt = json.loads(receipt_path.read_bytes())
    identity = receipt.get('shared_market_identity')
    if identity is None:
        return None, 'teacher receipt carries no shared market identity (legacy source; its actual scope is unchanged)'
    if measure is None:
        return None, 'shared teacher rows were not readable, so their explicit source scope cannot bind a cutoff'
    if (str(receipt.get('day')) != str(day)
            or receipt.get('rows_file', {}).get('sha256') != measure['sha256']
            or any(receipt.get(k) != measure[k] for k in ('as_of', 'through_cursor'))):
        raise ValueError('shared exchange context requires its exact teacher source')
    ingestion_pin = receipt['ingestion_receipt']
    raw = Path(ingestion_pin['path']).read_bytes()
    if _sha256(raw) != ingestion_pin['sha256']:
        raise ValueError('shared teacher ingestion receipt changed')
    reader = AdviserMarketContext(identity, day=day, source_hash=json.loads(raw)['source_prefix_hash'],
                                  as_of=measure['as_of'], through_cursor=measure['through_cursor'])
    if retain is not None and Path(retain).is_file():
        return load_context(retain, identity=reader.reader.identity, scope=reader.scope), None
    context = reader.read(check_save=check_save)
    if retain is not None:
        retain_context(retain, context)
    return context, None


def reference(context):
    """Bounded exact reference to a context: identity, scope, clocks, hash and dispositions, no picture body.
    For records and coordination prompts that must not carry the evidence itself."""
    check(context)
    coverage = context['coverage']
    return dict(schema=REFERENCE_SCHEMA, day=context['scope']['day'], scope=context['scope'], at=context['at'],
                picture_sha256=context['picture_sha256'], picture_chars=len(context['picture_text']),
                journal=context['identity'].get('journal'), read=context['read'],
                coverage=dict(source_status=coverage['source_status'], unpaired_outcomes=coverage['unpaired_outcomes'],
                              absent_layers=coverage['absent_layers'], updates_at_boundary=coverage['updates_at_boundary'],
                              last_observed={name: [dict(input_cursor=v['input_cursor'], age=v['age']) for v in values]
                                             for name, values in coverage['last_observed'].items()},
                              published_rows=coverage['published_rows'], clocks=coverage['clocks'],
                              tail=coverage.get('tail')),
                use=context['use'], limit=context['limit'],
                rule='reference only: the complete typed picture is the retained context named by picture_sha256')


def workflow_report(piece, *, context, inputs, use, outputs):
    """One piece's inputs / use / outputs record for the one-day operator review (Greg, 2026-10-07).

    Recorded facts only: which picture values reached which prompt or record, what a role or
    the privacy wall withheld, every missing/stale/unavailable disposition, every cap that
    refused, model calls made or refused, waits. Temporary operator review, not knowledge.
    `context` may be None (legacy source without a shared context) or a context/reference."""
    picture = None
    if isinstance(context, dict) and context.get('schema') == SCHEMA:
        picture = reference(context)
    elif isinstance(context, dict) and context.get('schema') == REFERENCE_SCHEMA:
        picture = context
    return dict(schema=WORKFLOW_REPORT_SCHEMA, piece=piece,
                inputs=dict(inputs, shared_market_picture=picture,
                            shared_market_dispositions=(None if picture is None else
                                                        dict(coverage=picture['coverage'], read=picture['read']))),
                use=use, outputs=outputs,
                rule='recorded inputs, use and outputs of this piece for the one-day review; '
                     'reaching a prompt or record is not proof of consumption or learning; '
                     'missing evidence means unknown, never zero')


def text(context):
    check(context)
    return ('Shared market picture at the original explicit source cutoff (%s). ' % context['scope']['position']
            + context['use'] + '. ' + context['limit'] + '\n'
            + 'SCOPE: ' + json.dumps(context['scope'], sort_keys=True) + '\n'
            + 'READ: ' + json.dumps(context['read'], sort_keys=True) + '\n'
            + 'COVERAGE AT THIS INSTANT (explicit missing/stale/previously-known dispositions; nothing invented): '
            + json.dumps(context['coverage'], sort_keys=True, default=str) + '\n'
            + context['picture_text'])
