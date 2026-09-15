"""Exact readable V2 reductions over the retained V1 context representation."""
import copy
import hashlib
import math
from pathlib import Path
from . import granite_context_stacked as v1

SCHEMA = 'BOSS_GRANITE_NATIVE_STACKED_CONTEXT_V2'
PROMPT_VERSION = 'BOSS_GRANITE_NATIVE_STACKED_PROMPT_V2'
GRAMMAR = v1.GRAMMAR + """
V2 additionally permits integer recipe A: [A,base,scale,recipe] means base+scale*x for each integer x decoded by the V1 recipe. Scale is a positive exact integer. Z: [Z,first,first_delta,recipe] stores second differences: begin with first and first+first_delta, then add each decoded second difference to the previous delta and add that delta to the previous value. In a C table, column [P,earlier_column_index,delta_recipe] equals that earlier named column plus the decoded per-row integer deltas. References may point only to earlier columns in the same table. All values remain exact integers; these are reversible identities, not forecasts, approximations, or omitted observations.
"""
DecodeLimits = v1.DecodeLimits
DEFAULT_LIMITS = v1.DEFAULT_LIMITS

def grammar_hash():
    return hashlib.sha256(GRAMMAR.encode()).hexdigest()

def codec_code_hash():
    return hashlib.sha256(Path(__file__).read_bytes() + v1.codec_code_hash().encode()).hexdigest()

