"""Extract existing Native records; never invoke a producer or rewrite a seal."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re


def extract(root, output):
    output.mkdir(parents=True, exist_ok=False)
    stage = json.loads((root / 'work/native-stage.json').read_text())
    source = next(a for a in stage['artifacts'] if a['path'].endswith('/exact_lifecycle_rows.jsonl'))
    digest = hashlib.sha256()
    counts = Counter()
    selected = Counter()
    with Path(source['path']).open('rb') as stream, gzip.open(output / 'native-research-records.jsonl.gz', 'wb') as dest:
        for line in stream:
            digest.update(line)
            match = re.search(rb'"emitting_section":"([^"]+)"', line)
            section = match[1].decode() if match else 'missing'
            counts[section] += 1
            if section in ('episode', 'candidate', 'flow_substrate'):
                dest.write(line)
                selected[section] += 1
    assert digest.hexdigest() == source['sha256'], 'sealed lifecycle digest mismatch'
    result_path = next(a['path'] for a in stage['artifacts'] if a['path'].endswith('/result.json'))
    result = json.loads(Path(result_path).read_text())
    receipt = dict(source=source, sections=dict(counts), selected=dict(selected),
                   candidate_detection=result['traversal']['candidate_detection'],
                   candidate_episodes=result['traversal']['candidate_episodes'],
                   output_sha256=hashlib.sha256((output / 'native-research-records.jsonl.gz').read_bytes()).hexdigest())
    (output / 'source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(root=str(root), selected=dict(selected), sections=dict(counts))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    extract(args.root, args.output)
