"""Pure deterministic execution eligibility; does not approve or dispatch orders."""
from dataclasses import dataclass
from fractions import Fraction

from .execution_contracts import (Intent, Policy, Registry, SourceReference,
    Valuation, MarketSnapshot, AccountSnapshot, Reservation, _typed)
from .c15_journal import evidence_hash
from .forecast_contract import sha256_digest


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    measured: tuple
    required: tuple


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    intent_hash: str
    input_hashes: tuple
    checks: tuple[Check, ...]
    notional: tuple[int, int]
    exposure: tuple[int, int]
    net_min: tuple[int, int]
    net_max: tuple[int, int]

    @property
    def digest(self):
        from dataclasses import asdict
        return evidence_hash(dict(schema='BOSS_EXECUTION_POLICY_V1',**asdict(self)))


def _pair(value):
    value=Fraction(value)
    return value.numerator,value.denominator


def evaluate(*, intent, policy, registry, source, expected_source_hash, expected_valuation_hash,
             valuation, market, account, reservations, now, loss_day, kill_switch):
    """All clocks and authorities are supplied explicitly. Empty allowlists deny.

    The caller independently trusts expected_source_hash, the policy/registry,
    expected_valuation_hash, and complete account/reservation observations.
    This slice validates their consistency; it does not fetch/attest those facts.
    """
    for value,kind in ((intent,Intent),(policy,Policy),(registry,Registry),
        (source,SourceReference),(valuation,Valuation),(market,MarketSnapshot),
        (account,AccountSnapshot)):
        _typed(value,kind,kind.__name__)
        value.__post_init__()
    _typed(reservations,tuple[Reservation,...],'reservations')
    for reservation in reservations:
        reservation.__post_init__()
    if type(now) is not int or now < 0 or type(kill_switch) is not bool or type(loss_day) is not str or not loss_day.strip():
        raise ValueError('explicit clock, loss day and boolean kill switch required')
    sha256_digest(expected_source_hash,'expected_source_hash')
    sha256_digest(expected_valuation_hash,'expected_valuation_hash')
    checks=[]

    def check(name,passed,measured=(),required=()):
        checks.append(Check(name,bool(passed),tuple(measured),tuple(required)))

    hashes=tuple((name,value.digest) for name,value in
        (('intent',intent),('policy',policy),('registry',registry),('source',source),
         ('valuation',valuation),('market',market),('account',account)))
    hashes += (('reservations',evidence_hash(tuple(r.digest for r in reservations))),
               ('evaluation',evidence_hash(dict(now=now,loss_day=loss_day,kill_switch=kill_switch,
                                               expected_source_hash=expected_source_hash,
                                               expected_valuation_hash=expected_valuation_hash))))

    def finish(notional=Fraction(0),exposure=Fraction(0),net_min=Fraction(0),net_max=Fraction(0)):
        return PolicyDecision(all(c.passed for c in checks),intent.digest,hashes,
                              tuple(checks),_pair(notional),_pair(exposure),_pair(net_min),_pair(net_max))

    check('kill_switch',not kill_switch,(kill_switch,),(False,))
    check('source_pin',intent.source_hash == source.digest == expected_source_hash,
          (intent.source_hash,source.digest),(expected_source_hash,))
    check('registry_pin',intent.registry_hash == registry.digest,(intent.registry_hash,),(registry.digest,))
    check('policy_pin',intent.policy_hash == policy.digest,(intent.policy_hash,),(policy.digest,))
    for name,value,allowed in (
        ('account',intent.account.digest,tuple(a.digest for a in policy.allowed_accounts)),
        ('instrument',intent.instrument_id,policy.allowed_instruments),
        ('side',intent.side,policy.allowed_sides),('effect',intent.effect,policy.allowed_effects),
        ('order_type',intent.order_type,policy.allowed_order_types),('tif',intent.tif,policy.allowed_tifs)):
        check(name+'_allowlist',value in allowed,(value,),allowed)
    for name,value,allowed in (('model',source.model_hash,policy.trusted_models),
        ('data',source.data_hash,policy.trusted_data),('strategy',intent.strategy_hash,policy.trusted_strategies),
        ('adapter',intent.adapter_hash,policy.trusted_adapters)):
        check(name+'_pin',value in allowed,(value,),allowed)
    check('supported_semantics',intent.account.venue in ('tastytrade','kalshi')
          and intent.account.environment in ('replay','shadow','sandbox','paper','live')
          and intent.side in ('buy','sell') and intent.effect in ('open','close')
          and intent.order_type == 'limit'
          and intent.tif in ('day','good_till_canceled','fill_or_kill','immediate_or_cancel'),
          (intent.account.venue,intent.account.environment,intent.side,intent.effect,intent.order_type,intent.tif),
          ('tastytrade/kalshi','replay/shadow/sandbox/paper/live','buy/sell','open/close','limit',
           'day/good_till_canceled/fill_or_kill/immediate_or_cancel'))
    check('intent_time',intent.created_ns <= now < intent.expires_ns and now-intent.created_ns <= policy.max_intent_age_ns,
          (intent.created_ns,now,intent.expires_ns),(policy.max_intent_age_ns,))
    check('session',policy.session_start_ns <= now < policy.session_end_ns,(now,),
          (policy.session_start_ns,policy.session_end_ns))
    instruments={i.instrument_id:i for i in registry.instruments}
    instrument=instruments.get(intent.instrument_id)
    check('known_instrument',instrument is not None,(intent.instrument_id,),tuple(instruments))
    if instrument is None:
        return finish()
    check('supported_product',
          (intent.account.venue=='tastytrade' and instrument.product in ('future','future_option'))
          or (intent.account.venue=='kalshi' and instrument.product=='event'),
          (intent.account.venue,instrument.product),('tastytrade:future/future_option','kalshi:event'))
    for name,value,allowed in (('product',instrument.product,policy.allowed_products),
                                ('maturity',instrument.maturity,policy.allowed_maturities)):
        check(name+'_allowlist',value in allowed,(value,),allowed)
    check('units',instrument.units == policy.units == account.units,
          (instrument.units.digest,account.units.digest),(policy.units.digest,))
    check('quantity_grid',intent.quantity % instrument.quantity_step == 0,
          (intent.quantity,),(instrument.quantity_step,))
    check('price_grid',intent.price % instrument.price_step == 0 and instrument.min_price <= intent.price <= instrument.max_price,
          (intent.price,),(instrument.price_step,instrument.min_price,instrument.max_price))
    check('order_quantity',intent.quantity <= policy.max_order_quantity,(intent.quantity,),(policy.max_order_quantity,))
    check('market_binding',market.instrument_id == intent.instrument_id and market.registry_hash == registry.digest
          and market.source_hash == source.source_hash and market.data_hash == source.data_hash,
          (market.instrument_id,market.registry_hash,market.source_hash,market.data_hash),
          (intent.instrument_id,registry.digest,source.source_hash,source.data_hash))
    check('market_time',market.event_ns <= market.received_ns <= market.observed_ns <= now
          and now-market.event_ns <= policy.max_market_age_ns,
          (market.event_ns,market.received_ns,market.observed_ns,now),(policy.max_market_age_ns,))
    check('market_book',market.healthy and market.bid <= market.ask
          and instrument.min_price <= market.bid <= market.ask <= instrument.max_price
          and market.bid % instrument.price_step == market.ask % instrument.price_step == 0,
          (market.healthy,market.bid,market.ask),(instrument.min_price,instrument.max_price,instrument.price_step))
    check('price_slippage',(intent.side == 'buy' and intent.price <= market.ask+policy.max_slippage)
          or (intent.side == 'sell' and intent.price >= market.bid-policy.max_slippage),
          (intent.price,market.bid,market.ask),(policy.max_slippage,))
    check('account_binding',account.account == intent.account,(account.account.digest,),(intent.account.digest,))
    check('account_complete',account.complete,(account.complete,),(True,))
    check('account_time',account.pnl_observed_ns <= account.observed_ns <= now
          and now-account.pnl_observed_ns <= policy.max_account_age_ns,
          (account.pnl_observed_ns,account.observed_ns,now),(policy.max_account_age_ns,))
    check('loss_day',account.loss_day == loss_day,(account.loss_day,),(loss_day,))
    for name,value,cap in (('realized_loss',account.realized_loss,policy.max_realized_loss),
                            ('mtm_loss',account.mtm_loss,policy.max_mtm_loss)):
        check(name,value < cap,(value,),(cap,))
    check('valuation_pin',intent.valuation_hash == valuation.digest == expected_valuation_hash and valuation.instrument_id == intent.instrument_id
          and valuation.side == intent.side
          and valuation.registry_hash == registry.digest and valuation.source_hash == source.source_hash
          and valuation.convention_hash == instrument.valuation_convention_hash,
          (valuation.digest,valuation.instrument_id,valuation.registry_hash,valuation.source_hash,valuation.convention_hash),
          (expected_valuation_hash,intent.instrument_id,registry.digest,source.source_hash,instrument.valuation_convention_hash))
    check('valuation_time',valuation.observed_ns <= now and now-valuation.observed_ns <= policy.max_valuation_age_ns,
          (valuation.observed_ns,now),(policy.max_valuation_age_ns,))
    execution_min=instrument.min_price if intent.side=='buy' else intent.price
    execution_max=intent.price if intent.side=='buy' else instrument.max_price
    check('valuation_price',valuation.min_price <= execution_min <= execution_max <= valuation.max_price,
          (execution_min,execution_max),(valuation.min_price,valuation.max_price))
    ratio=lambda r:Fraction(r.numerator,r.denominator)
    notional=intent.quantity*(ratio(valuation.notional_per_quantity)+ratio(valuation.fee_per_quantity))
    exposure=intent.quantity*ratio(valuation.exposure_per_quantity)
    net_min=intent.quantity*ratio(valuation.net_min_per_quantity)
    net_max=intent.quantity*ratio(valuation.net_max_per_quantity)
    check('order_notional',notional <= policy.max_order_notional,_pair(notional),(policy.max_order_notional,))
    ids=tuple(r.intent_id for r in reservations)
    check('reservation_identity',len(ids)==len(set(ids)) and intent.intent_id not in ids
          and intent.intent_id not in account.reflected_intents and not set(ids).intersection(account.reflected_intents)
          and all(r.account == intent.account and r.units == policy.units for r in reservations),ids,account.reflected_intents)
    limits={s.scope:s for s in policy.scope_limits}
    current={s.scope:s for s in account.exposures}
    check('exposure_coverage',set(instrument.scopes).issubset(limits) and set(current)==set(limits)
          and all({e.scope for e in r.exposures}==set(limits) for r in reservations),
          tuple(current),tuple(limits))
    for scope,limit in limits.items():
        if scope not in current:
            continue
        base=current[scope]
        pending=[e for r in reservations for e in r.exposures if e.scope==scope]
        add=exposure if scope in instrument.scopes else Fraction(0)
        gross=base.gross+sum(e.gross for e in pending)+add
        low=base.net_min+sum(e.net_min for e in pending)+(net_min if scope in instrument.scopes else 0)
        high=base.net_max+sum(e.net_max for e in pending)+(net_max if scope in instrument.scopes else 0)
        check('gross:'+scope,gross <= limit.gross,_pair(gross),(limit.gross,))
        check('net:'+scope,low >= limit.net_min and high <= limit.net_max,
              (_pair(low),_pair(high)),(limit.net_min,limit.net_max))
    return finish(notional,exposure,net_min,net_max)
