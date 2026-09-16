"""Additive raw C15R3 six-column teacher; caller verifies journal authority.

Raw and governed normalized attachment; no training, provider access or changes
to the C15R2 control.
See SPEC-c15-teacher-r3.md for the approved equation sources and scope.
"""
from collections import defaultdict, deque
import hashlib
from pathlib import Path

try:
    from .c15_normalizer import COLUMNS as CONTROL_COLUMNS, State
    from .c15_teacher import JournalTeacher
    from .c15_journal import evidence_hash
except ImportError:
    from c15_normalizer import COLUMNS as CONTROL_COLUMNS, State
    from c15_teacher import JournalTeacher
    from c15_journal import evidence_hash

CANDIDATE = 'BOSS_TEACHER_CANDIDATE_C15R3'
COLUMNS = CONTROL_COLUMNS[7:13]


def _value(value=0., state=State.PRESENT, reason=''):
    return dict(value=float(value) if state == State.PRESENT else 0.,
                state=int(state), mask=int(state == State.PRESENT), reason=reason)


def _missing(reason):
    return _value(state=State.MISSING, reason=reason)


def _invalid(reason):
    return _value(state=State.INVALID, reason=reason)


def _anchor(groups):
    if len(groups) < 64:
        return None, _missing('WINDOW_SHORT')
    trades = [e['normalized'] for g in groups[-64:] for e in g
              if e['normalized']['action'] == 'T']
    if any(m['side'] not in ('A', 'B') for m in trades):
        return None, _invalid('UNKNOWN_SIDE')
    buy = sum(m['size'] for m in trades if m['side'] == 'B')
    sell = sum(m['size'] for m in trades if m['side'] == 'A')
    if not buy + sell:
        return None, _missing('NO_FLOW')
    if abs(buy-sell)*20 <= buy+sell:
        return None, _missing('SIDE_UNDEFINED')
    return ('A' if buy > sell else 'B'), None


def _absorption(groups, side):
    # Share the immutable control's approved reconciliation/integrity checks.
    dynamics, _ = JournalTeacher._dynamics(groups, side)
    if dynamics['state'] == int(State.INVALID):
        return _invalid(dynamics['reason'])
    removed = fills = 0
    for group in groups:
        pending = {}
        for e in group:
            m = e['normalized']
            action, oid = m['action'], m['order_id']
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if action in ('T', 'N'):
                continue
            before, after = e['order_before'], e['order_after']
            old_in = (before is not None and before['side'] == side
                      and e['rank_before'] is not None and e['rank_before'] <= 3)
            new_in = (after is not None and after['side'] == side
                      and e['rank_after'] is not None and e['rank_after'] <= 3)
            old = before['size'] if old_in else 0
            new = after['size'] if new_in else 0
            removed += max(0, old-new)
            matched = pending.pop(oid, 0)
            if old_in:
                fills += matched
    if not removed:
        return _missing('NO_REMOVALS')
    if not 0 <= fills <= removed:
        return _invalid('UNRECONCILED_FILL')
    return _value(fills/removed)


def _cohort(start, groups, side):
    observation = start['observation']
    orders = {o['order_id']: o for o in observation['orders']}
    cohort = {oid: orders[oid]['size'] for level in observation['levels'][side][:3]
              for oid in level['order_ids']}
    scope = start['source_member_index'], start['session_id']
    alive = set(cohort)
    current = dict(cohort)
    for group in groups:
        pending = {}
        for e in group:
            m, effect = e['normalized'], e['effect']
            oid, action = m['order_id'], m['action']
            if (e['source_member_index'], e['session_id']) != scope:
                return (_invalid('SCOPE_BOUNDARY'),)*2
            if action == 'R':
                return (_invalid('RESET'),)*2
            if oid not in alive:
                continue
            if effect['missing_reference'] or (action == 'A' and effect['removed']):
                return (_invalid('MISSING_REFERENCE'),)*2
            if action == 'F':
                pending[oid] = pending.get(oid, 0) + m['size']
                continue
            if oid in pending:
                before, after = e['order_before'], e['order_after']
                if (action not in ('C', 'M') or before is None
                        or (after is not None and (before['price_raw'], before['side'])
                            != (after['price_raw'], after['side']))
                        or before['size']-(after['size'] if after else 0) != pending.pop(oid)):
                    return (_invalid('UNRECONCILED_FILL'),)*2
            if action in ('C', 'M'):
                after = e['order_after']
                if action == 'C' or after is None or after['size'] == 0:
                    alive.remove(oid)
                    current[oid] = 0
                else:
                    current[oid] = after['size']
        if pending:
            return (_invalid('UNRECONCILED_FILL'),)*2
    total = sum(cohort.values())
    if not total:
        return (_missing('COHORT_EMPTY'),)*2
    return (_value(sum(cohort[oid] for oid in alive)/total),
            _value(sum(min(size, current[oid]) for oid, size in cohort.items())/total))


