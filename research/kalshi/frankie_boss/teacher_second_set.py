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
            clock_lock_time                   not a picture element: stamped once at publication (the teacher's as_of)
          a clock with no carrier at this instant is listed in clocks_absent with its reason (never filled in)
  planes  every update the picture placed at this instant: (source, source_ordinal, input_cursor, instrument_id,
          known_at_ns, the 99 registry entries it carries), and every state row it carried (last_observed_state,
          active_instrument_state, published_state) as (source, source_ordinal); the invalidations; the picture's
          coverage (what is thinner at this instant and why)
  match   the picture's row identity against the teacher row's own fields (cursor, receive clock, member, session,
          instrument): each difference listed with both values, never aligned to the nearest

The plane VALUES are the ROOT's receipted rows themselves: each reference (source, source_ordinal) names one row of the
stream file pinned (path, bytes, sha256) in the second set's header, the very row the picture handed over. They are
referenced, not copied (a picture holds ~640 KB of layer values per APPLIED row on 20231018: a copy per teacher row
would be ~490 GB of duplicates of receipted rows).
"""

SCHEMA = 'FRANKIE_TEACHER_SECOND_SET_V1'
FORMAT = 1
KEY_FIELDS = ('adapter_cursor', 'input_cursor', 'input_journal_ordinal', 'source_input_index', 'source_member_index',
              'session_id', 'instrument_id', 'terminal_prefix_hash')
CLOCK_FIELDS = ('clock_event_time', 'clock_receive_time', 'clock_event_known_by', 'clock_feature_availability',
                'clock_prospective_discovery_confirmation', 'clock_model_evaluation', 'clock_lock_time')
PLANE_REFERENCE = ('source', 'source_ordinal', 'input_cursor', 'instrument_id', 'known_at_ns', 'entries')
STATE_REFERENCE = ('source', 'source_ordinal')


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
    absent['clock_lock_time'] = 'not a picture element: stamped at publication (the teacher\'s as_of)'
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
    return dict(key=key, clocks=clocks, clocks_absent=absent,
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
    a row without a record is listed as such."""
    out = dict(rows_total=len(rows), records=len(records), rows_matched=0, mismatches=[], rows_without_record=0,
               clocks_compared=0)
    for index, row in enumerate(rows):
        cursor, stamp, prefix = row[6], row[4], row[5]
        record = records[index] if index < len(records) else None
        if record is None:
            out['rows_without_record'] += 1
            if len(out['mismatches']) < 1000:
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
            out['mismatches'].extend(found[:max(0, 1000 - len(out['mismatches']))])
            out.setdefault('rows_mismatched', 0)
            out['rows_mismatched'] += 1
        else:
            out['rows_matched'] += 1
    out.setdefault('rows_mismatched', 0)
    return out