def _best(values):
    choices = [v1._integers(values)]
    if values:
        base = values[0]
        scale = 0
        for value in values:
            scale = math.gcd(scale, value-base)
        if scale > 1:
            choices.append(['A', base, scale, v1._integers([(v-base)//scale for v in values])])
    if len(values) >= 3:
        deltas = [b-a for a,b in zip(values,values[1:])]
        choices.append(['Z',values[0],deltas[0],v1._integers([b-a for a,b in zip(deltas,deltas[1:])])])
    return min(choices,key=lambda node:len(v1._text(node)))

def _ints(node,budget):
    if type(node) is not list or not node:
        raise ValueError('integer recipe required')
    if node[0] == 'A':
        if len(node)!=4 or type(node[1]) is not int or type(node[2]) is not int or node[2]<=1:
            raise ValueError('exact affine integer recipe required')
        values = v1._ints(node[3],budget)
        return [node[1]+node[2]*value for value in values]
    if node[0] == 'Z':
        if len(node)!=4 or type(node[1]) is not int or type(node[2]) is not int:
            raise ValueError('exact second differences required')
        changes = v1._ints(node[3],budget)
        budget.take(2)
        values,delta = [node[1],node[1]+node[2]],node[2]
        for change in changes:
            delta += change
            values.append(values[-1]+delta)
        return values
    return v1._ints(node,budget)

def _tighten(node,limits):
    tag=node[0]
    result=copy.deepcopy(node)
    if tag=='M':
        result[2]=[_tighten(item,limits) for item in node[2]]
    elif tag in ('L','T'):
        result[1]=[_tighten(item,limits) for item in node[1]]
    elif tag=='C':
        columns=[]
        original=[]
        for column in node[3]:
            reduced=_tighten(column,limits)
            values=v1._decode(column,v1._Budget(limits))
            numeric=type(values) is list and all(type(v) is int for v in values)
            if numeric:
                for index,prior in enumerate(original):
                    if prior is not None and len(prior)==len(values):
                        candidate=['P',index,_best([value-base for value,base in zip(values,prior)])]
                        if len(v1._text(candidate))<len(v1._text(reduced)):
                            reduced=candidate
            original.append(values if numeric else None)
            columns.append(reduced)
        result[3]=columns
    elif tag=='S':
        result[3]=_tighten(node[3],limits)
    elif tag=='Q':
        result[2]=[_tighten(item,limits) for item in node[2]]
        result[3]=_best(v1._ints(node[3],v1._Budget(limits)))
    elif tag=='N':
        result[2]=_best(v1._ints(node[2],v1._Budget(limits)))
    elif tag=='B':
        result[3]=[_best(v1._ints(item,v1._Budget(limits))) for item in node[3]]
    return result

def _restore(node,budget,depth=0):
    if depth>budget.limits.max_depth or type(node) is not list or not node or type(node[0]) is not str:
        raise ValueError('invalid V2 node or depth')
    budget.take()
    tag=node[0]
    result=list(node)
    child=lambda item:_restore(item,budget,depth+1)
    if tag=='M' and len(node)==3 and type(node[2]) is list:
        result[2]=[child(item) for item in node[2]]
    elif tag in ('L','T') and len(node)==2 and type(node[1]) is list:
        result[1]=[child(item) for item in node[1]]
    elif tag=='C' and len(node)==4 and type(node[3]) is list:
        columns=[]
        for column in node[3]:
            if type(column) is list and column and column[0]=='P':
                if len(column)!=3 or type(column[1]) is not int or not 0<=column[1]<len(columns):
                    raise ValueError('column reference must point strictly backward')
                prior=v1._decode(columns[column[1]],budget)
                deltas=_ints(column[2],budget)
                if type(prior) is not list or any(type(value) is not int for value in prior) or len(prior)!=len(deltas):
                    raise ValueError('exact integer column dimensions required')
                restored=['N','L',v1._integers([base+delta for base,delta in zip(prior,deltas)])]
            else:
                restored=child(column)
            columns.append(restored)
        result[3]=columns
    elif tag=='S' and len(node)==4:
        result[3]=child(node[3])
    elif tag=='Q' and len(node)==4 and type(node[2]) is list:
        result[2]=[child(item) for item in node[2]]
        result[3]=v1._integers(_ints(node[3],budget))
    elif tag=='N' and len(node)==3:
        result[2]=v1._integers(_ints(node[2],budget))
    elif tag=='B' and len(node)==4 and type(node[3]) is list:
        result[3]=[v1._integers(_ints(item,budget)) for item in node[3]]
    elif tag not in ('V','F','H','X','G'):
        raise ValueError('invalid V2 node')
    return result

def encode_v1(envelope,*,limits=DEFAULT_LIMITS):
    original=v1.decode(envelope,limits=limits)
    result=dict(schema=SCHEMA,prompt_version=PROMPT_VERSION,grammar_sha256=grammar_hash(),
                data=_tighten(envelope['data'],limits))
    if v1._exact(decode(result,limits=limits))!=v1._exact(original):
        raise ValueError('V2 exact inverse differs')
    return result

def encode(value,*,scope_public=None,prefix_seed=None,limits=DEFAULT_LIMITS):
    return encode_v1(v1.encode(value,scope_public=scope_public,prefix_seed=prefix_seed,limits=limits),limits=limits)

def decode(envelope,*,limits=DEFAULT_LIMITS):
    if type(limits) is not DecodeLimits:
        raise ValueError('explicit decoder limits required')
    if (type(envelope) is not dict or set(envelope)!={'schema','prompt_version','grammar_sha256','data'}
            or envelope['schema']!=SCHEMA or envelope['prompt_version']!=PROMPT_VERSION
            or envelope['grammar_sha256']!=grammar_hash()):
        raise ValueError('V2 envelope identity differs')
    if len(v1._text(envelope).encode())>limits.max_input_bytes:
        raise ValueError('V2 input exceeds decoder limit')
    try:
        restored=_restore(envelope['data'],v1._Budget(limits))
        return v1.decode(dict(schema=v1.SCHEMA,prompt_version=v1.PROMPT_VERSION,
            grammar_sha256=v1.grammar_hash(),data=restored),limits=limits)
    except (KeyError,TypeError,IndexError,OverflowError,RecursionError) as error:
        raise ValueError('malformed V2 context') from error
