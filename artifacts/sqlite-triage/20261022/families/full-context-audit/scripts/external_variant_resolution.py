"""Conservative as-of revision resolution, preserving every opposing version.

The pinned current source is the reference when already available. Alternatives
stay explicit; unranked disagreement does not acquire a fabricated winner.
"""
import hashlib
import json


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def occurrence_identity(point,scope,source_published_ns,event_ns,same_stamp_position):
    """A coordinate, never a numeric predictor; retains coincident message order.

    Source versions may still disagree on a position's payload. Those versions
    require explicit conflict handling; no exchange sequence is fabricated.
    """
    assert type(source_published_ns) is int and type(same_stamp_position) is int and same_stamp_position>=0
    return hashlib.sha256(canonical([point,scope,source_published_ns,event_ns,same_stamp_position]).encode()).hexdigest()


def resolve(variants,cutoff):
    known=[r for r in variants if r['available_ns']<=cutoff]
    if not known:return None
    primary=[r for r in known if r.get('primary_ordinal') is not None]
    chosen=max(primary,key=lambda r:(r['available_ns'],r['primary_ordinal'])) if primary else None
    numbers={};states={};alternatives={};categories={}
    numeric_fields=sorted(set().union(*(r['numeric'] for r in known)))
    category_fields=sorted(set().union(*(r['categories'] for r in known)))
    for field in numeric_fields:
        emitted=[r for r in known if field in r['numeric']]
        alternatives[field]=dict(finite_values=sorted({r['numeric'][field] for r in emitted if r['numeric'][field] is not None}),
            states=sorted({r['states'][field] for r in emitted}),emitting_variants=len(emitted),
            absent_in_variants=len(known)-len(emitted))
        if chosen is not None:
            numbers[field]=chosen['numeric'].get(field)
            states[field]=chosen['states'].get(field,'SOURCE_FIELD_ABSENT_IN_PRIMARY')
        elif len(emitted)==len(known) and len({canonical([r['numeric'][field],r['states'][field]]) for r in emitted})==1:
            numbers[field]=emitted[0]['numeric'][field];states[field]=emitted[0]['states'][field]
        else:
            numbers[field]=None;states[field]='CONFLICTING_SOURCE_VARIANTS'
    for field in category_fields:
        values={canonical(r['categories'][field]) for r in known if field in r['categories']}
        if chosen is not None:
            categories[field]=chosen['categories'].get(field,{'state':'SOURCE_FIELD_ABSENT_IN_PRIMARY'})
        elif len(values)==1 and all(field in r['categories'] for r in known):
            categories[field]=json.loads(next(iter(values)))
        else:categories[field]={'state':'CONFLICTING_SOURCE_VARIANTS','alternatives':[json.loads(v) for v in sorted(values)]}
    return dict(numeric=numbers,states=states,categories=categories,alternatives=alternatives,
                selected_primary_sha256=chosen['normalized_sha256'] if chosen else None,
                known_variant_sha256=sorted({r['normalized_sha256'] for r in known}),
                known_ns=max(r['available_ns'] for r in known),variant_count=len(known))
