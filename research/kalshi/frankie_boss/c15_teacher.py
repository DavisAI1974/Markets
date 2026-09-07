"""Current C15R2 teacher consumer of complete, verified journal evidence.

Target horizons/normalization are approved teacher definitions. They never
replace or prune native model evidence. B2/C1 slots remain explicitly ABLATED.
The caller owns source authority; ContextSessionRunner supplies verified journal
prefixes. This module neither authorizes phases nor launches a training run.
"""
from collections import defaultdict, deque
from dataclasses import asdict
import hashlib
import math
from pathlib import Path
import torch

try:
    from .c15_normalizer import CANDIDATE, COLUMNS, ABLATED_COLUMNS, State, Normalizer, IdentityNormalizer, NormalizedValue
    from .c15_dstate import DChain, DObservation
    from .c15_journal import evidence_hash
    from .dipole_target import DipoleTarget, DipoleTargetSpec
except ImportError:
    from c15_normalizer import CANDIDATE, COLUMNS, ABLATED_COLUMNS, State, Normalizer, IdentityNormalizer, NormalizedValue
    from c15_dstate import DChain, DObservation
    from c15_journal import evidence_hash
    from dipole_target import DipoleTarget, DipoleTargetSpec

K_SHORT,K_LONG,L_TOP=64,1024,3
IMB_EPS=.05


def value(v=0.,state=State.PRESENT,reason=''):
    if not math.isfinite(v):
        raise ValueError('nonfinite teacher value')
    return dict(value=float(v) if state==State.PRESENT else 0.,state=int(state),reason=reason)


def candidate_payload(ticks):
    here=Path(__file__).parent
    contracts=('parallel_r3_contracts/CLAUDE_C15_TARGET_SEMANTICS_PROPOSAL_R2_20260904.md',
               'parallel_r3_contracts/CLAUDE_BOSS_CONTRACT_ADDENDUM_R3_20260907.md',
               'parallel_r3_contracts/CODEX_REPLY_TO_CLAUDE_C15_R2_REVIEW_20260907.md')
    return dict(candidate=CANDIDATE,columns=COLUMNS,ablated=tuple(sorted(ABLATED_COLUMNS)),
        tick_raw=sorted(ticks.items()),k_short=64,k_long=1024,l_top=3,imb_eps=IMB_EPS,
        equations={p:hashlib.sha256((here/p).read_bytes()).hexdigest() for p in contracts})


