"""Candidate Tuesday/Wednesday trading days for the experiment, per day, from COMMITTED metadata only (Greg, 2026-09-29:
"we have to start picking closely matched Tue and Wed. We can use the last week of Sept through this year. I'd like to
have 30 days when we're done." and "The historical data days should be in aws.").

Reads nothing but the committed canonical object manifest of the 5-year NG MBO pull on S3
(research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json: key, bytes, sha256 per UTC partition,
every object S3-head-validated) and the CME calendar rule for NG's last trade date (contract_structure.computed_expiry:
3 business days before the first calendar day of the delivery month). No raw byte is read. Greg's answer of 2026-09-29:
the window is the last week of September through October of every year 2021-2026 the data covers, all years treated
alike for selection; the spec role (discovery 2021-2023 / confirmation 2024-2025) is kept on each row as a label only.

A trading day D (Tue or Wed) opens 18:00 ET the prior calendar day and halts 17:00 ET (21:00Z under EDT, all of late
September and October): it takes the post-halt TAIL of the prior UTC partition and the pre-halt HEAD of its own. Both
partitions are listed with their bytes; the measured record counts come from staging (frankie_box_day_facts.sh), never
from bytes.

Per day, every fact is listed on its own (nothing pooled or averaged). The eligibility filters and their tolerances are
arguments, so Greg can change them:
  --window-start MMDD (default 0922: the last week of September) .. --window-end MMDD (default 1031)
  --pre-ltd BD, --post-ltd BD (defaults 5 and 1): a day within [LTD - pre, LTD + post] business days of the last trade
    date of the contract expiring near it is in the ROLL WINDOW (excluded). The volume-continuous series NG.v.0 flips
    to the next contract a few days before the last trade date, and the partitions just before the flip are the fading
    contract (the thin files in the table), so the window is wider on the pre side.
  pairs: the proposed unit is the WEEK PAIR (the Tuesday and Wednesday of one week, both eligible): same front contract,
    same weekly calendar (the Thursday storage print after both), the way days 1 and 2 (Tue 2021-10-05, Wed 2021-10-06)
    were chosen. Reported per day, not a filter (a lone eligible Tuesday stays in).
  --front-month CODE (default X): the day's front contract must be that delivery month (X = November, as for days 1 and
    2). Days that pass every filter are `proposed`; the rest are listed with their reasons.

    python3.12 research/kalshi/frankie_boss/operations/day_selection_candidates.py \
        --out research/kalshi/frankie_boss/blocks/DAY_SELECTION_CANDIDATES_20260929.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'research' / 'kalshi'))
from contract_structure import business_days_between, computed_expiry  # noqa: E402

CANONICAL = REPO / 'research' / 'kalshi' / 'NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json'
CODES = 'FGHJKMNQUVXZ'
ROLE_OF_YEAR = {2021: 'discovery', 2022: 'discovery', 2023: 'discovery', 2024: 'confirmation', 2025: 'confirmation'}
ALREADY_IN = {'20211005': 1, '20211006': 2}     # days 1 and 2 (being ingested 2026-09-29)
# Committed calendar facts about unusual conditions in the window (CLAUDE.md, S97: "the 2025 shutdown suspended COT
# publication Oct 1-Nov 12"). Nothing else is asserted here; box-measured anomalies are added by the day facts.
EVENTS = {(2025, 10): 'US federal shutdown: CFTC COT publication suspended 2025-10-01..11-12 (committed, CLAUDE.md S97)'}
# NYMEX full-closure holidays between Sep 20 and Nov 5 of 2021-2025: none (Labor Day is the first Monday of September,
# Veterans Day is Nov 11; Columbus Day Monday trades: its partitions are full-size in the manifest below).
HOLIDAYS = frozenset()


def ymd(day):
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))


def symbol(year, month):
    return f'NG{CODES[month - 1]}{year % 100:02d}'


def ltd(year, month):
    return dt.date.fromisoformat(computed_expiry(symbol(year, month)))


def contracts_near(day):
    """(the front contract on `day`: the first delivery month whose last trade date is on or after it; the contract
    whose last trade date is nearest to `day`, either side)."""
    months = [(day.year + (day.month - 1 + k) // 12, (day.month - 1 + k) % 12 + 1) for k in range(-1, 4)]
    front = next(m for m in months if ltd(*m) >= day)
    nearest = min(months, key=lambda m: abs((ltd(*m) - day).days))
    return front, nearest


def partition_before(day):
    """The UTC partition that carries `day`'s tail: the prior calendar day's (Monday's for a Tuesday)."""
    prior = day - dt.timedelta(days=1)
    return prior.strftime('%Y%m%d')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--canonical', default=str(CANONICAL))
    p.add_argument('--years', default='2021,2022,2023,2024,2025,2026')
    p.add_argument('--window-start', default='0922')
    p.add_argument('--window-end', default='1031')
    p.add_argument('--pre-ltd', type=int, default=5)
    p.add_argument('--post-ltd', type=int, default=1)
    p.add_argument('--front-month', default='X', help='month code the front contract must carry (X = November)')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    manifest = json.loads(Path(a.canonical).read_bytes())
    objects = {o['key'].split('glbx-mdp3-')[1][:8]: o for o in manifest['canonical_dbn_objects']}
    coverage = dict(approved_range=manifest['approved_range'], last_partition=max(objects),
                    first_partition=min(objects), objects=len(objects), manifest_sha256=manifest['manifest_sha256'])
    rows = []
    for year in [int(y) for y in a.years.split(',')]:
        day = dt.date(year, int(a.window_start[:2]), int(a.window_start[2:]))
        end = dt.date(year, int(a.window_end[:2]), int(a.window_end[2:]))
        while day <= end:
            if day.weekday() in (1, 2):
                key = day.strftime('%Y%m%d')
                tail_key = partition_before(day)
                front, nearest = contracts_near(day)
                front_ltd, near_ltd = ltd(*front), ltd(*nearest)
                bd_to_front = business_days_between(day.isoformat(), front_ltd.isoformat())
                bd_from_nearest = business_days_between(near_ltd.isoformat(), day.isoformat())   # + after, - before
                reasons = []
                parts = []
                for role, pk in (('tail', tail_key), ('head', key)):
                    o = objects.get(pk)
                    parts.append(dict(role=role, partition=pk, key=o['key'] if o else None,
                                      bytes=o['bytes'] if o else None, sha256=o['sha256'] if o else None))
                    if o is None:
                        reasons.append(f'partition {pk} not on S3 (the pull covers {coverage["first_partition"]}..'
                                       f'{coverage["last_partition"]})')
                if -a.pre_ltd <= bd_from_nearest <= a.post_ltd:
                    reasons.append(f'roll window: {bd_from_nearest:+d} business days from {symbol(*nearest)} last trade '
                                   f'{near_ltd} (window {-a.pre_ltd:+d}..{a.post_ltd:+d})')
                if key in HOLIDAYS:
                    reasons.append('holiday')
                if symbol(*front)[2] != a.front_month:
                    reasons.append(f'front contract {symbol(*front)} is not the {a.front_month} month (days 1-2 trade the '
                                   f'{a.front_month} contract)')
                rows.append(dict(
                    day=key, weekday=day.strftime('%a'), year=year, role=ROLE_OF_YEAR.get(year, 'outside the assigned years'),
                    month_window='late September' if day.month == 9 else 'October' if day.month == 10 else day.strftime('%B'),
                    front_contract=symbol(*front), front_last_trade=front_ltd.isoformat(),
                    business_days_to_front_last_trade=bd_to_front,
                    nearest_last_trade=dict(contract=symbol(*nearest), date=near_ltd.isoformat(),
                                            business_days_from=bd_from_nearest),
                    partitions=parts, head_bytes=parts[1]['bytes'], tail_partition_bytes=parts[0]['bytes'],
                    event=EVENTS.get((year, day.month)), already_in=ALREADY_IN.get(key),
                    eligible=not reasons, excluded_because=reasons))
            day += dt.timedelta(days=1)
    by_day = {r['day']: r for r in rows}
    for r in rows:
        d = ymd(r['day'])
        partner = (d + dt.timedelta(days=1 if r['weekday'] == 'Tue' else -1)).strftime('%Y%m%d')
        other = by_day.get(partner)
        r['week_partner'] = partner
        r['week_pair_eligible'] = bool(r['eligible'] and other and other['eligible']
                                       and other['front_contract'] == r['front_contract'])
    day1 = by_day.get('20211005')
    for r in rows:     # a per-day comparison with day 1 (Tue 2021-10-05), never an average over days
        r['head_bytes_vs_day1'] = (round(r['head_bytes'] / day1['head_bytes'], 3)
                                   if day1 and r['head_bytes'] and day1['head_bytes'] else None)
    proposed = [r['day'] for r in rows if r['eligible']]
    partitions = sorted({x['partition'] for r in rows if r['eligible'] for x in r['partitions']})
    keys = {x['partition']: x['key'] for r in rows for x in r['partitions']}
    body = dict(schema='FRANKIE_DAY_SELECTION_CANDIDATES_V1', source='committed canonical object manifest + CME NG '
                'last-trade rule; no raw bytes read', coverage=coverage,
                filters=dict(window=[a.window_start, a.window_end], weekdays=['Tue', 'Wed'],
                             roll_window_business_days=[-a.pre_ltd, a.post_ltd], holidays=sorted(HOLIDAYS),
                             front_month=a.front_month,
                             pair_unit='the Tuesday and Wednesday of one week, both eligible, same front contract'),
                proposed=proposed, proposed_count=len(proposed),
                proposed_partitions=[dict(partition=x, key=keys[x]) for x in partitions],
                presign=' '.join(f"{manifest['bucket']}/{keys[x]}" for x in partitions),
                rows=rows)
    Path(a.out).write_text(json.dumps(body, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    for r in rows:
        print(r['day'], r['weekday'], r['role'][:5], r['front_contract'], f"{r['business_days_to_front_last_trade']:>3}",
              f"{r['nearest_last_trade']['business_days_from']:+4d}", r['tail_partition_bytes'], r['head_bytes'],
              'PAIR' if r['week_pair_eligible'] else ('ok' if r['eligible'] else '--'), '; '.join(r['excluded_because']))
    print('proposed', len(proposed), 'days;', len(partitions), 'partitions')
    return 0


if __name__ == '__main__':
    sys.exit(main())
