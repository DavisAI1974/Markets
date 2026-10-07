"""Exact existing-cutoff market context for governed adviser inputs.

The full reader remains owner-local. This module selects no target extrema or new
scientific window and never reads answers, grades, claims or private reasoning.
"""
import copy
import hashlib
import json
from pathlib import Path

SCHEMA = 'FRANKIE_ADVISER_MARKET_CONTEXT_V1'


class AdviserMarketContext:
    def __init__(self, identity, *, day, source_hash, as_of, through_cursor):
        from frankie_box_market_timeline import SharedMarketTimeline, _json
        self.root = Path(identity['calculations']['path']).parent
        self.day = str(day)
        self.reader = SharedMarketTimeline(self.root, day=self.day, workers=15)
        if self.reader.identity != identity:
            raise ValueError('adviser source differs from the shared market reader identity')
        ingestion = _json(self.reader.source['ingestion_receipt'])
        if (ingestion['source_prefix_hash'] != source_hash
                or ingestion['record_count'] - 1 != through_cursor
                or type(as_of) is not int or type(through_cursor) is not int):
            raise ValueError('adviser cutoff differs from the original complete sealed source scope')
        self.scope = dict(day=self.day, source_hash=source_hash, as_of=as_of, through_cursor=through_cursor)

    def read(self, *, check_save=lambda: None):
        from frankie_box_classroom_code import _exact_market_text
        selected = None
        stream = self.reader.iter_pictures()
        try:
            for item in stream:
                check_save()
                picture = item['picture']
                at = picture['at']
                if at['adapter_cursor'] == self.scope['through_cursor'] and item['evidence'] is not None:
                    if selected is not None:
                        raise ValueError('adviser cutoff has more than one original applied picture')
                    if (type(at['ts_recv_ns']) is not int or at['ts_recv_ns'] > self.scope['as_of']
                            or at['publication_frontier_ns'] > self.scope['as_of']):
                        raise ValueError('adviser cutoff would expose a later receive/publication state')
                    selected = copy.deepcopy(picture)
        finally:
            stream.close()
        if not self.reader.report['complete'] or selected is None:
            raise ValueError('adviser context needs the complete source and its exact original applied cutoff')
        text = _exact_market_text(selected)
        return dict(schema=SCHEMA, identity=self.reader.identity, scope=self.scope,
            at=selected['at'], picture_text=text,
            picture_sha256=hashlib.sha256(text.encode()).hexdigest(),
            report=copy.deepcopy(self.reader.report),
            reader=dict(module='frankie_box_market_timeline', interface='SharedMarketTimeline.iter_pictures',
                        calculations=str(self.root), day=self.day, identity=self.reader.identity),
            use='complete same-time picture at the existing original source cutoff; no target-derived selection',
            limit='model receives this complete cutoff picture, not every historical picture; full ordered reader remains '
                  'available to owner code; no time-addressable model query protocol or new scientific calculation')

    def iter_pictures(self):
        """Full exact owner-local history; never silently replace it with the cutoff snapshot."""
        from frankie_box_market_timeline import SharedMarketTimeline
        reader = SharedMarketTimeline(self.root, day=self.day, workers=15)
        if reader.identity != self.reader.identity:
            raise ValueError('adviser full history changed from its original selected source')
        yield from reader.iter_pictures()


def from_teacher(rows_path, day, measure):
    """Use only the teacher's already explicit source/as-of/cursor, never its answers."""
    receipt_path = Path(rows_path).parent / 'receipt.json'
    if not receipt_path.is_file():
        return None
    receipt = json.loads(receipt_path.read_bytes())
    identity = receipt.get('shared_market_identity')
    if identity is None:
        return None  # Historical nonshared sources keep their actual scope.
    if (measure is None or str(receipt.get('day')) != str(day)
            or receipt.get('rows_file', {}).get('sha256') != measure['sha256']
            or any(receipt.get(k) != measure[k] for k in ('as_of', 'through_cursor'))):
        raise ValueError('shared exchange context requires its exact teacher source')
    ingestion_pin = receipt['ingestion_receipt']
    raw = Path(ingestion_pin['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ingestion_pin['sha256']:
        raise ValueError('shared teacher ingestion receipt changed')
    reader = AdviserMarketContext(identity, day=day, source_hash=json.loads(raw)['source_prefix_hash'],
        as_of=measure['as_of'], through_cursor=measure['through_cursor'])
    return reader.read()


def text(context):
    if (context.get('schema') != SCHEMA
            or hashlib.sha256(context['picture_text'].encode()).hexdigest() != context['picture_sha256']
            or context['report'].get('complete') is not True):
        raise ValueError('adviser market context differs from its complete retained picture')
    return ('Complete shared market picture at the original explicit cutoff. '
            + context['use'] + '. ' + context['limit'] + '\n'
            + json.dumps(context['scope'], sort_keys=True) + '\n' + context['picture_text'])
