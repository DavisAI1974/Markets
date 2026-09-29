"""Frankie's 12 historical data points for the experiment's trading days: when each value became public (plan), a
1-2 minute probe of every free source (canary), and the fetch at NATIVE resolution (fetch). Greg, 2026-09-29: "find
the historical data that Frankie wants for the days it just picked. Some of this is hourly data, some isn't"; "it's 12
now"; "everyone who sees his ingest should see these data points too". Plan and reasons:
research/kalshi/frankie_boss/HISTORICAL_DATA_PLAN_20260929.md.

REUSE FIRST. Every fetch below calls the existing feed's own function where one exists and adds only what none has:
  weather_obs   nws_temp_feed.fetch_asos_raw           (IEM ASOS, hourly, every field verbatim) per station per month
  mos           nws_temp_feed.fetch_mos                (IEM MOS archive, every cycle, every valid time) per metro/model
  cot           cot_feed.download_archives + build     (CFTC disaggregated futures-only, weekly; 2018 onward)
  storage       EIA API v2 weekly working gas, the route eia_surprise.py reads (level per week; weekly change and
                vs-5yr are derived from levels, as forecast_harness._storage_series does)
  eia930        NEW (no hourly path exists; grid_stack.py pulls the DAILY routes): EIA API v2 electricity/rto
                fuel-type-data + region-data at frequency=hourly, UTC, the same seven respondents as grid_stack
  consensus     NEW (storage_consensus.py serves a store that was extracted by hand from Wayback snapshots,
                2025-08..2026-03; no code fetches it): the Wayback CDX listing + raw snapshots of the same pages
                (TradingEconomics, investing.com event 386) and of EIA's own WNGSR page (the as-printed actual) around
                each print; extraction is the next step once the real HTML is in hand
  calendar      flow_calendar.ng_expiry (squeeze_watch.sessions_since_prompt_expiry is pure calendar)

Nothing is rolled up or averaged here; raw rows are kept as served. Every fetch writes <out>/<family>/receipt.json with
the URLs (never a key), the retrieval time, each file's bytes and sha256, and every gap by day and reason. It writes
local files only; publishing to S3 is the workflow's step (frankie_day_history.yml). No Databento, no model call.

    python3.12 research/kalshi/frankie_boss/operations/fetch_day_history.py plan --out <file.json>     # offline
    python3.12 research/kalshi/frankie_boss/operations/fetch_day_history.py canary                     # network, ~1-2 min
    python3.12 research/kalshi/frankie_boss/operations/fetch_day_history.py fetch --family all --out <dir>
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[4]
KALSHI = REPO / 'research' / 'kalshi'
sys.path.insert(0, str(KALSHI))
CANDIDATES = REPO / 'research' / 'kalshi' / 'frankie_boss' / 'blocks' / 'DAY_SELECTION_CANDIDATES_20260929.json'
ET, UTC = ZoneInfo('America/New_York'), dt.timezone.utc
UA = 'Mozilla/5.0 (compatible; DavisAI-Markets/1.0; public research data)'
FAMILIES = ('calendar', 'cot', 'storage', 'consensus', 'weather_obs', 'mos', 'eia930')
EIA_API = 'https://api.eia.gov/v2'
STORAGE_SERIES = 'NW2_EPG0_SWO_R48_BCF'          # Lower-48 working gas, Bcf (eia_surprise.SERIES['KXNATGASD'])
EIA930_RESPONDENTS = ['US48', 'ERCO', 'CISO', 'MISO', 'PJM', 'SWPP', 'SOCO']     # grid_stack.RESPONDENTS
MOS_MODELS = ('GFS', 'NAM', 'MEX')              # nws_temp_feed.MOS_MODEL_ORDER
MOS_DISSEM_LAG_H = 4.5                          # mos_cycle_feed.DISSEM_LAG_H (conservative availability wall)
WAYBACK_PAGES = {                               # the pages STORAGE_CONSENSUS_NOTES_S98.md used, plus EIA's own report
    'tradingeconomics': 'tradingeconomics.com/united-states/natural-gas-stocks-change',
    'investing_www': 'www.investing.com/economic-calendar/natural-gas-storage-386',
    'investing_es': 'es.investing.com/economic-calendar/natural-gas-storage-386',
    'investing_mx': 'mx.investing.com/economic-calendar/natural-gas-storage-386',
    'eia_wngsr': 'ir.eia.gov/ngs/ngs.html',            # the as-printed actual (storage_vintage.py's source)
    'eia_wngsr_json': 'ir.eia.gov/ngs/wngsr.json',      # EIA's machine summary with its revision flags
}


def days_selected():
    body = json.loads(CANDIDATES.read_bytes())
    return [dt.date.fromisoformat(f'{d[:4]}-{d[4:6]}-{d[6:]}') for d in body['proposed']]


def session_bounds(day):
    """(open, halt) of trading day `day` in UTC: 18:00 ET the prior calendar day to 17:00 ET."""
    prior = day - dt.timedelta(days=1)
    return (dt.datetime(prior.year, prior.month, prior.day, 18, tzinfo=ET).astimezone(UTC),
            dt.datetime(day.year, day.month, day.day, 17, tzinfo=ET).astimezone(UTC))


def storage_prints_around(day):
    """(the last print strictly before the day opens, the next print after it), each as (release ET, week ending).
    Rule: Thursday 10:30 ET for the week ending the prior Friday. No federal holiday falls in the late-September to
    October weeks of 2021-2025 that moved a print (Columbus Day Monday does not; STORAGE_CONSENSUS_NOTES_S98 verified
    Oct 2025 against the archived release rows); the canary re-checks the release rows against EIA's own page."""
    open_utc, _ = session_bounds(day)
    thu = day + dt.timedelta(days=(3 - day.weekday()) % 7)
    nxt = dt.datetime(thu.year, thu.month, thu.day, 10, 30, tzinfo=ET)
    last = nxt - dt.timedelta(days=7)
    while last.astimezone(UTC) >= open_utc:
        last -= dt.timedelta(days=7)
    wk = lambda t: (t.date() - dt.timedelta(days=6)).isoformat()
    return (dict(release_et=last.isoformat(), week_ending=wk(last)), dict(release_et=nxt.isoformat(), week_ending=wk(nxt)))


