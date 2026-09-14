"""Pure synthetic execution checks; no credentials, models or broker I/O."""
from dataclasses import replace, FrozenInstanceError
import pytest

from research.kalshi.frankie_boss.execution_contracts import (
    AccountKey, Units, Ratio, SignedRatio, Instrument, Registry, SourceReference, Intent,
    ScopeLimit, Policy, Exposure, AccountSnapshot, MarketSnapshot, Valuation, Reservation)
from research.kalshi.frankie_boss.execution_policy import evaluate

H = 'a'*64


def fixture():
    account = AccountKey('tastytrade', 'replay', 'synthetic')
    units = Units('contract', 'price_tick', 'money_cent', 'underlying_unit')
    instrument = Instrument('SYN', 'future', 'SYN-U', 'expiry-A', units, 1, 1,
                            -100, 1000, ('venue:tastytrade', 'underlying:SYN-U'), H)
    registry = Registry((instrument,))
    policy = Policy((account,), ('SYN',), ('future',), ('expiry-A',), ('buy','sell'),
        ('open','close'), ('limit',), ('day',), units, 10, 1000,
        tuple(ScopeLimit(s, 100, -100, 100) for s in instrument.scopes),
        100, 100, 10, 10, 10, 20, 0, 100, 5, (H,), (H,), (H,), (H,))
    source = SourceReference(H,H,H,H,H,H)
    valuation = Valuation('SYN', registry.digest, H, H, 9, -100, 1000,
                          Ratio(100,1), Ratio(2,1), Ratio(0,1),'buy',SignedRatio(0,1),SignedRatio(2,1))
    intent = Intent('intent/1', account, 'SYN', 'buy', 'open', 'limit', 'day',
        2, 51, 9, 20, source.digest, registry.digest, policy.digest,
        valuation.digest, H, H)
    market = MarketSnapshot('SYN',registry.digest,H,H,8,9,9,50,51,True)
    snapshot = AccountSnapshot(account,units,9,True,'day-A',9,0,0,
        tuple(Exposure(s,0,0,0) for s in instrument.scopes),())
    return dict(intent=intent,policy=policy,registry=registry,source=source,
        expected_source_hash=source.digest,expected_valuation_hash=valuation.digest,valuation=valuation,market=market,
        account=snapshot,reservations=(),now=10,loss_day='day-A',kill_switch=False)


def changed_policy(args, **changes):
    policy=replace(args['policy'],**changes)
    return {**args,'policy':policy,'intent':replace(args['intent'],policy_hash=policy.digest)}


def codes(result):
    return {c.name for c in result.checks if not c.passed}


def test_exact_boundary_and_deterministic_full_receipt():
    args=fixture(); args=changed_policy(args,max_order_quantity=2,max_order_notional=200)
    result=evaluate(**args)
    assert result.allowed and result == evaluate(**args)
    assert result.notional == (200,1) and result.exposure == (4,1)
    assert result.intent_hash == args['intent'].digest
    assert dict(result.input_hashes)['registry'] == args['registry'].digest
    assert codes(evaluate(**changed_policy(args,max_order_notional=199))) == {'order_notional'}


@pytest.mark.parametrize('field,value,code',[
    ('max_order_quantity',1,'order_quantity'),('max_order_notional',0,'order_notional'),
    ('allowed_accounts',(),'account_allowlist'),('allowed_instruments',(),'instrument_allowlist'),
    ('allowed_products',(),'product_allowlist'),('allowed_maturities',(),'maturity_allowlist'),
    ('allowed_sides',(),'side_allowlist'),('allowed_effects',(),'effect_allowlist'),
    ('allowed_order_types',(),'order_type_allowlist'),('allowed_tifs',(),'tif_allowlist'),
    ('trusted_models',(),'model_pin'),('trusted_data',(),'data_pin'),
    ('trusted_strategies',(),'strategy_pin'),('trusted_adapters',(),'adapter_pin')])
def test_explicit_limits_and_empty_lists_deny(field,value,code):
    assert code in codes(evaluate(**changed_policy(fixture(),**{field:value})))