def _history_row(e):
    """Equation-specific history view; full original evidence is hashed first.

    Both top-three FIFO cohorts retain every member and its complete order
    fields. Full-depth observations remain in the source journal and are not
    replaced by this temporary view used only for the defined teacher horizons.
    """
    result={key:e[key] for key in ('normalized','effect','order_before','order_after',
        'rank_before','rank_after','source_member_index','session_id') if key in e}
    if e['observation'] is not None:
        observation=e['observation']
        levels={side:observation['levels'][side][:3] for side in ('A','B')}
        ids={oid for side in levels.values() for level in side for oid in level['order_ids']}
        result['observation']=dict(levels=levels,orders=[o for o in observation['orders'] if o['order_id'] in ids],
            integrity=observation['integrity'])
    else:
        result['observation']=None
    return result


class _OneRowInput:
    """Lockstep source for a raw iterator; never buffers a previous full row."""
    def __init__(self):
        self.row=None
        self.closed=False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        if self.row is None:
            raise ValueError('raw teacher requested more than one source row')
        row,self.row=self.row,None
        return row


def _paired_raw(control_teacher,raw_teacher,evidence,*,as_of,source_manifest_hash):
    left,right=_OneRowInput(),_OneRowInput()
    control=control_teacher.iter_raw(left,as_of=as_of)
    raw=raw_teacher.iter_raw(right,as_of=as_of,source_manifest_hash=source_manifest_hash)
    for e in evidence:
        left.row=right.row=e
        old,six=next(control),next(raw)
        if left.row is not None or right.row is not None or old[0] is not e or six[0] is not e:
            raise ValueError('raw teacher streams lost exact source alignment')
        yield e,old[1],six[1]
    left.closed=right.closed=True
    if next(control,None) is not None or next(raw,None) is not None:
        raise ValueError('raw teacher emitted an extra source row')


