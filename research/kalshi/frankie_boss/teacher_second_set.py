"""The teacher's second set: every teacher row joined to the picture row of the 99 planes it was read with.

Greg (2026-10-09): "The teacher is supposed to be reading all of Frankie's 99 planes pinned together that are streamed
to him and building a second set"; whatever Frankie sees is pinned together with the 99 planes on the same clocks.

The shared market timeline (frankie_box_market_timeline.SharedMarketTimeline.iter_applied) hands the teacher's walk one
picture per instant, and the teacher's row IS that instant's original APPLIED payload (picture['original_applied'] is
the very object the walk yields). So the join is exact by construction, not by search: the teacher row of adapter
cursor c is the picture whose at.adapter_cursor == c, read in the same step. join_record() takes, from that picture and
never recomputed:

  key     adapter_cursor (= the teacher row's cursor), input_cursor, input_journal_ordinal, source_input_index,
          source_member_index, session_id, instrument_id, and the teacher row's terminal_prefix_hash
  clocks  the seven causal clocks, each exactly as the picture carries it:
            clock_event_time                  at.ts_event_ns (and at.raw_event_clock)
            clock_receive_time                at.ts_recv_ns (and at.raw_receive_clock)
            clock_event_known_by              at.publication_frontier_ns
            clock_feature_availability        every update's (source, source_ordinal, known_at_ns, availability_basis)
            clock_prospective_discovery_confirmation   every native.lifecycle update's emission record
            clock_model_evaluation            every native.member update's clocks record
            clock_lock_time                   not a picture element: the TEACHER's as_of, labelled
                                              'teacher_as_of (lock time does not exist before Frankie reads)'
          a clock with no carrier at this instant is listed in clocks_absent with its reason (never filled in)
  planes  every update the picture placed at this instant: (source, source_ordinal, input_cursor, instrument_id,
          known_at_ns, the 99 registry entries it carries), and every state row it carried (last_observed_state,
          active_instrument_state, published_state) as (source, source_ordinal); the invalidations; the picture's
          coverage (what is thinner at this instant and why)
  match   the picture's row identity against the teacher row's own fields (cursor, receive clock, member, session,
          instrument): each difference listed with both values, never aligned to the nearest

  book    (attached at publication, FORMAT 2) the book read beside the pinned functions on the same full rows
          (teacher_book_read): the group the row closes (both sides, every level: book vs event counts and their
          reconciliation, the full depth, every event's level/queue/depth-beyond before and after) and each window
          the pinned R3 called on the row (64 groups; 1,024 on the pinned R3; the whole day with the teacher
          changes) with the book counterparts of the pinned balance and absorption; a row that closes no group reads
          NOT_F_LAST, a receipt row with no window carries the pinned R3's own reason

The plane VALUES are the ROOT's receipted rows themselves: each reference (source, source_ordinal) names one row of the
stream file pinned (path, bytes, sha256) in the second set's header, the very row the picture handed over. They are
referenced, not copied (a picture holds ~640 KB of layer values per APPLIED row on 20231018: a copy per teacher row
would be ~490 GB of duplicates of receipted rows).
"""

SCHEMA = 'FRANKIE_TEACHER_SECOND_SET_V1'
FORMAT = 3
KEY_FIELDS = ('adapter_cursor', 'input_cursor', 'input_journal_ordinal', 'source_input_index', 'source_member_index',
              'session_id', 'instrument_id', 'terminal_prefix_hash')
CLOCK_FIELDS = ('clock_event_time', 'clock_receive_time', 'clock_event_known_by', 'clock_feature_availability',
                'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time')
# clock_lock_time on a teacher row is the TEACHER's as_of, never Frankie's lock (Greg, 2026-10-09)
LOCK_LABEL = 'teacher_as_of (lock time does not exist before Frankie reads)'
PLANE_REFERENCE = ('source', 'source_ordinal', 'input_cursor', 'instrument_id', 'known_at_ns', 'entries')
STATE_REFERENCE = ('source', 'source_ordinal')


