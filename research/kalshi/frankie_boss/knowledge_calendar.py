"""Market calendar context, separate from when a lesson became available.

Regular session labels are Greg's 18:00-17:00 ET convention, not a holiday
calendar or an assertion about an exchange's official trade date.
"""
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, TZPATH
import hashlib

EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)
WEEKDAYS=('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')

def _zone(name):
    for root in TZPATH:
        path=Path(root)/name
        if path.is_file():
            raw=path.read_bytes()
            from io import BytesIO
            return ZoneInfo.from_file(BytesIO(raw),key=name),hashlib.sha256(raw).hexdigest()
    from importlib.resources import files
    from io import BytesIO
    raw=files('tzdata.zoneinfo').joinpath(*name.split('/')).read_bytes()
    return ZoneInfo.from_file(BytesIO(raw),key=name),hashlib.sha256(raw).hexdigest()

def _ns(moment):
    delta=moment.astimezone(timezone.utc)-EPOCH
    return (delta.days*86400+delta.seconds)*10**9+delta.microseconds*1000

def market_calendar(observed_ns):
    if type(observed_ns) is not int or observed_ns<0:
        raise ValueError('integer source market timestamp required')
    seconds,remainder=divmod(observed_ns,10**9)
    instant=EPOCH+timedelta(seconds=seconds,microseconds=remainder//1000)
    zones={}; clocks={}
    for key,name in (('new_york','America/New_York'),('chicago','America/Chicago'),('london','Europe/London')):
        zone,digest=_zone(name);zones[key]=zone
        local=instant.astimezone(zone)
        clocks[key]=dict(timezone=name,timezone_rules_sha256=digest,local_time=local.isoformat(),
            submicrosecond_ns=remainder%1000,fold=local.fold,
            utc_offset_minutes=int(local.utcoffset().total_seconds())//60,
            dst=bool(local.dst()))
    local=instant.astimezone(zones['new_york'])
    session_date=local.date()+timedelta(days=1 if local.hour>=18 else 0)
    start=datetime.combine(session_date-timedelta(days=1),time(18),zones['new_york'])
    end=datetime.combine(session_date,time(17),zones['new_york'])
    weekend=(local.weekday()==5 or (local.weekday()==6 and local.hour<18)
        or (local.weekday()==4 and local.hour>=17))
    if weekend: phase='weekend_closed'
    elif local.hour==17: phase='maintenance'
    elif local.hour>=18: phase='evening'
    else: phase='session_day'
    previous_friday=session_date-timedelta(days=(session_date.weekday()-4)%7 or 7)
    friday=datetime.combine(previous_friday,time(17),zones['new_york'])
    return dict(schema='FRANKIE_MARKET_CALENDAR_V1',observed_ns=observed_ns,
        civil_date=local.date().isoformat(),civil_weekday=WEEKDAYS[local.weekday()],
        session_date=session_date.isoformat(),session_weekday=WEEKDAYS[session_date.weekday()],
        session_date_basis='requested_regular_1800_to_1700_ET_convention',
        exchange_trade_date=None,regular_session_phase=phase,
        regular_session_open_utc=start.astimezone(timezone.utc).isoformat(),
        regular_session_close_utc=end.astimezone(timezone.utc).isoformat(),
        regular_session_duration_seconds=(_ns(end)-_ns(start))//10**9,
        elapsed_from_regular_open_ns=observed_ns-_ns(start),
        us_offset_changed_since_prior_friday=local.utcoffset()!=friday.utcoffset(),
        london_new_york_offset_minutes=clocks['london']['utc_offset_minutes']-clocks['new_york']['utc_offset_minutes'],
        holiday_context=dict(status='unverified',holiday=None,relationship=None,schedule_receipt_hash=None),
        behavioral_effect='hypothesis_requires_market_evidence',**clocks)
