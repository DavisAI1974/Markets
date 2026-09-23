"""Materialize a pinned shared research catalog on an authorized remote host."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0,str(Path(__file__).resolve().parents[4]))
from research.kalshi.frankie_boss.dipole_shared_knowledge import (
    _catalog, build_snapshot, descriptor, _put, _canonical)

def materialize(catalog_path, expected_catalog_sha256, destination, *, fetch=None):
    raw=Path(catalog_path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_catalog_sha256:
        raise ValueError('shared catalog file differs from independent pin')
    catalog=_catalog(json.loads(raw))
    def resolve(entry):
        if entry['provenance'].get('repository')!='DavisAI1974/Markets' or not re.fullmatch('[0-9a-f]{40}',entry['revision']):
            raise ValueError('shared source requires an immutable approved repository commit')
        url='https://raw.githubusercontent.com/DavisAI1974/Markets/'+entry['revision']+'/'+entry['path']
        if fetch is not None:
            return fetch(url)
        with urllib.request.urlopen(url,timeout=60) as response:
            data=response.read(entry['bytes']+1)
        return data
    # build_snapshot collects every deficiency and never publishes a partial manifest.
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={entry['id']:pool.submit(resolve,entry) for entry in catalog['sources']}
        snapshot=build_snapshot(catalog,lambda entry:futures[entry['id']].result(),destination)
    value=descriptor(snapshot)
    _put(Path(destination)/'DESCRIPTOR.json',_canonical(value))
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',required=True)
    parser.add_argument('--catalog-sha256',required=True)
    parser.add_argument('--destination',required=True)
    args=parser.parse_args()
    value=materialize(args.catalog,args.catalog_sha256,args.destination)
    print(json.dumps(dict(status='complete',snapshot_hash=value['snapshot_hash'],
        sources=len(value['sources']),bytes=sum(x['bytes'] for x in value['sources']),
        descriptor=str(Path(args.destination)/'DESCRIPTOR.json')),sort_keys=True))

if __name__=='__main__':
    main()