def cot_visible(day):
    """The newest COT report public before the day opens (cot_feed's own publication rule and 2025 override table)."""
    import cot_feed
    open_utc, halt_utc = session_bounds(day)
    rd = day - dt.timedelta(days=(day.weekday() - 1) % 7)            # the Tuesday on or before the day
    seen = []
    for k in range(0, 20):
        r = rd - dt.timedelta(days=7 * k)
        pub, delayed, conf = cot_feed.publication_datetime(r)
        seen.append((r, pub, delayed, conf))
        if pub.astimezone(UTC) < open_utc:
            during = [dict(report_date=x[0].isoformat(), publication_et=x[1].isoformat())
                      for x in seen if open_utc <= x[1].astimezone(UTC) < halt_utc]
            return dict(report_date=r.isoformat(), publication_et=pub.isoformat(), delayed=delayed, confidence=conf,
                        age_days_at_open=round((open_utc - pub.astimezone(UTC)).total_seconds() / 86400, 2),
                        published_during_day=during,
                        needs_history_from=(r - dt.timedelta(days=1095)).isoformat())
    return None


def sessions_since_prompt_expiry(day):
    """forecast_harness's squeeze_watch rule with flow_calendar's own functions: business days since the most recent
    NG expiry strictly before the day. flow_calendar's CME holiday table covers 2025-2027; no CME holiday falls between
    a late-September expiry and a late-September/October day in 2021-2024 (Columbus Day trades), so the count holds."""
    import flow_calendar as fc
    y, m = day.year, day.month + 2
    if m > 12:
        m, y = m - 12, y + 1
    for _ in range(5):
        exp = fc.ng_expiry(y, m)
        if exp < day:
            return dict(last_prompt_symbol=fc.ng_symbol(y, m), last_prompt_expiry=exp.isoformat(),
                        sessions_since_prompt_expiry=fc.bd_between(exp, day))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return None


