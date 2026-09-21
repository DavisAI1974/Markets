"""The comparison packet (Frankie's own ask, cycle 0 analysis section 4, 2026-09-21): every derived pin layer beside the
frozen learned-structure files, so the accounting entry can carry `compared` (with what differed) instead of `derived`
only. Cycle 0's accounting listed every layer as derived because the frozen learned structure was delivered BY PATH only
(the request's knowledge table names the files and 12-char digests); Greg's "unfreeze the structure content" made the
brain carry those files (frankie_box_brain.write_frozen_entry), and this packet puts each frozen layer's files, digests
and shape next to each derived layer's status, digest and size. The judgement of what corresponds to what and what
differs is Frankie's, in his accounting entry; this packet is observed fact only (nothing here compares by opinion).

Pure functions; the session writes work/comparison.json and work/comparison.md and puts the Markdown into the writing
base. No torch, stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

SCHEMA = 'FRANKIE_BOX_COMPARISON_V1'
FROZEN_DIR = 'frozen-learned-structure'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def summarize_content(name, data, limit=40):
    """What a frozen file is, from its bytes: JSON shape (top-level type, keys with lengths), Markdown headings, or size."""
    out = dict(bytes=len(data))
    text = data.decode('utf-8', errors='replace')
    if name.endswith('.json'):
        try:
            value = json.loads(text)
        except Exception as error:
            out.update(kind='json (unparseable: %s)' % type(error).__name__)
            return out
        if isinstance(value, dict):
            out.update(kind='json object', keys=[dict(key=k, type=type(v).__name__, length=(len(v) if hasattr(v, '__len__') and not isinstance(v, str) else None))
                                                  for k, v in list(value.items())[:limit]], key_count=len(value))
        elif isinstance(value, list):
            out.update(kind='json array', length=len(value), first_keys=(sorted(value[0])[:limit] if value and isinstance(value[0], dict) else None))
        else:
            out.update(kind='json ' + type(value).__name__)
        return out
    if name.endswith('.md'):
        heads = [line.strip() for line in text.splitlines() if line.startswith('#')]
        out.update(kind='markdown', lines=text.count('\n') + 1, headings=heads[:limit], heading_count=len(heads))
        return out
    out.update(kind='text' if text.isprintable() or '\n' in text else 'binary', lines=text.count('\n') + 1)
    return out


def derived_layers(work):
    """Every pin layer of derive.json with its status, producer, reason, digest and the count the derived file carries."""
    work = Path(work)
    receipt = json.loads((work / 'derive.json').read_bytes())
    layers = {}
    for name, entry in receipt['layers'].items():
        item = dict(status=entry.get('status'), producer=entry.get('producer'), reason=entry.get('reason'), sha256=entry.get('sha256'), bytes=entry.get('bytes'))
        path = work / 'derived' / f'{name}.json'
        if path.is_file():
            try:
                value = json.loads(path.read_bytes())
                if isinstance(value.get('count'), int):
                    item['count'] = value['count']
                else:
                    for key in ('series', 'per_second', 'frames', 'groups'):
                        if isinstance(value.get(key), list):
                            item['count'] = len(value[key])
                            break
                item['fields'] = sorted(k for k in value if k not in ('status', 'producer', 'reason'))[:30]
            except Exception:
                pass
        layers[name] = item
    return dict(pin_group=receipt.get('pin_group'), rows=receipt.get('rows', {}).get('count'), input_records=receipt.get('input_records'),
                f_last_groups=receipt.get('f_last_groups'), failures=receipt.get('failure_count'), layers=layers)


def frozen_layers(brain, names):
    """{layer: [file entries]} from the brain's frozen entry manifest, every named layer present (empty when nothing was
    delivered for it), each entry with the delivered digest prefix, the checkout digest, include/reason and a content summary."""
    brain = Path(brain)
    manifest_path = brain / FROZEN_DIR / 'MANIFEST.json'
    result = {name: [] for name in names}
    if not manifest_path.is_file():
        return result, None
    manifest = json.loads(manifest_path.read_bytes())
    for e in manifest.get('entries', []):
        entry = dict(source=e.get('source'), delivered_prefix=e.get('delivered_prefix'), sha256=e.get('sha256'), bytes=e.get('bytes'),
                     include=bool(e.get('include')), reason=e.get('reason'))
        path = brain / FROZEN_DIR / e.get('name', '')
        if e.get('include') and path.is_file():
            data = path.read_bytes()
            if sha256_bytes(data) == e.get('sha256'):
                entry['content'] = summarize_content(e.get('source', ''), data)
            else:
                entry['content'] = dict(kind='changed since its manifest; not summarized')
        for layer in e.get('layers', []):
            result.setdefault(layer, []).append(entry)
    return result, dict(at=manifest.get('at'), historical_prompt=manifest.get('historical_prompt'), layers=manifest.get('layers'))


def build(work, brain, frozen_names):
    derived = derived_layers(work)
    frozen, manifest = frozen_layers(brain, frozen_names)
    delivered = sum(len(v) for v in frozen.values())
    carried = sum(1 for v in frozen.values() for e in v if e['include'])
    return dict(schema=SCHEMA, at=time.time(), derived=derived, frozen=frozen, frozen_manifest=manifest,
                counts=dict(pin_layers=len(derived['layers']), derived=sum(1 for v in derived['layers'].values() if v['status'] == 'derived'),
                            frozen_layers=len(frozen_names), frozen_files_delivered=delivered, frozen_files_carried=carried))


def render(report):
    d, c = report['derived'], report['counts']
    lines = ['# Comparison packet (written by the session code; observed facts for the accounting entry\'s `compared` status)', '',
             'The frozen learned structure was delivered by path only; its files are now carried in the corpus (Frankie\'s brain, frozen '
             'learned structure; each file whole, verified against the delivered digest). This packet puts every derived pin layer beside '
             'the frozen files each learned-structure layer names. WHAT CORRESPONDS TO WHAT AND WHAT DIFFERS IS YOUR JUDGEMENT: for each '
             'pin layer, compare its derivation (the tables in the derivation digest) with the frozen content that speaks to the same '
             'observable, and file `compared` with what differed, or `could_not` with the reason, in the accounting entry.', '',
             f'Pin group {d["pin_group"]}: {c["pin_layers"]} layers, {c["derived"]} derived, on {d["input_records"]} INPUT records '
             f'({d["rows"]} entries; {d["f_last_groups"]} F_LAST groups; {d["failures"]} adapter failures). Frozen learned structure: '
             f'{c["frozen_layers"]} layers, {c["frozen_files_delivered"]} file references, {c["frozen_files_carried"]} files carried whole.', '',
             '## Derived pin layers (this cycle, this session)', '', '| layer | status | count | sha256 | producer | reason |', '|---|---|---:|---|---|---|']
    for name, v in d['layers'].items():
        lines.append(f'| {name} | {v["status"]} | {v.get("count", "")} | {(v.get("sha256") or "")[:16]} | {v.get("producer") or ""} | {v.get("reason") or ""} |')
    lines += ['', '## Frozen learned-structure layers and the files they name', '']
    for layer, entries in report['frozen'].items():
        lines.append(f'### {layer}')
        if not entries:
            lines += ['', 'no file delivered for this layer (nothing to compare against by content; say so in the accounting entry)', '']
            continue
        lines += ['', '| file | delivered digest | checkout sha256 | bytes | carried | content |', '|---|---|---|---:|---|---|']
        for e in entries:
            content = e.get('content') or {}
            shape = content.get('kind', '')
            if content.get('keys'):
                shape += ': ' + ', '.join(f'{k["key"]}[{k["length"]}]' if k['length'] is not None else k['key'] for k in content['keys'][:12])
            elif content.get('headings'):
                shape += ': ' + ' / '.join(h[:60] for h in content['headings'][:8])
            elif 'length' in content:
                shape += f' of {content["length"]}'
            carried = 'yes' if e['include'] else f'no ({e.get("reason") or "excluded"})'
            lines.append(f'| {e["source"]} | {e["delivered_prefix"]} | {(e.get("sha256") or "")[:16]} | {e.get("bytes") or ""} | {carried} | {shape} |')
        lines.append('')
    return '\n'.join(lines) + '\n'


def write(work, brain, frozen_names):
    work = Path(work)
    report = build(work, brain, frozen_names)
    (work / 'comparison.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    (work / 'comparison.md').write_text(render(report), encoding='utf-8')
    return report
