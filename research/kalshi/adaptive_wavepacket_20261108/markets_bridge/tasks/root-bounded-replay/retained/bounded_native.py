import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'deploy/aws/box'), str(HERE / 'research/kalshi')]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('day')
    parser.add_argument('work', type=Path)
    parser.add_argument('root_result', type=Path)
    args = parser.parse_args()
    import frankie_box_bedrock as native
    import frankie_box_boss_session as root

    # Reuse ROOT's witnessed input spool rather than extracting the journal a second time.
    receipt = json.loads((args.root_result / 'work/derive.json').read_bytes())
    container = receipt['rows']
    spool = container['record_spool']
    path = Path(spool['path'])
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != spool['sha256'] or path.stat().st_size != spool['bytes']:
        raise ValueError('sealed ROOT input spool has changed')
    records = root._reopen_counted_spool(native.RowSpool, path, receipt['input_records'])
    if len(records) != receipt['input_records']:
        raise ValueError('ROOT and Native input counts differ')
    result = native.run(root.NativeInputView(records), container, args.work,
                        HERE / 'producers', '00', native.PIN_COMMIT, args.day,
                        recovery=True)
    print(json.dumps(dict(ledgers=result['ledgers'], reconciliation=result.get('reconciliation')), indent=2))

if __name__ == '__main__':
    main()