def mos_cycles(day):
    """MOS cycles (00/06/12/18Z) by availability = runtime + 4.5 h: those public at the open, those arriving during
    the day. The feed's current D-1-evening as-of (runtime <= D-1 23:59Z) is a different wall; both are listed."""
    open_utc, halt_utc = session_bounds(day)
    out = dict(at_open=[], during_day=[])
    start = dt.datetime(day.year, day.month, day.day, tzinfo=UTC) - dt.timedelta(days=2)
    for h in range(0, 72, 6):
        rt = start + dt.timedelta(hours=h)
        avail = rt + dt.timedelta(hours=MOS_DISSEM_LAG_H)
        if avail < open_utc and rt >= open_utc - dt.timedelta(hours=30):
            out['at_open'].append(dict(runtime_utc=rt.isoformat(), available_utc=avail.isoformat()))
        elif open_utc <= avail < halt_utc:
            out['during_day'].append(dict(runtime_utc=rt.isoformat(), available_utc=avail.isoformat()))
    return out


def plan(out_path):
    rows = []
    for day in days_selected():
        o, h = session_bounds(day)
        last, nxt = storage_prints_around(day)
        rows.append(dict(
            day=day.isoformat(), open_utc=o.isoformat(), halt_utc=h.isoformat(),
            cot=cot_visible(day), storage=dict(last_print_before_open=last, next_print=nxt),
            consensus=dict(for_next_print=nxt['release_et'], for_last_print=last['release_et']),
            squeeze_watch=sessions_since_prompt_expiry(day), mos=mos_cycles(day),
            weather_obs=dict(hours_utc=[o.isoformat(), h.isoformat()], gas_day_gw_hdd_known_at_open=(
                day - dt.timedelta(days=2)).isoformat(), note='realized gw_hdd of a gas day (America/Chicago) is complete '
                'at its end; the gas day that ended before the open is D-2 (D-1 ends at 00:00 CT on D, inside the day)'),
            eia930=dict(hours_utc=[(o - dt.timedelta(days=8)).isoformat(), h.isoformat()],
                        availability='nominal: an hour is public about one hour after it ends (EIA-930 hourly '
                                     'collection); the API serves the CURRENT revision, not the first-published one')))
    Path(out_path).write_text(json.dumps(dict(schema='FRANKIE_DAY_HISTORY_AVAILABILITY_V1', source='offline: calendar '
                                              'rules and the feeds\' own publication rules; no network', days=rows),
                                         indent=1, sort_keys=True) + '\n', encoding='utf-8')
    for r in rows:
        c = r['cot'] or {}
        print(r['day'], 'cot', c.get('report_date'), 'pub', (c.get('publication_et') or '')[:16], 'age', c.get('age_days_at_open'),
              '| storage last', r['storage']['last_print_before_open']['release_et'][:10],
              'next', r['storage']['next_print']['release_et'][:10],
              '| sessions_since_expiry', (r['squeeze_watch'] or {}).get('sessions_since_prompt_expiry'))
    return 0


# ---------------------------------------------------------------------------------------------------- network pieces

def http_get(url, params=None, timeout=120, headers=None):
    if params:
        url = url + ('&' if '?' in url else '?') + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def redact(url):
    return url.split('api_key=')[0] + ('api_key=<redacted>' if 'api_key=' in url else '')