class JournalTeacher:
    def __init__(self,tick_raw,*,normalizer):
        if (not tick_raw or any(type(k) is not int or k<1 or
                (v is not None and (type(v) is not int or v<1)) for k,v in tick_raw.items())):
            raise ValueError('declare per-instrument positive tick_raw or explicit unknown')
        if set(tick_raw)!=set(normalizer.config.instrument_ids):
            raise ValueError('teacher and normalizer instrument universes differ')
        self.ticks=dict(tick_raw)
        self.normalizer=normalizer
        self.candidate_digest=evidence_hash(candidate_payload(self.ticks))

    @property
    def binding(self):
        return evidence_hash(dict(candidate=self.candidate_digest,initial_normalizer=self.normalizer.export(),
            code={name:Path(__file__).with_name(name).read_bytes() for name in
                  ('c15_teacher.py','c15_normalizer.py','c15_dstate.py','c15_observer.py','c15_builder.py')}))

    def _normalizer_copy(self):
        if isinstance(self.normalizer,IdentityNormalizer):
            return IdentityNormalizer(self.normalizer.config.instrument_ids)
        return Normalizer.restore(self.normalizer.config,self.normalizer.export(),self.normalizer.state_hash)

    def attach(self,evidence,context,*,as_of,source_manifest_hash):
        """Reconstruct causal teacher state from all prefix rows, then align context.

        The supplied normalizer is an immutable initial phase checkpoint. Every
        attachment starts from it; retries cannot double-fit observations.
        Only UPDATING consumes new target statistics. Frozen phases stay frozen.
        """
        normalizer=self._normalizer_copy()
        groups=defaultdict(lambda:deque(maxlen=K_LONG))
        pending=defaultdict(list); machines={}; origins={}; ordinal=defaultdict(int)
        wanted={e['cursor'] for e in context}; selected={}; processed=0; last=None; last_recv=-1
        for e in evidence:
            if e['cursor']!=processed:
                raise ValueError('teacher prefix must account for every source cursor from zero')
            processed+=1; last=e
            m=e['normalized']; iid=m['instrument_id']; key=(m['publisher_id'],iid)
            if iid not in self.ticks:
                raise ValueError('teacher encountered instrument outside declared universe')
            if m['ts_recv_ns']>as_of:
                raise ValueError('future teacher evidence')
            if m['ts_recv_ns']<last_recv:
                raise ValueError('receive-time regression: cannot attach an earlier-stamped teacher target to later evidence')
            last_recv=m['ts_recv_ns']
            oid=(key,m['order_id']); effect=e['effect']
            if m['action']=='R':
                origins={k:v for k,v in origins.items() if k[0]!=key}
            if e['order_after'] is not None:
                if m['action']=='A' or oid not in origins:
                    origins[oid]=(m['action']=='A' and not m['is_snapshot'] and not effect['missing_reference'])
            else:
                origins.pop(oid,None)
            pending[key].append({k:e[k] for k in ('normalized','effect','order_before','order_after','rank_before','rank_after') if k in e})
            raw=[value(state=State.ABLATED,reason='UNBUILT_B2_C1') if c in ABLATED_COLUMNS else
                 value(state=State.MISSING,reason='NOT_F_LAST') for c in COLUMNS]
            if e['receipt'] is not None:
                group=pending.pop(key)
                groups[key].append(group)
                raw=self._columns(e,groups[key],origins,key,machines,ordinal[key])
                ordinal[key]+=1
                normalized=[normalizer.observe(iid,c,r['value'],State(r['state'])) for c,r in zip(COLUMNS,raw)]
            else:
                normalized=[NormalizedValue(r['value'],State(r['state'])) for r in raw]
            if e['cursor'] in wanted:
                selected[e['cursor']]=(raw,self._target(e,normalized,normalizer,source_manifest_hash),
                    normalizer.receipt() if isinstance(normalizer,Normalizer) else dict(normalizer_id=normalizer.normalizer_id))
        if last is None or len(selected)!=len(context):
            raise ValueError('teacher context rows missing from complete prefix')
        raw_rows=[selected[e['cursor']][0] for e in context]
        targets=tuple(selected[e['cursor']][1] for e in context)
        receipts=tuple(dict(cursor=e['cursor'],source_prefix_hash=e['terminal_prefix_hash'],
            target_hash=selected[e['cursor']][1].target_hash,
            normalizer=selected[e['cursor']][2]) for e in context)
        return dict(targets=targets,raw=raw_rows,processed_records=processed,
            context_cursors=tuple(e['cursor'] for e in context),step_receipts=receipts,
            attachment_hash=evidence_hash(receipts),candidate_digest=self.candidate_digest)

    def _target(self,e,normalized,normalizer,source_manifest_hash):
        code=Path(__file__).read_bytes()
        spec=DipoleTargetSpec(registry_id=f'boss/teacher/{CANDIDATE}:{self.candidate_digest}',
            target_names=COLUMNS,target_units=(('log_seconds','log_seconds','share','log_quantity','log_quantity','share','share',
                'share','share','share','share','share','share','log_groups','log_count','log_ratio',
                'log_ticks','log_groups','log_ticks') if isinstance(normalizer,IdentityNormalizer) else ('z_score',)*len(COLUMNS)),
            normalizer_id=normalizer.normalizer_id,
            builder_code_sha=hashlib.sha1(b'blob '+str(len(code)).encode()+b'\0'+code).hexdigest())
        now=e['normalized']['ts_recv_ns']
        return DipoleTarget(spec,source_manifest_hash,e['terminal_prefix_hash'],now,
            torch.tensor([[[v.value for v in normalized]]],dtype=torch.float32),
            torch.tensor([[[int(v.state) for v in normalized]]],dtype=torch.int8),
            torch.tensor([[now]],dtype=torch.int64))

    def _columns(self,e,history,origins,key,machines,ordinal):
        raw=[value(state=State.ABLATED,reason='UNBUILT_B2_C1') if c in ABLATED_COLUMNS else
             value(state=State.MISSING,reason='WINDOW_SHORT') for c in COLUMNS]
        window=list(history)
        anchor=None; reason='WINDOW_SHORT'
        unknown_flow=False
        if len(window)>=K_SHORT:
            trades=[x['normalized'] for g in window[-K_SHORT:] for x in g if x['normalized']['action']=='T']
            unknown_flow=any(x['side'] not in ('A','B') for x in trades)
            buy=sum(x['size'] for x in trades if x['side']=='B')
            sell=sum(x['size'] for x in trades if x['side']=='A')
            reason='NO_FLOW' if buy+sell==0 else 'SIDE_UNDEFINED'
            # Compare integer arithmetic; no normalization of raw model input.
            if not unknown_flow and buy+sell and abs(buy-sell)*20>buy+sell:
                anchor=1 if buy>sell else -1
        obs=e['observation']; side='A' if anchor==1 else 'B'
        levels=obs['levels'][side] if anchor is not None else []
        orders={o['order_id']:o for o in obs['orders']}
        cohort=[orders[oid] for level in levels[:L_TOP] for oid in level['order_ids']]
        crossed=(obs['levels']['A'] and obs['levels']['B'] and
                 obs['levels']['B'][0]['price_raw']>=obs['levels']['A'][0]['price_raw'])
        healthy=not any(obs['integrity'].values()) and not crossed
        if unknown_flow:
            for i in (0,1,2,3,4,5,6): raw[i]=value(state=State.INVALID,reason='UNKNOWN_SIDE')
        elif anchor is None:
            for i in (0,1,2,3,4,5,6): raw[i]=value(state=State.MISSING,reason=reason)
        elif not healthy:
            for i in (0,1,2,3,4,5,6): raw[i]=value(state=State.INVALID,reason='LEVEL_INTEGRITY')
        elif not cohort:
            for i in (0,1,2): raw[i]=value(state=State.MISSING,reason='LEVEL_EMPTY')
        else:
            now=e['normalized']['ts_recv_ns']; total=sum(o['size'] for o in cohort)
            front=cohort[0]
            raw[0]=(value(math.log1p(max(0,(now-front['priority_recv_ns'])/1e9)))
                    if origins.get((key,front['order_id']),False) else value(state=State.INVALID,reason='LEFT_CENSORED'))
            if not all(origins.get((key,o['order_id']),False) for o in cohort):
                raw[1]=value(state=State.INVALID,reason='LEFT_CENSORED')
            elif total<=0:
                raw[1]=value(state=State.INVALID,reason='LEVEL_INTEGRITY')
            else:
                cumulative=0
                for order in sorted(cohort,key=lambda o:now-o['priority_recv_ns']):
                    cumulative+=order['size']
                    if cumulative*10>=9*total:
                        raw[1]=value(math.log1p(max(0,(now-order['priority_recv_ns'])/1e9))); break
            raw[2]=value(sum((o['size']/total)**2 for o in cohort)) if total>0 else value(state=State.INVALID,reason='LEVEL_INTEGRITY')
        if anchor is not None and healthy:
            for k,bi,mi in ((64,3,5),(1024,4,6)):
                if len(window)>=k:
                    raw[bi],raw[mi]=self._dynamics(window[-k:],side)
        machine=machines.setdefault(key,DChain(tick_raw=self.ticks[key[1]]))
        dout=machine.advance_synthetic(DObservation(ordinal,e['source_member_index'],e['session_id'],
            anchor,levels[0]['price_raw'] if levels else None,bool(healthy)))
        for i,d in enumerate(dout.columns,13):
            raw[i]=value(state=State.INVALID,reason='UNKNOWN_SIDE') if unknown_flow else value(d.value,State[d.state],d.reason or '')
        return raw

    @staticmethod
    def _dynamics(groups,side):
        added=removed=modifies=lost=0
        for group in groups:
            pending_fills={}
            for e in group:
                m=e['normalized']; effect=e['effect']; before=e['order_before']; after=e['order_after']
                if effect['missing_reference'] or m['action']=='R' or (m['action']=='A' and effect['removed']):
                    bad=value(state=State.INVALID,reason='MISSING_REFERENCE_OR_RESET'); return bad,bad
                if m['action']=='N': continue
                if m['side'] not in ('A','B'):
                    bad=value(state=State.INVALID,reason='UNKNOWN_SIDE'); return bad,bad
                oid=m['order_id']
                if m['action']=='T': continue
                if m['action']=='F':
                    if before is None:
                        bad=value(state=State.INVALID,reason='MISSING_REFERENCE'); return bad,bad
                    pending_fills[oid]=pending_fills.get(oid,0)+m['size']
                    continue
                if oid in pending_fills:
                    economic_removed=(before['size'] if before else 0)-(after['size'] if after else 0)
                    if (m['action'] not in ('C','M') or before is None
                            or (after is not None and (before['price_raw'],before['side']) != (after['price_raw'],after['side']))
                            or economic_removed != pending_fills[oid]):
                        bad=value(state=State.INVALID,reason='UNRECONCILED_FILL'); return bad,bad
                    del pending_fills[oid]
                if 'rank_before' not in e or 'rank_after' not in e:
                    bad=value(state=State.INVALID,reason='RANK_UNAVAILABLE'); return bad,bad
                old_in=before is not None and before['side']==side and e['rank_before'] is not None and e['rank_before']<=L_TOP
                new_in=after is not None and after['side']==side and e['rank_after'] is not None and e['rank_after']<=L_TOP
                if m['action']=='M' and old_in:
                    modifies+=1; lost+=int(effect['priority_lost'])
                old=before['size'] if old_in else 0; new=after['size'] if new_in else 0
                # Crossing the teacher boundary counts removal/addition once;
                # within it, quantity change counts once, including matched C/M.
                delta=new-old
                added+=max(0,delta); removed+=max(0,-delta)
            if pending_fills:
                bad=value(state=State.INVALID,reason='UNRECONCILED_FILL'); return bad,bad
        return value(math.log1p(added)-math.log1p(removed)), (value(lost/modifies) if modifies else value(state=State.MISSING,reason='NO_MODIFIES'))
