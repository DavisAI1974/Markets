"""Restore the existing pilot archive on AWS; credentials remain in private SSM parameters."""
import pathlib,json,hashlib,gzip,shutil,urllib.request,boto3,concurrent.futures
root=pathlib.Path('C:/Codex/Frankie-BOSS-20260919/delivery-plain');root.mkdir(parents=True,exist_ok=True)
receipt=json.loads(pathlib.Path('C:/Codex/Frankie-BOSS-20260919/retained-principal/delivery_receipt.json').read_bytes())
ssm=boto3.client('ssm',region_name='us-east-2')
objects=[{"name":"exact_lifecycle_rows.jsonl.gz","key":"nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1/ledgers/exact_lifecycle_rows.jsonl.gz","bytes":25581893,"param":"/markets/frankie/ledger-get-20260919/exact_lifecycle_rows-jsonl-gz"},{"name":"exact_member_rows.jsonl.gz","key":"nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1/ledgers/exact_member_rows.jsonl.gz","bytes":1705613663,"param":"/markets/frankie/ledger-get-20260919/exact_member_rows-jsonl-gz"},{"name":"legacy_observable_rows.jsonl.gz","key":"nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1/ledgers/legacy_observable_rows.jsonl.gz","bytes":2198595,"param":"/markets/frankie/ledger-get-20260919/legacy_observable_rows-jsonl-gz"},{"name":"small_artifacts.tar.gz","key":"nymex/ng_mbo_5y_v0/frankie/raw_mbo_benchmark/a-memory/full/7d0068d8ae720772415bf84c8c0689e84408d642/33746436209-1/small_artifacts.tar.gz","bytes":760560,"param":"/markets/frankie/ledger-get-20260919/small_artifacts-tar-gz"}]
def restore(row):
 target=root/row['name']
 if not target.exists():
  url=ssm.get_parameter(Name=row['param'],WithDecryption=True)['Parameter']['Value']
  partial=root/(row['name']+'.partial')
  if partial.exists():raise ValueError('preserve ambiguous transfer partial '+row['name'])
  with urllib.request.urlopen(url,timeout=300) as source,partial.open('xb') as out:
   while chunk:=source.read(4*1024*1024):out.write(chunk)
  if partial.stat().st_size!=row['bytes']:raise ValueError('compressed size differs')
  partial.rename(target)
 if target.stat().st_size!=row['bytes']:raise ValueError('retained compressed size differs')
 match=[v for v in receipt['ledgers'].values() if v['object']==row['name']]
 if match:
  ledger=match[0];plain=root/ledger['file']
  if not plain.exists():
   partial=root/(ledger['file']+'.partial')
   if partial.exists():raise ValueError('preserve ambiguous decoded partial')
   digest=hashlib.sha256();count=0
   with gzip.open(target,'rb') as source,partial.open('xb') as out:
    while chunk:=source.read(4*1024*1024):
     out.write(chunk);digest.update(chunk);count+=len(chunk)
   if count!=ledger['plain_bytes_expected'] or digest.hexdigest()!=ledger['plain_sha256_expected']:raise ValueError('archived plaintext differs')
   partial.rename(plain)
  else:
   with plain.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
   if plain.stat().st_size!=ledger['plain_bytes_expected'] or digest!=ledger['plain_sha256_expected']:raise ValueError('retained plaintext differs')
 print(json.dumps({'phase':'archived_ledger_restored','name':row['name'],'verified':True}),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(restore,objects))
target=root/'calculation_result.json'
if not target.exists():shutil.copyfile('E:/Codex/Frankie-BOSS-20260915/delivery-plain/calculation_result.json',target)
with target.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
assert actual==receipt['objects']['calculation_result.json']['sha256_expected']
print('ARCHIVED_INPUT_DELIVERY_VERIFIED',flush=True)