class Receipt:
    def __init__(self, out, family):
        self.dir = Path(out) / family
        self.dir.mkdir(parents=True, exist_ok=True)
        self.body = dict(family=family, started_utc=dt.datetime.now(UTC).isoformat(), files=[], requests=[], gaps=[])

    def save(self, name, data, url=None):
        path = self.dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = data if isinstance(data, bytes) else json.dumps(data, sort_keys=True).encode()
        path.write_bytes(raw)
        self.body['files'].append(dict(path=str(path.relative_to(self.dir)), bytes=len(raw),
                                       sha256=hashlib.sha256(raw).hexdigest(), url=redact(url) if url else None))

    def gap(self, day, reason):
        self.body['gaps'].append(dict(day=day, reason=reason))
        print('GAP', self.body['family'], day, reason, flush=True)

    def close(self):
        self.body['finished_utc'] = dt.datetime.now(UTC).isoformat()
        (self.dir / 'receipt.json').write_text(json.dumps(self.body, indent=1, sort_keys=True), encoding='utf-8')


def eia_key():
    key = os.environ.get('EIA_API_KEY', '')
    return key if key and not key.startswith('proxy-injected') else 'DEMO_KEY'


def eia_paged(route, params):
    rows, offset = [], 0
    while True:
        status, raw = http_get(f'{EIA_API}/{route}/data/', dict(params, api_key=eia_key(), length=5000, offset=offset))
        resp = json.loads(raw)['response']
        rows.extend(resp['data'])
        offset += len(resp['data'])
        if offset >= int(resp['total']) or not resp['data']:
            return rows


def windows_by_year(days, before, after):
    """One [start, end] per year spanning that year's days, padded; never pooled across years."""
    out = {}
    for d in days:
        lo, hi = out.get(d.year, (d, d))
        out[d.year] = (min(lo, d), max(hi, d))
    return {y: (lo - dt.timedelta(days=before), hi + dt.timedelta(days=after)) for y, (lo, hi) in sorted(out.items())}


def fetch_calendar(out):
    rec = Receipt(out, 'calendar')
    rec.save('sessions_since_prompt_expiry.json', {d.isoformat(): sessions_since_prompt_expiry(d) for d in days_selected()})
    rec.close()


def fetch_cot(out):
    import cot_feed
    rec = Receipt(out, 'cot')
    data_dir = str(rec.dir / 'store')
    years = tuple(range(2018, max(d.year for d in days_selected()) + 1))
    for code in cot_feed.SERVED_CONTRACT_CODES:
        try:
            store = cot_feed.build(data_dir=data_dir, contract_code=code, years=years)
            rec.body['requests'].append(dict(contract_code=code, n_reports=store['n_reports'], years=list(years)))
        except SystemExit as exc:
            rec.gap('all', f'contract {code}: {exc}')
    for p in sorted(Path(data_dir).rglob('*')):
        if p.is_file():
            rec.save(str(Path('store') / p.relative_to(data_dir)), p.read_bytes())
    rec.close()


def fetch_storage(out):
    rec = Receipt(out, 'storage')
    first = min(days_selected()) - dt.timedelta(days=366 * 6)      # 5-year comparisons need five prior years
    params = {'frequency': 'weekly', 'data[0]': 'value', 'facets[series][]': STORAGE_SERIES,
              'start': first.isoformat(), 'sort[0][column]': 'period', 'sort[0][direction]': 'asc'}
    try:
        rows = eia_paged('natural-gas/stor/wkly', params)
        rec.save('lower48_weekly_levels.json', rows, url=f'{EIA_API}/natural-gas/stor/wkly/data/?series={STORAGE_SERIES}')
    except Exception as exc:
        rec.gap('all', f'EIA weekly storage: {exc!r}')
    rec.close()