# The state labels the streamed planes carry at an instant (Greg, 2026-10-09: the pinned measures split by the bedrock
# state present at that moment). The label fields are the label-valued fields of each plane as the 20231018 probe
# (frankie_box_probe_picture_fields.py) showed them, every one; a native lifecycle section the probe did not reach
# (episode, candidate, lineage, ...) takes every top-level text or true/false field (its own values, nothing renamed).
# Plane names: root.structures, native.member, native.lifecycle:<emitting_section>. Several rows of one plane at an
# instant give the tuple of their values in row order. The values are the planes' own; nothing is binned or renamed.
STATE_LABEL_FIELDS = {
    'root.structures': ('discovery_status', 'candidate_family_id', 'carried_native_family',
                        'matches_carried_native_family', 'fill_disposition.class', 'mirror.orientation',
                        'terminal_action', 'terminal_side'),
    'native.member': ('session_phase', 'side_orientation', 'family_id', 'decision_basis', 'continuity_segment',
                      'snapshot_bootstrap_only', 'event_group_complete_f_last', 'sequence_contiguous',
                      'fifo_priority_reconstructed'),
    'native.lifecycle:mirror': ('disposition', 'orientation'),
    'native.lifecycle:ladder': ('ladder_scope', 'side', 'touch_state', 'best_price_moved'),
    'native.lifecycle:absorption': ('price_moved',),
    'native.lifecycle:flow_substrate': ('classification', 'window_direction', 'status', 'no_direction_reason',
                                        'roll20_defined', 'polarity'),
    'native.lifecycle:replenishment': ('action', 'liquidity_kind', 'liquidity_kind_basis', 'observation',
                                       'unattributed_reason', 'price_is_sentinel'),
    'native.lifecycle:queue': ('terminal_status', 'birth_session_phase', 'exit_session_phase', 'queue_scope',
                               'stratum_basis', 'terminal_basis', 'resolved', 'censored', 'exit_stratum_available',
                               'birth_family_id', 'exit_family_id'),
    'native.lifecycle:recurrence': (),          # lists only (runs[].node, gaps[].from_node): no scalar label
    'native.lifecycle:detector_coverage': (),   # counts and ratios only
}
# never a state label in the generic rule: identities and keys unique per event, clocks, and the row's own section name
GENERIC_EXCLUDED = ('member_id', 'runway_id', 'mirror_pair_key', 'level_event_key_at_exit', 'action_string',
                    'side_string', 'schema', 'clock', 'binning_clock', 'emitted_on', 'emitting_section')
LABEL_SOURCES = ('root.structures', 'native.member', 'native.lifecycle')


def _field(value, path):
    for part in path.split('.'):
        if not isinstance(value, dict) or part not in value:
            return False, None
        value = value[part]
    return True, value


def state_labels(picture):
    """({'plane|field': value (or the tuple of the values of several rows, in row order)}, {plane: 'placed'|'carried'})
    from the plane rows the picture placed at this instant, and, for a state plane with no row placed here, from its
    last observed row for the instrument (the state present at that moment)."""
    rows, origin = {}, {}
    for where, carried in (('updates', False), ('active_instrument_state', True)):
        for update in picture.get(where) or ():
            source = update.get('source') if isinstance(update, dict) else None
            value = update.get('value') if isinstance(update, dict) else None
            if source not in LABEL_SOURCES or not isinstance(value, dict):
                continue
            plane = ('native.lifecycle:%s' % value.get('emitting_section') if source == 'native.lifecycle' else source)
            if carried and origin.get(plane) == 'placed':
                continue
            origin.setdefault(plane, 'carried' if carried else 'placed')
            rows.setdefault(plane, []).append(value)
    labels = {}
    for plane, values in rows.items():
        names = STATE_LABEL_FIELDS.get(plane)
        if names is None:
            names = sorted({name for value in values for name, item in value.items()
                            if type(item) in (str, bool) and name not in GENERIC_EXCLUDED})
        for name in names:
            found = [_field(value, name) for value in values]
            if not any(present for present, _ in found):
                continue
            items = tuple(item for present, item in found if present)
            labels['%s|%s' % (plane, name)] = items[0] if len(items) == 1 else items
    return labels, origin


def _ref(update):
    return (update.get('source'), update.get('source_ordinal'), update.get('input_cursor'), update.get('instrument_id'),
            update.get('known_at_ns'), tuple(update.get('entries') or ()))


def _state(rows):
    return tuple((row.get('source'), row.get('source_ordinal')) for row in rows or () if isinstance(row, dict))


