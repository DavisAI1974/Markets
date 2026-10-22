"""FRANKIE_DAY_EXTERNAL_V1: Frankie's 13 historical data points for ONE trading day, at native resolution, every value
stamped with the time it became public; the one as-of reader; the staging check. Greg, 2026-09-29: "everyone who sees
his ingest should see these data points too"; "He'll get the futures curve shape too"; "I'm not concerned about him
having trade curves" (the guard is TIME only); "we should somehow still attach whatever doesn't get run with this tues
and wed to their historical data". Plan: research/kalshi/frankie_boss/HISTORICAL_DATA_PLAN_20260929.md.

THE DAY. Trading day D opens 18:00 ET on the prior calendar day and halts 17:00 ET on D. The file holds every value
published before the halt (a value published before the open is known at the open; one published during the day is
known from its stamp on). A value published at or after the halt belongs to a later day and is not in this day's file
(counted in `after_halt` per point, never silently lost).

INPUTS (local copies of the S3 objects, same key layout under --src; nothing is fetched here):
  frankie/day_history/<run>/...   operations/fetch_day_history.py fetch (calendar, cot, storage, consensus, weather_obs,
                                  mos, eia930), with its manifest.json
  nymex/ng_fut_parent_v0/<schema>/native/glbx-mdp3-<YYYYMMDD>.<schema>.dbn.zst   operations/pull_curve_days.py
                                  (NG.FUT parent: definition, statistics, mbo), the two UTC partitions of the day

THE FILE (JSON). {schema, trading_day, open_utc, halt_utc, open_ns, halt_ns, built_utc, inputs[], points{}, missing[]}.
Every point is a table: {columns, stamp_column ('published_ns'), rows, source, vintage, native_resolution, note,
after_halt}. published_ns is UTC nanoseconds. The 13 (Greg's order) and where they live:
   1 cot.managed_money_net_pctile_1y, 3 ..._chg_wow, 4 ..._pctile_3y   -> point 'cot.023651' (every report, stamped
                                                                          with cot_feed's publication rule)
   8 cot.ice.ld1.managed_money_net_pctile_1y                            -> point 'cot.023391' (and 023392/0233AG/0233AH)
   2 weather_forecast.forecast_gw_hdd                                   -> 'mos.gw_by_cycle' (per model cycle, per target
                                                                          day D..D+7) and 'mos.raw' (every MOS row)
   9 model_disagreement.summary.max_abs_spread_gw_hdd                   -> 'mos.disagreement_by_cycle'
   5 grid_stack.bas.US48.wind_mwh, 7 ...est_gas_burn_bcfd              -> 'eia930.hourly' (every row, 7 respondents) and
                                                                          'eia930.us48' (wind, gas, the burn estimate)
   6 squeeze_watch.sessions_since_prompt_expiry                         -> 'calendar.sessions_since_prompt_expiry'
  10 weather.gw_hdd                                                     -> 'weather.gw_daily' and 'weather.obs_hourly'
  11 EIA weekly storage (level, weekly change, vs 5-year)               -> 'storage.weekly' (as printed where the
                                                                          archived report is held, else the EIA series)
  12 storage estimate vs actual                                         -> 'storage.estimate' (estimate, printed actual,
                                                                          surprise per print; values, never page links)
  13 the futures curve                                                  -> 'curve.definitions', 'curve.statistics',
                                                                          'curve.trades' (every trade of every month),
                                                                          'curve.settled_shape', 'curve.traded_shape'

THE 99 AND THE READER STAMP (Greg 2026-10-07). Every table carries its 99 mapping (POINT_REGISTRY_MAP: registry_entries,
registry_mapping 'closest' with registry_mapping_reason, event_time_basis, points) and every row an event_time_ns column
(its own event time; None when it has none). published_ns is the ONE reader stamp: max(event_time_ns, publication); a
row with no event time sits at 14:00 ET of the trading day ('this is not a time-specific event') unless published later.

TIME GUARD (spec 2d7313bd): every row has published_ns. check_day_file() refuses a file with a row lacking it, with
a row at or after the halt, or with an event_time_ns after its reader stamp. AsOfReader(file, cutoff_ns) refuses (LeakRefused, naming the point, the time and the
cutoff) any request past its cutoff and any point holding a value past it; it never filters silently.

    python3.12 frankie_day_external.py build --src <dir> --history-prefix frankie/day_history/<run> --day 20211005 --out <file>
    python3.12 frankie_day_external.py check --file <file>
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA = 'FRANKIE_DAY_EXTERNAL_V1'
ET, UTC, CT = ZoneInfo('America/New_York'), dt.timezone.utc, ZoneInfo('America/Chicago')
CURVE_PREFIX = 'nymex/ng_fut_parent_v0'
UNDEF_PRICE = 9223372036854775807
OUTRIGHT = re.compile(r'^NG[FGHJKMNQUVXZ]\d{1,2}$')
MOS_LAG_NS = int(4.5 * 3600e9)            # mos_cycle_feed.DISSEM_LAG_H: conservative availability of a cycle
OBS_LAG_NS = int(600e9)                   # an ASOS observation is public minutes after its time (nominal 10 min)
EIA930_LAG_NS = int(2 * 3600e9)           # period stamp + 2 h: covers hour-beginning or hour-ending labels + ~1 h lag
SETTLE_STAT = 3                           # Databento StatType.SETTLEMENT_PRICE
N_RANKS = 12                              # forward_curve.N_RANKS
SERIES_STATIONS_NOTE = 'the 16 gas-weighted metros of nws_temp_feed.STATION_WEIGHTS_RAW'
DEFAULT_PLACEMENT_ET = (14, 0)            # Greg 2026-10-07: a value with no event time of its own sits at 14:00 ET
DEFAULT_PLACEMENT_NOTE = 'this is not a time-specific event'

# Greg, 2026-10-07: every point maps to one of the 99 (deploy/aws/box/frankie_box_all99_coverage.REGISTRY); none of the
# 13 is an MBO layer, so every mapping is the CLOSEST entry with its reason. Each table of the day file carries its
# mapping as metadata (registry_entries / registry_mapping / registry_mapping_reason / event_time_basis / points), the
# names frankie_box_all99_coverage.external_point_mapping reads. Keys are table names or prefixes ending in '.'.
_FLOW = 'aggressor_and_native_signed_flow'
_BAL = 'depletion_and_replenishment'
POINT_REGISTRY_MAP = {
    'cot.023651': dict(points=[1, 3, 4], registry_entries=[_FLOW], registry_mapping='closest',
                       registry_mapping_reason='managed-money net positioning (its 1y/3y percentiles and week-on-week change) '
                       'is the signed directional flow of one trader class; no 99 entry is external positioning',
                       event_time_basis='intrinsic'),
    'cot.023391': dict(points=[8], registry_entries=[_FLOW], registry_mapping='closest',
                       registry_mapping_reason='ICE Henry Hub LD1 managed-money net positioning, as cot.023651',
                       event_time_basis='intrinsic'),
    'cot.': dict(points=[8], registry_entries=[_FLOW], registry_mapping='closest',
                 registry_mapping_reason='other ICE Henry Hub codes beside LD1 (context for point 8), as cot.023651',
                 event_time_basis='intrinsic'),
    'mos.raw': dict(points=[2], registry_entries=['clock_feature_availability'], registry_mapping='closest',
                    registry_mapping_reason='every MOS model-cycle row, available at cycle time + dissemination; no 99 '
                    'entry is weather', event_time_basis='intrinsic'),
    'mos.gw_by_cycle': dict(points=[2], registry_entries=['clock_feature_availability'], registry_mapping='closest',
                            registry_mapping_reason='forecast gas-weighted HDD per model cycle, available at cycle time + '
                            'dissemination; no 99 entry is weather', event_time_basis='intrinsic'),
    'mos.disagreement_by_cycle': dict(points=[9], registry_entries=['clock_feature_availability'], registry_mapping='closest',
                                      registry_mapping_reason='GFS-minus-NAM spread per shared model cycle, available at '
                                      'cycle time + dissemination', event_time_basis='intrinsic'),
    'eia930.hourly': dict(points=[5, 7], registry_entries=[_BAL], registry_mapping='closest',
                          registry_mapping_reason='hourly generation by fuel and balancing-area demand: wind displaces gas '
                          'burn and gas burn draws on the gas balance', event_time_basis='intrinsic'),
    'eia930.us48': dict(points=[5, 7], registry_entries=[_BAL], registry_mapping='closest',
                        registry_mapping_reason='US48 wind and the gas-burn estimate are supply/demand balance terms',
                        event_time_basis='intrinsic'),
    'calendar.sessions_since_prompt_expiry': dict(points=[6], registry_entries=['contract_session_roll_state'],
                                                  registry_mapping='closest',
                                                  registry_mapping_reason='sessions since the prompt contract expired is '
                                                  'a contract/roll calendar state', event_time_basis='default_1400',
                                                  event_time_note=DEFAULT_PLACEMENT_NOTE),
    'weather.gw_daily': dict(points=[10], registry_entries=['clock_event_known_by'], registry_mapping='closest',
                             registry_mapping_reason='an observed gas-day index, known once the gas day ends (+10 min)',
                             event_time_basis='intrinsic'),
    'weather.obs_hourly': dict(points=[10], registry_entries=['clock_event_known_by'], registry_mapping='closest',
                               registry_mapping_reason='every ASOS observation, known minutes after its time',
                               event_time_basis='intrinsic'),
    'storage.weekly': dict(points=[11], registry_entries=[_BAL], registry_mapping='closest',
                           registry_mapping_reason='weekly working-gas level and injection are the gas balance itself',
                           event_time_basis='intrinsic'),
    'storage.estimate': dict(points=[12], registry_entries=[_BAL], registry_mapping='closest',
                             registry_mapping_reason='the street estimate of the injection against the printed actual',
                             event_time_basis='intrinsic'),
    'curve.': dict(points=[13], registry_entries=['price_and_book_path', 'contract_session_roll_state'],
                   registry_mapping='closest',
                   registry_mapping_reason='the futures curve across months (prices, settlements, shape) and its '
                   'front/next contract pair', event_time_basis='intrinsic'),
}


def registry_map_for(name):
    """The POINT_REGISTRY_MAP entry of a table name (exact name first, then the longest prefix ending in '.')."""
    if name in POINT_REGISTRY_MAP:
        return POINT_REGISTRY_MAP[name]
    pre = [k for k in POINT_REGISTRY_MAP if k.endswith('.') and name.startswith(k)]
    return POINT_REGISTRY_MAP[max(pre, key=len)] if pre else None


def _utc_ns(text, fmt):
    return ns(dt.datetime.strptime(text, fmt).replace(tzinfo=UTC))


def _et_ns(day_iso, hour, minute=0):
    d = dt.date.fromisoformat(day_iso)
    return ns(dt.datetime(d.year, d.month, d.day, hour, minute, tzinfo=ET).astimezone(UTC))


# The intrinsic event time of a row, per table (None: no event time of its own -> the 14:00 ET placement). The reader
# stamp (published_ns) of every row is max(event_time_ns, publication) so every reader of the file sees one time.
EVENT_TIME_RULES = {
    'cot.': lambda c, r: _et_ns(r[c.index('report_date')], 17) if 'report_date' in c and r[c.index('report_date')] else None,
    'storage.weekly': lambda c, r: _et_ns(r[c.index('week_ending')], 17),
    'storage.estimate': lambda c, r: r[c.index('print_ns')],
    'weather.obs_hourly': lambda c, r: _utc_ns(r[c.index('valid_utc')], '%Y-%m-%d %H:%M'),
    'weather.gw_daily': lambda c, r: r[c.index('published_ns')] - OBS_LAG_NS,
    'mos.': lambda c, r: _utc_ns(r[c.index('runtime_utc')], '%Y-%m-%d %H:%M:%S'),
    'eia930.': lambda c, r: _utc_ns(r[c.index('period_utc')], '%Y-%m-%dT%H'),
    'curve.statistics': lambda c, r: r[c.index('ts_event')],
    'curve.trades': lambda c, r: r[c.index('ts_event')],
    'curve.': lambda c, r: r[c.index('published_ns')],
    'calendar.': lambda c, r: None,
}


class LeakRefused(RuntimeError):
    """A value past the reader's cutoff was asked for or is present in a point read whole."""


