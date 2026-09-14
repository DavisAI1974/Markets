"""Single-writer synthetic execution outbox; no broker client or credential access."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, is_dataclass
from fractions import Fraction
import math
import os
from pathlib import Path
import threading
from typing import get_args, get_origin

from .c15_journal import EvidenceJournal, evidence_hash, pack, unpack
from .execution_contracts import (Contract, AccountKey, Intent, Policy, Registry,
    SourceReference, Valuation, MarketSnapshot, AccountSnapshot, Reservation, Exposure)
from .execution_policy import evaluate
from .forecast_contract import sha256_digest

SCHEMA='BOSS_EXECUTION_LEDGER_V1'


def _copy(value):
    return unpack(pack(value))


def _restore(kind,value):
    if get_origin(kind) is tuple:
        if type(value) is not tuple:
            raise ValueError('immutable stored sequence required')
        return tuple(_restore(get_args(kind)[0],v) for v in value)
    if is_dataclass(kind):
        if type(value) is not dict or set(value)!={f.name for f in fields(kind)}:
            raise ValueError('stored contract fields differ')
        return kind(**{f.name:_restore(f.type,value[f.name]) for f in fields(kind)})
    return value


_INPUT_TYPES=dict(intent=Intent,policy=Policy,registry=Registry,source=SourceReference,
    valuation=Valuation,market=MarketSnapshot,account=AccountSnapshot)


def _decode_inputs(value):
    if type(value) is not dict or set(value)!=set(_INPUT_TYPES)|{
        'expected_source_hash','expected_valuation_hash','reservations','now','loss_day','kill_switch'}:
        raise ValueError('exact evaluation inputs required')
    return {k:_restore(_INPUT_TYPES[k],v) if k in _INPUT_TYPES else
            _restore(tuple[Reservation,...],v) if k=='reservations' else v for k,v in value.items()}


@dataclass(frozen=True)
class WireRequest(Contract):
    intent_hash: str
    adapter_hash: str
    method: str
    path: str
    body: bytes
    client_id: str

    def __post_init__(self):
        super().__post_init__()
        if self.method != 'POST' or not self.path.startswith('/') or '://' in self.path:
            raise ValueError('explicit relative submission route required')


@dataclass(frozen=True)
class Observation(Contract):
    observation_id: str
    intent_id: str
    intent_hash: str
    account: AccountKey
    provider_id: str
    client_id: str
    status: str
    filled_quantity: int
    remaining_quantity: int
    account_snapshot_hash: str
    observed_ns: int
    complete: bool
    positions_match: bool
    raw_evidence: bytes

    def __post_init__(self):
        super().__post_init__()
        if self.filled_quantity < 0 or self.remaining_quantity < 0:
            raise ValueError('negative observation quantity')


class ExecutionLedger:
    """One OS lease throughout lifetime, exact replay and conservative reservations.

    Wire translation and reconciliation completeness are external typed inputs.
    This does not certify provider schema, perform network I/O or grant promotion.
    """
    def __init__(self,path,*,create=False,checkpoint=None):
        if type(create) is not bool or create==(checkpoint is not None):
            raise ValueError('create or independently trusted checkpoint required')
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
        self._lease=open(str(path)+'.writer.lock','a+b')
        try:
            self._lease.seek(0,os.SEEK_END)
            if self._lease.tell()==0:
                self._lease.write(b'0');self._lease.flush()
            self._lease.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self._lease.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self._lease.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except (OSError,BlockingIOError) as exc:
            self._lease.close()
            raise ValueError('execution writer lease unavailable') from exc
        self._lock=threading.Lock();self._failed=False;self._closed=False
        self._states={};self._observations={};self._killed=False;self._frontiers={}
        self._kill_path=Path(str(path)+'.kill')
        self._kill_event=threading.Event();self._kill_io_lock=threading.Lock()
        if self._kill_path.exists():self._kill_event.set()
        try:
            self.journal=EvidenceJournal(path,create=create)
            if checkpoint is not None:
                if type(checkpoint) is not dict or set(checkpoint)!={'schema','count','head_hash'} or checkpoint['schema']!=SCHEMA:
                    raise ValueError('invalid execution checkpoint')
                if type(checkpoint['count']) is not int or checkpoint['count']<0:
                    raise ValueError('invalid execution checkpoint count')
                sha256_digest(checkpoint['head_hash'],'checkpoint head')
                self.journal.verify(count=checkpoint['count'],head_hash=checkpoint['head_hash'])
                for entry in self.journal.entries():
                    if entry['kind']!=SCHEMA:
                        raise ValueError('foreign execution event')
                    self._transition(entry['payload'])
            self._sync_kill()
        except BaseException:
            if hasattr(self,'journal'): self.journal.close()
            self._lease.close();raise

    def _active(self):
        if self._closed or self._failed:
            raise ValueError('execution ledger uncertain or closed; trusted restore required')
        try:
            self.journal.verify(count=self.journal.count,head_hash=self.journal.head_hash)
        except BaseException:
            self._failed=True;raise

    @contextmanager
    def _operation(self):
        if not self._lock.acquire(blocking=False):
            raise ValueError('execution operation already in flight')
        try:
            self._active();self._sync_kill();yield
        finally:
            try:
                if not self._failed and not self._closed:self._sync_kill()
            finally:self._lock.release()

    def _sync_kill(self):
        if self._kill_event.is_set() and not self._killed:
            self._append('KILL','local persistent kill latch')

    def _check_frontier(self,args):
        now=args['now'];account=args['account']
        causal=max((s['observed_ns'] or 0 for s in self._states.values()),default=0)
        frontier=self._frontiers.get(account.account.digest)
        if type(now) is not int or now<causal or (frontier is not None and
            (account.digest!=frontier['hash'] or now<frontier['observed_ns'])):
            raise ValueError('account or clock precedes verified reconciliation frontier')

    def _valid_snapshot(self,snapshot,expected_hash,account,observed_ns,required_intents):
        if type(snapshot) is not AccountSnapshot:return False
        try:
            sha256_digest(expected_hash,'expected account hash')
            snapshot.__post_init__()
        except (ValueError,TypeError):return False
        prior=self._frontiers.get(account.digest)
        return (snapshot.digest==expected_hash and snapshot.complete and snapshot.account==account
            and snapshot.observed_ns>=snapshot.pnl_observed_ns>=observed_ns
            and (prior is None or snapshot.observed_ns>=prior['observed_ns'])
            and set(required_intents).issubset(snapshot.reflected_intents))

    def _reservation(self,intent,args,decision):
        gross=math.ceil(Fraction(*decision.exposure))
        low=math.floor(Fraction(*decision.net_min))
        high=math.ceil(Fraction(*decision.net_max))
        scopes=next(i.scopes for i in args['registry'].instruments if i.instrument_id==intent.instrument_id)
        return Reservation(intent.intent_id,intent.account,args['policy'].units,tuple(
            Exposure(s.scope,gross if s.scope in scopes else 0,low if s.scope in scopes else 0,
                     high if s.scope in scopes else 0) for s in args['policy'].scope_limits))

    def _pending(self,exclude=None):
        return tuple(_restore(Reservation,s['reservation']) for key,s in self._states.items()
                     if key!=exclude and s['reservation'] is not None and not s['released'])

    def _transition(self,event):
        if type(event) is not dict or set(event)!={'step','payload'}:
            raise ValueError('invalid execution event')
        step,p=event['step'],event['payload']
        if step=='KILL':
            if type(p) is not str or not p.strip():raise ValueError('kill reason required')
            self._killed=True;return
        if step=='CREATED':
            intent=_restore(Intent,p)
            if intent.intent_id in self._states: raise ValueError('duplicate execution intent')
            self._states[intent.intent_id]=dict(intent=p,status='CREATED',approval=None,
                reservation=None,released=False,wire=None,provider_id=None,filled=0,observed_ns=None)
            return
        if step=='APPROVAL':
            args=_decode_inputs(p['inputs']);intent=args['intent'];state=self._states[intent.intent_id]
            self._check_frontier(args)
            if state['intent']!=asdict(intent) or state['wire'] is not None:
                raise ValueError('approval intent changed or already sent')
            if any(s['status']=='SENT_UNKNOWN' for s in self._states.values()):
                raise ValueError('unknown submission requires reconciliation before approval')
            expected=self._pending(exclude=intent.intent_id)
            if args['reservations']!=expected or args['kill_switch'] is not self._killed:
                raise ValueError('approval omitted authoritative reservations/kill state')
            decision=evaluate(**args)
            if p['decision']!=asdict(decision):raise ValueError('approval decision mismatch')
            if decision.allowed:
                state['reservation']=asdict(self._reservation(intent,args,decision))
                state['approval']=p;state['status']='APPROVED'
            return
        if step=='SENT_UNKNOWN':
            wire=_restore(WireRequest,p['wire']);state=self._states[p['intent_id']]
            intent=_restore(Intent,state['intent'])
            if self._killed or state['status']!='APPROVED' or state['wire'] is not None or wire.intent_hash!=intent.digest or wire.adapter_hash!=intent.adapter_hash or p['approval_hash']!=evidence_hash(state['approval']):
                raise ValueError('outbox lacks exact current approval')
            if any(s['wire'] and s['wire']['client_id']==wire.client_id for s in self._states.values()):
                raise ValueError('duplicate client order identity')
            state['wire']=p['wire'];state['status']='SENT_UNKNOWN';return
        if step=='RETURN':
            state=self._states[p['intent_id']]
            if state['wire'] is None or type(p['body']) is not bytes:raise ValueError('invalid transport return')
            return
        if step=='ERROR':
            state=self._states[p['intent_id']]
            if state['wire'] is None or type(p['error_type']) is not str:raise ValueError('invalid transport error')
            return
        if step=='OBSERVATION':
            observation=_restore(Observation,p['observation'])
            if observation.observation_id in self._observations:raise ValueError('duplicate observation event')
            state=self._states[observation.intent_id]
            snapshot=None if p['account_snapshot'] is None else _restore(AccountSnapshot,p['account_snapshot'])
            valid=self._valid_observation(state,observation,snapshot,p['expected_account_hash'])
            if p['valid'] is not valid:raise ValueError('reconciliation verdict mismatch')
            self._observations[observation.observation_id]=p['observation']
            if not valid:
                self._killed=True;state['released']=False;return
            state['status']=observation.status;state['provider_id']=observation.provider_id
            state['filled']=observation.filled_quantity;state['observed_ns']=observation.observed_ns
            state['released']=observation.status in ('FILLED','CANCELED','REJECTED')
            if state['released']:
                self._frontiers[observation.account.digest]=dict(hash=snapshot.digest,observed_ns=snapshot.observed_ns)
            return
        if step=='ACCOUNT_SNAPSHOT':
            snapshot=_restore(AccountSnapshot,p['snapshot'])
            released=[key for key,s in self._states.items() if s['released'] and _restore(Intent,s['intent']).account==snapshot.account]
            causal=max((s['observed_ns'] or 0 for s in self._states.values()),default=0)
            if not self._valid_snapshot(snapshot,p['expected_hash'],snapshot.account,causal,released):
                raise ValueError('invalid reflected account frontier')
            self._frontiers[snapshot.account.digest]=dict(hash=snapshot.digest,observed_ns=snapshot.observed_ns)
            return
        raise ValueError('unknown execution transition')

    def _valid_observation(self,state,obs,snapshot=None,expected_hash=None):
        intent=_restore(Intent,state['intent']);wire=state['wire']
        terminal=('FILLED','CANCELED','REJECTED')
        if (wire is None or not obs.complete or not obs.positions_match or obs.intent_hash!=intent.digest
            or obs.account!=intent.account or obs.client_id!=wire['client_id']
            or (state['provider_id'] is not None and state['provider_id']!=obs.provider_id)
            or obs.status not in ('ACKNOWLEDGED','PARTIAL',*terminal)
            or obs.filled_quantity < state['filled'] or obs.filled_quantity+obs.remaining_quantity>intent.quantity
            or obs.observed_ns < state['approval']['inputs']['now']
            or (state['observed_ns'] is not None and obs.observed_ns < state['observed_ns'])):
            return False
        if state['status'] in terminal and (obs.status!=state['status'] or obs.filled_quantity!=state['filled']):
            return False
        if obs.status in terminal:
            released=[key for key,s in self._states.items() if s['released'] and _restore(Intent,s['intent']).account==obs.account]
            if not self._valid_snapshot(snapshot,expected_hash,obs.account,obs.observed_ns,(*released,obs.intent_id)):
                return False
            policy=_restore(Policy,state['approval']['inputs']['policy'])
            if (snapshot.digest!=obs.account_snapshot_hash or snapshot.units!=policy.units
                or {e.scope for e in snapshot.exposures}!={s.scope for s in policy.scope_limits}):return False
        if obs.status=='FILLED':return obs.filled_quantity==intent.quantity and obs.remaining_quantity==0
        if obs.status=='REJECTED':return obs.filled_quantity==obs.remaining_quantity==0
        if obs.status=='CANCELED':return obs.remaining_quantity==0
        if obs.status=='PARTIAL':return 0<obs.filled_quantity<intent.quantity and obs.filled_quantity+obs.remaining_quantity==intent.quantity
        return obs.filled_quantity==0 and obs.remaining_quantity==intent.quantity

    def _append(self,step,payload):
        self._active();event=_copy(dict(step=step,payload=payload))
        old=(_copy(self._states),_copy(self._observations),self._killed,_copy(self._frontiers))
        try:
            self._transition(event)
        except BaseException:
            self._states,self._observations,self._killed,self._frontiers=old;raise
        self._states,self._observations,self._killed,self._frontiers=old
        self._failed=True
        self.journal.append(SCHEMA,event)
        self._transition(event);self._failed=False

    def create(self,intent):
        with self._operation():
            if type(intent) is not Intent:raise ValueError('typed intent required')
            existing=self._states.get(intent.intent_id)
            if existing is not None:
                if existing['intent']!=asdict(intent):raise ValueError('intent ID changed')
                return
            self._append('CREATED',asdict(intent))

    def _approve(self,args):
        args=dict(args)
        self._sync_kill();self._check_frontier(args)
        if any(s['status']=='SENT_UNKNOWN' for s in self._states.values()):
            raise ValueError('unknown submission requires reconciliation before approval')
        if args.get('reservations')!=():raise ValueError('ledger owns authoritative reservations')
        if args.get('kill_switch') not in (False,True) or type(args.get('kill_switch')) is not bool:
            raise ValueError('explicit boolean kill switch required')
        if args['kill_switch'] and not self._killed:self._append('KILL','caller kill switch')
        args['kill_switch']=self._killed
        args['reservations']=self._pending(exclude=args['intent'].intent_id)
        decision=evaluate(**args)
        encoded={k:asdict(v) if k in _INPUT_TYPES else tuple(asdict(r) for r in v) if k=='reservations' else v for k,v in args.items()}
        self._append('APPROVAL',dict(inputs=encoded,decision=asdict(decision)))
        return decision

    def approve(self,**evaluation):
        with self._operation():return self._approve(evaluation)

    def dispatch_once(self,*,wire,sender,**evaluation):
        with self._operation():
            if type(wire) is not WireRequest or not callable(sender):raise ValueError('typed wire and explicit callback required')
            intent=evaluation['intent'];state=self._states[intent.intent_id]
            if state['wire'] is not None:raise ValueError('submission outcome exists; reconcile, never resend')
            if not self._approve(evaluation).allowed:raise ValueError('dispatch revalidation rejected')
            state=self._states[intent.intent_id]
            self._append('SENT_UNKNOWN',dict(intent_id=intent.intent_id,wire=asdict(wire),approval_hash=evidence_hash(state['approval'])))
            if self._kill_event.is_set():raise ValueError('local kill latch stopped dispatch')
            try:
                result=sender(wire)
                if type(result) is not bytes:raise ValueError('raw callback bytes required')
            except BaseException as exc:
                self._append('ERROR',dict(intent_id=intent.intent_id,error_type=type(exc).__name__))
                raise
            self._append('RETURN',dict(intent_id=intent.intent_id,body=result))
            return result

    def reconcile(self,observation,*,account_snapshot=None,expected_account_hash=None):
        with self._operation():
            if type(observation) is not Observation:raise ValueError('typed observation required')
            previous=self._observations.get(observation.observation_id)
            if previous is not None:
                if previous!=asdict(observation):
                    self._append('KILL','conflicting observation identity');raise ValueError('observation ID changed')
                return self._valid_observation(self._states[observation.intent_id],observation,account_snapshot,expected_account_hash)
            valid=self._valid_observation(self._states[observation.intent_id],observation,account_snapshot,expected_account_hash)
            self._append('OBSERVATION',dict(observation=asdict(observation),valid=valid,
                account_snapshot=None if account_snapshot is None else asdict(account_snapshot),expected_account_hash=expected_account_hash))
            return valid

    def reflect_account(self,snapshot,*,expected_hash):
        with self._operation():
            self._append('ACCOUNT_SNAPSHOT',dict(snapshot=asdict(snapshot),expected_hash=expected_hash))

    def latch_kill(self,reason):
        if type(reason) is not str or not reason.strip():raise ValueError('kill reason required')
        self._kill_event.set()
        # Independent of the provider/SQLite operation lock. The durable marker
        # must travel with the ledger; it is never silently cleared on restart.
        with self._kill_io_lock:
            with self._kill_path.open('ab') as marker:
                marker.write((reason+'\n').encode('utf-8'));marker.flush();os.fsync(marker.fileno())
        return dict(latched=True,durable=True,journaled=self._killed)

    @property
    def killed(self):
        return self._kill_event.is_set() or self._killed

    def state(self,intent_id):
        self._active();return _copy(self._states[intent_id])

    def reservations(self):
        self._active();return self._pending()

    def checkpoint(self):
        self._active();self._sync_kill();return dict(schema=SCHEMA,count=self.journal.count,head_hash=self.journal.head_hash)

    def close(self):
        if not self._closed:
            if not self._lock.acquire(blocking=False):raise ValueError('cannot close during execution operation')
            try:
                if not self._failed:self._sync_kill()
                self.journal.close();self._lease.close();self._closed=True
            finally:self._lock.release()