@pytest.mark.parametrize('part,changes,code',[
    ('market',{'observed_ns':11},'market_time'),
    ('market',{'event_ns':10,'received_ns':9},'market_time'),
    ('market',{'bid':52},'market_book'),('market',{'healthy':False},'market_book'),
    ('market',{'source_hash':'b'*64},'market_binding'),
    ('account',{'observed_ns':11},'account_time'),
    ('account',{'complete':False},'account_complete'),
    ('account',{'loss_day':'other'},'loss_day'),
    ('account',{'realized_loss':100},'realized_loss'),
    ('account',{'mtm_loss':100},'mtm_loss'),
    ('valuation',{'observed_ns':11},'valuation_time'),
    ('intent',{'expires_ns':10},'intent_time'),
    ('intent',{'source_hash':'b'*64},'source_pin'),
    ('intent',{'registry_hash':'b'*64},'registry_pin'),
    ('intent',{'policy_hash':'b'*64},'policy_pin'),
    ('intent',{'price':57},'price_slippage')])
def test_stale_future_unknown_and_mismatched_inputs(part,changes,code):
    args=fixture(); args[part]=replace(args[part],**changes)
    assert code in codes(evaluate(**args))


def test_stale_snapshot_thresholds_are_explicit():
    args=fixture()
    for field,code in [('max_market_age_ns','market_time'),('max_account_age_ns','account_time'),
                       ('max_valuation_age_ns','valuation_time')]:
        assert code in codes(evaluate(**changed_policy(args,**{field:0})))


def test_unknown_instrument_is_a_denial_not_fallback():
    args=fixture(); args['intent']=replace(args['intent'],instrument_id='MISSING')
    assert not evaluate(**args).allowed


def test_pending_opposite_orders_do_not_net_away_risk():
    args=fixture(); scopes=args['registry'].instruments[0].scopes
    args['reservations']=(Reservation('other',args['account'].account,args['policy'].units,
        tuple(Exposure(s,99,-99,0) for s in scopes)),)
    result=evaluate(**args)
    assert not result.allowed
    assert all('gross:'+s in codes(result) for s in scopes)


def test_already_reflected_reservation_and_missing_scopes_deny():
    args=fixture(); scopes=args['registry'].instruments[0].scopes
    reservation=Reservation('other',args['account'].account,args['policy'].units,
        tuple(Exposure(s,1,0,1) for s in scopes))
    args['reservations']=(reservation,)
    args['account']=replace(args['account'],reflected_intents=('other',))
    assert 'reservation_identity' in codes(evaluate(**args))
    args=fixture(); args['account']=replace(args['account'],exposures=())
    assert 'exposure_coverage' in codes(evaluate(**args))


def test_rational_valuation_does_not_round_at_boundary():
    args=fixture(); valuation=replace(args['valuation'],notional_per_quantity=Ratio(201,2))
    args['valuation']=valuation; args['intent']=replace(args['intent'],valuation_hash=valuation.digest)
    args['expected_valuation_hash']=valuation.digest
    result=evaluate(**changed_policy(args,max_order_notional=200))
    assert result.notional == (201,1) and 'order_notional' in codes(result)


def test_global_kill_switch_and_source_root_deny():
    args=fixture(); args['kill_switch']=True
    assert 'kill_switch' in codes(evaluate(**args))
    args=fixture();args['expected_source_hash']='b'*64
    assert 'source_pin' in codes(evaluate(**args))


@pytest.mark.parametrize('value',[True,1.0,'1',None])
def test_integer_units_never_coerce(value):
    with pytest.raises(ValueError): replace(fixture()['intent'],quantity=value)


def test_contracts_are_frozen_and_nested_lists_reject():
    args=fixture()
    with pytest.raises(FrozenInstanceError): args['intent'].quantity=3
    with pytest.raises(ValueError): replace(args['registry'],instruments=list(args['registry'].instruments))
    with pytest.raises(ValueError): Ratio(1,0)
    with pytest.raises(ValueError): Ratio(2,2)
    with pytest.raises(ValueError): replace(args['policy'],max_order_quantity=-1)
    with pytest.raises(ValueError): replace(args['account'],complete=1)