def fetch_consensus(out):
    rec = Receipt(out, 'consensus')
    prints = sorted({p['release_et'][:10] for d in days_selected() for p in storage_prints_around(d)})
    rec.body['prints'] = prints
    for name, page in WAYBACK_PAGES.items():
        for pr in prints:
            p = dt.date.fromisoformat(pr)
            lo, hi = (p - dt.timedelta(days=6)).strftime('%Y%m%d'), (p + dt.timedelta(days=8)).strftime('%Y%m%d')
            url = 'https://web.archive.org/cdx/search/cdx'
            try:
                _, raw = http_get(url, {'url': page, 'from': lo, 'to': hi, 'output': 'json',
                                        'fl': 'timestamp,original,statuscode,digest,length'}, timeout=90)
                listing = json.loads(raw or b'[]')
            except Exception as exc:
                rec.gap(pr, f'{name}: CDX listing failed {exc!r}')
                continue
            snaps = [dict(zip(listing[0], r)) for r in listing[1:]] if listing else []
            rec.save(f'cdx/{name}/{pr}.json', snaps, url=f'{url}?url={page}&from={lo}&to={hi}')
            if not snaps:
                rec.gap(pr, f'{name}: no Wayback snapshot {lo}..{hi}')
            for s in snaps:
                if s.get('statuscode') != '200':
                    continue
                raw_url = f"https://web.archive.org/web/{s['timestamp']}id_/{s['original']}"
                try:
                    _, html = http_get(raw_url, timeout=90)
                    rec.save(f"snapshots/{name}/{pr}/{s['timestamp']}.html", html, url=raw_url)
                except Exception as exc:
                    rec.gap(pr, f"{name}: snapshot {s['timestamp']} failed {exc!r}")
                time.sleep(1.0)                                # politeness to the Internet Archive
    rec.close()


def fetch_weather_obs(out):
    import nws_temp_feed as ntf
    rec = Receipt(out, 'weather_obs')
    months = sorted({(d - dt.timedelta(days=k)).strftime('%Y-%m') for d in days_selected() for k in (0, 1, 2)})
    for ym in months:
        y, m = int(ym[:4]), int(ym[5:])
        start = f'{ym}-01'
        end = f'{y + 1}-01-01' if m == 12 else f'{y}-{m + 1:02d}-01'
        for st in ntf.RAW_STATIONS:
            try:
                rows = ntf.fetch_asos_raw(st, start, end)
                rec.save(f'{st}_{ym.replace("-", "")}.json', rows, url=f'{ntf.IEM_URL}?station={st}&{start}..{end}')
                if not rows:
                    rec.gap(ym, f'{st}: no observations served')
            except Exception as exc:
                rec.gap(ym, f'{st}: {exc!r}')
            time.sleep(0.5)
    rec.close()


def fetch_mos(out):
    import nws_temp_feed as ntf
    rec = Receipt(out, 'mos')
    for year, (lo, hi) in windows_by_year(days_selected(), 3, ntf.MOS_HORIZONS + 1).items():
        sts, ets = lo.isoformat(), hi.isoformat()
        for st in ntf.STATION_WEIGHTS_RAW:
            for model in MOS_MODELS:
                try:
                    rows = ntf.fetch_mos('K' + st, model, sts, ets)
                    # the name nws_temp_feed.load_mos_cached uses, so model_disagreement/mos_cycle_feed read it as is
                    rec.save(f'raw/{st}_{model}_{sts}_{ets}.json', rows, url=f'{ntf.MOS_URL}?station=K{st}&model={model}')
                    if not rows:
                        rec.gap(str(year), f'{st} {model}: no MOS rows {sts}..{ets}')
                except Exception as exc:
                    rec.gap(str(year), f'{st} {model}: {exc!r}')
                time.sleep(0.4)
    rec.close()


def fetch_eia930(out):
    rec = Receipt(out, 'eia930')
    for d in days_selected():
        o, h = session_bounds(d)
        start = (o - dt.timedelta(days=8)).strftime('%Y-%m-%dT%H')
        end = h.strftime('%Y-%m-%dT%H')
        for route in ('fuel-type-data', 'region-data'):
            for ba in EIA930_RESPONDENTS:
                params = {'frequency': 'hourly', 'data[]': ['value'], 'facets[respondent][]': ba,
                          'start': start, 'end': end, 'sort[0][column]': 'period', 'sort[0][direction]': 'asc'}
                try:
                    rows = eia_paged(f'electricity/rto/{route}', params)
                    rec.save(f'{d.isoformat()}/{route}_{ba}.json', rows, url=f'{EIA_API}/electricity/rto/{route}/data/'
                             f'?frequency=hourly&respondent={ba}&start={start}&end={end}')
                    if not rows:
                        rec.gap(d.isoformat(), f'{route} {ba}: no hourly rows {start}..{end}')
                except Exception as exc:
                    rec.gap(d.isoformat(), f'{route} {ba}: {exc!r}')
    rec.close()