def join_record(evidence, picture):
    """The second-set record of one teacher row (its APPLIED payload) and the picture it was read with."""
    at = picture.get('at') or {}
    updates = [u for u in picture.get('updates') or () if isinstance(u, dict)]
    normalized = evidence.get('normalized') or {}
    lifecycle = tuple((u.get('source_ordinal'), (u.get('value') or {}).get('frankie_emission'),
                       (u.get('value') or {}).get('emitted_at_recv_ns'))
                      for u in updates if u.get('source') == 'native.lifecycle')
    member = tuple((u.get('source_ordinal'), (u.get('value') or {}).get('clocks'))
                   for u in updates if u.get('source') == 'native.member')
    clocks = dict(
        clock_event_time=dict(ts_event_ns=at.get('ts_event_ns'), raw_event_clock=at.get('raw_event_clock')),
        clock_receive_time=dict(ts_recv_ns=at.get('ts_recv_ns'), raw_receive_clock=at.get('raw_receive_clock')),
        clock_event_known_by=at.get('publication_frontier_ns'),
        clock_feature_availability=tuple((u.get('source'), u.get('source_ordinal'), u.get('known_at_ns'),
                                          u.get('availability_basis')) for u in updates),
        clock_prospective_discovery_confirmation=lifecycle,
        clock_model_evaluation=member,
        clock_lock_time=None)
    absent = {}
    if not updates:
        absent['clock_feature_availability'] = 'no layer update was placed at this instant'
    if not lifecycle:
        absent['clock_prospective_discovery_confirmation'] = 'no native.lifecycle row was placed at this instant'
    if not member:
        absent['clock_model_evaluation'] = 'no native.member row was placed at this instant'
    absent['clock_lock_time'] = LOCK_LABEL + ': not a picture element; the teacher\'s as_of is stamped at publication'
    key = dict(adapter_cursor=at.get('adapter_cursor'), input_cursor=at.get('input_cursor'),
               input_journal_ordinal=at.get('input_journal_ordinal'), source_input_index=at.get('source_input_index'),
               source_member_index=at.get('source_member_index'), session_id=at.get('session_id'),
               instrument_id=at.get('instrument_id'), terminal_prefix_hash=evidence.get('terminal_prefix_hash'))
    mismatches = []
    for name, pictured, own in (('adapter_cursor', at.get('adapter_cursor'), evidence.get('cursor')),
                                ('clock_receive_time', at.get('ts_recv_ns'), normalized.get('ts_recv_ns')),
                                ('source_member_index', at.get('source_member_index'), evidence.get('source_member_index')),
                                ('session_id', at.get('session_id'), evidence.get('session_id')),
                                ('instrument_id', at.get('instrument_id'), normalized.get('instrument_id'))):
        if pictured != own:
            mismatches.append((name, pictured, own))
    if picture.get('original_applied') is not evidence:
        mismatches.append(('original_applied', 'another object', 'the teacher row'))
    coverage = picture.get('coverage') or {}
    labels, label_origin = state_labels(picture)
    return dict(key=key, clocks=clocks, clocks_absent=absent, state_labels=labels, state_label_origin=label_origin,
                planes=tuple(_ref(u) for u in updates),
                state=dict(last_observed=_state(picture.get('last_observed_state')),
                           active_instrument=_state(picture.get('active_instrument_state')),
                           published=_state(picture.get('published_state'))),
                invalidated=tuple(picture.get('invalidated_state') or ()),
                coverage=dict(source_status=picture.get('source_status'), placement=coverage.get('placement'),
                              exact_clocks=coverage.get('exact_clocks'),
                              absent_layers=coverage.get('absent_layers'),
                              last_observed_state=coverage.get('last_observed_state'),
                              active_instrument_state=coverage.get('active_instrument_state')),
                match=dict(status='matched' if not mismatches else 'mismatch', mismatches=tuple(mismatches)))


def check_rows(records, rows):
    """Line the second set up with the teacher's rows (row tuples of parallel_teacher.row_pass: [4] receive clock,
    [5] terminal prefix hash, [6] cursor). Returns the counts and every mismatch (cursor, field, picture, teacher);
    a row without a record is listed as such. Every mismatch is kept."""
    out = dict(rows_total=len(rows), records=len(records), rows_matched=0, mismatches=[], rows_without_record=0,
               clocks_compared=0)
    for index, row in enumerate(rows):
        cursor, stamp, prefix = row[6], row[4], row[5]
        record = records[index] if index < len(records) else None
        if record is None:
            out['rows_without_record'] += 1
            out['mismatches'].append((cursor, 'no_picture_record', None, cursor))
            continue
        found = [(cursor,) + m for m in record['match']['mismatches']]
        key, clocks = record['key'], record['clocks']
        out['clocks_compared'] += 1
        for name, pictured, own in (('adapter_cursor', key['adapter_cursor'], cursor),
                                    ('clock_receive_time', clocks['clock_receive_time']['ts_recv_ns'], stamp),
                                    ('terminal_prefix_hash', key['terminal_prefix_hash'], prefix)):
            if pictured != own:
                found.append((cursor, name, pictured, own))
        if found:
            out['mismatches'].extend(found)                 # every one, never capped
            out.setdefault('rows_mismatched', 0)
            out['rows_mismatched'] += 1
        else:
            out['rows_matched'] += 1
    out.setdefault('rows_mismatched', 0)
    return out