def test_valuation_cannot_be_replaced_by_proposal_author():
    args=fixture();valuation=replace(args['valuation'],notional_per_quantity=Ratio(1,1))
    args['valuation']=valuation;args['intent']=replace(args['intent'],valuation_hash=valuation.digest)
    assert 'valuation_pin' in codes(evaluate(**args))


def test_valuation_covers_better_limit_fills_too():
    args=fixture();valuation=replace(args['valuation'],min_price=50)
    args['valuation']=valuation;args['intent']=replace(args['intent'],valuation_hash=valuation.digest)
    args['expected_valuation_hash']=valuation.digest
    assert 'valuation_price' in codes(evaluate(**args))


def test_net_interval_boundary_and_sell_reservation():
    args=fixture(); limits=tuple(replace(s,net_min=-3) for s in args['policy'].scope_limits)
    args=changed_policy(args,scope_limits=limits)
    args['intent']=replace(args['intent'],side='sell')
    valuation=replace(args['valuation'],side='sell',net_min_per_quantity=SignedRatio(-2,1),net_max_per_quantity=SignedRatio(0,1))
    args['valuation']=valuation;args['expected_valuation_hash']=valuation.digest
    args['intent']=replace(args['intent'],valuation_hash=valuation.digest)
    assert all('net:'+s.scope in codes(evaluate(**args)) for s in limits)


def test_fractional_risk_and_fees_preserve_exact_noninteger_value():
    args=fixture();valuation=replace(args['valuation'],fee_per_quantity=Ratio(1,3))
    args['valuation']=valuation;args['intent']=replace(args['intent'],valuation_hash=valuation.digest)
    args['expected_valuation_hash']=valuation.digest
    result=evaluate(**args)
    assert result.allowed and result.notional == (602,3)
    assert not evaluate(**changed_policy(args,max_order_notional=200)).allowed


def test_unknown_side_cannot_be_enabled_through_allowlist():
    args=changed_policy(fixture(),allowed_sides=('invented',))
    args['intent']=replace(args['intent'],side='invented')
    assert 'supported_semantics' in codes(evaluate(**args))


def test_unknown_tif_cannot_be_enabled_through_allowlist():
    args=changed_policy(fixture(),allowed_tifs=('invented',))
    args['intent']=replace(args['intent'],tif='invented')
    assert 'supported_semantics' in codes(evaluate(**args))


def test_long_put_buy_must_use_declared_negative_net_exposure():
    from research.kalshi.frankie_boss.execution_contracts import SignedRatio
    args=fixture()
    instrument=replace(args['registry'].instruments[0],product='future_option')
    registry=Registry((instrument,));args['registry']=registry
    valuation=replace(args['valuation'],registry_hash=registry.digest,
        side='buy',net_min_per_quantity=SignedRatio(-2,1),net_max_per_quantity=SignedRatio(0,1))
    args['valuation']=valuation;args['expected_valuation_hash']=valuation.digest
    args['market']=replace(args['market'],registry_hash=registry.digest)
    args['intent']=replace(args['intent'],registry_hash=registry.digest,valuation_hash=valuation.digest)
    args=changed_policy(args,allowed_products=('future_option',),
        scope_limits=tuple(replace(s,net_min=-3) for s in args['policy'].scope_limits))
    result=evaluate(**args)
    assert result.net_min == (-4,1) and result.net_max == (0,1)
    assert all('net:'+s.scope in codes(result) for s in args['policy'].scope_limits)


def test_wrong_side_valuation_denies_and_invalid_interval_rejects():
    args=fixture();args['intent']=replace(args['intent'],side='sell')
    assert 'valuation_pin' in codes(evaluate(**args))
    with pytest.raises(ValueError): replace(args['valuation'],net_min_per_quantity=SignedRatio(-3,1))
    with pytest.raises(ValueError): replace(args['valuation'],net_min_per_quantity=SignedRatio(1,1))
