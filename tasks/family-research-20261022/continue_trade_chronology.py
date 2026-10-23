"""Trade-first navigation of saved originals; no source retrieval, fits or averaging."""
import csv
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / 'artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1'
OUT = PARENT / 'chronological-lifecycle-v1'


def price_stretches(prices):
    """Maximal equal-price stretches, retaining every individual trade ordinal."""
    stretches, membership = [], []
    for ordinal, price in enumerate(prices):
        if not stretches or stretches[-1]['price_raw'] != price:
            stretches.append(dict(stretch_ordinal=len(stretches), price_raw=price,
                                  first_trade_ordinal=ordinal, last_trade_ordinal=ordinal))
        stretches[-1]['last_trade_ordinal'] = ordinal
        membership.append(len(stretches) - 1)
    for i, stretch in enumerate(stretches):
        incoming = None if i == 0 else stretch['price_raw'] - stretches[i - 1]['price_raw']
        outgoing = None if i + 1 == len(stretches) else stretches[i + 1]['price_raw'] - stretch['price_raw']
        stretch.update(incoming_step_raw=incoming, outgoing_step_raw=outgoing,
                       print_direction_turn=None if incoming is None or outgoing is None
                       else incoming * outgoing < 0)
    return stretches, membership


def sequence_diagnostics(sequences):
    """Diagnose the literal producer test without calling repeats packet loss."""
    return dict(
        literal_one_sequence_per_action=sequences == list(range(sequences[0], sequences[0] + len(sequences))),
        duplicate_adjacent_pairs=[[i, i + 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if a == b],
        forward_jump_pairs=[[i, i + 1, b - a - 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if b > a + 1],
        regression_pairs=[[i, i + 1] for i, (a, b) in enumerate(zip(sequences, sequences[1:])) if b < a])


def jsonrows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            yield json.loads(line)


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def write_rows(name, rows):
    with (OUT / name).open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as handle:
            for row in rows:
                handle.write((json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n').encode())