class RawJournalTeacherR3:
    """Reconstruct all six shares from a caller-verified complete source prefix.

    Expected prefix and manifest identities come from the caller's trusted
    receipt; this consumer does not itself grant result-bearing source authority.
    Returned dictionaries are newly owned and retain no aliases to source rows.
    """

    @property
    def candidate_digest(self):
        here = Path(__file__).parent
        files = ('c15_teacher_r3.py', 'c15_normalizer_r3.py', 'SPEC-c15-teacher-r3.md', 'c15_teacher.py',
                 'c15_normalizer.py',
                 'parallel_r3_contracts/CLAUDE_C15_TARGET_SEMANTICS_PROPOSAL_R2_20260904.md',
                 'parallel_r3_contracts/CODEX_REPLY_TO_CLAUDE_C15_R2_REVIEW_20260907.md')
        return evidence_hash(dict(candidate=CANDIDATE, columns=COLUMNS,
            horizons=(64, 1024), top_levels=3, imbalance_epsilon='.05',
            code={name: hashlib.sha256((here/name).read_bytes()).hexdigest() for name in files}))

    def iter_raw(self, evidence, *, as_of, source_manifest_hash):
        """Stream all six-column rows while retaining only defined group history."""
        if type(as_of) is not int or as_of < 0:
            raise ValueError('nonnegative as_of required')
        for identity in (source_manifest_hash,):
            if (type(identity) is not str or len(identity) != 64
                    or any(c not in '0123456789abcdef' for c in identity)):
                raise ValueError('declare source and expected prefix hashes')
        candidate = self.candidate_digest
        history = defaultdict(lambda: deque(maxlen=1025))
        pending = defaultdict(list)
        publishers = {}
        content = evidence_hash(dict(candidate=candidate, source=source_manifest_hash))
        last_recv = -1
        for cursor, e in enumerate(evidence):
            if type(e['cursor']) is not int or e['cursor'] != cursor:
                raise ValueError('complete prefix requires every cursor from zero')
            m = e['normalized']
            previous_publisher = publishers.setdefault(m['instrument_id'], m['publisher_id'])
            if previous_publisher != m['publisher_id']:
                raise ValueError('unresolvable publisher scope in instrument-owned book')
            if m['ts_recv_ns'] > as_of:
                raise ValueError('future teacher evidence')
            if m['ts_recv_ns'] < last_recv:
                raise ValueError('receive-time regression')
            last_recv = m['ts_recv_ns']
            content = evidence_hash(dict(previous=content, evidence=e))
            key = m['publisher_id'], m['instrument_id']
            pending[key].append(_history_row(e))
            values = [_missing('NOT_F_LAST') for _ in COLUMNS]
            if e['receipt'] is not None:
                history[key].append(pending.pop(key))
                groups = list(history[key])
                side, missing = _anchor(groups)
                obs = e['observation']
                crossed = (obs['levels']['A'] and obs['levels']['B'] and
                    obs['levels']['B'][0]['price_raw'] >= obs['levels']['A'][0]['price_raw'])
                if missing is None and (any(obs['integrity'].values()) or crossed):
                    missing = _invalid('LEVEL_INTEGRITY')
                if missing is not None:
                    values = [dict(missing) for _ in COLUMNS]
                else:
                    for index, horizon in enumerate((64, 1024)):
                        values[index] = (_absorption(groups[-horizon:], side)
                            if len(groups) >= horizon else _missing('WINDOW_SHORT'))
                        pair = (_cohort(groups[-horizon-1][-1], groups[-horizon:], side)
                            if len(groups) > horizon else (_missing('WINDOW_SHORT'),)*2)
                        values[2+index], values[4+index] = pair
            yield e,dict(cursor=cursor, source_prefix_hash=e['terminal_prefix_hash'],
                as_of_ts_recv_ns=last_recv, evidence_content_hash=content, columns=values)

    def attach(self, evidence, *, context_cursors, as_of, source_manifest_hash,
               expected_prefix_hash):
        if (type(context_cursors) is not tuple or not context_cursors
                or any(type(c) is not int or c < 0 for c in context_cursors)
                or tuple(sorted(set(context_cursors))) != context_cursors):
            raise ValueError('declare ordered unique context cursors and nonnegative as_of')
        if (type(expected_prefix_hash) is not str or len(expected_prefix_hash)!=64
                or any(c not in '0123456789abcdef' for c in expected_prefix_hash)):
            raise ValueError('declare source and expected prefix hashes')
        wanted=set(context_cursors);rows=[];last=None;count=0
        for last,row in self.iter_raw(evidence,as_of=as_of,source_manifest_hash=source_manifest_hash):
            count+=1
            if row['cursor'] in wanted: rows.append(row)
        if last is None or last['terminal_prefix_hash'] != expected_prefix_hash:
            raise ValueError('terminal prefix mismatch')
        if len(rows) != len(context_cursors):
            raise ValueError('context cursor absent from prefix')
        result = dict(candidate=CANDIDATE, candidate_digest=self.candidate_digest, target_names=COLUMNS,
            source_manifest_hash=source_manifest_hash, terminal_prefix_hash=expected_prefix_hash,
            processed_records=count, rows=rows, normalization='RAW_SHARE')
        return dict(result, attachment_hash=evidence_hash(result))