class StagingRefused(RuntimeError):
    """The day file breaks the time guard (a value without a stamp, or at/after the halt)."""


def ns(t):
    return int(t.timestamp()) * 10**9 + t.microsecond * 1000


def session(day):
    d = dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    p = d - dt.timedelta(days=1)
    return (dt.datetime(p.year, p.month, p.day, 18, tzinfo=ET).astimezone(UTC),
            dt.datetime(d.year, d.month, d.day, 17, tzinfo=ET).astimezone(UTC))


def table(columns, rows, *, source, vintage, native_resolution, note=None, after_halt=0):
    return dict(columns=list(columns), stamp_column='published_ns', rows=rows, source=source, vintage=vintage,
                native_resolution=native_resolution, note=note, after_halt=after_halt)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------------------------------------ the builder pieces

class Build:
    # 'as_printed' (fetch_day_history.py as-printed): the storage report and the street estimate as published at the
    # time, extracted from the archived pages; it replaces reading the consensus captures here (values, not pointers)
    FAMILIES = ('calendar', 'cot', 'storage', 'weather_obs', 'mos', 'eia930', 'as_printed')

    def __init__(self, src, history_prefix, day, eia930_prefix=None, family_prefixes=None):
        self.src, self.hp, self.day = Path(src), history_prefix.strip('/'), day
        # a family may come from another day_history run (Greg 2026-09-29: the eia930-only re-fetch with the real key,
        # the gap-only chunks of the fetch); every prefix is recorded in the day file, every manifest checks the reads
        self.fam = {f: self.hp for f in self.FAMILIES}
        if eia930_prefix:
            self.fam['eia930'] = eia930_prefix.strip('/')
        self.fam.update({f: v.strip('/') for f, v in (family_prefixes or {}).items() if f in self.fam and v})
        self.eia_hp = self.fam['eia930']
        self.open, self.halt = session(day)
        self.open_ns, self.halt_ns = ns(self.open), ns(self.halt)
        self.date = dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))
        self.points, self.missing, self.inputs = {}, [], []
        self.manifest = {}
        for prefix in dict.fromkeys((self.hp,) + tuple(self.fam.values())):
            m = self.src / prefix / 'manifest.json'
            if m.is_file():
                self.manifest.update({e['key']: e for e in json.loads(m.read_bytes())})

    def read(self, key, binary=False):
        """A local copy of an S3 object, its sha256 checked against the day-history manifest when it names it."""
        path = self.src / key
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        want = self.manifest.get(key, {}).get('sha256')
        if want and want != digest:
            raise StagingRefused('%s differs from its manifest sha256' % key)
        self.inputs.append(dict(key=key, bytes=len(raw), sha256=digest, manifest_checked=bool(want)))
        return raw if binary else json.loads(raw)

    def lack(self, point, reason):
        self.missing.append(dict(point=point, day=self.day, reason=reason))

    def keep(self, rows, stamp_index=0):
        kept = [r for r in rows if r[stamp_index] is not None and r[stamp_index] < self.halt_ns]
        return kept, len(rows) - len(kept)

    # 6
    def calendar(self):
        key = f'{self.fam['calendar']}/calendar/sessions_since_prompt_expiry.json'
        if not (self.src / key).is_file():
            return self.lack('calendar.sessions_since_prompt_expiry', 'no calendar file under the day-history run')
        v = self.read(key).get(self.date.isoformat())
        if v is None:
            return self.lack('calendar.sessions_since_prompt_expiry', 'the calendar file has no entry for the day')
        self.points['calendar.sessions_since_prompt_expiry'] = table(
            ['published_ns', 'sessions_since_prompt_expiry', 'last_prompt_symbol', 'last_prompt_expiry'],
            [[self.open_ns, v['sessions_since_prompt_expiry'], v['last_prompt_symbol'], v['last_prompt_expiry']]],
            source='flow_calendar.ng_expiry/bd_between', vintage='calendar rule', native_resolution='per day',
            note='a calendar count, known before the open (stamped at the open)')

    # 1, 3, 4, 8
    def cot(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import cot_feed
        found = sorted(glob.glob(str(self.src / self.fam['cot'] / 'cot' / 'store' / 'ng_cot_*.json')))
        if not found:
            return self.lack('cot', 'no COT store under the day-history run')
        for path in found:
            key = str(Path(path).relative_to(self.src))
            store = self.read(key)
            code = store.get('contract_code') or Path(path).stem.split('_')[-1]
            reports = store.get('reports') or []
            cols = sorted({k for r in reports for k in r})
            lead = ['published_ns', 'publication_confidence', 'publication_delayed']
            # a store field with a lead column's name (the store records its own publication fields) keeps its value
            # under 'store_<name>', so no column repeats and nothing is dropped
            names = [('store_' + c) if c in lead else c for c in cols]
            rows = []
            for r in reports:
                pub, delayed, conf = cot_feed.publication_datetime(dt.date.fromisoformat(r['report_date']))
                rows.append([ns(pub.astimezone(UTC)), conf, bool(delayed)] + [r.get(c) for c in cols])
            kept, later = self.keep(rows)
            self.points[f'cot.{code}'] = table(lead + names, kept,
                                               source=store.get('source'), vintage='CFTC archive as retrieved',
                                               native_resolution='weekly (positions as of Tuesday)', after_halt=later,
                                               note='every report published before the halt; percentiles are the feed\'s '
                                                    'per-report trailing windows (None when the window is short)')
            if not kept:
                self.lack(f'cot.{code}', 'no report of this code published before the halt')

    # 11
    def storage(self):
        key = f'{self.fam['storage']}/storage/lower48_weekly_levels.json'
        if not (self.src / key).is_file():
            return self.lack('storage.weekly', 'no EIA weekly storage file under the day-history run')
        levels = {}
        for r in self.read(key):
            try:
                levels[dt.date.fromisoformat(r['period'])] = float(r['value'])
            except (KeyError, TypeError, ValueError):
                self.lack('storage.weekly', 'unreadable row %r' % (r,))
        printed = self.as_printed().get('reports', {})
        rows = []
        for week in sorted(levels):
            thu = week + dt.timedelta(days=6)
            pub = dt.datetime(thu.year, thu.month, thu.day, 10, 30, tzinfo=ET).astimezone(UTC)
            prev = levels.get(week - dt.timedelta(days=7))
            iso = week.isocalendar()[1]
            prior = [(w.year, levels[w]) for w in levels if w.isocalendar()[1] == iso and week.year - 5 <= w.year < week.year]
            vs5 = round(levels[week] - sum(v for _, v in prior) / len(prior), 1) if len(prior) == 5 else None
            level, chg = levels[week], None if prev is None else round(levels[week] - prev, 1)
            five, year_ago, source = None, None, 'EIA API v2 natural-gas/stor/wkly NW2_EPG0_SWO_R48_BCF'
            p = printed.get(week.isoformat())
            if p:                    # Greg 2026-10-07: the value as published at the time, where the archive holds it
                pub = dt.datetime.fromisoformat(p['print_datetime_et']).astimezone(UTC)
                level = float(p['level_bcf']) if p.get('level_bcf') is not None else level
                chg = float(p['net_change_bcf']) if p.get('net_change_bcf') is not None else chg
                five, year_ago = p.get('five_year_avg_bcf'), p.get('year_ago_bcf')
                vs5 = round(level - five, 1) if five is not None else vs5
                source = p['source']
            rows.append([ns(pub), week.isoformat(), level, chg, vs5, prior, five, year_ago, source])
        kept, later = self.keep(rows)
        self.points['storage.weekly'] = table(
            ['published_ns', 'week_ending', 'level_bcf', 'weekly_chg_bcf', 'vs_5yr_bcf', 'same_week_prior_5y_levels',
             'five_yr_avg_bcf', 'year_ago_bcf', 'source'], kept,
            source='EIA Weekly Natural Gas Storage Report as printed (archived report pages, as_printed family) where '
                   'held; otherwise EIA API v2 natural-gas/stor/wkly NW2_EPG0_SWO_R48_BCF', vintage='as published',
            native_resolution='weekly (week ending Friday)', after_halt=later,
            note='published Thursday 10:30 ET after the week (rule; no holiday moved a late-September/October print); '
                 'vs_5yr is EIA\'s own comparison (the printed level minus the printed five-year average when the '
                 'report is held, else the level minus the same week\'s five prior-year levels, all five listed beside '
                 'it); None when fewer than five prior years exist; each row names its source')

    def as_printed(self):
        """The as_printed family's storage_as_printed.json ({} when absent; the absence is listed once)."""
        if getattr(self, '_as_printed', None) is None:
            key = f'{self.fam["as_printed"]}/as_printed/storage_as_printed.json'
            if (self.src / key).is_file():
                self._as_printed = self.read(key)
            else:
                self._as_printed = {}
                self.lack('as_printed', 'no as_printed/storage_as_printed.json under %s (storage stays the EIA series; '
                          'the estimate is not available)' % self.fam['as_printed'])
        return self._as_printed

    # 12
    def estimate(self):
        """The street estimate against the printed actual, per print published before the halt (values, not pages)."""
        doc = self.as_printed()
        if not doc:
            return self.lack('storage.estimate', 'no as_printed file (see as_printed)')
        # one row per EIA print of the as_printed document (review E-2): a print whose estimate was not found keeps its row
        # with estimate_bcf None and the reason, so a reader sees the latest print as missing, never an older print's value
        reasons = {m['print_date']: m['reason'] for m in doc.get('missing') or [] if m.get('field') == 'estimate'}
        ests = doc.get('estimates') or {}
        rows = []
        for pr in sorted(set(doc.get('prints') or []) | set(ests)):
            e = ests.get(pr)
            p = dt.date.fromisoformat(pr)
            at = e['print_datetime_et'] if e else dt.datetime(p.year, p.month, p.day, 10, 30, tzinfo=ET).isoformat()
            t = ns(dt.datetime.fromisoformat(at).astimezone(UTC))
            if e:
                est, act = e.get('estimate_bcf'), e.get('actual_bcf')
                rows.append([t, t, pr, e.get('week_ending'), est, act,
                             None if est is None or act is None else round(act - est, 1), e.get('source'), None])
            else:
                rows.append([t, t, pr, (p - dt.timedelta(days=6)).isoformat(), None, None, None, None,
                             reasons.get(pr, 'no street estimate found for this print')])
        kept, later = self.keep(rows)
        self.points['storage.estimate'] = table(
            ['published_ns', 'print_ns', 'print_date', 'week_ending', 'estimate_bcf', 'actual_bcf', 'surprise_bcf', 'source',
             'missing_reason'],
            kept, source='street estimate (TradingEconomics consensus / investing.com forecast, archived calendar pages and '
            'the investing.com event-386 chart feed) and the printed actual (EIA report as printed)', vintage='as published',
            native_resolution='per weekly print (one row per print, found or not)',
            after_halt=later, note='a print\'s estimate is public before the print; the row is placed at the print '
                                   '(10:30 ET Thursday); surprise = actual minus estimate; estimate_bcf None with '
                                   'missing_reason = the estimate of that print was not found (never filled from another print)')
        recent = (self.date - dt.timedelta(days=8)).isoformat()
        for m in doc.get('missing') or []:       # the prints of this day's week that the archive does not hold
            if m.get('print_date') and recent <= m['print_date'] <= self.date.isoformat():
                self.lack('storage.estimate' if m.get('field') == 'estimate' else 'storage.weekly.as_printed',
                          '%s: %s' % (m['print_date'], m['reason']))

    # 10
    def weather(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import nws_temp_feed as ntf
        months = sorted({(self.date - dt.timedelta(days=k)).strftime('%Y%m') for k in range(0, 12)})
        per_station, hourly, cols = {}, [], set()
        for st in ntf.RAW_STATIONS:
            obs = []
            for ym in months:
                key = f'{self.fam['weather_obs']}/weather_obs/{st}_{ym}.json'
                if not (self.src / key).is_file():
                    self.lack('weather.obs_hourly', f'{st} {ym}: no observation file')
                    continue
                for r in self.read(key):
                    try:
                        t = dt.datetime.strptime(r['valid'], '%Y-%m-%d %H:%M').replace(tzinfo=UTC)
                    except (KeyError, ValueError):
                        continue
                    obs.append((t, r))
            rows_for_daily = []
            for t, r in obs:
                rows_for_daily.append((t, ntf._parse_temp(r.get('tmpf', 'M')), ntf._parse_precip(r.get('p01i', 'M'))))
                if self.open_ns - 72 * 3600 * 10**9 <= ns(t) and ns(t) + OBS_LAG_NS < self.halt_ns:
                    cols.update(r)
                    hourly.append((ns(t) + OBS_LAG_NS, st, r))
            if st in ntf.STATION_WEIGHTS_RAW:
                per_station[st] = ntf.daily_from_obs(rows_for_daily)
        cols = sorted(cols - {'station', 'valid'})
        self.points['weather.obs_hourly'] = table(
            ['published_ns', 'station', 'valid_utc'] + cols,
            [[p, st, r.get('valid')] + [r.get(c) for c in cols] for p, st, r in sorted(hourly, key=lambda x: (x[0], x[1]))],
            source='IEM ASOS (nws_temp_feed.fetch_asos_raw)', vintage='archive as retrieved',
            native_resolution='every observation (hourly routine + specials), every field verbatim',
            note='from 72 h before the open to the halt; public ~10 min after its time (nominal)')
        gw = ntf.gas_weighted(per_station)
        rows = []
        for gas_day, v in sorted(gw.items()):
            d = dt.date.fromisoformat(gas_day) + dt.timedelta(days=1)
            end = dt.datetime(d.year, d.month, d.day, tzinfo=CT).astimezone(UTC)
            rows.append([ns(end) + OBS_LAG_NS, gas_day, v['gw_hdd'], v['gw_cdd'], v['gw_precip'], v['n_stations'],
                         v['coverage'], v['regime']])
        kept, later = self.keep(rows)
        self.points['weather.gw_daily'] = table(
            ['published_ns', 'gas_day', 'gw_hdd', 'gw_cdd', 'gw_precip', 'n_stations', 'coverage', 'regime'], kept,
            source='nws_temp_feed.daily_from_obs + gas_weighted', vintage='archive as retrieved',
            native_resolution='per gas day (America/Chicago)', after_halt=later,
            note='a gas day\'s index exists when it ends (00:00 CT next day, + 10 min); ' + SERIES_STATIONS_NOTE)

    # 2, 9
    def mos(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import nws_temp_feed as ntf
        runs = {}
        conflicts = 0
        for path in sorted(glob.glob(str(self.src / self.fam['mos'] / 'mos' / 'raw' / '*.json'))):
            name = Path(path).stem.split('_')
            if len(name) != 4:
                continue
            st, model, sts, ets = name
            if not (sts <= self.date.isoformat() <= ets):
                continue
            for r in self.read(str(Path(path).relative_to(self.src))):
                per = runs.setdefault((st, model), {}).setdefault(r['runtime'], {})
                if r['ftime'] in per and per[r['ftime']] != r['tmp']:
                    conflicts += 1
                per[r['ftime']] = r['tmp']
        if not runs:
            return self.lack('mos', 'no MOS raw file covering the day under the day-history run')
        lo = self.open_ns - 72 * 3600 * 10**9
        raw_rows = []
        for (st, model), per in runs.items():
            for rt, fc in per.items():
                t = ns(ntf._parse_ts(rt))
                if t >= lo and t + MOS_LAG_NS < self.halt_ns:
                    raw_rows += [[t + MOS_LAG_NS, st, model, rt, ft, tmp] for ft, tmp in sorted(fc.items())]
        self.points['mos.raw'] = table(['published_ns', 'station', 'model', 'runtime_utc', 'valid_utc', 'tmp_f'],
                                       sorted(raw_rows), source='IEM MOS archive (nws_temp_feed.fetch_mos)',
                                       vintage='archive as retrieved', native_resolution='per model cycle, every valid time',
                                       note='cycles initialized from 72 h before the open; public at runtime + 4.5 h '
                                            '(conservative); %d conflicting duplicate rows across files' % conflicts)
        w = ntf.station_weights()
        targets = [(self.date + dt.timedelta(days=h)).isoformat() for h in range(0, 8)]
        gw_rows, per_cycle = [], {}
        for (st, model), per in runs.items():
            for rt, fc in per.items():
                t = ns(ntf._parse_ts(rt))
                if not (t >= lo and t + MOS_LAG_NS < self.halt_ns):
                    continue
                for h, target in enumerate(targets):
                    mm = ntf._day_temp_from_run(fc, target, ntf.MOS_MIN_OBS[model])
                    if mm is not None:
                        hdd, cdd = ntf.degree_days((mm[0] + mm[1]) / 2.0)
                        per_cycle.setdefault((model, rt, h), {})[st] = (hdd, cdd)
        for (model, rt, h), stations in sorted(per_cycle.items()):
            wsum = sum(w[s] for s in stations if s in w)
            if wsum <= 0:
                continue
            gw_rows.append([ns(ntf._parse_ts(rt)) + MOS_LAG_NS, model, rt, targets[h], h,
                            round(sum(w[s] * v[0] for s, v in stations.items() if s in w) / wsum, 3),
                            round(sum(w[s] * v[1] for s, v in stations.items() if s in w) / wsum, 3),
                            len([s for s in stations if s in w]), round(wsum, 4),
                            sorted(s for s in ntf.STATION_WEIGHTS_RAW if s not in stations)])
        self.points['mos.gw_by_cycle'] = table(
            ['published_ns', 'model', 'runtime_utc', 'target_day', 'horizon_days', 'gw_hdd', 'gw_cdd', 'n_metros',
             'coverage', 'metros_missing'], sorted(gw_rows),
            source='nws_temp_feed (_day_temp_from_run, degree_days, station_weights) per cycle',
            vintage='archive as retrieved', native_resolution='per model cycle x target day',
            note='forecast_gw_hdd per cycle and model for D..D+7 (the feed\'s D-1-evening as-of is one of these '
                 'cycles); weights renormalized over the metros present, the missing ones named')
        dis = []
        rts = sorted({rt for (m, rt, h) in per_cycle if m == 'GFS'} & {rt for (m, rt, h) in per_cycle if m == 'NAM'})
        for rt in rts:
            spreads = []
            for h in range(8):
                a, b = per_cycle.get(('GFS', rt, h)), per_cycle.get(('NAM', rt, h))
                if not a or not b:
                    continue
                common = sorted(s for s in a if s in b and s in w)
                wsum = sum(w[s] for s in common)
                if wsum <= 0:
                    continue
                ga = sum(w[s] * a[s][0] for s in common) / wsum
                gb = sum(w[s] * b[s][0] for s in common) / wsum
                spreads.append((h, round(ga - gb, 3), len(common)))
            if spreads:
                top = max(spreads, key=lambda x: abs(x[1]))
                dis.append([ns(ntf._parse_ts(rt)) + MOS_LAG_NS, rt, abs(top[1]), top[0], spreads])
        self.points['mos.disagreement_by_cycle'] = table(
            ['published_ns', 'runtime_utc', 'max_abs_spread_gw_hdd', 'at_horizon_days', 'spreads_by_horizon'], dis,
            source='GFS-MOS minus NAM-MOS gw_hdd on the common metro set, per shared cycle (model_disagreement.py\'s '
                   'measure at cycle resolution)', vintage='archive as retrieved', native_resolution='per model cycle',
            note='every matched horizon listed as (horizon, spread, common metros); the max is over those horizons')

    # 5, 7
    def eia930(self):
        base = self.src / self.eia_hp / 'eia930' / self.date.isoformat()
        if not base.is_dir():
            return self.lack('eia930', 'no EIA-930 hourly files for the day under the day-history run %s' % self.eia_hp)
        rows, us48 = [], {}
        for path in sorted(base.glob('*.json')):
            route, ba = path.stem.rsplit('_', 1)
            for r in self.read(str(path.relative_to(self.src))):
                try:
                    t = dt.datetime.strptime(r['period'], '%Y-%m-%dT%H').replace(tzinfo=UTC)
                    v = None if r.get('value') in (None, '') else float(r['value'])
                except (KeyError, ValueError):
                    self.lack('eia930.hourly', 'unreadable row %r' % (r,))
                    continue
                kind = r.get('fueltype') or r.get('type')
                rows.append([ns(t) + EIA930_LAG_NS, r['period'], r.get('respondent', ba), route, kind, v, r.get('value-units')])
                if r.get('respondent', ba) == 'US48' and route == 'fuel-type-data' and kind in ('WND', 'NG'):
                    us48.setdefault(r['period'], {})[kind] = v
        kept, later = self.keep(rows)
        self.points['eia930.hourly'] = table(
            ['published_ns', 'period_utc', 'respondent', 'route', 'fueltype_or_type', 'value', 'units'],
            sorted(kept, key=lambda r: (r[0], str(r[2]), r[3], str(r[4]))),
            source='EIA API v2 electricity/rto fuel-type-data + region-data, frequency=hourly', vintage='current revision '
            '(the first-published value is not recoverable)', native_resolution='hourly', after_halt=later,
            note='from 8 days before the open; published_ns = period + 2 h (nominal)')
        u = []
        for period, v in sorted(us48.items()):
            t = dt.datetime.strptime(period, '%Y-%m-%dT%H').replace(tzinfo=UTC)
            gas = v.get('NG')
            u.append([ns(t) + EIA930_LAG_NS, period, v.get('WND'), gas,
                      None if gas is None else round(gas * 24 * 7900 / 1.035e9, 3)])
        kept, later = self.keep(u)
        self.points['eia930.us48'] = table(
            ['published_ns', 'period_utc', 'wind_mwh', 'gas_mwh', 'est_gas_burn_bcfd_rate'], kept,
            source='eia930.hourly, US48 rows', vintage='current revision', native_resolution='hourly', after_halt=later,
            note='est_gas_burn_bcfd_rate = gas MWh in the hour x 24 x 7,900 Btu/kWh / 1.035e9 (grid_stack\'s stated '
                 'method, an ESTIMATE); the other six respondents are in eia930.hourly')

    # 13
    def curve(self, src_curve=None):
        import databento_dbn as dbn
        import zstandard as zstd
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        import forward_curve
        base = Path(src_curve) if src_curve else self.src / CURVE_PREFIX
        parts = [(self.date - dt.timedelta(days=1)).strftime('%Y%m%d'), self.day]

        kinds = dict(definition=dbn.InstrumentDefMsg, statistics=dbn.StatMsg, mbo=dbn.MBOMsg)

        def records(schema, part):
            """Every record of the schema's type in the native file (multi-frame zstd, as mbo_source reads it); any
            other record type is counted in `other_records`, never an error and never silently taken."""
            path = base / schema / 'native' / f'glbx-mdp3-{part}.{schema}.dbn.zst'
            if not path.is_file():
                self.lack('curve.' + schema, f'{path.name}: not on the box (pull_curve_days.py output)')
                return
            raw = path.read_bytes()
            entry = dict(key=f'{CURVE_PREFIX}/{schema}/native/{path.name}', bytes=len(raw), sha256=sha256_bytes(raw),
                         manifest_checked=False, other_records=0)
            self.inputs.append(entry)
            decoder = dbn.DBNDecoder(upgrade_policy=dbn.VersionUpgradePolicy.AS_IS)
            position, unzip = 0, None
            while position < len(raw) or unzip is not None:
                if unzip is None:
                    unzip = zstd.ZstdDecompressor().decompressobj()
                data = raw[position:position + (1 << 22)]
                position += len(data)
                out = unzip.decompress(data) if data else b''
                if unzip.eof:
                    tail = unzip.unused_data
                    position -= len(tail)
                    unzip = None
                elif not data:
                    raise StagingRefused(f'{path.name}: truncated zstd frame')
                for rec in decoder.write_and_decode(out):
                    if type(rec) is kinds[schema]:
                        yield rec
                    elif type(rec) is not dbn.Metadata:
                        entry['other_records'] += 1

        def num(x):
            try:
                return int(x)
            except (TypeError, ValueError):
                return int(getattr(x, 'value'))

        defs = {}
        for part in parts:
            for r in records('definition', part):
                if int(r.ts_recv) >= self.halt_ns:
                    continue
                defs[int(r.instrument_id)] = dict(ts=int(r.ts_recv), raw_symbol=str(r.raw_symbol),
                                                  instrument_class=str(r.instrument_class), expiration=int(r.expiration))
        self.points['curve.definitions'] = table(
            ['published_ns', 'instrument_id', 'raw_symbol', 'instrument_class', 'expiration_ns'],
            sorted([d['ts'], i, d['raw_symbol'], d['instrument_class'], d['expiration']] for i, d in defs.items()),
            source='Databento GLBX.MDP3 definition, NG.FUT parent', vintage='exchange', native_resolution='per instrument')
        outright = {i: d for i, d in defs.items() if OUTRIGHT.match(d['raw_symbol'])}
        stats, trades, undefined = [], [], 0
        for part in parts:
            for r in records('statistics', part):
                t = int(r.ts_recv)
                if t >= self.halt_ns:
                    continue
                p = int(r.price)
                stats.append([t, int(r.ts_event), int(r.ts_ref), int(r.instrument_id),
                              defs.get(int(r.instrument_id), {}).get('raw_symbol'), num(r.stat_type),
                              None if p == UNDEF_PRICE else p / 1e9, int(r.quantity), num(r.update_action),
                              num(r.stat_flags)])
            for r in records('mbo', part):
                if str(r.action) != 'T':
                    continue
                t = int(r.ts_recv)
                if t >= self.halt_ns:
                    continue
                p = int(r.price)
                if p == UNDEF_PRICE:
                    undefined += 1
                    continue
                trades.append([t, int(r.ts_event), int(r.instrument_id), defs.get(int(r.instrument_id), {}).get('raw_symbol'),
                               p / 1e9, int(r.size), str(r.side)])
        stats.sort(key=lambda x: x[0])
        trades.sort(key=lambda x: x[0])
        self.points['curve.statistics'] = table(
            ['published_ns', 'ts_event', 'ts_ref', 'instrument_id', 'raw_symbol', 'stat_type', 'price', 'quantity',
             'update_action', 'stat_flags'], stats, source='Databento GLBX.MDP3 statistics, NG.FUT parent',
            vintage='exchange', native_resolution='per statistics message',
            note='settlements (stat_type 3), open interest (9), session high/low, cleared volume and the rest, each at its '
                 'receive time; both UTC partitions of the day, up to the halt')
        self.points['curve.trades'] = table(
            ['published_ns', 'ts_event', 'instrument_id', 'raw_symbol', 'price', 'size', 'side'], trades,
            source='Databento GLBX.MDP3 mbo, NG.FUT parent, action T', vintage='exchange',
            native_resolution='every trade of every month and spread (not sampled)',
            note='%d trade records with an undefined price counted, not kept' % undefined)

        by_expiry = sorted((d['expiration'], i) for i, d in outright.items())

        def shape(prices, t):
            live = []
            for exp, i in by_expiry:
                if exp > t and i in prices:
                    live.append((exp, i))
                    if len(live) == N_RANKS:
                        break
            closes = {k: prices[i] for k, (_, i) in enumerate(live)}
            symbols = {k: outright[i]['raw_symbol'] for k, (_, i) in enumerate(live)}
            f = forward_curve.curve_features(closes, symbols)
            if f is None:
                return None
            return [symbols[0], symbols[1], f['front'], f['c1'], f['back_rank'], f['back'], f['slope_1'], f['slope_back'],
                    f['curvature'], round(f['front'] - f['c1'], 4), f['regime'], f['n_ranks']]

        cols = ['published_ns', 'front_symbol', 'next_symbol', 'front', 'c1', 'back_rank', 'back', 'slope_1', 'slope_back',
                'curvature', 'front_next_spread', 'regime', 'n_ranks']
        settled, prices, last = [], {}, None
        for s in stats:
            if s[5] == SETTLE_STAT and s[6] is not None and s[3] in outright:
                prices[s[3]] = s[6]
                cur = shape(prices, s[0])
                if cur is not None and cur != last:
                    settled.append([s[0]] + cur)
                    last = cur
        traded, prices, last = [], {}, None
        for tr in trades:
            if tr[2] in outright:
                prices[tr[2]] = tr[4]
                cur = shape(prices, tr[0])
                if cur is not None and cur != last:
                    traded.append([tr[0]] + cur)
                    last = cur
        note = ('forward_curve.curve_features over the outright months by expiry (up to %d ranks), recomputed at each '
                'change; front_next_spread = front minus next (the calendar-front pair); a month enters when it first '
                'has a price, so early ranks can be sparse (n_ranks says how many)' % N_RANKS)
        self.points['curve.settled_shape'] = table(cols, settled, source='curve.statistics settlements',
                                                   vintage='exchange', native_resolution='per settlement message', note=note)
        self.points['curve.traded_shape'] = table(cols, traded, source='curve.trades (last trade per month)',
                                                  vintage='exchange', native_resolution='per trade that changes the shape',
                                                  note=note)
        # Greg 2026-10-07: the squeeze 3-day calendar-front spread change is dropped from the research (not one of the 13;
        # point 6 stays); it is not listed as missing. The front/next spread itself is in curve.settled_shape.

    # every gap the fetch recorded that touches the day: listed as missing with the fetch's own reason (Greg: no data
    # dropped, missing is LISTED, the day is never skipped)
    def source_gaps(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fetch_day_history import storage_prints_around
        prints = {p['release_et'][:10] for p in storage_prints_around(self.date)}
        months = {(self.date - dt.timedelta(days=k)).strftime('%Y-%m') for k in range(0, 12)}
        # a print after the trading day cannot touch it (its gap is the later day's, never this day's missing item)
        prints = {p for p in prints if p <= self.date.isoformat()}
        touching = {self.date.isoformat(), 'all', str(self.date.year)} | prints | months
        for fam in self.FAMILIES:
            prefix = self.fam[fam]
            key = f'{prefix}/{fam}/receipt.json'
            if not (self.src / key).is_file():
                self.lack(fam + '.fetch', 'no %s receipt under %s (the family was not fetched in that run)' % (fam, prefix))
                continue
            for g in self.read(key).get('gaps') or []:
                if str(g.get('day')) in touching:
                    self.lack(fam + '.fetch_gap', '%s (fetch gap keyed %s in %s)' % (g.get('reason'), g.get('day'), prefix))

    def place(self):
        """Every table gets its 99 mapping (POINT_REGISTRY_MAP) and every row its reader stamp: event_time_ns (the row's
        own event time, None when it has none) and published_ns = max(event time, publication); a row with no event
        time sits at 14:00 ET of the trading day unless published later (Greg 2026-10-07). Every reader of the file
        (the shared market reader, the classroom, the search) then sees one time per row. A row placed at or after the
        halt leaves the day (counted in after_halt)."""
        default = _et_ns(self.date.isoformat(), *DEFAULT_PLACEMENT_ET)
        for name, t in self.points.items():
            mapping = registry_map_for(name)
            if mapping is None:
                self.lack(name, 'no 99 mapping for this table (POINT_REGISTRY_MAP)')
            else:
                t.update({k: (list(v) if isinstance(v, list) else v) for k, v in mapping.items()})
            rule = next((EVENT_TIME_RULES[k] for k in sorted(EVENT_TIME_RULES, key=len, reverse=True)
                         if name == k or (k.endswith('.') and name.startswith(k))), None)
            cols = t['columns']
            if 'event_time_ns' in cols:
                continue
            i = cols.index(t['stamp_column'])
            rows, later = [], 0
            for r in t['rows']:
                ev = rule(cols, r) if rule else None
                stamp = max(ev, r[i]) if ev is not None else max(default, r[i])
                r = list(r)
                r[i] = stamp
                if stamp >= self.halt_ns:
                    later += 1
                    continue
                rows.append(r[:i + 1] + [ev] + r[i + 1:])
            t['columns'] = cols[:i + 1] + ['event_time_ns'] + cols[i + 1:]
            t['rows'] = sorted(rows, key=lambda r: r[i]) if later or any(
                rows[k][i] > rows[k + 1][i] for k in range(len(rows) - 1)) else rows
            t['after_halt'] = (t.get('after_halt') or 0) + later
            if mapping and mapping.get('event_time_basis') == 'default_1400':
                t['placement_ns'] = default

    def run(self, with_curve=True, src_curve=None):
        for piece in (self.calendar, self.cot, self.storage, self.estimate, self.weather, self.mos, self.eia930,
                      self.source_gaps):
            try:
                piece()
            except StagingRefused:
                raise
            except Exception as exc:          # a source that fails is listed, the others go on
                self.lack(piece.__name__, f'{type(exc).__name__}: {exc}')
        if with_curve:
            try:
                self.curve(src_curve)
            except StagingRefused:
                raise
            except Exception as exc:
                self.lack('curve', f'{type(exc).__name__}: {exc}')
        else:
            self.lack('curve', 'not built in this run (--no-curve)')
        self.place()
        body = dict(schema=SCHEMA, trading_day=self.day, open_utc=self.open.isoformat(), halt_utc=self.halt.isoformat(),
                    open_ns=self.open_ns, halt_ns=self.halt_ns, built_utc=dt.datetime.now(UTC).isoformat(),
                    history_prefix=self.hp, eia930_history_prefix=self.eia_hp,
                    family_history_prefixes=dict(self.fam), inputs=self.inputs, points=self.points, missing=self.missing,
                    point_registry_map=POINT_REGISTRY_MAP, placement_et='%02d:%02d' % DEFAULT_PLACEMENT_ET,
                    placement_note=DEFAULT_PLACEMENT_NOTE,
                    guard='time only: every row carries published_ns = max(event_time_ns, publication) < halt_ns; read '
                          'through AsOfReader')
        check_day_file(body)
        return body


# ------------------------------------------------------------------------------------------------ guard and reader

def check_day_file(body):
    """The staging check: refuses a row without a stamp, a stamp that is not an integer, or one at/after the halt."""
    if body.get('schema') != SCHEMA:
        raise StagingRefused('not a %s document' % SCHEMA)
    day = str(body.get('trading_day', ''))
    if len(day) != 8 or not day.isdigit():
        raise StagingRefused('trading_day YYYYMMDD required')
    opened, halted = session(day)
    if body.get('open_ns') != ns(opened) or body.get('halt_ns') != ns(halted):
        raise StagingRefused('day bounds do not belong to trading_day %s' % day)
    halt = body['halt_ns']
    for name, t in body['points'].items():
        if len(set(t['columns'])) != len(t['columns']):
            raise StagingRefused('%s repeats a column name' % name)
        i = t['columns'].index(t['stamp_column'])
        ev = t['columns'].index('event_time_ns') if 'event_time_ns' in t['columns'] else None
        for n, row in enumerate(t['rows']):
            if len(row) != len(t['columns']):
                raise StagingRefused('%s row %d has %d values for %d columns' % (
                    name, n, len(row), len(t['columns'])))
            stamp = row[i]
            if not isinstance(stamp, int) or isinstance(stamp, bool):
                raise StagingRefused('%s row %d has no integer publication stamp (%r)' % (name, n, stamp))
            if stamp >= halt:
                raise StagingRefused('%s row %d is stamped %d, at or after the halt %d' % (name, n, stamp, halt))
            if ev is not None:
                event = row[ev]
                if event is not None and (not isinstance(event, int) or isinstance(event, bool) or event > stamp):
                    raise StagingRefused('%s row %d: event_time_ns %r is not an integer at or before its reader stamp %d'
                                         % (name, n, event, stamp))
    return True


def computation_receipt(reader, day):
    """Read every native row/field through the time guard; retain exact scoped counts and source identities.

    Equal published values on adjacent days are legal. No value is changed to make days look different.
    Row-order changes are descriptive counts, not evidence of a relationship between unrelated entities.
    """
    if reader.body['trading_day'] != day:
        raise StagingRefused('external trading_day differs from the day being calculated')
    points = {}
    for name in reader.body['points']:
        t = reader.point(name)
        fields = {c: dict(values=0, null=0, numeric=0, text=0, structured=0,
                          comparable_adjacent=0, changed=0, unchanged=0) for c in t['columns']}
        previous = {}
        stream = hashlib.sha256()
        for row in t['rows']:
            stream.update((json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode())
            for column, value in zip(t['columns'], row):
                f = fields[column]
                f['values'] += 1
                f['null' if value is None else 'numeric' if isinstance(value, (bool, int, float))
                  else 'text' if isinstance(value, str) else 'structured'] += 1
                if column in previous and value is not None and previous[column] is not None:
                    f['comparable_adjacent'] += 1
                    f['unchanged' if value == previous[column] else 'changed'] += 1
                previous[column] = value
        points[name] = dict(rows=len(t['rows']), fields=fields, rows_sha256=stream.hexdigest(),
                            source=t.get('source'), vintage=t.get('vintage'),
                            native_resolution=t.get('native_resolution'), after_halt=t.get('after_halt', 0))
    return dict(schema='FRANKIE_DAY_EXTERNAL_COMPUTATION_V1', trading_day=day, cutoff_ns=reader.cutoff,
                points=points, missing=reader.body.get('missing', []),
                rows_read=sum(p['rows'] for p in points.values()),
                values_read=sum(f['values'] for p in points.values() for f in p['fields'].values()),
                rule='every native row and field read without limits, filling, averaging, smoothing or normalization')


class AsOfReader:
    """The one reader of a day file. cutoff_ns is the reader's decision time; nothing past it is ever handed out, and a
    request that would need it is refused (LeakRefused), never filtered silently."""

    def __init__(self, body, cutoff_ns):
        check_day_file(body)
        self.body, self.cutoff = body, int(cutoff_ns)

    @classmethod
    def open(cls, path, cutoff_ns, receipt=None):
        raw = Path(path).read_bytes()
        if receipt is not None:
            want = json.loads(Path(receipt).read_bytes())['sha256']
            if sha256_bytes(raw) != want:
                raise StagingRefused('%s differs from its receipt sha256' % path)
        return cls(json.loads(raw), cutoff_ns)

    def point(self, name):
        """The whole point; refused if any of its rows lies past the cutoff (read it with until= instead)."""
        t = self.body['points'][name]
        i = t['columns'].index(t['stamp_column'])
        late = [r[i] for r in t['rows'] if r[i] > self.cutoff]
        if late:
            raise LeakRefused('%s holds %d values past the cutoff %d (first at %d): read with until=<= cutoff'
                              % (name, len(late), self.cutoff, min(late)))
        return t

    def until(self, name, t_ns):
        """The rows of a point known at t_ns (stamp <= t_ns). A t_ns past the cutoff is refused. The count of rows not
        yet known at t_ns is returned beside them, so nothing is hidden."""
        if t_ns > self.cutoff:
            raise LeakRefused('%s asked at %d, past the cutoff %d' % (name, t_ns, self.cutoff))
        t = self.body['points'][name]
        i = t['columns'].index(t['stamp_column'])
        rows = [r for r in t['rows'] if r[i] <= t_ns]
        return dict(columns=t['columns'], rows=rows, not_yet_known=len(t['rows']) - len(rows))


SEARCH_SERIES = (   # (series name, point, value column, row filter) - the 13 points as series on the day's causal axis
    ('cot.managed_money_net_pctile_1y', 'cot.023651', 'managed_money_net_pctile_1y', None),
    ('cot.managed_money_net_chg_wow', 'cot.023651', 'managed_money_net_chg_wow', None),
    ('cot.managed_money_net_pctile_3y', 'cot.023651', 'managed_money_net_pctile_3y', None),
    ('cot.ice.ld1.managed_money_net_pctile_1y', 'cot.023391', 'managed_money_net_pctile_1y', None),
    ('mos.GFS.gw_hdd_D', 'mos.gw_by_cycle', 'gw_hdd', {'model': 'GFS', 'horizon_days': 0}),
    ('mos.NAM.gw_hdd_D', 'mos.gw_by_cycle', 'gw_hdd', {'model': 'NAM', 'horizon_days': 0}),
    ('mos.GFS.gw_hdd_D1', 'mos.gw_by_cycle', 'gw_hdd', {'model': 'GFS', 'horizon_days': 1}),
    ('mos.MEX.gw_hdd_D3', 'mos.gw_by_cycle', 'gw_hdd', {'model': 'MEX', 'horizon_days': 3}),
    ('mos.max_abs_spread_gw_hdd', 'mos.disagreement_by_cycle', 'max_abs_spread_gw_hdd', None),
    ('eia930.US48.wind_mwh', 'eia930.us48', 'wind_mwh', None),
    ('eia930.US48.est_gas_burn_bcfd_rate', 'eia930.us48', 'est_gas_burn_bcfd_rate', None),
    ('calendar.sessions_since_prompt_expiry', 'calendar.sessions_since_prompt_expiry', 'sessions_since_prompt_expiry', None),
    ('weather.gw_hdd', 'weather.gw_daily', 'gw_hdd', None),
    ('storage.level_bcf', 'storage.weekly', 'level_bcf', None),
    ('storage.weekly_chg_bcf', 'storage.weekly', 'weekly_chg_bcf', None),
    ('storage.vs_5yr_bcf', 'storage.weekly', 'vs_5yr_bcf', None),
    ('storage.estimate_bcf', 'storage.estimate', 'estimate_bcf', None),
    ('storage.actual_bcf', 'storage.estimate', 'actual_bcf', None),
    ('storage.surprise_bcf', 'storage.estimate', 'surprise_bcf', None),
    ('curve.settled.front', 'curve.settled_shape', 'front', None),
    ('curve.settled.slope_1', 'curve.settled_shape', 'slope_1', None),
    ('curve.settled.slope_back', 'curve.settled_shape', 'slope_back', None),
    ('curve.settled.curvature', 'curve.settled_shape', 'curvature', None),
    ('curve.settled.front_next_spread', 'curve.settled_shape', 'front_next_spread', None),
    ('curve.traded.front', 'curve.traded_shape', 'front', None),
    ('curve.traded.c1', 'curve.traded_shape', 'c1', None),
    ('curve.traded.slope_1', 'curve.traded_shape', 'slope_1', None),
    ('curve.traded.slope_back', 'curve.traded_shape', 'slope_back', None),
    ('curve.traded.curvature', 'curve.traded_shape', 'curvature', None),
    ('curve.traded.front_next_spread', 'curve.traded_shape', 'front_next_spread', None),
)


def search_series(reader):
    """{series: (known_at_ns list, values list)} for the search, through the reader (the whole day: cutoff = halt).
    Hourly station temperatures are added per weighted station. Missing points are returned in `absent`."""
    out, absent = {}, []
    for name, point, column, where in SEARCH_SERIES:
        if point not in reader.body['points']:
            absent.append(dict(series=name, point=point, reason='point not in the day file (see its missing list)'))
            continue
        t = reader.point(point)
        cols = t['columns']
        i, j = cols.index('published_ns'), cols.index(column)
        rows = t['rows']
        if where:
            rows = [r for r in rows if all(r[cols.index(k)] == v for k, v in where.items())]
        known = [r[i] for r in rows]
        vals = [r[j] if isinstance(r[j], (int, float)) and not isinstance(r[j], bool) else None for r in rows]
        if known:
            out[name] = (known, vals)
        else:
            absent.append(dict(series=name, point=point, reason='no rows'))
    if 'weather.obs_hourly' in reader.body['points']:
        t = reader.point('weather.obs_hourly')
        cols = t['columns']
        i, s = cols.index('published_ns'), cols.index('station')
        k = cols.index('tmpf') if 'tmpf' in cols else None
        by = {}
        for r in t['rows']:
            if k is None:
                break
            try:
                v = float(r[k])
            except (TypeError, ValueError):
                continue
            by.setdefault(r[s], ([], []))
            by[r[s]][0].append(r[i])
            by[r[s]][1].append(v)
        for st, (known, vals) in sorted(by.items()):
            out['weather.tmpf.' + st] = (known, vals)
    return out, absent


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--src', required=True, help='local mirror of the S3 keys')
    b.add_argument('--history-prefix', required=True, help='frankie/day_history/<run>')
    b.add_argument('--eia930-history-prefix', help='frankie/day_history/<run> of the eia930 family (default --history-prefix)')
    b.add_argument('--family-history-prefix', action='append', default=[],
                   help='family=frankie/day_history/<run>: that family from another run (repeatable)')
    b.add_argument('--curve-dir', help='default <src>/nymex/ng_fut_parent_v0')
    b.add_argument('--day', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--no-curve', action='store_true')
    c = sub.add_parser('check')
    c.add_argument('--file', required=True)
    a = p.parse_args()
    if a.cmd == 'check':
        check_day_file(json.loads(Path(a.file).read_bytes()))
        print('ok')
        return 0
    if not (len(a.day) == 8 and a.day.isdigit()):
        raise SystemExit('--day YYYYMMDD required')
    t0 = time.time()
    body = Build(a.src, a.history_prefix, a.day, a.eia930_history_prefix,
                 dict(x.split('=', 1) for x in a.family_history_prefix)).run(with_curve=not a.no_curve, src_curve=a.curve_dir)
    raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode()
    with open(a.out, 'xb') as f:
        f.write(raw)
    print(json.dumps(dict(day=a.day, out=a.out, bytes=len(raw), sha256=sha256_bytes(raw), seconds=round(time.time() - t0, 1),
                          points={k: len(v['rows']) for k, v in body['points'].items()}, missing=body['missing'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