FETCH = dict(calendar=fetch_calendar, cot=fetch_cot, storage=fetch_storage, consensus=fetch_consensus,
             weather_obs=fetch_weather_obs, mos=fetch_mos, eia930=fetch_eia930)


def canary():
    """One small request per source: reachable, the format as the feeds expect, and 2021 coverage. ~1-2 minutes."""
    probes = [
        ('IEM ASOS hourly', 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py',
         dict(station='ORD', data='tmpf', year1=2021, month1=10, day1=4, year2=2021, month2=10, day2=5, tz='Etc/UTC',
              format='onlycomma', missing='M', trace='T')),
        ('IEM MOS', 'https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py',
         dict(station='KORD', model='GFS', sts='2021-10-03T00:00Z', ets='2021-10-03T23:59Z', format='csv')),
        ('CFTC 2018 archive', 'https://www.cftc.gov/files/dea/history/fut_disagg_txt_2018.zip', None),
        ('EIA storage weekly', f'{EIA_API}/natural-gas/stor/wkly/data/',
         {'api_key': eia_key(), 'frequency': 'weekly', 'data[0]': 'value', 'facets[series][]': STORAGE_SERIES,
          'start': '2021-09-24', 'end': '2021-10-15'}),
        ('EIA-930 hourly', f'{EIA_API}/electricity/rto/fuel-type-data/data/',
         {'api_key': eia_key(), 'frequency': 'hourly', 'data[]': ['value'], 'facets[respondent][]': 'US48',
          'start': '2021-10-04T00', 'end': '2021-10-04T03'}),
        ('Wayback CDX TradingEconomics', 'https://web.archive.org/cdx/search/cdx',
         dict(url=WAYBACK_PAGES['tradingeconomics'], **{'from': '20211001', 'to': '20211008'}, output='json')),
        ('Wayback CDX investing 386', 'https://web.archive.org/cdx/search/cdx',
         dict(url=WAYBACK_PAGES['investing_www'], **{'from': '20211001', 'to': '20211008'}, output='json')),
        ('Wayback CDX EIA WNGSR', 'https://web.archive.org/cdx/search/cdx',
         dict(url=WAYBACK_PAGES['eia_wngsr'], **{'from': '20211007', 'to': '20211008'}, output='json')),
    ]
    for name, url, params in probes:
        t0 = time.time()
        try:
            status, raw = http_get(url, params, timeout=60)
            head = raw[:300].decode('utf-8', 'replace').replace('\n', ' | ')
            key = eia_key()
            if key and key != 'DEMO_KEY':
                head = head.replace(key, '<redacted>')          # the EIA API echoes its request parameters
            print(f'OK   {name}: HTTP {status}, {len(raw)} bytes, {time.time() - t0:.1f}s: {head}', flush=True)
        except Exception as exc:
            print(f'FAIL {name}: {exc!r}', flush=True)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('plan'); a.add_argument('--out', required=True)
    sub.add_parser('canary')
    f = sub.add_parser('fetch'); f.add_argument('--family', required=True, help='all or a comma list of ' + ','.join(FAMILIES))
    f.add_argument('--out', required=True)
    args = p.parse_args()
    if args.cmd == 'plan':
        return plan(args.out)
    if args.cmd == 'canary':
        return canary()
    fams = FAMILIES if args.family == 'all' else tuple(x for x in args.family.split(',') if x)
    unknown = set(fams) - set(FAMILIES)
    if unknown:
        raise SystemExit(f'unknown families {sorted(unknown)}')
    for fam in fams:
        print(f'### {fam}', flush=True)
        FETCH[fam](args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