class JournalTeacherR3:
    """Governed full-width R3 attachment, selected explicitly by the caller.

    Both raw consumers reconstruct the complete verified prefix. Their outputs
    are normalized only after combination, using an initial-checkpoint copy.
    Existing R2 target bytes and registry remain independently reproducible.
    """
    def __init__(self, tick_raw, *, normalizer):
        try:
            from .c15_normalizer import IdentityNormalizer
            from .c15_normalizer_r3 import NormalizerR3, IdentityNormalizerR3
        except ImportError:
            from c15_normalizer import IdentityNormalizer
            from c15_normalizer_r3 import NormalizerR3, IdentityNormalizerR3
        if type(normalizer) not in (NormalizerR3, IdentityNormalizerR3):
            raise ValueError('explicit R3 normalizer required')
        self.control = JournalTeacher(tick_raw,
            normalizer=IdentityNormalizer(normalizer.config.instrument_ids))
        self.normalizer = normalizer
        self.raw_teacher = RawJournalTeacherR3()
        self.candidate_digest = evidence_hash(dict(raw=self.raw_teacher.candidate_digest,
            control=self.control.candidate_digest, columns=CONTROL_COLUMNS))

    @property
    def binding(self):
        return evidence_hash(dict(candidate=self.candidate_digest,
            control=self.control.binding, normalizer=self.normalizer.export(),
            code={name:Path(__file__).with_name(name).read_bytes() for name in
                  ('c15_teacher_r3.py','c15_normalizer_r3.py')}))

    def attach(self, evidence, context, *, as_of, source_manifest_hash):
        import torch
        try:
            from .c15_normalizer_r3 import NormalizerR3, IdentityNormalizerR3
            from .c15_normalizer import NormalizedValue
            from .dipole_target import DipoleTarget, DipoleTargetSpec
        except ImportError:
            from c15_normalizer_r3 import NormalizerR3, IdentityNormalizerR3
            from c15_normalizer import NormalizedValue
            from dipole_target import DipoleTarget, DipoleTargetSpec
        context = list(context)
        if type(as_of) is not int or as_of<0:
            raise ValueError('nonnegative as_of required')
        if not context:
            raise ValueError('nonempty complete prefix and context required')
        selected = tuple(e['cursor'] for e in context)
        if (any(type(cursor) is not int or cursor<0 for cursor in selected)
                or tuple(sorted(set(selected))) != selected):
            raise ValueError('ordered unique context cursors required')
        session_fields = {'cursor','raw_record','normalized','source_member_index',
                          'session_id','integrity','terminal_prefix_hash'}
        selected_rows={item['cursor']:item for item in context}
        identity = isinstance(self.normalizer, IdentityNormalizerR3)
        normalizer = (IdentityNormalizerR3(self.normalizer.config.instrument_ids) if identity else
            NormalizerR3.restore(self.normalizer.config, self.normalizer.export(), self.normalizer.state_hash))
        code = Path(__file__).read_bytes()
        builder_sha = hashlib.sha1(b'blob '+str(len(code)).encode()+b'\0'+code).hexdigest()
        units = ('log_seconds','log_seconds','share','log_quantity','log_quantity','share','share',
                 'share','share','share','share','share','share','log_groups','log_count','log_ratio',
                 'log_ticks','log_groups','log_ticks') if identity else ('z_score',)*19
        wanted = set(selected)
        targets, raw_rows, receipts = [], [], []
        processed=0
        for e,old,six in _paired_raw(self.control,self.raw_teacher,evidence,
                as_of=as_of,source_manifest_hash=source_manifest_hash):
            processed+=1
            if e['cursor'] in wanted:
                item=selected_rows[e['cursor']]
                if (set(item) not in (session_fields,set(e))
                        or evidence_hash(item)!=evidence_hash({k:e[k] for k in item})):
                    raise ValueError('context must match exact verified prefix row')
            combined = [dict(v) for v in old]
            combined[7:13] = [{k: v[k] for k in ('value','state','reason')} for v in six['columns']]
            iid = e['normalized']['instrument_id']
            normalized = ([normalizer.observe(iid,c,v['value'],State(v['state']))
                for c,v in zip(CONTROL_COLUMNS,combined)] if e['receipt'] is not None else
                [NormalizedValue(v['value'],State(v['state'])) for v in combined])
            if e['cursor'] not in wanted:
                continue
            now = e['normalized']['ts_recv_ns']
            spec = DipoleTargetSpec(registry_id=f'boss/teacher/{CANDIDATE}:{self.candidate_digest}',
                target_names=CONTROL_COLUMNS, target_units=units,
                normalizer_id=normalizer.normalizer_id, builder_code_sha=builder_sha)
            target = DipoleTarget(spec, source_manifest_hash,e['terminal_prefix_hash'],now,
                torch.tensor([[[v.value for v in normalized]]],dtype=torch.float32),
                torch.tensor([[[int(v.state) for v in normalized]]],dtype=torch.int8),
                torch.tensor([[now]],dtype=torch.int64))
            receipt = dict(cursor=e['cursor'],source_prefix_hash=e['terminal_prefix_hash'],
                evidence_content_hash=six['evidence_content_hash'], target_hash=target.target_hash,
                normalizer=(normalizer.export() if identity else normalizer.receipt()))
            targets.append(target)
            raw_rows.append(combined)
            receipts.append(receipt)
        if not processed or len(targets)!=len(context):
            raise ValueError('context cursor absent from complete prefix')
        return dict(targets=tuple(targets),raw=raw_rows,processed_records=processed,
            context_cursors=selected,step_receipts=tuple(receipts),
            attachment_hash=evidence_hash(receipts),candidate_digest=self.candidate_digest)
